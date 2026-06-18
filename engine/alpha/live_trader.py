"""AutonomousTrader — the single live trading path.

Runs the validated V3 signal engine (`strategy_v3.SignalEngine`) directly on
live Delta candles and places REAL orders. No paper account, no mirror copy
step: the strategy brain and the executor are one loop now.

Per-confidence leverage (user call, 06-13 — never 100x, it blew the account):
    conf 85–91  → 10x
    conf 92–96  → 25x
    conf 97+    → 50x
A liquidation safety guard steps the tier DOWN if 50x/25x would put the 1.6×ATR
stop outside the liquidation price (so the stop always fires before liquidation).

Sizing & rails ($13 real account):
    * $5 margin/trade (hard cap ~$8 when 1 contract rounds above $5)
    * max 2 open positions, one per asset (BTC + ETH)
    * daily realized loss <= DAILY_LOSS_STOP → no new entries until UTC midnight
    * balance < KILL_BALANCE → stand down
    * exits = the validated V3 engine (ATR stop, breakeven ratchet, tightening
      chandelier trail, stagnation/no-traction purge, 24h max)

Manual Delta trades are still adopted (`adopt_manual`) and managed to the same
exits but with NO impatience purges and a liquidation-aware stop — a human took
that trade on purpose, so ride it, don't churn it.

Rows are tagged `strategy='live_mirror'` for history/dashboard/reconciler
continuity (the stable DB key for "the live path"). On boot we re-attach to any
open rows rather than closing real positions.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from alpha.strategy_v3 import SignalEngine, _atr_rows
from alpha.utils import setup_logger

logger = setup_logger("live_trader")

CONTRACT_SIZE: dict[str, float] = {"BTC": 0.001, "ETH": 0.01}

# Liquid majors the scanner hunts across (resolved against the exchange's live
# perp list at start — anything Delta doesn't list is dropped). The trader still
# only opens MAX_OPEN at a time, picking the best setup anywhere in this set.
MAJOR_BASES: list[str] = [
    "BTC", "ETH", "SOL", "XRP", "DOGE", "AVAX", "LINK", "BNB", "ADA", "LTC", "SUI", "AAVE",
]
STRATEGY_TAG = "live_mirror"   # stable DB key for the live path (history continuity)


@dataclass
class Position:
    pair: str
    direction: str               # long | short
    contracts: float
    csize: float
    entry: float
    atr: float
    stop: float
    margin: float
    leverage: float
    row_id: int | None = None
    pending_row: dict[str, Any] | None = None
    peak_price: float = 0.0
    peak_pnl_pct: float = 0.0
    be_locked: bool = False
    opened_mono: float = 0.0
    is_manual: bool = False
    liq: float = 0.0
    confidence: float | None = None   # entry confidence (persisted through manage updates)
    htf_trend: int | None = None
    lane: str = ""

    @property
    def is_long(self) -> bool:
        return self.direction == "long"


class AutonomousTrader:
    POLL_SEC = 12
    # Sized for the live ~$4.77 account (user 06-19: "take it live, whatever we
    # have"). $4 money-in, one trade at a time (can't fund two), trade down to $2.
    MARGIN_USD = 4.0
    MARGIN_HARD_CAP = 4.5         # never try a trade that needs more than we have
    MAX_OPEN = 1                  # only ~$4.77 — one position at a time
    # Trades ONLY these (the edge). The rest of the scan universe is watch-only —
    # shown on the board but the bot won't open trades on them (user 06-14:
    # "it's firing everywhere — keep these 5 as trading pairs, pause the rest").
    TRADE_BASES = {"BTC", "ETH", "SOL", "XRP", "DOGE"}
    TAKER_FEE = 0.0005
    DAILY_LOSS_STOP = -3.0
    KILL_BALANCE = 2.0           # trade down to $2 on the small live account
    # confidence → leverage tiers (never 100x)
    LEV_TIERS = ((97.0, 50.0), (92.0, 25.0), (0.0, 10.0))   # (min_conf, leverage), high→low
    LIQ_SAFETY = 0.85            # the 1.6×ATR stop must sit within this fraction of the liq distance
    # V3 exit engine (identical constants to the validated lanes)
    STOP_ATR_MULT = 1.6
    BREAKEVEN_ATR = 1.2
    PROFIT_LOCK_FRAC = 0.4
    TRAIL_ARM_ATR = 1.0
    TRAIL_ATR_MULT = 1.8
    TRAIL_TIGHT_1_PEAK = 15.0
    TRAIL_TIGHT_1_MULT = 1.2
    TRAIL_TIGHT_2_PEAK = 30.0
    TRAIL_TIGHT_2_MULT = 0.8
    STAGNATION_SEC = 75 * 60
    STAGNATION_ATR = 0.5
    NO_TRACTION_SEC = 60 * 60
    NO_TRACTION_ATR = 0.4
    MAX_HOLD_SEC = 24 * 60 * 60
    # ── profit harvest (06-15) ────────────────────────────────────────────
    # We keep hitting +7-13% peaks (Donchian/EMA find the move) but hand them
    # back to breakeven. The old PEAK-based floor lagged on the 12s loop: by the
    # time it armed, price had retraced below the floor → stop above market →
    # instant breakeven exit. Fix: harvest off the CURRENT gain (always ≤ price,
    # so no lag trap), ratcheting UP. Above +5% lock most of what's on the table.
    PROFIT_ARM_PCT = 4.0           # start harvesting above +4% — capture a bit earlier/closer
    PROFIT_KEEP_FRAC = 0.65        # lock 65% of the CURRENT gain (ratchet up only)
    PROFIT_TAKE_PCT = 18.0         # hard-bank a big spike outright
    # ── hard loss cap (06-16) ─────────────────────────────────────────────
    # The losers all NEVER peaked (0→−20, +4→−28): no harvest protection, so
    # they rode the ATR stop down AND slipped past it on fast 25x moves (the 12s
    # loop). Cap the per-trade loss in MARGIN terms, checked every tick, so one
    # non-peaking trade can't erase a day. Autonomous only; manual rides to liq.
    MAX_LOSS_PCT = -12.0           # close immediately at −12% margin (~−$0.60)
    # ── fee-aware breakeven (06-13 fix) ───────────────────────────────────
    # Round-trip taker fee = 0.1% of NOTIONAL → on BTC that's a ~0.1% price
    # move (~$64) just to break even, independent of leverage. The old lock
    # armed at +0.4 ATR and floored the stop at the fee distance — which sat
    # ABOVE market when the move was smaller than fees, stopping out instantly
    # and booking a gross < fees (live #3713: +$0.12 gross, −$0.14 net). So:
    # never arm the breakeven lock until the trade has actually moved past the
    # fee threshold, and lock at a level that clears fees WITH profit.
    BE_FEE_ARM_MULT = 1.6     # arm BE only once peak move ≥ 1.6× round-trip fee distance
    LOCK_FEE_FLOOR_MULT = 1.3 # locked stop always covers ≥ 1.3× fees (real net profit)
    # manual-trade tuning (user, 06-13: "I take the trade — let it keep doing
    # what it wants, don't be trigger-happy; only cut if it REALLY goes bad").
    # → RIDE to near liquidation, LET WINNERS RUN. No breakeven cut, no early
    #   trail. The only downside exit is the liquidation-pad stop; the trail
    #   only arms after a genuine multi-ATR run and trails LOOSE so it protects
    #   a real winner without ever cutting near breakeven.
    MANUAL_STOP_ATR = 8.0          # wide fallback when exchange liq is unknown
    MANUAL_LIQ_PAD_ATR = 0.3       # downside stop = liquidation + this pad
    MANUAL_TRAIL_ARM_ATR = 3.0     # don't protect until +3 ATR in profit (a real winner)
    MANUAL_TRAIL_MULT = 2.5        # then trail loosely, 2.5 ATR behind the peak

    def __init__(
        self,
        exchange: Any,
        db: Any,
        alerts: Any,
        balance_fn: Callable[[], Awaitable[float | None]],
        pairs: list[str] | None = None,
    ) -> None:
        self.exchange = exchange
        self.db = db
        self.alerts = alerts
        self.balance_fn = balance_fn
        # Desired universe as base assets; resolved to live perp symbols in start().
        # Accepts bases ("BTC") or full symbols ("BTC/USD:USD").
        self._desired_bases = [str(b).split("/")[0].upper() for b in (pairs or MAJOR_BASES)]
        self.pairs: list[str] = []
        self.engines: dict[str, SignalEngine] = {}
        self.is_active = False
        self.user_paused = False
        self._task: asyncio.Task[None] | None = None
        self._killed = False
        self._daily_realized = 0.0
        self._daily_date = ""
        self._positions: dict[str, Position] = {}

    # ── universe / contract size ───────────────────────────────────────
    def _csize(self, pair: str) -> float | None:
        """Contract size for a pair — exchange truth first, hardcoded fallback."""
        try:
            m = (getattr(self.exchange, "markets", None) or {}).get(pair) or {}
            cs = float(m.get("contractSize") or 0)
            if cs > 0:
                return cs
        except Exception:
            pass
        return CONTRACT_SIZE.get(pair.split("/")[0])

    async def _resolve_universe(self) -> None:
        """Resolve desired base assets → live USD-perp symbols Delta actually lists."""
        markets = getattr(self.exchange, "markets", None)
        if not markets:
            try:
                markets = await self.exchange.load_markets()
            except Exception:
                markets = {}
        pairs: list[str] = []
        for base in self._desired_bases:
            sym = f"{base}/USD:USD"
            m = (markets or {}).get(sym) or {}
            is_perp = bool(m.get("swap") or m.get("contract")) and m.get("active", True) is not False
            if m and is_perp:
                pairs.append(sym)
            elif base in ("BTC", "ETH"):
                pairs.append(sym)   # always keep the core two even if markets didn't load
        # de-dup, keep order
        seen: set[str] = set()
        self.pairs = [p for p in pairs if not (p in seen or seen.add(p))]
        self.engines = {p: SignalEngine(p, self.exchange) for p in self.pairs}

    # ── lifecycle ──────────────────────────────────────────────────────
    async def start(self) -> None:
        if self.is_active:
            return
        self.is_active = True
        await self._resolve_universe()
        await self._reattach()
        bases = ", ".join(p.split("/")[0] for p in self.pairs)
        logger.warning(
            "🔴 AutonomousTrader ACTIVE — real money. $%.0f/trade · 10/25/50x by conf · "
            "max %d open · day stop $%.2f · kill <$%.2f · scanning %d: %s",
            self.MARGIN_USD, self.MAX_OPEN, self.DAILY_LOSS_STOP, self.KILL_BALANCE, len(self.pairs), bases,
        )
        try:
            await self.alerts._send(
                "🔴 <b>LIVE TRADER ACTIVE — real money</b>\n"
                f"${self.MARGIN_USD:.0f}/trade · 10/25/50x by confidence · max {self.MAX_OPEN} open\n"
                f"Day stop −${abs(self.DAILY_LOSS_STOP):.0f} · kill &lt;${self.KILL_BALANCE:.0f}\n"
                f"Scanning {len(self.pairs)} futures: {bases}",
                allow_in_quiet=True,
            )
        except Exception:
            pass
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        # Live positions are real and persist on the exchange — never close on
        # shutdown; we re-attach on next boot.
        self.is_active = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self) -> None:
        while self.is_active:
            try:
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("AutonomousTrader tick failed")
            await asyncio.sleep(self.POLL_SEC)

    # ── boot re-attach ─────────────────────────────────────────────────
    async def _reattach(self) -> None:
        loop = asyncio.get_running_loop()

        def q() -> list[dict[str, Any]]:
            try:
                return (
                    self.db.client.table("trades").select("*")
                    .eq("strategy", STRATEGY_TAG).eq("status", "open")
                    .order("opened_at", desc=True).limit(10).execute().data or []
                )
            except Exception:
                return []

        rows = await loop.run_in_executor(None, q)
        for r in rows:
            pair = r["pair"]
            if pair in self._positions:
                continue
            meta = r.get("metadata") or {}
            direction = r.get("position_type") or ("long" if r.get("side") == "buy" else "short")
            entry = float(r.get("entry_price") or 0)
            opened_mono = asyncio.get_running_loop().time() - max(
                0.0,
                (datetime.now(timezone.utc) - datetime.fromisoformat(str(r["opened_at"]).replace("Z", "+00:00"))).total_seconds(),
            )
            pos = Position(
                pair=pair,
                direction=direction,
                contracts=float(r.get("contracts") or r.get("amount") or 0),
                csize=float(meta.get("contract_size") or self._csize(pair) or 0.001),
                entry=entry,
                atr=float(meta.get("atr") or 0),
                stop=float(r.get("stop_loss") or 0),
                margin=float(r.get("collateral") or self.MARGIN_USD),
                leverage=float(r.get("leverage") or 10.0),
                row_id=int(r["id"]),
                peak_price=float(meta.get("peak_price") or entry),
                peak_pnl_pct=float(r.get("peak_pnl") or 0),
                be_locked=bool(meta.get("be_locked")),
                opened_mono=opened_mono,
                is_manual=bool(meta.get("manual")),
                liq=float(meta.get("liq_price") or 0),
                confidence=(float(meta["confidence_score"]) if meta.get("confidence_score") is not None else None),
                htf_trend=(int(meta["htf_trend"]) if meta.get("htf_trend") is not None else None),
                lane=str(meta.get("lane") or ("MANUAL" if meta.get("manual") else "")),
            )
            # Manual trades: re-apply the current ride-to-liquidation policy on
            # boot (a stale tight stop stored from an older policy would cut the
            # trade early). Downside = liquidation + pad; let it ride otherwise.
            if pos.is_manual and pos.liq > 0 and pos.atr > 0:
                pad = self.MANUAL_LIQ_PAD_ATR * pos.atr
                pos.stop = pos.liq + pad if pos.is_long else pos.liq - pad
            self._positions[pair] = pos
            logger.warning(
                "Re-attached open position id=%s %s %s x%.0f entry=%.2f stop=%.2f%s",
                pos.row_id, pair, direction.upper(), pos.contracts, entry, pos.stop,
                " (manual)" if pos.is_manual else "",
            )

    # ── main tick ──────────────────────────────────────────────────────
    async def _tick(self) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._daily_date:
            self._daily_date = today
            self._daily_realized = 0.0

        # 1. manage every open position
        for pair in list(self._positions.keys()):
            try:
                await self._manage_position(self._positions[pair])
            except Exception:
                logger.exception("manage failed %s", pair)

        # 2. evaluate ALL pairs — firing `best` signal + per-lane proximity scan
        results: dict[str, dict[str, Any] | None] = {}
        for pair, engine in self.engines.items():
            try:
                results[pair] = await engine.evaluate()
            except Exception:
                results[pair] = None

        # 3. entry gates
        can_enter = not (self._killed or self.user_paused)
        if can_enter and self._daily_realized <= self.DAILY_LOSS_STOP:
            can_enter = False
        bal: float | None = None
        if can_enter:
            try:
                bal = await self.balance_fn()
            except Exception:
                bal = None
            if bal is None:
                can_enter = False
            elif bal < self.KILL_BALANCE:
                can_enter = False
                if not self._killed:
                    self._killed = True
                    logger.error("KILL SWITCH: balance $%.2f < $%.2f — standing down", bal, self.KILL_BALANCE)
                    try:
                        await self.alerts._send(
                            f"🛑 <b>LIVE KILL SWITCH</b>\nBalance ${bal:.2f} below ${self.KILL_BALANCE:.2f}. "
                            "New entries stopped; open trades still managed.",
                            allow_in_quiet=True,
                        )
                    except Exception:
                        pass

        # 4. open new trades on the best fresh signals (1 per asset, MAX_OPEN cap)
        if can_enter:
            for pair in self.pairs:
                if len(self._positions) >= self.MAX_OPEN:
                    break
                if pair in self._positions:
                    continue
                if pair.split("/")[0] not in self.TRADE_BASES:
                    continue   # watch-only asset — scanned but not traded
                res = results.get(pair)
                best = res.get("best") if res else None
                if best:
                    await self._open(best)

        # 5. publish the scanner board for the dashboard
        await self._publish_signals(results)

    # ── confidence → leverage with liquidation safety guard ─────────────
    def _leverage_for(self, conf: float, price: float, atr: float) -> float:
        base = next((lev for floor, lev in self.LEV_TIERS if conf >= floor), 10.0)
        stop_dist = self.STOP_ATR_MULT * atr
        # step DOWN from the tier until the hard stop sits inside the liq distance
        for floor, lev in self.LEV_TIERS:           # 50 → 25 → 10
            if lev > base:
                continue
            liq_dist = price / lev                  # isolated-margin liq ≈ price/lev
            if stop_dist <= liq_dist * self.LIQ_SAFETY:
                return lev
        return 10.0

    # ── open ───────────────────────────────────────────────────────────
    async def _open(self, sig: dict[str, Any]) -> None:
        pair = str(sig["pair"])
        base = pair.split("/")[0]
        csize = self._csize(pair)
        if not csize:
            return
        direction = str(sig["direction"])
        conf = float(sig.get("confidence") or 0)
        atr = float(sig.get("atr") or 0)
        if atr <= 0:
            return
        try:
            ticker = await self.exchange.fetch_ticker(pair)
            price = float(ticker.get("last") or 0)
        except Exception:
            return
        if price <= 0:
            return

        lev = self._leverage_for(conf, price, atr)
        target_notional = self.MARGIN_USD * lev
        contracts = float(int(target_notional / (price * csize)))
        if contracts < 1:
            margin_one = price * csize / lev
            if margin_one > self.MARGIN_HARD_CAP:
                logger.info("Skip %s — 1 contract needs $%.2f margin (> cap $%.2f)", pair, margin_one, self.MARGIN_HARD_CAP)
                return
            contracts = 1.0
        margin = contracts * price * csize / lev
        long = direction == "long"

        try:
            try:
                await self.exchange.set_leverage(int(lev), pair)
            except Exception:
                pass  # already set / not required
            order = await self.exchange.create_order(pair, "market", "buy" if long else "sell", contracts)
        except Exception:
            logger.exception("LIVE order failed %s %s x%.0f", pair, direction, contracts)
            return
        fill = float(order.get("average") or order.get("price") or price)
        stop = fill - self.STOP_ATR_MULT * atr if long else fill + self.STOP_ATR_MULT * atr
        lane = sig.get("lane") or "FUT"
        now_iso = datetime.now(timezone.utc).isoformat()
        row = {
            "pair": pair,
            "side": "buy" if long else "sell",
            "position_type": direction,
            "entry_price": fill,
            "amount": contracts,
            "contracts": contracts,
            "cost": round(margin, 4),
            "collateral": round(margin, 4),
            "leverage": lev,
            "strategy": STRATEGY_TAG,
            "setup_type": f"LIVE_{lane}",
            "order_type": "market",
            "exchange": "delta",
            "status": "open",
            "opened_at": now_iso,
            "stop_loss": round(stop, 4),
            "order_id": str(order.get("id") or ""),
            "metadata": {
                "source": "autonomous",
                "lane": lane,
                "confidence_score": round(conf, 1),
                "htf_trend": sig.get("htf_trend"),
                "atr": atr,
                "contract_size": csize,
                "peak_price": fill,
                "be_locked": False,
            },
        }
        pos = Position(
            pair=pair, direction=direction, contracts=contracts, csize=csize,
            entry=fill, atr=atr, stop=stop, margin=margin, leverage=lev,
            peak_price=fill, opened_mono=asyncio.get_running_loop().time(),
            confidence=round(conf, 1), htf_trend=sig.get("htf_trend"), lane=lane,
        )
        self._positions[pair] = pos       # source of truth: order filled
        pos.row_id = await self.db.log_trade(row)
        if not pos.row_id:
            pos.pending_row = row
            logger.error("LIVE trade opened but DB insert failed — position IS managed, insert will retry")
        logger.warning(
            "🔴 LIVE OPEN id=%s %s %s %.0f ct @ %.2f margin=$%.2f %.0fx stop=%.2f (%s conf %.1f)",
            pos.row_id, pair, direction.upper(), contracts, fill, margin, lev, stop, lane, conf,
        )
        try:
            await self.alerts._send(
                f"🔴 <b>LIVE TRADE OPENED</b>\n"
                f"{base} {direction.upper()} · {int(contracts)} contract(s) @ {fill:,.2f}\n"
                f"Money in ${margin:.2f} · {int(lev)}x · stop {stop:,.2f}\n"
                f"{lane.replace('FUT_', '')} · conf {conf:.0f}",
                allow_in_quiet=True,
            )
        except Exception:
            pass

    # ── manual trade adoption ──────────────────────────────────────────
    async def adopt_manual(
        self, pair: str, side: str, contracts: float, entry_px: float,
        leverage: float | None = None, margin: float | None = None,
        liquidation: float | None = None,
    ) -> bool:
        """Adopt a trade the user opened directly on Delta.

        Full V3 exit engine but NO impatience purges and a liquidation-aware
        stop. Refused only if we're already at MAX_OPEN or already hold this pair.
        """
        if pair in self._positions:
            return False
        if len(self._positions) >= self.MAX_OPEN:
            return False
        base = pair.split("/")[0]
        csize: float | None = None
        try:
            market = (getattr(self.exchange, "markets", None) or {}).get(pair) or {}
            csize = float(market.get("contractSize") or 0) or None
        except Exception:
            pass
        if not csize:
            csize = CONTRACT_SIZE.get(base)
        if not csize or entry_px <= 0 or contracts <= 0:
            logger.warning("adopt_manual: no contract size for %s — cannot adopt", pair)
            return False
        atr = 0.0
        try:
            raw = await self.exchange.fetch_ohlcv(pair, "5m", limit=80)
            atr = _atr_rows([[float(x) for x in r] for r in raw[:-1]])
        except Exception:
            pass
        if atr <= 0:
            atr = entry_px * 0.003
        long = side == "long"
        # Downside = ride to JUST above liquidation (user: "let it keep doing what
        # it wants, only cut if it really goes bad"). No 2-ATR drawdown cut.
        if liquidation and liquidation > 0:
            pad = self.MANUAL_LIQ_PAD_ATR * atr
            stop = liquidation + pad if long else liquidation - pad
        else:
            stop = entry_px - self.MANUAL_STOP_ATR * atr if long else entry_px + self.MANUAL_STOP_ATR * atr
        notional = contracts * csize * entry_px
        if margin and margin > 0:
            lev = notional / margin
        else:
            lev = float(leverage or 10.0)
            margin = notional / lev if lev > 0 else notional
        now_iso = datetime.now(timezone.utc).isoformat()
        row = {
            "pair": pair, "side": "buy" if long else "sell", "position_type": side,
            "entry_price": entry_px, "amount": contracts, "contracts": contracts,
            "cost": round(margin, 4), "collateral": round(margin, 4), "leverage": lev,
            "strategy": STRATEGY_TAG, "setup_type": "LIVE_MANUAL", "order_type": "market",
            "exchange": "delta", "status": "open", "opened_at": now_iso,
            "stop_loss": round(stop, 4),
            "reason": "manual trade on Delta — adopted by AutonomousTrader",
            "metadata": {
                "source": "manual_adopt", "manual": True, "atr": atr,
                "contract_size": csize, "peak_price": entry_px, "be_locked": False,
                "liq_price": round(liquidation, 4) if liquidation else None,
                "leverage_actual": round(lev, 1),
            },
        }
        pos = Position(
            pair=pair, direction=side, contracts=contracts, csize=csize, entry=entry_px,
            atr=atr, stop=stop, margin=margin, leverage=lev, peak_price=entry_px,
            opened_mono=asyncio.get_running_loop().time(), is_manual=True,
            liq=float(liquidation or 0), lane="MANUAL",
        )
        self._positions[pair] = pos
        pos.row_id = await self.db.log_trade(row)
        if not pos.row_id:
            pos.pending_row = row
        logger.warning(
            "🤝 MANUAL ADOPTED id=%s %s %s %.0f ct @ %.2f %.0fx margin≈$%.2f stop=%.2f",
            pos.row_id, pair, side.upper(), contracts, entry_px, lev, margin, stop,
        )
        try:
            liq_line = f"Liquidation {liquidation:,.2f} · safety exit {stop:,.2f}\n" if liquidation else f"Safety exit {stop:,.2f} (wide)\n"
            await self.alerts._send(
                f"🤝 <b>YOUR TRADE — now managed</b>\n"
                f"{base} {side.upper()} · {int(contracts)} contract(s) @ {entry_px:,.2f} · {int(lev)}x\n"
                f"Money in ${margin:.2f}\n{liq_line}"
                f"Up → I bank it early (breakeven from +0.4 ATR, lock 50% of the peak). "
                f"Down → I cut at a deep drawdown or just before liquidation, whichever first.",
                allow_in_quiet=True,
            )
        except Exception:
            pass
        return True

    # ── manage / close ─────────────────────────────────────────────────
    def _trail_mult(self, peak_pnl_pct: float) -> float:
        if peak_pnl_pct >= self.TRAIL_TIGHT_2_PEAK:
            return self.TRAIL_TIGHT_2_MULT
        if peak_pnl_pct >= self.TRAIL_TIGHT_1_PEAK:
            return self.TRAIL_TIGHT_1_MULT
        return self.TRAIL_ATR_MULT

    async def _manage_position(self, pos: Position) -> None:
        # Heal a failed open-insert so the dashboard/trade board see the position.
        if pos.row_id is None and pos.pending_row is not None:
            pos.row_id = await self.db.log_trade(pos.pending_row)
            if pos.row_id:
                pos.pending_row = None
                logger.warning("LIVE trade DB record healed: id=%s", pos.row_id)
        try:
            ticker = await self.exchange.fetch_ticker(pos.pair)
            price = float(ticker.get("last") or 0)
        except Exception:
            return
        if price <= 0:
            return
        long = pos.is_long
        pnl_usd = (price - pos.entry) * pos.contracts * pos.csize * (1 if long else -1)
        pnl_pct = (pnl_usd / pos.margin * 100.0) if pos.margin > 0 else 0.0
        pos.peak_pnl_pct = max(pos.peak_pnl_pct, pnl_pct)
        pos.peak_price = max(pos.peak_price, price) if long else min(pos.peak_price, price)
        age = asyncio.get_running_loop().time() - pos.opened_mono

        atr = pos.atr
        peak_fav = (pos.peak_price - pos.entry) if long else (pos.entry - pos.peak_price)

        # MANUAL trades: NO breakeven ratchet (it's what cut #3713/#3714 at
        # breakeven). The downside stop stays near liquidation; we only add a
        # LOOSE trail once the trade is a genuine winner (+3 ATR), trailing 2.5
        # ATR behind the peak so it rides but still banks a real run.
        if not pos.is_manual:
            trail_arm = self.TRAIL_ARM_ATR
            trail_mult = self._trail_mult(pos.peak_pnl_pct)
            # Fee-aware breakeven: arm only once the move clears round-trip fees
            # with room, so the lock never sits above market and books a sub-fee scrap.
            fee_buffer = pos.entry * self.TAKER_FEE * 2
            be_threshold = max(self.BREAKEVEN_ATR * atr, fee_buffer * self.BE_FEE_ARM_MULT)
            if atr > 0 and peak_fav >= be_threshold:
                locked = max(fee_buffer * self.LOCK_FEE_FLOOR_MULT, self.PROFIT_LOCK_FRAC * peak_fav)
                if long:
                    pos.stop = max(pos.stop, pos.entry + locked)
                else:
                    pos.stop = min(pos.stop, pos.entry - locked)
                pos.be_locked = True
            # Profit harvest: above +5%, lock 60% of the CURRENT gain. Uses the
            # live PnL (not the peak), so the locked stop is always BELOW price —
            # no lag trap — and only ratchets up, so a +13% run banks ~+8%, a
            # +8% run banks ~+5%, instead of bleeding to breakeven.
            if pnl_pct >= self.PROFIT_ARM_PCT and pos.leverage > 0:
                keep_pct = pnl_pct * self.PROFIT_KEEP_FRAC                    # margin %
                offset = pos.entry * (keep_pct / 100.0) / pos.leverage        # → price move
                if long:
                    pos.stop = max(pos.stop, pos.entry + offset)
                else:
                    pos.stop = min(pos.stop, pos.entry - offset)
                pos.be_locked = True
        else:
            trail_arm = self.MANUAL_TRAIL_ARM_ATR
            trail_mult = self.MANUAL_TRAIL_MULT

        live_stop = pos.stop
        if atr > 0 and peak_fav >= trail_arm * atr:
            trail = pos.peak_price - trail_mult * atr if long else pos.peak_price + trail_mult * atr
            live_stop = max(live_stop, trail) if long else min(live_stop, trail)

        reason = ""
        if (not pos.is_manual) and pnl_pct <= self.MAX_LOSS_PCT:
            reason = "loss_cap"        # non-peaker bleeding out — cut before it slips deeper
        elif (long and price <= live_stop) or (not long and price >= live_stop):
            if live_stop != pos.stop:
                reason = "trail_stop"
            else:
                reason = "breakeven_stop" if pos.be_locked else "hard_stop"
        elif (not pos.is_manual) and pnl_pct >= self.PROFIT_TAKE_PCT:
            reason = "profit_take"      # hard-bank a big spike (user: harvest the peaks)
        elif (not pos.is_manual) and atr > 0 and age >= self.STAGNATION_SEC and abs(price - pos.entry) < self.STAGNATION_ATR * atr:
            reason = "stagnant_exit"
        elif (not pos.is_manual) and atr > 0 and age >= self.NO_TRACTION_SEC and pnl_usd < 0 and peak_fav < self.NO_TRACTION_ATR * atr:
            reason = "no_traction"
        elif age >= self.MAX_HOLD_SEC:
            reason = "max_hold"

        if pos.row_id:
            await self.db.update_trade(
                pos.row_id,
                {
                    "current_price": price,
                    "current_pnl": round(pnl_usd, 4),
                    "pnl_pct": round(pnl_pct, 4),
                    "peak_pnl": round(pos.peak_pnl_pct, 4),
                    "trail_stop_price": round(live_stop, 4),
                    "stop_loss": round(pos.stop, 4),
                    "metadata": {
                        "source": "manual_adopt" if pos.is_manual else "autonomous",
                        "manual": pos.is_manual,
                        "atr": atr,
                        "contract_size": pos.csize,
                        "peak_price": pos.peak_price,
                        "be_locked": pos.be_locked,
                        "liq_price": round(pos.liq, 4) if pos.liq else None,
                        # preserve entry context so it isn't wiped each tick (was the
                        # bug: confidence/htf showed "—" on the board after 12s)
                        "confidence_score": pos.confidence,
                        "htf_trend": pos.htf_trend,
                        "lane": pos.lane,
                    },
                },
            )
        if reason:
            await self._close(pos, price, reason)

    async def _close(self, pos: Position, ref_price: float, reason: str) -> None:
        long = pos.is_long
        fill = ref_price
        try:
            order = await self.exchange.create_order(
                pos.pair, "market", "sell" if long else "buy", pos.contracts,
                None, {"reduce_only": True},
            )
            fill = float(order.get("average") or order.get("price") or ref_price)
        except Exception:
            # Maybe the user already closed it on Delta — check before retrying.
            flat = False
            try:
                ps = await self.exchange.fetch_positions([pos.pair])
                flat = all(abs(float(p.get("contracts") or 0)) < 1e-9 for p in ps)
            except Exception:
                pass
            if not flat:
                logger.exception("LIVE close order failed %s — will retry next tick", pos.pair)
                return
            reason = "closed_externally"
            logger.warning("Position %s already closed on the exchange — finalizing record", pos.pair)
        gross = (fill - pos.entry) * pos.contracts * pos.csize * (1 if long else -1)
        notional = pos.contracts * pos.csize * (pos.entry + fill) / 2
        fees = notional * self.TAKER_FEE * 2
        net = gross - fees
        self._daily_realized += net
        if pos.row_id:
            await self.db.update_trade(
                pos.row_id,
                {
                    "status": "closed",
                    "closed_at": datetime.now(timezone.utc).isoformat(),
                    "exit_price": fill,
                    "current_price": fill,
                    "gross_pnl": round(gross, 4),
                    "entry_fee": round(fees / 2, 4),
                    "exit_fee": round(fees / 2, 4),
                    "net_pnl": round(net, 4),
                    "pnl": round(net, 4),
                    "pnl_pct": round((net / pos.margin * 100.0) if pos.margin else 0.0, 4),
                    "exit_reason": reason,
                    "reason": reason,
                },
            )
        logger.warning(
            "🔴 LIVE CLOSE id=%s %s exit=%.2f reason=%s net=$%+.3f (day $%+.2f)",
            pos.row_id, pos.pair, fill, reason, net, self._daily_realized,
        )
        try:
            emoji = "🟢" if net >= 0 else "🔴"
            await self.alerts._send(
                f"{emoji} <b>LIVE TRADE CLOSED</b>\n"
                f"{pos.pair.split('/')[0]} {pos.direction.upper()} → {reason.replace('_', ' ')}\n"
                f"Net ${net:+.3f} · day ${self._daily_realized:+.2f}",
                allow_in_quiet=True,
            )
        except Exception:
            pass
        self._positions.pop(pos.pair, None)

    # ── scanner board (dashboard) ───────────────────────────────────────
    async def _publish_signals(self, results: dict[str, dict[str, Any] | None]) -> None:
        rows = []
        now_iso = datetime.now(timezone.utc).isoformat()
        for pair, res in results.items():
            if not res:
                continue
            pos = self._positions.get(pair)
            in_pos = pos is not None
            best = res.get("best")
            price = float(res.get("mark") or 0)
            atr = float(res.get("atr") or 0)
            conf = float(best.get("confidence") or 0) if best else 0.0
            would_lev = int(self._leverage_for(conf, price, atr)) if (best and price > 0 and atr > 0) else None
            # attach the leverage tier each lane would take if it fired now
            lanes = []
            for ln in (res.get("lanes") or []):
                lc = float(ln.get("would_conf") or 0)
                lanes.append({
                    **ln,
                    "would_lev": int(self._leverage_for(lc, price, atr)) if (price > 0 and atr > 0 and lc >= 90) else None,
                })
            rows.append({
                "pair": pair,
                "lane": best.get("lane") if best else None,
                "direction": best.get("direction") if best else None,
                "confidence": round(conf, 1),
                "htf_trend": res.get("htf_trend"),
                "would_lev": would_lev,
                "in_position": in_pos,
                "scan": {
                    "mark": price,
                    "status": res.get("status"),
                    "htf_trend": res.get("htf_trend"),
                    "in_position": in_pos,
                    "tradeable": pair.split("/")[0] in self.TRADE_BASES,
                    "lanes": lanes,
                },
                "updated_at": now_iso,
            })
        if not rows:
            return
        loop = asyncio.get_running_loop()

        def w() -> None:
            try:
                self.db.client.table("live_signals").upsert(rows, on_conflict="pair").execute()
            except Exception:
                pass

        await loop.run_in_executor(None, w)

"""LiveMirror — the ONLY live trading path in the V3 era.

Watches the V3 paper futures lanes and mirrors a tiny, heavily-filtered subset
of their entries with REAL money on Delta perpetuals. The paper lab keeps
learning at full speed; this takes roughly "1 trade in 10" — only the
highest-conviction, trend-aligned signal from the best-performing lane.

Filters (ALL must pass):
  * a paper lane opened a trade in the last SIGNAL_FRESH_SEC seconds
  * its confidence >= MIN_CONF and it carries an htf_trend stamp (1h-aligned)
  * it comes from the lane with the best trailing profit factor
  * no live position is already open

Hard rails (non-negotiable at a ~$27 account):
  * margin ~MARGIN_USD per trade at LEVERAGE x, one position max
  * daily realized loss <= DAILY_LOSS_STOP -> no new entries until UTC midnight
  * balance < KILL_BALANCE -> permanent stand-down + Telegram alert
  * exits run the SAME validated V3 engine: ATR stop, breakeven ratchet,
    tightening chandelier trail, stagnation purge, no-traction purge, 24h max

Restart behaviour: a live position is REAL — it persists on the exchange, so
on boot we re-attach to any open `live_mirror` row instead of closing it.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from alpha.paper_futures import _atr_rows
from alpha.utils import setup_logger

logger = setup_logger("live_mirror")

CONTRACT_SIZE: dict[str, float] = {"BTC": 0.001, "ETH": 0.01}


def _pct(start: float, end: float) -> float:
    return (end - start) / start * 100.0 if start > 0 else 0.0


class LiveMirror:
    POLL_SEC = 12
    SIGNAL_FRESH_SEC = 120
    MIN_CONF = 85.0
    MARGIN_USD = 5.0            # target money-in per trade
    MARGIN_HARD_CAP = 8.0       # never let 1-contract minimums push margin past this
    LEVERAGE = 10.0
    TAKER_FEE = 0.0005          # Delta perp taker per side
    DAILY_LOSS_STOP = -3.0
    KILL_BALANCE = 20.0
    PF_CACHE_SEC = 1800.0
    PF_LOOKBACK_H = 48
    # V3 exit engine (identical constants to the validated paper lanes)
    STOP_ATR_MULT = 1.6
    BREAKEVEN_ATR = 1.2
    PROFIT_LOCK_FRAC = 0.4          # lock 40% of the peak move once BE arms (mirrors paper lanes)
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

    def __init__(
        self,
        exchange: Any,
        db: Any,
        alerts: Any,
        balance_fn: Callable[[], Awaitable[float | None]],
    ) -> None:
        self.exchange = exchange
        self.db = db
        self.alerts = alerts
        self.balance_fn = balance_fn
        self.is_active = False
        self.user_paused = False        # pause/resume commands toggle this
        self._task: asyncio.Task[None] | None = None
        self._killed = False
        self._daily_realized = 0.0
        self._daily_date = ""
        self._pf_cache: tuple[float, dict[str, float]] = (0.0, {})
        # open position state
        # CRITICAL: _position_open is the source of truth for "do we have a real
        # position", set the instant an exchange order fills. It must NEVER
        # depend on the DB write succeeding — on 06-11 a DB CHECK constraint
        # rejected the insert, _row_id stayed None, and the mirror re-entered
        # 4x before the margin ran out (orphan protection flattened it, -$0.03).
        self._position_open = False
        self._pending_row: dict[str, Any] | None = None   # row to retry-insert if log_trade failed
        self._row_id: int | None = None
        self._pair = ""
        self._direction = ""            # long | short
        self._contracts = 0.0
        self._csize = 0.0
        self._entry = 0.0
        self._atr = 0.0
        self._stop = 0.0
        self._peak_price = 0.0
        self._peak_pnl_pct = 0.0
        self._be_locked = False
        self._margin = 0.0
        self._opened_mono = 0.0
        self._is_manual = False     # adopted user trade: manage exits, but no
                                    # impatience purges (stagnation/no-traction)

    # ── lifecycle ──────────────────────────────────────────────────────
    async def start(self) -> None:
        if self.is_active:
            return
        self.is_active = True
        await self._reattach()
        logger.warning(
            "🔴 LiveMirror ACTIVE — real money. margin=$%.2f lev=%.0fx daily_stop=$%.2f kill=$%.2f",
            self.MARGIN_USD, self.LEVERAGE, self.DAILY_LOSS_STOP, self.KILL_BALANCE,
        )
        try:
            await self.alerts._send(
                "🔴 <b>LIVE MIRROR ACTIVE — real money</b>\n"
                f"${self.MARGIN_USD:.0f}/trade · {self.LEVERAGE:.0f}x · max 1 open\n"
                f"Day stop −${abs(self.DAILY_LOSS_STOP):.0f} · kill switch &lt;${self.KILL_BALANCE:.0f}\n"
                "Waiting for the next conf≥85 trend-aligned signal from the best lane.",
                allow_in_quiet=True,
            )
        except Exception:
            pass
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        # A live position is real and persists on the exchange — do NOT close
        # it here; we re-attach on next boot.
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
                logger.exception("LiveMirror tick failed")
            await asyncio.sleep(self.POLL_SEC)

    # ── boot re-attach ─────────────────────────────────────────────────
    async def _reattach(self) -> None:
        loop = asyncio.get_running_loop()

        def q() -> list[dict[str, Any]]:
            try:
                return (
                    self.db.client.table("trades").select("*")
                    .eq("strategy", "live_mirror").eq("status", "open")
                    .order("opened_at", desc=True).limit(1).execute().data or []
                )
            except Exception:
                return []

        rows = await loop.run_in_executor(None, q)
        if not rows:
            return
        r = rows[0]
        meta = r.get("metadata") or {}
        self._position_open = True
        self._row_id = int(r["id"])
        self._pair = r["pair"]
        self._direction = r.get("position_type") or ("long" if r.get("side") == "buy" else "short")
        self._contracts = float(r.get("contracts") or r.get("amount") or 0)
        self._csize = float(meta.get("contract_size") or CONTRACT_SIZE.get(self._pair.split("/")[0], 0.001))
        self._entry = float(r.get("entry_price") or 0)
        self._atr = float(meta.get("atr") or 0)
        self._stop = float(r.get("stop_loss") or 0)
        self._peak_price = float(meta.get("peak_price") or self._entry)
        self._peak_pnl_pct = float(r.get("peak_pnl") or 0)
        self._be_locked = bool(meta.get("be_locked"))
        self._is_manual = bool(meta.get("manual"))
        self._margin = float(r.get("collateral") or self.MARGIN_USD)
        self._opened_mono = asyncio.get_running_loop().time() - max(
            0.0,
            (datetime.now(timezone.utc) - datetime.fromisoformat(str(r["opened_at"]).replace("Z", "+00:00"))).total_seconds(),
        )
        logger.warning(
            "LiveMirror re-attached to open position id=%s %s %s x%.0f entry=%.2f stop=%.2f",
            self._row_id, self._pair, self._direction.upper(), self._contracts, self._entry, self._stop,
        )

    # ── main tick ──────────────────────────────────────────────────────
    async def _tick(self) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._daily_date:
            self._daily_date = today
            self._daily_realized = 0.0

        if self._position_open:
            await self._manage_position()
            return

        if self._killed or self.user_paused:
            return
        if self._daily_realized <= self.DAILY_LOSS_STOP:
            return
        bal = None
        try:
            bal = await self.balance_fn()
        except Exception:
            pass
        if bal is None:
            return
        if bal < self.KILL_BALANCE:
            self._killed = True
            logger.error("LiveMirror KILL SWITCH: balance $%.2f < $%.2f — standing down", bal, self.KILL_BALANCE)
            try:
                await self.alerts._send(
                    f"🛑 <b>LIVE KILL SWITCH</b>\nBalance ${bal:.2f} fell below ${self.KILL_BALANCE:.2f}. "
                    "Live mirror stopped. Paper lab continues.",
                    allow_in_quiet=True,
                )
            except Exception:
                pass
            return

        cand = await self._best_candidate()
        if cand:
            await self._open(cand)

    # ── manual trade adoption ──────────────────────────────────────────
    async def adopt_manual(
        self, pair: str, side: str, contracts: float, entry_px: float, leverage: float | None = None,
    ) -> bool:
        """Adopt a trade the user opened directly on Delta.

        The position gets the full V3 exit engine (ATR stop → breakeven lock →
        profit ratchet → tightening trail → 24h max) but NO impatience purges:
        a human took this trade on purpose — manage it, don't second-guess it.
        Returns False if the mirror is already managing a position.
        """
        if self._position_open:
            return False
        base = pair.split("/")[0]
        csize = CONTRACT_SIZE.get(base)
        if not csize or entry_px <= 0 or contracts <= 0:
            return False
        atr = 0.0
        try:
            raw = await self.exchange.fetch_ohlcv(pair, "5m", limit=80)
            atr = _atr_rows([[float(x) for x in r] for r in raw[:-1]])
        except Exception:
            pass
        if atr <= 0:
            atr = entry_px * 0.003   # conservative fallback ≈ typical 5m ATR
        long = side == "long"
        stop = entry_px - self.STOP_ATR_MULT * atr if long else entry_px + self.STOP_ATR_MULT * atr
        lev = float(leverage or self.LEVERAGE)
        margin = contracts * csize * entry_px / lev if lev > 0 else contracts * csize * entry_px
        now_iso = datetime.now(timezone.utc).isoformat()
        row = {
            "pair": pair,
            "side": "buy" if long else "sell",
            "position_type": side,
            "entry_price": entry_px,
            "amount": contracts,
            "contracts": contracts,
            "cost": round(margin, 4),
            "collateral": round(margin, 4),
            "leverage": lev,
            "strategy": "live_mirror",
            "setup_type": "LIVE_MANUAL",
            "order_type": "market",
            "exchange": "delta",
            "status": "open",
            "opened_at": now_iso,
            "stop_loss": round(stop, 4),
            "reason": "manual trade on Delta — adopted by LiveMirror",
            "metadata": {
                "source": "manual_adopt",
                "manual": True,
                "atr": atr,
                "contract_size": csize,
                "peak_price": entry_px,
                "be_locked": False,
            },
        }
        self._position_open = True
        self._is_manual = True
        self._row_id = await self.db.log_trade(row)
        if not self._row_id:
            self._pending_row = row
        self._pair = pair
        self._direction = side
        self._contracts = contracts
        self._csize = csize
        self._entry = entry_px
        self._atr = atr
        self._stop = stop
        self._peak_price = entry_px
        self._peak_pnl_pct = 0.0
        self._be_locked = False
        self._margin = margin
        self._opened_mono = asyncio.get_running_loop().time()
        logger.warning(
            "🤝 MANUAL ADOPTED id=%s %s %s %.0f ct @ %.2f %sx margin≈$%.2f stop=%.2f",
            self._row_id, pair, side.upper(), contracts, entry_px, int(lev), margin, stop,
        )
        try:
            await self.alerts._send(
                f"🤝 <b>YOUR TRADE — now managed</b>\n"
                f"{base} {side.upper()} · {int(contracts)} contract(s) @ {entry_px:,.2f} · {int(lev)}x\n"
                f"Money in ≈ ${margin:.2f} · stop {stop:,.2f}\n"
                f"V3 exits active: ATR stop → breakeven lock → profit ratchet → trail. "
                f"No impatience exits on manual trades.",
                allow_in_quiet=True,
            )
        except Exception:
            pass
        return True

    # ── candidate selection (the "1 in 10" brain) ──────────────────────
    async def _best_candidate(self) -> dict[str, Any] | None:
        loop = asyncio.get_running_loop()
        cutoff = datetime.now(timezone.utc).timestamp() - self.SIGNAL_FRESH_SEC
        cutoff_iso = datetime.fromtimestamp(cutoff, tz=timezone.utc).isoformat()

        def q() -> list[dict[str, Any]]:
            try:
                return (
                    self.db.client.table("paper_futures_trades")
                    .select("id,pair,setup_type,direction,entry_price,opened_at,metadata")
                    .eq("status", "open").gte("opened_at", cutoff_iso)
                    .execute().data or []
                )
            except Exception:
                return []

        rows = await loop.run_in_executor(None, q)
        pf = await self._lane_pf()
        best: dict[str, Any] | None = None
        best_key: tuple[float, float] = (-1.0, -1.0)
        for r in rows:
            meta = r.get("metadata") or {}
            conf = float(meta.get("confidence_score") or 0)
            if conf < self.MIN_CONF or meta.get("htf_trend") is None:
                continue
            lane_pf = pf.get(str(r.get("setup_type")), 0.0)
            key = (lane_pf, conf)
            if key > best_key:
                best_key = key
                best = r
        return best

    async def _lane_pf(self) -> dict[str, float]:
        now = asyncio.get_running_loop().time()
        if now - self._pf_cache[0] < self.PF_CACHE_SEC:
            return self._pf_cache[1]
        loop = asyncio.get_running_loop()
        cutoff = datetime.fromtimestamp(
            datetime.now(timezone.utc).timestamp() - self.PF_LOOKBACK_H * 3600, tz=timezone.utc
        ).isoformat()

        def q() -> list[dict[str, Any]]:
            try:
                return (
                    self.db.client.table("paper_futures_trades")
                    .select("setup_type,pnl_usd").eq("status", "closed")
                    .gte("opened_at", cutoff).limit(2000).execute().data or []
                )
            except Exception:
                return []

        rows = await loop.run_in_executor(None, q)
        wins: dict[str, float] = {}
        losses: dict[str, float] = {}
        for r in rows:
            k = str(r.get("setup_type"))
            p = float(r.get("pnl_usd") or 0)
            if p > 0:
                wins[k] = wins.get(k, 0.0) + p
            else:
                losses[k] = losses.get(k, 0.0) - p
        pf = {k: (wins.get(k, 0.0) / losses[k]) if losses.get(k) else (2.0 if wins.get(k) else 0.0)
              for k in set(wins) | set(losses)}
        self._pf_cache = (now, pf)
        return pf

    # ── open ───────────────────────────────────────────────────────────
    async def _open(self, cand: dict[str, Any]) -> None:
        pair = str(cand["pair"])
        base = pair.split("/")[0]
        csize = CONTRACT_SIZE.get(base)
        if not csize:
            return
        direction = str(cand["direction"])
        meta = cand.get("metadata") or {}
        try:
            ticker = await self.exchange.fetch_ticker(pair)
            price = float(ticker.get("last") or 0)
        except Exception:
            return
        if price <= 0:
            return
        target_notional = self.MARGIN_USD * self.LEVERAGE
        contracts = float(int(target_notional / (price * csize)))
        if contracts < 1:
            margin_one = price * csize / self.LEVERAGE
            if margin_one > self.MARGIN_HARD_CAP:
                logger.info("Skip %s — one contract needs $%.2f margin (> cap $%.2f)", pair, margin_one, self.MARGIN_HARD_CAP)
                return
            contracts = 1.0
        margin = contracts * price * csize / self.LEVERAGE
        atr = float(meta.get("atr") or 0)
        if atr <= 0:
            return
        long = direction == "long"
        stop = price - self.STOP_ATR_MULT * atr if long else price + self.STOP_ATR_MULT * atr

        try:
            try:
                await self.exchange.set_leverage(int(self.LEVERAGE), pair)
            except Exception:
                pass  # already set / not required
            order = await self.exchange.create_order(
                pair, "market", "buy" if long else "sell", contracts
            )
        except Exception:
            logger.exception("LIVE order failed %s %s x%.0f", pair, direction, contracts)
            return
        fill = float(order.get("average") or order.get("price") or price)
        stop = fill - self.STOP_ATR_MULT * atr if long else fill + self.STOP_ATR_MULT * atr
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
            "leverage": self.LEVERAGE,
            "strategy": "live_mirror",
            "setup_type": f"LIVE_{cand.get('setup_type')}",
            "order_type": "market",
            "exchange": "delta",
            "status": "open",
            "opened_at": now_iso,
            "stop_loss": round(stop, 4),
            "order_id": str(order.get("id") or ""),
            "metadata": {
                "source": "live_mirror",
                "paper_trade_id": cand.get("id"),
                "source_lane": cand.get("setup_type"),
                "confidence_score": meta.get("confidence_score"),
                "htf_trend": meta.get("htf_trend"),
                "atr": atr,
                "contract_size": csize,
                "peak_price": fill,
                "be_locked": False,
            },
        }
        # The exchange order is FILLED — we have a position no matter what the
        # DB says. Mark it open first; the row insert may fail and be retried.
        self._position_open = True
        self._row_id = await self.db.log_trade(row)
        if not self._row_id:
            self._pending_row = row
            logger.error("LIVE trade opened but DB insert failed — position IS managed, insert will retry")
            try:
                await self.alerts._send(
                    "⚠️ <b>Live trade opened but DB record failed</b> — the position is "
                    "still fully managed in-memory; the record insert will retry.",
                    allow_in_quiet=True,
                )
            except Exception:
                pass
        self._pair = pair
        self._direction = direction
        self._contracts = contracts
        self._csize = csize
        self._entry = fill
        self._atr = atr
        self._stop = stop
        self._peak_price = fill
        self._peak_pnl_pct = 0.0
        self._be_locked = False
        self._margin = margin
        self._opened_mono = asyncio.get_running_loop().time()
        logger.warning(
            "🔴 LIVE OPEN id=%s %s %s %.0f contracts @ %.2f margin=$%.2f stop=%.2f (lane %s conf %s)",
            self._row_id, pair, direction.upper(), contracts, fill, margin, stop, cand.get("setup_type"), meta.get("confidence_score"),
        )
        try:
            await self.alerts._send(
                f"🔴 <b>LIVE TRADE OPENED</b>\n"
                f"{base} {direction.upper()} · {int(contracts)} contract(s) @ {fill:,.2f}\n"
                f"Money in ${margin:.2f} · {int(self.LEVERAGE)}x · stop {stop:,.2f}\n"
                f"Mirroring {cand.get('setup_type')} (conf {meta.get('confidence_score')})",
                allow_in_quiet=True,
            )
        except Exception:
            pass

    # ── manage / close ─────────────────────────────────────────────────
    def _trail_mult(self) -> float:
        if self._peak_pnl_pct >= self.TRAIL_TIGHT_2_PEAK:
            return self.TRAIL_TIGHT_2_MULT
        if self._peak_pnl_pct >= self.TRAIL_TIGHT_1_PEAK:
            return self.TRAIL_TIGHT_1_MULT
        return self.TRAIL_ATR_MULT

    async def _manage_position(self) -> None:
        # Heal a failed open-insert so the dashboard/trade board see the position.
        if self._row_id is None and self._pending_row is not None:
            self._row_id = await self.db.log_trade(self._pending_row)
            if self._row_id:
                self._pending_row = None
                logger.warning("LIVE trade DB record healed: id=%s", self._row_id)
        try:
            ticker = await self.exchange.fetch_ticker(self._pair)
            price = float(ticker.get("last") or 0)
        except Exception:
            return
        if price <= 0:
            return
        long = self._direction == "long"
        pnl_usd = (price - self._entry) * self._contracts * self._csize * (1 if long else -1)
        pnl_pct = (pnl_usd / self._margin * 100.0) if self._margin > 0 else 0.0
        self._peak_pnl_pct = max(self._peak_pnl_pct, pnl_pct)
        self._peak_price = max(self._peak_price, price) if long else min(self._peak_price, price)
        age = asyncio.get_running_loop().time() - self._opened_mono

        atr = self._atr
        peak_fav = (self._peak_price - self._entry) if long else (self._entry - self._peak_price)
        if atr > 0 and peak_fav >= self.BREAKEVEN_ATR * atr:
            # breakeven first, then keep ratcheting: lock 40% of the peak move
            # (monotonic — the stop only ever improves). Fix for live #3699:
            # +6.6% peak fell back to $0.00 because BE protected but the
            # 1.8-ATR trail never harvested sub-15% peaks.
            fee_buffer = self._entry * self.TAKER_FEE * 2
            locked = max(fee_buffer, self.PROFIT_LOCK_FRAC * peak_fav)
            if long:
                self._stop = max(self._stop, self._entry + locked)
            else:
                self._stop = min(self._stop, self._entry - locked)
            self._be_locked = True

        live_stop = self._stop
        if atr > 0 and peak_fav >= self.TRAIL_ARM_ATR * atr:
            trail = self._peak_price - self._trail_mult() * atr if long else self._peak_price + self._trail_mult() * atr
            live_stop = max(live_stop, trail) if long else min(live_stop, trail)

        reason = ""
        if (long and price <= live_stop) or (not long and price >= live_stop):
            if live_stop != self._stop:
                reason = "trail_stop"
            else:
                reason = "breakeven_stop" if self._be_locked else "hard_stop"
        elif (not self._is_manual) and atr > 0 and age >= self.STAGNATION_SEC and abs(price - self._entry) < self.STAGNATION_ATR * atr:
            reason = "stagnant_exit"
        elif (not self._is_manual) and atr > 0 and age >= self.NO_TRACTION_SEC and pnl_usd < 0 and peak_fav < self.NO_TRACTION_ATR * atr:
            reason = "no_traction"
        elif age >= self.MAX_HOLD_SEC:
            reason = "max_hold"

        if self._row_id:
            await self.db.update_trade(
                self._row_id,
                {
                    "current_price": price,
                    "current_pnl": round(pnl_usd, 4),
                    "pnl_pct": round(pnl_pct, 4),
                    "peak_pnl": round(self._peak_pnl_pct, 4),
                    "trail_stop_price": round(live_stop, 4),
                    "stop_loss": round(self._stop, 4),
                    "metadata": {
                        "source": "manual_adopt" if self._is_manual else "live_mirror",
                        "manual": self._is_manual,
                        "atr": atr,
                        "contract_size": self._csize,
                        "peak_price": self._peak_price,
                        "be_locked": self._be_locked,
                    },
                },
            )
        if reason:
            await self._close(price, reason)

    async def _close(self, ref_price: float, reason: str) -> None:
        long = self._direction == "long"
        fill = ref_price
        try:
            order = await self.exchange.create_order(
                self._pair, "market", "sell" if long else "buy", self._contracts,
                None, {"reduce_only": True},
            )
            fill = float(order.get("average") or order.get("price") or ref_price)
        except Exception:
            # Maybe the user already closed it on Delta themselves — check.
            flat = False
            try:
                ps = await self.exchange.fetch_positions([self._pair])
                flat = all(abs(float(p.get("contracts") or 0)) < 1e-9 for p in ps)
            except Exception:
                pass
            if not flat:
                logger.exception("LIVE close order failed — will retry next tick")
                return
            reason = "closed_externally"
            logger.warning("Position %s already closed on the exchange — finalizing record", self._pair)
        gross = (fill - self._entry) * self._contracts * self._csize * (1 if long else -1)
        notional = self._contracts * self._csize * (self._entry + fill) / 2
        fees = notional * self.TAKER_FEE * 2
        net = gross - fees
        self._daily_realized += net
        if self._row_id:
            await self.db.update_trade(
                self._row_id,
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
                    "pnl_pct": round((net / self._margin * 100.0) if self._margin else 0.0, 4),
                    "exit_reason": reason,
                    "reason": reason,
                },
            )
        logger.warning(
            "🔴 LIVE CLOSE id=%s %s exit=%.2f reason=%s net=$%+.3f (day $%+.2f)",
            self._row_id, self._pair, fill, reason, net, self._daily_realized,
        )
        try:
            emoji = "🟢" if net >= 0 else "🔴"
            await self.alerts._send(
                f"{emoji} <b>LIVE TRADE CLOSED</b>\n"
                f"{self._pair.split('/')[0]} {self._direction.upper()} → {reason.replace('_', ' ')}\n"
                f"Net ${net:+.3f} · day ${self._daily_realized:+.2f}",
                allow_in_quiet=True,
            )
        except Exception:
            pass
        self._position_open = False
        self._is_manual = False
        self._pending_row = None
        self._row_id = None
        self._pair = ""
        self._direction = ""
        self._contracts = 0.0
        self._entry = 0.0
        self._atr = 0.0
        self._stop = 0.0
        self._peak_price = 0.0
        self._peak_pnl_pct = 0.0
        self._be_locked = False
        self._margin = 0.0
        self._opened_mono = 0.0

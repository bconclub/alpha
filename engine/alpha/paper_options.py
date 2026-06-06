"""Independent paper OPTIONS strategy lab (buy-only, price-action, ride-the-wave).

These strategies never place exchange orders. They read the REAL Delta option
chain + live premiums for BTC/ETH, "buy" a call (up view) or put (down view) on
a genuine underlying price-action move, then RIDE THE WAVE — holding through
premium noise while the underlying structure supports the trade, and exiting
only when the underlying move is over (or a hard catastrophic stop / expiry).

No time-based decision gates: no min-hold, no cooldown, no fixed scalp timer.
The only clock is the contract's own expiry (options settle — that's reality,
not a strategy choice).

Rows are written to paper_options_trades so we can compare option behaviour
against paper futures before risking any real capital.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from alpha.db import Database
from alpha.paper_futures import _clamp, _ema, _pct_move
from alpha.utils import setup_logger

# Delta Exchange option contract multipliers (underlying units per contract).
CONTRACT_MULTIPLIER: dict[str, float] = {"BTC": 0.001, "ETH": 0.01}


def _rsi(closes: list[float], period: int = 14) -> float:
    """Simple Wilder-ish RSI on a close series. Returns 50 on insufficient data."""
    if len(closes) < period + 1:
        return 50.0
    gains = 0.0
    losses = 0.0
    for i in range(len(closes) - period, len(closes)):
        diff = closes[i] - closes[i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses -= diff
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _ema_series(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    alpha = 2.0 / (period + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * alpha + out[-1] * (1.0 - alpha))
    return out


def _atr(rows: list[list[float]], period: int = 14) -> float:
    """Average true range over the last `period` bars."""
    if len(rows) < period + 1:
        return 0.0
    trs: list[float] = []
    for i in range(1, len(rows)):
        h, l, pc = rows[i][2], rows[i][3], rows[i - 1][4]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs[-period:]) / period


def _vwap(rows: list[list[float]]) -> float:
    """Rolling volume-weighted average price over the supplied bars."""
    pv = 0.0
    vol = 0.0
    for r in rows:
        typical = (r[2] + r[3] + r[4]) / 3.0
        v = r[5]
        pv += typical * v
        vol += v
    return pv / vol if vol > 0 else 0.0


def _macd(closes: list[float], fast: int = 12, slow: int = 26, sig: int = 9) -> tuple[float, float]:
    """Return (macd_line, signal_line) at the latest bar."""
    if len(closes) < slow + sig:
        return 0.0, 0.0
    ef = _ema_series(closes, fast)
    es = _ema_series(closes, slow)
    macd_line = [ef[i] - es[i] for i in range(len(closes))]
    signal = _ema_series(macd_line[-(sig * 3):], sig)
    return macd_line[-1], signal[-1]


def _supertrend_dir(rows: list[list[float]], period: int = 10, mult: float = 3.0) -> int:
    """Supertrend direction: +1 uptrend, -1 downtrend, 0 unknown."""
    n = len(rows)
    if n < period + 2:
        return 0
    highs = [r[2] for r in rows]
    lows = [r[3] for r in rows]
    closes = [r[4] for r in rows]
    tr = [max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])) for i in range(1, n)]
    direction = 1
    fu = 0.0
    fl = 0.0
    for i in range(period, n):
        atr = sum(tr[i - period:i]) / period
        hl2 = (highs[i] + lows[i]) / 2.0
        bu = hl2 + mult * atr
        bl = hl2 - mult * atr
        if i == period:
            fu, fl = bu, bl
            direction = 1 if closes[i] >= hl2 else -1
            continue
        fu = bu if (bu < fu or closes[i - 1] > fu) else fu
        fl = bl if (bl > fl or closes[i - 1] < fl) else fl
        if direction == 1:
            direction = -1 if closes[i] < fl else 1
        else:
            direction = 1 if closes[i] > fu else -1
    return direction


class PaperMarketData:
    """Per-underlying shared cache of spot + OHLCV so many lanes don't hammer the API."""

    TTL = 4.0

    def __init__(self, futures_exchange: Any, pair: str) -> None:
        self.ex = futures_exchange
        self.pair = pair
        self._ohlcv: dict[str, tuple[float, list[list[float]]]] = {}
        self._spot: tuple[float, float] = (0.0, 0.0)

    async def ohlcv(self, tf: str) -> list[list[float]]:
        now = asyncio.get_running_loop().time()
        cached = self._ohlcv.get(tf)
        if cached and now - cached[0] < self.TTL:
            return cached[1]
        try:
            raw = await self.ex.fetch_ohlcv(self.pair, tf, limit=120)
            rows = [[float(x) for x in r] for r in raw]
        except Exception:
            rows = cached[1] if cached else []
        self._ohlcv[tf] = (now, rows)
        return rows

    async def spot(self) -> float:
        now = asyncio.get_running_loop().time()
        if self._spot[0] and now - self._spot[0] < self.TTL:
            return self._spot[1]
        price = self._spot[1]
        try:
            t = await self.ex.fetch_ticker(self.pair)
            price = float(t.get("last") or t.get("bid") or 0) or price
        except Exception:
            pass
        if price > 0:
            self._spot = (now, price)
        return self._spot[1]

# How close to expiry we force-close (options settle; this is a contract reality).
PRE_EXPIRY_CLOSE_SEC = 30 * 60
# Skip strikes whose nearest expiry is sooner than this when opening.
MIN_EXPIRY_HOURS_FOR_ENTRY = 2.0


class PaperOptionChain:
    """Reads the real Delta option chain for one base asset (BTC/ETH).

    Shared by all paper-option lanes on the same underlying so the chain is
    scanned once. Never trades — pure read of options_exchange.markets + tickers.
    """

    REFRESH_SEC = 120.0

    def __init__(self, options_exchange: Any, base_asset: str) -> None:
        self.options_exchange = options_exchange
        self.base_asset = base_asset
        self.logger = setup_logger(f"paper.optchain.{base_asset}")
        self._chain: list[dict[str, Any]] = []
        self._expiry: datetime | None = None
        self._strikes: list[float] = []
        self._symbol_lookup: dict[tuple[float, str], str] = {}
        self._last_refresh = 0.0

    def refresh(self) -> None:
        now = asyncio.get_running_loop().time()
        if self._chain and now - self._last_refresh < self.REFRESH_SEC:
            return
        markets = getattr(self.options_exchange, "markets", None) or {}
        now_utc = datetime.now(timezone.utc)
        chain: list[dict[str, Any]] = []
        for symbol, market in markets.items():
            try:
                if market.get("type") != "option":
                    continue
                if market.get("base") != self.base_asset:
                    continue
                if not market.get("active", True):
                    continue
                expiry_ts = market.get("expiry")
                if expiry_ts is None:
                    continue
                expiry_dt = datetime.fromtimestamp(expiry_ts / 1000, tz=timezone.utc)
                if expiry_dt <= now_utc:
                    continue
                chain.append(
                    {
                        "symbol": symbol,
                        "strike": float(market.get("strike", 0) or 0),
                        "option_type": (market.get("optionType") or "").lower(),
                        "expiry": expiry_dt,
                    }
                )
            except Exception:
                continue
        chain.sort(key=lambda x: (x["expiry"], x["strike"]))
        self._chain = chain
        self._last_refresh = now
        if not chain:
            self._expiry = None
            self._strikes = []
            self._symbol_lookup = {}
            return
        # nearest expiry that is at least MIN_EXPIRY_HOURS away if possible
        expiries = sorted({c["expiry"] for c in chain})
        chosen = expiries[0]
        for exp in expiries:
            if (exp - now_utc).total_seconds() / 3600.0 >= MIN_EXPIRY_HOURS_FOR_ENTRY:
                chosen = exp
                break
        self._expiry = chosen
        self._strikes = sorted({c["strike"] for c in chain if c["expiry"] == chosen})
        self._symbol_lookup = {
            (c["strike"], c["option_type"]): c["symbol"]
            for c in chain
            if c["expiry"] == chosen
        }

    @property
    def expiry(self) -> datetime | None:
        return self._expiry

    def seconds_to_expiry(self) -> float:
        if not self._expiry:
            return 0.0
        return (self._expiry - datetime.now(timezone.utc)).total_seconds()

    def atm_strike(self, spot: float) -> float | None:
        if not self._strikes or spot <= 0:
            return None
        return min(self._strikes, key=lambda s: abs(s - spot))

    def pick_strike(self, spot: float, option_type: str, otm_steps: int = 0) -> float | None:
        """ATM (otm_steps=0) or N steps out-of-the-money."""
        atm = self.atm_strike(spot)
        if atm is None:
            return None
        if otm_steps <= 0:
            return atm
        idx = self._strikes.index(atm)
        if option_type == "call":
            idx = min(len(self._strikes) - 1, idx + otm_steps)
        else:
            idx = max(0, idx - otm_steps)
        return self._strikes[idx]

    def symbol_for(self, strike: float, option_type: str) -> str | None:
        sym = self._symbol_lookup.get((strike, option_type))
        if sym:
            return sym
        if not self._expiry:
            return None
        expiry_str = self._expiry.strftime("%y%m%d")
        cp = "C" if option_type == "call" else "P"
        return f"{self.base_asset}/USD:USD-{expiry_str}-{int(strike)}-{cp}"


class BasePaperOptions:
    """Base runner + paper ledger for one buy-only option strategy lane."""

    SETUP_TYPE = "PAPER_OPT_BASE"
    TIMEFRAME = "5m"
    CHECK_INTERVAL_SEC = 5
    PAPER_ACCOUNT_USD = 1000.0
    STAKE_USD = 80.0                # target premium spent per trade (aggressive on $1000)
    OTM_STEPS = 0                   # 0 = ATM; lanes may reach 1 step OTM on strong moves
    # BUY (ride-the-wave) exits (premium %, leverage = 1 since buy-only)
    HARD_STOP_PCT = -45.0           # thesis dead — catastrophic premium loss
    TRAIL_ARM_PCT = 18.0            # arm the trail early so mid-size peaks aren't given back
    TRAIL_RETRACE_PCT = 0.45        # exit if premium gives back this fraction of the peak
    # SELL mode (theta harvest): collect premium, profit as it decays.
    SELL = False                    # when True this lane WRITES options instead of buying
    SELL_OTM_STEPS = 3              # sell well OTM (lower delta = higher prob of profit)
    SELL_TP_PCT = 30.0             # bank earlier — data showed peaks ~46% then reversing past the old +50% TP
    SELL_SL_PCT = -80.0           # cut a bit sooner too (premium up 80%) to cap the naked-short tail
    SELL_STRIKE_BUFFER = 0.001     # breach when spot reaches ~0.1% past the short strike
    NOTIONAL_CAP_MULT = 20.0       # cap a trade's underlying notional at 20x the stake (no $80→$312k)
    # Fee model: 0.03% of underlying notional per side, capped at 2.5% of premium/stake (gentle so
    # fees don't dominate the test — the breach + churn bug, not fees, was the real killer).
    FEE_NOTIONAL_RATE = 0.0003
    FEE_PREMIUM_CAP = 0.025

    def __init__(
        self,
        pair: str,
        options_exchange: Any,
        futures_exchange: Any,
        db: Database,
        chain: PaperOptionChain,
        *,
        logger_name: str,
        data: "PaperMarketData | None" = None,
        setup_override: str | None = None,
        trail_arm: float | None = None,
        otm_steps: int | None = None,
    ) -> None:
        self.data = data
        # Per-variant overrides (instance attrs shadow class attrs).
        if setup_override:
            self.SETUP_TYPE = setup_override
        if trail_arm is not None:
            self.TRAIL_ARM_PCT = trail_arm
        if otm_steps is not None:
            self.OTM_STEPS = otm_steps
            self.SELL_OTM_STEPS = otm_steps
        self.pair = pair                       # underlying perp, e.g. BTC/USD:USD
        self.options_exchange = options_exchange
        self.futures_exchange = futures_exchange
        self.db = db
        self.chain = chain
        self.base_asset = pair.split("/")[0]
        self.multiplier = CONTRACT_MULTIPLIER.get(self.base_asset, 0.01)
        self.logger = setup_logger(logger_name)
        self.setup_type = self.SETUP_TYPE
        self.is_active = False
        self._task: asyncio.Task[None] | None = None
        # open position state
        self._trade_id: int | None = None
        self._option_symbol: str | None = None
        self._option_type: str | None = None   # call | put
        self._direction: str | None = None     # long | short (underlying view)
        self._strike = 0.0
        self._entry_premium = 0.0
        self._contracts = 0.0
        self._stake = 0.0
        self._peak_pnl_pct = 0.0
        self._entry_metadata: dict[str, Any] = {}
        self._last_signal_key: str | None = None

    # ── lifecycle ──────────────────────────────────────────────────────
    async def start(self) -> None:
        if self.is_active:
            return
        self.is_active = True
        self.logger.info("Starting paper OPTIONS lane: %s %s", self.SETUP_TYPE, self.pair)
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
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
                await self.check()
            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception("Paper options check failed")
            await asyncio.sleep(self.CHECK_INTERVAL_SEC)

    # ── main tick ──────────────────────────────────────────────────────
    async def check(self) -> None:
        # Ensure the options market map is loaded so the chain can be read.
        if not getattr(self.options_exchange, "markets", None):
            try:
                await self.options_exchange.load_markets()
            except Exception:
                return
        self.chain.refresh()
        rows = await self._fetch_ohlcv()
        spot = await self._fetch_spot(rows)
        if spot <= 0:
            return

        if self._trade_id:
            premium = await self._fetch_premium(self._option_symbol, side="mark")
            if premium > 0:
                await self._mark_open(premium)
                reason = self._exit_reason(premium, rows, spot)
                if reason:
                    await self._close(premium, reason)
            return

        decision = self._entry_decision(rows, spot)
        if decision is None:
            return
        direction, signal_key, meta = decision
        if self._last_signal_key == signal_key:
            return
        await self._try_open(direction, spot, signal_key, meta)

    # ── data ───────────────────────────────────────────────────────────
    async def _fetch_ohlcv(self) -> list[list[float]]:
        if self.data is not None:
            return await self.data.ohlcv(self.TIMEFRAME)
        try:
            rows = await self.futures_exchange.fetch_ohlcv(self.pair, self.TIMEFRAME, limit=120)
            return [[float(x) for x in row] for row in rows]
        except Exception:
            return []

    async def _fetch_spot(self, rows: list[list[float]]) -> float:
        if self.data is not None:
            spot = await self.data.spot()
            if spot > 0:
                return spot
            return float(rows[-1][4]) if rows else 0.0
        try:
            ticker = await self.futures_exchange.fetch_ticker(self.pair)
            last = ticker.get("last") or ticker.get("bid")
            if last:
                return float(last)
        except Exception:
            pass
        return float(rows[-1][4]) if rows else 0.0

    async def _fetch_premium(self, symbol: str | None, *, side: str) -> float:
        if not symbol:
            return 0.0
        try:
            t = await self.options_exchange.fetch_ticker(symbol)
        except Exception:
            return 0.0
        info = t.get("info") or {}
        ask = float(t.get("ask") or 0)
        bid = float(t.get("bid") or 0)
        mark = float(t.get("mark") or info.get("mark_price") or 0)
        last = float(t.get("last") or 0)
        if side == "ask":
            return ask or mark or last or bid
        # mark / mid
        if mark > 0:
            return mark
        if ask > 0 and bid > 0:
            return (ask + bid) / 2.0
        return last or ask or bid

    async def _fetch_greeks(self, symbol: str | None) -> dict[str, Any]:
        if not symbol:
            return {}
        try:
            t = await self.options_exchange.fetch_ticker(symbol)
        except Exception:
            return {}
        info = t.get("info") or {}
        out: dict[str, Any] = {}
        for k in ("delta", "gamma", "theta", "vega"):
            v = info.get(k)
            if v is not None:
                try:
                    out[k] = float(v)
                except Exception:
                    pass
        iv = info.get("mark_vol") or info.get("iv")
        if iv is not None:
            try:
                out["iv"] = float(iv)
            except Exception:
                pass
        out["ask"] = float(t.get("ask") or 0)
        out["bid"] = float(t.get("bid") or 0)
        return out

    # ── strategy hooks (override) ──────────────────────────────────────
    def _entry_decision(self, rows: list[list[float]], spot: float):
        """Return (direction 'long'/'short', signal_key, metadata) or None."""
        raise NotImplementedError

    def _underlying_reversed(self, rows: list[list[float]], spot: float) -> bool:
        """True when the underlying move that justified the trade is over."""
        return False

    # ── ride-the-wave exit ─────────────────────────────────────────────
    def _premium_pnl_pct(self, premium: float) -> float:
        if self._entry_premium <= 0:
            return 0.0
        move = _pct_move(self._entry_premium, premium)
        # SELL: we profit when premium FALLS, so invert.
        return -move if self.SELL else move

    def _sell_strike_breached(self, spot: float) -> bool:
        """A short option's real risk is the spot reaching the strike (going ITM).
        Exit a hair before the strike rather than on indicator noise."""
        if self._strike <= 0 or spot <= 0:
            return False
        buf = self.SELL_STRIKE_BUFFER
        if self._option_type == "put":
            return spot <= self._strike * (1.0 + buf)   # spot fell to the short put strike
        return spot >= self._strike * (1.0 - buf)        # spot rose to the short call strike

    def _exit_reason(self, premium: float, rows: list[list[float]], spot: float) -> str:
        # 1) contract reality: settle before expiry (sellers want this — full decay)
        if self.chain.seconds_to_expiry() <= PRE_EXPIRY_CLOSE_SEC:
            return "pre_expiry"
        pnl = self._premium_pnl_pct(premium)
        if self.SELL:
            # theta harvest: take 50% of credit; cut if premium doubles; or if
            # the underlying breaks against the short (option going ITM).
            if pnl >= self.SELL_TP_PCT:
                return "sell_take_profit"
            if pnl <= self.SELL_SL_PCT:
                return "sell_stop"
            if self._sell_strike_breached(spot):
                return "sell_breached"
            return ""
        # BUY: ride-the-wave
        # 2) catastrophic stop (thesis dead)
        if pnl <= self.HARD_STOP_PCT:
            return "hard_stop"
        # 3) lock a big winner after the wave gave back half its peak
        if self._peak_pnl_pct >= self.TRAIL_ARM_PCT:
            floor = self._peak_pnl_pct * (1.0 - self.TRAIL_RETRACE_PCT)
            if pnl <= floor:
                return "wave_trail"
        # 4) underlying move is over — exit and bank the wave (price-action exit)
        if self._underlying_reversed(rows, spot):
            return "underlying_reversed"
        return ""

    # ── open / mark / close ────────────────────────────────────────────
    async def _try_open(self, direction: str, spot: float, signal_key: str, meta: dict[str, Any]) -> None:
        if not self.db.is_connected:
            return
        if self.chain.seconds_to_expiry() <= PRE_EXPIRY_CLOSE_SEC:
            return
        if self.SELL:
            # Sell the side the market is moving AWAY from: bullish → short put, bearish → short call.
            option_type = "put" if direction == "long" else "call"
            otm = int(meta.get("otm_steps", self.SELL_OTM_STEPS) or 0)
        else:
            option_type = "call" if direction == "long" else "put"
            otm = int(meta.get("otm_steps", self.OTM_STEPS) or 0)
        strike = self.chain.pick_strike(spot, option_type, otm_steps=otm)
        if strike is None:
            return
        symbol = self.chain.symbol_for(strike, option_type)
        if not symbol:
            return
        # Buyers pay the ask; sellers receive the bid.
        entry_premium = await self._fetch_premium(symbol, side="bid" if self.SELL else "ask")
        if entry_premium <= 0:
            return
        per_contract_usd = entry_premium * self.multiplier
        if per_contract_usd <= 0:
            return
        contracts = max(1.0, round(self.STAKE_USD / per_contract_usd))
        # Cap underlying notional so a cheap far-OTM premium can't control a huge position.
        if spot > 0 and self.multiplier > 0:
            max_contracts = (self.NOTIONAL_CAP_MULT * self.STAKE_USD) / (spot * self.multiplier)
            if max_contracts >= 1:
                contracts = min(contracts, float(int(max_contracts)))
        stake = entry_premium * contracts * self.multiplier
        notional = contracts * spot * self.multiplier
        greeks = await self._fetch_greeks(symbol)
        confidence = _clamp(float(meta.get("confidence_score") or 60.0), 0.0, 100.0)
        moneyness = "ATM" if otm == 0 else f"OTM{otm}"
        now_iso = datetime.now(timezone.utc).isoformat()
        metadata = {
            "source": "paper_options_lab",
            "strategy": self.SETUP_TYPE,
            "side": "sell" if self.SELL else "buy",
            "signal_key": signal_key,
            "confidence_score": round(confidence, 1),
            "hard_stop_pct": self.HARD_STOP_PCT,
            "trail_arm_pct": self.TRAIL_ARM_PCT,
            "spot_at_entry": round(spot, 4),
            "greeks": greeks,
            **meta,
        }
        row = {
            "pair": self.pair,
            "base_asset": self.base_asset,
            "option_symbol": symbol,
            "option_type": option_type,
            "strike": float(strike),
            "expiry": self.chain.expiry.strftime("%y%m%d") if self.chain.expiry else None,
            "moneyness": moneyness,
            "setup_type": self.SETUP_TYPE,
            "direction": direction,
            "status": "open",
            "opened_at": now_iso,
            "updated_at": now_iso,
            "entry_premium": round(entry_premium, 8),
            "current_premium": round(entry_premium, 8),
            "spot_at_entry": round(spot, 8),
            "contracts": contracts,
            "option_multiplier": self.multiplier,
            "paper_account_usd": self.PAPER_ACCOUNT_USD,
            "stake_usd": round(stake, 8),
            "notional_usd": round(notional, 8),
            "peak_pnl_pct": 0.0,
            "metadata": metadata,
        }
        trade_id = await self.db.log_paper_options_trade(row)
        if not trade_id:
            return
        self._trade_id = int(trade_id)
        self._option_symbol = symbol
        self._option_type = option_type
        self._direction = direction
        self._strike = float(strike)
        self._entry_premium = entry_premium
        self._contracts = contracts
        self._stake = stake
        self._peak_pnl_pct = 0.0
        self._entry_metadata = metadata
        self._last_signal_key = signal_key
        self.logger.info(
            "%s_OPEN id=%s %s %s %s strike=%s prem=%.4f x%.0f stake=$%.2f conf=%.0f",
            self.SETUP_TYPE, trade_id, self.pair, direction.upper(), moneyness,
            strike, entry_premium, contracts, stake, confidence,
        )

    async def _mark_open(self, premium: float) -> None:
        if not self._trade_id:
            return
        pnl = self._premium_pnl_pct(premium)
        self._peak_pnl_pct = max(self._peak_pnl_pct, pnl)
        await self.db.update_paper_options_trade(
            self._trade_id,
            {
                "current_premium": round(premium, 8),
                "pnl_pct": round(pnl, 4),
                "pnl_usd": round(self._stake * pnl / 100.0, 8),
                "peak_pnl_pct": round(self._peak_pnl_pct, 4),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    def _fees(self, notional: float) -> float:
        per_side = min(self.FEE_PREMIUM_CAP * self._stake, self.FEE_NOTIONAL_RATE * notional)
        return per_side * 2.0

    async def _close(self, exit_premium: float, reason: str) -> None:
        if not self._trade_id:
            return
        pnl = self._premium_pnl_pct(exit_premium)
        gross = self._stake * pnl / 100.0
        notional = self._contracts * (self._entry_metadata.get("spot_at_entry") or 0) * self.multiplier
        fees = self._fees(notional)
        net = gross - fees
        trade_id = self._trade_id
        await self.db.update_paper_options_trade(
            trade_id,
            {
                "status": "closed",
                "exit_premium": round(exit_premium, 8),
                "current_premium": round(exit_premium, 8),
                "closed_at": datetime.now(timezone.utc).isoformat(),
                "pnl_pct": round(pnl, 4),
                "gross_pnl_usd": round(gross, 8),
                "fees_usd": round(fees, 8),
                "pnl_usd": round(net, 8),
                "peak_pnl_pct": round(max(self._peak_pnl_pct, pnl), 4),
                "exit_reason": reason,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        self.logger.info(
            "%s_CLOSE id=%s %s exit=%.4f reason=%s net=$%+.3f pnl=%+.1f%% peak=%+.1f%%",
            self.SETUP_TYPE, trade_id, self.pair, exit_premium, reason, net, pnl, self._peak_pnl_pct,
        )
        self._trade_id = None
        self._option_symbol = None
        self._option_type = None
        self._direction = None
        self._strike = 0.0
        self._entry_premium = 0.0
        self._contracts = 0.0
        self._stake = 0.0
        self._peak_pnl_pct = 0.0
        self._entry_metadata = {}


# ── strategy lanes (price-action on the underlying → buy call/put) ─────────

class TrendRideOptions(BasePaperOptions):
    """Strong EMA trend → buy ATM in trend direction and ride until trend breaks."""

    SETUP_TYPE = "OPT_TREND_RIDE"
    TIMEFRAME = "5m"

    def _entry_decision(self, rows, spot):
        if len(rows) < 30:
            return None
        closed = rows[:-1]
        closes = [r[4] for r in closed]
        ema8 = _ema(closes[-34:], 8)
        ema21 = _ema(closes[-55:], 21)
        close = closes[-1]
        ts = int(closed[-1][0])
        gap = _pct_move(ema21, ema8)
        if ema8 > ema21 and close > ema8 and gap > 0.05:
            conf = _clamp(64 + abs(gap) * 14, 55, 92)
            return "long", f"{ts}:long", {"timeframe": self.TIMEFRAME, "ema8": ema8, "ema21": ema21, "trend_gap_pct": gap, "confidence_score": conf}
        if ema8 < ema21 and close < ema8 and gap < -0.05:
            conf = _clamp(64 + abs(gap) * 14, 55, 92)
            return "short", f"{ts}:short", {"timeframe": self.TIMEFRAME, "ema8": ema8, "ema21": ema21, "trend_gap_pct": gap, "confidence_score": conf}
        return None

    def _underlying_reversed(self, rows, spot):
        if len(rows) < 30:
            return False
        closes = [r[4] for r in rows[:-1]]
        ema21 = _ema(closes[-55:], 21)
        close = closes[-1]
        if self._direction == "long":
            return close < ema21
        return close > ema21


class DonchianBreakoutOptions(BasePaperOptions):
    """20-bar channel breakout → buy in breakout direction, ride to mid-revert."""

    SETUP_TYPE = "OPT_DONCHIAN"
    TIMEFRAME = "5m"
    CHANNEL_LEN = 20

    def _channel(self, rows):
        closed = rows[:-1]
        history = closed[-(self.CHANNEL_LEN + 1):-1]
        upper = max(r[2] for r in history)
        lower = min(r[3] for r in history)
        return upper, lower, (upper + lower) / 2.0

    def _entry_decision(self, rows, spot):
        if len(rows) < self.CHANNEL_LEN + 2:
            return None
        upper, lower, _mid = self._channel(rows)
        signal = rows[:-1][-1]
        close = signal[4]
        ts = int(signal[0])
        if close > upper:
            bp = _pct_move(upper, close)
            return "long", f"{ts}:long", {"timeframe": self.TIMEFRAME, "upper": upper, "lower": lower, "breakout_pct": bp, "confidence_score": _clamp(66 + bp * 45, 55, 93)}
        if close < lower:
            bp = abs(_pct_move(lower, close))
            return "short", f"{ts}:short", {"timeframe": self.TIMEFRAME, "upper": upper, "lower": lower, "breakout_pct": bp, "confidence_score": _clamp(66 + bp * 45, 55, 93)}
        return None

    def _underlying_reversed(self, rows, spot):
        if len(rows) < self.CHANNEL_LEN + 2:
            return False
        _u, _l, mid = self._channel(rows)
        close = rows[:-1][-1][4]
        if self._direction == "long":
            return close < mid
        return close > mid


class MomentumImpulseOptions(BasePaperOptions):
    """1m impulse + volume → buy and ride; can reach 1 step OTM on strong moves."""

    SETUP_TYPE = "OPT_MOMENTUM"
    TIMEFRAME = "1m"
    MOVE_3M_PCT = 0.16
    VOL_RATIO_MIN = 1.12

    def _entry_decision(self, rows, spot):
        if len(rows) < 30:
            return None
        closed = rows[:-1]
        closes = [r[4] for r in closed]
        vols = [r[5] for r in closed]
        ema9 = _ema(closes[-20:], 9)
        move_3m = _pct_move(closes[-4], closes[-1])
        avg_vol = sum(vols[-21:-1]) / max(1, len(vols[-21:-1]))
        vol_ratio = vols[-1] / avg_vol if avg_vol > 0 else 0.0
        ts = int(closed[-1][0])
        strong = abs(move_3m) >= self.MOVE_3M_PCT * 2
        if move_3m >= self.MOVE_3M_PCT and vol_ratio >= self.VOL_RATIO_MIN and closes[-1] > ema9:
            return "long", f"{ts}:long", {"timeframe": self.TIMEFRAME, "move_3m_pct": move_3m, "vol_ratio": vol_ratio, "otm_steps": 1 if strong else 0, "confidence_score": _clamp(64 + (abs(move_3m) - self.MOVE_3M_PCT) * 70, 55, 95)}
        if move_3m <= -self.MOVE_3M_PCT and vol_ratio >= self.VOL_RATIO_MIN and closes[-1] < ema9:
            return "short", f"{ts}:short", {"timeframe": self.TIMEFRAME, "move_3m_pct": move_3m, "vol_ratio": vol_ratio, "otm_steps": 1 if strong else 0, "confidence_score": _clamp(64 + (abs(move_3m) - self.MOVE_3M_PCT) * 70, 55, 95)}
        return None

    def _underlying_reversed(self, rows, spot):
        if len(rows) < 22:
            return False
        closes = [r[4] for r in rows[:-1]]
        ema9 = _ema(closes[-20:], 9)
        close = closes[-1]
        if self._direction == "long":
            return close < ema9
        return close > ema9


class EmaPullbackOptions(BasePaperOptions):
    """Trend + pullback-to-EMA8 entry → buy with the trend, ride to EMA21 loss."""

    SETUP_TYPE = "OPT_EMA_PULLBACK"
    TIMEFRAME = "5m"

    def _entry_decision(self, rows, spot):
        if len(rows) < 35:
            return None
        closed = rows[:-1]
        closes = [r[4] for r in closed]
        lows = [r[3] for r in closed]
        highs = [r[2] for r in closed]
        ema8 = _ema(closes[-34:], 8)
        ema21 = _ema(closes[-55:], 21)
        close, prev = closes[-1], closes[-2]
        ts = int(closed[-1][0])
        gap = _pct_move(ema21, ema8)
        ft = abs(_pct_move(prev, close))
        if ema8 > ema21 and close > ema21 and lows[-1] <= ema8 and close > prev:
            return "long", f"{ts}:long", {"timeframe": self.TIMEFRAME, "trend_gap_pct": gap, "follow_through_pct": ft, "confidence_score": _clamp(62 + abs(gap) * 12 + ft * 18, 50, 88)}
        if ema8 < ema21 and close < ema21 and highs[-1] >= ema8 and close < prev:
            return "short", f"{ts}:short", {"timeframe": self.TIMEFRAME, "trend_gap_pct": gap, "follow_through_pct": ft, "confidence_score": _clamp(62 + abs(gap) * 12 + ft * 18, 50, 88)}
        return None

    def _underlying_reversed(self, rows, spot):
        if len(rows) < 35:
            return False
        closes = [r[4] for r in rows[:-1]]
        ema21 = _ema(closes[-55:], 21)
        close = closes[-1]
        if self._direction == "long":
            return close < ema21
        return close > ema21


class MeanReversionOptions(BasePaperOptions):
    """Fade RSI extremes on 5m: oversold → buy CALL, overbought → buy PUT.

    A counter-trend bet that the underlying snaps back to its mean. Tests
    whether reversals (vs the trend-following lanes) carry any edge.
    """

    SETUP_TYPE = "OPT_MEAN_REVERT"
    TIMEFRAME = "5m"
    RSI_LOW = 30.0
    RSI_HIGH = 70.0

    def _entry_decision(self, rows, spot):
        if len(rows) < 30:
            return None
        closed = rows[:-1]
        closes = [r[4] for r in closed]
        rsi = _rsi(closes, 14)
        ts = int(closed[-1][0])
        if rsi <= self.RSI_LOW:
            return "long", f"{ts}:long", {"timeframe": self.TIMEFRAME, "rsi": rsi, "confidence_score": _clamp(60 + (self.RSI_LOW - rsi) * 1.5, 55, 90)}
        if rsi >= self.RSI_HIGH:
            return "short", f"{ts}:short", {"timeframe": self.TIMEFRAME, "rsi": rsi, "confidence_score": _clamp(60 + (rsi - self.RSI_HIGH) * 1.5, 55, 90)}
        return None

    def _underlying_reversed(self, rows, spot):
        # Exit once price has reverted back to the mean (RSI crosses 50).
        if len(rows) < 16:
            return False
        closes = [r[4] for r in rows[:-1]]
        rsi = _rsi(closes, 14)
        if self._direction == "long":
            return rsi >= 52.0
        return rsi <= 48.0


class VwapPullbackOptions(BasePaperOptions):
    """Institutional VWAP play: in an uptrend buy the dip toward VWAP (call),
    in a downtrend buy the rally toward VWAP (put). Exit when VWAP is lost."""

    SETUP_TYPE = "OPT_VWAP_PULLBACK"
    TIMEFRAME = "5m"

    def _entry_decision(self, rows, spot):
        if len(rows) < 35:
            return None
        closed = rows[:-1]
        closes = [r[4] for r in closed]
        vwap = _vwap(closed)
        if vwap <= 0:
            return None
        ema8 = _ema(closes[-34:], 8)
        ema21 = _ema(closes[-55:], 21)
        close, prev = closes[-1], closes[-2]
        ts = int(closed[-1][0])
        dist = (close - vwap) / vwap * 100.0
        conf = _clamp(66 + (0.5 - abs(dist)) * 18, 55, 90)
        if ema8 > ema21 and -0.15 < dist < 0.5 and close > prev:
            return "long", f"{ts}:long", {"timeframe": self.TIMEFRAME, "vwap": vwap, "dist_pct": dist, "confidence_score": conf}
        if ema8 < ema21 and -0.5 < dist < 0.15 and close < prev:
            return "short", f"{ts}:short", {"timeframe": self.TIMEFRAME, "vwap": vwap, "dist_pct": dist, "confidence_score": conf}
        return None

    def _underlying_reversed(self, rows, spot):
        if len(rows) < 35:
            return False
        closed = rows[:-1]
        vwap = _vwap(closed)
        if vwap <= 0:
            return False
        close = closed[-1][4]
        return close < vwap if self._direction == "long" else close > vwap


class SupertrendOptions(BasePaperOptions):
    """ATR Supertrend: ride the trend direction, exit on the supertrend flip."""

    SETUP_TYPE = "OPT_SUPERTREND"
    TIMEFRAME = "5m"
    ST_PERIOD = 10
    ST_MULT = 3.0

    def _entry_decision(self, rows, spot):
        if len(rows) < self.ST_PERIOD + 5:
            return None
        closed = rows[:-1]
        d = _supertrend_dir(closed, self.ST_PERIOD, self.ST_MULT)
        ts = int(closed[-1][0])
        if d == 1:
            return "long", f"{ts}:long", {"timeframe": self.TIMEFRAME, "supertrend": 1, "confidence_score": 72.0}
        if d == -1:
            return "short", f"{ts}:short", {"timeframe": self.TIMEFRAME, "supertrend": -1, "confidence_score": 72.0}
        return None

    def _underlying_reversed(self, rows, spot):
        if len(rows) < self.ST_PERIOD + 5:
            return False
        d = _supertrend_dir(rows[:-1], self.ST_PERIOD, self.ST_MULT)
        return d == -1 if self._direction == "long" else d == 1


class OpeningRangeBreakoutOptions(BasePaperOptions):
    """ORB: break of the UTC-day opening range (first ORB_BARS bars) → ride the break."""

    SETUP_TYPE = "OPT_ORB"
    TIMEFRAME = "5m"
    ORB_BARS = 3

    def _orb(self, closed):
        today = datetime.fromtimestamp(int(closed[-1][0]) / 1000, tz=timezone.utc).date()
        todays = [r for r in closed if datetime.fromtimestamp(int(r[0]) / 1000, tz=timezone.utc).date() == today]
        if len(todays) < self.ORB_BARS + 1:
            return None
        opening = todays[:self.ORB_BARS]
        return max(r[2] for r in opening), min(r[3] for r in opening)

    def _entry_decision(self, rows, spot):
        if len(rows) < self.ORB_BARS + 2:
            return None
        closed = rows[:-1]
        orb = self._orb(closed)
        if not orb:
            return None
        orh, orl = orb
        close = closed[-1][4]
        day = datetime.fromtimestamp(int(closed[-1][0]) / 1000, tz=timezone.utc).strftime("%y%m%d")
        if close > orh:
            return "long", f"{day}:long", {"timeframe": self.TIMEFRAME, "orb_high": orh, "orb_low": orl, "confidence_score": 74.0}
        if close < orl:
            return "short", f"{day}:short", {"timeframe": self.TIMEFRAME, "orb_high": orh, "orb_low": orl, "confidence_score": 74.0}
        return None

    def _underlying_reversed(self, rows, spot):
        if len(rows) < self.ORB_BARS + 2:
            return False
        orb = self._orb(rows[:-1])
        if not orb:
            return False
        orh, orl = orb
        close = rows[:-1][-1][4]
        return close < orh if self._direction == "long" else close > orl


class MacdCrossOptions(BasePaperOptions):
    """MACD: long when MACD>signal and >0, short when MACD<signal and <0; exit on cross."""

    SETUP_TYPE = "OPT_MACD"
    TIMEFRAME = "5m"

    def _entry_decision(self, rows, spot):
        if len(rows) < 40:
            return None
        closed = rows[:-1]
        closes = [r[4] for r in closed]
        macd, sig = _macd(closes)
        ts = int(closed[-1][0])
        if macd > sig and macd > 0:
            return "long", f"{ts}:long", {"timeframe": self.TIMEFRAME, "macd": macd, "signal": sig, "confidence_score": 70.0}
        if macd < sig and macd < 0:
            return "short", f"{ts}:short", {"timeframe": self.TIMEFRAME, "macd": macd, "signal": sig, "confidence_score": 70.0}
        return None

    def _underlying_reversed(self, rows, spot):
        if len(rows) < 40:
            return False
        closes = [r[4] for r in rows[:-1]]
        macd, sig = _macd(closes)
        return macd < sig if self._direction == "long" else macd > sig


# ── OPTION SELLING lanes (theta harvest — SELL=True) ──────────────────────
# Buying short-dated options lost across 766 paper trades (theta + spread).
# These SELL premium instead: collect the credit, profit as it decays, take 50%,
# cut if it doubles, or ride to near-expiry. The logical flip of a losing buyer.

class SellPutTrendOptions(BasePaperOptions):
    """Uptrend → short an OTM put (collect premium, profit if price holds up)."""
    SETUP_TYPE = "OPT_SELL_PUT"
    TIMEFRAME = "5m"
    SELL = True

    def _entry_decision(self, rows, spot):
        if len(rows) < 35:
            return None
        closes = [r[4] for r in rows[:-1]]
        ema8 = _ema(closes[-34:], 8)
        ema21 = _ema(closes[-55:], 21)
        ts = int(rows[:-1][-1][0])
        if ema8 > ema21 and closes[-1] > ema21:
            return "long", f"{ts}:long", {"timeframe": self.TIMEFRAME, "confidence_score": 70.0}
        return None

    def _underlying_reversed(self, rows, spot):
        if len(rows) < 35:
            return False
        closes = [r[4] for r in rows[:-1]]
        return closes[-1] < _ema(closes[-55:], 21)  # trend broke → short put at risk


class SellCallTrendOptions(BasePaperOptions):
    """Downtrend → short an OTM call (profit if price stays down)."""
    SETUP_TYPE = "OPT_SELL_CALL"
    TIMEFRAME = "5m"
    SELL = True

    def _entry_decision(self, rows, spot):
        if len(rows) < 35:
            return None
        closes = [r[4] for r in rows[:-1]]
        ema8 = _ema(closes[-34:], 8)
        ema21 = _ema(closes[-55:], 21)
        ts = int(rows[:-1][-1][0])
        if ema8 < ema21 and closes[-1] < ema21:
            return "short", f"{ts}:short", {"timeframe": self.TIMEFRAME, "confidence_score": 70.0}
        return None

    def _underlying_reversed(self, rows, spot):
        if len(rows) < 35:
            return False
        closes = [r[4] for r in rows[:-1]]
        return closes[-1] > _ema(closes[-55:], 21)


class SellPremiumNeutralOptions(BasePaperOptions):
    """Quiet/range regime → harvest premium via a far-OTM put (BTC/ETH up-drift)."""
    SETUP_TYPE = "OPT_SELL_NEUTRAL"
    TIMEFRAME = "5m"
    SELL = True
    SELL_OTM_STEPS = 4

    def _entry_decision(self, rows, spot):
        if len(rows) < 35:
            return None
        closes = [r[4] for r in rows[:-1]]
        gap = abs(_pct_move(_ema(closes[-55:], 21), _ema(closes[-34:], 8)))
        rsi = _rsi(closes, 14)
        ts = int(rows[:-1][-1][0])
        if gap < 0.15 and 40 <= rsi <= 65:
            return "long", f"{ts}:long", {"timeframe": self.TIMEFRAME, "ema_gap": gap, "rsi": rsi, "confidence_score": 66.0}
        return None

    def _underlying_reversed(self, rows, spot):
        if len(rows) < 16:
            return False
        return _rsi([r[4] for r in rows[:-1]], 14) < 35


def build_paper_options_strategies(
    pair: str,
    options_exchange: Any,
    futures_exchange: Any,
    db: Database,
) -> list[BasePaperOptions]:
    """Paper OPTION SELLING lab for one underlying (BTC/ETH).

    Pivoted from buying (confirmed loser, 766 trades) to SELLING premium —
    harvest theta, take 50% profit, cut at 2x, ride to near-expiry. OTM strikes
    at varying distance so the data shows which delta/strategy carries edge.
    """
    base = pair.split("/")[0]
    chain = PaperOptionChain(options_exchange, base)
    data = PaperMarketData(futures_exchange, pair)

    def mk(cls, name, **kw):
        return cls(pair, options_exchange, futures_exchange, db, chain,
                   logger_name=f"paper.opt.{name}.{base}", data=data, **kw)

    return [
        # trend-aligned OTM premium selling (3 strikes OTM default)
        mk(SellPutTrendOptions, "sell_put"),
        mk(SellCallTrendOptions, "sell_call"),
        mk(SellPremiumNeutralOptions, "sell_neutral"),
        # further-OTM variants (lower delta = higher win prob, smaller credit)
        mk(SellPutTrendOptions, "sell_put_far", setup_override="OPT_SELL_PUT_FAR", otm_steps=5),
        mk(SellCallTrendOptions, "sell_call_far", setup_override="OPT_SELL_CALL_FAR", otm_steps=5),
    ]

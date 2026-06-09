"""Independent paper futures strategy lab.

These strategies never place exchange orders. They write to
paper_futures_trades so we can compare futures-style entries, holding rules,
and exits against the live options system before risking real futures capital.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Protocol

from alpha.db import Database
from alpha.utils import setup_logger


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class PaperFuturesStrategy(Protocol):
    pair: str
    setup_type: str
    is_active: bool

    async def start(self) -> None: ...
    async def stop(self) -> None: ...


def _ema(values: list[float], period: int) -> float:
    if not values:
        return 0.0
    alpha = 2.0 / (period + 1)
    ema = values[0]
    for value in values[1:]:
        ema = value * alpha + ema * (1.0 - alpha)
    return ema


def _atr_rows(rows: list[list[float]], period: int = 14) -> float:
    """Average true range of the last `period` closed bars."""
    if len(rows) < period + 1:
        return 0.0
    trs: list[float] = []
    for i in range(1, len(rows)):
        h, l, pc = rows[i][2], rows[i][3], rows[i - 1][4]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs[-period:]) / period


def _vwap_rows(rows: list[list[float]]) -> float:
    """Rolling volume-weighted average price over the supplied bars."""
    pv = 0.0
    vol = 0.0
    for r in rows:
        typical = (r[2] + r[3] + r[4]) / 3.0
        pv += typical * r[5]
        vol += r[5]
    return pv / vol if vol > 0 else 0.0


def _pct_move(start: float, end: float) -> float:
    if start <= 0:
        return 0.0
    return (end - start) / start * 100.0


class PaperFuturesPositionBook:
    """In-memory paper exposure lock.

    Paper strategies compete with each other. For a realistic futures model,
    only one paper position may be active per pair at a time.
    """

    def __init__(self) -> None:
        self._active: dict[str, dict[str, Any]] = {}

    def get(self, pair: str) -> dict[str, Any] | None:
        return self._active.get(pair)

    def can_open(self, pair: str) -> bool:
        return pair not in self._active

    def open(self, pair: str, *, trade_id: int, direction: str, setup_type: str) -> None:
        self._active[pair] = {
            "trade_id": trade_id,
            "direction": direction,
            "setup_type": setup_type,
        }

    def close(self, pair: str, trade_id: int | None) -> None:
        active = self._active.get(pair)
        if active and active.get("trade_id") == trade_id:
            self._active.pop(pair, None)


class BasePaperFutures:
    """Base runner and paper ledger helpers for one paper futures strategy."""

    SETUP_TYPE = "PAPER_BASE"
    TIMEFRAME = "5m"
    CHECK_INTERVAL_SEC = 30
    PAPER_ACCOUNT_USD = 1000.0
    MARGIN_USD = 100.0              # money-in per trade (V3: fixed $100, real-account scale)
    BASE_LEVERAGE = 10.0
    FIXED_LEVERAGE: float | None = 10.0
    FEE_RATE = 0.0005
    MIN_CONFIDENCE = 70.0           # V3: entry gate — conf 80+ reached the 10%+ tail 31% vs 15%
    MAX_HOLD_SEC = 24 * 60 * 60     # let winners run; only 1 of 1,468 V2 trades ever held >1h
    # ── V3 exits live in ATR PRICE space, not leveraged-PnL space ──────────
    # V2 lesson: a -6% PnL stop at 67x = a 0.09% price wiggle → 828 noise-stops,
    # 0% win, -$30k (113% of all losses). Stop distance must be independent of
    # leverage: leverage only scales the payoff, never the survival of the idea.
    STOP_ATR_MULT = 1.6             # initial stop: entry ∓ 1.6×ATR(14)
    BREAKEVEN_ATR = 1.2             # once +1.2×ATR in profit, stop jumps to entry (exit with profit)
    TRAIL_ARM_ATR = 1.0             # arm the chandelier after +1×ATR favorable excursion
    TRAIL_ATR_MULT = 1.8            # then trail 1.8×ATR behind the peak price
    STAGNATION_SEC = 2 * 60 * 60    # don't get stuck: flat for 2h within ±0.5×ATR → exit
    STAGNATION_ATR = 0.5
    LIQUIDATION_PCT = -90.0         # margin gone — modeled liquidation
    COOLDOWN_SEC = 0                # aggressive: take every opportunity, re-enter immediately

    def __init__(
        self,
        pair: str,
        exchange: Any,
        db: Database,
        *,
        logger_name: str,
        position_book: PaperFuturesPositionBook,
    ) -> None:
        self.pair = pair
        self.exchange = exchange
        self.db = db
        self.position_book = position_book
        self.logger = setup_logger(logger_name)
        self.setup_type = self.SETUP_TYPE
        self.is_active = False
        self._task: asyncio.Task[None] | None = None
        self._trade_id: int | None = None
        self._direction: str | None = None
        self._entry_price = 0.0
        self._leverage = self.BASE_LEVERAGE
        self._peak_pnl_pct = 0.0
        self._entry_metadata: dict[str, Any] = {}
        self._opened_mono = 0.0
        self._last_signal_key: str | None = None
        self._last_close_mono = 0.0
        self._last_exposure_skip_mono = 0.0
        # V3 price-space exit state
        self._entry_atr = 0.0
        self._stop_price = 0.0
        self._peak_price = 0.0
        self._breakeven_locked = False

    async def start(self) -> None:
        if self.is_active:
            return
        self.is_active = True
        self.logger.info(
            "Starting paper futures strategy: %s %s tf=%s",
            self.SETUP_TYPE,
            self.pair,
            self.TIMEFRAME,
        )
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
                self.logger.exception("Paper futures check failed")
            await asyncio.sleep(self.CHECK_INTERVAL_SEC)

    async def check(self) -> None:
        rows = await self._fetch_rows()
        mark = await self._fetch_mark(rows)
        if mark <= 0:
            return

        if self._trade_id:
            await self._mark_open(mark)
            reason = self._exit_reason(mark, rows)
            if reason:
                await self._close(mark, reason, self._metadata(rows))
            return

        now_mono = asyncio.get_running_loop().time()
        if now_mono - self._last_close_mono < self.COOLDOWN_SEC:
            return

        decision = self._entry_decision(rows, mark)
        if decision is None:
            return
        direction, signal_key, metadata = decision
        if self._last_signal_key == signal_key:
            return
        if float(metadata.get("confidence_score") or 0.0) < self.MIN_CONFIDENCE:
            return
        if not self.position_book.can_open(self.pair):
            active = self.position_book.get(self.pair) or {}
            now = asyncio.get_running_loop().time()
            if now - self._last_exposure_skip_mono > 60:
                self.logger.info(
                    "%s_SKIP %s %s blocked by active paper %s %s id=%s",
                    self.SETUP_TYPE,
                    self.pair,
                    direction.upper(),
                    active.get("setup_type"),
                    str(active.get("direction") or "").upper(),
                    active.get("trade_id"),
                )
                self._last_exposure_skip_mono = now
            return
        metadata.setdefault("atr", _atr_rows(rows[:-1] if rows else []))
        await self._open(direction, mark, signal_key, metadata)

    async def _fetch_rows(self) -> list[list[float]]:
        rows = await self.exchange.fetch_ohlcv(self.pair, self.TIMEFRAME, limit=80)
        return [[float(x) for x in row] for row in rows]

    async def _fetch_mark(self, rows: list[list[float]]) -> float:
        ticker = await self.exchange.fetch_ticker(self.pair)
        if ticker.get("last"):
            return float(ticker["last"])
        if rows:
            return float(rows[-1][4])
        return 0.0

    def _entry_decision(
        self,
        rows: list[list[float]],
        mark: float,
    ) -> tuple[str, str, dict[str, Any]] | None:
        raise NotImplementedError

    def _exit_reason(self, mark: float, rows: list[list[float]]) -> str:
        """V3 exit engine — all distances in underlying PRICE (ATR units).

        Order: liquidation guard → hard ATR stop (ratcheted to breakeven once
        in profit) → chandelier trail behind the peak → stagnation purge →
        max-hold. Leverage never changes WHERE we exit, only what it pays.
        """
        age = asyncio.get_running_loop().time() - self._opened_mono
        if self._pnl_pct(mark) <= self.LIQUIDATION_PCT:
            return "liquidated"
        long = self._direction == "long"
        atr = self._entry_atr
        if self._stop_price > 0:
            if (long and mark <= self._stop_price) or (not long and mark >= self._stop_price):
                return "breakeven_stop" if self._breakeven_locked else "paper_stop"
        if atr > 0:
            peak_fav = (self._peak_price - self._entry_price) if long else (self._entry_price - self._peak_price)
            # ratchet: once the trade has paid 1.2×ATR, never let it go red again
            if not self._breakeven_locked and peak_fav >= self.BREAKEVEN_ATR * atr:
                fee_buffer = self._entry_price * self.FEE_RATE * 2
                self._stop_price = self._entry_price + fee_buffer if long else self._entry_price - fee_buffer
                self._breakeven_locked = True
            if peak_fav >= self.TRAIL_ARM_ATR * atr:
                trail = self._peak_price - self.TRAIL_ATR_MULT * atr if long else self._peak_price + self.TRAIL_ATR_MULT * atr
                if (long and mark <= trail) or (not long and mark >= trail):
                    return "paper_trail"
            # don't get stuck: dead-flat trades release the lane for a live one
            if age >= self.STAGNATION_SEC and abs(mark - self._entry_price) < self.STAGNATION_ATR * atr:
                return "stagnant_exit"
        if age >= self.MAX_HOLD_SEC:
            return "paper_max_hold"
        return ""

    def _metadata(self, rows: list[list[float]]) -> dict[str, Any]:
        return {"source": "independent_paper_strategy", "strategy": self.SETUP_TYPE}

    async def _open(
        self,
        direction: str,
        entry_price: float,
        signal_key: str,
        metadata: dict[str, Any],
    ) -> None:
        if not self.db.is_connected:
            return
        confidence = _clamp(float(metadata.get("confidence_score") or 55.0), 0.0, 100.0)
        leverage = self._leverage_for_confidence(confidence)
        margin = self.MARGIN_USD
        notional = margin * leverage
        atr = float(metadata.get("atr") or 0.0)
        long = direction == "long"
        stop_override = float(metadata.get("stop_price") or 0.0)
        if stop_override > 0:
            stop_price = stop_override
        elif atr > 0:
            stop_price = entry_price - self.STOP_ATR_MULT * atr if long else entry_price + self.STOP_ATR_MULT * atr
        else:
            stop_price = entry_price * (0.99 if long else 1.01)   # ATR unavailable: 1% emergency stop
        now_iso = datetime.now(timezone.utc).isoformat()
        row = {
            "pair": self.pair,
            "base_asset": self.pair.split("/")[0],
            "setup_type": self.SETUP_TYPE,
            "direction": direction,
            "status": "open",
            "entry_price": round(entry_price, 8),
            "current_price": round(entry_price, 8),
            "paper_account_usd": self.PAPER_ACCOUNT_USD,
            "margin_usd": round(margin, 8),
            "notional_usd": round(notional, 8),
            "leverage": leverage,
            "opened_at": now_iso,
            "updated_at": now_iso,
            "metadata": {
                "source": "independent_paper_strategy",
                "strategy": self.SETUP_TYPE,
                "signal_key": signal_key,
                "confidence_score": round(confidence, 1),
                "leverage_model": "fixed_v3_atr_stop",
                "stop_price": round(stop_price, 4),
                **metadata,
            },
        }
        trade_id = await self.db.log_paper_futures_trade(row)
        if not trade_id:
            return
        self.position_book.open(
            self.pair,
            trade_id=int(trade_id),
            direction=direction,
            setup_type=self.SETUP_TYPE,
        )
        self._trade_id = trade_id
        self._direction = direction
        self._entry_price = entry_price
        self._leverage = leverage
        self._peak_pnl_pct = 0.0
        self._entry_atr = atr
        self._stop_price = stop_price
        self._peak_price = entry_price
        self._breakeven_locked = False
        self._entry_metadata = {
            "source": "independent_paper_strategy",
            "strategy": self.SETUP_TYPE,
            "signal_key": signal_key,
            "confidence_score": round(confidence, 1),
            "leverage_model": "fixed_v3_atr_stop",
            "stop_price": round(stop_price, 4),
            **metadata,
        }
        self._opened_mono = asyncio.get_running_loop().time()
        self._last_signal_key = signal_key
        self.logger.info(
            "%s_OPEN id=%s %s %s entry=%.2f lev=%.0fx conf=%.1f",
            self.SETUP_TYPE,
            trade_id,
            self.pair,
            direction.upper(),
            entry_price,
            leverage,
            confidence,
        )

    def _leverage_for_confidence(self, confidence: float) -> float:
        """V3: leverage is FIXED per lane and decoupled from conviction.

        The V2 confidence ladder (25–100×) was the single biggest destroyer of
        capital: win rate decayed 34%@25× → 14%@67× → 16%@100×, and it chained
        the BEST setups to the WORST leverage. Confidence now gates entries
        (MIN_CONFIDENCE); it never sizes them.
        """
        return self.FIXED_LEVERAGE if self.FIXED_LEVERAGE is not None else self.BASE_LEVERAGE

    def _pnl_pct(self, price: float) -> float:
        if self._entry_price <= 0:
            return 0.0
        mult = 1.0 if self._direction == "long" else -1.0
        return _pct_move(self._entry_price, price) * mult * self._leverage

    async def _mark_open(self, price: float) -> None:
        if not self._trade_id:
            return
        pnl_pct = self._pnl_pct(price)
        self._peak_pnl_pct = max(self._peak_pnl_pct, pnl_pct)
        if self._direction == "long":
            self._peak_price = max(self._peak_price, price)
        else:
            self._peak_price = min(self._peak_price, price) if self._peak_price > 0 else price
        margin = self.MARGIN_USD
        await self.db.update_paper_futures_trade(
            self._trade_id,
            {
                "current_price": round(price, 8),
                "pnl_pct": round(pnl_pct, 4),
                "pnl_usd": round(margin * pnl_pct / 100.0, 8),
                "peak_pnl_pct": round(self._peak_pnl_pct, 4),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    async def _close(self, exit_price: float, reason: str, metadata: dict[str, Any]) -> None:
        if not self._trade_id:
            return
        pnl_pct = self._pnl_pct(exit_price)
        margin = self.MARGIN_USD
        notional = margin * self._leverage
        gross = margin * pnl_pct / 100.0
        fees = notional * self.FEE_RATE * 2
        net = gross - fees
        trade_id = self._trade_id
        await self.db.update_paper_futures_trade(
            trade_id,
            {
                "status": "closed",
                "exit_price": round(exit_price, 8),
                "current_price": round(exit_price, 8),
                "closed_at": datetime.now(timezone.utc).isoformat(),
                "pnl_pct": round(pnl_pct, 4),
                "gross_pnl_usd": round(gross, 8),
                "fees_usd": round(fees, 8),
                "pnl_usd": round(net, 8),
                "peak_pnl_pct": round(max(self._peak_pnl_pct, pnl_pct), 4),
                "exit_reason": reason,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    **self._entry_metadata,
                    **metadata,
                },
            },
        )
        self.logger.info(
            "%s_CLOSE id=%s %s exit=%.2f reason=%s net=$%+.4f pnl=%+.2f%% peak=%+.2f%%",
            self.SETUP_TYPE,
            trade_id,
            self.pair,
            exit_price,
            reason,
            net,
            pnl_pct,
            self._peak_pnl_pct,
        )
        self._trade_id = None
        self.position_book.close(self.pair, trade_id)
        self._direction = None
        self._entry_price = 0.0
        self._leverage = self.BASE_LEVERAGE
        self._peak_pnl_pct = 0.0
        self._entry_metadata = {}
        self._opened_mono = 0.0
        self._entry_atr = 0.0
        self._stop_price = 0.0
        self._peak_price = 0.0
        self._breakeven_locked = False
        self._last_close_mono = asyncio.get_running_loop().time()


class DonchianPaperFutures(BasePaperFutures):
    """Paper-only Donchian channel breakout strategy for Delta perpetuals."""

    SETUP_TYPE = "DONCHIAN_BREAKOUT"
    CHANNEL_LEN = 20
    TIMEFRAME = "5m"
    MAX_HOLD_SEC = 4 * 60 * 60   # ride the trend
    STOP_PCT = -6.0
    TRAIL_ARM_PCT = 7.0

    def __init__(self, pair: str, exchange: Any, db: Database, position_book: PaperFuturesPositionBook) -> None:
        super().__init__(
            pair,
            exchange,
            db,
            logger_name=f"paper.donchian.{pair.replace('/', '')}",
            position_book=position_book,
        )

    def _entry_decision(
        self,
        rows: list[list[float]],
        mark: float,
    ) -> tuple[str, str, dict[str, Any]] | None:
        if len(rows) < self.CHANNEL_LEN + 2:
            return None
        closed = rows[:-1]
        signal = closed[-1]
        history = closed[-(self.CHANNEL_LEN + 1):-1]
        upper = max(float(r[2]) for r in history)
        lower = min(float(r[3]) for r in history)
        close = float(signal[4])
        candle_ts = int(signal[0])
        mid = (upper + lower) / 2.0
        channel_width_pct = _pct_move(lower, upper) if lower > 0 else 0.0
        metadata = {
            "timeframe": self.TIMEFRAME,
            "channel_len": self.CHANNEL_LEN,
            "upper": upper,
            "lower": lower,
            "mid": mid,
            "channel_width_pct": channel_width_pct,
        }
        if close > upper:
            breakout_pct = _pct_move(upper, close)
            metadata.update(
                {
                    "breakout_pct": breakout_pct,
                    "confidence_score": _clamp(68.0 + breakout_pct * 45.0 + min(channel_width_pct, 2.0) * 2.0, 55.0, 94.0),
                },
            )
            return "long", f"{candle_ts}:long", metadata
        if close < lower:
            breakout_pct = abs(_pct_move(lower, close))
            metadata.update(
                {
                    "breakout_pct": breakout_pct,
                    "confidence_score": _clamp(68.0 + breakout_pct * 45.0 + min(channel_width_pct, 2.0) * 2.0, 55.0, 94.0),
                },
            )
            return "short", f"{candle_ts}:short", metadata
        return None

    def _exit_reason(self, mark: float, rows: list[list[float]]) -> str:
        reason = super()._exit_reason(mark, rows)
        if reason:
            return reason
        if len(rows) < self.CHANNEL_LEN + 2:
            return ""
        closed = rows[:-1]
        history = closed[-(self.CHANNEL_LEN + 1):-1]
        mid = (max(float(r[2]) for r in history) + min(float(r[3]) for r in history)) / 2.0
        close = float(closed[-1][4])
        if self._direction == "long" and close < mid:
            return "donchian_mid_revert"
        if self._direction == "short" and close > mid:
            return "donchian_mid_revert"
        return ""


class EmaPullbackPaperFutures(BasePaperFutures):
    """Paper-only trend pullback strategy using EMA 8/21 structure."""

    SETUP_TYPE = "EMA_PULLBACK"
    TIMEFRAME = "5m"
    MAX_HOLD_SEC = 4 * 60 * 60   # ride the trend
    STOP_PCT = -5.0
    TRAIL_ARM_PCT = 6.0

    def __init__(self, pair: str, exchange: Any, db: Database, position_book: PaperFuturesPositionBook) -> None:
        super().__init__(
            pair,
            exchange,
            db,
            logger_name=f"paper.ema_pullback.{pair.replace('/', '')}",
            position_book=position_book,
        )

    def _entry_decision(
        self,
        rows: list[list[float]],
        mark: float,
    ) -> tuple[str, str, dict[str, Any]] | None:
        if len(rows) < 35:
            return None
        closed = rows[:-1]
        closes = [float(r[4]) for r in closed]
        lows = [float(r[3]) for r in closed]
        highs = [float(r[2]) for r in closed]
        ema8 = _ema(closes[-34:], 8)
        ema21 = _ema(closes[-55:], 21)
        close = closes[-1]
        prev_close = closes[-2]
        candle_ts = int(closed[-1][0])
        trend_gap = _pct_move(ema21, ema8)
        follow_through_pct = abs(_pct_move(prev_close, close))
        metadata = {
            "timeframe": self.TIMEFRAME,
            "ema8": ema8,
            "ema21": ema21,
            "trend_gap_pct": trend_gap,
            "follow_through_pct": follow_through_pct,
        }
        if ema8 > ema21 and close > ema21 and lows[-1] <= ema8 and close > prev_close:
            metadata["confidence_score"] = _clamp(62.0 + abs(trend_gap) * 12.0 + follow_through_pct * 18.0, 50.0, 88.0)
            return "long", f"{candle_ts}:long", metadata
        if ema8 < ema21 and close < ema21 and highs[-1] >= ema8 and close < prev_close:
            metadata["confidence_score"] = _clamp(62.0 + abs(trend_gap) * 12.0 + follow_through_pct * 18.0, 50.0, 88.0)
            return "short", f"{candle_ts}:short", metadata
        return None

    def _exit_reason(self, mark: float, rows: list[list[float]]) -> str:
        reason = super()._exit_reason(mark, rows)
        if reason:
            return reason
        if len(rows) < 35:
            return ""
        closed = rows[:-1]
        closes = [float(r[4]) for r in closed]
        ema21 = _ema(closes[-55:], 21)
        close = closes[-1]
        if self._direction == "long" and close < ema21:
            return "ema21_lost"
        if self._direction == "short" and close > ema21:
            return "ema21_reclaimed"
        return ""


class MomentumImpulsePaperFutures(BasePaperFutures):
    """Paper-only continuation entry when a 1m impulse has volume support."""

    SETUP_TYPE = "MOMENTUM_IMPULSE"
    TIMEFRAME = "1m"
    MAX_HOLD_SEC = 25 * 60
    STOP_PCT = -5.0
    TRAIL_ARM_PCT = 5.0
    TRAIL_RETRACE_PCT = 0.50
    MOVE_3M_PCT = 0.16
    VOL_RATIO_MIN = 1.12

    def __init__(self, pair: str, exchange: Any, db: Database, position_book: PaperFuturesPositionBook) -> None:
        super().__init__(
            pair,
            exchange,
            db,
            logger_name=f"paper.momentum_impulse.{pair.replace('/', '')}",
            position_book=position_book,
        )

    def _entry_decision(
        self,
        rows: list[list[float]],
        mark: float,
    ) -> tuple[str, str, dict[str, Any]] | None:
        if len(rows) < 30:
            return None
        closed = rows[:-1]
        closes = [float(r[4]) for r in closed]
        vols = [float(r[5]) for r in closed]
        ema9 = _ema(closes[-20:], 9)
        move_3m = _pct_move(closes[-4], closes[-1])
        avg_vol = sum(vols[-21:-1]) / max(1, len(vols[-21:-1]))
        vol_ratio = vols[-1] / avg_vol if avg_vol > 0 else 0.0
        candle_ts = int(closed[-1][0])
        metadata = {
            "timeframe": self.TIMEFRAME,
            "move_3m_pct": move_3m,
            "vol_ratio": vol_ratio,
            "ema9": ema9,
        }
        if move_3m >= self.MOVE_3M_PCT and vol_ratio >= self.VOL_RATIO_MIN and closes[-1] > ema9:
            metadata["confidence_score"] = _clamp(
                64.0 + (move_3m - self.MOVE_3M_PCT) * 70.0 + (vol_ratio - self.VOL_RATIO_MIN) * 12.0,
                55.0,
                96.0,
            )
            return "long", f"{candle_ts}:long", metadata
        if move_3m <= -self.MOVE_3M_PCT and vol_ratio >= self.VOL_RATIO_MIN and closes[-1] < ema9:
            metadata["confidence_score"] = _clamp(
                64.0 + (abs(move_3m) - self.MOVE_3M_PCT) * 70.0 + (vol_ratio - self.VOL_RATIO_MIN) * 12.0,
                55.0,
                96.0,
            )
            return "short", f"{candle_ts}:short", metadata
        return None


class SignalMixPaperFutures(BasePaperFutures):
    """Paper-only entries from the live scalp signal mix, including blocked ideas."""

    SETUP_TYPE = "SIGNAL_MIX"
    TIMEFRAME = "signals"
    CHECK_INTERVAL_SEC = 15
    MAX_HOLD_SEC = 35 * 60
    STOP_PCT = -6.0
    TRAIL_ARM_PCT = 6.0

    def __init__(
        self,
        pair: str,
        exchange: Any,
        db: Database,
        scalp_strategy: Any,
        position_book: PaperFuturesPositionBook,
    ) -> None:
        super().__init__(
            pair,
            exchange,
            db,
            logger_name=f"paper.signal_mix.{pair.replace('/', '')}",
            position_book=position_book,
        )
        self.scalp_strategy = scalp_strategy

    async def _fetch_rows(self) -> list[list[float]]:
        return []

    def _entry_decision(
        self,
        rows: list[list[float]],
        mark: float,
    ) -> tuple[str, str, dict[str, Any]] | None:
        state = getattr(self.scalp_strategy, "last_signal_state", None) or {}
        if not state:
            return None
        state_ts = float(state.get("timestamp") or 0.0)
        if state_ts and asyncio.get_running_loop().time() - state_ts > 90:
            return None

        bull_count = int(state.get("bull_count") or 0)
        bear_count = int(state.get("bear_count") or 0)
        strength = int(state.get("strength") or max(bull_count, bear_count))
        side = state.get("side")
        if side not in ("long", "short"):
            if bull_count >= 3 and bull_count > bear_count:
                side = "long"
                strength = max(strength, bull_count)
            elif bear_count >= 3 and bear_count > bull_count:
                side = "short"
                strength = max(strength, bear_count)
            else:
                return None

        momentum_60s = float(state.get("momentum_60s") or 0.0)
        aligned = (side == "long" and momentum_60s >= 0.05) or (side == "short" and momentum_60s <= -0.05)
        if strength < 3 or not aligned:
            return None

        signal_bucket = int(state_ts // 60) if state_ts else int(asyncio.get_running_loop().time() // 60)
        direction = "long" if side == "long" else "short"
        metadata = {
            "timeframe": "signal_state",
            "strength": strength,
            "bull_count": bull_count,
            "bear_count": bear_count,
            "momentum_60s": momentum_60s,
            "rsi": state.get("rsi"),
            "trend_15m": state.get("trend_15m"),
            "reason": state.get("reason"),
            "skip_reason": state.get("skip_reason"),
            "confidence_score": _clamp(55.0 + strength * 8.0 + abs(momentum_60s) * 120.0, 55.0, 96.0),
        }
        return direction, f"{signal_bucket}:{direction}:{strength}", metadata

    def _exit_reason(self, mark: float, rows: list[list[float]]) -> str:
        reason = super()._exit_reason(mark, rows)
        if reason:
            return reason
        state = getattr(self.scalp_strategy, "last_signal_state", None) or {}
        momentum_60s = float(state.get("momentum_60s") or 0.0)
        if self._direction == "long" and momentum_60s < -0.08:
            return "signal_momentum_flip"
        if self._direction == "short" and momentum_60s > 0.08:
            return "signal_momentum_flip"
        return ""


# ── V3 lanes: pullback/retest entries, chop filters, ATR price-space exits ──
# Built from the V2 evidence (1,468 closed trades, −$26.7k, 26 burns):
#  * the ONLY profitable cohorts were trades that survived 10+ minutes (51% win,
#    +$1,788) and trades reaching a 25%+ peak (91–97% win, +$5.2k);
#  * 828 trades noise-stopped at 0% win because the stop lived in leveraged-PnL
#    space; 65% of all loss came from 1m momentum + the 100× lane.
# V3 therefore: fixed 10–20× leverage, ATR price stops, breakeven ratchet,
# conf-gated pullback entries, and a 20× lane as an A/B against identical 10×
# entries so leverage's marginal effect is finally measured cleanly.


class EmaPullbackV3(BasePaperFutures):
    """EMA 8/21 trend + pullback-to-EMA8 + follow-through, with a chop filter.

    The best V2 entry (34.7% win, least-bad lane) — now gated so the flat-tape
    junk that produced the <2%-peak graveyard is skipped entirely.
    """

    SETUP_TYPE = "FUT_EMA_PB"
    TIMEFRAME = "5m"
    MIN_TREND_GAP_PCT = 0.06     # EMA8 vs EMA21 separation — flat tape = no trade
    MIN_FOLLOW_PCT = 0.04        # the bounce candle must actually move

    def __init__(self, pair: str, exchange: Any, db: Database, position_book: PaperFuturesPositionBook) -> None:
        super().__init__(
            pair, exchange, db,
            logger_name=f"paper.ema_pb_v3.{pair.replace('/', '')}",
            position_book=position_book,
        )

    def _entry_decision(self, rows, mark):
        if len(rows) < 35:
            return None
        closed = rows[:-1]
        closes = [float(r[4]) for r in closed]
        lows = [float(r[3]) for r in closed]
        highs = [float(r[2]) for r in closed]
        ema8 = _ema(closes[-34:], 8)
        ema21 = _ema(closes[-55:], 21)
        close, prev = closes[-1], closes[-2]
        ts = int(closed[-1][0])
        gap = _pct_move(ema21, ema8)
        ft = abs(_pct_move(prev, close))
        if abs(gap) < self.MIN_TREND_GAP_PCT or ft < self.MIN_FOLLOW_PCT:
            return None
        meta = {
            "timeframe": self.TIMEFRAME,
            "ema8": ema8, "ema21": ema21,
            "trend_gap_pct": gap, "follow_through_pct": ft,
            "confidence_score": _clamp(70.0 + abs(gap) * 60.0 + ft * 40.0, 70.0, 95.0),
        }
        if gap > 0 and close > ema21 and lows[-1] <= ema8 and close > prev:
            return "long", f"{ts}:long", meta
        if gap < 0 and close < ema21 and highs[-1] >= ema8 and close < prev:
            return "short", f"{ts}:short", meta
        return None


class DonchianRetestV3(BasePaperFutures):
    """FRESH Donchian-20 breakout only — never chase an extended one.

    V2 entered on every bar that closed beyond the channel (including bar 10 of
    a move, the top). V3 requires the PREVIOUS bar inside the channel (first
    close beyond) and refuses breakouts already stretched past 0.4%.
    """

    SETUP_TYPE = "FUT_DONCHIAN_RT"
    TIMEFRAME = "5m"
    CHANNEL_LEN = 20
    MAX_CHASE_PCT = 0.40         # skip if close is already this far past the band
    MIN_WIDTH_PCT = 0.30         # a meaningful channel, not a flat-tape ribbon

    def __init__(self, pair: str, exchange: Any, db: Database, position_book: PaperFuturesPositionBook) -> None:
        super().__init__(
            pair, exchange, db,
            logger_name=f"paper.donchian_rt_v3.{pair.replace('/', '')}",
            position_book=position_book,
        )

    def _entry_decision(self, rows, mark):
        if len(rows) < self.CHANNEL_LEN + 3:
            return None
        closed = rows[:-1]
        history = closed[-(self.CHANNEL_LEN + 1):-1]
        upper = max(float(r[2]) for r in history)
        lower = min(float(r[3]) for r in history)
        close = float(closed[-1][4])
        prev_close = float(closed[-2][4])
        ts = int(closed[-1][0])
        width = _pct_move(lower, upper) if lower > 0 else 0.0
        if width < self.MIN_WIDTH_PCT:
            return None
        meta = {
            "timeframe": self.TIMEFRAME, "channel_len": self.CHANNEL_LEN,
            "upper": upper, "lower": lower, "channel_width_pct": width,
        }
        if close > upper and prev_close <= upper:
            bp = _pct_move(upper, close)
            if bp > self.MAX_CHASE_PCT:
                return None
            meta.update({"breakout_pct": bp, "confidence_score": _clamp(71.0 + width * 8.0 + bp * 20.0, 70.0, 92.0)})
            return "long", f"{ts}:long", meta
        if close < lower and prev_close >= lower:
            bp = abs(_pct_move(lower, close))
            if bp > self.MAX_CHASE_PCT:
                return None
            meta.update({"breakout_pct": bp, "confidence_score": _clamp(71.0 + width * 8.0 + bp * 20.0, 70.0, 92.0)})
            return "short", f"{ts}:short", meta
        return None


class VwapBounceV3(BasePaperFutures):
    """Institutional VWAP pullback: with the trend, enter the bounce off VWAP."""

    SETUP_TYPE = "FUT_VWAP"
    TIMEFRAME = "5m"
    VWAP_BARS = 60
    TOUCH_PCT = 0.0008           # the bar must have actually tagged VWAP (±0.08%)
    MAX_DIST_PCT = 0.35          # and closed back with the trend, not run away

    def __init__(self, pair: str, exchange: Any, db: Database, position_book: PaperFuturesPositionBook) -> None:
        super().__init__(
            pair, exchange, db,
            logger_name=f"paper.vwap_v3.{pair.replace('/', '')}",
            position_book=position_book,
        )

    def _entry_decision(self, rows, mark):
        if len(rows) < self.VWAP_BARS + 2:
            return None
        closed = rows[:-1]
        closes = [float(r[4]) for r in closed]
        vwap = _vwap_rows(closed[-self.VWAP_BARS:])
        if vwap <= 0:
            return None
        ema8 = _ema(closes[-34:], 8)
        ema21 = _ema(closes[-55:], 21)
        close, prev = closes[-1], closes[-2]
        low, high = float(closed[-1][3]), float(closed[-1][2])
        ts = int(closed[-1][0])
        gap = _pct_move(ema21, ema8)
        dist = (close - vwap) / vwap * 100.0
        meta = {"timeframe": self.TIMEFRAME, "vwap": vwap, "dist_pct": dist, "trend_gap_pct": gap}
        if gap > 0.05 and low <= vwap * (1 + self.TOUCH_PCT) and 0.0 < dist < self.MAX_DIST_PCT and close > prev:
            meta["confidence_score"] = _clamp(72.0 + gap * 50.0, 70.0, 92.0)
            return "long", f"{ts}:long", meta
        if gap < -0.05 and high >= vwap * (1 - self.TOUCH_PCT) and -self.MAX_DIST_PCT < dist < 0.0 and close < prev:
            meta["confidence_score"] = _clamp(72.0 + abs(gap) * 50.0, 70.0, 92.0)
            return "short", f"{ts}:short", meta
        return None


class SfpReversalV3(BasePaperFutures):
    """Liquidity sweep / swing-failure: price spikes through an obvious swing
    level (stop hunt), then closes back inside — enter the reclaim with the
    stop just beyond the sweep wick (tight, STRUCTURAL, not noise)."""

    SETUP_TYPE = "FUT_SFP"
    TIMEFRAME = "5m"
    SWING_BARS = 12
    STOP_PAD_ATR = 0.25          # stop sits just past the swept extreme

    def __init__(self, pair: str, exchange: Any, db: Database, position_book: PaperFuturesPositionBook) -> None:
        super().__init__(
            pair, exchange, db,
            logger_name=f"paper.sfp_v3.{pair.replace('/', '')}",
            position_book=position_book,
        )

    def _entry_decision(self, rows, mark):
        if len(rows) < self.SWING_BARS + 4:
            return None
        closed = rows[:-1]
        sig = closed[-1]
        prior = closed[-(self.SWING_BARS + 1):-1]
        swing_low = min(float(r[3]) for r in prior)
        swing_high = max(float(r[2]) for r in prior)
        low, high, close = float(sig[3]), float(sig[2]), float(sig[4])
        ts = int(sig[0])
        atr = _atr_rows(closed)
        if atr <= 0:
            return None
        if low < swing_low and close > swing_low:
            reclaim = (close - swing_low) / atr
            return "long", f"{ts}:long", {
                "timeframe": self.TIMEFRAME, "swing_low": swing_low, "sweep_low": low,
                "reclaim_atr": reclaim, "stop_price": low - self.STOP_PAD_ATR * atr,
                "confidence_score": _clamp(72.0 + reclaim * 10.0, 70.0, 92.0),
            }
        if high > swing_high and close < swing_high:
            reclaim = (swing_high - close) / atr
            return "short", f"{ts}:short", {
                "timeframe": self.TIMEFRAME, "swing_high": swing_high, "sweep_high": high,
                "reclaim_atr": reclaim, "stop_price": high + self.STOP_PAD_ATR * atr,
                "confidence_score": _clamp(72.0 + reclaim * 10.0, 70.0, 92.0),
            }
        return None


def build_paper_futures_strategies(
    pair: str,
    exchange: Any,
    db: Database,
    scalp_strategy: Any | None = None,
) -> list[PaperFuturesStrategy]:
    """V3 round — apply EVERYTHING the first 1,468 trades taught us.

    Fixed 10–20× leverage (user wants leverage; the data caps how much survives),
    pullback/retest entries with chop filters, conf≥70 gate, ATR price stops,
    breakeven ratchet at +1.2 ATR, chandelier trail, stagnation purge, 24h max
    hold. FUT_EMA_PB runs at BOTH 10× and 20× on identical entries — the clean
    leverage A/B the ladder never gave us. Paper only; never places real orders.
    """
    def mk(cls, setup: str, lev: float) -> PaperFuturesStrategy:
        s = cls(pair, exchange, db, PaperFuturesPositionBook())
        s.FIXED_LEVERAGE = lev
        s.SETUP_TYPE = setup
        s.setup_type = setup
        return s

    return [
        mk(EmaPullbackV3, "FUT_EMA_PB_10X", 10.0),
        mk(EmaPullbackV3, "FUT_EMA_PB_20X", 20.0),     # leverage A/B vs identical entries
        mk(DonchianRetestV3, "FUT_DONCHIAN_RT_10X", 10.0),
        mk(VwapBounceV3, "FUT_VWAP_10X", 10.0),
        mk(SfpReversalV3, "FUT_SFP_15X", 15.0),        # tight structural stop earns extra lev
    ]

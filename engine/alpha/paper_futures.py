"""Independent paper futures strategies.

These strategies never place exchange orders. They write to
paper_futures_trades so we can compare futures-style signals against the live
options system before risking real futures capital.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from alpha.db import Database
from alpha.utils import setup_logger


class DonchianPaperFutures:
    """Paper-only Donchian channel breakout strategy for Delta perpetuals."""

    SETUP_TYPE = "DONCHIAN_BREAKOUT"
    PAPER_ACCOUNT_USD = 100.0
    ALLOC_PCT = 0.25
    LEVERAGE = 5.0
    FEE_RATE = 0.0005
    CHANNEL_LEN = 20
    TIMEFRAME = "5m"
    CHECK_INTERVAL_SEC = 30
    MAX_HOLD_SEC = 45 * 60
    STOP_PCT = -4.0
    TRAIL_ARM_PCT = 6.0
    TRAIL_RETRACE_PCT = 0.45

    def __init__(self, pair: str, exchange: Any, db: Database) -> None:
        self.pair = pair
        self.exchange = exchange
        self.db = db
        self.logger = setup_logger(f"paper.donchian.{pair.replace('/', '')}")
        self.is_active = False
        self._task: asyncio.Task[None] | None = None
        self._trade_id: int | None = None
        self._direction: str | None = None
        self._entry_price = 0.0
        self._peak_pnl_pct = 0.0
        self._opened_mono = 0.0
        self._last_signal_candle_ts: int | None = None

    async def start(self) -> None:
        if self.is_active:
            return
        self.is_active = True
        self.logger.info(
            "Starting paper futures strategy: %s %s channel=%d %s",
            self.SETUP_TYPE,
            self.pair,
            self.CHANNEL_LEN,
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
        rows = await self.exchange.fetch_ohlcv(
            self.pair,
            self.TIMEFRAME,
            limit=self.CHANNEL_LEN + 3,
        )
        if len(rows) < self.CHANNEL_LEN + 2:
            return

        closed = rows[:-1]  # ignore currently forming candle
        signal_candle = closed[-1]
        history = closed[-(self.CHANNEL_LEN + 1):-1]
        upper = max(float(r[2]) for r in history)
        lower = min(float(r[3]) for r in history)
        mid = (upper + lower) / 2.0
        close = float(signal_candle[4])
        candle_ts = int(signal_candle[0])

        ticker = await self.exchange.fetch_ticker(self.pair)
        mark = float(ticker.get("last") or close)
        if mark <= 0:
            return

        if self._trade_id:
            await self._mark_open(mark)
            await self._maybe_exit(mark=mark, close=close, mid=mid, upper=upper, lower=lower)
            return

        if self._last_signal_candle_ts == candle_ts:
            return

        if close > upper:
            await self._open("long", mark, candle_ts, upper, lower, mid)
        elif close < lower:
            await self._open("short", mark, candle_ts, upper, lower, mid)

    async def _open(
        self,
        direction: str,
        entry_price: float,
        candle_ts: int,
        upper: float,
        lower: float,
        mid: float,
    ) -> None:
        if not self.db.is_connected:
            return
        margin = self.PAPER_ACCOUNT_USD * self.ALLOC_PCT
        notional = margin * self.LEVERAGE
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
            "leverage": self.LEVERAGE,
            "opened_at": now_iso,
            "updated_at": now_iso,
            "metadata": {
                "source": "independent_paper_strategy",
                "strategy": self.SETUP_TYPE,
                "timeframe": self.TIMEFRAME,
                "channel_len": self.CHANNEL_LEN,
                "upper": upper,
                "lower": lower,
                "mid": mid,
            },
        }
        trade_id = await self.db.log_paper_futures_trade(row)
        if not trade_id:
            return
        self._trade_id = trade_id
        self._direction = direction
        self._entry_price = entry_price
        self._peak_pnl_pct = 0.0
        self._opened_mono = asyncio.get_running_loop().time()
        self._last_signal_candle_ts = candle_ts
        self.logger.info(
            "DONCHIAN_PAPER_OPEN id=%s %s %s entry=%.2f upper=%.2f lower=%.2f",
            trade_id,
            self.pair,
            direction.upper(),
            entry_price,
            upper,
            lower,
        )

    def _pnl_pct(self, price: float) -> float:
        if self._entry_price <= 0:
            return 0.0
        mult = 1.0 if self._direction == "long" else -1.0
        spot_pct = (price - self._entry_price) / self._entry_price * 100.0 * mult
        return spot_pct * self.LEVERAGE

    async def _mark_open(self, price: float) -> None:
        if not self._trade_id:
            return
        pnl_pct = self._pnl_pct(price)
        self._peak_pnl_pct = max(self._peak_pnl_pct, pnl_pct)
        margin = self.PAPER_ACCOUNT_USD * self.ALLOC_PCT
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

    async def _maybe_exit(
        self,
        *,
        mark: float,
        close: float,
        mid: float,
        upper: float,
        lower: float,
    ) -> None:
        pnl_pct = self._pnl_pct(mark)
        age = asyncio.get_running_loop().time() - self._opened_mono
        reason = ""
        if pnl_pct <= self.STOP_PCT:
            reason = "paper_stop"
        elif self._peak_pnl_pct >= self.TRAIL_ARM_PCT:
            floor = self._peak_pnl_pct * (1.0 - self.TRAIL_RETRACE_PCT)
            if pnl_pct <= floor:
                reason = "paper_trail"
        if not reason and self._direction == "long" and close < mid:
            reason = "donchian_mid_revert"
        if not reason and self._direction == "short" and close > mid:
            reason = "donchian_mid_revert"
        if not reason and age >= self.MAX_HOLD_SEC:
            reason = "paper_max_hold"
        if reason:
            await self._close(mark, reason, upper, lower, mid)

    async def _close(
        self,
        exit_price: float,
        reason: str,
        upper: float,
        lower: float,
        mid: float,
    ) -> None:
        if not self._trade_id:
            return
        pnl_pct = self._pnl_pct(exit_price)
        margin = self.PAPER_ACCOUNT_USD * self.ALLOC_PCT
        notional = margin * self.LEVERAGE
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
                    "source": "independent_paper_strategy",
                    "strategy": self.SETUP_TYPE,
                    "timeframe": self.TIMEFRAME,
                    "channel_len": self.CHANNEL_LEN,
                    "upper": upper,
                    "lower": lower,
                    "mid": mid,
                },
            },
        )
        self.logger.info(
            "DONCHIAN_PAPER_CLOSE id=%s %s exit=%.2f reason=%s net=$%+.4f pnl=%+.2f%% peak=%+.2f%%",
            trade_id,
            self.pair,
            exit_price,
            reason,
            net,
            pnl_pct,
            self._peak_pnl_pct,
        )
        self._trade_id = None
        self._direction = None
        self._entry_price = 0.0
        self._peak_pnl_pct = 0.0
        self._opened_mono = 0.0

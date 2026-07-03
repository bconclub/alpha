"""V4 signal engine — 4h trend rider (Donchian breakout), signals only.

Why V4 (07-03 backtest on 20 days of real Delta candles, our sizing + fees):
    5m scalper (what we ran):      253 trades  −$19.20
    15m Donchian trail:            366 trades  −$44.48
    1h  fast-invalidation:         130 trades  −$28.31
    1h  Donchian wide trail:        76 trades   −$9.04
    4h  Donchian-20 + 3ATR trail:   15 trades  +$12.86   ← the only green config

The gradient was unambiguous: slower = better; 4h flips positive. It is also the
user's stated thesis: "get in early, stay in the market; if it goes against us,
cut out; if it's staying, we stay and take the money."

Signal: a 4h close beyond the prior 20-bar (≈3.3-day) high/low box. Long above,
short below. Fresh breaks only (one entry per breakout candle). The 4h box IS
the higher-timeframe filter — no extra gates, no confidence theater.

This module stays PURE READ: fetches candles, returns the current signal per
pair. The trader (`live_trader.py`) manages entries/exits (3×ATR(4h) chandelier).
"""

from __future__ import annotations

import asyncio
from typing import Any

from alpha.utils import setup_logger

logger = setup_logger("strategy_v4")

TIMEFRAME = "4h"
CANDLE_LIMIT = 60
CHANNEL_LEN = 20            # Donchian box length (backtested: N=20 on 4h)
TRAIL_ATR_MULT = 3.0        # published so the trader + docs share one number

# Kept for back-compat imports elsewhere in the engine.
MIN_CONFIDENCE = 90.0


# ── pure indicator helpers ───────────────────────────────────────────────────
def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


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


def _pct_move(start: float, end: float) -> float:
    if start <= 0:
        return 0.0
    return (end - start) / start * 100.0


class SignalEngine:
    """Per-pair 4h Donchian breakout reader. One instance per traded pair."""

    def __init__(self, pair: str, exchange: Any) -> None:
        self.pair = pair
        self.exchange = exchange
        self._last: dict[str, Any] | None = None
        self._last_signal_key: str | None = None   # one entry per breakout candle

    async def _fetch_rows(self) -> list[list[float]]:
        rows = await self.exchange.fetch_ohlcv(self.pair, TIMEFRAME, limit=CANDLE_LIMIT)
        return [[float(x) for x in row] for row in rows]

    async def evaluate(self) -> dict[str, Any] | None:
        """Full read: the firing `best` signal (if any) + a proximity scan.

        Shape (unchanged from V3 so trader + dashboard keep working):
        {pair, mark, atr, htf_trend, status, best|None, lanes:[...]}
        """
        try:
            rows = await self._fetch_rows()
        except Exception:
            logger.exception("signal fetch failed %s", self.pair)
            return None
        if len(rows) < CHANNEL_LEN + 16:
            return None
        closed = rows[:-1]                      # decide on CLOSED 4h candles only
        sig = closed[-1]
        history = closed[-(CHANNEL_LEN + 1):-1]
        upper = max(float(r[2]) for r in history)
        lower = min(float(r[3]) for r in history)
        close = float(sig[4])
        ts = int(sig[0])
        mark = float(rows[-1][4])
        atr = _atr_rows(closed)
        width = _pct_move(lower, upper) if lower > 0 else 0.0
        # cosmetic trend hint for the dashboard (box mid-point drift)
        mid = (upper + lower) / 2.0
        htf = 1 if close > mid else (-1 if close < mid else 0)

        best: dict[str, Any] | None = None
        direction = None
        if close > upper:
            direction = "long"
        elif close < lower:
            direction = "short"
        if direction:
            key = f"{ts}:{direction}"
            if key != self._last_signal_key:
                self._last_signal_key = key
                bp = _pct_move(upper, close) if direction == "long" else abs(_pct_move(lower, close))
                conf = _clamp(90.0 + min(bp, 1.0) * 8.0, 90.0, 98.0)   # cosmetic, flat 10x anyway
                best = {
                    "pair": self.pair, "lane": "FUT_DONCHIAN_4H", "direction": direction,
                    "signal_key": key, "confidence": conf, "htf_trend": htf,
                    "atr": atr, "mark": mark,
                    "metadata": {
                        "lane": "FUT_DONCHIAN_4H", "timeframe": TIMEFRAME,
                        "channel_len": CHANNEL_LEN, "upper": upper, "lower": lower,
                        "channel_width_pct": width, "breakout_pct": bp,
                        "confidence_score": conf,
                    },
                }

        # proximity scan for the dashboard: how close is price to breaking the box
        d_up = _pct_move(mark, upper)      # % move needed to break up
        d_dn = _pct_move(lower, mark)      # inverse gap down (positive when above lower)
        near_up = max(0.0, min(95.0, 95.0 * (1.0 - abs(d_up) / 1.2)))
        near_dn = max(0.0, min(95.0, 95.0 * (1.0 - abs(_pct_move(mark, lower)) / 1.2)))
        def fp(x: float) -> str:   # price with sane precision for sub-$1 assets
            return f"{x:,.0f}" if x >= 100 else (f"{x:.3f}" if x >= 1 else f"{x:.4f}")
        if near_up >= near_dn:
            side, ready, watching, level = "LONG", near_up, f"break {fp(upper)} (4h box high)", upper
        else:
            side, ready, watching, level = "SHORT", near_dn, f"break {fp(lower)} (4h box low)", lower
        if best:
            status = "READY"
        elif ready >= 78:
            status = "CLOSE"
        else:
            status = "SCANNING"
        lanes = [{
            "lane": "FUT_DONCHIAN_4H", "name": "Donchian 4h",
            "status": "READY" if best else ("CLOSE" if ready >= 78 else ("SCANNING" if ready >= 35 else "WAITING")),
            "readiness": round(ready, 0), "watching": watching,
            "level": round(level, 2) if level else None,
            "would_conf": 92.0, "side": side,
        }]

        result = {
            "pair": self.pair, "mark": mark, "atr": atr, "htf_trend": htf,
            "status": status, "best": best, "lanes": lanes,
        }
        self._last = result
        return result

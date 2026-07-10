"""V5 signal engine — 1h trend rider (Donchian breakout, 4h-aligned), signals only.

Why V5 (07-10, 30-day backtest on real Delta 5m candles, our sizing + fees):
    momentum-burst scalps (8 variants):  −$48 … −$100   more trades ≠ more money
    every harvest / time-stop variant:   negative        capping winners kills the edge
    4h Donchian-20 + 3ATR (V4 as-is):     21 trades  +$0.16   breakeven in chop
    1h Donchian-20 + 3ATR trail:         106 trades  +$1.48
    1h Donchian-20 + 3ATR + 4h align:     89 trades  +$6.50   ← winner, ~3 signals/day

DB truth (402 closed since 06-01, −$50.82 net): the entire loss is trades that
never peaked past +5% margin; movers (peak ≥10%) were net positive. Entries were
the problem, exits never were. V5 keeps the ride-the-tail exit but moves to the
1h box so the trail is 5-6× tighter in price terms — a +30% peak exits ≈ +20%
instead of round-tripping red (V4 trades #4036-4039).

Signal: a 1h close beyond the prior 20-bar high/low box, taken ONLY in the
direction of the 4h regime (last closed 4h close vs the 4h Donchian-20 midline).
Fresh breaks only (one entry per breakout candle).

This module stays PURE READ: fetches candles, returns the current signal per
pair. The trader (`live_trader.py`) manages entries/exits (3×ATR(1h) chandelier).
"""

from __future__ import annotations

import asyncio
from typing import Any

from alpha.utils import setup_logger

logger = setup_logger("strategy_v5")

TIMEFRAME = "1h"
CANDLE_LIMIT = 60
CHANNEL_LEN = 20            # Donchian box length (backtested: N=20 on 1h)
TRAIL_ATR_MULT = 3.0        # published so the trader + docs share one number
HTF_TIMEFRAME = "4h"        # regime filter: trade only with the 4h box direction
HTF_CHANNEL_LEN = 20
HTF_CACHE_SEC = 900.0       # refresh the 4h regime every ~15 min per pair

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
    """Per-pair 1h Donchian breakout reader (4h-aligned). One instance per traded pair."""

    def __init__(self, pair: str, exchange: Any) -> None:
        self.pair = pair
        self.exchange = exchange
        self._last: dict[str, Any] | None = None
        self._last_signal_key: str | None = None   # one entry per breakout candle
        self._htf: tuple[float, int] | None = None  # (monotonic_ts, trend −1/0/+1)

    async def _fetch_rows(self) -> list[list[float]]:
        rows = await self.exchange.fetch_ohlcv(self.pair, TIMEFRAME, limit=CANDLE_LIMIT)
        return [[float(x) for x in row] for row in rows]

    async def _htf_trend(self) -> int | None:
        """4h regime: +1 above the 4h Donchian-20 midline, −1 below, 0 on it.

        Cached ~15 min so the 12s trader loop doesn't double the API load.
        On fetch failure the stale value is served regardless of age; if we have
        never fetched, return None → caller fails CLOSED (no entry without regime).
        """
        mono = asyncio.get_running_loop().time()
        if self._htf is not None and mono - self._htf[0] <= HTF_CACHE_SEC:
            return self._htf[1]
        try:
            raw = await self.exchange.fetch_ohlcv(
                self.pair, HTF_TIMEFRAME, limit=HTF_CHANNEL_LEN + 2
            )
            rows = [[float(x) for x in row] for row in raw]
        except Exception:
            logger.exception("4h regime fetch failed %s", self.pair)
            return self._htf[1] if self._htf is not None else None
        if len(rows) < HTF_CHANNEL_LEN + 2:
            return self._htf[1] if self._htf is not None else None
        closed = rows[:-1]                          # regime from CLOSED 4h candles
        box = closed[-(HTF_CHANNEL_LEN + 1):-1]     # 20 bars before the deciding one
        mid = (max(r[2] for r in box) + min(r[3] for r in box)) / 2.0
        close = closed[-1][4]
        trend = 1 if close > mid else (-1 if close < mid else 0)
        self._htf = (mono, trend)
        return trend

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
        # real 4h regime (cached ~15 min) — the backtested alignment gate
        htf_raw = await self._htf_trend()
        htf = htf_raw if htf_raw is not None else 0

        best: dict[str, Any] | None = None
        direction = None
        if close > upper:
            direction = "long"
        elif close < lower:
            direction = "short"
        # 4h alignment gate BEFORE the dedupe key: a filtered breakout must not
        # burn the one-entry-per-candle key (the regime can flip mid-candle).
        if direction == "long" and htf_raw != 1:
            direction = None
        elif direction == "short" and htf_raw != -1:
            direction = None
        if direction:
            key = f"{ts}:{direction}"
            if key != self._last_signal_key:
                self._last_signal_key = key
                bp = _pct_move(upper, close) if direction == "long" else abs(_pct_move(lower, close))
                conf = _clamp(90.0 + min(bp, 1.0) * 8.0, 90.0, 98.0)   # cosmetic, flat 10x anyway
                best = {
                    "pair": self.pair, "lane": "FUT_DONCHIAN_1H", "direction": direction,
                    "signal_key": key, "confidence": conf, "htf_trend": htf,
                    "atr": atr, "mark": mark,
                    "metadata": {
                        "lane": "FUT_DONCHIAN_1H", "timeframe": TIMEFRAME,
                        "channel_len": CHANNEL_LEN, "upper": upper, "lower": lower,
                        "channel_width_pct": width, "breakout_pct": bp,
                        "confidence_score": conf, "htf_trend_4h": htf,
                    },
                }

        # proximity scan for the dashboard: how close is price to breaking the box
        d_up = _pct_move(mark, upper)      # % move needed to break up
        d_dn = _pct_move(lower, mark)      # inverse gap down (positive when above lower)
        near_up = max(0.0, min(95.0, 95.0 * (1.0 - abs(d_up) / 1.2)))
        near_dn = max(0.0, min(95.0, 95.0 * (1.0 - abs(_pct_move(mark, lower)) / 1.2)))
        def fp(x: float) -> str:   # price with sane precision for sub-$1 assets
            return f"{x:,.0f}" if x >= 100 else (f"{x:.3f}" if x >= 1 else f"{x:.4f}")
        regime = "4h↑" if htf_raw == 1 else ("4h↓" if htf_raw == -1 else "4h·")
        if near_up >= near_dn:
            side, ready, watching, level = "LONG", near_up, f"break {fp(upper)} (1h box high · {regime})", upper
        else:
            side, ready, watching, level = "SHORT", near_dn, f"break {fp(lower)} (1h box low · {regime})", lower
        # a side the 4h regime blocks can never fire — show it as gated
        if (side == "LONG" and htf_raw != 1) or (side == "SHORT" and htf_raw != -1):
            watching += " — gated"
        if best:
            status = "READY"
        elif ready >= 78:
            status = "CLOSE"
        else:
            status = "SCANNING"
        lanes = [{
            "lane": "FUT_DONCHIAN_1H", "name": "Donchian 1h",
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

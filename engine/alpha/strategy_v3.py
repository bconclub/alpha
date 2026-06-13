"""V3 signal engine — the validated strategy brain, signals only.

Lifted from the paper lab (1,468 trades of evidence) with the paper-trade
simulation stripped out. Three lanes, each gated by a confidence floor and the
1h higher-timeframe trend:

  * FUT_EMA_PB    — EMA 8/21 trend + pullback-to-EMA8 + follow-through
  * FUT_DONCHIAN_RT — FRESH Donchian-20 breakout only (never chase an extended one)
  * FUT_VWAP      — institutional VWAP bounce with the trend

This module is PURE READ: it fetches live candles and returns the single best
current signal per pair. It never places orders and never writes the DB — the
autonomous trader (`live_trader.py`) polls `SignalEngine.latest_signal()` and
decides sizing/leverage/entry. The 1h gate is the lesson of the 06-10 massacre
(15 straight long stop-outs while the hourly trend was down).
"""

from __future__ import annotations

import asyncio
from typing import Any

from alpha.utils import setup_logger

logger = setup_logger("strategy_v3")

# Entry conviction floor — below this no lane trades. The autonomous trader maps
# everything ABOVE this to leverage tiers (85–91→10x, 92–96→25x, 97+→50x).
MIN_CONFIDENCE = 85.0

# Higher-timeframe gate (1h EMA 8/21 drift): longs need a 1h uptrend, shorts a
# 1h downtrend, a flat hour = stand down.
HTF_TIMEFRAME = "1h"
HTF_MIN_GAP_PCT = 0.05
HTF_CACHE_SEC = 300.0

TIMEFRAME = "5m"
CANDLE_LIMIT = 80


# ── pure indicator helpers (identical math to the validated paper lanes) ─────
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


# ── lane signals — return (direction, signal_key, metadata) or None ──────────
# `metadata` always carries confidence_score; the engine attaches atr/htf_trend.

def ema_pullback_signal(rows: list[list[float]]) -> tuple[str, str, dict[str, Any]] | None:
    """EMA 8/21 trend + pullback-to-EMA8 + follow-through, chop-filtered."""
    MIN_TREND_GAP_PCT = 0.06
    MIN_FOLLOW_PCT = 0.04
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
    if abs(gap) < MIN_TREND_GAP_PCT or ft < MIN_FOLLOW_PCT:
        return None
    meta = {
        "lane": "FUT_EMA_PB",
        "ema8": ema8, "ema21": ema21,
        "trend_gap_pct": gap, "follow_through_pct": ft,
        "confidence_score": _clamp(70.0 + abs(gap) * 60.0 + ft * 40.0, 70.0, 95.0),
    }
    if gap > 0 and close > ema21 and lows[-1] <= ema8 and close > prev:
        return "long", f"{ts}:long", meta
    if gap < 0 and close < ema21 and highs[-1] >= ema8 and close < prev:
        return "short", f"{ts}:short", meta
    return None


def donchian_retest_signal(rows: list[list[float]]) -> tuple[str, str, dict[str, Any]] | None:
    """FRESH Donchian-20 breakout only — the PREVIOUS bar must be inside."""
    CHANNEL_LEN = 20
    MAX_CHASE_PCT = 0.40
    MIN_WIDTH_PCT = 0.30
    if len(rows) < CHANNEL_LEN + 3:
        return None
    closed = rows[:-1]
    history = closed[-(CHANNEL_LEN + 1):-1]
    upper = max(float(r[2]) for r in history)
    lower = min(float(r[3]) for r in history)
    close = float(closed[-1][4])
    prev_close = float(closed[-2][4])
    ts = int(closed[-1][0])
    width = _pct_move(lower, upper) if lower > 0 else 0.0
    if width < MIN_WIDTH_PCT:
        return None
    meta = {
        "lane": "FUT_DONCHIAN_RT", "channel_len": CHANNEL_LEN,
        "upper": upper, "lower": lower, "channel_width_pct": width,
    }
    if close > upper and prev_close <= upper:
        bp = _pct_move(upper, close)
        if bp > MAX_CHASE_PCT:
            return None
        meta.update({"breakout_pct": bp, "confidence_score": _clamp(71.0 + width * 8.0 + bp * 20.0, 70.0, 92.0)})
        return "long", f"{ts}:long", meta
    if close < lower and prev_close >= lower:
        bp = abs(_pct_move(lower, close))
        if bp > MAX_CHASE_PCT:
            return None
        meta.update({"breakout_pct": bp, "confidence_score": _clamp(71.0 + width * 8.0 + bp * 20.0, 70.0, 92.0)})
        return "short", f"{ts}:short", meta
    return None


def vwap_bounce_signal(rows: list[list[float]]) -> tuple[str, str, dict[str, Any]] | None:
    """Institutional VWAP pullback: with the trend, enter the bounce off VWAP."""
    VWAP_BARS = 60
    TOUCH_PCT = 0.0008
    MAX_DIST_PCT = 0.35
    if len(rows) < VWAP_BARS + 2:
        return None
    closed = rows[:-1]
    closes = [float(r[4]) for r in closed]
    vwap = _vwap_rows(closed[-VWAP_BARS:])
    if vwap <= 0:
        return None
    ema8 = _ema(closes[-34:], 8)
    ema21 = _ema(closes[-55:], 21)
    close, prev = closes[-1], closes[-2]
    low, high = float(closed[-1][3]), float(closed[-1][2])
    ts = int(closed[-1][0])
    gap = _pct_move(ema21, ema8)
    dist = (close - vwap) / vwap * 100.0
    meta = {"lane": "FUT_VWAP", "vwap": vwap, "dist_pct": dist, "trend_gap_pct": gap}
    if gap > 0.05 and low <= vwap * (1 + TOUCH_PCT) and 0.0 < dist < MAX_DIST_PCT and close > prev:
        meta["confidence_score"] = _clamp(72.0 + gap * 50.0, 70.0, 92.0)
        return "long", f"{ts}:long", meta
    if gap < -0.05 and high >= vwap * (1 - TOUCH_PCT) and -MAX_DIST_PCT < dist < 0.0 and close < prev:
        meta["confidence_score"] = _clamp(72.0 + abs(gap) * 50.0, 70.0, 92.0)
        return "short", f"{ts}:short", meta
    return None


LANES = (ema_pullback_signal, donchian_retest_signal, vwap_bounce_signal)


class SignalEngine:
    """Per-pair live signal reader. One instance per traded pair."""

    def __init__(self, pair: str, exchange: Any) -> None:
        self.pair = pair
        self.exchange = exchange
        self._htf_cache: tuple[float, int] = (0.0, 0)   # (mono_ts, dir +1/-1/0)
        self._last: dict[str, Any] | None = None

    async def _fetch_rows(self) -> list[list[float]]:
        rows = await self.exchange.fetch_ohlcv(self.pair, TIMEFRAME, limit=CANDLE_LIMIT)
        return [[float(x) for x in row] for row in rows]

    async def _htf_trend(self) -> int:
        """Hourly EMA 8/21 drift: +1 up, -1 down, 0 flat/unknown. Cached 5 min."""
        loop = asyncio.get_running_loop()
        ts, cached = self._htf_cache
        if loop.time() - ts < HTF_CACHE_SEC:
            return cached
        d = cached
        try:
            raw = await self.exchange.fetch_ohlcv(self.pair, HTF_TIMEFRAME, limit=60)
            closes = [float(r[4]) for r in raw[:-1]]
            if len(closes) >= 25:
                gap = _pct_move(_ema(closes[-55:], 21), _ema(closes[-34:], 8))
                d = 1 if gap >= HTF_MIN_GAP_PCT else (-1 if gap <= -HTF_MIN_GAP_PCT else 0)
        except Exception:
            pass   # keep last known on a transient API failure
        self._htf_cache = (loop.time(), d)
        return d

    async def latest_signal(self) -> dict[str, Any] | None:
        """Best current entry across all lanes, or None.

        A signal must clear MIN_CONFIDENCE and be aligned with the 1h trend.
        Returns the highest-confidence survivor with atr + htf_trend attached.
        The result is also cached on `self._last` for status publishing.
        """
        try:
            rows = await self._fetch_rows()
        except Exception:
            logger.exception("signal fetch failed %s", self.pair)
            self._last = None
            return None
        if len(rows) < 60:
            self._last = None
            return None
        mark = float(rows[-1][4])
        atr = _atr_rows(rows[:-1])
        htf = await self._htf_trend()

        best: dict[str, Any] | None = None
        best_conf = -1.0
        for lane_fn in LANES:
            try:
                decision = lane_fn(rows)
            except Exception:
                continue
            if decision is None:
                continue
            direction, signal_key, meta = decision
            conf = float(meta.get("confidence_score") or 0.0)
            if conf < MIN_CONFIDENCE:
                continue
            # 1h trend gate: flat hour or wrong way = not our trade.
            if htf == 0 or (htf > 0) != (direction == "long"):
                continue
            if conf > best_conf:
                best_conf = conf
                best = {
                    "pair": self.pair,
                    "lane": meta.get("lane"),
                    "direction": direction,
                    "signal_key": signal_key,
                    "confidence": conf,
                    "htf_trend": htf,
                    "atr": atr,
                    "mark": mark,
                    "metadata": meta,
                }
        self._last = best or {
            "pair": self.pair, "lane": None, "direction": None,
            "confidence": 0.0, "htf_trend": htf, "atr": atr, "mark": mark,
        }
        return best

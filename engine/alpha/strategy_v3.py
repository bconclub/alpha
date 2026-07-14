"""V5.2 signal engine — 2h trend rider (Donchian breakout), signals only.

Why V5.2 (07-14) — and the bug that invalidated everything before it:
every backtest from 07-10 to 07-14 resampled candles from the array start
instead of true UTC boundaries. Offset bars created breakouts that never
existed on real exchange candles — which is why V5 backtested +$6.50 and then
bled live (live trades REAL aligned candles). With the sim corrected
(UTC-aligned bars, warmup excluded, walk-forward: tuned Jan10-May14, validated
blind May15-Jul14, 141 configs):

    old V5 (1h box + 4h gate), honest:   IS  −$4.02   OOS −$4.83   ← the bleed, explained
    1d gate / tight-box variants:        IS negative or OOS-flipped
    2h Donchian-20 + 2.5×ATR trail:      IS +$25.43   OOS +$3.03   ← only config green in BOTH
    ... without BTC (a drag both windows): IS +$30.05  OOS +$3.83

Monthly truth for this config (fees + our sizing, all 5 pairs): Jan +21.6,
Feb +27.8, Mar +0.6, Apr −18.3, May −5.4, Jun +2.6, Jul −0.4. It is a trend
follower: it banks trending months, treads water in chop. It is NOT a chop
money-printer; nothing tested is. Expectations set accordingly.

Signal: a 2h close beyond the prior 20-bar (≈1.7-day) high/low box. Long above,
short below. Fresh breaks only (one entry per breakout candle). No HTF gate, no
box-width gate — both failed honest out-of-sample validation.

This module stays PURE READ: fetches candles, returns the current signal per
pair. The trader (`live_trader.py`) manages entries/exits (2.5×ATR(2h)
chandelier, ratchet-only).
"""

from __future__ import annotations

from typing import Any

from alpha.utils import setup_logger

logger = setup_logger("strategy_v5")

TIMEFRAME = "2h"
CANDLE_LIMIT = 60
CHANNEL_LEN = 20            # Donchian box length (walk-forward: N=20 on 2h)
TRAIL_ATR_MULT = 2.5        # published so the trader + docs share one number

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
    """Per-pair 2h Donchian breakout reader. One instance per traded pair."""

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
        closed = rows[:-1]                      # decide on CLOSED 2h candles only
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
                    "pair": self.pair, "lane": "FUT_DONCHIAN_2H", "direction": direction,
                    "signal_key": key, "confidence": conf, "htf_trend": htf,
                    "atr": atr, "mark": mark,
                    "metadata": {
                        "lane": "FUT_DONCHIAN_2H", "timeframe": TIMEFRAME,
                        "channel_len": CHANNEL_LEN, "upper": upper, "lower": lower,
                        "channel_width_pct": width, "breakout_pct": bp,
                        "confidence_score": conf,
                    },
                }

        # proximity scan for the dashboard: how close is price to breaking the box
        d_up = _pct_move(mark, upper)      # % move needed to break up
        near_up = max(0.0, min(95.0, 95.0 * (1.0 - abs(d_up) / 1.2)))
        near_dn = max(0.0, min(95.0, 95.0 * (1.0 - abs(_pct_move(mark, lower)) / 1.2)))
        def fp(x: float) -> str:   # price with sane precision for sub-$1 assets
            return f"{x:,.0f}" if x >= 100 else (f"{x:.3f}" if x >= 1 else f"{x:.4f}")
        # ASCII only: this text round-trips through the DB/dashboard pipeline,
        # which mangles multibyte chars (mojibake seen live on 07-10).
        if near_up >= near_dn:
            side, ready, watching, level = "LONG", near_up, f"break {fp(upper)} (2h box high)", upper
        else:
            side, ready, watching, level = "SHORT", near_dn, f"break {fp(lower)} (2h box low)", lower
        if best:
            status = "READY"
        elif ready >= 78:
            status = "CLOSE"
        else:
            status = "SCANNING"
        lanes = [{
            "lane": "FUT_DONCHIAN_2H", "name": "Donchian 2h",
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

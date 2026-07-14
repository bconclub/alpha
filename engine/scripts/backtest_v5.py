#!/usr/bin/env python3
"""Backtest the V5.2 trend rider on real Delta public candles. No DB, no keys.

CRITICAL LESSON (07-14): every backtest before this date resampled sim bars
from the fetched-array start instead of true UTC boundaries. Offset bars
manufactured breakouts that never existed on real exchange candles — V5
backtested +$6.50 and bled live. This harness aligns every bar to UTC epoch
boundaries (ts // bar_seconds), drops partial edge bars, and fetches extra
warmup history so indicator warmup never eats the evaluation window.
If you change the sim, verify it still reproduces live fills before trusting it.

Simulates what the live engine runs: 2h Donchian-20 breakout entries (both
directions, no HTF gate — gates failed honest out-of-sample validation),
initial stop 2.5×ATR(2h), 2.5×ATR(2h) chandelier trail from peak (ratchet-only,
ATR refreshed per closed 2h bar), 72h max hold, taker fees both sides.
Entries fill at the open of the next 5m bar; stops are checked intrabar on
5m highs/lows (worst case: stop before target).

Usage (anywhere with internet, from repo root):
    python3 engine/scripts/backtest_v5.py                    # 30d, live pairs, $3 @ 10x
    python3 engine/scripts/backtest_v5.py --days 185 --split 60
    python3 engine/scripts/backtest_v5.py --gate 1d          # ablation: add a daily gate
    python3 engine/scripts/backtest_v5.py --pairs BTC,ETH --tf 1h --trail 3.0

Walk-forward numbers that picked V5.2 (07-14, UTC-aligned, IS Jan10-May14 /
blind OOS May15-Jul14): IS +$25.43, OOS +$3.03 (only both-window-green config
of 141); without BTC IS +$30.05 / OOS +$3.83. Monthly: Jan +21.6 Feb +27.8
Mar +0.6 Apr −18.3 May −5.4 Jun +2.6 Jul −0.4 — banks trends, treads chop.
Tune HERE, not on the account, and always hold out unseen data.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from alpha.strategy_v3 import CHANNEL_LEN, TIMEFRAME, TRAIL_ATR_MULT  # noqa: E402

API = "https://api.india.delta.exchange/v2/history/candles"
FEE = 0.0005            # Delta taker, per side
STOP_ATR_MULT = 2.5     # must mirror live_trader.STOP_ATR_MULT
MAX_HOLD_MIN = 72 * 60  # must mirror live_trader.MAX_HOLD_SEC
TF_SEC = {"1h": 3600, "2h": 7200, "4h": 14400, "1d": 86400}
WARMUP_DAYS = 5         # extra history so Donchian/ATR warmup precedes the window
GATE_WARMUP_DAYS = 25   # a 1d-gate needs ~21 daily closed bars before day one


def fetch_5m(symbol: str, days: int) -> list[dict]:
    """Paginated public 5m candles, oldest→newest."""
    end = int(time.time())
    cur = end - days * 86400
    step = 1900 * 300
    seen: dict[int, dict] = {}
    while cur < end:
        e = min(cur + step, end)
        url = f"{API}?resolution=5m&symbol={symbol}&start={cur}&end={e}"
        req = urllib.request.Request(url, headers={"User-Agent": "alpha-backtest"})
        for row in json.load(urllib.request.urlopen(req, timeout=30))["result"]:
            seen[row["time"]] = row
        cur = e
        time.sleep(0.15)
    return sorted(seen.values(), key=lambda r: r["time"])


def resample_utc(rows: list[dict], sec: int) -> list[dict]:
    """UTC-aligned bars (ts // sec buckets), complete bars only.

    i5 = index of the first 5m row AFTER the bar close — where a live entry
    on that bar's close would fill.
    """
    groups: dict[int, dict] = {}
    for i, r in enumerate(rows):
        b = int(r["time"]) // sec
        g = groups.setdefault(b, {"t": b * sec, "h": -1e18, "l": 1e18, "c": 0.0,
                                  "i5": i + 1, "n": 0})
        g["h"] = max(g["h"], float(r["high"]))
        g["l"] = min(g["l"], float(r["low"]))
        g["c"] = float(r["close"])
        g["i5"] = i + 1
        g["n"] += 1
    return [g for _, g in sorted(groups.items()) if g["n"] == sec // 300]


def atr(bars: list[dict], j: int, period: int = 14) -> float:
    trs = [
        max(bars[k]["h"] - bars[k]["l"],
            abs(bars[k]["h"] - bars[k - 1]["c"]),
            abs(bars[k]["l"] - bars[k - 1]["c"]))
        for k in range(j - period, j)
    ]
    return sum(trs) / period


def entries(rows5: list[dict], tf_sec: int, gate: str) -> list[tuple[int, str, float, int, int]]:
    """(i5_entry, direction, entry_atr, bar_ts, bar_index) per fresh breakout."""
    bars = resample_utc(rows5, tf_sec)
    gt = resample_utc(rows5, TF_SEC["1d"]) if gate == "1d" else None
    out = []
    for j in range(max(CHANNEL_LEN, 15) + 1, len(bars)):
        hh = max(b["h"] for b in bars[j - CHANNEL_LEN:j])
        ll = min(b["l"] for b in bars[j - CHANNEL_LEN:j])
        c = bars[j]["c"]
        a = atr(bars, j)
        if a <= 0:
            continue
        d = "long" if c > hh else ("short" if c < ll else None)
        if not d:
            continue
        if gt is not None:
            close_ts = bars[j]["t"] + tf_sec
            k = min(close_ts // 86400 - gt[0]["t"] // 86400 - 1, len(gt) - 1)
            if k < CHANNEL_LEN + 1:
                continue
            mid = (max(b["h"] for b in gt[k - CHANNEL_LEN:k])
                   + min(b["l"] for b in gt[k - CHANNEL_LEN:k])) / 2
            if d == "long" and gt[k]["c"] <= mid:
                continue
            if d == "short" and gt[k]["c"] >= mid:
                continue
        out.append((bars[j]["i5"], d, a, bars[j]["t"], j))
    return out


def simulate(rows5: list[dict], ents: list, tf_sec: int, trail_mult: float,
             margin: float, lev: float, eval_from_ts: int) -> list[dict]:
    bars = resample_utc(rows5, tf_sec)
    trades = []
    busy_until = 0
    for (i0, d, a0, bts, j0) in ents:
        if bts < eval_from_ts:          # warmup period: observe, never trade
            continue
        if i0 < busy_until or i0 >= len(rows5):
            continue
        e = float(rows5[i0]["open"])
        a = a0
        stop = e - STOP_ATR_MULT * a if d == "long" else e + STOP_ATR_MULT * a
        peak = e
        peak_pct = 0.0
        exit_px = None
        j = i0
        jj = j0
        while j < len(rows5):
            r = rows5[j]
            hi, lo = float(r["high"]), float(r["low"])
            peak = max(peak, hi) if d == "long" else min(peak, lo)
            peak_pct = max(peak_pct, (peak / e - 1) * 100 * lev * (1 if d == "long" else -1))
            if d == "long" and lo <= stop:
                exit_px = stop
                break
            if d == "short" and hi >= stop:
                exit_px = stop
                break
            if (j - i0) * 5 >= MAX_HOLD_MIN:
                exit_px = float(r["close"])
                break
            # refresh ATR each completed signal-TF bar (live: 15-min cached fetch)
            while jj + 1 < len(bars) and bars[jj + 1]["i5"] <= j:
                jj += 1
            if jj > 15:
                a = atr(bars, jj)
            tr = peak - trail_mult * a if d == "long" else peak + trail_mult * a
            stop = max(stop, tr) if d == "long" else min(stop, tr)
            j += 1
        if exit_px is None:
            exit_px = float(rows5[-1]["close"])
        gross = (exit_px / e - 1) * (1 if d == "long" else -1) * lev * margin
        fees = (e + exit_px) / e * FEE * lev * margin
        trades.append({"pnl": gross - fees, "peak": peak_pct,
                       "hold_min": (j - i0) * 5, "ts": bts})
        busy_until = j
    return trades


def _table(rows: list[tuple[str, list[dict]]], days: int, label: str) -> None:
    total: list[dict] = []
    print(f"[{label}]")
    print(f"{'pair':10s} {'n':>4s} {'net$':>8s} {'wr%':>4s} {'avgW':>7s} {'avgL':>7s} {'medHold_h':>9s}")
    for base, t in rows:
        total += t
        if not t:
            print(f"{base:10s} {0:4d}")
            continue
        pnl = [x["pnl"] for x in t]
        w = [x for x in pnl if x > 0]
        losses = [x for x in pnl if x <= 0]
        print(f"{base:10s} {len(t):4d} {sum(pnl):+8.2f} {len(w) / len(t) * 100:4.0f} "
              f"{statistics.mean(w) if w else 0:+7.3f} {statistics.mean(losses) if losses else 0:+7.3f} "
              f"{statistics.median(x['hold_min'] for x in t) / 60:9.1f}")
    if total:
        pnl = [x["pnl"] for x in total]
        w = [x for x in pnl if x > 0]
        eq = pk = dd = 0.0
        for x in pnl:
            eq += x
            pk = max(pk, eq)
            dd = min(dd, eq - pk)
        by_mo: dict[str, float] = {}
        for x in total:
            m = datetime.fromtimestamp(x["ts"], tz=timezone.utc).strftime("%m")
            by_mo[m] = by_mo.get(m, 0.0) + x["pnl"]
        print("-" * 60)
        print(f"{'TOTAL':10s} {len(total):4d} {sum(pnl):+8.2f} {len(w) / len(total) * 100:4.0f}   "
              f"maxDD={dd:+.2f}  trades/day={len(total) / days:.1f}")
        print("monthly: " + "  ".join(f"{m}:{v:+.1f}" for m, v in sorted(by_mo.items())))


def main() -> None:
    ap = argparse.ArgumentParser(description="V5.2 trend-rider backtest (Delta public candles)")
    ap.add_argument("--days", type=int, default=30, help="evaluation window (warmup fetched on top)")
    ap.add_argument("--pairs", default="ETH,SOL,XRP,DOGE", help="live trade set; add BTC for ablation")
    ap.add_argument("--margin", type=float, default=3.0)
    ap.add_argument("--lev", type=float, default=10.0)
    ap.add_argument("--tf", default=TIMEFRAME, choices=list(TF_SEC), help="signal timeframe")
    ap.add_argument("--trail", type=float, default=TRAIL_ATR_MULT)
    ap.add_argument("--gate", choices=["none", "1d"], default="none",
                    help="HTF alignment gate (live runs none; 1d for ablation)")
    ap.add_argument("--split", type=int, default=0,
                    help="if >0, also report the last N days separately (walk-forward OOS view)")
    args = ap.parse_args()

    tf_sec = TF_SEC[args.tf]
    warm = GATE_WARMUP_DAYS if args.gate == "1d" else max(
        WARMUP_DAYS, (CHANNEL_LEN + 16) * tf_sec // 86400 + 1)
    eval_from = int(time.time()) - args.days * 86400
    split_ts = int(time.time()) - args.split * 86400 if args.split else None

    per_pair: list[tuple[str, list[dict]]] = []
    for base in [p.strip().upper() for p in args.pairs.split(",") if p.strip()]:
        rows = fetch_5m(f"{base}USD", args.days + warm)
        ents = entries(rows, tf_sec, args.gate)
        per_pair.append((base, simulate(rows, ents, tf_sec, args.trail,
                                        args.margin, args.lev, eval_from)))

    if split_ts:
        _table([(b, [x for x in t if x["ts"] < split_ts]) for b, t in per_pair],
               args.days - args.split, f"first {args.days - args.split}d (IS)")
        print()
        _table([(b, [x for x in t if x["ts"] >= split_ts]) for b, t in per_pair],
               args.split, f"last {args.split}d (OOS)")
    else:
        _table(per_pair, args.days, f"{args.days}d")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Backtest the V5 trend rider on real Delta public candles. No DB, no keys.

Simulates exactly what the live engine runs: 1h Donchian-20 breakout entries
gated by the 4h regime (last closed 4h close vs the 4h Donchian-20 midline),
initial stop 3×ATR(1h), 3×ATR(1h) chandelier trail from peak (ratchet-only,
ATR refreshed per closed 1h bar), 72h max hold, taker fees both sides.
Entries fill at the open of the next 5m bar; stops are checked intrabar on
5m highs/lows (worst case: stop before target).

Usage (anywhere with internet, from repo root):
    python3 engine/scripts/backtest_v5.py                    # 30d, 5 pairs, $3 @ 10x
    python3 engine/scripts/backtest_v5.py --days 60
    python3 engine/scripts/backtest_v5.py --pairs SOL,XRP --margin 4
    python3 engine/scripts/backtest_v5.py --no-htf-gate      # ablate the 4h filter

This is the harness that picked V5 (07-10): +$6.50/30d vs V4's +$0.16, with
every harvest/time-stop variant negative. Keep it green before touching live
constants — tune HERE, not on the account.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from alpha.strategy_v3 import CHANNEL_LEN, HTF_CHANNEL_LEN, TRAIL_ATR_MULT  # noqa: E402

API = "https://api.india.delta.exchange/v2/history/candles"
FEE = 0.0005            # Delta taker, per side
STOP_ATR_MULT = 3.0     # must mirror live_trader.STOP_ATR_MULT
MAX_HOLD_MIN = 72 * 60  # must mirror live_trader.MAX_HOLD_SEC


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


def resample(rows: list[dict], n: int) -> list[dict]:
    """n 5m bars → one bar. i5 = index of the first 5m bar AFTER the close."""
    out = []
    for k in range(0, len(rows) - n + 1, n):
        ch = rows[k:k + n]
        out.append({
            "o": float(ch[0]["open"]),
            "h": max(float(x["high"]) for x in ch),
            "l": min(float(x["low"]) for x in ch),
            "c": float(ch[-1]["close"]),
            "i5": k + n,
        })
    return out


def atr(bars: list[dict], j: int, period: int = 14) -> float:
    trs = [
        max(bars[k]["h"] - bars[k]["l"],
            abs(bars[k]["h"] - bars[k - 1]["c"]),
            abs(bars[k]["l"] - bars[k - 1]["c"]))
        for k in range(j - period, j)
    ]
    return sum(trs) / period


def entries(rows5: list[dict], htf_gate: bool) -> list[tuple[int, str, int]]:
    """(i5_entry, direction, 1h_bar_index) for each fresh gated 1h breakout."""
    h1 = resample(rows5, 12)
    h4 = resample(rows5, 48)
    out = []
    for j in range(max(CHANNEL_LEN, 15) + 1, len(h1)):
        hh = max(b["h"] for b in h1[j - CHANNEL_LEN:j])
        ll = min(b["l"] for b in h1[j - CHANNEL_LEN:j])
        c = h1[j]["c"]
        d = "long" if c > hh else ("short" if c < ll else None)
        if not d:
            continue
        if htf_gate:
            k = min((h1[j]["i5"] - 1) // 48, len(h4) - 1)
            if k < HTF_CHANNEL_LEN:
                continue
            mid = (max(b["h"] for b in h4[k - HTF_CHANNEL_LEN:k])
                   + min(b["l"] for b in h4[k - HTF_CHANNEL_LEN:k])) / 2
            if d == "long" and h4[k]["c"] <= mid:
                continue
            if d == "short" and h4[k]["c"] >= mid:
                continue
        out.append((h1[j]["i5"], d, j))
    return out


def simulate(rows5: list[dict], ents: list[tuple[int, str, int]],
             margin: float, lev: float) -> list[dict]:
    h1 = resample(rows5, 12)
    trades = []
    busy_until = 0
    for (i0, d, j0) in ents:
        if i0 < busy_until or i0 >= len(rows5):
            continue
        e = float(rows5[i0]["open"])
        a = atr(h1, j0)
        if a <= 0:
            continue
        stop = e - STOP_ATR_MULT * a if d == "long" else e + STOP_ATR_MULT * a
        peak = e
        peak_pct = 0.0
        exit_px = None
        j = i0
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
            # refresh ATR each completed 1h bar (live: 15-min cached 1h fetch)
            jj = min(j // 12, len(h1) - 1)
            if jj > 15:
                a = atr(h1, jj)
            tr = peak - TRAIL_ATR_MULT * a if d == "long" else peak + TRAIL_ATR_MULT * a
            stop = max(stop, tr) if d == "long" else min(stop, tr)
            j += 1
        if exit_px is None:
            exit_px = float(rows5[-1]["close"])
        gross = (exit_px / e - 1) * (1 if d == "long" else -1) * lev * margin
        fees = (e + exit_px) / e * FEE * lev * margin
        trades.append({"pnl": gross - fees, "peak": peak_pct, "hold_min": (j - i0) * 5})
        busy_until = j
    return trades


def main() -> None:
    ap = argparse.ArgumentParser(description="V5 trend-rider backtest (Delta public candles)")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--pairs", default="BTC,ETH,SOL,XRP,DOGE")
    ap.add_argument("--margin", type=float, default=3.0)
    ap.add_argument("--lev", type=float, default=10.0)
    ap.add_argument("--no-htf-gate", action="store_true", help="ablate the 4h alignment filter")
    args = ap.parse_args()

    total: list[dict] = []
    print(f"{'pair':10s} {'n':>4s} {'net$':>8s} {'wr%':>4s} {'avgW':>7s} {'avgL':>7s} {'medHold_h':>9s}")
    for base in [p.strip().upper() for p in args.pairs.split(",") if p.strip()]:
        sym = f"{base}USD"
        rows = fetch_5m(sym, args.days)
        t = simulate(rows, entries(rows, not args.no_htf_gate), args.margin, args.lev)
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
        print("-" * 60)
        print(f"{'TOTAL':10s} {len(total):4d} {sum(pnl):+8.2f} {len(w) / len(total) * 100:4.0f}   "
              f"maxDD={dd:+.2f}  trades/day={len(total) / args.days:.1f}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Review yesterday + today trades, grouped by setup_type.

Surfaces trail-issue signals: peak vs. final P&L gap, exit reason distribution,
win rate per setup, and a raw per-trade table you can eyeball.

Usage (on the VPS, from the repo root):
    python3 engine/scripts/trade_review.py                  # yesterday + today UTC
    python3 engine/scripts/trade_review.py --days 3         # last 3 calendar days
    python3 engine/scripts/trade_review.py --tz ist         # treat "today" as IST
    python3 engine/scripts/trade_review.py --strategy options_scalp
    python3 engine/scripts/trade_review.py --open-only      # only currently open
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(".env")

IST = timezone(timedelta(hours=5, minutes=30))

# ANSI colors; degrade gracefully if terminal doesn't support
def c(code: str, s: Any) -> str:
    if not sys.stdout.isatty():
        return str(s)
    return f"\033[{code}m{s}\033[0m"


def red(s: Any) -> str: return c("31", s)
def green(s: Any) -> str: return c("32", s)
def yellow(s: Any) -> str: return c("33", s)
def cyan(s: Any) -> str: return c("36", s)
def bold(s: Any) -> str: return c("1", s)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--days", type=int, default=2, help="Number of calendar days back (default 2 = yesterday+today)")
    p.add_argument("--tz", choices=["utc", "ist"], default="utc", help="Timezone for day-boundary math")
    p.add_argument("--strategy", default=None, help="Filter by strategy (e.g. options_scalp, scalp)")
    p.add_argument("--exchange", default=None, help="Filter by exchange (e.g. delta, bybit)")
    p.add_argument("--open-only", action="store_true", help="Only show currently-open trades")
    p.add_argument("--no-table", action="store_true", help="Skip the per-trade table")
    return p.parse_args()


def fetch_trades(args: argparse.Namespace) -> list[dict]:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("ERROR: SUPABASE_URL / SUPABASE_KEY missing", file=sys.stderr)
        sys.exit(1)
    sb = create_client(url, key)

    tz = IST if args.tz == "ist" else timezone.utc
    now_local = datetime.now(tz)
    day_start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    window_start_local = day_start_local - timedelta(days=args.days - 1)
    window_start_utc = window_start_local.astimezone(timezone.utc)

    q = (
        sb.table("trades")
        .select("*")
        .gte("opened_at", window_start_utc.isoformat())
        .order("opened_at", desc=False)
    )
    if args.strategy:
        q = q.eq("strategy", args.strategy)
    if args.exchange:
        q = q.eq("exchange", args.exchange)
    if args.open_only:
        q = q.eq("status", "open")

    rows = q.execute().data or []
    print(
        f"Window: {window_start_utc.isoformat()} UTC → now "
        f"({args.days} day(s), tz={args.tz}) | rows={len(rows)}"
    )
    return rows


def fmt_pct(v: float | None) -> str:
    if v is None:
        return "  —   "
    s = f"{v:+6.2f}%"
    return green(s) if v > 0 else (red(s) if v < 0 else s)


def fmt_pnl(v: float | None) -> str:
    if v is None:
        return "   —  "
    s = f"${v:+7.4f}"
    return green(s) if v > 0 else (red(s) if v < 0 else s)


def hold_str(sec: float | None) -> str:
    if not sec or sec <= 0:
        return "    —"
    if sec < 60:
        return f"{sec:>4.0f}s"
    if sec < 3600:
        return f"{sec/60:>4.1f}m"
    return f"{sec/3600:>4.1f}h"


def compute_hold_seconds(row: dict) -> float | None:
    hs = row.get("hold_time_seconds")
    if hs:
        return float(hs)
    try:
        o = datetime.fromisoformat((row.get("opened_at") or "").replace("Z", "+00:00"))
        c = datetime.fromisoformat((row.get("closed_at") or "").replace("Z", "+00:00"))
        return (c - o).total_seconds()
    except Exception:
        return None


def print_per_setup_summary(rows: list[dict]) -> None:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[r.get("setup_type") or "NULL"].append(r)

    print()
    print(bold("=" * 110))
    print(bold("PER-SETUP SUMMARY"))
    print(bold("=" * 110))
    header = (
        f"{'setup_type':<26} {'n':>4} {'open':>4} {'closed':>6} "
        f"{'wins':>4} {'losses':>6} {'win%':>6} "
        f"{'net_pnl':>10} {'avg_pnl%':>9} {'avg_peak%':>10} {'avg_surrender':>14} {'avg_hold':>9}"
    )
    print(header)
    print("-" * len(header))

    totals = {"n": 0, "open": 0, "closed": 0, "wins": 0, "losses": 0, "net": 0.0}
    for setup, group in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        n = len(group)
        open_n = sum(1 for r in group if r.get("status") == "open")
        closed = [r for r in group if r.get("status") == "closed"]
        wins = sum(1 for r in closed if (r.get("pnl") or 0) > 0)
        losses = sum(1 for r in closed if (r.get("pnl") or 0) < 0)
        net = sum((r.get("pnl") or 0) for r in closed)
        win_rate = (wins / len(closed) * 100) if closed else 0
        pcts = [r.get("pnl_pct") for r in closed if r.get("pnl_pct") is not None]
        avg_pct = sum(pcts) / len(pcts) if pcts else 0
        peaks = [r.get("peak_pnl") for r in closed if r.get("peak_pnl") is not None]
        avg_peak = sum(peaks) / len(peaks) if peaks else 0
        surrenders = [
            (r.get("peak_pnl") or 0) - (r.get("pnl_pct") or 0)
            for r in closed
            if r.get("peak_pnl") is not None and r.get("pnl_pct") is not None
        ]
        avg_surr = sum(surrenders) / len(surrenders) if surrenders else 0
        holds = [h for h in (compute_hold_seconds(r) for r in closed) if h]
        avg_hold = sum(holds) / len(holds) if holds else 0

        totals["n"] += n
        totals["open"] += open_n
        totals["closed"] += len(closed)
        totals["wins"] += wins
        totals["losses"] += losses
        totals["net"] += net

        print(
            f"{setup:<26} {n:>4} {open_n:>4} {len(closed):>6} "
            f"{wins:>4} {losses:>6} {win_rate:>5.1f}% "
            f"{fmt_pnl(net):>10} {fmt_pct(avg_pct):>9} {fmt_pct(avg_peak):>10} "
            f"{fmt_pct(avg_surr):>14} {hold_str(avg_hold):>9}"
        )

    print("-" * len(header))
    wr = (totals["wins"] / totals["closed"] * 100) if totals["closed"] else 0
    print(
        f"{'TOTAL':<26} {totals['n']:>4} {totals['open']:>4} {totals['closed']:>6} "
        f"{totals['wins']:>4} {totals['losses']:>6} {wr:>5.1f}% "
        f"{fmt_pnl(totals['net']):>10}"
    )


def print_exit_reason_breakdown(rows: list[dict]) -> None:
    closed = [r for r in rows if r.get("status") == "closed"]
    if not closed:
        return
    by_reason: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in closed:
        key = (r.get("setup_type") or "NULL", (r.get("exit_reason") or "—")[:28])
        by_reason[key].append(r)

    print()
    print(bold("=" * 110))
    print(bold("EXIT REASON BREAKDOWN (setup_type × exit_reason)"))
    print(bold("=" * 110))
    print(f"{'setup_type':<26} {'exit_reason':<30} {'n':>4} {'wins':>5} {'net':>10} {'avg_pnl%':>10} {'avg_peak%':>10}")
    print("-" * 105)
    for (setup, reason), group in sorted(by_reason.items(), key=lambda kv: (kv[0][0], -len(kv[1]))):
        n = len(group)
        wins = sum(1 for r in group if (r.get("pnl") or 0) > 0)
        net = sum((r.get("pnl") or 0) for r in group)
        pcts = [r.get("pnl_pct") for r in group if r.get("pnl_pct") is not None]
        avg_pct = sum(pcts) / len(pcts) if pcts else 0
        peaks = [r.get("peak_pnl") for r in group if r.get("peak_pnl") is not None]
        avg_peak = sum(peaks) / len(peaks) if peaks else 0
        print(
            f"{setup:<26} {reason:<30} {n:>4} {wins:>5} "
            f"{fmt_pnl(net):>10} {fmt_pct(avg_pct):>10} {fmt_pct(avg_peak):>10}"
        )


def print_trail_issues(rows: list[dict]) -> None:
    """Flag trades where peak was >=10% but final was <=0% — trail failed to lock."""
    closed = [r for r in rows if r.get("status") == "closed"]
    suspects = [
        r for r in closed
        if (r.get("peak_pnl") or 0) >= 10 and (r.get("pnl_pct") or 0) <= 0
    ]
    if not suspects:
        return
    print()
    print(bold("=" * 110))
    print(bold(yellow("TRAIL-ISSUE SUSPECTS  (peak ≥ +10% but final ≤ 0%)")))
    print(bold("=" * 110))
    print(f"{'id':>6} {'pair':<30} {'setup':<22} {'peak%':>8} {'final%':>8} {'surrender':>10} {'exit_reason':<22}")
    print("-" * 110)
    for r in sorted(suspects, key=lambda r: -(r.get("peak_pnl") or 0)):
        peak = r.get("peak_pnl") or 0
        final = r.get("pnl_pct") or 0
        surrender = peak - final
        print(
            f"{r.get('id'):>6} {(r.get('pair') or '')[:30]:<30} "
            f"{(r.get('setup_type') or 'NULL')[:22]:<22} "
            f"{peak:>7.2f}% {final:>+7.2f}% {surrender:>9.2f}% "
            f"{(r.get('exit_reason') or '—')[:22]:<22}"
        )


def print_trade_table(rows: list[dict]) -> None:
    print()
    print(bold("=" * 140))
    print(bold("PER-TRADE DETAIL (chronological)"))
    print(bold("=" * 140))
    header = (
        f"{'id':>5} {'opened (UTC)':<19} {'pair':<30} {'str':<4} "
        f"{'setup':<22} {'entry':>9} {'exit':>9} {'peak%':>7} {'pnl%':>7} "
        f"{'pnl$':>9} {'hold':>6} {'status':<6} {'exit_reason':<22}"
    )
    print(header)
    print("-" * len(header))
    for r in rows:
        opened = (r.get("opened_at") or "")[:19].replace("T", " ")
        entry = r.get("entry_price") or 0
        exitp = r.get("exit_price") or 0
        peak = r.get("peak_pnl")
        pnlp = r.get("pnl_pct")
        pnld = r.get("pnl")
        hold = compute_hold_seconds(r)
        strat = (r.get("strategy") or "")[:4]
        setup = (r.get("setup_type") or "NULL")[:22]
        status = (r.get("status") or "")[:6]
        exit_r = (r.get("exit_reason") or "—")[:22]
        pair = (r.get("pair") or "")[:30]

        print(
            f"{r.get('id'):>5} {opened:<19} {pair:<30} {strat:<4} "
            f"{setup:<22} {entry:>9.4f} {exitp:>9.4f} "
            f"{(f'{peak:+6.2f}%' if peak is not None else '    —'):>7} "
            f"{fmt_pct(pnlp):>7} {fmt_pnl(pnld):>9} "
            f"{hold_str(hold):>6} {status:<6} {exit_r:<22}"
        )


def main() -> int:
    args = parse_args()
    rows = fetch_trades(args)
    if not rows:
        print("No trades in window.")
        return 0

    print_per_setup_summary(rows)
    print_exit_reason_breakdown(rows)
    print_trail_issues(rows)
    if not args.no_table:
        print_trade_table(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())

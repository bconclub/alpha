#!/usr/bin/env python3
"""Backfill NULL / empty setup_type on existing trades rows.

Infers the historical setup_type from the row's strategy + reason fields so
that legacy/reconciled trades aren't rendered as blank on the dashboard.

Usage:
    python3 engine/scripts/backfill_setup_type.py                 # dry run
    python3 engine/scripts/backfill_setup_type.py --apply         # write
    python3 engine/scripts/backfill_setup_type.py --inspect 3881  # dump a row
    python3 engine/scripts/backfill_setup_type.py --inspect 3881,2999,2992
"""
from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

# Match engine/alpha/config.py: load engine/.env first, then any nearby .env
_engine_env = Path(__file__).resolve().parent.parent / ".env"
if _engine_env.exists():
    load_dotenv(_engine_env)
load_dotenv(".env")  # also pick up cwd .env if present

APPLY = "--apply" in sys.argv

INSPECT_IDS: list[int] = []
if "--inspect" in sys.argv:
    i = sys.argv.index("--inspect")
    if i + 1 >= len(sys.argv):
        print("ERROR: --inspect requires an id (or comma-separated ids)", file=sys.stderr)
        sys.exit(2)
    try:
        INSPECT_IDS = [int(x) for x in sys.argv[i + 1].split(",") if x.strip()]
    except ValueError:
        print("ERROR: --inspect ids must be integers", file=sys.stderr)
        sys.exit(2)

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
if not url or not key:
    print(
        f"ERROR: SUPABASE_URL / SUPABASE_KEY missing from env\n"
        f"  Looked in: {_engine_env} and ./.env",
        file=sys.stderr,
    )
    sys.exit(1)

sb = create_client(url, key)


def infer(row: dict) -> str:
    """Map each row to one of the two real setup labels the dashboard renders.

    Only BB_SQUEEZE and MOMENTUM_BURST_ENTRY are valid — the dashboard ignores
    anything else. For reconciled/legacy rows where the original setup wasn't
    logged, we default to BB_SQUEEZE (the primary setup) and upgrade to
    MOMENTUM_BURST_ENTRY only if reason/signals_fired explicitly say so.
    """
    reason = (row.get("reason") or "").lower()
    exit_reason = (row.get("exit_reason") or "").lower()
    signals = (row.get("signals_fired") or "").lower()
    haystack = f"{reason} {exit_reason} {signals}"

    if "momentum_burst" in haystack or "mom_burst" in haystack or "momentum burst" in haystack:
        return "MOMENTUM_BURST_ENTRY"
    if "bb_squeeze" in haystack or "squeeze" in haystack:
        return "BB_SQUEEZE"
    # No hint available — default to primary setup.
    return "BB_SQUEEZE"


SELECT_COLS = "id,strategy,reason,exit_reason,signals_fired,pair,status,opened_at,setup_type"


def fetch_missing_rows() -> list[dict]:
    """Pull every trade where setup_type is NULL OR empty string. Paginates."""
    rows: list[dict] = []
    page = 0
    page_size = 1000
    # Supabase PostgREST: combine NULL + empty string via or()
    # or=(setup_type.is.null,setup_type.eq.)
    while True:
        resp = (
            sb.table("trades")
            .select(SELECT_COLS)
            .or_("setup_type.is.null,setup_type.eq.")
            .order("id")
            .range(page * page_size, (page + 1) * page_size - 1)
            .execute()
        )
        batch = resp.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        page += 1
    return rows


def inspect_rows(ids: list[int]) -> int:
    """Dump raw fields for specific trade ids so you can verify what's stored."""
    resp = (
        sb.table("trades")
        .select("*")
        .in_("id", ids)
        .order("id")
        .execute()
    )
    rows = resp.data or []
    found_ids = {r["id"] for r in rows}
    missing = [i for i in ids if i not in found_ids]
    if missing:
        print(f"NOT FOUND in DB: {missing}")
    for r in rows:
        st = r.get("setup_type")
        if st is None:
            st_disp = "<NULL>"
        elif st == "":
            st_disp = "<EMPTY STRING>"
        else:
            st_disp = repr(st)
        print("─" * 78)
        print(f"id={r['id']}  pair={r.get('pair')}  strategy={r.get('strategy')}  status={r.get('status')}")
        print(f"  setup_type   = {st_disp}")
        print(f"  reason       = {r.get('reason')!r}")
        print(f"  exit_reason  = {r.get('exit_reason')!r}")
        print(f"  signals_fired= {(r.get('signals_fired') or '')[:100]!r}")
        print(f"  opened_at    = {r.get('opened_at')}")
        print(f"  closed_at    = {r.get('closed_at')}")
        print(f"  entry={r.get('entry_price')} exit={r.get('exit_price')} "
              f"pnl={r.get('pnl')} pnl_pct={r.get('pnl_pct')} peak={r.get('peak_pnl')}")
        if st is not None and st != "":
            proposed = infer(r)
            print(f"  → would be relabeled to: {proposed}  (not picked up by backfill because setup_type is not NULL/empty)")
        else:
            print(f"  → backfill would set to: {infer(r)}")
    return 0


def main() -> int:
    if INSPECT_IDS:
        return inspect_rows(INSPECT_IDS)

    rows = fetch_missing_rows()
    null_count = sum(1 for r in rows if r.get("setup_type") is None)
    empty_count = sum(1 for r in rows if r.get("setup_type") == "")
    print(
        f"Found {len(rows)} trades with missing setup_type "
        f"(NULL={null_count}, empty-string={empty_count})"
    )
    if not rows:
        print("All trades already have a non-empty setup_type.")
        return 0

    # Show id range so the operator can cross-check the dashboard
    ids = [r["id"] for r in rows]
    print(f"Affected id range: {min(ids)} … {max(ids)}")

    plans: list[tuple[int, str]] = []
    breakdown: Counter[str] = Counter()
    strategy_breakdown: Counter[str] = Counter()
    for row in rows:
        label = infer(row)
        plans.append((row["id"], label))
        breakdown[label] += 1
        strategy_breakdown[row.get("strategy") or "<none>"] += 1

    print("\nBy strategy:")
    for s, count in strategy_breakdown.most_common():
        print(f"  {s:20s} {count}")

    print("\nInferred labels:")
    for label, count in breakdown.most_common():
        print(f"  {label:28s} {count}")

    print("\nSample (first 15, newest first):")
    for rid, label in sorted(plans, key=lambda p: -p[0])[:15]:
        matched = next(r for r in rows if r["id"] == rid)
        st = matched.get("setup_type")
        st_tag = "NULL" if st is None else ("EMPTY" if st == "" else "?")
        print(
            f"  id={rid:<6} [{st_tag:5s}] strategy={matched.get('strategy'):<13} "
            f"reason={(matched.get('reason') or '')[:40]:<40} → {label}"
        )

    if not APPLY:
        print("\nDRY RUN — pass --apply to write these updates.")
        print("Tip: use --inspect <id> to see the raw DB row for a trade.")
        return 0

    print(f"\nApplying {len(plans)} UPDATE statements...")
    ok = 0
    failed = 0
    for rid, label in plans:
        try:
            sb.table("trades").update({"setup_type": label}).eq("id", rid).execute()
            ok += 1
            if ok % 25 == 0:
                print(f"  updated {ok}/{len(plans)}")
        except Exception as e:
            failed += 1
            print(f"  FAIL id={rid}: {e}")

    print(f"\nDone: {ok} updated, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

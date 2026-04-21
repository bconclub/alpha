#!/usr/bin/env python3
"""Backfill NULL setup_type on existing trades rows.

Infers the historical setup_type from the row's strategy + reason fields so
that legacy/reconciled trades aren't rendered as None on the dashboard.

Usage:
    python3 engine/scripts/backfill_setup_type.py           # dry run
    python3 engine/scripts/backfill_setup_type.py --apply   # write updates
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
    """Map (strategy, reason, exit_reason) → a best-guess setup_type label."""
    strategy = (row.get("strategy") or "").lower()
    reason = (row.get("reason") or "").lower()
    exit_reason = (row.get("exit_reason") or "").lower()
    combined = f"{reason} {exit_reason}"

    if "discovered_by_reconcile" in reason:
        return "RECONCILED_DISCOVERED"
    if "discovered_on_restart" in reason:
        return "RECONCILED_RESTART"
    if "ghost" in combined or "smart_reconcile" in combined:
        return "MOMENTUM_BURST"
    if "backfill" in combined:
        return "backfill"
    if "bb_squeeze" in combined or "squeeze" in combined:
        return "BB_SQUEEZE"
    if "momentum" in combined:
        return "MOMENTUM_BURST_ENTRY"

    if strategy == "options_scalp":
        return "BB_SQUEEZE"
    if strategy == "scalp":
        return "UNSPECIFIED_LEGACY"
    return "UNSPECIFIED_LEGACY"


def fetch_null_rows() -> list[dict]:
    """Pull every trade where setup_type is NULL. Paginates defensively."""
    rows: list[dict] = []
    page = 0
    page_size = 1000
    while True:
        resp = (
            sb.table("trades")
            .select("id,strategy,reason,exit_reason,pair,status,opened_at")
            .is_("setup_type", "null")
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


def main() -> int:
    rows = fetch_null_rows()
    print(f"Found {len(rows)} trades with setup_type = NULL")
    if not rows:
        return 0

    plans: list[tuple[int, str]] = []
    breakdown: Counter[str] = Counter()
    for row in rows:
        label = infer(row)
        plans.append((row["id"], label))
        breakdown[label] += 1

    print("\nInferred labels:")
    for label, count in breakdown.most_common():
        print(f"  {label:28s} {count}")

    print("\nSample (first 15):")
    for rid, label in plans[:15]:
        matched = next(r for r in rows if r["id"] == rid)
        print(
            f"  id={rid:<6} strategy={matched.get('strategy'):<13} "
            f"reason={(matched.get('reason') or '')[:40]:<40} → {label}"
        )

    if not APPLY:
        print("\nDRY RUN — pass --apply to write these updates.")
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

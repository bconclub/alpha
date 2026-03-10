"""Fix all historical options trade P&L in Supabase.

The DB has wrong gross_pnl on options trades because the contract multiplier
was not applied.  Correct formula (Delta Exchange):

  ETH options: contract_multiplier = 0.01
  BTC options: contract_multiplier = 0.001

  gross_pnl = (exit_price - entry_price) * contracts * contract_multiplier
  net_pnl   = gross_pnl - entry_fee - exit_fee
  pnl_pct   = (exit_price - entry_price) / entry_price * 100

Usage:
  cd /root/alpha/engine && python3 scripts/fix_options_pnl.py          # dry run
  cd /root/alpha/engine && python3 scripts/fix_options_pnl.py --apply  # write
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from supabase import create_client


# ── Orphan trades that need metadata fixes too ──────────────────────────
ORPHAN_FIXES = {
    2062: {"pair": "P-BTC-69400", "contracts": 1, "entry_price": 356.0, "exit_price": 307.0},
    2063: {"pair": "P-BTC-69800", "contracts": 1, "entry_price": 338.0, "exit_price": 456.0},
}


def multiplier(pair: str) -> float:
    """Return the Delta Exchange contract multiplier for a given pair."""
    return 0.001 if "BTC" in pair.upper() else 0.01


def recalc(entry_price: float, exit_price: float, contracts: int,
           pair: str, entry_fee: float, exit_fee: float):
    """Return (gross_pnl, net_pnl, pnl_pct) using the correct formula."""
    m = multiplier(pair)
    gross = (exit_price - entry_price) * contracts * m
    net = gross - entry_fee - exit_fee
    pct = (exit_price - entry_price) / entry_price * 100 if entry_price else 0.0
    return gross, net, pct


def main():
    parser = argparse.ArgumentParser(description="Fix options P&L in Supabase")
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry run)")
    args = parser.parse_args()

    sb_url = os.getenv("SUPABASE_URL")
    sb_key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    if not sb_url or not sb_key:
        print("ERROR: SUPABASE_URL / SUPABASE_KEY not set in .env")
        sys.exit(1)

    sb = create_client(sb_url, sb_key)
    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"=== Options P&L Backfill ({mode}) ===\n")

    # ── 1. Fix orphan trades (2062, 2063) ────────────────────────────────
    for tid, info in ORPHAN_FIXES.items():
        entry_fee = 0.0
        exit_fee = 0.0
        # Fetch current row to get existing fees if any
        row = sb.table("trades").select("*").eq("id", tid).execute()
        if row.data:
            entry_fee = float(row.data[0].get("entry_fee") or 0)
            exit_fee = float(row.data[0].get("exit_fee") or 0)
            old_gross = row.data[0].get("gross_pnl")
            old_net = row.data[0].get("pnl")
        else:
            old_gross = None
            old_net = None

        gross, net, pct = recalc(
            info["entry_price"], info["exit_price"],
            info["contracts"], info["pair"], entry_fee, exit_fee,
        )
        print(f"ORPHAN  #{tid}: {info['pair']}")
        print(f"  gross {old_gross} -> {round(gross, 8)}, net {old_net} -> {round(net, 8)}, pct {round(pct, 4)}%")

        if args.apply:
            sb.table("trades").update({
                "strategy": "options_scalp",
                "contracts": info["contracts"],
                "leverage": 50,
                "gross_pnl": round(gross, 8),
                "pnl": round(net, 8),
                "pnl_pct": round(pct, 4),
            }).eq("id", tid).execute()
            print(f"  UPDATED")
        print()

    # ── 2. Fix all closed options_scalp trades ───────────────────────────
    resp = (
        sb.table("trades")
        .select("*")
        .eq("strategy", "options_scalp")
        .eq("status", "closed")
        .not_.is_("exit_price", "null")
        .order("id")
        .execute()
    )
    trades = resp.data or []
    print(f"Found {len(trades)} closed options_scalp trades\n")

    updated = 0
    skipped = 0
    for t in trades:
        tid = t["id"]

        # Orphans already handled above
        if tid in ORPHAN_FIXES:
            continue

        entry_price = float(t.get("entry_price") or 0)
        exit_price = float(t.get("exit_price") or 0)
        contracts = int(t.get("contracts") or t.get("amount") or 0)
        pair = t.get("pair") or ""
        entry_fee = float(t.get("entry_fee") or 0)
        exit_fee = float(t.get("exit_fee") or 0)

        if not entry_price or not exit_price or not contracts:
            print(f"SKIP    #{tid}: missing data (entry={entry_price}, exit={exit_price}, contracts={contracts})")
            skipped += 1
            continue

        old_gross = t.get("gross_pnl")
        old_net = t.get("pnl")
        gross, net, pct = recalc(entry_price, exit_price, contracts, pair, entry_fee, exit_fee)

        print(f"BACKFILL #{tid}: gross {old_gross} -> {round(gross, 8)}, net {old_net} -> {round(net, 8)}")

        if args.apply:
            sb.table("trades").update({
                "gross_pnl": round(gross, 8),
                "pnl": round(net, 8),
                "pnl_pct": round(pct, 4),
            }).eq("id", tid).execute()

        updated += 1

    print(f"\n=== Summary ({mode}) ===")
    print(f"  Orphans fixed:  {len(ORPHAN_FIXES)}")
    print(f"  Trades updated: {updated}")
    print(f"  Trades skipped: {skipped}")
    if not args.apply:
        print("\n  Re-run with --apply to write changes.")


if __name__ == "__main__":
    main()

"""
One-time fix for trades #2844 and #2845 on 2026-04-15.

Fetches real Delta fills for ETH 2320C, matches them to DB trades by timestamp,
and updates the DB with accurate entry/exit/PnL data.

Run from engine/ directory:
    cd /root/alpha/engine && python3 scripts/fix_apr15_trades.py [--apply]

Default is dry-run. Use --apply to actually write changes.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Any

# Ensure engine/ is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alpha.config import config
from alpha.db import Database
from alpha.smart_reconcile import SmartDeltaReconciler


async def main() -> None:
    parser = argparse.ArgumentParser(description="Fix Apr 15 Delta trades")
    parser.add_argument("--apply", action="store_true", help="Actually apply updates (default: dry-run)")
    parser.add_argument("--pair", default="ETH/USD:USD-260415-2320-C", help="Option symbol to fix")
    parser.add_argument("--date", default="2026-04-15", help="Date to fix (YYYY-MM-DD)")
    args = parser.parse_args()

    dry_run = not args.apply
    pair = args.pair
    date_str = args.date

    date_from = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    date_to = date_from + timedelta(days=1)

    print(f"=== Apr 15 Trade Fix (dry_run={dry_run}) ===")
    print(f"Pair: {pair}")
    print(f"Window: {date_from.isoformat()} → {date_to.isoformat()}")

    # Init DB
    db = Database()
    await db.connect()
    if not db.is_connected:
        print("ERROR: Could not connect to DB")
        sys.exit(1)

    # Init Delta exchange (same as main.py)
    import ccxt
    import aiohttp
    delta_key = getattr(config.delta, "api_key", "") or ""
    delta_secret = getattr(config.delta, "api_secret", "") or ""
    if not delta_key or not delta_secret:
        print("ERROR: Delta API credentials not configured")
        sys.exit(1)

    delta_options_session = aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(
            resolver=aiohttp.resolver.ThreadedResolver(), ssl=True,
        )
    )
    delta_options = ccxt.delta({
        "apiKey": delta_key,
        "secret": delta_secret,
        "enableRateLimit": True,
        "options": {"defaultType": "option"},
        "session": delta_options_session,
    })
    delta_options.urls["api"] = {
        "public": config.delta.base_url,
        "private": config.delta.base_url,
    }
    await delta_options.load_markets()

    logger = __import__("logging").getLogger("fix_apr15")
    logger.setLevel(__import__("logging").INFO)
    handler = __import__("logging").StreamHandler()
    handler.setFormatter(__import__("logging").Formatter("%(message)s"))
    logger.addHandler(handler)

    reconciler = SmartDeltaReconciler(delta_options, db.client, logger)
    result = await reconciler.run(date_from=date_from, date_to=date_to, dry_run=dry_run)

    print("\n=== RESULT ===")
    print(f"Processed: {result['processed']}")
    print(f"Updated:   {result['updated']}")
    print(f"Skipped:   {result['skipped']}")
    print(f"Errors:    {result['errors']}")

    # Also try to directly fetch and print the specific trades for verification
    try:
        resp = (
            db.client.table("trades")
            .select("*")
            .eq("pair", pair)
            .eq("exchange", "delta")
            .eq("strategy", "options_scalp")
            .gte("opened_at", date_from.isoformat())
            .lte("opened_at", date_to.isoformat())
            .order("opened_at", desc=False)
            .execute()
        )
        trades = resp.data or []
        print(f"\nDB trades for {pair}:")
        for t in trades:
            print(
                f"  #{t['id']}: opened_at={t['opened_at']} "
                f"contracts={t.get('contracts')} entry={t.get('entry_price')} "
                f"exit={t.get('exit_price')} pnl={t.get('pnl')} pnl_pct={t.get('pnl_pct')} "
                f"exit_reason={t.get('exit_reason')}"
            )
    except Exception as e:
        print(f"Could not fetch final DB state: {e}")

    # If we actually updated, set manual_fix_applied flag
    if not dry_run and result["updated"] > 0:
        for detail in result["details"]:
            if detail.get("action") == "updated":
                trade_id = detail["trade_id"]
                try:
                    # Fetch current metadata
                    row = db.client.table("trades").select("metadata").eq("id", trade_id).execute()
                    meta = {}
                    if row.data:
                        meta_raw = row.data[0].get("metadata") or {}
                        if isinstance(meta_raw, str):
                            meta = json.loads(meta_raw)
                        elif isinstance(meta_raw, dict):
                            meta = meta_raw
                    meta["manual_fix_applied"] = True
                    meta["fix_reason"] = "apr15_onetime_fix"
                    db.client.table("trades").update({"metadata": meta}).eq("id", trade_id).execute()
                    print(f"  → Marked trade #{trade_id} with manual_fix_applied=true")
                except Exception as e:
                    print(f"  → Failed to mark manual_fix on #{trade_id}: {e}")

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())

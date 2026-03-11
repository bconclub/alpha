"""Reconcile all historical options trades against Delta Exchange fills.

Pulls fills directly from Delta API, FIFO-matches into round trips,
then corrects every options_scalp trade in Supabase with the real
entry/exit prices, fees, and contract-multiplier P&L.

Usage:
  cd /root/alpha/engine && python3 scripts/reconcile_live.py          # dry run
  cd /root/alpha/engine && python3 scripts/reconcile_live.py --apply  # write
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import ccxt.async_support as ccxt
from supabase import create_client

# ── Constants ──────────────────────────────────────────────────────────
CONTRACT_MULTIPLIER = {"BTC": 0.001, "ETH": 0.01}

# Options symbol regex: ASSET-YYMMDD-STRIKE-C/P
_OPTION_RE = re.compile(r"(\w+)-(\d{6})-(\d+)-([CP])")

# ── Data structures ───────────────────────────────────────────────────

@dataclass
class Fill:
    """A single fill from Delta Exchange."""
    symbol: str         # ccxt unified symbol
    side: str           # "buy" or "sell"
    price: float
    amount: float       # contracts
    fee: float          # in USD
    timestamp: int      # ms
    order_id: str
    trade_id: str
    raw: dict = field(default_factory=dict, repr=False)


@dataclass
class RoundTrip:
    """A matched buy→sell pair for one option contract."""
    symbol: str
    entry_price: float
    exit_price: float
    contracts: float
    entry_fee: float
    exit_fee: float
    entry_ts: int
    exit_ts: int
    matched: bool = False  # True once paired with a DB trade


def base_asset(symbol: str) -> str:
    """Extract base asset (BTC/ETH) from an option symbol."""
    if "BTC" in symbol.upper():
        return "BTC"
    return "ETH"


def multiplier(symbol: str) -> float:
    return CONTRACT_MULTIPLIER.get(base_asset(symbol), 0.01)


def calc_pnl(rt: RoundTrip) -> tuple[float, float, float]:
    """Return (gross_pnl, net_pnl, pnl_pct) for a round trip."""
    m = multiplier(rt.symbol)
    gross = (rt.exit_price - rt.entry_price) * rt.contracts * m
    net = gross - rt.entry_fee - rt.exit_fee
    pct = (rt.exit_price - rt.entry_price) / rt.entry_price * 100 if rt.entry_price > 0 else 0.0
    return gross, net, pct


# ── Delta Exchange connection (same pattern as bot) ───────────────────

async def create_delta_exchange() -> ccxt.delta:
    """Create Delta Exchange ccxt instance using bot credentials."""
    api_key = os.getenv("DELTA_API_KEY", "").strip()
    api_secret = os.getenv("DELTA_SECRET", "").strip()
    testnet = os.getenv("DELTA_TESTNET", "false").lower() in ("true", "1", "yes")

    if not api_key or not api_secret:
        print("ERROR: DELTA_API_KEY / DELTA_SECRET not set in .env")
        sys.exit(1)

    if testnet:
        base_url = "https://cdn-ind.testnet.deltaex.org"
    else:
        base_url = "https://api.india.delta.exchange"

    exchange = ccxt.delta({
        "apiKey": api_key,
        "secret": api_secret,
        "enableRateLimit": True,
        "options": {"defaultType": "option"},
    })
    # Override to India endpoint (same as bot)
    exchange.urls["api"] = {
        "public": base_url,
        "private": base_url,
    }
    return exchange


# ── Fetch all option fills with pagination ────────────────────────────

def _parse_fill(t: dict) -> Fill | None:
    """Parse a ccxt-unified trade dict into a Fill (options only)."""
    symbol = t.get("symbol", "")
    if not _OPTION_RE.search(symbol):
        return None  # not an option

    fee_info = t.get("fee", {})
    fee_cost = float(fee_info.get("cost", 0) or 0) if isinstance(fee_info, dict) else 0

    return Fill(
        symbol=symbol,
        side=t.get("side", ""),
        price=float(t.get("price", 0) or 0),
        amount=float(t.get("amount", 0) or 0),
        fee=abs(fee_cost),
        timestamp=int(t.get("timestamp", 0) or 0),
        order_id=str(t.get("order", "")),
        trade_id=str(t.get("id", "")),
        raw=t,
    )


async def fetch_all_option_fills(exchange: ccxt.delta) -> list[Fill]:
    """Fetch all historical fills from Delta, keep only options.

    Uses the raw private_get_fills endpoint directly (bypassing ccxt's
    fetch_my_trades which mangles the 'since' parameter).  Delta's
    /fills API uses cursor-based pagination via meta.after / meta.before.

    We filter server-side with contract_types=call_options,put_options
    so every returned fill is an option.
    """
    from datetime import datetime, timezone

    all_fills: list[Fill] = []
    seen_ids: set[str] = set()

    print("Fetching fills from Delta Exchange...")
    await exchange.load_markets()

    PER_PAGE = 100
    MAX_PAGES = 200         # safety cap (~20k fills max)
    cursor_after: str | None = None

    page = 0
    while page < MAX_PAGES:
        page += 1

        req_params: dict = {
            "page_size": str(PER_PAGE),
            "contract_types": "call_options,put_options",
        }
        if cursor_after:
            req_params["after"] = cursor_after

        try:
            resp = await exchange.private_get_fills(req_params)
        except Exception as e:
            print(f"  Page {page} error: {e}")
            break

        if not isinstance(resp, dict):
            print(f"  Page {page}: unexpected response type {type(resp)}")
            break

        meta = resp.get("meta", {})
        raw_fills = resp.get("result", [])

        if not raw_fills:
            break

        # Parse each raw fill through ccxt's parser for unified format
        try:
            trades = exchange.parse_trades(raw_fills)
        except Exception:
            # If parse_trades fails, parse individually and skip bad ones
            trades = []
            for rf in raw_fills:
                try:
                    trades.append(exchange.parse_trade(rf))
                except Exception:
                    pass

        # Deduplicate
        new_count = 0
        for t in trades:
            tid = str(t.get("id", ""))
            if tid and tid not in seen_ids:
                seen_ids.add(tid)
                new_count += 1

                fill = _parse_fill(t)
                if fill:
                    all_fills.append(fill)

        # Also count raw fills for option detection (in case ccxt
        # strips the option symbol during parsing)
        if new_count == 0 and len(raw_fills) > 0:
            # ccxt might have failed to parse — try raw
            for rf in raw_fills:
                fid = str(rf.get("id", ""))
                if fid and fid not in seen_ids:
                    seen_ids.add(fid)
                    # Build Fill from raw Delta response
                    product_id = rf.get("product_id")
                    symbol = rf.get("product_symbol", "")
                    side = rf.get("side", "").lower()
                    price = float(rf.get("price", 0) or 0)
                    size = float(rf.get("size", 0) or 0)
                    fee = abs(float(rf.get("commission", 0) or 0))
                    ts_str = rf.get("created_at", "")
                    try:
                        ts = int(datetime.fromisoformat(
                            ts_str.replace("Z", "+00:00")
                        ).timestamp() * 1000)
                    except Exception:
                        ts = 0

                    if _OPTION_RE.search(symbol):
                        all_fills.append(Fill(
                            symbol=symbol,
                            side=side,
                            price=price,
                            amount=size,
                            fee=fee,
                            timestamp=ts,
                            order_id=str(rf.get("order_id", "")),
                            trade_id=fid,
                            raw=rf,
                        ))
                        new_count += 1

        print(
            f"  Page {page}: {len(raw_fills)} fills, {new_count} new "
            f"(total options: {len(all_fills)}) "
            f"cursor={'yes' if meta.get('after') else 'end'}"
        )

        # Next page cursor
        cursor_after = meta.get("after")
        if not cursor_after:
            break

        await asyncio.sleep(0.3)

    print(f"\nTotal option fills: {len(all_fills)}")
    if all_fills:
        all_fills.sort(key=lambda f: f.timestamp)
        oldest = datetime.fromtimestamp(
            all_fills[0].timestamp / 1000, tz=timezone.utc
        ).strftime("%Y-%m-%d")
        newest = datetime.fromtimestamp(
            all_fills[-1].timestamp / 1000, tz=timezone.utc
        ).strftime("%Y-%m-%d")
        print(f"  Date range: {oldest} to {newest}")
        print(f"  Sample fills:")
        for f in all_fills[:5]:
            print(f"    {f.symbol} | {f.side} {f.amount}x @ ${f.price} | fee=${f.fee}")
    return all_fills


# ── Build round trips via FIFO matching ───────────────────────────────

def build_round_trips(fills: list[Fill]) -> list[RoundTrip]:
    """FIFO match buys to sells per contract symbol."""
    # Group fills by symbol
    by_symbol: dict[str, list[Fill]] = defaultdict(list)
    for f in fills:
        by_symbol[f.symbol].append(f)

    round_trips: list[RoundTrip] = []

    for symbol, sym_fills in sorted(by_symbol.items()):
        # Sort by timestamp ascending
        sym_fills.sort(key=lambda f: f.timestamp)

        buys: list[Fill] = []
        sells: list[Fill] = []
        for f in sym_fills:
            if f.side == "buy":
                buys.append(f)
            else:
                sells.append(f)

        # FIFO match
        buy_idx = 0
        sell_idx = 0
        while buy_idx < len(buys) and sell_idx < len(sells):
            buy = buys[buy_idx]
            sell = sells[sell_idx]

            matched_qty = min(buy.amount, sell.amount)
            if matched_qty <= 0:
                buy_idx += 1
                continue

            # Proportional fees
            buy_fee_share = buy.fee * (matched_qty / buy.amount) if buy.amount > 0 else 0
            sell_fee_share = sell.fee * (matched_qty / sell.amount) if sell.amount > 0 else 0

            round_trips.append(RoundTrip(
                symbol=symbol,
                entry_price=buy.price,
                exit_price=sell.price,
                contracts=matched_qty,
                entry_fee=buy_fee_share,
                exit_fee=sell_fee_share,
                entry_ts=buy.timestamp,
                exit_ts=sell.timestamp,
            ))

            # Consume matched qty
            buy.amount -= matched_qty
            sell.amount -= matched_qty
            if buy.amount <= 0:
                buy_idx += 1
            if sell.amount <= 0:
                sell_idx += 1

        if buy_idx < len(buys):
            remaining = sum(b.amount for b in buys[buy_idx:] if b.amount > 0)
            if remaining > 0:
                print(f"  {symbol}: {remaining:.0f} unmatched buy contracts (open position?)")

    print(f"\nBuilt {len(round_trips)} round trips from {len(fills)} fills")
    return round_trips


# ── Normalize symbol for DB matching ──────────────────────────────────

def normalize_symbol(symbol: str) -> str:
    """Normalize option symbol to canonical form: ASSET-YYMMDD-STRIKE-C/P

    ETH/USD:USD-260311-2040-C   → ETH-260311-2040-C
    ETH/USDT:USDT-260310-2040-C → ETH-260310-2040-C
    BTC/USD:USD-260311-69400-P  → BTC-260311-69400-P
    ETH-260311-2040-C           → ETH-260311-2040-C  (already short)
    """
    # Extract base asset from "ETH/USD:..." or "BTC/USDT:..."
    base = symbol.split("/")[0] if "/" in symbol else None

    # Find the date-strike-C/P part
    m = re.search(r"(\d{6})-(\d+)-([CP])", symbol)
    if m:
        if base:
            return f"{base}-{m.group(1)}-{m.group(2)}-{m.group(3)}"
        # No slash — infer asset from strike (BTC strikes > 10000)
        strike = int(m.group(2))
        asset = "BTC" if strike >= 10000 else "ETH"
        return f"{asset}-{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return symbol


# ── Main reconciliation ──────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="Reconcile options trades against Delta fills")
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry run)")
    args = parser.parse_args()

    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"=== Options Reconciliation ({mode}) ===\n")

    # ── 1. Connect to Delta ──────────────────────────────────────────
    exchange = await create_delta_exchange()

    try:
        # ── 2. Fetch all option fills ────────────────────────────────
        fills = await fetch_all_option_fills(exchange)
        if not fills:
            print("No option fills found. Check API credentials and endpoint.")
            return

        # ── 3. Build round trips ─────────────────────────────────────
        round_trips = build_round_trips(fills)
        if not round_trips:
            print("No round trips matched.")
            return

        # Index round trips by DB pair for FIFO matching
        rt_by_pair: dict[str, list[RoundTrip]] = defaultdict(list)
        for rt in round_trips:
            db_pair = normalize_symbol(rt.symbol)
            rt_by_pair[db_pair].append(rt)

        # Sort each group by entry timestamp for FIFO
        for pair_rts in rt_by_pair.values():
            pair_rts.sort(key=lambda r: r.entry_ts)

        print(f"\nRound trips by pair:")
        for pair, rts in sorted(rt_by_pair.items()):
            total_gross = sum(calc_pnl(rt)[0] for rt in rts)
            print(f"  {pair}: {len(rts)} trades, gross=${total_gross:+.4f}")

        # ── 4. Connect to Supabase ───────────────────────────────────
        sb_url = os.getenv("SUPABASE_URL")
        sb_key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
        if not sb_url or not sb_key:
            print("\nERROR: SUPABASE_URL / SUPABASE_KEY not set in .env")
            return

        sb = create_client(sb_url, sb_key)

        # ── 5. Fetch all closed options trades from DB ───────────────
        resp = (
            sb.table("trades")
            .select("*")
            .eq("strategy", "options_scalp")
            .eq("status", "closed")
            .not_.is_("exit_price", "null")
            .order("id")
            .execute()
        )
        db_trades = resp.data or []
        print(f"\nDB: {len(db_trades)} closed options_scalp trades")

        # Debug: show sample pairs from both sides
        db_pairs_set = set()
        for t in db_trades[:10]:
            raw = t.get("pair", "")
            norm = normalize_symbol(raw)
            db_pairs_set.add(norm)
            print(f"  DB sample: id={t['id']} raw='{raw}' norm='{norm}'")
        rt_pairs_set = set(rt_by_pair.keys())
        overlap = db_pairs_set & rt_pairs_set
        print(f"\n  DB pairs (first 10 normalized): {sorted(db_pairs_set)}")
        print(f"  RT pairs: {sorted(rt_pairs_set)}")
        print(f"  Overlap: {sorted(overlap)} ({len(overlap)} pairs)")
        if not overlap:
            print("  WARNING: ZERO overlap — pair formats don't match!")

        # ── 6. FIFO match DB trades to round trips ───────────────────
        matched = 0
        unmatched_db = 0
        updated = 0
        entry_changes = 0
        total_old_pnl = 0.0
        total_new_pnl = 0.0
        total_fees = 0.0

        # Track consumed round trips per pair
        rt_cursor: dict[str, int] = defaultdict(int)

        print(f"\n{'='*80}")
        print(f"{'ID':>6} {'Pair':<25} {'Old Net':>10} {'New Net':>10} {'Delta':>10} {'Fees':>8} {'Entry Chg'}")
        print(f"{'='*80}")

        for t in db_trades:
            tid = t["id"]
            db_pair_raw = t.get("pair", "")
            db_pair = normalize_symbol(db_pair_raw)  # canonical form for matching
            old_entry = float(t.get("entry_price") or 0)
            old_exit = float(t.get("exit_price") or 0)
            old_net = float(t.get("pnl") or 0)

            # Find matching round trip (FIFO)
            cursor = rt_cursor[db_pair]
            pair_rts = rt_by_pair.get(db_pair, [])

            if cursor >= len(pair_rts):
                # No more round trips for this pair
                unmatched_db += 1
                print(f"{tid:>6} {db_pair:<25} {'UNMATCHED':>10} (no Delta fill)")
                continue

            rt = pair_rts[cursor]
            rt_cursor[db_pair] = cursor + 1
            rt.matched = True
            matched += 1

            # Calculate correct P&L
            gross, net, pct = calc_pnl(rt)
            total_old_pnl += old_net
            total_new_pnl += net
            total_fees += rt.entry_fee + rt.exit_fee

            entry_changed = abs(rt.entry_price - old_entry) > 0.001
            if entry_changed:
                entry_changes += 1

            delta_pnl = net - old_net
            entry_flag = f"${old_entry:.2f}->${rt.entry_price:.2f}" if entry_changed else ""

            print(
                f"{tid:>6} {db_pair:<25} "
                f"${old_net:>9.4f} ${net:>9.4f} ${delta_pnl:>9.4f} "
                f"${rt.entry_fee + rt.exit_fee:>7.4f} {entry_flag}"
            )

            if args.apply:
                update_data = {
                    "entry_price": round(rt.entry_price, 8),
                    "exit_price": round(rt.exit_price, 8),
                    "contracts": int(rt.contracts),
                    "entry_fee": round(rt.entry_fee, 8),
                    "exit_fee": round(rt.exit_fee, 8),
                    "gross_pnl": round(gross, 8),
                    "pnl": round(net, 8),
                    "pnl_pct": round(pct, 4),
                    "leverage": 50,
                    "strategy": "options_scalp",
                }
                sb.table("trades").update(update_data).eq("id", tid).execute()
                updated += 1

                # Rate limit: pause every 25 updates
                if updated % 25 == 0:
                    await asyncio.sleep(0.5)

        # ── 7. Report unmatched round trips ──────────────────────────
        unmatched_rt = [rt for rt in round_trips if not rt.matched]

        print(f"\n{'='*80}")
        print(f"=== Summary ({mode}) ===")
        print(f"  Delta fills:        {len(fills)}")
        print(f"  Round trips:        {len(round_trips)}")
        print(f"  DB trades:          {len(db_trades)}")
        print(f"  Matched:            {matched}")
        print(f"  Unmatched DB:       {unmatched_db}")
        print(f"  Unmatched Delta:    {len(unmatched_rt)}")
        print(f"  Entry price changes:{entry_changes}")
        print(f"  Old total P&L:      ${total_old_pnl:+.4f}")
        print(f"  New total P&L:      ${total_new_pnl:+.4f}")
        print(f"  Total fees:         ${total_fees:.4f}")
        print(f"  P&L delta:          ${total_new_pnl - total_old_pnl:+.4f}")

        if updated:
            print(f"  DB rows updated:    {updated}")

        if unmatched_rt:
            print(f"\n  Unmatched Delta round trips:")
            for rt in unmatched_rt:
                g, n, p = calc_pnl(rt)
                print(f"    {normalize_symbol(rt.symbol)}: ${rt.entry_price:.2f}->${rt.exit_price:.2f} x{rt.contracts:.0f} net=${n:.4f}")

        if not args.apply and matched > 0:
            print(f"\n  Re-run with --apply to write changes.")

    finally:
        await exchange.close()


if __name__ == "__main__":
    asyncio.run(main())

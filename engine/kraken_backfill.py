"""Kraken Trades Backfill — fetch fill history from Kraken Futures and backfill
missing trades into Supabase so the dashboard shows the complete picture.

Uses FIFO position reconstruction from individual fills to create trade records.
Each fill-pair (entry portion → exit fill) becomes one DB row — matching the
Kraken dashboard view.

Run from engine/ directory where .env exists:
    python kraken_backfill.py                  # dry-run: show what's missing
    python kraken_backfill.py --apply          # actually write missing trades to DB
    python kraken_backfill.py --hours 72       # custom lookback (default: 48h)
    python kraken_backfill.py --pair XRP       # single pair only
"""

import asyncio
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure engine/ is on path for alpha imports
sys.path.insert(0, str(Path(__file__).parent))

# ── Config ────────────────────────────────────────────────────────────────────

PAIRS = ["ETH/USD:USD", "XRP/USD:USD"]
LEVERAGE = 50  # Kraken Futures leverage (matches screenshots)
DEFAULT_TAKER_FEE = 0.0005  # 0.05%/side


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class ReconTrade:
    """A reconstructed trade from FIFO fill matching."""
    pair: str
    side: str           # "long" or "short"
    entry_price: float
    exit_price: float
    amount: float       # base currency (XRP count or ETH amount)
    opened_at: str      # ISO datetime of entry fill
    closed_at: str      # ISO datetime of exit fill
    entry_ts: int       # unix ms
    exit_ts: int        # unix ms
    entry_fee: float    # from exchange fill data
    exit_fee: float     # from exchange fill data


# ── Fetch fills with pagination ───────────────────────────────────────────────

async def fetch_all_fills(exchange, pair: str, since_ms: int) -> list[dict]:
    """Fetch all fills for a pair since a timestamp, handling pagination."""
    all_fills: list[dict] = []
    cursor = since_ms
    while True:
        batch = await exchange.fetch_my_trades(pair, since=cursor, limit=500)
        if not batch:
            break
        all_fills.extend(batch)
        if len(batch) < 500:
            break
        # Next page: 1ms after last fill to avoid duplicates
        cursor = batch[-1]["timestamp"] + 1
    return all_fills


# ── FIFO position reconstruction ─────────────────────────────────────────────

def reconstruct_trades(fills: list[dict], pair: str) -> list[ReconTrade]:
    """Reconstruct complete trades from a chronological sequence of fills.

    Uses FIFO matching: oldest entry fills are matched first when closing.
    Each (entry_portion, exit_fill) pair becomes one ReconTrade — matching
    the row-per-fill view on the Kraken dashboard.
    """
    if not fills:
        return []

    fills = sorted(fills, key=lambda f: f["timestamp"])
    trades: list[ReconTrade] = []

    # Stack of open entry fills: [(price, amount, timestamp, datetime, fee)]
    open_stack: list[tuple[float, float, int, str, float]] = []
    pos_side: str = ""  # "long" | "short" | ""

    for fill in fills:
        f_side = fill["side"]        # "buy" or "sell"
        f_price = float(fill["price"])
        f_amount = float(fill["amount"])
        f_ts = fill["timestamp"]
        f_dt = fill["datetime"]
        f_fee = float((fill.get("fee") or {}).get("cost", 0) or 0)

        if not pos_side:
            # No open position — this fill opens one
            pos_side = "long" if f_side == "buy" else "short"
            open_stack.append((f_price, f_amount, f_ts, f_dt, f_fee))
            continue

        # Same direction → adding to position
        same_dir = (pos_side == "long" and f_side == "buy") or \
                   (pos_side == "short" and f_side == "sell")
        if same_dir:
            open_stack.append((f_price, f_amount, f_ts, f_dt, f_fee))
            continue

        # Opposite direction → closing (FIFO)
        remaining = f_amount
        while remaining > 1e-12 and open_stack:
            e_price, e_amount, e_ts, e_dt, e_fee = open_stack[0]
            matched = min(remaining, e_amount)

            # Pro-rate entry fee by matched portion
            entry_fee_portion = e_fee * (matched / e_amount) if e_amount > 0 else 0
            exit_fee_portion = f_fee * (matched / f_amount) if f_amount > 0 else 0

            trades.append(ReconTrade(
                pair=pair,
                side=pos_side,
                entry_price=e_price,
                exit_price=f_price,
                amount=round(matched, 8),
                opened_at=e_dt,
                closed_at=f_dt,
                entry_ts=e_ts,
                exit_ts=f_ts,
                entry_fee=round(entry_fee_portion, 8),
                exit_fee=round(exit_fee_portion, 8),
            ))

            remaining -= matched
            if matched >= e_amount - 1e-12:
                open_stack.pop(0)
            else:
                # Partial match — reduce entry
                leftover = e_amount - matched
                leftover_fee = e_fee * (leftover / e_amount) if e_amount > 0 else 0
                open_stack[0] = (e_price, leftover, e_ts, e_dt, leftover_fee)

        if remaining > 1e-12:
            # More closing than opening → position flipped direction
            new_side = "long" if f_side == "buy" else "short"
            pos_side = new_side
            leftover_fee = f_fee * (remaining / f_amount) if f_amount > 0 else 0
            open_stack.append((f_price, remaining, f_ts, f_dt, leftover_fee))
        elif not open_stack:
            pos_side = ""

    return trades


# ── DB matching ───────────────────────────────────────────────────────────────

def find_db_match(trade: ReconTrade, db_trades: list[dict]) -> dict | None:
    """Find a matching DB trade for a reconstructed trade.

    Matches on: pair + side + entry_price (±0.5%) + amount (±40%) + time (±120s).
    """
    for db_t in db_trades:
        if db_t.get("_matched"):
            continue

        if db_t.get("pair") != trade.pair:
            continue

        # Side match
        db_side = db_t.get("position_type", "")
        if db_side != trade.side:
            continue

        # Entry price within 0.5%
        db_entry = float(db_t.get("entry_price", 0) or 0)
        if db_entry <= 0:
            continue
        if abs(db_entry - trade.entry_price) / trade.entry_price * 100 > 0.5:
            continue

        # Amount within 40% (fills can be split differently vs DB aggregation)
        db_amount = float(db_t.get("amount", 0) or db_t.get("contracts", 0) or 0)
        if db_amount > 0:
            ratio = min(db_amount, trade.amount) / max(db_amount, trade.amount)
            if ratio < 0.60:
                continue

        # Time within 120 seconds
        db_opened = db_t.get("opened_at", "")
        if db_opened:
            try:
                db_time = datetime.fromisoformat(db_opened.replace("Z", "+00:00"))
                trade_time = datetime.fromisoformat(trade.opened_at.replace("Z", "+00:00"))
                if abs((db_time - trade_time).total_seconds()) > 120:
                    continue
            except (ValueError, TypeError):
                continue

        db_t["_matched"] = True
        return db_t

    return None


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    # ── Deferred heavy imports (only needed when actually running) ─────────
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
    import ccxt.async_support as ccxt
    from supabase import create_client
    from alpha.trade_executor import calc_pnl

    KRAKEN_TAKER_FEE = float(os.getenv("KRAKEN_TAKER_FEE", str(DEFAULT_TAKER_FEE)))

    # ── Parse args ────────────────────────────────────────────────────────────
    apply = "--apply" in sys.argv
    hours = 48
    pair_filter = ""
    for i, arg in enumerate(sys.argv):
        if arg == "--hours" and i + 1 < len(sys.argv):
            hours = int(sys.argv[i + 1])
        if arg == "--pair" and i + 1 < len(sys.argv):
            pair_filter = sys.argv[i + 1].upper()

    pairs = PAIRS
    if pair_filter:
        pairs = [p for p in PAIRS if pair_filter in p]
        if not pairs:
            print(f"ERROR: no pair matches '{pair_filter}'. Available: {PAIRS}")
            return

    mode = "🔴 APPLY" if apply else "🟡 DRY-RUN"
    print(f"\n{'='*72}")
    print(f"  KRAKEN TRADES BACKFILL — {mode}")
    print(f"  Lookback: {hours}h | Pairs: {', '.join(pairs)}")
    print(f"  Leverage: {LEVERAGE}x | Taker fee: {KRAKEN_TAKER_FEE*100:.3f}%/side")
    print(f"{'='*72}\n")

    # ── Connect to Supabase ───────────────────────────────────────────────────
    sb_url = os.getenv("SUPABASE_URL")
    sb_key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    if not sb_url or not sb_key:
        print("ERROR: SUPABASE_URL or SUPABASE_KEY not set in .env")
        return
    sb = create_client(sb_url, sb_key)
    print("✓ Connected to Supabase")

    # ── Connect to Kraken Futures ─────────────────────────────────────────────
    kraken_key = os.getenv("KRAKEN_API_KEY")
    kraken_secret = os.getenv("KRAKEN_SECRET")
    if not kraken_key or not kraken_secret:
        print("ERROR: KRAKEN_API_KEY or KRAKEN_SECRET not set in .env")
        return

    kraken = ccxt.krakenfutures({
        "apiKey": kraken_key,
        "secret": kraken_secret,
        "enableRateLimit": True,
    })
    print("✓ Connected to Kraken Futures")

    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    since_ms = int(since.timestamp() * 1000)
    since_iso = since.isoformat()

    try:
        # ── 1. Fetch fills from Kraken ────────────────────────────────────────
        print(f"\n── Step 1: Fetch fills from Kraken (last {hours}h) ──")
        pair_fills: dict[str, list[dict]] = {}
        total_fills = 0
        for pair in pairs:
            fills = await fetch_all_fills(kraken, pair, since_ms)
            pair_fills[pair] = fills
            total_fills += len(fills)
            print(f"  {pair}: {len(fills)} fills")
        print(f"  Total: {total_fills} fills")

        # ── 2. Reconstruct trades via FIFO ────────────────────────────────────
        print(f"\n── Step 2: Reconstruct positions (FIFO matching) ──")
        all_trades: list[ReconTrade] = []
        for pair in pairs:
            trades = reconstruct_trades(pair_fills[pair], pair)
            all_trades.extend(trades)
            print(f"  {pair}: {len(trades)} complete trades reconstructed")
        all_trades.sort(key=lambda t: t.entry_ts)
        print(f"  Total: {len(all_trades)} trades")

        # ── 3. Fetch DB trades for comparison ─────────────────────────────────
        print(f"\n── Step 3: Fetch DB trades for comparison ──")
        db_result = (
            sb.table("trades")
            .select("*")
            .eq("exchange", "kraken")
            .gte("opened_at", since_iso)
            .order("opened_at", desc=False)
            .execute()
        )
        db_trades = db_result.data or []
        print(f"  DB has {len(db_trades)} Kraken trades in period")

        # ── 4. Match exchange trades → DB trades ──────────────────────────────
        print(f"\n── Step 4: Match exchange ↔ DB ──")
        matched: list[ReconTrade] = []
        unmatched: list[ReconTrade] = []

        for trade in all_trades:
            db_match = find_db_match(trade, db_trades)
            if db_match:
                matched.append(trade)
            else:
                unmatched.append(trade)

        db_unmatched = [t for t in db_trades if not t.get("_matched")]

        # ── 5. Summary ────────────────────────────────────────────────────────
        print(f"\n{'='*72}")
        print(f"  RESULTS")
        print(f"{'='*72}")
        print(f"  Exchange trades (reconstructed): {len(all_trades)}")
        print(f"  DB trades:                       {len(db_trades)}")
        print(f"  ✓ Matched:                       {len(matched)}")
        print(f"  ✗ Missing from DB:               {len(unmatched)}  ← NEED BACKFILL")
        print(f"  ? DB-only (extra):               {len(db_unmatched)}")

        if unmatched:
            print(f"\n{'='*72}")
            print(f"  MISSING TRADES ({len(unmatched)} need backfill)")
            print(f"{'='*72}")
            total_pnl = 0.0
            total_gross = 0.0
            for i, t in enumerate(unmatched, 1):
                # Use bot's calc_pnl for accurate P&L
                pnl_result = calc_pnl(
                    entry_price=t.entry_price,
                    exit_price=t.exit_price,
                    amount=t.amount,
                    position_type=t.side,
                    leverage=LEVERAGE,
                    exchange_id="kraken",
                    pair=t.pair,
                    entry_fee_rate=KRAKEN_TAKER_FEE,
                    exit_fee_rate=KRAKEN_TAKER_FEE,
                )
                total_pnl += pnl_result.net_pnl
                total_gross += pnl_result.gross_pnl
                # Compact display
                amt_str = f"{t.amount:.3f}" if t.pair.startswith("ETH") else f"{t.amount:.0f}"
                print(
                    f"  {i:3d}. {t.pair:15s} {t.side:5s} {amt_str:>8s} "
                    f"@ ${t.entry_price:>10.4f} → ${t.exit_price:>10.4f} | "
                    f"PnL=${pnl_result.net_pnl:>+7.2f} ({pnl_result.pnl_pct:>+6.2f}%) | "
                    f"{t.opened_at[:19]} → {t.closed_at[:19]}"
                )

            print(f"\n  Total missing: gross=${total_gross:+.2f}  net=${total_pnl:+.2f}")

        if db_unmatched:
            print(f"\n  DB-only trades ({len(db_unmatched)}) — may be from reconciliation/manual:")
            for t in db_unmatched[:10]:
                status = t.get("status", "?")
                ep = t.get("entry_price", 0)
                xp = t.get("exit_price", "-")
                print(
                    f"    id={str(t.get('id','?')):>5s} {t.get('pair',''):15s} "
                    f"{t.get('position_type',''):5s} ${ep} → ${xp} | "
                    f"{status} | {t.get('opened_at','')[:19]}"
                )
            if len(db_unmatched) > 10:
                print(f"    ... and {len(db_unmatched) - 10} more")

        # ── 6. Backfill if --apply ────────────────────────────────────────────
        if unmatched and apply:
            print(f"\n{'='*72}")
            print(f"  BACKFILLING {len(unmatched)} TRADES TO SUPABASE...")
            print(f"{'='*72}")

            inserted = 0
            failed = 0
            for trade in unmatched:
                try:
                    pnl_result = calc_pnl(
                        entry_price=trade.entry_price,
                        exit_price=trade.exit_price,
                        amount=trade.amount,
                        position_type=trade.side,
                        leverage=LEVERAGE,
                        exchange_id="kraken",
                        pair=trade.pair,
                        entry_fee_rate=KRAKEN_TAKER_FEE,
                        exit_fee_rate=KRAKEN_TAKER_FEE,
                    )
                    notional = trade.entry_price * trade.amount
                    collateral = notional / LEVERAGE

                    data = {
                        "pair": trade.pair,
                        "side": "buy" if trade.side == "long" else "sell",
                        "entry_price": round(trade.entry_price, 8),
                        "exit_price": round(trade.exit_price, 8),
                        "amount": round(trade.amount, 8),
                        "contracts": round(trade.amount, 8),
                        "cost": round(notional, 8),
                        "collateral": round(collateral, 8),
                        "strategy": "scalp",
                        "order_type": "market",
                        "exchange": "kraken",
                        "status": "closed",
                        "opened_at": trade.opened_at,
                        "closed_at": trade.closed_at,
                        "reason": "BACKFILL from Kraken exchange",
                        "exit_reason": "BACKFILL",
                        "leverage": LEVERAGE,
                        "position_type": trade.side,
                        "setup_type": "backfill",
                        "pnl": pnl_result.net_pnl,
                        "pnl_pct": pnl_result.pnl_pct,
                        "gross_pnl": pnl_result.gross_pnl,
                        "entry_fee": pnl_result.entry_fee,
                        "exit_fee": pnl_result.exit_fee,
                    }

                    result = sb.table("trades").insert(data).execute()
                    row_id = result.data[0].get("id") if result.data else "?"
                    inserted += 1
                    amt_str = f"{trade.amount:.3f}" if trade.pair.startswith("ETH") else f"{trade.amount:.0f}"
                    print(
                        f"  ✓ id={row_id} {trade.pair} {trade.side} {amt_str} "
                        f"${trade.entry_price:.4f}→${trade.exit_price:.4f} "
                        f"PnL=${pnl_result.net_pnl:+.2f}"
                    )
                except Exception as e:
                    failed += 1
                    print(f"  ✗ FAILED {trade.pair} {trade.side} {trade.amount}: {e}")

            print(f"\n  Done: {inserted} inserted, {failed} failed")

        elif unmatched and not apply:
            print(f"\n  👉 Run with --apply to insert these {len(unmatched)} trades into Supabase")
        else:
            print(f"\n  ✓ All exchange trades already in DB — nothing to backfill!")

    finally:
        await kraken.close()
        print("\n✓ Kraken connection closed")


if __name__ == "__main__":
    asyncio.run(main())

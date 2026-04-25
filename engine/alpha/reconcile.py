"""
Auto-reconciliation against Delta Exchange fills.

Pulls recent fills from the exchange API, FIFO-matches them into
round trips, compares against DB, and fixes discrepancies:
  - UPDATE trades where entry/exit/fees/pnl differ
  - INSERT ghost trades that were never recorded

Usage (from bot):
    reconciler = DeltaReconciler(delta_options, db.client, logger)
    result = await reconciler.run(since_hours=2)
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
from typing import Any

CONTRACT_MULTIPLIER: dict[str, float] = {"ETH": 0.01, "BTC": 0.001}


class DeltaReconciler:
    """Pull fills from Delta Exchange, build round trips, reconcile with DB."""

    def __init__(
        self,
        options_exchange: Any,
        db_client: Any,
        logger: logging.Logger | None = None,
    ) -> None:
        self.exchange = options_exchange
        self.db = db_client  # raw Supabase client
        self.log = logger or logging.getLogger(__name__)

    # ──────────────────────────────────────────────────────
    # PUBLIC
    # ──────────────────────────────────────────────────────

    async def run(self, since_hours: int = 2) -> dict:
        """Run full reconciliation cycle. Returns summary dict."""
        since_ts = datetime.now(timezone.utc) - timedelta(hours=since_hours)
        since_ms = int(since_ts.timestamp() * 1000)

        self.log.info(
            "RECONCILE START: looking back %dh (since %s)",
            since_hours, since_ts.strftime("%Y-%m-%d %H:%M UTC"),
        )

        # 1. Discover symbols
        symbols = await self._discover_symbols(since_ts)
        if not symbols:
            self.log.info("RECONCILE: no symbols found — nothing to do")
            return self._empty_result()

        self.log.info("RECONCILE: found %d symbols: %s", len(symbols), symbols)

        # 2. Fetch all fills from exchange
        all_fills = await self._fetch_all_fills(symbols, since_ms)
        if not all_fills:
            self.log.info("RECONCILE: no fills from exchange — nothing to do")
            return self._empty_result()

        self.log.info("RECONCILE: fetched %d fills across %d symbols", len(all_fills), len(symbols))

        # 3. Build round trips (FIFO)
        round_trips = self._build_round_trips(all_fills)
        self.log.info("RECONCILE: built %d round trips from fills", len(round_trips))

        # 4. Fetch DB trades for same period
        db_trades = self._fetch_db_trades(since_ts)
        self.log.info("RECONCILE: found %d DB trades in window", len(db_trades))

        # 5-7. Match, update, insert
        result = await self._reconcile(round_trips, db_trades)

        self.log.info(
            "RECONCILE DONE: matched=%d updated=%d inserted=%d "
            "delta_net=$%.4f db_net=$%.4f diff=$%.4f",
            result["matched"], result["updated"], result["inserted"],
            result["delta_net"], result["db_net"], result["diff"],
        )

        return result

    # ──────────────────────────────────────────────────────
    # SYMBOL DISCOVERY
    # ──────────────────────────────────────────────────────

    async def _discover_symbols(self, since: datetime) -> list[str]:
        """Find all option symbols traded in the window."""
        symbols: set[str] = set()

        # Source 1: DB trades
        try:
            since_iso = since.isoformat()
            resp = (
                self.db.table("trades")
                .select("pair")
                .eq("strategy", "options_scalp")
                .gte("opened_at", since_iso)
                .execute()
            )
            for row in resp.data or []:
                pair = row.get("pair")
                if pair and ("C" in pair or "P" in pair):
                    symbols.add(pair)
        except Exception:
            self.log.exception("RECONCILE: failed to query DB for symbols")

        # Source 2: Exchange recent orders (catches ghosts not in DB)
        try:
            # Try fetching orders without symbol to get all recent activity
            orders = await self.exchange.fetch_orders(None, since=int(since.timestamp() * 1000), limit=200)
            for order in orders:
                sym = order.get("symbol", "")
                if sym and ("-C" in sym or "-P" in sym):
                    symbols.add(sym)
        except Exception:
            # Some exchanges don't support fetch_orders without symbol
            self.log.debug("RECONCILE: fetch_orders(None) not supported, using DB symbols only")

        return sorted(symbols)

    # ──────────────────────────────────────────────────────
    # FILL FETCHING
    # ──────────────────────────────────────────────────────

    async def _fetch_all_fills(self, symbols: list[str], since_ms: int) -> list[dict]:
        """Fetch fills for all symbols from Delta Exchange."""
        all_fills: list[dict] = []

        for symbol in symbols:
            try:
                fills = await self.exchange.fetch_my_trades(symbol, since=since_ms, limit=500)
                for fill in fills:
                    fill["_symbol"] = symbol  # ensure symbol is attached
                all_fills.extend(fills)
                if fills:
                    self.log.debug(
                        "RECONCILE: %s → %d fills", symbol, len(fills),
                    )
                # Rate limit courtesy
                await asyncio.sleep(0.2)
            except Exception:
                self.log.warning("RECONCILE: failed to fetch fills for %s", symbol, exc_info=True)

        # Sort by timestamp
        all_fills.sort(key=lambda f: f.get("timestamp", 0))
        return all_fills

    # ──────────────────────────────────────────────────────
    # ROUND TRIP BUILDER (FIFO)
    # ──────────────────────────────────────────────────────

    @staticmethod
    def _merge_split_fills(fills: list[dict]) -> list[dict]:
        """Merge consecutive same-side fills on same symbol within 30s.

        Split fills (e.g. 14ct + 1ct + 1ct @$10.9 within 5s) get merged
        into a single fill with summed qty, weighted avg price, summed fees.
        """
        if not fills:
            return fills

        merged: list[dict] = []
        current = dict(fills[0])

        for fill in fills[1:]:
            same_side = fill.get("side", "").lower() == current.get("side", "").lower()
            same_sym = (fill.get("_symbol") or fill.get("symbol", "")) == (
                current.get("_symbol") or current.get("symbol", "")
            )

            # Check time gap
            cur_ts = current.get("timestamp", 0)
            fill_ts = fill.get("timestamp", 0)
            within_window = abs(fill_ts - cur_ts) <= 30_000  # 30s in ms

            if same_side and same_sym and within_window:
                # Merge: weighted avg price, sum qty, sum fees
                cur_qty = float(current.get("amount", 0))
                fill_qty = float(fill.get("amount", 0))
                cur_price = float(current.get("price", 0))
                fill_price = float(fill.get("price", 0))
                total_qty = cur_qty + fill_qty

                if total_qty > 0:
                    current["price"] = round(
                        (cur_price * cur_qty + fill_price * fill_qty) / total_qty, 8,
                    )
                current["amount"] = total_qty

                # Sum fees
                cur_fee = float((current.get("fee") or {}).get("cost", 0) or 0)
                fill_fee = float((fill.get("fee") or {}).get("cost", 0) or 0)
                current["fee"] = {"cost": cur_fee + fill_fee}
                # Keep earliest timestamp (already set from first fill)
            else:
                merged.append(current)
                current = dict(fill)

        merged.append(current)
        return merged

    def _build_round_trips(self, fills: list[dict]) -> list[dict]:
        """FIFO match buys to sells per symbol → round trips."""
        # Group fills by symbol
        by_symbol: dict[str, list[dict]] = defaultdict(list)
        for fill in fills:
            sym = fill.get("_symbol") or fill.get("symbol", "")
            by_symbol[sym].append(fill)

        round_trips: list[dict] = []

        for symbol, sym_fills in by_symbol.items():
            # Merge split fills before FIFO matching
            sym_fills = self._merge_split_fills(sym_fills)

            asset = self._get_asset(symbol)
            option_type = self._get_option_type(symbol)
            multiplier = CONTRACT_MULTIPLIER.get(asset, 0.01)

            # Separate buys and sells, maintain FIFO order
            buy_queue: deque[dict] = deque()
            sell_queue: deque[dict] = deque()

            for fill in sym_fills:
                side = fill.get("side", "").lower()
                if side == "buy":
                    buy_queue.append(fill)
                elif side == "sell":
                    sell_queue.append(fill)

            self.log.debug(
                "Building round trips for %s: %d buys, %d sells",
                symbol, len(buy_queue), len(sell_queue),
            )

            # FIFO match: each buy pairs with next sell
            while buy_queue and sell_queue:
                buy = buy_queue.popleft()
                sell = sell_queue.popleft()

                buy_price = float(buy.get("price", 0))
                sell_price = float(sell.get("price", 0))
                # Use the smaller quantity for the match
                buy_qty = float(buy.get("amount", 0))
                sell_qty = float(sell.get("amount", 0))
                qty = min(buy_qty, sell_qty)

                if qty <= 0:
                    continue

                # If quantities don't match, push remainder back
                if buy_qty > sell_qty:
                    remainder = dict(buy)
                    remainder["amount"] = buy_qty - sell_qty
                    buy_queue.appendleft(remainder)
                elif sell_qty > buy_qty:
                    remainder = dict(sell)
                    remainder["amount"] = sell_qty - buy_qty
                    sell_queue.appendleft(remainder)

                # Extract fees from fill data
                buy_fee = float((buy.get("fee") or {}).get("cost", 0) or 0)
                sell_fee = float((sell.get("fee") or {}).get("cost", 0) or 0)

                # Scale fees proportionally if partial match
                if buy_qty > 0 and qty < buy_qty:
                    buy_fee = buy_fee * (qty / buy_qty)
                if sell_qty > 0 and qty < sell_qty:
                    sell_fee = sell_fee * (qty / sell_qty)

                gross = round((sell_price - buy_price) * qty * multiplier, 8)
                net = round(gross - buy_fee - sell_fee, 8)
                pnl_pct = round((sell_price - buy_price) / buy_price * 100, 4) if buy_price > 0 else 0

                buy_time = buy.get("datetime") or ""
                sell_time = sell.get("datetime") or ""

                round_trips.append({
                    "pair": symbol,
                    "entry": buy_price,
                    "exit": sell_price,
                    "qty": int(qty),
                    "gross": gross,
                    "net": net,
                    "pct": pnl_pct,
                    "efee": round(buy_fee, 8),
                    "xfee": round(sell_fee, 8),
                    "buy_time": buy_time,
                    "sell_time": sell_time,
                    "asset": asset,
                    "option_type": option_type,
                })

            # Log unmatched fills
            if buy_queue:
                self.log.debug(
                    "RECONCILE: %s has %d unmatched buy fills (open position?)",
                    symbol, len(buy_queue),
                )
            if sell_queue:
                self.log.warning(
                    "RECONCILE: %s has %d unmatched sell fills (missing buys?)",
                    symbol, len(sell_queue),
                )
            if buy_queue and len(buy_queue) > len(sell_queue):
                self.log.warning(
                    "RECONCILE: %s has %d unmatched buys vs %d sells — "
                    "possible crossed trades (orphaned buys)",
                    symbol, len(buy_queue), len(sell_queue),
                )

        return round_trips

    # ──────────────────────────────────────────────────────
    # DB FETCH
    # ──────────────────────────────────────────────────────

    def _fetch_db_trades(self, since: datetime) -> list[dict]:
        """Fetch closed option trades from DB within the reconcile window."""
        try:
            since_iso = since.isoformat()
            resp = (
                self.db.table("trades")
                .select("*")
                .eq("strategy", "options_scalp")
                .eq("status", "closed")
                .gte("closed_at", since_iso)
                .order("id")
                .execute()
            )
            return resp.data or []
        except Exception:
            self.log.exception("RECONCILE: failed to fetch DB trades")
            return []

    # ──────────────────────────────────────────────────────
    # RECONCILIATION
    # ──────────────────────────────────────────────────────

    async def _reconcile(
        self, delta_rts: list[dict], db_trades: list[dict],
    ) -> dict:
        """Match Delta round trips against DB trades, fix discrepancies."""
        # Group both by pair in FIFO order
        delta_pool: dict[str, deque[dict]] = defaultdict(deque)
        for rt in delta_rts:
            delta_pool[rt["pair"]].append(rt)

        db_pool: dict[str, deque[dict]] = defaultdict(deque)
        for trade in db_trades:
            db_pool[trade["pair"]].append(trade)

        matched = 0
        updated = 0
        inserted = 0
        delta_net = sum(rt["net"] for rt in delta_rts)
        db_net = sum(float(t.get("pnl") or t.get("net_pnl") or 0) for t in db_trades)

        # Phase 1: Match DB trades to Delta round trips by pair (FIFO)
        matched_delta_indices: set[int] = set()
        delta_rt_list = list(delta_rts)  # for index tracking

        for pair, db_queue in db_pool.items():
            d_queue = delta_pool.get(pair)
            if not d_queue:
                continue

            # Count mismatch guard: skip updates if counts don't align
            if len(d_queue) != len(db_queue):
                self.log.warning(
                    "Mismatched trade count for %s: %d Delta round trips vs %d DB trades. "
                    "Skipping updates to prevent cross-trade corruption.",
                    pair, len(d_queue), len(db_queue),
                )
                continue

            for db_trade in db_queue:
                if not d_queue:
                    break

                # FIFO: pop first Delta round trip for this pair
                delta_rt = d_queue.popleft()

                # Find index in original list
                for idx, rt in enumerate(delta_rt_list):
                    if idx not in matched_delta_indices and rt is delta_rt:
                        matched_delta_indices.add(idx)
                        break

                matched += 1

                # Time-alignment guard before updating
                db_opened = db_trade.get("opened_at", "")
                delta_buy = delta_rt.get("buy_time", "")
                if db_opened and delta_buy:
                    try:
                        from datetime import datetime
                        db_dt = datetime.fromisoformat(str(db_opened).replace("Z", "+00:00"))
                        delta_dt = datetime.fromisoformat(str(delta_buy).replace("Z", "+00:00"))
                        time_diff = abs((db_dt - delta_dt).total_seconds())
                        if time_diff > 300:
                            self.log.warning(
                                "Skipping update for trade %s — time mismatch: "
                                "DB opened_at=%s, Delta buy_time=%s (diff=%ss)",
                                db_trade["id"], db_trade["opened_at"],
                                delta_rt["buy_time"], int(time_diff),
                            )
                            continue
                    except Exception:
                        pass

                # Check if values differ meaningfully
                db_entry = float(db_trade.get("entry_price") or 0)
                db_exit = float(db_trade.get("exit_price") or 0)
                db_pnl = float(db_trade.get("pnl") or db_trade.get("net_pnl") or 0)
                db_gross = float(db_trade.get("gross_pnl") or 0)
                db_efee = float(db_trade.get("entry_fee") or 0)
                db_xfee = float(db_trade.get("exit_fee") or 0)

                needs_update = (
                    abs(db_entry - delta_rt["entry"]) > 0.01
                    or abs(db_exit - delta_rt["exit"]) > 0.01
                    or abs(db_pnl - delta_rt["net"]) > 0.001
                    or abs(db_gross - delta_rt["gross"]) > 0.001
                    or abs(db_efee - delta_rt["efee"]) > 0.001
                    or abs(db_xfee - delta_rt["xfee"]) > 0.001
                )

                if needs_update:
                    trade_id = db_trade["id"]
                    entry_corrected = abs(db_entry - delta_rt["entry"]) > 0.01
                    update_data = {
                        "entry_price": delta_rt["entry"],
                        "exit_price": delta_rt["exit"],
                        "contracts": float(delta_rt["qty"]),
                        "gross_pnl": delta_rt["gross"],
                        "net_pnl": delta_rt["net"],
                        "pnl": delta_rt["net"],
                        "pnl_pct": delta_rt["pct"],
                        "entry_fee": delta_rt["efee"],
                        "exit_fee": delta_rt["xfee"],
                    }

                    # If entry_price was wrong, peak_pnl was computed from
                    # the wrong base — recalculate what we can.
                    if entry_corrected:
                        exit_pnl_pct = delta_rt["pct"]
                        if db_trade.get("status") == "closed" and exit_pnl_pct > 0:
                            # Trade was profitable: peak was at least the exit P&L%
                            update_data["peak_pnl"] = round(exit_pnl_pct, 4)
                        else:
                            # Negative or open: can't recover true peak, reset to 0
                            update_data["peak_pnl"] = 0

                    self.log.info(
                        "Updating trade %s: opened_at=%s, delta_buy=%s, delta_sell=%s, fields=%s",
                        trade_id, db_trade.get("opened_at"), delta_rt.get("buy_time"),
                        delta_rt.get("sell_time"), list(update_data.keys()),
                    )

                    try:
                        self.db.table("trades").update(update_data).eq("id", trade_id).execute()
                        updated += 1
                        peak_msg = ""
                        if entry_corrected:
                            old_peak = float(db_trade.get("peak_pnl") or 0)
                            peak_msg = f" peak {old_peak:.1f}%→{update_data['peak_pnl']:.1f}%"
                        self.log.info(
                            "RECONCILE UPDATE #%s: entry $%.2f→$%.2f exit $%.2f→$%.2f "
                            "net $%.6f→$%.6f%s",
                            trade_id, db_entry, delta_rt["entry"],
                            db_exit, delta_rt["exit"],
                            db_pnl, delta_rt["net"], peak_msg,
                        )
                    except Exception:
                        self.log.exception("RECONCILE UPDATE FAILED #%s", trade_id)

        # Phase 2: Insert ghost trades (unmatched Delta round trips)
        for idx, rt in enumerate(delta_rt_list):
            if idx in matched_delta_indices:
                continue

            # This is a ghost trade — Delta has it, DB doesn't
            # Dedup check: skip if DB already has a trade with same pair,
            # similar entry price, opened within 120s
            if self._is_duplicate(rt):
                continue

            row = self._build_insert_row(rt)
            try:
                self.db.table("trades").insert(row).execute()
                inserted += 1
                self.log.info(
                    "RECONCILE INSERT: %s $%.2f→$%.2f net=$%.6f (%s)",
                    rt["pair"], rt["entry"], rt["exit"], rt["net"], rt["option_type"],
                )
            except Exception:
                self.log.exception(
                    "RECONCILE INSERT FAILED: %s $%.2f→$%.2f",
                    rt["pair"], rt["entry"], rt["exit"],
                )

        diff = abs(delta_net - db_net)
        return {
            "matched": matched,
            "updated": updated,
            "inserted": inserted,
            "delta_net": round(delta_net, 8),
            "db_net": round(db_net, 8),
            "diff": round(diff, 8),
        }

    # ──────────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────────

    def _is_duplicate(self, rt: dict) -> bool:
        """Check if a round trip already exists in DB (dedup before insert)."""
        buy_time = rt.get("buy_time", "")
        if not buy_time:
            return False

        try:
            opened = datetime.fromisoformat(buy_time.replace("Z", "+00:00"))
            window = timedelta(seconds=120)
            opened_min = (opened - window).isoformat()
            opened_max = (opened + window).isoformat()

            resp = (
                self.db.table("trades")
                .select("id,entry_price,opened_at")
                .eq("pair", rt["pair"])
                .gte("opened_at", opened_min)
                .lte("opened_at", opened_max)
                .execute()
            )

            for ex in resp.data or []:
                ex_price = float(ex.get("entry_price") or 0)
                if abs(ex_price - rt["entry"]) < 2.0:
                    self.log.info(
                        "RECONCILE DEDUP: skipping %s $%.2f, matches #%s ($%.2f)",
                        rt["pair"], rt["entry"], ex["id"], ex_price,
                    )
                    return True
        except Exception:
            self.log.debug("RECONCILE DEDUP check failed for %s", rt["pair"], exc_info=True)

        return False

    def _build_insert_row(self, rt: dict) -> dict:
        """Build a DB insert row for a ghost trade."""
        buy_time = rt.get("buy_time", "")
        sell_time = rt.get("sell_time", "")

        # Parse ISO timestamps → UTC strings for DB
        opened_at = buy_time if buy_time else datetime.now(timezone.utc).isoformat()
        closed_at = sell_time if sell_time else datetime.now(timezone.utc).isoformat()

        pct = rt.get("pct", 0)
        # Ghost trade: no tick history, so peak = exit P&L% if positive, else 0
        peak_pnl = round(pct, 4) if pct > 0 else 0

        return {
            "pair": rt["pair"],
            "exchange": "delta",
            "strategy": "options_scalp",
            "side": "buy",
            "entry_price": rt["entry"],
            "exit_price": rt["exit"],
            "contracts": float(rt["qty"]),
            "leverage": 50,
            "gross_pnl": rt["gross"],
            "net_pnl": rt["net"],
            "pnl": rt["net"],
            "pnl_pct": pct,
            "peak_pnl": peak_pnl,
            "entry_fee": rt["efee"],
            "exit_fee": rt["xfee"],
            "status": "closed",
            "exit_reason": "GONE",
            "setup_type": "MOM_BURST",
            "opened_at": opened_at,
            "closed_at": closed_at,
        }

    @staticmethod
    def _get_asset(symbol: str) -> str:
        """Extract base asset from symbol like 'BTC/USD:USD-260311-69600-P'."""
        if symbol.startswith("BTC"):
            return "BTC"
        if symbol.startswith("ETH"):
            return "ETH"
        if symbol.startswith("SOL"):
            return "SOL"
        return symbol.split("/")[0] if "/" in symbol else "ETH"

    @staticmethod
    def _get_option_type(symbol: str) -> str:
        """Extract option type from symbol suffix."""
        if symbol.endswith("-C") or symbol.endswith("C"):
            return "call"
        if symbol.endswith("-P") or symbol.endswith("P"):
            return "put"
        return "call"

    @staticmethod
    def _empty_result() -> dict:
        return {
            "matched": 0, "updated": 0, "inserted": 0,
            "delta_net": 0.0, "db_net": 0.0, "diff": 0.0,
        }

"""
Smart reconciliation against Delta Exchange fills.

Unlike the FIFO reconciler, this matches trades by:
  - pair/symbol
  - opened_at timestamp (within 2-minute window)
  - entry_price (within 1% tolerance)

Features:
  - dry-run mode: preview changes without applying
  - metadata backup: stores old values before updating
  - manual_fix guard: skips trades marked with metadata.manual_fix_applied = true
  - time mismatch protection: skips if delta buy_time and DB opened_at differ > 5 min

Usage:
    from alpha.smart_reconcile import SmartDeltaReconciler
    reconciler = SmartDeltaReconciler(delta_options, db.client, logger)
    result = await reconciler.run(date_from, date_to, dry_run=False)
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
from typing import Any

CONTRACT_MULTIPLIER: dict[str, float] = {"ETH": 0.01, "BTC": 0.001}


class SmartDeltaReconciler:
    """Pull fills from Delta Exchange, build round trips, reconcile with DB smartly."""

    def __init__(
        self,
        options_exchange: Any,
        db_client: Any,
        logger: logging.Logger | None = None,
    ) -> None:
        self.exchange = options_exchange
        self.db = db_client
        self.log = logger or logging.getLogger(__name__)

    async def run(
        self,
        date_from: datetime,
        date_to: datetime,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Run smart reconciliation for a date range."""
        since_ms = int(date_from.timestamp() * 1000)

        self.log.info(
            "SMART RECONCILE START: %s → %s (dry_run=%s)",
            date_from.isoformat(), date_to.isoformat(), dry_run,
        )

        # 1. Discover symbols from DB and exchange
        symbols = await self._discover_symbols(date_from, date_to)
        if not symbols:
            self.log.info("SMART RECONCILE: no symbols found")
            return self._empty_result()

        self.log.info("SMART RECONCILE: %d symbols", len(symbols))

        # 2. Fetch fills
        all_fills = await self._fetch_all_fills(symbols, since_ms)
        if not all_fills:
            self.log.info("SMART RECONCILE: no fills")
            return self._empty_result()

        # 3. Build round trips
        round_trips = self._build_round_trips(all_fills)
        self.log.info("SMART RECONCILE: %d round trips", len(round_trips))

        # 4. Fetch DB trades
        db_trades = await self._fetch_db_trades(date_from, date_to)
        self.log.info("SMART RECONCILE: %d DB trades", len(db_trades))

        # 5. Match and update
        result = await self._reconcile(round_trips, db_trades, dry_run)

        self.log.info(
            "SMART RECONCILE DONE: processed=%d updated=%d skipped=%d errors=%d",
            result["processed"], result["updated"], result["skipped"], result["errors"],
        )
        return result

    # ──────────────────────────────────────────────────────
    # SYMBOL DISCOVERY
    # ──────────────────────────────────────────────────────

    async def _discover_symbols(self, date_from: datetime, date_to: datetime) -> list[str]:
        """Find all option symbols traded in the window."""
        symbols: set[str] = set()

        # Source 1: DB trades
        try:
            resp = (
                self.db.table("trades")
                .select("pair")
                .eq("strategy", "options_scalp")
                .eq("exchange", "delta")
                .gte("opened_at", date_from.isoformat())
                .lte("opened_at", date_to.isoformat())
                .execute()
            )
            for row in resp.data or []:
                pair = row.get("pair")
                if pair and ("-C" in pair or "-P" in pair):
                    symbols.add(pair)
        except Exception:
            self.log.exception("SMART RECONCILE: failed to query DB for symbols")

        # Source 2: Exchange recent orders
        try:
            orders = await self.exchange.fetch_orders(
                None, since=int(date_from.timestamp() * 1000), limit=500
            )
            for order in orders:
                sym = order.get("symbol", "")
                if sym and ("-C" in sym or "-P" in sym):
                    # Normalize symbol
                    symbols.add(sym)
        except Exception:
            self.log.debug("SMART RECONCILE: fetch_orders(None) not supported")

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
                    fill["_symbol"] = symbol
                all_fills.extend(fills)
                if fills:
                    self.log.debug("SMART RECONCILE: %s → %d fills", symbol, len(fills))
                await asyncio.sleep(0.2)
            except Exception:
                self.log.warning("SMART RECONCILE: failed to fetch fills for %s", symbol, exc_info=True)
        all_fills.sort(key=lambda f: f.get("timestamp", 0))
        return all_fills

    # ──────────────────────────────────────────────────────
    # ROUND TRIP BUILDER
    # ──────────────────────────────────────────────────────

    @staticmethod
    def _merge_split_fills(fills: list[dict]) -> list[dict]:
        """Merge consecutive same-side fills within 30s."""
        if not fills:
            return fills
        merged: list[dict] = []
        current = dict(fills[0])
        for fill in fills[1:]:
            same_side = fill.get("side", "").lower() == current.get("side", "").lower()
            same_sym = (fill.get("_symbol") or fill.get("symbol", "")) == (
                current.get("_symbol") or current.get("symbol", "")
            )
            within_window = abs(
                (fill.get("timestamp", 0) or 0) - (current.get("timestamp", 0) or 0)
            ) <= 30_000
            if same_side and same_sym and within_window:
                cur_qty = float(current.get("amount", 0))
                fill_qty = float(fill.get("amount", 0))
                cur_price = float(current.get("price", 0))
                fill_price = float(fill.get("price", 0))
                total_qty = cur_qty + fill_qty
                if total_qty > 0:
                    current["price"] = round(
                        (cur_price * cur_qty + fill_price * fill_qty) / total_qty, 8
                    )
                current["amount"] = total_qty
                cur_fee = float((current.get("fee") or {}).get("cost", 0) or 0)
                add_fee = float((fill.get("fee") or {}).get("cost", 0) or 0)
                current["fee"] = {"cost": cur_fee + add_fee}
            else:
                merged.append(current)
                current = dict(fill)
        merged.append(current)
        return merged

    def _build_round_trips(self, fills: list[dict]) -> list[dict]:
        """FIFO match buys to sells per symbol → round trips."""
        by_symbol: dict[str, list[dict]] = defaultdict(list)
        for fill in fills:
            sym = fill.get("_symbol") or fill.get("symbol", "")
            by_symbol[sym].append(fill)

        round_trips: list[dict] = []
        for symbol, sym_fills in by_symbol.items():
            sym_fills = self._merge_split_fills(sym_fills)
            asset = self._get_asset(symbol)
            option_type = self._get_option_type(symbol)
            multiplier = CONTRACT_MULTIPLIER.get(asset, 0.01)

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

            while buy_queue and sell_queue:
                buy = buy_queue.popleft()
                sell = sell_queue.popleft()
                buy_price = float(buy.get("price", 0))
                sell_price = float(sell.get("price", 0))
                buy_qty = float(buy.get("amount", 0))
                sell_qty = float(sell.get("amount", 0))
                qty = min(buy_qty, sell_qty)
                if qty <= 0:
                    continue
                if buy_qty > sell_qty:
                    remainder = dict(buy)
                    remainder["amount"] = buy_qty - sell_qty
                    buy_queue.appendleft(remainder)
                elif sell_qty > buy_qty:
                    remainder = dict(sell)
                    remainder["amount"] = sell_qty - buy_qty
                    sell_queue.appendleft(remainder)

                buy_fee = float((buy.get("fee") or {}).get("cost", 0) or 0)
                sell_fee = float((sell.get("fee") or {}).get("cost", 0) or 0)
                if buy_qty > 0 and qty < buy_qty:
                    buy_fee = buy_fee * (qty / buy_qty)
                if sell_qty > 0 and qty < sell_qty:
                    sell_fee = sell_fee * (qty / sell_qty)

                gross = round((sell_price - buy_price) * qty * multiplier, 8)
                net = round(gross - buy_fee - sell_fee, 8)
                pnl_pct = round((sell_price - buy_price) / buy_price * 100, 4) if buy_price > 0 else 0

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
                    "buy_time": buy.get("datetime") or "",
                    "sell_time": sell.get("datetime") or "",
                    "asset": asset,
                    "option_type": option_type,
                })

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

    async def _fetch_db_trades(self, date_from: datetime, date_to: datetime) -> list[dict]:
        """Fetch DB trades for the date range."""
        try:
            resp = (
                self.db.table("trades")
                .select("*")
                .eq("strategy", "options_scalp")
                .eq("exchange", "delta")
                .gte("opened_at", date_from.isoformat())
                .lte("opened_at", date_to.isoformat())
                .order("opened_at", desc=False)
                .execute()
            )
            return resp.data or []
        except Exception:
            self.log.exception("SMART RECONCILE: failed to fetch DB trades")
            return []

    # ──────────────────────────────────────────────────────
    # RECONCILIATION
    # ──────────────────────────────────────────────────────

    async def _reconcile(
        self, delta_rts: list[dict], db_trades: list[dict], dry_run: bool,
    ) -> dict[str, Any]:
        """Smart match and update.

        Behavior:
        - Match Delta round-trips to DB trades by pair + time + entry tolerance.
        - Update matched DB rows when values differ.
        - Mark unmatched DB rows as duplicate/unmatched (cleanup path).
        - Insert unmatched Delta round-trips as ghost-reconciled rows.
        """
        processed = 0
        updated = 0
        skipped = 0
        errors = 0
        duplicates_marked = 0
        ghosts_inserted = 0
        details: list[dict] = []

        # Group by pair
        db_by_pair: dict[str, list[dict]] = defaultdict(list)
        for t in db_trades:
            db_by_pair[t.get("pair", "")].append(t)

        rt_by_pair: dict[str, list[dict]] = defaultdict(list)
        for rt in delta_rts:
            rt_by_pair[rt["pair"]].append(rt)

        all_pairs = sorted(set(rt_by_pair.keys()) | set(db_by_pair.keys()))
        for pair in all_pairs:
            pair_rts = rt_by_pair.get(pair, [])
            db_list = db_by_pair.get(pair, [])
            used_db_ids: set[int] = set()
            matched_rt_idx: set[int] = set()

            if len(pair_rts) != len(db_list):
                self.log.warning(
                    "Count mismatch for %s: Delta=%d DB=%d. "
                    "Proceeding with safe matching + cleanup/ghost handling.",
                    pair, len(pair_rts), len(db_list),
                )

            for idx, delta_rt in enumerate(pair_rts):
                processed += 1
                match = self._find_best_match(
                    delta_rt,
                    [t for t in db_list if t.get("id") not in used_db_ids],
                )

                if not match:
                    self.log.warning(
                        "No DB match for Delta round trip %s buy_time=%s entry=$%.2f",
                        pair, delta_rt["buy_time"], delta_rt["entry"],
                    )
                    skipped += 1
                    details.append({
                        "pair": pair,
                        "action": "skipped_no_match",
                        "delta_index": idx,
                        "delta_buy_time": delta_rt["buy_time"],
                        "delta_entry": delta_rt["entry"],
                    })
                    continue

                db_trade, time_diff_sec = match
                trade_id = db_trade["id"]
                used_db_ids.add(trade_id)
                matched_rt_idx.add(idx)

                # Time mismatch guard
                if time_diff_sec > 300:
                    self.log.warning(
                        "Skipping update for trade %s — time mismatch: "
                        "DB opened_at=%s, Delta buy_time=%s (diff=%ss)",
                        trade_id, db_trade.get("opened_at"),
                        delta_rt["buy_time"], int(time_diff_sec),
                    )
                    skipped += 1
                    details.append({
                        "trade_id": trade_id,
                        "action": "skipped_time_mismatch",
                        "diff_sec": int(time_diff_sec),
                    })
                    continue

                # Manual fix guard
                metadata = db_trade.get("metadata") or {}
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except Exception:
                        metadata = {}
                if metadata.get("manual_fix_applied"):
                    self.log.info("Skipping trade %s — manual_fix_applied is set", trade_id)
                    skipped += 1
                    details.append({
                        "trade_id": trade_id,
                        "action": "skipped_manual_fix",
                    })
                    continue

                # Build update data
                update_data = self._build_update_data(db_trade, delta_rt)
                if not update_data:
                    details.append({
                        "trade_id": trade_id,
                        "action": "no_change_needed",
                    })
                    continue

                # Backup old values
                backup = {
                    k: float(db_trade.get(k, 0) or 0) if k in db_trade else None
                    for k in update_data.keys()
                }
                backup = {k: v for k, v in backup.items() if v is not None}
                update_data["metadata"] = {
                    **metadata,
                    "reconcile_backup": backup,
                    "reconciled_at": datetime.now(timezone.utc).isoformat(),
                }

                self.log.info(
                    "Updating trade %s: opened_at=%s, delta_buy=%s, delta_sell=%s, fields=%s",
                    trade_id, db_trade.get("opened_at"), delta_rt.get("buy_time"),
                    delta_rt.get("sell_time"), list(update_data.keys()),
                )

                if dry_run:
                    details.append({
                        "trade_id": trade_id,
                        "action": "would_update",
                        "old": {k: float(db_trade.get(k, 0) or 0) for k in update_data if k != "metadata"},
                        "new": {k: v for k, v in update_data.items() if k != "metadata"},
                    })
                    continue

                try:
                    self.db.table("trades").update(update_data).eq("id", trade_id).execute()
                    updated += 1
                    details.append({
                        "trade_id": trade_id,
                        "action": "updated",
                        "fields": list(update_data.keys()),
                    })
                except Exception:
                    self.log.exception("SMART RECONCILE UPDATE FAILED #%s", trade_id)
                    errors += 1
                    details.append({
                        "trade_id": trade_id,
                        "action": "update_failed",
                    })

            # DB rows that never matched any Delta round-trip: only mark DUPLICATE
            # when an exact twin exists (same entry, contracts, opened_at within 120s),
            # and this pair has more than one trade in that time window.
            unmatched_db = [t for t in db_list if t.get("id") not in used_db_ids]
            for db_trade in unmatched_db:
                trade_id = int(db_trade.get("id", 0) or 0)
                if trade_id <= 0:
                    continue

                if not self._should_mark_duplicate_unmatched(db_trade, db_list):
                    self.log.info(
                        "SKIP_DUPLICATE_TAG: trade #%s is unique",
                        trade_id,
                    )
                    details.append({
                        "trade_id": trade_id,
                        "pair": pair,
                        "action": "skipped_duplicate_rules",
                    })
                    continue

                ep = self._normalize_trade_price(
                    db_trade.get("entry_price", db_trade.get("price", 0)),
                )
                ct = self._normalize_trade_contracts(
                    db_trade.get("contracts", db_trade.get("amount", 0)),
                )
                opened = db_trade.get("opened_at")
                self.log.info(
                    "SMART RECONCILE%s: %s DUPLICATE_UNMATCHED trade_id=%s pair=%s "
                    "entry_price=%s contracts=%s opened_at=%s",
                    " [dry_run]" if dry_run else "",
                    "would mark" if dry_run else "marking",
                    trade_id,
                    pair,
                    ep,
                    ct,
                    opened,
                )

                details.append({
                    "trade_id": trade_id,
                    "pair": pair,
                    "action": "duplicate_unmatched_db_dry_run" if dry_run else "duplicate_unmatched_db",
                })
                if dry_run:
                    continue

                try:
                    self._mark_duplicate_trade(db_trade)
                    duplicates_marked += 1
                except Exception:
                    self.log.exception("SMART RECONCILE: failed to mark duplicate trade %s", trade_id)
                    errors += 1

            # Delta round-trips that never matched any DB row are missing ghosts.
            unmatched_delta = [rt for i, rt in enumerate(pair_rts) if i not in matched_rt_idx]
            for rt in unmatched_delta:
                details.append({
                    "pair": pair,
                    "action": "ghost_missing_in_db",
                    "delta_buy_time": rt.get("buy_time"),
                    "delta_entry": rt.get("entry"),
                })
                if dry_run:
                    continue
                try:
                    self._insert_ghost_trade(rt)
                    ghosts_inserted += 1
                except Exception:
                    self.log.exception("SMART RECONCILE: failed to insert ghost for %s", pair)
                    errors += 1

        return {
            "processed": processed,
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
            "duplicates_marked": duplicates_marked,
            "ghosts_inserted": ghosts_inserted,
            "dry_run": dry_run,
            "details": details,
        }

    @staticmethod
    def _normalize_trade_price(val: Any) -> float:
        return round(float(val or 0), 8)

    @staticmethod
    def _normalize_trade_contracts(val: Any) -> float:
        return round(float(val or 0), 8)

    @staticmethod
    def _parse_opened_at(val: Any) -> datetime | None:
        if val is None:
            return None
        if isinstance(val, datetime):
            dt = val
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        s = str(val).replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return None

    def _has_exact_duplicate_peer(
        self,
        db_trade: dict,
        db_list: list[dict],
    ) -> bool:
        """GPFC #44: Match only when another row shares the same exchange
        order_id. Strike+side+time-window matching generated false positives
        that killed real winners as DUPLICATE_UNMATCHED.
        """
        tid = db_trade.get("id")
        oid = str(db_trade.get("order_id") or "").strip()
        if not oid:
            return False
        for other in db_list:
            if other.get("id") == tid:
                continue
            o_oid = str(other.get("order_id") or "").strip()
            if o_oid and o_oid == oid:
                return True
        return False

    def _should_mark_duplicate_unmatched(
        self, db_trade: dict, db_list: list[dict],
    ) -> bool:
        """GPFC #44: only mark DUPLICATE_UNMATCHED when an exchange_fill_id
        (order_id) peer exists. If in doubt, log a WARNING and do NOT close.
        """
        if len(db_list) <= 1:
            return False
        if not self._has_exact_duplicate_peer(db_trade, db_list):
            self.log.warning(
                "SMART RECONCILE: trade #%s unmatched but has no order_id "
                "duplicate peer — letting normal exit logic handle it",
                db_trade.get("id"),
            )
            return False
        return True

    def _find_best_match(
        self, delta_rt: dict, db_list: list[dict]
    ) -> tuple[dict, float] | None:
        """Find the DB trade with closest opened_at to delta buy_time."""
        if not db_list:
            return None

        try:
            delta_dt = datetime.fromisoformat(str(delta_rt["buy_time"]).replace("Z", "+00:00"))
        except Exception:
            return None

        best: dict | None = None
        best_diff: float = float("inf")

        for db_trade in db_list:
            opened = db_trade.get("opened_at")
            if not opened:
                continue
            try:
                db_dt = datetime.fromisoformat(str(opened).replace("Z", "+00:00"))
            except Exception:
                continue

            diff = abs((db_dt - delta_dt).total_seconds())
            if diff < best_diff:
                best_diff = diff
                best = db_trade

        # Also verify entry price is within 1%
        if best and delta_rt["entry"] > 0:
            db_entry = float(best.get("entry_price", 0) or 0)
            if db_entry > 0:
                price_diff_pct = abs(db_entry - delta_rt["entry"]) / delta_rt["entry"] * 100
                if price_diff_pct > 1.0:
                    self.log.debug(
                        "Rejecting match for trade %s: entry price mismatch %.2f%%",
                        best["id"], price_diff_pct,
                    )
                    return None

        return (best, best_diff) if best else None

    def _build_update_data(self, db_trade: dict, delta_rt: dict) -> dict[str, Any]:
        """Build update dict only for fields that actually differ."""
        out: dict[str, Any] = {}
        mappings = {
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
        for key, new_val in mappings.items():
            old_val = db_trade.get(key)
            # Numeric tolerance
            if old_val is None:
                out[key] = new_val
            else:
                try:
                    diff = abs(float(old_val) - float(new_val))
                    if diff > 0.0001:
                        out[key] = new_val
                except Exception:
                    out[key] = new_val

        # Derive/repair exit_reason from pnl sign when missing or still UNKNOWN
        existing_exit_reason = str(db_trade.get("exit_reason") or "").strip().upper()
        if "exit_reason" not in out and (not existing_exit_reason or existing_exit_reason == "UNKNOWN"):
            if delta_rt["pct"] >= 20:
                out["exit_reason"] = "TP"
            elif delta_rt["pct"] <= -20:
                out["exit_reason"] = "OPT_SL"
            else:
                out["exit_reason"] = "RECONCILE"

        # Fix peak_pnl if entry was corrected
        if "entry_price" in out:
            exit_pnl_pct = delta_rt["pct"]
            if db_trade.get("status") == "closed" and exit_pnl_pct > 0:
                out["peak_pnl"] = round(exit_pnl_pct, 4)
            else:
                out["peak_pnl"] = 0

        return out

    # ──────────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────────

    @staticmethod
    def _get_asset(symbol: str) -> str:
        if symbol.startswith("C-") or symbol.startswith("P-"):
            parts = symbol.split("-")
            return parts[1] if len(parts) > 1 else "ETH"
        return symbol.split("/")[0] if "/" in symbol else symbol.replace("USD", "")

    @staticmethod
    def _get_option_type(symbol: str) -> str:
        if symbol.startswith("C-"):
            return "call"
        if symbol.startswith("P-"):
            return "put"
        if symbol.endswith("-C"):
            return "call"
        if symbol.endswith("-P"):
            return "put"
        return "call"

    def _empty_result(self) -> dict[str, Any]:
        return {
            "processed": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "duplicates_marked": 0,
            "ghosts_inserted": 0,
            "dry_run": True,
            "details": [],
        }

    def _mark_duplicate_trade(self, db_trade: dict) -> None:
        """Mark an unmatched DB row as duplicate/unmatched instead of deleting it."""
        trade_id = int(db_trade["id"])
        metadata = db_trade.get("metadata") or {}
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except Exception:
                metadata = {}
        metadata["duplicate_cleanup"] = {
            "reason": "unmatched_in_delta_reconcile",
            "marked_at": datetime.now(timezone.utc).isoformat(),
        }

        self.db.table("trades").update({
            "status": "cancelled",
            "exit_reason": "DUPLICATE",
            "reason": "smart_reconcile_cleanup",
            "closed_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata,
        }).eq("id", trade_id).execute()

    def _insert_ghost_trade(self, rt: dict) -> None:
        """Insert a closed trade row for a Delta round-trip missing in DB."""
        buy_time = rt.get("buy_time") or datetime.now(timezone.utc).isoformat()
        sell_time = rt.get("sell_time") or datetime.now(timezone.utc).isoformat()
        pct = float(rt.get("pct", 0) or 0)
        peak_pnl = round(pct, 4) if pct > 0 else 0

        row = {
            "pair": rt["pair"],
            "exchange": "delta",
            "strategy": "options_scalp",
            "side": "buy",
            "entry_price": float(rt["entry"]),
            "exit_price": float(rt["exit"]),
            "contracts": float(rt["qty"]),
            "leverage": 50,
            "gross_pnl": float(rt["gross"]),
            "net_pnl": float(rt["net"]),
            "pnl": float(rt["net"]),
            "pnl_pct": pct,
            "peak_pnl": peak_pnl,
            "entry_fee": float(rt["efee"]),
            "exit_fee": float(rt["xfee"]),
            "status": "closed",
            "exit_reason": "GONE",
            "reason": "smart_reconcile_insert_missing",
            "setup_type": "MOM_BURST",
            "opened_at": buy_time,
            "closed_at": sell_time,
            "metadata": {
                "reconciled_at": datetime.now(timezone.utc).isoformat(),
                "ghost_inserted": True,
            },
        }
        self.db.table("trades").insert(row).execute()

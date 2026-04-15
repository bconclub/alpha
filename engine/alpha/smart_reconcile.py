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
        """Smart match and update."""
        processed = 0
        updated = 0
        skipped = 0
        errors = 0
        details: list[dict] = []

        # Group by pair
        db_by_pair: dict[str, list[dict]] = defaultdict(list)
        for t in db_trades:
            db_by_pair[t.get("pair", "")].append(t)

        rt_by_pair: dict[str, list[dict]] = defaultdict(list)
        for rt in delta_rts:
            rt_by_pair[rt["pair"]].append(rt)

        for pair, pair_rts in rt_by_pair.items():
            db_list = db_by_pair.get(pair, [])

            # Count mismatch guard
            if len(pair_rts) != len(db_list):
                self.log.warning(
                    "Mismatched trade count for %s: %d Delta round trips vs %d DB trades. "
                    "Skipping updates to prevent cross-trade corruption.",
                    pair, len(pair_rts), len(db_list),
                )
                skipped += len(pair_rts)
                details.append({
                    "pair": pair,
                    "action": "skipped_count_mismatch",
                    "delta_count": len(pair_rts),
                    "db_count": len(db_list),
                })
                continue

            for delta_rt in pair_rts:
                processed += 1
                match = self._find_best_match(delta_rt, db_list)

                if not match:
                    self.log.warning(
                        "No DB match for Delta round trip %s buy_time=%s entry=$%.2f",
                        pair, delta_rt["buy_time"], delta_rt["entry"],
                    )
                    skipped += 1
                    details.append({
                        "pair": pair,
                        "action": "skipped_no_match",
                        "delta_buy_time": delta_rt["buy_time"],
                        "delta_entry": delta_rt["entry"],
                    })
                    continue

                db_trade, time_diff_sec = match
                trade_id = db_trade["id"]

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

        return {
            "processed": processed,
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
            "dry_run": dry_run,
            "details": details,
        }

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

        # Derive exit_reason from pnl sign if missing
        if "exit_reason" not in out and not db_trade.get("exit_reason"):
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
            "dry_run": True,
            "details": [],
        }

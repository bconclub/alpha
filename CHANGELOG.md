# Changelog

## 2026-05-15 · GPFC #76: ghost-proof trade lifecycle — strict write/update, real exit labels, pre-expiry close

- `options_scalp.py` (`_write_entry_to_db`): Added GPFC #76 fill-confirmation gate — trade INSERT now aborted if any of: order_id missing, fill_price=0, contracts=0, entry_path unset
- `options_scalp.py` (`_handle_position_gone`): Replaced catch-all "GONE"/"EXPIRY" labels with specific: EXPIRED_ITM, EXPIRED_OTM, TICKER_DROPOUT, RECONCILE_GONE; label computed after premium so ITM/OTM split is accurate
- `options_scalp.py` (`check`): Added PRE_EXPIRY_FORCE pre-emptive close 5 minutes before contract expiry — fires market exit before Delta can settle silently and create a ghost row
- `trade_executor.py`: Changed executor reconcile path exit_reason POSITION_GONE → RECONCILE_GONE
- `SupabaseProvider.tsx`: Added `isGhostTrade()` helper; applied at all 4 trade load/set sites — hides $0 POSITION_GONE/RECONCILE_GONE rows and auto_closed_stale rows from UI (rows remain in DB for audit)
- **DB cleanup (Part 5)**: Deleted 103 existing ghost rows (POSITION_GONE/GONE with pnl=0); 0 stale open trades found
- User-facing: trades table no longer shows 103 ghost rows; future ghost creation blocked at INSERT level

## 2026-05-15 · GPFC #75: breathing room — trust conf gate, exit only on real signals

- `options_scalp.py` (`OPT_TRAIL_TIERS`): Widened all trail tiers; first tier 4%→10% activation, 1%→5% lock. Removed lowest two micro-tiers, now 7 tiers total
- `options_scalp.py` (`PULLBACK_ACTIVATE_PCT`): Raised 4.0 → 10.0; PEAK exit now arms only at peak ≥ 10%
- `options_scalp.py` (`_check_option_exit`): Added explicit guard `if peak_pnl_pct < 10.0: return []` before PEAK/BREAKEVEN block — no soft exits below 10% peak (SL and DEAD still fire normally)
- User-facing: trades now have breathing room up to 10% peak before any pullback/trail/breakeven exit can fire; reduces premature chops on conf-gated entries

## 2026-05-15 · GPFC #74 FIX: remove await from sync on_fill_fallback, use cached ticker

- `options_scalp.py`: Added `self._last_option_ticker` attribute in `__init__` (initialized to `None`)
- `options_scalp.py` (`_execute_breakout_entry`): Cache `_pre_ticker` into `self._last_option_ticker` immediately after the pre-entry fetch
- `options_scalp.py` (`_check_option_exit`): Cache `ticker` into `self._last_option_ticker` after each clean (non-absurd) tick
- `options_scalp.py` (`on_fill`): Replaced the `await self.options_exchange.fetch_ticker()` call inside the sync `on_fill_fallback` path with `self._last_option_ticker`; if cache is cold, logs a warning and skips metadata without crashing
- User-facing: bot no longer crashes on import with "await outside async function"; on_fill_fallback writes DB row without confidence when ticker cache is cold rather than raising `SyntaxError`
- Fixes deploy blocker introduced in GPFC #74 (commit 90dfd69)

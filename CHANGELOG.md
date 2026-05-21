# Changelog

## 2026-05-21 · GPFC #79.2: dashboard two-pill exit display

- `dashboard/lib/exitReason.ts` (new): added `parseExitReason()` parser that splits `stop_phase_a` / `trail_phase_c` into `{primary: "STOP"|"TRAIL", phase: "A"-"E"}` and `exitReasonColor()` color keyword helper
- `dashboard/components/ui/ExitChip.tsx`: refactored to render two pills for phased exits (primary action + neutral mono phase letter), single pill for breakeven/dead/pre-expiry/expired_itm/expired_otm/etc., backward-compat for legacy uppercase rows (TRAIL/PEAK/GONE/EXPIRY/…)
- User-facing: trade rows in `/trades` and any other ExitChip site now show e.g. `[STOP] [A]` two-pill instead of literal `STOP_PHASE_A`; legacy trades still render normally

## 2026-05-21 · GPFC #79: tighten backstops, kill old STOP, gate third SQUEEZE entry, proper exit names

- `options_scalp.py`: tightened phase-B SL (-8→-5), phase-C SL (-15→-8); added explicit `PHASE_D_SL_PCT` / `PHASE_E_SL_PCT` (-8 each)
- `options_scalp.py` (exit ladder): per-phase SL via dict (`{C/D/E: ...}`) instead of using `PHASE_C_SL_PCT` for all C/D/E
- `options_scalp.py`: all exit_reason strings migrated to lowercase snake_case (`stop_phase_a`, `trail_phase_c`, `breakeven`, `dead`, `pre_expiry`, `expired_itm`, `expired_otm`, `expired_worthless`, `ticker_dropout`, `reconcile_gone`)
- `options_scalp.py`: added module-level `EXIT_REASON_DISPLAY` map + `format_exit_reason()` helper for human-readable rendering
- `options_scalp.py` (`_execute_breakout_entry`): added 3rd-path confidence gate immediately after `_build_entry_metadata`, before order placement — closes the SQUEEZE-execution bypass (detection-time gate could pass on stale conditions)
- User-facing: every order placement now re-checks `confidence >= 60`; ugly raw exit reasons (`STOP_PHASE_A`) now stored as `stop_phase_a` and displayed as "Stop Phase A"

## 2026-05-21 · GPFC #78: regime-switching exit by peak (phases A-E)

- `options_scalp.py`: added phase constants (PHASE_A through PHASE_E) for peak-based exit regimes
- `options_scalp.py`: added 3 helper methods — `_current_phase`, `_phase_trail_floor`, `_underlying_turned_against`
- `options_scalp.py`: added `_peak_pnl_pct` / `_current_pnl_pct` instance attrs (live-set each exit tick)
- `options_scalp.py` (`_check_option_exit`): replaced OPT_HARD_SL + OPT_TRAIL (tier ladder) + OPT_PEAK_TRAIL pullback + OPT_BREAKEVEN_STOP with a single phase-based ladder. DEAD detector preserved (peak ≤ 3% + premium ≤ -8% + underlying turned against)
- Phase ladder:
  - A (peak < 3%): -3% SL only
  - B (peak 3-9%): breakeven exit when retrace to ≤ +0.5% AND peak ≥ 3%; -8% SL backstop
  - C (peak 9-15%): trail at 45% of peak; -15% catastrophic SL
  - D (peak 15-50%): trail at 60% of peak
  - E (peak ≥ 50%): trail at 75% of peak (moonshots)
- User-facing: exit reasons now include STOP_PHASE_A, STOP_PHASE_B, BREAKEVEN, TRAIL_PHASE_C/D/E, STOP_PHASE_C/D/E. Old TRAIL / OPT_PEAK / OPT_BREAKEVEN_STOP exits gone

## 2026-05-19 · GPFC #77: kill ghost-insert feature in reconciler — root cause of phantom rows

- `smart_reconcile.py` (`_insert_ghost_trade`): gutted body, now logs warning only — no INSERT
- `reconcile.py` (line ~497): replaced try-insert block with warning log only — no INSERT
- `main.py` (scheduler): commented out hourly `_run_reconciliation` job. Reconciler still callable manually via "reconcile" / "smart_reconcile" CLI commands
- `trade_executor.py` (`_open_trade_in_db`): defense-in-depth — refuses INSERT when `order.id` is null
- `trade_executor.py` (`_close_trade_in_db` fallback): same guard on the legacy "standalone closed row" insert path
- User-facing: phantom rows can no longer be created by the auto-reconciler; even bypass paths get rejected at the executor

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

# Changelog

## 2026-06-06 · Widen the paper options grid + earlier wave trail

- `paper_options.py`: early read showed slow ride-the-wave lanes (5m) winning (50–77% peaks) while fast 1m momentum loses. Acting on it:
  - `TRAIL_ARM_PCT` 40 → **18** (+ retrace 0.50 → 0.45) so mid-size peaks (17–29%) stop giving it all back.
  - Per-lane config overrides (setup label / trail_arm / otm_steps) on the base runner.
  - Grid expanded 4 → **8 lanes**: Trend Ride (ATM + OTM), Donchian (ATM + OTM), EMA Pullback, **Trend Runner** (trail arms at +35% to capture moonshots), Momentum (control), and new **Mean Revert** (RSI<30 buy call / RSI>70 buy put — counter-trend test).
- `dashboard/app/paper/page.tsx`: labels for the new lanes.
- User-facing: the paper lab now runs more strategy × moneyness combinations per asset, riding winners earlier. More free data toward a real strategy. `(SHA on commit)`

## 2026-06-06 · Paper Lab dashboard: Options + Futures in one view

- `dashboard/app/paper/page.tsx`: rebuilt as **Paper Lab** with an Options/Futures toggle. Normalizes both ledgers into one view; Options shows premium entry/mark, strike + moneyness, stake, CALL/PUT; Futures shows leverage/margin. Per-instrument $100 balance, win-rate/peak/return stats, Setup Edge / Moneyness(or Leverage) / Pair-Direction panels, exit-reason breakdown.
- `dashboard/app/api/paper-futures/route.ts`: now returns both `options` (paper_options_trades) and `futures` (paper_futures_trades) plus bot status; paperAccountUsd 50 → 100.
- User-facing: `/paper` now shows the BTC/ETH options AND futures labs side by side with one click. `(SHA on commit)`

## 2026-06-06 · Paper OPTIONS lab (buy-only, ride-the-wave) + BTC/ETH-only paper @ $100

- `engine/alpha/paper_options.py` (new): buy-only paper options lab. Reads the REAL Delta option chain + live premiums for BTC/ETH, picks ATM (or 1-step OTM on strong moves), "buys" a call (up) or put (down) on a genuine underlying price-action move, then **rides the wave** — holds through premium noise while the underlying structure supports the trade, exits on underlying reversal / hard −45% premium stop / big-run trail / pre-expiry. **No time-based decision gates** (no min-hold, no cooldown). 4 lanes: OPT_TREND_RIDE, OPT_DONCHIAN, OPT_MOMENTUM, OPT_EMA_PULLBACK. Writes `paper_options_trades` with confidence + greeks + price-action context.
- `db.py`: `log_paper_options_trade` / `update_paper_options_trade` (+ 5-min backoff if the table is missing), `TABLE_PAPER_OPTIONS`.
- `main.py`: paper lab is now **BTC + ETH only** (was top-5 volume). Builds + starts both paper futures and paper options lanes on BTC/ETH; wired into shutdown/pause/resume/toggle. `resume` in PAPER-ONLY mode restarts only the paper lab and keeps live off.
- `paper_futures.py`: paper account **$50 → $100**.
- User-facing: the paper lab now runs BTC/ETH futures AND options side by side on a $100 paper account, aggressively, riding moves — all with no real money. Dashboard rebuild next.
- (SHA on commit)

## 2026-06-05 23:55 IST · PAPER-ONLY mode: live trading disabled (durable)

- **Live bot paused** via `bot_commands` (id 314) — stops the real-money bleed immediately.
- `main.py`: new `self.paper_only` flag (env `PAPER_ONLY`, **defaults ON**). When on: live options strategies are never built, and `risk_manager.is_paused` is forced True at startup so **no live entry can fire — durable across the ~21 restarts/day** (an in-memory pause alone would be wiped by a crash-restart). Paper lanes ignore the flag and keep running.
- `supabase/migrations/20260605_create_paper_options_trades.sql` (new, applied): `paper_options_trades` table — buy-only price-action paper options ledger (premium-based, $100 account), parallel to `paper_futures_trades` so the dashboard can show which row is an OPTION vs a FUTURE.
- Rationale: 1,396 live option trades show no edge in ANY slice (97% taken in CHOPPY regime, every hold-bucket negative, even quality-gated trades lose). Stop risking real money; rebuild + prove edge in paper first.
- User-facing: live trading is OFF. Next: paper options engine (BTC/ETH), paper futures restricted to BTC/ETH @ $100, and a paper-first dashboard.
- (SHA on commit)

## 2026-06-05 17:55 IST · Stop the bleed: always-on hard stop + non-underwater entries

- `engine/STRATEGY.md` (new): compiled price-action strategy — buy-only, ~$29 account, one entry engine, structural exits, premium-dip re-entry, all time-gates to be stripped, dynamic ATM→slightly-OTM strike selection. No option selling, no paper-futures focus. This is the reference we build against.
- `options_scalp.py` `PHASE_A_EMERGENCY_SL_PCT`: −50% → **−15%**. The −50% warmup backstop was letting noise-level dips free-fall to −16/−24% market fills (today: trades 3682 −24%, 3683 −21%, 3687 −17%). −15% is now the universal warmup floor.
- `options_scalp.py` `PHASE_A_DYNAMIC_HARD_FAIL_PCT`: −12% → **−8%**. Never-worked trades (peak ≤3%) now cut at −8% observed, so market-order slippage on illiquid Delta strikes lands near −12% instead of −24%.
- `options_scalp.py` `FAST_ENTRY_LIMIT_CROSS_PCT`: 8% → **4%**. Crossing the ask by 8% made entries start deep underwater (trade 3671: −22% in 0 min). Now we pay up only modestly.
- `options_scalp.py` `EXPLOSIVE_MOVE_MAX_SPREAD_PCT`: 18% → **9%**. Tolerating 18%-wide spreads was the direct source of the −24% slippage; spread/liquidity is the hard entry gate.
- User-facing: live options trades should stop producing −20%+ losses on trades that never worked; entries no longer start instantly deep in the red. Surgical bleed-stop ahead of the full structural exit rewrite. `(a9495db)`

- `options_scalp.py`: `ENABLED_SETUPS = {"MOM_BURST", "SQUEEZE"}` — SQUEEZE re-enabled
- `options_scalp.py`: added IV-regime constants — `SQUEEZE_MAX_IV_FOR_ENTRY = 0.35`, `MOM_BURST_MIN_IV_FOR_ENTRY = 0.25`, `SQUEEZE_REQUIRES_LOW_VOL = True`
- `options_scalp.py`: added `_extract_iv(ticker)` helper — reads `info.mark_vol` as decimal, returns `None` on missing/unparseable
- `options_scalp.py` (`_check_momentum_burst_entry`): blocks MOM_BURST when IV < 0.25 (SQUEEZE regime — let SQUEEZE handle it)
- `options_scalp.py` (`_handle_squeeze_breakout`): blocks SQUEEZE when IV > 0.35 (MOM_BURST regime — breakout already priced in)
- Kept GPFC #81's conf=aligned_mom score and all #78/#79/#80 phase exits untouched
- User-facing: SQUEEZE entries can start firing again, but only in low-vol windows; MOM_BURST only fires when vol is meaningful. Two setups become mutually-exclusive by regime

## 2026-05-21 · GPFC #81: MOM_BURST only, conf=aligned_mom (drop SQUEEZE + 5 noisy components)

- `options_scalp.py`: added `ENABLED_SETUPS: frozenset = frozenset({"MOM_BURST"})` class constant — SQUEEZE entries now disabled at config level
- `options_scalp.py` (`_handle_squeeze_breakout`): short-circuit at the top of the function when SQUEEZE is not in ENABLED_SETUPS (throttled log every 30 ticks); no SQUEEZE entry can ever queue
- `options_scalp.py` (`_execute_breakout_entry`): belt-and-suspenders gate — refuses to fire if resolved `setup_type not in ENABLED_SETUPS`, resets breakout state
- `options_scalp.py` (`_calculate_confidence`): score collapsed to `aligned_mom` only. The 6-component breakdown is still computed and stored in `trades.metadata.confidence_breakdown` for observation, but only aligned_mom drives the gate
- `options_scalp.py` (`on_start`): emit `[CONFIDENCE] GPFC #81 model:` banner at startup with active setups
- User-facing: zero new SQUEEZE rows going forward; confidence threshold of 60 now maps to ~0.60% aligned 60s underlying momentum (top tercile historically). Expect right-tail rate 17-22%

## 2026-05-21 · GPFC #80: Phase A/B SL requires underlying momentum confirmation

- `options_scalp.py`: added constants `PHASE_A_SPOT_FAVORABLE_BPS = 0.05` (%, not bps) and `PHASE_A_SPOT_LOOKBACK_SEC = 30`
- `options_scalp.py`: added 3 helpers — `_get_spot_price_at(seconds_ago)` (uses existing `_momentum_price_history`), `_underlying_still_favorable(lookback, threshold)` returning True if spot has moved in our trade direction by ≥threshold over the lookback window, and `_persist_sl_defer_count()` async writer to `trades.metadata.sl_deferred_count`
- `options_scalp.py`: added `_sl_defer_count` instance attr (reset on entry, incremented each defer)
- `options_scalp.py` (exit ladder): Phase A SL now defers when spot is still favorable (logs `stop_phase_a DEFERRED`); fires only when spot turns or goes flat. Phase B -5% SL backstop gets the same momentum-confirmation rule. Phase C/D/E SL backstops unchanged (catastrophic gap, immediate exit)
- User-facing: bot no longer cuts on noise-level premium dips when underlying is still pushing in our favor; defers per trade are persisted to metadata for analysis

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

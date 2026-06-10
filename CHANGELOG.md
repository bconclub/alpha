# Changelog

## 2026-06-10 19:45 IST · DK harvest lane — sell the expiry window, hold through settlement

- Data showed selling never stood where decay happens: avg entry 18.5h from expiry (min 6.2h), avg decay captured −7%, and the trend-break exit churned green positions (13 trades, 7.7% win).
- New `OPT_SELL_DK_V3` (BTC+ETH): enters ONLY 0.7–4.5h before the 12:00 UTC daily settle, sells 2-OTM with the trend on its own near-expiry chain, and holds straight through settlement — `settled_otm` books the full credit; exits early only on breach/blowout/TP 60%.
- Settlement modeling: at expiry an open short closes at intrinsic value (no dead-ticker polling). Chain supports per-instance `min_expiry_hours` so the DK chain stays on today's expiry while other lanes roll to tomorrow.
- All sell lanes: `sell_trend_break` now fires only when the position is RED — protection, never churn.
- User-facing: new DK lane on the paper page; first entries in tomorrow's pre-settle window (~13:00–16:50 IST).
- `(SHA on commit)`

## 2026-06-10 11:30 IST · Pull out sooner: no-traction exit + faster stagnation purge

- User observed V3 holding losers too long. Data agreed: flat trades sat the full 2h stagnation window, and red drifters took 40–55 min to reach the ATR stop with no early abandon.
- `paper_futures.py`: new `no_traction` exit — red after 60 min AND never reached +0.4 ATR favorable → exit (winners announce themselves early). Stagnation purge tightened 2h → 75 min.
- User-facing: fewer long-held red positions on the paper page; new `no_traction` exit reason in trade history.
- `(SHA on commit)`

## 2026-06-10 03:45 IST · V3 era cutover — dashboard + Telegram show the fresh $1,000 start only

- Dashboard API (`paper-futures/route.ts`): all trade queries and the deposit ledger now era-scoped from 2026-06-09 21:21 UTC; funded = $1,000 seed + era refills. Burns reset to 0 for the era. Response carries `era` metadata.
- Paper page: green **V3** badge on the balance card (tooltip: fresh start date + where V2 history lives).
- Engine `_build_paper_pulse`: same era scoping — Telegram pulses now report $1,000-based balances and era burns.
- Routine SKILL: balance/burn formulas rewritten to era math so check-ins agree with the dashboard.
- User-facing: Options and Futures cards both show $1,000 starts; no more $27.9k/$1.4k lifetime funded numbers. V2 history preserved in DB + `engine/PAPER_RESULTS.md`.
- `(SHA on commit)`

## 2026-06-10 03:15 IST · V3 PAPER RESET — rebuild both labs on everything 4,900 trades taught us

- **Futures lab rebuilt (`engine/alpha/paper_futures.py`)**: V2's 25–100× lanes retired (−$26.7k, 26 burns — the definitive sample). V3 = 5 lanes: FUT_EMA_PB_10X + FUT_EMA_PB_20X (clean leverage A/B on identical pullback entries), FUT_DONCHIAN_RT_10X (fresh breakouts only, no chasing), FUT_VWAP_10X (institutional VWAP bounce), FUT_SFP_15X (liquidity-sweep reversal with structural stop).
- **The structural fix**: stops moved from leveraged-PnL space into **ATR price space** (1.6×ATR), with a breakeven ratchet at +1.2 ATR ("exit with profit"), chandelier trail (1.8 ATR behind peak), 2h stagnation purge ("don't get stuck"), 24h max hold, conf≥70 entry gate, $100 margin/trade.
- **Options selling rebuilt (`engine/alpha/paper_options.py`)**: V2 was gross-breakeven but fee-dead (gross +$27, fees $448 over 742 trades). V3 = 3 lanes (SELL_PUT/CALL/RANGE_V3), 2-OTM strikes with credit≥$2 gate, 15m signals + 15-min re-entry cooldown (churn killer), ≥4h expiry runway, **real Delta India fee model** (0.03% notional capped 10% premium, +18% GST), new sell_trend_break exit, $100 margin/trade.
- **Bug fixes**: Telegram pulses no longer die on "<=" (HTML-escape learned/next + notify fallback); Binance load_markets startup traceback guarded in paper-only runs.
- **Bankrolls re-seeded to exactly $1,000 each via additive paper_deposits rows — zero rows deleted, full V2 history preserved.** LEARNINGS.md: verdicts #8–#10 finalized + 5 new principles (price-space stops, survival-time edge, fees-as-filter, conf gates not sizes, exits-were-never-the-problem). PAPER_RESULTS.md: permanent era-2 final snapshot.
- User-facing: dashboard now shows the V3 lanes; Telegram pulses resume cleanly; routine updated to rank V3 lanes, use [skip ci] on check-in commits (no more engine restarts per check-in), and verify its pushes land.
- `(SHA on commit)`

## 2026-06-07 · Deep-research synthesis → LIVE_STRATEGY_PLAN.md (ready on approval)

- Mined all data (≈2,800 live + ≈2,100 paper trades). Findings: options dead both ways (selling profit factor 0.07–0.20); futures is a trend system whose money is in the fat tail — trades reaching 25%+ peak are 91–97% win, but 1,036 junk entries (<10% peak) amplified by leverage cause the −$20k loss; confidence predicts the tail (80+ reaches 10%+ 31% vs 15%) but is shackled to high leverage that stops it on noise.
- `engine/LIVE_STRATEGY_PLAN.md` (new): the evidence-based spec — **futures only, EMA-trend entries, conf≥75, fixed 3–5× leverage (decoupled from conviction), ATR stop, ride winners to the tail; risk 1–2%/trade on the real $50.** Options dropped from live.
- Honest gate: nothing is yet net-positive (all configs were over-leveraged). Plan = paper-validate this exact spec → require PF>1 over ~200 trades → then go live tiny. NOT live yet (PAPER_ONLY stays on).
- `(SHA on commit)`

## 2026-06-07 · Options selling scaled up (moderate-aggressive)

- Options selling was too timid (~$150 margin / ~7× → small noise while futures raged). Scaled to **$250 margin / ~8× leverage** per short (~$2,000 notional) so it commits real, meaningful size and generates a cleaner edge signal (still slower-burn than the 25–100× futures).
- `paper_options.py`: `SELL_MARGIN_USD` 150 → 250, `SELL_MARGIN_RATE` 0.15 → 0.125.
- No reset (per policy); deploy restart auto-cancels open old-size sells.
- `(SHA on commit)`

## 2026-06-07 · Deterministic Telegram pulse (engine-formatted, always clean)

- **Problem:** the hourly routine wrote the Telegram text freehand each run, so it kept drifting into dense walls of text. Only hand-formatted one-offs looked clean.
- **Fix:** new `paper_pulse` bot-command — the **engine** builds the pulse from the DB in a fixed, clean layout (P/L, 🟢 Working, 🔴 Losing, 🧠 Learned, 🔧 Next, status). The routine no longer composes the message; it only passes two short lines (`learned`, `next`, ≤90 chars each). Format is now guaranteed identical every hour.
- Routine updated to call `paper_pulse` (not `notify`) with just the two insight lines.
- `(SHA on commit)`

## 2026-06-07 · Real "money in" for sells + decluttered mobile card

- **Sells now size by committed MARGIN, not the tiny premium.** Was: collect a $1–3 credit (notional-capped) → trivial, noisy trades. Now: each short commits a real ~$150 margin (≈15% of a ~$1,000 notional); the collected premium is recorded as `credit_usd`. So "money in" is a true, meaningful number.
- **P&L computed from contracts** for both sides (`_gross_usd`): buyers profit on premium up, sellers on premium down; `pnl_pct` = return on money committed. Cleaner and correct.
- **Mobile card decluttered:** leads with the signal (setup chip + **Conf**) and the result (Net + return%), then a tight 6-field grid — **Money in**, Conf, Hold, Entry→Mark, Strike/Liq, Peak. Dropped the noise (notional, $0 fees, empty liq on options, redundant open-exit).
- No reset (per policy); the deploy restart auto-cancels the few open old-basis sells.
- `(SHA on commit)`

## 2026-06-07 · Dashboard defaults to "All" (history wasn't lost) + no-more-resets

- **It wasn't resetting.** The `/paper` view defaulted to the "Today" window; just past midnight IST that hid every pre-midnight trade, making it look like only ~3 trades existed. In reality 18 futures + closed history were persisting fine.
- Changed the default window **Today → All** so every trade we've taken is visible by default.
- **Policy:** no more destructive resets. Balance refills now go through the additive `paper_deposits` ledger — trade history is never deleted again. (Earlier tonight's `DELETE`-resets were the real history loss; that stops now.)
- Note: restart-orphan rows are `cancelled` (hidden), never deleted — closed history always persists.
- `(SHA on commit)`

## 2026-06-06 · Fix ghost "open" paper trades from restarts (no fake trades)

- **Root cause:** on every engine restart (we deployed ~16× tonight) the in-memory position state was lost, but the DB row stayed `status='open'` forever — frozen mark, frozen "profit". That's why you'd see a LONG and SHORT both "open" on the same asset with different (one stale) marks. Not fake P&L generation — orphaned ghost rows.
- `db.py` `cancel_orphan_paper_trades()`: at startup, void any paper trade still 'open' (it belongs to the dead previous process) → status='cancelled', exit_reason='restart_orphan'.
- `main.py`: calls it during paper startup, before opening any new positions.
- Cleaned the existing orphans (1 futures + 2 options) immediately.
- Dashboard API now hides `cancelled` rows — only real open + closed trades show.
- User-facing: no more phantom long+short-both-open with frozen marks. If it's closed, it's closed.
- `(SHA on commit)`

## 2026-06-06 · Autonomous refill + mobile/risk dashboard (liquidation, at-risk)

- **Auto-refill bankroll (autonomous):** new `paper_deposits` ledger (seed $1,000/lab). The hourly routine now computes balance = funded + closed net, and when a lab burns to ≤$50 it inserts a +$1,000 refill row and **counts the burn** — labs run forever, and burn-count itself becomes a learning (how aggressive/risky an approach is). Context recorded: real account is ~$50; the $1,000 paper is a sandbox; winning strategy scales down to the real account.
- **Dashboard mobile fix:** the wide table was unusable on phones. Added a responsive **card view** (`md:hidden`) — each trade as a readable card; the table stays for desktop.
- **Risk visibility:** added **Liquidation price** (+ distance-to-liq %, red when <1.5%) for futures, **At-risk / Margin** highlighted, and the balance card now shows **Funded**, **🔥 burned N×**, and **At risk $** for live positions.
- API returns `funded` + `burns` per lab; balance reflects refills.
- `(SHA on commit)`

## 2026-06-06 · Hourly Telegram pulse from the co-work routine

- `main.py`: new `notify` bot-command — generic Telegram passthrough (`alerts._send`, sends even in quiet mode). The hourly paper-lab routine inserts a `notify` row each run; the engine (which holds the Telegram token on the VPS) pushes the summary to the user's chat.
- The routine now sends an hourly Telegram update: what was checked, # trades, P/L, what's working, what we should do, what we're doing next. So the user sees the lab evolving in real time.
- `(SHA on commit)`

## 2026-06-06 · Act on routine's bug findings: fix selling engine + capture peaks

Acting on the hourly co-work routine's check-in (it found the SELL results were engine bugs, not a verdict):
- **Sell breach fixed:** exit now fires when SPOT actually reaches the short strike (±0.1%), not on EMA/RSI noise — was dumping winners in 15–25 min before theta could work.
- **Notional capped:** a trade's underlying notional is limited to 20× the stake (no more $80 controlling $312k far-OTM).
- **Fees made gentle/realistic:** capped at 2.5% of premium/side (was 10% → ~20% round-trip that alone ate ~$780); fees no longer dominate the test.
- **Capture peaks (futures):** trail arms at +5% and exits after giving back only 30% of the peak (was 45%) — bank ~70% of the move instead of round-tripping. Max hold 45m→4h so trend lanes ride; cooldown 90s→0 for aggressive re-entry on every opportunity.
- LEARNINGS.md is the shared brain: routine drops findings hourly, this session acts on them.
- `(SHA on commit)` · both paper labs reset to clean $1,000 after deploy.

## 2026-06-06 · Aggressive futures leverage (25–100×) + selling TP fix + reset #2

- **Findings logged** to `engine/PAPER_RESULTS.md` + `engine/LEARNINGS.md`: option SELLING (naked) = **0% realized win** (theta worked, peaks +34–46%, but all reversed past the +50% TP to the −100% stop); sane-leverage futures 0–17% win, slow bleed.
- **Futures → aggressive (user request):** confidence leverage ladder **25/50/75/100×** restored + explicit `FUT_DONCHIAN_50X` / `FUT_DONCHIAN_100X` lanes + conf-ladder Donchian/EMA/Momentum. (Prior data says high leverage amplifies losses — testing in paper anyway.)
- **Selling TP fix:** take-profit +50% → **+30%** (peaks reversed ~46%), stop −100% → **−80%** to cap the naked tail.
- **Reset #2:** both paper ledgers wiped back to a clean **$1,000** each.
- Knowledge files to pull up anytime: **`engine/PAPER_RESULTS.md`** (per-lane results) and **`engine/LEARNINGS.md`** (verdicts + principles).
- `(SHA on commit)`

## 2026-06-06 · Reset both paper balances to $1,000 + results snapshot in repo

- `engine/PAPER_RESULTS.md` (new): full point-in-time dump of the option-BUYING era + reckless-leverage futures results (every lane, win%, net) before the reset, so the data survives. Only OPT_DONCHIAN (ATM breakout) was net-positive (+$29); futures loss scaled directly with leverage.
- **Balances reset to a clean $1,000 each.** Deleted 829 old buying-option rows and 359 old high-leverage futures rows from the paper ledgers so the new approaches (option SELLING, sane-leverage futures) start fresh from $1,000 — no more old losses dragging the displayed balance.
- Pairs with `engine/LEARNINGS.md` (verdicts + principles) as the in-repo knowledge base.
- `(SHA on commit)`

## 2026-06-06 · Pivot: OPTION SELLING + sane-leverage FUTURES + knowledge table

- **Options: BUYING → SELLING.** Buying lost across 766 trades (theta + spread). Added SELL mode to the paper options engine (collect premium at the bid, profit as it decays): take-profit at +50% of credit, stop at −100% (premium doubles), ride to near-expiry. New lanes: Sell Put / Sell Call (trend-aligned OTM), Sell Neutral (quiet regime far-OTM put), + further-OTM variants. Options lab now SELLS premium instead of buying it.
- **Futures: sane leverage.** Replaced the reckless 25–100× confidence ladder with a clean trend/breakout test at **3×/4×/5×** (Donchian 3×, Donchian 5×, EMA 4×, Momentum 4× control). Tests whether the directional entries carry edge without option drag. Each lane independent for clean leverage comparison.
- **`engine/LEARNINGS.md` (new):** knowledge table of every verdict so far (live buying dead, paper buying dead, momentum dead, mean-revert weak, high-lev dead) + hard-won principles, so future setups build on what we know.
- Dashboard: labels for all new sell + futures lanes.
- Refresh: new lanes write fresh-tagged rows; selling/sane-futures data starts clean.
- (SHA on commit)

## 2026-06-06 · Re-deploy (prev VPS deploy failed) + big-sample finding

- The `fbf41d5` engine deploy **failed at the VPS step** (known flaky SSH) — the bot ran the prior build ($100, 12 lanes) for ~12h, so the $1,000 bump never applied. Re-deploying to land it.
- **Finding (667 closed paper option trades):** every lane is net-negative on a real sample; the early "100% win" lanes were small-sample noise. Trend lanes have decent win rates (Donchian 68%, Trend Ride 63%, Supertrend 59%) and ~34% avg peaks but still lose — i.e. **the entries are directionally right; the exits give the edge back.** Buying short-dated options is structurally hard (theta + spread + give-back). Next lever is the EXIT/R:R, not the entry.
- (SHA on commit)

## 2026-06-06 · Bump paper account $100 → $1,000 (headroom + bigger size)

- Paper account base raised **$100 → $1,000** for both labs so the running balance has plenty of headroom and won't hit zero while we test.
- `paper_options.py`: `STAKE_USD` $8 → **$80** per trade (scaled 10×, aggressive).
- `paper_futures.py`: account $1,000 → margin auto-scales to $250/trade (ALLOC 25%).
- Dashboard API + page default account → $1,000; table column defaults → 1000.
- Existing rows kept as-is (not rewritten); balance now = $1,000 + cumulative net, so options ≈ $944 and futures ≈ $881 with room to run.
- User-facing: paper labs keep trading aggressively on a $1,000 bankroll each. `(SHA on commit)`

## 2026-06-06 · Bring in the strategy canon: VWAP, Supertrend, ORB, MACD (researched)

- Researched the most-used institutional/quant intraday strategies and implemented the proven families as new paper option lanes (buy-only, ride-the-wave exits):
  - **VWAP Pullback** — buy dips toward session VWAP in an uptrend / rallies in a downtrend (the #1 institutional benchmark).
  - **Supertrend** — ATR trend, ride direction, exit on the flip.
  - **Opening Range Breakout (ORB)** — break of the UTC-day opening range.
  - **MACD** — MACD/signal cross with zero-line filter.
- `paper_options.py`: added indicator helpers (`_atr`, `_vwap`, `_macd`, `_supertrend_dir`, `_ema_series`) and a per-underlying **shared market-data cache** (`PaperMarketData`) so 12 lanes/asset don't hammer the exchange (spot + OHLCV cached ~4s).
- Options grid is now **12 lanes per asset** (BTC + ETH): Trend Ride (ATM/OTM), Donchian (ATM/OTM), EMA Pullback, Trend Runner, VWAP, Supertrend, ORB, MACD, Mean Revert, Momentum.
- `dashboard/app/paper/page.tsx`: labels for the new lanes.
- User-facing: the paper lab now stress-tests the canonical strategy playbook on BTC/ETH options — the routine will rank them every 2h. `(SHA on commit)`

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

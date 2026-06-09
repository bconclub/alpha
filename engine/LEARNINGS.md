# Alpha — Trading Knowledge (what the data has taught us)

> Living record of what works and what doesn't, proven on real live + paper data.
> Build every new setup on top of this. Don't repeat dead ends.

## Verdicts so far

| # | Approach | Tested on | Result | Verdict |
|---|---|---|---|---|
| 1 | **Live options BUYING** (scalp, fast in/out) | 1,396 real trades | −$95 all-time, 28% win, every slice negative | ❌ DEAD — no edge in any regime/hold/setup |
| 2 | **Paper options BUYING** (12 strategies: trend, breakout, VWAP, Supertrend, ORB, MACD, mean-revert, momentum) | 766+ paper trades, $100 & $1,000 scales | Early small-sample winners (60–68% win) all went negative on bigger sample; −$1,600 at $1k scale | ❌ DEAD — entries directionally OK but theta + spread + give-back eat the edge. Buying short-dated options is the wrong vehicle. |
| 3 | **Fast 1-minute momentum** (options & futures) | 100s of trades | 17–22% win, biggest loser every time (−$175 paper) | ❌ DEAD — confirmed repeatedly. Stop scalping fast moves. |
| 4 | **Mean reversion / counter-trend** (RSI fade) | paper | 0–51% win, negative | ❌ Weak — fading trends in a trending/choppy crypto tape loses. |
| 5 | **High leverage on negative edge** (paper futures 25–100×) | 265 paper trades | −$119 → blew the account; higher lev = bigger loss | ❌ Leverage amplifies noise; never scale a negative-edge system. |
| 6 | **OTM option SELLING (naked)** | 52 paper trades | **0% realized win**, −$1,450; peaks +34–46% then reversed to the −100% stop | ❌ Naked selling = tail-risk death in fast crypto. Theta works but one adverse move wipes the credit. Fixes: take profit at ~+30% (not +50%), and use DEFINED-RISK SPREADS. |
| 7 | **Futures at SANE leverage (3–5×) on trend** | 58 paper trades | 0–17% win, −$171; tiny peaks (3–7%) | ❌ Trend entries don't follow through in chop; sane leverage just loses slowly. Entry edge still missing. |
| 8 | **Futures at HIGH leverage (confidence ladder 25–100×)** | — | not yet (this round) | 🧪 TESTING — user wants aggressive leverage. Prior data (#5) says leverage amplifies a negative-edge entry → expect bigger losses. Proving in paper. |

## Hard-won principles
- **Win rate ≠ profit.** Trend lanes hit 60%+ win but still lost — the exits gave back the ~34% avg peaks while losers ran. Risk/reward and exit quality matter more than hit rate.
- **Buying options has a structural tax** (theta decay + wide Delta spreads + slippage). Directionally-right trades still lose. Don't fight it.
- **Forward-test in paper before real money.** Small-sample "100% win" lanes evaporated at scale. Need hundreds of trades per lane before trusting a verdict.
- **Scaling bankroll ≠ edge.** The $100→$1,000 bump just lost 10× faster. Find edge first, size second.
- **Regime matters.** Trend strategies need trending tape; they get shredded in chop. ~most BTC/ETH intraday windows here have been choppy.
- **Always verify the deploy CONCLUSION** (not just "completed") — the VPS deploy fails intermittently and silently serves the old build.

## Current direction
Options: switch entirely from BUYING to **OTM SELLING** (theta harvest), fresh paper bankroll.
Futures: test **trend/breakout entries at 3–5× leverage** (sane), no option drag.
Keep the 2-hourly routine ranking everything. Crown a winner only after a real sample.

---

## Check-in log (2-hourly routine)

### 2026-06-09 09:39 UTC — heaviest hour in a while, no burn yet, verdict unchanged 35th run `[updated by: alpha-paper-lab-monitor]`

**What happened since last check (gap ~1h):** Hardest red hour of the recent stretch. Futures bled **−$341.75 over 15 closes (4 wins)** — bigger than the prior hour's −$227.74 — dropping bal **$542.68 → $205.99** (still >$50, burns stay at **21**, but burn #22 is now plausibly 1–2 hours out if this rate holds). Options 24 closes −$12.57 (2 wins), bal $622.88. No structural change; entries remain the whole problem.

- **Balances:** Futures funded **$22,000** (21 burns), closed **1,207 / net −$21,794.01**, **bal $205.99**. Options funded **$1,000** (0 burns), closed **702 / net −$377.12**, **bal $622.88**. No lab ≤ $50 → **no AUTO-REFILL this hour**.
- **Live OFF:** `bot_status` is_paused=true, bot_state=**paused**, market_regime TRENDING_DOWN, pause_reason "PAPER-ONLY mode", FRESH **09:37 UTC**, 0 `options_scalp` trades last hour. Paper-only confirmed. ✓
- **Per-lane futures (n=1,207):** FUT_MOMENTUM_CONF 514/15%/**−$9,316.50**; FUT_DONCHIAN_100X 141/16%/−$4,845.14; FUT_DONCHIAN_CONF 133/23%/−$2,715.01; FUT_EMA_CONF 287/32%/−$2,510.05 (least-bad win, lowest avg-peak 5.59 = lowest lev); FUT_DONCHIAN_50X 132/20%/−$2,407.30. **MOMENTUM_CONF = 42.7% of loss; + DONCHIAN_100X = −$14,161.64 = 65.0%** (shape unchanged).
- **Exit cohorts (futures, n=1,207):** `paper_stop` **672/0%/−$24,473.74 @ +1.47% avg peak = 112.3% of total loss** (wrong-direction entries noise-stopped before ever in money). Profit cohort `paper_trail` +$1,108.96 (459/50%/+15.9%) + `paper_max_hold` +$2,209.74 (25/84%/+49.2%) = **+$3,318.70**. Plus ema21_lost −$360.23 (30), ema21_reclaimed −$248.58 (21), donchian_mid_revert −$26.82 (2). **Exits work, entries are the whole problem (35th run).**
- **Options (n=702, all 5 SELL lanes red):** OPT_SELL_PUT_FAR 169/−$93.87 (−$0.555/trade), OPT_SELL_PUT 176/−$85.44 (−$0.485), OPT_SELL_CALL 140/−$84.33 (−$0.602), OPT_SELL_NEUTRAL 150/−$68.31 (−$0.455), OPT_SELL_CALL_FAR 67/−$45.17 (−$0.674). Avg fee ≈$0.58/trade vs per-trade loss −$0.46..−$0.67 → **fee-bound, ~100% of options loss is fees**. No lane-config change.
- **What we should change (unchanged):** (1) Strategy: attack ENTRIES not exits — pullback/retest before breakout + **cap leverage ≤10×**; **kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (65.0% of loss)**; keep EMA_CONF as template. (2) Options ENGINE BUG: charge fees on premium/stake not underlying notional → defined-risk spreads to escape fee drag. (Append-only; did NOT refill or change code this hour.)

### 2026-06-09 08:39 UTC — quiet hour, no burn, verdict unchanged 34th run `[updated by: alpha-paper-lab-monitor]`

**What happened since last check (gap ~1h since 07:39 burn #21):** Calm hour, **no burn**. Futures bled −$227.74 over **14 closes (1 win)**, dropping bal from the post-refill ≈$774 to **$542.68** (still >$50, burns stay at **21**). Options 15 closes −$6.47 (2 wins), bal $630.54. The 44-open-SELL-options cluster that Cowork flagged at 07:40 **closed into the predicted fee-bound pattern** (+58 options closed since the monitor's 06:39 count, all ≈−$0.54/trade). Same structural story, nothing new.

- **Balances:** Futures funded **$22,000** (21 burns), closed **1,201 / net −$21,457.32**, **bal $542.68**. Options funded **$1,000** (0 burns), closed **722 / net −$369.46**, **bal $630.54**. No lab ≤ $50 → **no AUTO-REFILL this hour**.
- **Live OFF:** `bot_status` is_paused=true, bot_state=**paused**, FRESH **08:37 UTC** (db now 08:38), 0 `options_scalp` trades last hour. Paper-only confirmed. ✓
- **Per-lane futures (n=1,201):** FUT_MOMENTUM_CONF 508/15%/**−$9,036.79**; FUT_DONCHIAN_100X 140/16%/−$4,791.20; FUT_DONCHIAN_CONF 133/23%/−$2,715.01; FUT_EMA_CONF 288/32%/−$2,507.46 (least-bad win, lowest lev); FUT_DONCHIAN_50X 132/20%/−$2,407.30. **MOMENTUM_CONF = 42.1% of loss; + DONCHIAN_100X = −$13,828 = 64.4%** (shape unchanged).
- **Exit cohorts (futures, n=1,201):** `paper_stop` **661/0%/−$24,114.60 @ +1.48% avg peak = 112.4% of total loss** (wrong-direction entries noise-stopped before ever in money). Profit cohort `paper_trail` +$1,089.45 (454/49%/+15.98%) + `paper_max_hold` +$2,209.74 (25/84%/+49.22%) = **+$3,299.19**. Plus ema21_lost −$360.23 (30), ema21_reclaimed −$248.58 (21), donchian_mid_revert −$26.82 (2), restart_orphan −$2.45 (6). **Exits work, entries are the whole problem (34th run).**
- **Options (n=722, all 5 SELL lanes red):** OPT_SELL_PUT_FAR 175/6%/−$95.09, OPT_SELL_PUT 182/12%/−$87.82, OPT_SELL_CALL 138/17%/−$77.72, OPT_SELL_NEUTRAL 154/15%/−$67.11, OPT_SELL_CALL_FAR 73/16%/−$41.78. Per-trade −$0.43..−$0.57 ≈ avg fee → **fee-bound, ~100% of options loss is fees**. The 44 open-SELL cluster from 07:40 closed exactly here, no lane-config change.
- **What we should change (unchanged):** (1) Strategy: attack ENTRIES not exits — pullback/retest before breakout + **cap leverage ≤10×**; **kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (64.4% of loss)**; keep EMA_CONF as template. (2) Options ENGINE BUG: charge fees on premium/stake not underlying notional → defined-risk spreads to escape fee drag. (Append-only; did NOT refill or change code this hour.)
- **Verdict:** #8 (aggressive 25–100× futures) **❌ DEAD** (−$21.5k closed, 21 burns, solvent only via refills). #6 (OTM selling) **⚠️ break-even/dead, fee-bound** (n=722, no lane with edge). No strategy verdict change without a clean entry-filter + leverage-cap rebuild.

### 2026-06-09 08:40 UTC — check-in `[updated by: Cowork]`
**Clean ~1h interval since the 07:40 Cowork run; corroborates the monitor's 08:39 entry (ran ~1 min after it). Futures funded $22,000 (21 burns, NO new burn — last deposit 07:39 = burn #21), closed net −$21,451.04 (n=1,193), bal ≈$548.96. Options funded $1,000 (0 burns), closed net −$364.55 (n=678), bal ≈$635.45. Live OFF; regime round-tripped and is TRENDING_DOWN again (regime_since 08:11). The 44 open SELL options flagged last hour are STILL open (did not realize) — options closed only +14 while open held at 44. Verdict unchanged, 34th run.**
- **What's happening:** `bot_status` FRESH 08:39:05 UTC (~1 min before db now 08:40), is_paused=true, bot_state=paused, **market_regime=TRENDING_DOWN** (regime_since 08:11:32 — flipped away and back within the hour), chop 0.607, delta_bal $27.08, live open_positions=0. Paper-only. Open paper: **futures 8, options 44.** Lanes active: 5 FUT_* + 5 OPT_SELL_*.
- **What happened since last check (07:40, ~60 min):** Futures closed 1,179 → **1,193 (+14)**, net −$21,223.29 → **−$21,451.04 (−$227.75)**; last-60-min futures **14 closes, −$227.74, only 1 win (7%)**. Options closed 664 → **678 (+14)**, net −$358.81 → **−$364.55 (−$5.74)**. No new burn (bal >$50). Normal-bleed hour, no green.
- **Per-lane futures (n=1,193):** FUT_MOMENTUM_CONF 506/14.8%/**−$9,049.61**/67.8×/5.1m; FUT_DONCHIAN_100X 140/15.7%/−$4,791.20/100×/2.2m; FUT_DONCHIAN_CONF 133/23.3%/−$2,715.01/56.8×/5.4m; FUT_EMA_CONF 282/31.9%/−$2,487.91/30×/10.0m; FUT_DONCHIAN_50X 132/20.5%/−$2,407.30/50×/4.8m. **MOMENTUM_CONF = 42.2% of loss; + DONCHIAN_100X = −$13,840.81 = 64.5%** (shape unchanged). Least-bad EMA_CONF (31.9% win, lowest lev 30×, longest hold 10m).
- **Exit cohorts (futures, n=1,193):** `paper_stop` **661/0%/−$24,114.60/+1.48% peak = 112.4% of total loss** (wrong-direction entries noise-stopped before ever in money). Profit cohort `paper_trail` +$1,089.45 (454/49.1%/+15.98%) + `paper_max_hold` +$2,209.74 (25/84.0%/+49.22%) = **+$3,299.19**. Plus ema21_lost −$360.23 (30), ema21_reclaimed −$248.58 (21), donchian_mid_revert −$26.82 (2). Exits work, entries are the whole problem (34 runs).
- **Options (n=678, all 5 SELL lanes red):** OPT_SELL_PUT_FAR 169/5.9%/−$93.87, OPT_SELL_PUT 176/12.5%/−$85.44, OPT_SELL_CALL 128/13.3%/−$78.47, OPT_SELL_NEUTRAL 144/14.6%/−$64.80, OPT_SELL_CALL_FAR 61/13.1%/−$41.97. Avg fee $0.57–0.59 ≈ per-trade loss (−$364.55/678 = −$0.54) = fee-bound. Exits: sell_take_profit 467/16.7%/−$105.36 (68.9% of closes, clears at a loss), sell_stop 142/0%/−$190.45, **sell_breached 69/0%/−$68.74 = 10.2% of closes.**
- **The new thing:** the **44 open SELL options persisted from last hour** — options closed advanced only +14 while open held flat at 44, so the entry cluster flagged at 07:40 has NOT realized into closes yet (positions sitting open >1h). Not a runaway loop adding more (open didn't grow), but a batch hung open. Watch next interval whether they close into the same fee-bound −$0.54/trade pattern (likely) or are stuck. Otherwise static: regime round-tripped back to TRENDING_DOWN, paper_stop still drives 112% of futures loss across every regime.
- **What we should change (unchanged):** (1) Strategy: attack ENTRIES not exits — pullback/retest before breakout + **cap leverage ≤10×**; **kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (64.5% of loss)**; keep EMA_CONF as template. Options: defined-risk spreads to escape fee drag. (2) Operational: confirm the 44 hung-open options realize on schedule (now >1h open). (Did NOT refill / change anything — append-only scope.)
- **Known-bug status (vs 06-06):** (a) option-sell fee-on-notional **STILL PRESENT** (avg fee ~$0.58 ≈ per-trade loss; ~100% of options PnL is fees). (b) `sell_breached` 15–25m exit **STILL APPEARS FIXED** (10.2% of closes, not "nearly all"). (c) futures `paper_max_hold` ~30m cap **NOT the driver** (25 trades, +$2,210 @ +49% peak; lanes hold 2.2–10.0m). `paper_stop`/entries remain the structural killer.
- **Verdict:** #8 (aggressive 25–100× futures) **❌ DEAD** (−$21.5k closed, 21 burns, solvent only via refills). #6 (OTM selling) **⚠️ break-even/dead, fee-bound** (n=678, no lane with edge). #5 dead. No strategy verdict change without a clean entry-filter + leverage-cap rebuild.

### 2026-06-09 07:40 UTC — check-in `[updated by: Cowork]`
**Corroborates the monitor's 07:39 burn-#21 entry (ran ~1 min after it): same hour window, near-zero new closes since. Futures funded $22,000 (21 burns), closed net −$21,223.29 (FUT_ lanes, n=1,179), bal ≈$777. Options all-5-SELL still red, net −$358.81 (n=664). Live OFF; regime flipped back TRENDING_DOWN (07:27). New flag: open SELL options spiked to 44 (vs ~6–8 typical) = a fresh entry cluster. Verdict unchanged, 33rd run.**
- **What's happening:** `bot_status` FRESH 07:39:05 UTC (~1.3 min before db now 07:40:18), is_paused=true, bot_state=paused, **market_regime=TRENDING_DOWN** (flipped from TRENDING_UP, regime_since 07:27), chop 0.429, delta_bal $27.08, live open_positions=0. Paper-only. Open paper: **futures 8, options 44.** Lanes active: 5 FUT_* + 5 OPT_SELL_*.
- **What happened since last check (07:39, ~1 min):** essentially nothing new closed — last-60-min futures identical to the monitor's entry (**22 closes, −$525.32, 2 wins**). Cumulative futures closed 1,179 / net −$21,223.29; options closed 664 / net −$358.81. No new burn (#21 was the monitor's; bal >$50). This is a corroboration + independent recompute, not a fresh interval.
- **Per-lane futures (n=1,179):** FUT_MOMENTUM_CONF 500/15.0%/**−$8,884.59**/67.6×/5.1m; FUT_DONCHIAN_100X 138/15.9%/−$4,773.87/100×/2.2m; FUT_DONCHIAN_CONF 131/23.7%/−$2,681.78/56.9×/5.5m; FUT_EMA_CONF 280/31.8%/−$2,490.07/30×/9.9m; FUT_DONCHIAN_50X 130/20.8%/−$2,392.98/50×/4.9m. **MOMENTUM_CONF = 41.9% of loss; + DONCHIAN_100X = −$13,658.46 = 64.4%** (shape unchanged). Least-bad EMA_CONF (31.8% win, lowest lev 30×).
- **Exit cohorts (futures, n=1,179):** `paper_stop` **656/0%/−$23,917.62/+1.44% peak = 112.7% of total loss** (wrong-direction entries noise-stopped before ever in money). Profit cohort `paper_trail` +$1,113.78 (446/49.8%/+16.01%) + `paper_max_hold` +$2,216.18 (24/87.5%/+51.14%) = **+$3,329.96**. Plus ema21_lost −$360.23 (30), ema21_reclaimed −$248.58 (21), donchian_mid_revert −$26.82 (2). Exits work, entries are the whole problem (33 runs).
- **Options (n=664, all 5 SELL lanes red):** OPT_SELL_PUT_FAR 168/6.0%/−$93.30, OPT_SELL_PUT 176/12.5%/−$85.44, OPT_SELL_CALL 121/12.4%/−$76.42, OPT_SELL_NEUTRAL 139/15.1%/−$62.13, OPT_SELL_CALL_FAR 60/13.3%/−$41.52. Avg fee $0.57–0.59 ≈ per-trade loss (−$358.81/664 = −$0.54) = fee-bound. Exits: sell_take_profit 458/16.6%/−$102.67 (69% of closes, clears at a loss), sell_stop 141/0%/−$189.85, **sell_breached 65/0%/−$66.28 = 9.8% of closes.**
- **The new thing:** open SELL-options jumped to **44** (typical 6–8 in prior entries) while futures open held at 8 — a burst of fresh OPT_SELL entries opened this interval, not yet realized. Watch whether they close into the same fee-bound −$0.54/trade pattern (likely) or signal a lane-config/entry-loop change. Otherwise static: regime round-tripped UP→DOWN within the hour, yet paper_stop still drives 113% of futures loss in every regime.
- **What we should change (unchanged):** (1) Strategy: attack ENTRIES not exits — pullback/retest before breakout + **cap leverage ≤10×**; **kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (64.4% of loss)**; keep EMA_CONF as template. Options: defined-risk spreads to escape fee drag. (2) Operational: confirm the 44 open options aren't a runaway entry loop. (Did NOT refill / change anything — append-only scope.)
- **Known-bug status (vs 06-06):** (a) option-sell fee-on-notional **STILL PRESENT** (avg fee ~$0.58 ≈ per-trade loss; ~100% of options PnL is fees). (b) `sell_breached` 15–25m exit **STILL APPEARS FIXED** (9.8% of closes, not "nearly all"). (c) futures `paper_max_hold` ~30m cap **NOT the driver** (24 trades, +$2,216 @ +51% peak; lanes hold 2.2–9.9m). `paper_stop`/entries remain the structural killer.
- **Verdict:** #8 (aggressive 25–100× futures) **❌ DEAD** (−$21.2k closed, 21 burns, solvent only via refills). #6 (OTM selling) **⚠️ break-even/dead, fee-bound** (n=664, no lane with edge). #5 dead. No strategy verdict change without a clean entry-filter + leverage-cap rebuild.

### 2026-06-09 07:39 UTC — AUTO-REFILL burn #21 fired, verdict unchanged 32nd run `[updated by: alpha-paper-lab-monitor]`

**What happened since last check (gap ~1h since 06:39):** Futures went insolvent again → **BURN #21** (bal hit **−$225.74** ≤ $50 → refilled $1,000, funded now **$22k**, bal +$774.26). Resolves the 06:39 burn-#20 cycle; same structural story, no new behavior.

- **Funding/balance/burns:** Futures funded **$22,000** (21 burns), closed **1,186**, net **−$21,225.74** → bal **$774.26** post-refill. Options funded **$1,000** (0 burns), closed **707**, net **−$363.19** → bal **$636.81** (>$50, no refill).
- **Last hour (futures):** 22 closes, **−$525.32**, only 2 wins — heavier bleed than the prior quiet hour, triggering the insolvency + burn.
- **Live OFF confirmed:** `bot_status` is_paused=true, bot_state=paused, FRESH 07:37 UTC; 0 options_scalp trades last hour.

**Exit-reason story (FUT, n=1,186), unchanged & ironclad:**
| Exit | Closed | Win% | Net | Avg peak% |
|---|---|---|---|---|
| **paper_stop** | 656 | 0 | **−23,917.62** | +1.44 |
| paper_trail | 446 | 50 | **+1,113.78** | +16.01 |
| paper_max_hold | 24 | 88 | **+2,216.18** | +51.14 |
| ema21_lost/reclaimed | 51 | ~1 | −608.81 | ~2.3 |

`paper_stop` = 656 wrong-direction entries noise-stopped at avg peak +1.44% (never in the money), losing **−$23,918 = 113% of the whole book**. Trail (50% win, banks ~16% peak) + max_hold (88% win, +51% peak) are the only green = **exits work, entries are the entire problem.**

**Worst FUT lanes (cum):**
| Lane | Closed | Win% | Net |
|---|---|---|---|
| FUT_MOMENTUM_CONF | 723 | 15 | **−8,871.76** |
| FUT_DONCHIAN_100X | 276 | ~20 | −4,773.87 |
| FUT_DONCHIAN_CONF | 262 | ~22 | −2,681.78 |
| FUT_EMA_CONF | 570 | 32 | −2,505.34 |
| FUT_DONCHIAN_50X | 260 | ~26 | −2,392.98 |

MOMENTUM_CONF = 42% of loss; +DONCHIAN_100X = **64%** of loss. EMA_CONF still least-bad (highest win 32%, lowest lev; its paper_trail prints 87% win +$1,107).

**Options (n=707, all 5 SELL lanes negative, fee-bound):** worst OPT_SELL_PUT_FAR −$94.53/175 (−$0.54/trade); least-bad OPT_SELL_CALL_FAR −$41.27/72. Avg PnL −$0.43 to −$0.58/trade = fee drag ≈ 100% of loss (gross ~breakeven). Structurally dead until fees charge on premium, not underlying notional.

**Verdict status:** unchanged (32nd run). #8 aggressive futures **DEAD** (21 burns). #6 OTM selling **break-even/fee-capped** (engine fee bug). **FIX = pullback/retest entries + cap leverage ≤10× + kill MOMENTUM_CONF/DONCHIAN_100X (64% of loss); fix options fee model (charge on premium).**

### 2026-06-09 06:40 UTC — check-in `[updated by: Cowork]`
**Corroborates the monitor's 06:39 entry: INSOLVENCY RESOLVED — auto-refill burn #20 fired 06:39:34 UTC ($1,000), futures balance −$584.22 (insolvent at 05:38) → +$302.02 (solvent). The refill-not-firing bug flagged at 05:38 self-resolved once cadence normalized (~62 min, no gap). Quietest hour in the log: 5 futures closes (−$94.52) + 11 options (−$6.14). Regime still TRENDING_UP (2nd consecutive). Verdict unchanged, 31st run.**
- **What's happening:** `bot_status` last write **2026-06-09 06:39:04 UTC** (~1.3 min before db now 06:40:20, FRESH), `is_paused=true`, `bot_state="paused"`, **market_regime=TRENDING_UP** (held from 05:38), chop 0.536, delta_bal $27.08, live `open_positions=0`. Live OFF, paper-only. Open paper: **futures 4, options 8.** Lanes active: 5 FUT_* + 5 OPT_SELL_*.
- **What happened since last check (05:38, ~62 min):**
  - **Futures:** funded **$20,000 → $21,000 (burn #20 fired 06:39:34 UTC)**. Closed 1,150 → **1,157 (+7)**. Net −$20,584.22 → **−$20,697.98 (−$113.76)**. Balance **−$584.22 (insolvent) → +$302.02 (refilled, solvent)**. Last 1h: **5 closes, −$94.52** (lowest-activity hour logged; DONCHIAN lanes near-idle).
  - **Options (SELL):** funded $1,000. Closed 635 → **646 (+11)**. Net −$341.63 → **−$347.77 (−$6.14)**. Balance ≈ **$652.23**.
  - Per-lane futures (n=1,157): **FUT_MOMENTUM_CONF** 492cl/14.8%/**−$8,754.30**/67.6×/5.1m; **FUT_DONCHIAN_100X** 136/16.2%/−$4,682.25/100×/2.2m (0 new closes); **FUT_DONCHIAN_CONF** 129/24.0%/−$2,599.60/56.4×/5.5m; **FUT_EMA_CONF** 272/32.7%/−$2,336.21/30.0×/9.9m; **FUT_DONCHIAN_50X** 128/21.1%/−$2,325.61/50×/4.9m. **MOMENTUM_CONF = 42.3% of futures loss; + DONCHIAN_100X = −$13,436.55 = 64.9%** (shape unchanged, 31st run). Least-bad: **EMA_CONF (32.7% win, lowest lev 30×)**, now ~tied with DONCHIAN_50X on net but highest win%.
  - Options per-lane: OPT_SELL_PUT_FAR 166/6.0%/−$92.14, OPT_SELL_PUT 170/12.9%/−$82.19, OPT_SELL_CALL 117/12.8%/−$73.39, OPT_SELL_NEUTRAL 134/15.7%/−$59.25, OPT_SELL_CALL_FAR 59/13.6%/−$40.80. Avg fee $0.57–0.59, avg peak 0.13–0.70%.
- **Exit cohorts (futures, n=1,157):** `paper_stop` **642 cl, 0% win, −$23,456.98, avg PEAK +1.46%** = **113.3% of total futures loss** (wrong entries noise-stopped before reaching money). Profit cohort ~flat: `paper_trail` **+$1,126.32** (n=442, 49.8% win, +16.02% peak) + `paper_max_hold` **+$2,216.18** (n=24, 87.5% win, +51.14% peak) = **+$3,342.50** (vs +$3,335.96 last check, +$7 — barely moved in the quiet hour). Plus ema21_lost −$308.10 (n=26), ema21_reclaimed −$248.58 (n=21), donchian_mid_revert −$26.82 (n=2). Entries remain the whole problem, 31 runs.
- **Exit cohorts (options, n=646):** sell_take_profit **449 cl / 16.9% / −$97.88 / +0.45% peak** (dominant, 69.5% of closes, clears at a loss = fees), sell_stop 135 / 0% / −$185.92, **sell_breached 62 / 0% / −$63.97 = 9.6% of closes** (still not "nearly all").
- **The new thing:** (1) the refill-not-firing operational bug flagged at 05:38 self-resolved — burn #20 fired on schedule this run, restoring solvency (+$302). Refill loop appears functional when cadence is normal; the 05:38 insolvency was the *scheduler gap*, not the refill mechanism. (2) Lowest-volume hour in the log (5 futures + 11 options closes); DONCHIAN 100X/CONF/50X took ~0 new closes, so the −$114 came almost entirely from MOMENTUM_CONF + EMA_CONF wrong-entry stops. (3) Second consecutive TRENDING_UP read, yet paper_stop still drives 113% of loss — breakout/momentum entries fail in up-tape too, confirming 05:38's observation it isn't just chop/down.
- **What we should change (unchanged):**
  1. **Strategy:** attack ENTRIES not exits — pullback/retest before breakout entry and **cap leverage ≤10×** (wrong entry then costs ~−2% not ~−8.7%). **Kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (64.9% of loss).** Keep EMA_CONF as template. Options: defined-risk spreads to escape fee drag.
  2. **Operational:** refill fired correctly this run; remaining risk is the scheduler gap (don't let runs stall and leave the lab insolvent between burns). (Did NOT refill — append-only scope; burn #20 was the engine's own auto-refill.)
- **Known-bug status (vs 06-06):** (a) option-sell fee-on-notional **STILL PRESENT** (avg fee $0.58 ≈ per-trade loss −347.77/646 ≈ −$0.54; ~100% of options PnL is fees). (b) `sell_breached` 15–25m exit **STILL APPEARS FIXED** (9.6% of closes). (c) futures `paper_max_hold` ~30m cap **NOT the driver** (24 trades, +$2,216 @ +51.14% peak; lanes hold 2.2–9.9m so cap rarely binds). `paper_stop` (entries) remains the structural killer.
- **Verdict:** #8 (aggressive 25–100× futures) **❌ DEAD** (−$20.7k closed, 20 burns, only solvent via refills). #6 (OTM selling) **⚠️ break-even/dead, fee-bound** (n=646, no lane with edge). #5 dead. No strategy verdict change without a clean entry-filter + leverage-cap rebuild.

### 2026-06-09 06:39 UTC — AUTO-REFILL burn #20 fired, verdict unchanged 31st run `[updated by: alpha-paper-lab-monitor]`
**Resolved the insolvency the 05:38 run flagged: futures had bled to ≈ −$697.98 (funded $20,000, closed −$20,697.98, still 19 burns) → fired AUTO-REFILL burn #20 (paper_deposits id 22, +$1,000). Funded now $21,000, balance ≈ +$302.02. Quiet hour. Live OFF. Same structural story, 31st run.**
- **Live/bot:** `bot_status` last write **2026-06-09 06:39:04 UTC** (~30s before db now, FRESH), `is_paused=true`, `bot_state="paused"`, pause_reason "PAPER-ONLY mode", **market_regime=TRENDING_UP** (held since 06:21, chop 0.536), delta_bal $27.08. **0 open positions, 0 options_scalp last hour.** Live OFF confirmed.
- **Since 05:38 (~1h):**
  - **Futures:** closed 1,150 → **1,157 (+7)**. Net −$20,584.22 → **−$20,697.98 (−$113.76)**. Balance −$584 → **−$697.98 → +$302.02 after refill #20**. Last 1h: **6 closes, −$86.10** — quiet, no green, same shape.
  - **Options (SELL):** closed 635 → **645 (+10)**. Net −$341.63 → **−$347.26 (−$5.63)**. Balance ≈ **$652.74** (>$50, no refill).
- **Per-lane futures (n=1,157):** FUT_MOMENTUM_CONF 492cl/15%/**−$8,754.30**/68×/5.1m; FUT_DONCHIAN_100X 136/16%/−$4,682.25/100×/2.2m; FUT_DONCHIAN_CONF 129/24%/−$2,599.60/56×/5.5m; **FUT_EMA_CONF** 272/**33%**/−$2,336.21/30×/9.9m (least-bad win, lowest lev); FUT_DONCHIAN_50X 128/21%/−$2,325.61/50×/4.9m. **MOMENTUM_CONF = 42% of loss; + DONCHIAN_100X = −$13,436.55 = 65%** (shape unchanged).
- **Options per-lane (n=645):** OPT_SELL_PUT_FAR 166/6%/−$92.14; OPT_SELL_PUT 169/13%/−$81.68; OPT_SELL_CALL 117/13%/−$73.39; OPT_SELL_NEUTRAL 134/16%/−$59.25; OPT_SELL_CALL_FAR 59/14%/−$40.80. Avg fee $0.57–0.59 ≈ per-trade loss (fee-bound).
- **Exit cohorts (futures, the whole story):**

| exit | n | win% | net | avg peak |
|---|---|---|---|---|
| paper_stop | 642 | 0% | **−$23,456.98** | +1.46% |
| ema21_lost | 26 | 4% | −$308.10 | +1.86% |
| ema21_reclaimed | 21 | 0% | −$248.58 | +2.64% |
| paper_trail | 442 | 50% | **+$1,126.32** | +15.99% |
| paper_max_hold | 24 | 88% | **+$2,216.18** | +51.14% |

  `paper_stop` = **113% of net loss** at +1.46% avg peak (wrong entries noise-stopped, never in money). Profit cohort trail+max_hold = **+$3,342.50** = exits work, entries are the whole problem (unchanged proof).
- **What to change (unchanged):** (1) attack ENTRIES not exits — pullback/retest before breakout + **cap lev ≤10×**; **kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (65% of loss)**; keep EMA_CONF as template. Options: defined-risk spreads to escape fee drag. (2) Refill #20 fired clean this hour — the 05:38 stall was the scheduler gap, not the refill logic in this run.
- **Known bugs (vs 06-06):** (a) option-sell fee-on-notional STILL PRESENT (avg fee $0.58 ≈ −$347.26/645 ≈ −$0.54/trade; ~100% of options PnL = fees). (b) `sell_breached` exit appears still fixed. (c) `paper_max_hold` not the driver (24 trades, +$2,216, lanes hold 2.2–9.9m). `paper_stop`/entries remain the structural killer.
- **Verdict:** #8 (aggressive 25–100× futures) **❌ DEAD** (−$20.7k closed, 20 burns). #6 (OTM selling) **⚠️ break-even/dead, fee-bound** (n=645, no lane with edge). No strategy verdict change without a clean entry-filter + leverage-cap rebuild.

### 2026-06-09 05:38 UTC — check-in `[updated by: Cowork]`
**~6h CADENCE GAP (last log 06-08 23:39 → now 05:38; the 00:39–04:39 runs did not fire). Futures lab INSOLVENT AGAIN ≈ −$584.22 (funded $20,000, closed −$20,584.22, 19 burns, NO burn #20 fired in the gap) — same refill-not-firing pattern flagged 06-08. Regime flipped to TRENDING_UP (first up-regime in the recent log). Verdict unchanged, 30th run.**
- **What's happening:** `bot_status` last write **2026-06-09 05:37:04 UTC** (~1.3 min before db now 05:38:19, FRESH), `is_paused=true`, `bot_state="paused"`, **market_regime=TRENDING_UP** (flipped from TRENDING_DOWN), chop 0.607, delta_bal $27.08. Live OFF, paper-only. Open: **futures 5, options 6.** Lanes active: 5 FUT_* + 5 OPT_SELL_*.
- **What happened since last check (23:39, ~6h):**
  - **Futures:** funded still **$20,000 (19 burns, NO new refill)**. Closed 1,030 → **1,150 (+120)**. Net −$19,049.90 → **−$20,584.22 (−$1,534.32; ~−$256/hr, normal)**. Balance **$950.10 → ≈ −$584.22 (insolvent)**. Last 1h: 33 closes, **−$539.41**.
  - **Options (SELL):** funded $1,000. Closed 569 → **635 (+66)**. Net −$312.89 → **−$341.63 (−$28.74)**. Balance ≈ **$658.37**.
  - Per-lane futures (n=1,150): **FUT_MOMENTUM_CONF** 489cl/14.7%/**−$8,723.69**/67.7×/5.0m; **FUT_DONCHIAN_100X** 136/16.2%/−$4,682.25/100×/2.2m; **FUT_DONCHIAN_CONF** 128/24.2%/−$2,571.94/56.4×/5.5m; **FUT_DONCHIAN_50X** 127/21.3%/−$2,293.71/50×/4.9m; **FUT_EMA_CONF** 268/32.5%/−$2,293.67/29.9×/9.8m. **MOMENTUM_CONF = 42.4% of futures loss; + DONCHIAN_100X = −$13,405.94 = 65.1%** (shape unchanged, 30th run). Least-bad: **EMA_CONF (32.5% win, lowest lev).**
  - Options per-lane: OPT_SELL_PUT_FAR 164/6.1%/−$91.02, OPT_SELL_PUT 162/13.6%/−$77.72, OPT_SELL_CALL 117/12.8%/−$73.39, OPT_SELL_NEUTRAL 133/15.8%/−$58.70, OPT_SELL_CALL_FAR 59/13.6%/−$40.80. Avg fee $0.57–0.59, avg peak 0.14–0.70%.
- **Exit cohorts (futures, n=1,150):** `paper_stop` **638 cl, 0% win, −$23,343.51, avg PEAK +1.46%** = **113% of total futures loss** (wrong entries noise-stopped before reaching money). Profit cohort GREW: `paper_trail` **+$1,128.20** (n=439, 49.7% win, +16.07% peak) + `paper_max_hold` **+$2,207.76** (n=23, 87% win, +52.95% peak) = **+$3,335.96** (up ~+$729 from +$2,607 last check). Plus ema21_lost −$308.10 (n=26), ema21_reclaimed −$248.58 (n=21), donchian_mid_revert −$26.82 (n=2). Entries remain the whole problem, 30 runs.
- **Exit cohorts (options, n=635):** sell_take_profit **440 cl / 17.3% / −$93.19 / +0.46% peak** (dominant exit, but clears at a loss = fees), sell_stop 133 / 0% / −$184.47, **sell_breached 62 / 0% / −$63.97** = only **9.8% of closes**.
- **The new thing:** (1) lab went insolvent across the cadence gap with no auto-refill — the refill-not-firing + scheduler-gap operational bug recurred (≈ −$584 unattended). (2) Regime flipped **TRENDING_UP** for the first time recently; even so, paper_stop still drives 113% of loss — these breakout/momentum entries fail in up-trend tape too, not just chop/down. (3) profit cohort keeps compounding (+$729 this window via trail/max_hold) while entries bleed — cleanest restatement of the thesis yet.
- **What we should change (unchanged):**
  1. **Strategy:** attack ENTRIES not exits — pullback/retest before breakout entry and **cap leverage ≤10×** (wrong entry then costs ~−2% not ~−8.7%). **Kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (65.1% of loss).** Keep EMA_CONF as template. Options: defined-risk spreads to escape fee drag.
  2. **Operational:** auto-refill again failed to fire and the hourly run stalled ~6h, leaving the lab insolvent. Decouple/repair the refill loop and scheduler. (Did NOT refill — append-only scope.)
- **Known-bug status (vs 06-06):** (a) option-sell fee-on-notional **STILL PRESENT** (avg fee $0.58 ≈ per-trade loss −341.63/635 ≈ −$0.54; ~100% of options PnL is fees). (b) `sell_breached` 15–25m exit **APPEARS STILL FIXED** (9.8% of closes, not "nearly all"). (c) futures `paper_max_hold` ~30m cap **NOT the driver** (23 trades, +$2,208 @ +52.95% peak; lanes hold 2.2–9.8m so cap rarely binds). `paper_stop` (entries) remains the structural killer.
- **Verdict:** #8 (aggressive 25–100× futures) **❌ DEAD** (−$20.6k closed, 19 burns, insolvent again). #6 (OTM selling) **⚠️ break-even/dead, fee-bound** (n=635, no lane with edge). #5 dead. No strategy verdict change without a clean entry-filter + leverage-cap rebuild.

### 2026-06-08 23:39 UTC — calmest hour post-refill (-$109/11 closes), no burn #20, verdict unchanged 29th run `[updated by: alpha-paper-lab-monitor]`
**Futures lab:** FUNDED $20,000 · BURNS 19 · closed PnL −$19,049.90 (n=1,030) · **BALANCE $950.10** → above $50, **no refill** (burns stay 19). Last hour: 11 closes, **−$108.84** — quietest hour since refill #19, ~half the prior hour's bleed, but still red and still the same structural story (no green this hour, the 21:38 green hour remains a one-off).

**Exit-reason cohort (the whole story):**
| exit | n | win% | net | avg peak |
|---|---|---|---|---|
| paper_stop | 576 | 0% | **−$21,171.00** | +1.50% |
| ema21_lost | 23 | 4% | −$261.80 | +1.98% |
| ema21_reclaimed | 17 | 0% | −$197.81 | +2.40% |
| paper_trail | 393 | 48% | **+$799.21** | +15.75% |
| paper_max_hold | 19 | 84% | **+$1,808.32** | +52.26% |

paper_stop = **111% of all loss** at +1.50% avg peak / 0% win = wrong entries noise-stopped before ever going in-money. Profit cohort (trail +$799 + max_hold +$1,808) = **+$2,607.53** = exits work fine when an entry lands and is let to run. Entries are the entire problem — unchanged 29 runs.

**Futures lanes:** MOMENTUM_CONF −$8,284 (14% win) = **44% of loss**; +DONCHIAN_100X −$4,220 (15%) = **66%**. DONCHIAN_CONF −$2,337 (23%), DONCHIAN_50X −$2,156 (19%), **EMA_CONF −$2,053 (33% win) = least-bad**.

**Options:** flat/fee-bound, all SELL lanes red, n=569 −$312.89. Worst SELL_PUT_FAR (7% win), SELL_PUT −$69, SELL_CALL −$68, SELL_NEUTRAL −$54.

**Live:** OFF — is_paused=true, bot_status FRESH (23:37 UTC), 0 options_scalp/hr, regime TRENDING_DOWN, delta bal $27.08.

**Verdict (unchanged, 29th run):** pullback/limit entries (don't chase momentum) + cap leverage ≤10× + kill MOMENTUM_CONF & DONCHIAN_100X. Keep EMA_CONF as the only survivable lane. Exits are not the bug — entries are.

### 2026-06-08 22:39 UTC — AUTO-REFILL BURN #19; green hour was a one-off, futures reverted to bleed `[updated by: alpha-paper-lab-monitor]`
**The +$72 green hour did NOT hold. Futures bled −$367.90 this interval (23 closes), dropping balance $406.64 → $38.74 ≤ $50 → AUTO-REFILL fired (burn #19), restoring to ~$1,038.74. Funded now $20,000 across 19 burns. The reversion is the signal: the profit exit-cohort barely grew (+$10) while fresh `paper_stop` wrong-entries resumed — confirming the green hour was a lucky catch by trail/max_hold, not a structural change. Live OFF, bot_status FRESH (22:37 UTC). Verdict unchanged, 28th run.**

- **What's happening:** `bot_status` last write **2026-06-08 22:37:03 UTC** (~2.4 min before db now 22:39:29, FRESH), `is_paused=true`, `is_running=true`, `bot_state="paused"`, `pause_reason="PAPER-ONLY mode (no live trading)"`, **market_regime=TRENDING_DOWN** (flipped back from CHOPPY), chop_score 0.46, 0 open positions, daily_pnl 0. Live trading OFF confirmed.
- **What happened since last check (21:40, ~59 min):**
  - **Futures:** closed 1,005 → **1,028 (+23)**. Net −$18,593.36 → **−$18,961.26 (−$367.90)**. Balance **$406.64 → $38.74** (back near floor) → **refill #19 → ~$1,038.74**. Funded $19,000 → **$20,000**, burns 18 → **19**.
  - **Options (SELL):** closed 543 → **599 (+56)**. Net −$295.02 → **−$308.06 (−$13.04)**. Balance **$691.94**. No burn (funded $1,000, 0 burns).
  - Per-lane futures (n=1,028): **FUT_MOMENTUM_CONF** 444cl/14%/**−$8,311.47**/8.94% avg-peak/4.8m; **FUT_DONCHIAN_100X** 117/15%/−$4,179.48/9.45%/2.3m; **FUT_DONCHIAN_CONF** 111/23%/−$2,334.50/7.66%/5.6m; **FUT_DONCHIAN_50X** 112/20%/−$2,123.24/6.65%/5.0m; **FUT_EMA_CONF** 244/33%/−$2,013.92/5.64%/9.8m. **MOMENTUM_CONF = 43.8% of futures loss; + DONCHIAN_100X = −$12,490.95 = 65.9%** (shape unchanged, 28th run). Least-bad: **EMA_CONF (33% win, lowest lev).**
  - Options per-lane: OPT_SELL_PUT_FAR 154/7%/−$81.90, OPT_SELL_PUT 150/15%/−$70.15, OPT_SELL_CALL 103/17%/−$65.10, OPT_SELL_NEUTRAL 129/19%/−$52.80, OPT_SELL_CALL_FAR 63/19%/−$37.97. All SELL lanes 7–19% win, fee-bound (≈−$0.51/trade).
- **What happened — exit cohorts (n=1,028):** `paper_stop` **569 cl, −$20,985.43, avg PEAK +1.51%** = **111% of total futures loss** — wrong-direction entries that never reach the money, exit at ~−8.7% under leverage. Profit cohort **barely moved**: `paper_trail` **+$818.54** (n=390, +15.77% peak) + `paper_max_hold` **+$1,712.26** (n=18, +51.44% peak) = **+$2,530.80** (up only **+$10** from +$2,520.72 last check). That flat cohort vs growing paper_stop = the −$368 red hour, undoing the prior +$72. Mechanically identical pattern, 28 runs: **entries are the whole problem.**
- **The signal this hour:** the green hour reverted, exactly as expected for a noise-driven lab. Profit cohort gained nothing (+$10); the entire move was fresh wrong entries adding to paper_stop. There is no entry edge — green hours are when trail/max_hold happen to catch a real move, red hours (the default) are wrong-entry noise-stops. Nothing changed structurally.
- **What we should change (unchanged):**
  1. **Attack ENTRIES, not exits** — pullback/retest before breakout entry and **cap leverage ≤10×** (wrong entry then costs ~−2% not ~−8.7%). **Kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (65.9% of loss).** Keep EMA_CONF as template. The profit cohort proves exits already work.
  2. Options: defined-risk spreads to escape fee drag (all 5 SELL lanes fee-bound, ~100% of credit eaten by ~$0.51/trade fees).
- **Known-bug status:** (a) option-sell fee-on-notional **STILL PRESENT** (−$308.06 / 599 ≈ −$0.51/trade ≈ fee). (b) futures `paper_max_hold` cap **NOT the driver** (18 trades, +$1,712 @ +51% peak; lanes hold 2.3–9.8m so cap rarely binds). (c) `paper_stop` (entries) remains the structural killer.
- **Verdict:** #8 (aggressive 25–100× futures) **❌ DEAD** (−$18.96k closed across **19 burns**; the one green hour reverted in one hour). #6 (OTM selling) **⚠️ break-even/dead, fee-bound** (n=599). #5 dead. No strategy verdict change without a clean entry-filter + leverage-cap rebuild.

### 2026-06-08 21:40 UTC — check-in `[updated by: Cowork]`
**Corroborates the monitor's 21:38 entry exactly: first net-green futures hour in the log, +$72.45 (16 closes), driven entirely by the profit exit-cohort (trail+max_hold = +$2,521, up +$355) outrunning paper_stop. Balance $334→$407, no burn #19. Regime flipped TRENDING_DOWN→CHOPPY. My added signal: options `sell_breached` has collapsed from "nearly all sells" to 8% of closes — that engine bug looks changed. Verdict unchanged, 27th run.**

- **What's happening:** `bot_status` last write **2026-06-08 21:39:06 UTC** (~1.4 min before db now 21:40:27, FRESH), `is_paused=true`, `is_running=true`, `bot_state="paused"`, `pause_reason="PAPER-ONLY mode (no live trading)"`, **market_regime=CHOPPY** (flipped from TRENDING_DOWN). 30 status writes last hour, paper-only. Open: **futures 2** (MOMENTUM_CONF 1, EMA_CONF 1), **options 7.** Lanes active: 5 FUT_* + 5 OPT_SELL_*.
- **What happened since last check (20:40, ~60 min):**
  - **Futures:** funded **$19,000 (NO new burn since 19:40:57)**. Closed 989 → **1,005 (+16)**. Net −$18,665.81 → **−$18,593.36 (+$72.45 — first green hour logged)**. Balance **$334.19 → $406.64** (off the floor). Last-24h **490 closes −$9,406** (gap bleed still in trailing window, easing from −$9,765).
  - **Options (SELL):** funded $1,000. Net −$287.47 → **−$295.02 (−$7.55)**. Balance **$704.98**. Closed 531 → **543 (+12)**.
  - Per-lane futures (n=1,005): **FUT_MOMENTUM_CONF** 433cl/13.4%/**−$8,171.56**/67.4×/4.8m; **FUT_DONCHIAN_100X** 115/15.7%/−$4,088.92/100×/2.3m; **FUT_DONCHIAN_CONF** 109/23.9%/−$2,278.42/56.7×/5.7m; **FUT_DONCHIAN_50X** 110/20.0%/−$2,065.78/50×/5.0m; **FUT_EMA_CONF** 238/33.2%/−$1,988.68/29.8×/9.8m. Worst: **MOMENTUM_CONF = 44.0% of futures loss; MOMENTUM_CONF + DONCHIAN_100X = −$12,260.48 = 65.9%** (shape unchanged, 27th run). Least-bad: **EMA_CONF (33.2% win, lowest lev 29.8×).**
  - Options per-lane: OPT_SELL_PUT_FAR 145/6.9%/−$79.80, OPT_SELL_PUT 141/15.6%/−$64.88, OPT_SELL_CALL 90/13.3%/−$62.70, OPT_SELL_NEUTRAL 116/18.1%/−$49.53, OPT_SELL_CALL_FAR 51/15.7%/−$38.11. Avg fees $0.57–0.59, avg peak 0.15–0.78%.
- **What happened — exit cohorts:**
  - Futures (n=1,005): `paper_stop` **559 cl, −$20,627.64, avg PEAK +1.53%** = **111% of total futures loss** — wrong-direction entries that never reach the money. Profitable cohort GREW: `paper_trail` **+$808.46** (n=386, +15.68% peak) + `paper_max_hold` **+$1,712.26** (n=18, +51.44% peak) = **+$2,520.72** (up from +$2,166 last check, +$355). That +$355 cohort gain net of fresh paper_stop damage is the entire +$72 green hour. Entries remain the whole problem, 27 runs.
  - Options (n=543): `sell_take_profit` **381 cl / −$73.02 / +0.50% peak**, `sell_stop` 117 / −$169.87 / +0.07%, `sell_breached` **45 / −$52.14 / +0.15%**.
- **The new thing:** **`sell_breached` has collapsed.** Prior runs flagged it firing on "nearly all sell trades in 15–25 min"; it is now only **45 of 543 closes (8%)**, while `sell_take_profit` dominates at 381 (70%). The 15–25 min forced-breach pattern appears changed/possibly fixed in the engine. BUT the win is hollow: `sell_take_profit` still nets **−$73 across 381 trades** at +0.50% avg peak — the "take profit" exits clear at a loss because the ~$0.58 fee ≈ the entire credit. The bottleneck moved from a bad exit-reason to pure fee drag.
- **What we should change:**
  1. **Strategy (unchanged):** attack ENTRIES not exits — pullback/retest before breakout entry and **cap leverage ≤10×** (wrong entry then costs ~−2% not ~−8.7%). **Kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (65.9% of loss).** Keep EMA_CONF as template. Options: defined-risk spreads to escape fee drag (the only path now that the exit-timing bug looks gone but fees still eat 100% of credit).
  2. **Known-bug status (vs 06-06):** (a) **option-sell fee-on-notional — STILL PRESENT:** avg fee $0.58 ≈ per-trade loss (−$295.02 / 543 ≈ −$0.54), ~100% of options PnL is fees. (b) **`sell_breached` 15–25m exit — APPEARS CHANGED/FIXED:** down to 8% of closes (was "nearly all"); sell_take_profit now the dominant exit. Monitor to confirm it holds. (c) **futures `paper_max_hold` ~30m clip — STILL NOT the driver:** max_hold cohort 18 trades, +$1,712 @ +51.44% peak, lane holds avg 2.3–9.8m, so the cap rarely binds; `paper_stop` (entries) remains the structural killer.
- **Verdict:** #8 (aggressive 25–100× futures) **❌ DEAD** (−$18.6k closed across 18 burns; one green hour off a thin floor changes nothing). #6 (OTM selling) **⚠️ break-even/dead, fee-bound** (n=543, no lane with edge). #5 dead. No strategy verdict change without a clean entry-filter + leverage-cap rebuild.

### 2026-06-08 21:38 UTC — FIRST POSITIVE FUTURES HOUR (+$72); profit cohort outran noise-stops `[updated by: alpha-paper-lab-monitor]`
**Futures balance ROSE this hour — $334.19 → $406.64 (+$72.45 net, 16 closes) — the first net-green hour in the lab's history. Not fewer wrong entries: the profit cohort (trail+max_hold = +$376) simply caught real moves and outran the noise-stops (−$268). Cleanest proof yet that exits work and entries are the whole problem. No new burn (bal > $50, burns still 18). Live OFF, bot_status FRESH (21:37 UTC, ~1.3 min old). Verdict unchanged, 27th run.**

- **Live/cadence:** `is_paused=true`, `bot_state="paused"`, `scalp_enabled`/`options_scalp_enabled=true` but **0 scalp trades last hour** (futures & options) → paper-only confirmed. Status fresh (21:37:05 UTC, ~1.3 min before db now). Cadence normal (~58 min since 20:40).
- **Balances:** Futures **$406.64** (= $19,000 funded − $18,593.36 closed net; 18 burns; thin but > $50, **no auto-refill**). Options **$704.97** (funded $1,000, 0 burns, closed n=543, net −$295.03).
- **Per-lane — Futures (n=1005):**

| Lane | Closed | Win% | Net | Avg peak% | Max peak% | Avg hold |
|---|---|---|---|---|---|---|
| **FUT_MOMENTUM_CONF** | 433 | 13% | **−$8,172** | 8.91 | 326.56 | 5m |
| FUT_DONCHIAN_100X | 115 | 16% | −$4,089 | 9.62 | 88.37 | 2m |
| FUT_DONCHIAN_CONF | 109 | 24% | −$2,278 | 7.81 | 78.60 | 6m |
| FUT_DONCHIAN_50X | 110 | 20% | −$2,066 | 6.77 | 43.16 | 5m |
| FUT_EMA_CONF | 238 | 33% | −$1,989 | 5.76 | 133.43 | 10m |

  Worst: **MOMENTUM_CONF = 44% of all futures loss; MOMENTUM_CONF + DONCHIAN_100X = −$12,261 = 66%** (shape unchanged, 27th run). Least-bad: **EMA_CONF (33% win, lowest lev).**
- **Per-lane — Options SELL (n=543):** OPT_SELL_PUT_FAR 145/7%/−$80, OPT_SELL_PUT 141/16%/−$65, OPT_SELL_CALL 90/13%/−$63, OPT_SELL_NEUTRAL 116/18%/−$50, OPT_SELL_CALL_FAR 51/16%/−$38. Flat fee-bound noise, no lane with edge.
- **This hour's split (16 closes, +$72.45):** the green came entirely from the **profit cohort** — `paper_max_hold` +$217 (2 MOMENTUM_CONF, peak 117.80%), `paper_trail` +$159 (DONCHIAN_100X +$100 @ 88% peak, DONCHIAN_50X +$51, DONCHIAN_CONF +$8). Against them, `paper_stop` wrongs lost **−$268** (DONCHIAN_CONF −$144 @ **1.07% avg peak** = never-in-money noise stops; EMA/MOMENTUM/50X/100X stops the rest) + one donchian_mid_revert −$14. Winners ($376) > stops+revert (−$282) → first green hour. **Same lanes that bleed on wrong entries make the money when an entry lands and the trail/max_hold exit lets it run.**
- **The new thing:** a positive hour does NOT change the verdict — it's the strongest confirmation of it. The lab didn't get better entries; it got a handful of entries that happened to be right, and the exit logic banked them cleanly (peaks 88–118% realized via trail/max_hold). Fix the entry hit-rate and every hour looks like this one.
- **What to change (unchanged, 27th run):** attack ENTRIES not exits — require pullback/retest before breakout entry and **cap leverage ≤10×** (a wrong entry then costs ~−2% not −8.7%). **Kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (66% of loss).** Keep EMA_CONF as the template. Options: defined-risk spreads to escape the fee drag.
- **Verdict:** #8 (aggressive 25–100× futures) **❌ DEAD** (18 burns / −$18.6k closed). #6 (OTM selling) **⚠️ break-even/dead** (n=543, fee-bound, no edge). #5 dead. No strategy verdict change without a clean entry-filter + leverage-cap rebuild.

### 2026-06-08 20:40 UTC — check-in `[updated by: Cowork]`
**Same hour as the monitor's 20:39 entry; my independent queries corroborate it exactly. Lab STABLE for a full hour post-refill — no insolvency, no new burn. Futures balance ≈ $334.19, bled −$279 this hour at the normal ~−$280/hr rate. Verdict unchanged, 26th run. Adds the engine-bug status check the 20:39 entry skipped.**

- **What's happening:** `bot_status` last write **2026-06-08 20:39:05 UTC** (~1.7 min before db now 20:40:51, FRESH), `is_paused=true`, `is_running=true`, `bot_state="paused"`, `pause_reason="PAPER-ONLY mode (no live trading)"`, **market_regime=TRENDING_DOWN** (flipped back from SIDEWAYS at 19:40). 30 status writes last hour, 0 live `options_scalp` → paper-only. Open: **futures 3, options 9.** Lanes active: 5 FUT_* + 5 OPT_SELL_*.
- **What happened since last check (19:40/19:42, ~60 min):**
  - **Futures:** funded **$19,000 (18 burns, NO new burn #19)**. Closed 979 → **989 (+10)**. Net −$18,386.63 → **−$18,665.81 (−$279.18; ~−$280/hr, normal)**. Balance **$612.88 → $334.19** (thin but > $50). Last-1h 16 closes −$279; last-24h **487 closes −$9,765** (the gap bleed still in the trailing window).
  - **Options (SELL):** funded $1,000. Net −$290.39 → **−$287.47 (+$2.92, flat)**. Balance **$712.53**. Closed count reads 531 vs the 564 logged at 19:40 — a counting/reclass artifact (net is unchanged), not new closes.
  - Per-lane futures (n=989): **FUT_MOMENTUM_CONF** 429cl/13.1%/**−$8,340.70**/67.3×/4.7m; **FUT_DONCHIAN_100X** 112/14.3%/−$4,142.94/100×/2.2m; **FUT_DONCHIAN_CONF** 104/24.0%/−$2,127.94/56.3×/5.5m; **FUT_DONCHIAN_50X** 107/18.7%/−$2,085.09/50×/4.9m; **FUT_EMA_CONF** 237/33.3%/−$1,969.14/29.9×/9.8m. Worst: **MOMENTUM_CONF = 44.7% of futures loss; MOMENTUM_CONF + DONCHIAN_100X = −$12,483.64 = 66.9%** (shape unchanged, 26th run). Least-bad: **EMA_CONF (33.3% win, lowest lev 29.9×).**
  - Options per-lane: OPT_SELL_PUT_FAR 142/7.0%/−$78.38, OPT_SELL_PUT 137/15.3%/−$63.57, OPT_SELL_CALL 89/13.5%/−$60.69, OPT_SELL_NEUTRAL 113/18.6%/−$48.72, OPT_SELL_CALL_FAR 50/16.0%/−$36.10. Avg fees $0.57–0.59, avg peak 0.15–0.79%.
- **The new thing:** stability held a second consecutive read (monitor's 20:39 + this 20:40). The operational fire is out; the refill loop works via the scheduled task. Only remaining item is strategy. `paper_stop` cohort widened to **−$20,359.57 (552 trades, 109% of net loss, avg peak +1.52%)** while the profitable `paper_trail`+`paper_max_hold` cohort held **+$2,166.10** (n=396) — the entry/exit split is the cleanest and most stable signal in the lab, intact 26 runs.
- **What we should change:**
  1. **Strategy (unchanged):** attack ENTRIES not exits — pullback/retest before breakout entry and **cap leverage ≤10×** (wrong entry then costs ~−2% not ~−8.7%). **Kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (66.9% of loss).** Keep EMA_CONF as template. Options: defined-risk spreads to escape fee drag.
  2. **Known-bug status (vs 06-06):** (a) **option-sell fee-on-notional — STILL PRESENT:** avg fee $0.58 ≈ the entire per-trade loss (net −$287.47 / 531 ≈ −$0.54), so ~100% of options PnL is fees. (b) **`sell_breached` 15–25m exit — not separately queried this run**, but options avg peak 0.15–0.79% confirms sells almost never reach profit (consistent with the bug). (c) **futures `paper_max_hold` ~30m clip — not the driver:** max_hold cohort only 16 trades but +$1,495 @ +49.45% peak, holds avg 2–10m, so the cap rarely binds; `paper_stop` (entries) remains the structural killer. None of the three appear fixed.
- **Verdict:** #8 (aggressive 25–100× futures) **❌ DEAD** (−$18.7k closed across 18 burns); #6 (OTM selling) **⚠️ break-even/dead, fee-bound** (n=531, no lane with edge); #5 dead. No strategy verdict change without a clean entry-filter + leverage-cap rebuild.

### 2026-06-08 20:39 UTC — first stable post-refill hour, NO new burn `[updated by: alpha-paper-lab-monitor]`
**The 11-burn catch-up at 19:42 held. Futures balance sits at ≈ $334.19 (funded $19,000, 18 burns, closed net −$18,665.81) — bled only −$282 this hour (16 closes), no burn #19. First non-insolvent, non-refill check-in in three runs. Live OFF, bot_status FRESH (20:37 UTC, 1.7 min old). Verdict unchanged, 25th run.**

- **Live/cadence:** `is_paused=true`, `is_running=true`, `bot_state="paused"`, `scalp_enabled`/`options_scalp_enabled=true` but **0 options_scalp trades last hour** → paper-only confirmed. Cadence normal (~57 min since 19:42). Last 1h: futures 17 opened / 16 closed / **−$282**; options 6 opened / 0 closed.
- **Balances:** Futures **$334.19** (= $19,000 − $18,665.81; thin but > $50, **no auto-refill**). Options **$712.53** (funded $1,000, 0 burns, closed n=531, net −$287.47; ~flat vs −$290 last run).
- **Per-lane — Futures (n=989):**

| Lane | Closed | Win% | Net | Avg peak% | Max peak% | Avg hold |
|---|---|---|---|---|---|---|
| **FUT_MOMENTUM_CONF** | 429 | 13% | **−$8,341** | 8.65 | 326.56 | 5m |
| FUT_DONCHIAN_100X | 112 | 14% | −$4,143 | 8.78 | 57.90 | 2m |
| FUT_DONCHIAN_CONF | 104 | 24% | −$2,128 | 7.96 | 78.60 | 5m |
| FUT_DONCHIAN_50X | 107 | 19% | −$2,085 | 6.39 | 35.89 | 5m |
| FUT_EMA_CONF | 237 | 33% | −$1,969 | 5.76 | 133.43 | 10m |

  Worst: **MOMENTUM_CONF = 45% of all futures loss; MOMENTUM_CONF + DONCHIAN_100X = −$12,484 = 67%** (shape unchanged, 25th run). Least-bad: **EMA_CONF (33% win, lowest lev).**
- **Per-lane — Options SELL (n=531):** OPT_SELL_PUT_FAR 142/7%/−$78, OPT_SELL_PUT 137/15%/−$64, OPT_SELL_CALL 89/13%/−$61, OPT_SELL_NEUTRAL 113/19%/−$49, OPT_SELL_CALL_FAR 50/16%/−$36. Avg peak 0.2–0.8%. Flat fee-bound noise, no lane with edge.
- **Exit-cohort split (n=989):** `paper_stop` **552 trades, −$20,360, avg PEAK +1.52%, avg realized −8.68%** = **109% of total futures loss** — wrong-direction entries that never reach the money, then exit at −8.7% under leverage. Profitable cohort still positive: `paper_trail` **+$671** (n=380, +15.40% peak) + `paper_max_hold` **+$1,495** (n=16, +49.45% peak) = **+$2,166**. Exits make money; entries are the entire problem, 25 runs running.
- **The new thing:** the lab is finally *stable* (refill loop confirmed working via the scheduled task; balance held a full hour without a burn). That removes the operational fire of the last three runs — the only open item is now purely the strategy: nothing about the entry quality has changed.
- **What to change (unchanged, 25th run):** attack ENTRIES not exits — require pullback/retest before breakout entry and **cap leverage ≤10×** (a wrong entry would cost ~−2% not −8.7%). **Kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (67% of loss).** Keep EMA_CONF as the template. Options: defined-risk spreads to escape the fee drag.
- **Verdict:** #8 (aggressive 25–100× futures) **❌ DEAD** (18 burns / −$18.7k in ~2 days). #6 (OTM selling) **⚠️ break-even/dead** (n=531, fee-bound, no edge). #5 dead. No strategy verdict change without a clean entry-filter + leverage-cap rebuild.

### 2026-06-08 19:42 UTC — AUTO-REFILL FIRED `[updated by: alpha-paper-lab-monitor]`
**The insolvency the 18:46 + 19:40 entries flagged is now RESOLVED. This scheduled-task run is authorized for step-3 auto-refill (the two Cowork entries below ran append-only and could not), so I executed 11 catch-up refills = BURNS #8–#18.** Futures funded **$8,000 → $19,000**; balance **−$10,387.12 → +$612.88**; burns **7 → 18**. Each `paper_deposits` row noted "gap catch-up; bal was -$10,387". The 11 burns accurately bank the ~$10.4k of damage from the 27h-stall window.

- **Data is the same hour as the 19:40 entry** (futures closed n≈981, net −$18,387.12; options n=573, net −$290.68 — full lane tables in the 19:40 entry below, unchanged shape). Last 1h futures: 12 trades −$215; last 24h: 488 trades **−$9,801** (the gap bleed). Live OFF: `is_paused=true`, `pause_reason=PAPER-ONLY`, 0 `options_scalp`/hr, bot_status fresh 19:39 UTC.
- **Diagnosis unchanged (24th run):** `paper_stop` 546/0% win/**−$20,168** @ +1.52% avg peak = 110% of loss (entries noise-stopped before reaching money); profitable `paper_trail`+`paper_max_hold` = +$2,215. MOMENTUM_CONF + DONCHIAN_100X = 67% of loss.
- **Change:** attack ENTRIES (pullback/retest), **cap leverage ≤10×**, kill MOMENTUM_CONF + DONCHIAN_100X, keep EMA_CONF as template. Operationally: refill now confirmed working via this task; the open issue is just scheduler reliability (don't let runs stall 27h).
- **Verdict:** #8 (aggressive 25–100× futures) **❌ DEAD** — 18 burns / −$18.4k in ~2 days is definitive (confirms #5). #6 (OTM selling) **⚠️ break-even/dead**, fee-bound.

### 2026-06-08 19:40 UTC — check-in `[updated by: Cowork]`
**Hourly cadence RESTORED (54 min since last check vs the prior 27h gap). Bleed back to a normal ~−$240/hr, not the gap-rate. Futures lab STILL INSOLVENT at ≈ −$10,387 balance — no refill fired again (append-only scope; flagging for owner). market_regime flipped TRENDING_DOWN → SIDEWAYS. Verdict unchanged, 24th run.**

- **What's happening:** `bot_status` last write **2026-06-08 19:39:04 UTC** (~1 min old, FRESH), `is_paused=true`, `bot_state="paused"`, `pause_reason="PAPER-ONLY mode (no live trading)"`, `market_regime=SIDEWAYS`. Live engine off (paper only). Open: **futures 2** (down from 10), **options 9**. Lanes active: 5 FUT_* + 5 OPT_SELL_*.

- **What happened since last check (~54 min):**
  - **Futures:** funded still **$8,000 (no new refill, last 06-07 15:39)**. Closed 961 → **979 (+18)**. Net −$18,168.79 → **−$18,386.63 (−$217.84; ≈−$240/hr — normal hourly rate, gap is over)**. Balance **≈ −$10,386.63 (insolvent, status unchanged)**. The +18 closes were only MOMENTUM_CONF (+8) and EMA_CONF (+10); the three DONCHIAN lanes idle this hour.
  - **Options (SELL):** funded $1,000. Closed 518 → **564 (+46)**. Net −$281.78 → **−$290.39 (−$8.61)**. Balance **≈ $709.61**.
  - Per-lane futures (n=979): **FUT_MOMENTUM_CONF** 425cl/13.4%/**−$8,188.08**/67.4×/4.6m; **FUT_DONCHIAN_100X** 110/14.5%/−$4,083.07/100×/2.2m; **FUT_DONCHIAN_CONF** 104/24.0%/−$2,127.94/56.3×/5.5m; **FUT_DONCHIAN_50X** 105/19.0%/−$2,078.17/50×/4.9m; **FUT_EMA_CONF** 235/33.6%/−$1,909.37/29.9×/9.7m. Worst: **MOMENTUM_CONF = 44.5% of all futures loss; MOMENTUM_CONF + DONCHIAN_100X = −$12,271 = 66.7%** (shape unchanged, 24th run). Best/least-bad: **EMA_CONF (33.6% win, lowest lev 29.9×)**.
  - Options per-lane: OPT_SELL_PUT_FAR 148cl/6.8%/−$79.61, OPT_SELL_PUT 143/14.7%/−$65.95, OPT_SELL_CALL 92/17.4%/−$57.67, OPT_SELL_NEUTRAL 123/18.7%/−$51.04, OPT_SELL_CALL_FAR 58/17.2%/−$36.13. Avg fees $0.57–0.59/trade; avg peak 0.19–2.89%.

- **The new thing:**
  1. **Cadence fixed but refill still not firing.** The 27h-gap problem is gone (hourly run resumed, bleed normalized to ~−$240/hr), but the futures lab has now sat insolvent (≈ −$10.4k) across two consecutive checks with no auto-refill. So the prior stall was the *scheduler*; refill itself appears separately broken or disabled. Operational flag stands.
  2. **Exit-cohort split intact (n=979):** `paper_stop` **546 trades, −$20,168.46 (110% of total futures loss), avg PEAK +1.52%** — wrong-direction entries that never reach the money. Profitable cohort still positive: `paper_trail` **+$708.58** (n=374, +15.52% peak) + `paper_max_hold` **+$1,506.11** (n=15, +52.54% peak) = **+$2,214.69**, though it gave back ~$17 this hour (a trail exit round-tripped). Entries remain the entire problem, 24 runs.
  3. **Regime shift to SIDEWAYS** is the worst tape for these breakout/momentum lanes — expect paper_stop to keep dominating until an entry filter lands.

- **What we should change:**
  1. **Operational:** the refill loop is the active bug now (not cadence). Decouple/repair auto-refill so the lab can't run insolvent indefinitely. (Did NOT refill — append-only scope.)
  2. **Strategy (unchanged, 24th run):** attack ENTRIES not exits — require pullback/retest before breakout entry and **cap leverage ≤10×**. **Kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (66.7% of loss).** Keep EMA_CONF as template. More urgent now that regime = SIDEWAYS.
  3. **Known-bug status (vs 06-06):** (a) option-sell fee-on-notional — **STILL PRESENT** (avg fee $0.58 ≈ per-trade loss $0.515, ~100% of options PnL is fees); (b) `sell_breached` 15–25m exit — not separately queried this run, but options avg peak 0.19–2.89% confirms sells almost never reach profit; (c) futures `paper_max_hold` ~30m clip — max_hold cohort only 15 trades but +$1,506 @ +52.54% peak, avg holds 2–10m, so most exits are stop/trail before the cap; clipping plausibly present but not the driver. **paper_stop (entries) remains the structural killer.**

- **Verdict:** #8 (aggressive futures) **❌ DEAD** (≈ −$10.4k insolvent, refill not firing); #6 (OTM selling) **⚠️ break-even/dead** (n=564, no lane with edge, fee-bound); #5 dead. No strategy verdict change without a clean entry-filter + leverage-cap rebuild.

### 2026-06-08 18:46 UTC — check-in `[updated by: Cowork]`
**27-HOUR GAP since last check (06-07 15:39) — routine did not run in between. NO auto-refill fired in that window, so the futures lab ran unattended into deep negative: balance now ≈ −$10,168.79 (funded $8,000, closed −$18,168.79). This is the headline anomaly. Verdict unchanged (23rd run).**

- **What's happening:** `bot_status` last write **2026-06-08 18:45:07 UTC** (~1.5 min old, FRESH), `is_paused=true`, `bot_state="paused"`, `pause_reason="PAPER-ONLY mode"`, `market_regime=TRENDING_DOWN`. **0 live `options_scalp` trades** — live engine off, paper engine active. Open paper trades: **futures 10** (MOMENTUM_CONF 3, EMA_CONF 7), **options 47** (across all 5 SELL lanes). Lanes active: 5 futures FUT_* + 5 options SELL.

- **What happened since last check (~27.1h):**
  - **Futures:** funded still **$8,000 (8 deposits, last 06-07 15:39 — NO new refill)**. Closed n: 419 → **961** (+542). Net: −$7,492.92 → **−$18,168.79** (−$10,675.87 more; ≈ **−$394/hr** avg, in line with prior runs). Balance pre-any-refill **≈ −$10,168.79** — the lab has been insolvent and kept trading because no burn/refill executed.
  - **Options (SELL):** funded $1,000. Closed n: 189 → **518** (+329). Net: −$106.08 → **−$281.78** (−$175.70). Balance **≈ $718.22**.
  - Per-lane futures (cumulative, n=961): **FUT_MOMENTUM_CONF** 417cl/13.4%/**−$8,054.08**/67.6×/4.6m; **FUT_DONCHIAN_100X** 110/14.5%/−$4,083.07/100×/2.2m; **FUT_DONCHIAN_CONF** 104/24.0%/−$2,127.94/56×/5.5m; **FUT_DONCHIAN_50X** 105/19.0%/−$2,078.17/50×/4.9m; **FUT_EMA_CONF** 225/33.8%/−$1,825.53/30×/9.6m. Worst: **MOMENTUM_CONF = 44% of all futures loss; MOMENTUM_CONF + DONCHIAN_100X = −$12,137 = 67%** (unchanged shape, 23rd run). Best/least-bad: **EMA_CONF (33.8% win, lowest lev 30×)**.
  - Options per-lane: OPT_SELL_PUT_FAR 142cl/7.0%/−$78.38, OPT_SELL_PUT 136/15.4%/−$63.22, OPT_SELL_CALL 78/14.1%/−$55.11, OPT_SELL_NEUTRAL 113/18.6%/−$48.72, OPT_SELL_CALL_FAR 49/14.3%/−$36.35. Avg fees ~$0.58/trade, avg peak only 0.15–0.80%.

- **The new thing:**
  1. **Operational, not strategy:** the check-in/refill loop stalled for 27h. With auto-refill tied to this routine, the futures lab sat at ≈ −$10.2k balance the whole time. If burns are supposed to fire from here, ~17–18 refills' worth of damage accrued un-actioned. Flag the scheduler, not the model.
  2. **Exit-cohort split sharper than ever (n=961):** `paper_stop` **540 trades, −$20,003.80 (110% of total futures loss), avg PEAK +1.53%** — wrong-direction entries that never reach the money. Profitable cohort intact and GROWING: `paper_trail` **+$725.75** (n=370, +15.58% peak) + `paper_max_hold` **+$1,506.11** (n=15, +52.54% peak) = **+$2,231.86**. Exits work; entries are the entire problem. Unbroken 23 runs.
  3. **Options:** avg fee (~$0.58) ≈ the entire per-trade loss (−$0.54/trade); peaks near 0% mean premium sells almost never reach profit. Fee drag + sells-never-profit pattern persists.

- **What we should change:**
  1. **Operational first:** restore the hourly cadence / decouple auto-refill from the check-in run so the lab can't silently run insolvent for a day. (Did NOT refill this run — task scope is append-only; flagging for the owner.)
  2. **Strategy (unchanged, 23rd run):** attack ENTRIES, not exits — require pullback/retest before breakout entry and **cap leverage ≤10×** (a wrong entry then costs ~−2% not −8%). **Kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (67% of loss).** Keep EMA_CONF as template.
  3. **Known-bug status (as of 06-06):** (a) option-sell fee-on-notional — **STILL PRESENT** (fees ≈ 100% of options PnL); (b) `sell_breached` 15–25m exit — not separately queried this run; (c) futures `paper_max_hold` ~30m clipping trends — holds remain 2–10m and max_hold cohort is only 15 trades but +$1,506, so most exits are stop/trail before the cap; clipping plausibly still present but not the main driver. paper_stop (entries) remains the structural killer.

- **Verdict:** #8 (aggressive futures) **❌ DEAD** (now ≈ −$10.2k insolvent, no refill); #6 (OTM selling) **⚠️ break-even/dead** (n=518, no lane with edge, fee-bound); #5 dead. No strategy verdict change without a clean entry-filter + leverage-cap rebuild.

### 2026-06-07 15:39 UTC — bleed RE-ACCELERATES to −$405/hr (≈2× last hour's −$208) → **BURN #7** (bal hit −$492.92, refilled, funded now $8k); BOTH cohorts bled — fresh paper_stop wrongs −$372 (92% of hour) AND profit cohort gave back (paper_trail −$33 incl a MOMENTUM_CONF +55.82% peak that ROUND-TRIPPED to a loss); cumulative paper_stop −$8,153 n=231 @ +1.49% peak = 109% of loss; MOMENTUM_CONF −$2,976 = 40%, +100X = 65%; verdict unchanged 22nd run `[updated by: Cowork]`

**Live OFF** — `bot_status` last write **2026-06-07 15:37:04 UTC** (FRESH, ~2 min old), `is_paused=true`, `is_running=true`; **0 live `options_scalp` trades last hour**. Paper engine active (23 futures closed last hour, 0 options). Tree left clean.

**Balances & burns:**

| Lab | Funded | Closed P/L | Balance | Burns | Action |
|---|---|---|---|---|---|
| Futures | $8,000 (orig $1k + 7 refills) | −$7,492.92 | **$507.08** (post-refill) | 7 | **auto-refill burn #7** (pre-refill −$492.92 ≤ $50) |
| Options | $1,000 | −$106.08 | **$893.92** | 0 | none (> $50) |

**Hour-over-hour:** Futures closed **23 for −$404.83** — bleed roughly DOUBLED vs last hour's −$207.93 and the thin $97.77 cushion went negative (−$492.92) → burn #7, funded $7k → $8k. Options 0 closed this hour (n=189 cum, −$106.08).

**Per-lane — Futures (cumulative, n=419):**

| Lane | Closed | Win% | Net | Avg peak% | Max peak% | Avg lev |
|---|---|---|---|---|---|---|
| **FUT_MOMENTUM_CONF** | 165 | 16% | **−$2,975.94** | 8.72 | 114.00 | 68× |
| FUT_DONCHIAN_100X | 56 | 13% | −$1,874.99 | 8.62 | 57.90 | 100× |
| FUT_EMA_CONF | 95 | 29% | −$1,034.50 | 4.33 | 24.45 | 29× |
| FUT_DONCHIAN_50X | 52 | 27% | −$808.52 | 7.26 | 35.89 | 50× |
| FUT_DONCHIAN_CONF | 51 | 27% | −$798.97 | 7.92 | 72.75 | 55× |

Worst: **FUT_MOMENTUM_CONF −$2,976 (40% of all futures losses; worst lane 22nd straight run)**. MOMENTUM_CONF + DONCHIAN_100X = **−$4,851 = 65% of the loss**. Best win-rate (least-bad): **FUT_EMA_CONF (29% win, 29× lev)**, then DONCHIAN_50X/CONF (27%).

**This hour's lane split (since 14:39):** MOMENTUM_CONF −$167.61 (13, incl a **+55.82% peak round-trip to a loss**), DONCHIAN_100X −$109.90 (2, +4.26% peak), EMA_CONF −$55.48 (6, +8.21% noise-stop), DONCHIAN_50X −$40.24 (1, +4.91%), DONCHIAN_CONF −$31.59 (1, +1.00%). No lane positive.

**Exit-reason cohort (cumulative, n=419):**

| Exit reason | Closed | Net | Avg peak% |
|---|---|---|---|
| **paper_stop** | 231 | **−$8,153.02** | **+1.49** |
| ema21_lost | 9 | −$127.76 | +1.66 |
| ema21_reclaimed | 8 | −$100.06 | +2.48 |
| donchian_mid_revert | 1 | −$12.72 | +4.93 |
| **paper_trail** | 165 | **+$309.42** | +14.83 |
| **paper_max_hold** | 5 | **+$591.22** | +56.84 |

1. **`paper_stop` is now −$8,153 across 231 trades = 109% of the entire futures loss, avg PEAK +1.49%.** Wrong-direction entries that never reach the money, exiting deep negative under 25–100× lev — the structural driver, unchanged for 22 runs. This hour paper_stop alone was −$371.88 (11 trades, max peak only +4.91%) = 92% of the hour's −$404.83.
2. **New wrinkle this hour: the profit cohort ALSO bled.** `paper_trail` went +$342.37 → **+$309.42** (gave back ~$33), because a MOMENTUM_CONF trade peaked **+55.82%** then round-tripped and exited via trail at a loss. The trail still banks ~ when entries are right, but high-lev round-trips can flip a trail-exit negative. `paper_max_hold` flat at +$591.22 (n=5).
3. **STRATEGY verdict confirmed (not engine bug).** Fees/sizing/liq/holds sane; profit cohort cumulatively still net +$900.64 proves exit logic works. Defect = entry filter (breakouts chopped on crypto noise) × 25–100× leverage.
4. **Options clean non-result** at n=189, −$106.08 — long puts −$99.56 (6% win, the drag), short calls −$6.52 (43% win). No lane with edge.

**What to change (single highest-leverage move):**
1. **Attack the entries + cap leverage ≤10×.** Require a pullback/retest before breakout entry (stop chasing). At ≤10× a wrong entry costs ~−2% not −8%, AND a +55% round-trip can't flip a trail-exit deeply negative. Throttle/kill **FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (65% of the loss)**.
2. Carry-over: defined-risk spreads on options; long-put buying (6% win) is dead.

**Verdict status:** unchanged, 22nd run. #8 (aggressive futures) **❌ DEAD** (now **7 full-bankroll burns**); #6 (OTM selling) **⚠️ break-even/dead** (n=189, no signal); #5 dead.

### 2026-06-07 14:39 UTC — bleed EASES to −$208/hr (from −$553; no burn #7, bal THIN $97.77); shape shifts — this hour's losers ROUND-TRIPPED (MOMENTUM/100X peaked +17.6%/+15.2% then gave it back) rather than the usual never-in-money wrongs; profit cohort RECOVERED +$35.64; cumulative paper_stop −$7,781 n=220 @ +1.49% peak = 113% of loss; MOMENTUM_CONF −$2,677 = 39%, +100X = 64%; verdict unchanged 21st run `[updated by: Cowork]`

**Live OFF** — `bot_status` last write **2026-06-07 14:39:06 UTC** (FRESH, 0 min old), `is_paused=true`, `is_running=true`; **0 live `options_scalp` trades last hour**. Paper engine active (23 futures + 5 options closed last hour). Tree left clean.

**Balances & burns:**

| Lab | Funded | Closed P/L | Balance | Burns | Action |
|---|---|---|---|---|---|
| Futures | $7,000 (orig $1k + 6 refills) | −$6,902.23 | **$97.77** | 6 | none (> $50, but THIN → burn #7 likely soon) |
| Options | $1,000 | −$115.77 | **$884.23** | 0 | none (> $50) |

**Hour-over-hour:** Futures closed **23 for −$207.93** — bleed roughly thirds vs last hour's −$552.68. Balance $134.38 → **$97.77** (−$37 net incl. options). Options 5 closed for −$4.01 (n=236 cum, −$115.77). No burn #7; cushion is razor-thin.

**Per-lane — Futures (cumulative, n=406):**

| Lane | Closed | Win% | Net | Avg peak% | Max peak% | Avg lev |
|---|---|---|---|---|---|---|
| **FUT_MOMENTUM_CONF** | 155 | 17% | **−$2,676.96** | 8.73 | 114.00 | 68× |
| FUT_DONCHIAN_100X | 55 | 15% | −$1,763.28 | 8.78 | 57.90 | 100× |
| FUT_EMA_CONF | 93 | 28% | −$994.28 | 4.20 | 24.45 | 30× |
| FUT_DONCHIAN_CONF | 51 | 27% | −$769.39 | 7.92 | 72.75 | 55× |
| FUT_DONCHIAN_50X | 52 | 29% | −$762.45 | 7.26 | 35.89 | 50× |

Worst: **FUT_MOMENTUM_CONF −$2,677 (39% of all futures losses; worst lane 21st straight run)**. MOMENTUM_CONF + DONCHIAN_100X = **−$4,440 = 64% of the loss**. Best win-rate (least-bad): **FUT_DONCHIAN_50X (29% win)**, then EMA_CONF (28%, 30× lev).

**This hour's lane split (since 13:39):** MOMENTUM_CONF −$79.48 (8, **+17.63% peak**), DONCHIAN_100X −$68.13 (4, **+15.17% peak**), EMA_CONF −$54.52 (5, +4.89% noise-stop), DONCHIAN_CONF −$38.32 (4, +7.94%), DONCHIAN_50X −$21.89 (3, +8.91%). **Note the shift:** the two high-lev lanes peaked +15–18% this hour then round-tripped — gains given back, not the usual +1.5% never-in-money wrongs. No lane positive.

**Exit-reason cohort (cumulative, n=406):**

| Exit reason | Closed | Net | Avg peak% |
|---|---|---|---|
| **paper_stop** | 220 | **−$7,781.14** | **+1.49** |
| ema21_lost | 9 | −$127.76 | +1.66 |
| ema21_reclaimed | 8 | −$100.06 | +2.48 |
| **paper_trail** | 153 | **+$342.37** | +14.89 |
| **paper_max_hold** | 5 | **+$591.22** | +56.84 |

1. **`paper_stop` is now −$7,781 across 220 trades = 113% of the entire futures loss, avg PEAK +1.49%.** Wrong-direction entries that never reach the money, exiting deep negative under 25–100× lev. This hour paper_stop alone was −$243.47 (6 trades) = 117% of the hour's −$208 net.
2. **The profitable exit cohort RECOVERED this hour: paper_trail+max_hold +$35.64 (was ~$0 stalled last hour), now +$933.59 cumulative** (+$342.37 @ +14.89% peak; +$591.22 @ +56.84% peak). The eased bleed = this cohort earning again, NOT fewer wrong entries. Exit logic is sound; entries are the entire problem.
3. **STRATEGY verdict confirmed (not engine bug)** for the 21st straight run. Fees/sizing/liq/holds sane. Defect = entry quality amplified by leverage. The round-trip variant this hour (peak +17% → loss) further argues for a tighter trailing trigger on the high-lev lanes, but the structural fix remains entries + leverage cap.
4. **Options clean non-result** (n=236, −$115.77). Short PUTs worst (OPT_SELL_PUT 6% win −$42.63, OPT_SELL_PUT_FAR 4% win −$39.02, OPT_SELL_NEUTRAL 14% −$22.70); short CALLs near-flat (OPT_SELL_CALL 47% win −$6.09, OPT_SELL_CALL_FAR 32% −$5.23). Call-side selling is the only lane that doesn't materially bleed.

**What to change (single highest-leverage move):**
1. **Attack entries, not exits.** Require a pullback/retest before breakout entry and cap leverage ≤10× so a wrong entry costs ~−2% not −8%. The +$934 profitable trail/max-hold cohort proves the exit side already works — fix entries and the lab flips.
2. **Kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X** (64% of the loss, both <18% win). Keep EMA_CONF/DONCHIAN_50X only with leverage capped.
3. Carry-over: short-CALL / call-side selling is the only options edge worth a defined-risk test; abandon the PUT side.

**Verdict status:** unchanged. #8 (aggressive futures) **❌ DEAD** (6 full-bankroll burns, balance thin at $97.77); #6 (OTM selling) **⚠️ break-even / call-side only** (n=236); #5 dead. Easing this hour is exit-cohort recovery, not entry improvement — the fix is still the entry filter + leverage cap.

### 2026-06-07 13:39 UTC — bleed RE-ACCELERATES HARD (−$553/hr, worst since burn hours; "nearly stopped −$36" last hour fully reversed); no burn #7 but futures balance now THIN at $134.38; 100% of this hour's damage = fresh `paper_stop` wrong entries while the profitable exit cohort STALLED flat (+$898 cum, ~$0 this hr); MOMENTUM_CONF gave back ALL of last hour's +$272 gain; verdict unchanged 20th run `[updated by: Cowork]`

**Live OFF** — `bot_status` last write **2026-06-07 13:37:03 UTC** (FRESH, 2 min old), `is_paused=true`, `bot_state="paused"`; no live `options_scalp` activity. Paper engine active (22 futures + 2 options closed last hour). Tree left clean.

**Balances & burns:**

| Lab | Funded | Closed P/L | Balance | Burns | Action |
|---|---|---|---|---|---|
| Futures | $7,000 (orig $1k + 6 refills) | −$6,865.62 | **$134.38** | 6 | none (> $50, but thin → burn #7 likely next hr) |
| Options | $1,000 | −$111.76 | **$888.24** | 0 | none (> $50) |

**Hour-over-hour:** Futures closed **22 for −$552.68** — a sharp reversal from last hour's −$36 (the "nearly stopped" read did not hold). Balance $733.59 → **$134.38** (−$599 incl. options). Options 2 closed for −$11.04 (n=228 cum, −$111.76). No burn #7 yet but the cushion is nearly gone.

**Per-lane — Futures (cumulative, n=382):**

| Lane | Closed | Win% | Net | Avg peak% | Max peak% | Avg lev |
|---|---|---|---|---|---|---|
| **FUT_MOMENTUM_CONF** | 147 | 16% | **−$2,681.17** | 7.87 | 114.00 | 68× |
| FUT_DONCHIAN_100X | 51 | 12% | −$1,751.29 | 8.28 | 57.90 | 100× |
| FUT_EMA_CONF | 89 | 29% | −$925.95 | 4.18 | 24.45 | 30× |
| FUT_DONCHIAN_CONF | 47 | 26% | −$760.64 | 7.92 | 72.75 | 55× |
| FUT_DONCHIAN_50X | 48 | 27% | −$746.40 | 7.21 | 35.89 | 50× |

Worst: **FUT_MOMENTUM_CONF −$2,681 (39% of all futures losses; worst lane 20th straight run)** — and this hour it round-tripped, giving back ALL of last hour's +$272 (−$270.80 this hr @ only +2.76% peak). MOMENTUM_CONF + DONCHIAN_100X = **−$4,432 = 65% of the loss**. Least-bad by win-rate: **FUT_EMA_CONF (29% win, 30× lev)** — but it was actually this hour's #2 damage (−$110 @ +1.55% peak = noise-stopped again).

**This hour's lane split (since 12:39):** MOMENTUM_CONF −$270.80 (10, +2.76% peak, round-trip), EMA_CONF −$110.24 (6, +1.55%, noise-stop), DONCHIAN_100X −$91.72 (2, +4.73%), DONCHIAN_CONF −$63.28 (2, +1.09%), DONCHIAN_50X −$16.65 (2). No lane positive.

**Exit-reason cohort (cumulative, n=382) — the split is now decisive and unchanged in shape:**

| Exit reason | Closed | Net | Avg peak% |
|---|---|---|---|
| **paper_stop** | 215 | **−$7,592.01** | **+1.42** |
| ema21_lost | 9 | −$127.76 | +1.66 |
| ema21_reclaimed | 6 | −$77.14 | +1.69 |
| **paper_trail** | 139 | **+$313.81** | +14.66 |
| **paper_max_hold** | 4 | **+$584.14** | +69.72 |

1. **`paper_stop` is now −$7,592 across 215 trades = 111% of the entire futures loss, at avg PEAK +1.42%.** Wrong-direction entries that never reach the money, then exit deep negative under 25–100× leverage. **100% of this hour's −$553 came from this cohort** — the bleed re-accelerated purely because entries kept firing into chop.
2. **The profitable exit cohort (`paper_trail` +$313.81 @ +14.66% peak, `paper_max_hold` +$584.14 @ +69.72% peak) = +$897.95 combined, but it STALLED this hour (~$0).** Exits keep what entries hand them; when entries are wrong there's nothing to trail. Exit logic is sound — entries are the entire problem.
3. **STRATEGY verdict confirmed (not engine bug)** for the 20th straight run. Fees/sizing/liq/holds sane. The defect is entry quality amplified by leverage.
4. **Options clean non-result** (n=228, −$111.76). Short PUTs worst (OPT_SELL_PUT 4% win −$44, OPT_SELL_PUT_FAR 2% win −$39.55); short CALLs near-flat (OPT_SELL_CALL 53% win −$0.90, OPT_SELL_CALL_FAR 42% −$2.07). Selling-the-call side is the only lane that doesn't bleed.

**What to change (single highest-leverage move):**
1. **Attack entries, not exits.** Require a pullback/retest before breakout entry (stop chasing breakouts into noise) and cap leverage ≤10× so a wrong entry costs ~−2% not −8%. The +$898 profitable trail/max-hold cohort proves the exit side already works — fix entries and the lab flips.
2. **Kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X** (65% of the loss, both <16% win). Keep EMA_CONF only if leverage is capped — at 30× it still noise-stops.
3. Carry-over: short-CALL / call-side selling is the only options edge worth a defined-risk test; abandon the PUT side.

**Verdict status:** unchanged. #8 (aggressive futures) **❌ DEAD** (6 full-bankroll burns, balance thin again); #6 (OTM selling) **⚠️ break-even / call-side only** (n=228); #5 dead. Re-acceleration this hour reaffirms: it is the entry filter, not the exit, not the engine.

### 2026-06-07 12:39 UTC — bleed NEARLY STOPS (−$36/hr, best hour since burn #5; no burn #7, bal $733.59); the profitable exit cohort RECOVERED (paper_trail+max_hold +$899 cum, +$357 this hr) which offset fresh paper_stop damage; `bot_status` is now **reporting FRESH again** (12:39 UTC, is_paused=true) after ~3 months stale; verdict unchanged 19th run `[updated by: Cowork]`

**Live OFF** — `bot_status` last write **2026-06-07 12:39:08 UTC** (FRESH — the row resumed updating after being stale since 2026-03-11), `is_paused=true`, `pause_reason="PAPER-ONLY mode (no live trading)"`; **0 `options_scalp` trades last hour** confirms no live activity. Paper engine active (28 futures closed last hour). Tree left clean.

**Balances & burns:**

| Lab | Funded | Closed P/L | Balance | Burns | Action |
|---|---|---|---|---|---|
| Futures | $7,000 (orig $1k + 6 refills) | −$6,266.41 | **$733.59** | 6 | none (> $50) |
| Options | $1,000 | −$110.46 | **$889.54** | 0 | none (> $50) |

**Hour-over-hour:** Futures closed **28 for −$36.43** — the smallest hourly bleed in many runs (was −$410, −$559 prior hours). Options 8 closed for −$10.94 (n=227 cum, −$110.46). No burn #7; balance held near $734 all hour.

**Per-lane — Futures (cumulative, n=362):**

| Lane | Closed | Win% | Net | Avg peak% | Max peak% | Avg lev | Avg hold |
|---|---|---|---|---|---|---|---|
| **FUT_MOMENTUM_CONF** | 137 | 17% | **−$2,422.77** | 8.30 | 114.00 | 68× | 5.1m |
| FUT_DONCHIAN_100X | 50 | 12% | −$1,702.56 | 8.44 | 57.90 | 100× | 2.3m |
| FUT_EMA_CONF | 82 | 30% | −$829.52 | 4.36 | 24.45 | 29× | 10.9m |
| FUT_DONCHIAN_50X | 47 | 26% | −$734.91 | 7.04 | 35.89 | 50× | 6.5m |
| FUT_DONCHIAN_CONF | 46 | 26% | −$712.33 | 8.09 | 72.75 | 55× | 7.4m |

Worst: **FUT_MOMENTUM_CONF −$2,423 (39% of all futures losses; worst lane 19th straight run)** — though it actually gained ~+$272 this hour. MOMENTUM_CONF + DONCHIAN_100X = **−$4,125 = 66% of the loss**. Least-bad by win-rate: **FUT_EMA_CONF (30% win, 29× lev, peaks capped at 24×)**.

**Exit-reason breakdown (cumulative, n=362) — the bleed is entries, not exits:**

| Exit reason | Closed | Net | Avg peak% |
|---|---|---|---|
| **paper_stop** | 198 | **−$7,083.09** | **+1.44** |
| paper_trail | 135 | **+$314.59** | +14.80 |
| paper_max_hold | 4 | **+$584.14** | +69.72 |
| ema21_lost | 9 | −$127.76 | +1.66 |
| ema21_reclaimed | 6 | −$77.14 | +1.69 |
| donchian_mid_revert | 1 | −$12.72 | +4.93 |
| restart_orphan | 6 | −$2.45 | +1.82 |

1. **`paper_stop` = 113% of the entire futures loss** (198 trades, −$7,083, avg PEAK only +1.44%). Entries go wrong almost immediately and never reach the money — leveraged wrong-direction entries with no edge. Unbroken signal across 19 runs.
2. **`paper_trail` + `paper_max_hold` = NET POSITIVE +$899** (n=139, avg peak +14.80% / +69.72%). This cohort **recovered +$357 this hour** (was +$542) — that recovery, not fewer wrong entries, is why the hourly bleed nearly stopped. **Exit logic works, entry filter does not.**
3. **STRATEGY verdict (not engine bug)** — fees/sizing/liq/holds sane; defect is the entry filter (breakouts chopped on crypto noise) amplified by 25–100× leverage.
4. **Options** clean non-result (n=227, −$110.46). Notable tilt: **PUT-selling lanes worst** (OPT_SELL_PUT −$44 @ 4% win, OPT_SELL_PUT_FAR −$38 @ 2% win) while **CALL-selling is near flat** (OPT_SELL_CALL −$2 @ 53% win, OPT_SELL_CALL_FAR −$3 @ 37% win) — consistent with a downward-drifting tape punishing short puts.

**What to change (unchanged, 19th run):** Attack entries — require a pullback/retest before breakout entry and **cap leverage ≤10×** so a wrong entry costs ~−2% not −8%. Kill **FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X** (66% of loss). The profitable paper_trail/max_hold cohort proves the exit side already works.

**Verdict status:** unchanged. #8 (aggressive futures) **❌ DEAD** (6 full-bankroll burns); #6 (OTM selling) **⚠️ flat** (n=227, no signal; mild edge only on short calls); #5 dead.

### 2026-06-07 11:39 UTC — **BURN #6** (futures hit −$298.36 ≤ $50 → auto-refilled, funded now $7k); bleed eases to −$410/hr (was −$559); cohort split holds: paper_stop = 105% of loss (−$6,631, n=188, +1.36% avg peak) = wrong entries, vs paper_trail+max_hold NET POSITIVE +$542 (n=120) but gave back ~$41 this hr; verdict unchanged 18th run `[updated by: Cowork]`

**Live OFF** (`is_paused` reads false but `bot_status` is **stale — last write 2026-03-11**, ~3 months silent; **0 `options_scalp` trades last hour**). Paper engine active (18 futures closed last hour). Tree left clean.

**Balances:** Futures FUNDED $7,000 (orig $1k + **6 refills**), closed PnL −$6,298.36 → **BALANCE pre-refill −$298.36 → refill #6 → +$701.64**. Options FUNDED $1,000, closed PnL −$87.69 → BALANCE **$912.31** (0 burns).

**Hour-over-hour:** Futures closed 18 for **−$410.23** (bleed slows from last hour's −$559). Balance ran from +$111.87 through zero → burn #6. Options flat (n=173 cum, −$87.69).

**Per-lane — Futures (cumulative, n=323):**

| Lane | Closed | Win% | Net | Avg peak% | Max peak% | Avg hold |
|---|---|---|---|---|---|---|
| **FUT_MOMENTUM_CONF** | 129 | 15% | **−$2,694.96** | 7.40 | 108.44 | 4.8m |
| FUT_DONCHIAN_100X | 42 | 10% | −$1,503.97 | 7.48 | 57.90 | 2.3m |
| FUT_EMA_CONF | 75 | 31% | −$785.44 | 4.47 | 24.45 | 11.2m |
| FUT_DONCHIAN_50X | 39 | 18% | −$706.51 | 6.11 | 35.89 | 6.6m |
| FUT_DONCHIAN_CONF | 38 | 24% | −$607.49 | 7.82 | 72.75 | 7.8m |

Worst: **FUT_MOMENTUM_CONF −$2,695 (43% of all futures losses; worst lane 18th straight run)**. MOMENTUM_CONF + DONCHIAN_100X = **−$4,199 = 67% of the loss**. Least-bad by win-rate: **FUT_EMA_CONF (31% win, capped peaks at 24×, noise-stopped)**.

**Exit-reason breakdown (cumulative, n=323) — the bleed is entries, not exits:**

| Exit reason | Closed | Net | Avg peak% |
|---|---|---|---|
| **paper_stop** | 188 | **−$6,631.28** | **+1.36** |
| paper_trail | 118 | **+$252.13** | +14.56 |
| paper_max_hold | 2 | **+$290.25** | +67.93 |
| ema21_lost | 9 | −$127.76 | +1.66 |
| ema21_reclaimed | 5 | −$68.97 | +1.98 |
| donchian_mid_revert | 1 | −$12.72 | +4.93 |

1. **`paper_stop` = 105% of the entire futures loss** (188 trades, −$6,631, avg PEAK only +1.36%). Entries go wrong almost immediately and never reach the money — leveraged wrong-direction entries with no edge.
2. **`paper_trail` + `paper_max_hold` remain NET POSITIVE +$542** (n=120, avg peak +14.56% / +67.93%). Exits bank winners cleanly. The split is unbroken across 18 runs: **exit logic works, entry filter does not.** This hour the positive cohort gave back ~$41 (minor), all fresh damage still paper_stop.
3. **STRATEGY verdict (not engine bug)** — fees/sizing/liq/holds sane; defect is the entry filter (breakouts chopped on crypto noise) amplified by 25–100× leverage.
4. **Options** clean non-result (n=173, −$87.69) — no lane with edge.

**What to change (unchanged, 18th run):** Attack entries — require a pullback/retest before breakout entry and **cap leverage ≤10×** so a wrong entry costs ~−2% not −8%. Kill **FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X** (67% of loss). The profitable paper_trail/max_hold cohort proves the exit side already works.

**Verdict status:** unchanged. #8 (aggressive futures) **❌ DEAD** (now **6 full-bankroll burns**); #6 (OTM selling) **⚠️ flat** (n=173, no signal); #5 dead.

### 2026-06-07 10:39 UTC — bleed RE-ACCELERATES (−$559/hr, worst hour since burn #5; no burn #6, bal $111.87); the split is now starkest yet: ALL the damage is fresh `paper_stop` wrong entries while the profitable cohort STALLED — paper_stop = 107% of loss (−$6,277, n=177) vs paper_trail+max_hold NET POSITIVE +$583 (n=114, +$0 this hr); verdict unchanged 17th run `[updated by: Cowork]`

**Live OFF** (`is_paused` reads false but the entire `bot_status` row is **stale — last write 2026-03-11**, i.e. the live engine has not reported in ~3 months; **0 `options_scalp` trades last hour** confirms no live activity). Paper engine active (21 futures closed last hour). Open positions checked via lanes only. Tree left clean.

**Balances & burns:**

| Lab | Funded | Closed P/L | Balance | Burns | Action |
|---|---|---|---|---|---|
| Futures | $6,000 (orig + 5 refills) | −$5,888.13 | **$111.87** | 5 | none (> $50) |
| Options | $1,000 | −$86.74 | **$913.26** | 0 | none |

**Hour-over-hour:** Futures $670.93 → **$111.87** — **this hour closed 21 futures for −$559.06, the worst hour since burn #5** (prior hr was −$217). The bleed more than doubled. The profitable `paper_trail` cohort barely grew (+2 trades, net essentially flat vs last hr's +$585) — i.e. **100% of the new damage is fresh wrong-direction `paper_stop` entries.** Options flat (n=171, −$86.74).

**Per-lane — Futures (n=305, cumulative):**

| Lane | Closed | Win% | Net | Avg peak% | Max peak% | Avg hold |
|---|---|---|---|---|---|---|
| **FUT_MOMENTUM_CONF** | 122 | 15% | **−$2,590.96** | 7.41 | 108.44 | 4.9m |
| FUT_DONCHIAN_100X | 40 | 10% | −$1,399.29 | 7.77 | 57.90 | 2.2m |
| FUT_EMA_CONF | 70 | 31% | −$712.36 | 4.54 | 24.45 | 10.9m |
| FUT_DONCHIAN_50X | 37 | 19% | −$639.06 | 6.23 | 35.89 | 6.4m |
| FUT_DONCHIAN_CONF | 36 | 25% | −$546.47 | 7.99 | 72.75 | 7.6m |

Worst lane (10th+ straight run): **FUT_MOMENTUM_CONF −$2,591 = 44% of all futures loss.** MOMENTUM_CONF + DONCHIAN_100X = **−$3,990 = 68% of the loss.** Least-bad by win-rate: **FUT_EMA_CONF (31% win)** — but at 25× it still bled −$108 this hour (avg peak only 0.54%), confirming even the "good" lane is noise-stopped under high leverage.

**Per-lane — Options SELL (n=171):** OPT_SELL_PUT −$32.81 (4% win), OPT_SELL_PUT_FAR −$29.58 (2%), OPT_SELL_NEUTRAL −$13.59 (6%), OPT_SELL_CALL −$6.30 (20%), OPT_SELL_CALL_FAR −$4.45 (20%). Net −$86.74. Flat non-result.

**Exit-reason cohort split (n=305, cumulative) — the decisive signal, sharper than ever:**

| Exit reason | Closed | Net | Avg peak% |
|---|---|---|---|
| **paper_stop** | 177 | **−$6,276.78** | **+1.26** |
| paper_trail | 112 | **+$292.75** | +14.84 |
| paper_max_hold | 2 | **+$290.25** | +67.93 |
| ema21_lost | 9 | −$127.76 | +1.66 |
| ema21_reclaimed | 4 | −$53.87 | +2.05 |
| donchian_mid_revert | 1 | −$12.72 | +4.93 |

1. **`paper_stop` is now 107% of the entire futures loss (−$6,277 vs −$5,888 net), avg peak only +1.26%.** These entries go against almost immediately and never reach the money. This hour added 16 such trades for ≈−$520 — the whole −$559 hour.
2. **The exit side is profitable and proven:** `paper_trail` +$292.75 (avg peak +14.84%) and `paper_max_hold` +$290.25 (avg peak +67.93%) = **+$583 combined NET POSITIVE.** But this cohort **stalled this hour** (+2 trades, flat) — the engine took almost no good entries, only bad ones.
3. **STRATEGY verdict (not engine bug), 17th confirmation.** Fees/sizing/liq/holds sane. Defect = entry filter (breakouts chopped on crypto noise) amplified by 25–100× leverage → −8%/wrong entry. Even the best lane (EMA_CONF 31%) gets stopped at 25×.

**What to change (unchanged, now 17 runs un-actioned):**
1. **Fix the ENTRIES, not the exits.** Require a pullback/retest before breakout entry; cap leverage ≤10× so a wrong entry costs ≈−2% not −8%. Kill/throttle FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (68% of loss). The +$583 trail/max-hold cohort proves exits already work — fix entries and the lab flips positive.
2. Carry-over: defined-risk spreads on options.

**Verdict status:** unchanged. #8 (aggressive futures) **❌ DEAD** (5 full-bankroll burns); #6 (OTM selling) **⚠️ break-even** (n=171, no signal); #5 dead. The cohort split is the cleanest it has ever been: losers grow, winners stall — the fix is entry quality + leverage cap, repeatedly identified, still unimplemented.

### 2026-06-07 09:39 UTC — bleed halves (−$217/hr, no burn #6); cumulative cohort split is now decisive: paper_stop = 108% of loss (−$5,757, n=161) vs paper_trail+max_hold NET POSITIVE +$585 (n=112); verdict unchanged 16th run `[updated by: Cowork]`

**Live OFF** (`is_paused=true`, `bot_state="paused"`, `pause_reason="PAPER-ONLY mode (no live trading)"`, last status @ 09:39 UTC; **0 `options_scalp` trades last hour**). Locks: cleared a stale `.git/objects/maintenance.lock` (Jun 6 22:37, >2min). Open positions: futures 0, options 4.

**Balances & burns:**

| Lab | Funded | Closed P/L | Balance | Burns |
|---|---|---|---|---|
| Options (SELL) | $1,000 | −$81.93 | **$918.07** | 0× |
| Futures (aggressive) | $6,000* | −$5,329.07 | **$670.93** | **5×** |

*\*$1,000 seed + 5× $1,000 refills. No refill this hour — futures balance $670.93 sits well above the $50 trigger (burn #5 fired last hour). No burn #6.*

**Hour-over-hour:** Futures **−$217.08 (31 closed)** — bleed roughly **halves** vs last hour's −$414/hr; calmest tape in several hours, no fresh burn. Options −$13.95 (24 closed) — noise.

**Per-lane — Futures (cumulative, n=284):**

| Lane | Closed | Win% | Net | Avg peak% | Max peak% | Avg lev |
|---|---|---|---|---|---|---|
| **FUT_MOMENTUM_CONF** | 110 | 15% | **−$2,237.52** | 7.79 | 108.44 | 68× |
| FUT_DONCHIAN_100X | 39 | 10% | −$1,355.45 | 7.88 | 57.90 | 100× |
| FUT_DONCHIAN_50X | 36 | 19% | −$608.12 | 6.40 | 35.89 | 50× |
| FUT_EMA_CONF | 64 | 34% | −$603.90 | 4.91 | 24.45 | 30× |
| FUT_DONCHIAN_CONF | 35 | 26% | −$524.08 | 8.21 | 72.75 | 56× |

Worst: **FUT_MOMENTUM_CONF −$2,237 (42% of all futures losses; worst lane 16th straight run)**. MOMENTUM_CONF + DONCHIAN_100X = **−$3,593 = 67% of the −$5,329 total**. Least-bad / best win%: **FUT_EMA_CONF (34% win, 30× lev)** — the only lane near respectable, and notably the lowest-leverage lane.

**Per-lane — Options SELL (cumulative, n=163):** OPT_SELL_PUT −$29.91, OPT_SELL_PUT_FAR −$27.67, OPT_SELL_NEUTRAL −$13.59, OPT_SELL_CALL −$6.30, OPT_SELL_CALL_FAR −$4.45. Net −$81.93 (≈−$0.50/trade). Flat noise, no lane with edge.

**Key findings — exit-reason cohort (cumulative, n=284) is now decisive:**

| Exit reason | Closed | Net | Avg peak% |
|---|---|---|---|
| **paper_stop** | 161 | **−$5,757.48** | **+1.19** |
| paper_trail | 110 | **+$295.20** | +14.93 |
| paper_max_hold | 2 | **+$290.25** | +67.93 |
| ema21_lost | 7 | −$107.66 | +2.13 |
| ema21_reclaimed | 3 | −$36.65 | +2.11 |
| donchian_mid_revert | 1 | −$12.72 | +4.93 |

1. **`paper_stop` is now 108% of the entire net loss** (161 trades, −$5,757, vs −$5,329 total). Their avg PEAK is only **+1.19%** — these entries go wrong almost immediately and never reach the money. This is the single largest and most stable signal in the lab.
2. **The trades that survive are NET POSITIVE: paper_trail (+$295) + paper_max_hold (+$290) = +$585 across 112 trades.** When an entry goes the right way, the exit logic banks it. **Exits work; entries do not** — confirmed across the full sample, not a small cohort.
3. **STRATEGY verdict, not engine bug.** Fees/sizing/liq/holds all sane. Defect = entry filter (breakouts chopped on crypto noise) × 25–100× leverage → a wrong entry costs ~−8% realized.
4. **Options clean non-result** at n=163, −$81.93 — no lane with edge.

**What to change (single highest-leverage move, unchanged 16th run):**
1. **Attack entries, not exits.** Require a pullback/retest before breakout entry (stop chasing) and **cap leverage ≤10×** so a wrong entry costs ~−2% not −8%. The +$585 paper_trail/max_hold cohort proves the exit side already works — fix entries and the lab flips.
2. **Kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X** (67% of the loss); keep FUT_EMA_CONF as the template (lowest lev, best win%).
3. Carry-over: defined-risk spreads on options.

**Verdict status:** unchanged. #8 (aggressive futures) **❌ DEAD** (**5 full-bankroll burns**); #6 (OTM selling) **⚠️ break-even** (n=163, no signal); #5 dead. The cohort math (paper_stop −$5,757 @ +1.19% peak vs paper_trail/max_hold +$585) is the durable signal: **wrong entries + excess leverage, exits are fine.**

### 2026-06-07 08:39 UTC — **BURN #5** (bal hit −$111.99, refilled to ~$888); bleed re-accelerates (−$414/hr); paper_stop = 101% of loss (−$5,149, n=146); paper_trail still NET POSITIVE +$147 (n=95) but gave back ~$82 this hr; verdict unchanged 15th run `[updated by: Cowork]`

**Live OFF** (`is_paused=true`, `bot_state="paused"`, last status @ 08:37 UTC; **0 `options_scalp` trades last hour**). Locks: none.

**Balances & burns:**

| Lab | Funded | Closed P/L | Balance | Burns |
|---|---|---|---|---|
| Options (SELL) | $1,000 | −$67.98 | **$932.02** | 0× |
| Futures (aggressive) | $6,000* | −$5,111.99 | **$888.01** | **5×** |

*\*$1,000 seed + 5× $1,000 refills. Pre-check balance −$111.99 ≤ $50 → **auto-refill burn #5** fired (deposit `auto-refill burn #5 2026-06-07 08:39Z`), post-refill ~$888.*

**Hour-over-hour:** Futures bal $301.63 → pre-refill **−$111.99 = −$414/hr** — bleed re-accelerated from −$247/hr last hour (closed last hr −$413.61 over 23 trades). Options −$67.98 cumulative, flat noise.

**Per-lane — Futures (n=253):**

| Lane | Closed | Win% | Net | Avg peak% | Max peak% | Avg lev | Avg hold |
|---|---|---|---|---|---|---|---|
| **FUT_MOMENTUM_CONF** | 101 | 15% | **−$2,226.17** | 7.02 | 62.03 | 68× | 4.7m |
| FUT_DONCHIAN_100X | 33 | 9% | −$1,151.42 | 6.82 | 57.90 | 100× | 2.1m |
| FUT_DONCHIAN_50X | 31 | 16% | −$594.95 | 5.68 | 35.89 | 50× | 6.5m |
| FUT_DONCHIAN_CONF | 29 | 21% | −$572.49 | 5.74 | 29.41 | 54× | 7.9m |
| FUT_EMA_CONF | 59 | 34% | −$566.96 | 4.86 | 24.45 | 30× | 11.6m |

Best (least-bad): **FUT_EMA_CONF −$567** (lowest lev 30×, highest win 34%, longest hold). Worst: **FUT_MOMENTUM_CONF −$2,226** (44% of all futures losses; worst lane 15th straight run). **MOMENTUM_CONF + DONCHIAN_100X = −$3,378 = 66% of total loss.**

**Per-lane — Options SELL (n=139):** OPT_SELL_PUT_FAR −$24.29 (2% win, n=48), OPT_SELL_PUT −$19.91 (6%, n=47), OPT_SELL_NEUTRAL −$13.02 (6%, n=34), OPT_SELL_CALL −$6.30 (20%, n=5), OPT_SELL_CALL_FAR −$4.45 (20%, n=5). Net −$67.98 (≈−$0.49/trade). Flat noise, no lane with edge.

**Key findings — exit-reason split, 15th confirmation (n=253):**

| Exit reason | Closed | Net | Avg peak% | Avg lev |
|---|---|---|---|---|
| **paper_stop** | 146 | **−$5,149.09** | **+1.20** | 61× |
| **paper_trail** | 95 | **+$146.92** | **+14.05** | 60× |
| ema21_lost | 7 | −$107.66 | +2.13 | 25× |
| ema21_reclaimed | 3 | −$36.65 | +2.11 | 25× |
| donchian_mid_revert | 1 | −$12.72 | +4.93 | 25× |
| paper_max_hold | 1 | +$47.23 | +27.42 | 50× |

1. **`paper_trail` cohort still NET POSITIVE +$146.92 (n=95, avg peak +14.05%)** — but gave back ~$82 this hour (was +$229 n=82). New trail exits this hour ran weaker; the cohort is positive but not monotonic. Exit logic still banks gains when a trade runs — **not the problem.**
2. **`paper_stop` is 101% of the entire futures loss (n=146, −$5,149), avg PEAK only +1.20%.** Entries go against almost immediately, never reach the money, then exit under 61× leverage. The bleed is **wrong-direction entries.**
3. **STRATEGY verdict re-confirmed (not engine bug).** Fees/sizing/liq/holds sane. Defect = entry filter (breakouts chopped on crypto noise) amplified by 25–100×.
4. Options clean non-result at n=139, −$67.98 — no lane with edge; defined-risk-spreads thesis holds.

**What to change (single highest-leverage move, unchanged 15 runs):**
1. **Attack entries, not exits.** Require a pullback/retest before breakout entry and **cap leverage ≤10×** so a wrong entry costs ~−2% not −8%. **Kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (66% of loss).** The profitable paper_trail cohort proves the exit side already works — fix entries and the lab flips.
2. Carry-over: defined-risk spreads on options.

**Verdict status:** unchanged. #8 (aggressive futures) **❌ DEAD** (5 full-bankroll burns); #6 (OTM selling) **⚠️ break-even** (n=139, no signal); #5 dead. The entry-quality + leverage-cap fix is the standing recommendation.

---

### 2026-06-07 07:40 UTC — bleed slows (−$247/hr, no burn #5; bal $301.63); paper_trail cohort grows NET POSITIVE +$229 (n=82) → exits profitable; paper_stop = 102% of loss (−$4,817, n=136); verdict unchanged 14th run `[updated by: Cowork]`

**Live OFF** (`is_paused=true`, `pause_reason="PAPER-ONLY mode (no live trading)"`, last status @ 07:37 UTC; **0 `options_scalp` trades last hour**). Locks: none.

**Balances & burns:**

| Lab | Funded | Closed P/L | Balance | Burns | 
|---|---|---|---|---|
| Options (SELL) | $1,000 | −$55.37 | **$944.63** | 0× |
| Futures (aggressive) | $5,000* | −$4,698.37 | **$301.63** | **4×** |

*\*$1,000 seed + 4× $1,000 refills. Pre-check balance $301.63 > $50 → **no auto-refill** this hour (burn #5 not reached).*

**Hour-over-hour:** Futures bal $548.85 → **$301.63 = −$247/hr** — calmest bleed since the 04:39 lull (was −$427/hr last hour). Closed buckets: 05:00 −$296 (24), 06:00 −$410 (23), 07:00 partial −$215 (10). Options −$55.37 cumulative, flat noise.

**Per-lane — Futures (n=230):**

| Lane | Closed | Win% | Net | Avg peak% | Max peak% | Avg hold |
|---|---|---|---|---|---|---|
| **FUT_MOMENTUM_CONF** | 95 | 16% | **−$2,076.33** | 7.25 | 62.03 | 4.8m |
| FUT_DONCHIAN_100X | 28 | 11% | −$1,014.86 | 6.92 | 57.90 | 2.0m |
| FUT_EMA_CONF | 55 | 31% | −$572.42 | 4.75 | 24.45 | 10.7m |
| FUT_DONCHIAN_50X | 27 | 19% | −$525.29 | 5.78 | 35.89 | 6.8m |
| FUT_DONCHIAN_CONF | 25 | 24% | −$509.47 | 5.78 | 29.41 | 8.5m |

Best (least-bad): **FUT_DONCHIAN_CONF −$509**. Worst: **FUT_MOMENTUM_CONF −$2,076** (44% of all futures losses; worst lane 14th straight run). **MOMENTUM_CONF + DONCHIAN_100X = −$3,091 = 66% of total loss.**

**Per-lane — Options SELL (n=116):** OPT_SELL_PUT_FAR −$19.67 (3% win, n=40), OPT_SELL_PUT −$14.13 (8%, n=36), OPT_SELL_NEUTRAL −$10.83 (7%, n=30), OPT_SELL_CALL −$6.30 (20%, n=5), OPT_SELL_CALL_FAR −$4.45 (20%, n=5). Net −$55.37 (≈−$0.48/trade). Flat noise, no lane with edge.

**Key findings — exit-reason split, 14th confirmation (n=230):**

| Exit reason | Closed | Net | Avg peak% | Avg realized% |
|---|---|---|---|---|
| **paper_stop** | 136 | **−$4,817.25** | **+1.16** | **−8.03** |
| **paper_trail** | 82 | **+$228.68** | **+15.05** | **+7.09** |
| ema21_lost | 7 | −$107.66 | +2.13 | −3.65 |
| ema21_reclaimed | 3 | −$36.65 | +2.11 | −2.39 |
| donchian_mid_revert | 1 | −$12.72 | +4.93 | −2.59 |
| paper_max_hold | 1 | +$47.23 | +27.42 | +23.89 |

1. **`paper_trail` cohort is now NET POSITIVE +$228.68 (n=82, avg peak +15.05%, realized +7.09%)** — when a trade goes the right way the trailing exit banks ~47% of peak. Grows hour over hour (+$142 → +$194 → **+$229**). **Exit logic is profitable; it is not the problem.**
2. **`paper_stop` is 102% of the entire futures loss (n=136, −$4,817), avg PEAK only +1.16%.** These entries go against almost immediately, never reach the money, then exit −8.03% under leverage. The bleed is **wrong-direction entries**, not round-tripping.
3. **STRATEGY verdict re-confirmed (not engine bug).** Fees/sizing/liq/holds sane. Defect = entry filter (breakouts chopped on crypto noise) amplified by 25–100× → −8% per wrong entry.
4. Options clean non-result at n=116, −$55.37 — no lane with edge; thesis (flat; needs defined-risk spreads) holds.

**What to change (single highest-leverage move, unchanged 14 runs):**
1. **Attack entries, not exits.** Require a pullback/retest before breakout entry (stop chasing) and **cap leverage ≤10×** so a wrong entry costs ~−2% not −8%. **Kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (66% of loss).** The profitable paper_trail cohort proves the exit side already works — fix entries and the lab flips.
2. Carry-over: defined-risk spreads on options.

**Verdict status:** unchanged. #8 (aggressive futures) **❌ DEAD** (4 full-bankroll burns); #6 (OTM selling) **⚠️ break-even** (n=116, no signal); #5 dead. No new verdict changes — the entry-quality + leverage-cap fix is the standing recommendation.

### 2026-06-07 06:40 UTC — bleed continues (−$427/hr, no burn #5; bal $548.85); paper_trail cohort grows to +$194 (n=76) → exits profitable; paper_stop = 101% of loss (−$4,511, n=127); verdict unchanged 13th run `[updated by: Cowork]`

**Live OFF** (`bot_status.is_paused=true`, `is_running=true`, latest row 06:37 UTC; **0 live `options_scalp` trades last hour** — engine paused). Real account `capital`=$27.08. Locks: none. Tree clean.

**No refill:** futures balance **$548.85 > $50** floor — no burn this hour (last burn #4 at 05:40). Bleed pace would put next burn ~1h out if unchanged.

**Balances & burns:**

| Lab | Funded | Closed P/L | Balance | Burns | Open |
|---|---|---|---|---|---|
| Futures | $5,000* | −$4,451.15 (n=214) | **$548.85** | **4** | 2 |
| Options | $1,000 | −$52.67 (n=111) | **$947.33** | 0 | 5 |

*\*$1,000 seed + 4× $1,000 burn refills.*

**Hour-over-hour:** Futures closed for **−$427.41** (22 opened) — bleed re-accelerated from last hour's −$98 calm, back into the −$200–$440 band. Options drift −$9 noise.

**Per-lane — Futures (n=214):**

| Lane | Closed | Win% | Net | Avg peak% | Max peak% | Avg hold | Avg lev |
|---|---|---|---|---|---|---|---|
| **FUT_MOMENTUM_CONF** | 85 | 15.3% | **−$1,927.22** | 6.91 | 53.20 | 4.8m | 67× |
| FUT_DONCHIAN_100X | 27 | 11.1% | −$966.35 | 7.18 | 57.90 | 2.0m | 100× |
| FUT_EMA_CONF | 53 | 30.2% | −$555.26 | 4.81 | 24.45 | 10.3m | 31× |
| FUT_DONCHIAN_50X | 26 | 19.2% | −$497.72 | 6.00 | 35.89 | 7.0m | 50× |
| FUT_DONCHIAN_CONF | 24 | 25.0% | −$479.79 | 6.02 | 29.41 | 8.8m | 55× |

**Per-lane — Options SELL (n=111):** OPT_SELL_PUT_FAR −$19.02 (2.6% win), OPT_SELL_PUT −$12.57 (9.1%), OPT_SELL_NEUTRAL −$10.33 (6.9%), OPT_SELL_CALL −$6.30 (20%), OPT_SELL_CALL_FAR −$4.45 (20%). Net −$52.67 (≈−$0.47/trade) — flat noise, no lane with edge; near-zero avg peak (≤1.2%) = premium sells almost never reach profit, but tiny sizing keeps it harmless.

Best lane: **FUT_DONCHIAN_CONF −$480** (least-bad). Worst: **FUT_MOMENTUM_CONF −$1,927** (43% of all futures losses; worst lane 13th straight run). MOMENTUM_CONF + DONCHIAN_100X = −$2,894 = **65%** of futures loss.

**Key findings — exit/entry split unchanged (n=214):**

| Exit reason | Closed | Net | Avg peak% |
|---|---|---|---|
| **paper_stop** | 127 | **−$4,510.86** | **+1.20** |
| ema21_lost | 7 | −$107.66 | +2.13 |
| ema21_reclaimed | 3 | −$36.65 | +2.11 |
| donchian_mid_revert | 1 | −$12.72 | +4.93 |
| paper_max_hold | 1 | +$47.23 | +27.42 |
| **paper_trail** | 76 | **+$194.33** | **+14.88** |

1. **`paper_trail` cohort keeps growing positive: +$194.33 over 76 trades at +14.88% avg peak.** The exit/trailing logic is profitable when the entry is correct — strongest proof yet the exit side works.
2. **`paper_stop` is 101% of the loss: −$4,510.86 over 127 trades at avg peak only +1.20%.** Wrong-direction entries that never reach the money before the leveraged stop. The entire lab loss is entry quality.
3. **STRATEGY verdict re-confirmed (not engine bug), 13th run.** Fees/sizing/liq/holds all sane; defect is entry quality amplified by 25–100× leverage.
4. **Options clean non-result** at n=111, −$52.67 — no lane with edge.

**What to change (single highest-leverage move) — UNCHANGED for the 13th run:**
1. **Fix entries, not exits.** Require a pullback/retest before breakout entry (stop chasing) and cap leverage ≤10× so a wrong entry costs ~−2% not −8%. The profitable `paper_trail` cohort proves the exit side already makes money — fix entries and the lab flips green.
2. **Kill/throttle FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X** (together −$2,894 = 65% of the futures loss).
3. Carry-over: defined-risk spreads on options.

**Verdict status:** unchanged. #8 (aggressive futures) **❌ DEAD** (4 full-bankroll burns); #6 (OTM selling) **⚠️ break-even** (n=111, no signal); #5 dead. Continuing signal: **paper_trail net positive (+$194)** — the fix is entry-side only.

### 2026-06-07 05:40 UTC — BURN #4 (futures hit $1.07, refilled); paper_trail cohort flips NET POSITIVE (+$142, n=69) → exits profitable, 100% of damage is paper_stop wrong entries, 12th run `[updated by: Cowork]`

**Live OFF** (`bot_status.is_paused=true`, `bot_state=paused`, latest row 05:39 UTC; **0 live `options_scalp` trades** — engine paused). Locks: none. Tree clean.

**AUTO-REFILL fired:** futures pre-refill balance **$1.07 ≤ $50 → burn #4** (`paper_deposits` id 6, note `auto-refill burn #4 2026-06-07 05:40 UTC`). Funded $4,000 → **$5,000**, balance restored to ≈**$1,001.07**.

**Balances & burns:**

| Lab | Funded | Closed P/L | Balance | Burns | Open |
|---|---|---|---|---|---|
| Futures | $5,000* | −$3,998.93 (n=194) | **$1,001.07** (post-refill) | **4** | 0 |
| Options | $1,000 | −$43.15 (n=92) | **$956.85** | 0 | — |

*\*$1,000 seed + 4× $1,000 burn refills.*

**Hour-over-hour:** Futures closed 24 trades for **−$206.82** (21 opened, 0 open now) — bleed **re-accelerated** from last hour's −$98 calm (back toward the −$200–$440 band). That last $206 was enough to cross the $50 floor and trigger burn #4.

**Per-lane — Futures (n=194):**

| Lane | Closed | Win% | Net | Avg peak% | Max peak% | Avg hold |
|---|---|---|---|---|---|---|
| **FUT_MOMENTUM_CONF** | 77 | 16% | **−$1,738.75** | 6.99 | 53.20 | 5.0m |
| FUT_DONCHIAN_100X | 25 | 12% | −$870.64 | 7.56 | 57.90 | 2.1m |
| FUT_EMA_CONF | 46 | 28% | −$531.52 | 4.35 | 15.61 | 10.5m |
| FUT_DONCHIAN_CONF | 22 | 27% | −$446.09 | 6.02 | 29.41 | 9.6m |
| FUT_DONCHIAN_50X | 24 | 21% | −$411.92 | 6.37 | 35.89 | 7.2m |

**Per-lane — Options SELL (n=92):** OPT_SELL_PUT_FAR −$18.11 (3% win), OPT_SELL_PUT −$8.85 (12%), OPT_SELL_NEUTRAL −$7.57 (9%), OPT_SELL_CALL −$4.98 (25%), OPT_SELL_CALL_FAR −$3.63 (25%). Net −$43.15 (≈−$0.47/trade) — flat noise, no lane with edge.

Best lane: **FUT_DONCHIAN_50X −$412** (least-bad). Worst: **FUT_MOMENTUM_CONF −$1,739** (43% of all futures losses; worst lane for the 12th straight run).

**Key findings — paper_trail cohort is now NET POSITIVE (n=194):**

| Exit reason | Closed | Net | Avg peak% |
|---|---|---|---|
| **paper_stop** | 114 | **−$4,046.73** | **+1.23** |
| ema21_lost | 6 | −$92.06 | +2.49 |
| ema21_reclaimed | 3 | −$36.65 | +2.11 |
| donchian_mid_revert | 1 | −$12.72 | +4.93 |
| paper_max_hold | 1 | +$47.23 | +27.42 |
| **paper_trail** | 69 | **+$142.00** | **+14.76** |

1. **`paper_trail` has crossed into net-positive territory: +$142.00 over 69 trades at +14.76% avg peak.** The exit/trailing logic is not just "fine" — it is **profitable** on the trades where the entry is correct. This is the cleanest proof yet that the exit side works.
2. **`paper_stop` is 100%+ of the loss: −$4,046.73 over 114 trades at avg peak only +1.23%.** These entries go against immediately and never reach the money before the leveraged stop. The entire lab loss is wrong-direction entries; everything else nets out positive.
3. **STRATEGY verdict re-confirmed (not engine bug), 12th run.** Fees/sizing/liq/holds all sane; the defect is entry quality amplified by 25–100× leverage.
4. **Options clean non-result** at n=92, −$43.15 — no lane with edge.

**What to change (single highest-leverage move) — UNCHANGED for the 12th run:**
1. **Fix entries, not exits.** Require a pullback/retest before breakout entry (stop chasing) and cap leverage ≤10× so a wrong entry costs ~−2% not −8%. The now-profitable `paper_trail` cohort proves the exit side already makes money — fix entries and the lab flips green.
2. **Kill/throttle FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X** (together −$2,609 = 65% of the futures loss).
3. Carry-over: defined-risk spreads on options.

**Verdict status:** unchanged. #8 (aggressive futures) **❌ DEAD** (now **4 full-bankroll burns**); #6 (OTM selling) **⚠️ break-even** (n=92, no signal); #5 dead. New signal this run: **paper_trail net positive (+$142)** — the strongest evidence the fix is entry-side only.



**Live OFF** (`is_paused=true`; **0 `options_scalp` trades last hour**). Locks: none. Tree clean. No refill (futures $207.89 > $50).

**Balances & burns:**

| Lab | Funded | Closed P/L | Balance | Burns | Open |
|---|---|---|---|---|---|
| Futures | $4,000* | −$3,792.11 (n=170) | **$207.89** | 3 | 3 |
| Options | $1,000 | −$27.28 (n=68) | **$972.72** | 0 | — |

*\*$1,000 original + 3× $1,000 burn refills.*

**Hour-over-hour:** Futures closed 5 trades for **−$98.44** — the calmest hour in the last five (vs −$441, −$341, −$1,042, −$477 prior). Still bleeding, just slower with little activity. Options flat (no new closes of note). No burn #4 this hour; ~$158 buffer above the $50 refill line.

**Per-lane — Futures (n=170):**

| Lane | Closed | Win% | Net | Avg peak% | Max peak% | Avg hold |
|---|---|---|---|---|---|---|
| **FUT_MOMENTUM_CONF** | 67 | 13% | **−$1,552.41** | 6.50 | 35.37 | 4.9m |
| FUT_DONCHIAN_100X | 22 | 9% | −$843.22 | 5.96 | 29.41 | 2.0m |
| FUT_EMA_CONF | 41 | 22% | −$552.62 | 3.74 | 13.23 | 11.0m |
| FUT_DONCHIAN_CONF | 19 | 21% | −$459.73 | 4.70 | 29.41 | 9.3m |
| FUT_DONCHIAN_50X | 21 | 19% | −$384.12 | 5.92 | 35.89 | 7.4m |

Worst: **FUT_MOMENTUM_CONF −$1,552** (41% of all futures losses; worst lane for the 11th straight run). FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X together = **−$2,396 (63% of the loss)**.

**Key findings — exit-reason split (n=170), the verdict is now ironclad:**

| Exit reason | Closed | Net | Avg peak% | Avg lev |
|---|---|---|---|---|
| **paper_stop** | 103 | **−$3,635.84** | **+1.31** | 59.7× |
| paper_trail | 57 | −$79.93 | +13.12 | 62.3× |
| ema21_lost | 5 | −$74.19 | +2.41 | 25.0× |
| ema21_reclaimed | 3 | −$36.65 | +2.11 | 25.0× |
| donchian_mid_revert | 1 | −$12.72 | +4.93 | 25.0× |
| paper_max_hold | 1 | +$47.23 | +27.42 | 50.0× |

1. **`paper_stop` is the ENTIRE loss: 103 trades, −$3,636, avg peak only +1.31% at ~60× leverage.** Entries go adverse almost immediately and never reach the money — wrong-direction entries with no edge, not winners round-tripping.
2. **`paper_trail` cohort is breakeven (−$79.93 on n=57, avg peak +13.12%).** When a trade goes the right way the trailing exit banks it. **Exit logic works; entries do not** — same as last 5 runs, now at n=170.
3. **STRATEGY verdict (not engine bug).** Fees/sizing/liq/holds sane. Defect = entry filter (breakouts chopped on crypto noise) amplified by 25–100× leverage.
4. **Options clean non-result** at n=68, −$27.28 — no lane with edge.

**What to change (unchanged, 11th run):**
1. **Attack entries, not exits.** Require a pullback/retest before breakout entry (stop chasing) and cap leverage ≤10× so a wrong entry costs ~−2% not −8%. The paper_trail winners prove the exit side already works.
2. **Kill/throttle FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X** (63% of the loss).
3. Carry-over: defined-risk spreads on options.

**Verdict status:** unchanged. #8 (aggressive futures) **❌ DEAD** (3 full-bankroll burns); #6 (OTM selling) **⚠️ break-even** (n=68, no signal); #5 dead. The fix is fully specified and remains un-implemented — engine code is owner-gated for this monitor.

### 2026-06-07 03:39 UTC — paper_stop bleed crosses n=100 (+1.27% avg peak); same fix unimplemented for 10th run `[updated by: Cowork]`

**Live OFF** (`is_paused=true`, `pause_reason="PAPER-ONLY mode (no live trading)"`; **0 `options_scalp` trades last hour**). Locks: none. Tree clean.

**Balances & burns:**

| Lab | Funded | Closed P/L | Balance | Burns | Open |
|---|---|---|---|---|---|
| Options (SELL) | $1,000 | −$31.02 | **$968.98** | 0× | — |
| Futures (aggressive) | $4,000* | −$3,700.93 | **$299.07** | **3×** | 0 |

*\*$1,000 seed + 3×$1,000 refills. No burn this hour — balance $299.07 > $50 floor, no refill fired.*

**Hour-over-hour:** Futures $744.45 (post burn-#3 refill last hour) → **$299.07** — this hour closed **21 futures for −$440.57**, burning ~60% of the fresh buffer. Pace (−$441/hr) matches last hour (−$341) — steady bleed, no new burn yet (~$249 buffer ⇒ burn #4 likely within ~1hr if unchanged). Options −$6.44 (drift, noise).

**Per-lane — Futures (n=172):**

| Lane | Closed | Win% | Net | Avg peak% | Avg lev |
|---|---|---|---|---|---|
| **FUT_MOMENTUM_CONF** | 66 | 15% | **−$1,478.70** | 6.39 | 65.9× |
| FUT_DONCHIAN_100X | 22 | 9% | −$843.22 | 5.96 | 100× |
| FUT_EMA_CONF | 44 | 23% | −$533.29 | 3.49 | 30.7× |
| FUT_DONCHIAN_CONF | 19 | 21% | −$459.73 | 4.70 | 55.3× |
| FUT_DONCHIAN_50X | 21 | 19% | −$384.12 | 5.92 | 50× |

Best (least-bad): **FUT_DONCHIAN_50X −$384**. Worst: **FUT_MOMENTUM_CONF −$1,479** (40% of all futures loss; worst lane for the 11th straight run, avg lev 66×).

**Per-lane — Options SELL (n=109):** PUT_FAR −$14.06, PUT −$7.01, NEUTRAL −$5.65, CALL −$2.33, CALL_FAR −$1.94. Net −$31.02 (≈−$0.28/trade). Flat noise, no lane with edge.

**Key findings — exit-reason split, now n=100 on paper_stop:**

| Exit reason | Closed | Net | Avg peak% | Avg realized% |
|---|---|---|---|---|
| **paper_stop** | 100 | **−$3,556.47** | **+1.27** | **−8.23** |
| paper_trail | 56 | −$78.43 | +13.13 | **+5.69** |
| ema21_lost | 4 | −$56.62 | +1.91 | −3.16 |
| ema21_reclaimed | 3 | −$36.65 | +2.11 | −2.39 |
| paper_max_hold | 1 | +$47.23 | +27.42 | +23.89 |

1. **96% of all futures loss = `paper_stop` (n=100, −$3,556), avg PEAK only +1.27%.** Diagnosis identical to the last 3 hours, now with a clean 100-trade sample: these entries go **against immediately**, never reach the money, and exit at −8.23% under 30–100× leverage. **Wrong-direction entries, not give-back.**
2. **`paper_trail` cohort remains profitable on a %-basis** — n=56, avg peak +13.13%, **avg realized +5.69%**, net only −$78. Exit logic banks ~43% of peak when a trade works. **Exits are fine; entries have no edge.**
3. **STRATEGY verdict, not engine bug** (re-confirmed). Stop is correctly capping losers; the −8% stop at 66× leverage = a 0.12% adverse price move, i.e. the stop fires inside pure noise → high leverage *manufactures* the loss. Fees/sizing/liq/holds all sane.
4. **Options is a settled non-result** — n=109, −$31, no lane with edge. Thesis (flat; needs defined-risk spreads) holds.

**What to change (single highest-leverage move):**
1. **The fix is identified and UNCHANGED for 10 runs — it just needs implementing in engine code (out of this monitor's read-only scope): (a) require a pullback/retest before breakout entry; (b) cap leverage ≤10× so a wrong entry costs ~−2% not −8%; (c) kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (63% of the loss, both 66–100× lev).** The profitable paper_trail winners prove the exit side already works. Re-running the lab without this change only re-confirms the same number and burns more bankroll.
2. Carry-over: defined-risk spreads on options.

**Verdict status:** unchanged. #8 (aggressive futures) **❌ DEAD** (3 full-bankroll burns); #6 (OTM selling) **⚠️ break-even** (n=109, no signal); #5 still dead. No new signal — this hour is a high-confidence re-confirmation, not a discovery.

---

### 2026-06-07 02:39 UTC — BURN #3 fired; paper_stop bleed re-confirmed at +1.26% avg peak `[updated by: Cowork]`

**Live OFF** (`is_paused=true`; **0 `options_scalp` trades last hour**). Locks: none. Tree clean.

**Balances & burns:**

| Lab | Funded | Closed P/L | Balance | Burns | Open |
|---|---|---|---|---|---|
| Options (SELL) | $1,000 | −$24.58 | **$975.42** | 0× | — |
| Futures (aggressive) | $4,000* | −$3,255.55 | **$744.45** | **3×** | — |

*\*$1,000 original + 3×$1,000 refills. Pre-refill balance was **−$255.55 ≤ $50 → AUTO-REFILL fired** (note `auto-refill burn #3 2026-06-07 02:39Z`), restoring to +$744.45.*

**Hour-over-hour:** Futures $87.97 → **−$255.55 before refill** — this hour closed ~21 futures for **−$341.07** (much calmer than last hour's −$1,042, but still a steady one-way bleed → burn #3). Options −$8.19 (~48 closed) — noise.

**Per-lane — Futures (n=150):**

| Lane | Closed | Win% | Net | Avg peak% | Max peak% | Avg hold |
|---|---|---|---|---|---|---|
| **FUT_MOMENTUM_CONF** | 59 | 15% | **−$1,303.19** | 6.24 | 35.37 | 5.1m |
| FUT_DONCHIAN_100X | 20 | 10% | −$729.71 | 6.55 | 29.41 | 2.1m |
| FUT_EMA_CONF | 35 | 14% | −$522.70 | 2.25 | 9.36 | 8.6m |
| FUT_DONCHIAN_CONF | 17 | 24% | −$377.89 | 5.26 | 29.41 | 10.3m |
| FUT_DONCHIAN_50X | 19 | 21% | −$322.05 | 6.41 | 35.89 | 8.0m |

Best lane (least-bad): **FUT_DONCHIAN_50X −$322**. Worst: **FUT_MOMENTUM_CONF −$1,303** (40% of all futures losses; worst lane 11th straight run). This hour's bleed was MOMENTUM_CONF (+12 closed, −$226) and EMA_CONF (+9 closed, −$118); the 50×/100× Donchian lanes did not trade (throttled/quiet).

**Per-lane — Options SELL (n=92):** OPT_SELL_PUT_FAR −$8.30 (8% win), OPT_SELL_PUT −$7.40 (14%), OPT_SELL_NEUTRAL −$4.39 (18%), OPT_SELL_CALL −$2.33 (55%), OPT_SELL_CALL_FAR −$1.94 (31%). Net −$24.58 (≈−$0.27/trade). Flat noise, sample doubled with no edge emerging.

**Key findings — exit-reason breakdown holds firm (n=150):**

| Exit reason | Closed | Net | Avg peak% | Avg lev |
|---|---|---|---|---|
| **paper_stop** | 89 | **−$3,094.40** | **+1.26** | 58.7× |
| paper_trail | 46 | −$99.93 | +13.47 | 66.3× |
| ema21_lost | 4 | −$56.62 | +1.91 | 25.0× |
| ema21_reclaimed | 3 | −$36.65 | +2.11 | 25.0× |
| donchian_mid_revert | 1 | −$12.72 | +4.93 | 25.0× |
| restart_orphan | 6 | −$2.45 | +1.82 | 37.5× |
| paper_max_hold | 1 | +$47.23 | +27.42 | 50.0× |

1. **95% of the entire futures loss (−$3,094 of −$3,256) is `paper_stop`, avg peak only +1.26%.** Re-confirmed and slightly sharper than last hour (+1.31%). These entries go against almost immediately and never reach the money — **wrong-direction entries with no edge, amplified by 58.7× avg leverage.**
2. **`paper_trail` cohort still near-breakeven** — 46 trades, avg peak +13.47%, net only −$99.93. When direction is right the trailing exit banks it. **Exit logic works; entries do not.** Same conclusion three hours running.
3. **STRATEGY verdict (not engine bug).** Fees/sizing/holds all sane; the defect is entry quality × leverage. The structural fix is unchanged and now backed by n=150.
4. **Options:** clean non-result at n=92, −$24.58 — no lane with edge.

**What to change (single highest-leverage move):**
1. **Attack entries, not exits.** Require a pullback/retest confirmation before breakout entry (stop chasing) and cap leverage ≤10× so a wrong entry costs ~−2% not −8%. Throttle/kill FUT_MOMENTUM_CONF (40% of loss) + FUT_DONCHIAN_100X.
2. Carry-over: defined-risk spreads on options.

**Verdict status:** unchanged. #8 (aggressive futures) **❌ DEAD** (now **3 full-bankroll burns**); #6 (OTM selling) **⚠️ break-even** (n=92, no signal); #5 dead. The +1.26% avg-peak `paper_stop` signal continues to point the fix squarely at entry quality + leverage cap.

### 2026-06-06 17:10 UTC — first check-in after the reset `[updated by: Cowork]`

**What's happening:** Bot is live and trading both new labs. SELL options lanes: 52 closed + 8 open. Sane-leverage futures: 58 closed + 8 open since 06-05.

**What happened (numbers):**

Options SELLING — 0 winners out of 52. Every single lane negative:

| Lane | Closed | Win% | Net |
|---|---|---|---|
| OPT_SELL_NEUTRAL | 3 | 0% | −$99.90 |
| OPT_SELL_PUT | 10 | 0% | −$225.43 |
| OPT_SELL_CALL | 14 | 0% | −$320.94 |
| OPT_SELL_CALL_FAR | 14 | 0% | −$368.86 |
| OPT_SELL_PUT_FAR | 11 | 0% | −$439.43 |
| **Total** | **52** | **0%** | **≈ −$1,455** |

Futures sane-leverage — all negative, small losses:

| Lane | Closed | Win% | Net |
|---|---|---|---|
| FUT_DONCHIAN_3X | 7 | 14% | −$19.26 |
| FUT_DONCHIAN_5X | 7 | 14% | −$23.29 |
| FUT_EMA_4X | 21 | 0% | −$58.47 |
| FUT_MOMENTUM_4X | 23 | 17% | −$70.15 |

**The new thing (key finding): the SELL results are NOT a strategy verdict — they're engine bugs.** Three smoking guns from trade-level inspection:

1. **Fee model is wrong for selling.** Fees ≈ $15–16 on an $80 stake (≈20% per round trip). They're computed as ~0.03% × underlying NOTIONAL × 2 legs (e.g. $80 stake controlling $25k–$312k notional → $15+ fees). Real venues (Deribit-style) charge per-contract on PREMIUM, capped at ~12.5% of premium. ~$780 of the −$1,455 is just this fee bug.
2. **`sell_breached` exit fires on 51/52 trades within 15–25 min.** Avg exit −14.7% pre-fee while avg PEAK was +16–34%. The breach check is way too tight — trades were winning and got dumped on noise. TP (+50% credit) is unreachable because breach always fires first.
3. **Hold times of 15–25 min can't harvest theta.** Theta accrues over hours/days. The "ride to near-expiry" logic never engages. We're effectively testing "short gamma for 20 minutes while paying notional fees" — not premium selling.

Also: contract sizing lets $80 of stake control up to $312k notional (ETH far-OTM). That's the old reckless-leverage mistake wearing a new hat.

Futures finding: 27 of 58 exits are `paper_max_hold` at ~30 min. A 30-minute clock on a TREND strategy converts it back into scalping — the exact thing verdicts #1–#3 killed. FUT_EMA_4X is 0/21 (EMA pullback weak again, consistent with options-era EMA lanes). Donchian samples too small to judge.

**What we should change:**
1. Fix option-sell fees: charge on premium (per-contract, capped ~12.5% of premium), not on underlying notional.
2. Fix `sell_breached`: trigger on spot CLOSING beyond strike (or strike ± buffer), not touching an over-tight level. Log the breach price vs strike to verify.
3. Let sells run: min hold measured in hours, ride toward expiry as designed; theta needs time.
4. Cap notional per trade (e.g. ≤ 5–10× stake) on the sell lanes.
5. Futures: replace `paper_max_hold` 30 min with trend-break exits (Donchian mid / EMA loss only) or extend max hold to several hours. Until then the 3–5× test isn't testing the thesis.
6. After fixes: reset SELL bankroll and restart the count. The current 52 trades are contaminated — exclude them from any strategy verdict.

**Verdict status:** #6 (OTM selling) and #7 (sane-leverage futures) stay 🧪 TESTING — current data is invalid as evidence either way.

### 2026-06-06 17:38 UTC — post-reset, both labs just restarted clean `[updated by: Cowork]`

**What's happening:** Both labs were reset to $1,000 and restarted ~3 min before this check-in (first trades 17:31–17:35 UTC). The contaminated SELL data (52 trades) and old futures data are gone. This is the FIXED selling engine + aggressive-leverage futures running on a clean slate. **Live trading still OFF** (bot_status is_paused=true; 0 `options_scalp` trades in the last hour).

**What happened (numbers):** Almost nothing closed yet — too early to judge anything.

| Lab | Open | Closed | Balance |
|---|---|---|---|
| Options (SELL) | 6 | 0 | $1,000.00 |
| Futures (aggressive) | 1 | 1 | $979.16 |

Open SELL lanes seeded: OPT_SELL_NEUTRAL×2, OPT_SELL_PUT×2, OPT_SELL_PUT_FAR×2. The single closed futures trade:

| Lane | Dir | Lev | Margin→Notional | Fees | Exit | Hold | Peak | Net |
|---|---|---|---|---|---|---|---|---|
| FUT_EMA_CONF | ETH long | 25× | $250→$6,250 | $6.25 | paper_stop | 2.3 min | 0% | −$20.84 |

**Key finding — futures fee model now looks SANE, but the leverage-noise stop-out is back.** Two things from the one trade:
1. **Fees are no longer the notional bug.** $6.25 on $6,250 notional = 0.1% (reasonable taker round-trip). Margin→notional is a clean 25× (confidence 67 → bottom of the 25–100× ladder). The old "$80 stake controls $312k notional" sizing pathology is not present on the futures side.
2. **Stopped on noise in 2.3 min.** Spot moved −0.23% (1563.65→1560.00); at 25× that's −5.8% on margin → `paper_stop`. Peak was 0% — the trade never went green, so the peak-capture trail (banks ~70% of peak) had nothing to bank. This is exactly the risk flagged last round: at 25–100× a sub-0.5% wiggle stops you out before the thesis can play. n=1, but it's the pattern to watch.

**What we should change (carry-over, pending sample):**
1. Futures: the paper_stop is too tight relative to leverage. Either (a) widen the stop to survive normal intrabar noise (e.g. ATR-based, not a fixed % on margin), or (b) cap leverage so a 0.2–0.3% wiggle isn't a −5%+ margin hit. As-is, 25–100× + tight stop = guaranteed churn.
2. Let the next ~30–50 closes accumulate before any verdict. Both lanes are essentially at sample size 0–1.
3. Watch the first SELL closes closely to confirm the fee/breach fixes hold (fees ≤ ~12.5% of premium, breach = spot reaching strike, holds measured in hours not minutes).

**Verdict status:** unchanged — #6 (OTM selling) 🧪 TESTING, #8 (aggressive-leverage futures) 🧪 TESTING. Clean data collection just (re)started; nothing to conclude.

### 2026-06-06 18:39 UTC — first real sample on the clean slate `[updated by: Cowork]`

**What's happening:** One hour into the clean restart. **Live trading OFF** (bot_status is_paused=true, bot_state=paused; 0 `trades` and 0 `options_scalp` in the last hour). No burns on either lab; no refill triggered (both balances ≫ $50 floor).

**Balances & burns:**

| Lab | Funded | Closed P/L | Balance | Burns | Open |
|---|---|---|---|---|---|
| Options (SELL) | $1,000 | +$1.18 | **$1,001.18** | 0× | 6 |
| Futures (aggressive) | $1,000 | −$405.28 | **$594.72** | 0× | 1 |

**Per-lane (this clean run):**

| Lab | Lane | Closed | Win% | Net | Avg peak% | Max peak% | Avg hold |
|---|---|---|---|---|---|---|---|
| Options | OPT_SELL_NEUTRAL | 1 | 100% | +$0.65 | 30.6 | 30.6 | 37m |
| Options | OPT_SELL_CALL | 1 | 100% | +$0.46 | 31.9 | 31.9 | 2m |
| Options | OPT_SELL_CALL_FAR | 1 | 100% | +$0.07 | 30.1 | 30.1 | 6m |
| Futures | FUT_DONCHIAN_CONF | 1 | 0% | −$22.12 | 0.0 | 0.0 | 6m |
| Futures | FUT_DONCHIAN_50X | 1 | 0% | −$27.71 | 0.0 | 0.0 | 2m |
| Futures | FUT_EMA_CONF | 3 | 33% | −$44.72 | 2.8 | 7.7 | 12m |
| Futures | FUT_DONCHIAN_100X | 1 | 0% | −$49.21 | 0.0 | 0.0 | 1m |
| Futures | **FUT_MOMENTUM_CONF** | 12 | 17% | **−$261.54** | 5.5 | 32.5 | 4m |

Best lane: OPT_SELL_NEUTRAL (+$0.65, only positive lanes are SELL). Worst: **FUT_MOMENTUM_CONF −$261.54** (12 trades, 17% win).

**Key finding — aggressive futures is repeating verdict #5/#8 in real time; this is STRATEGY, not an engine bug.** Exit-reason breakdown:

| Exit | Cnt | Net | Avg lev | Avg margin | Avg fees | Avg peak% | Avg pnl% (margin) |
|---|---|---|---|---|---|---|---|
| paper_stop | 13 | −$394.26 | 50× | $250 | $12.50 | 0.5 | −7.1 |
| paper_trail | 5 | −$11.03 | 50× | $250 | $12.50 | 13.6 | +4.1 |

1. **Fees are sane, not the bug.** $12.50 on $12,500 notional = 0.1% (realistic taker round-trip). Margin is the fixed $250 constant; notional = margin × leverage as designed. The old notional-fee pathology is gone.
2. **13 of 18 trades stopped on noise, never going green** (avg peak 0.5%). At 50× a −7% margin stop = a −0.14% price wiggle. The signal isn't predictive on a 1–4 min horizon and the leverage turns every wiggle into a stop. −$394 of the −$405 is these stops.
3. **ENGINE-ADJACENT FLAG — the peak-capture trail is banking ~30% of peak, not the intended ~70%.** paper_trail exits average a 13.6% peak but exit at only +4.1% pnl% (of margin) → net still −$11 after fees. If the trail is meant to lock ~70% of peak it should exit near +9.5%. Either the give-back band is too wide or price polling is too coarse to catch the peak. Worth inspecting the trail logic / sampling cadence — but secondary: even a perfect trail can't rescue a 17%-win, mostly-straight-to-stop entry.
4. **Options SELLING (fixed engine) looks healthy.** 3/3 wins, each rode to ~30% premium decay and banked it green; fees sane; holds 2–37 min. Tiny sample but the fix is behaving as intended — this is the only thing working.

**What we should change:**
1. Futures stop must scale with leverage/volatility — ATR-based or price-based, not a fixed % of margin. As-is, 25–100× + a −7% margin stop = guaranteed churn on sub-0.2% noise (n=13 stops confirms).
2. Investigate the trail give-back: it's banking ~30% of peak vs the intended ~70% (check band width and price-poll granularity).
3. Keep letting the SELL lanes accumulate — they're the only positive lanes; need dozens of closes before crowning.
4. Consider pausing the pure-momentum futures lane (FUT_MOMENTUM_CONF) — it's −$261 of the −$405 and matches the dead "fast 1-min momentum" verdict #3.

**Verdict status:** #6 (OTM selling) 🧪 TESTING — early signs positive but n=3. #8 (aggressive-leverage futures) 🧪 TESTING, **leaning ❌** — first real sample is −40% of bankroll in an hour, exactly as #5 predicted.

### 2026-06-06 19:38 UTC — 2h into clean slate; futures now −62% `[updated by: Cowork]`

**Live-safety flag (read this first):** `bot_status.is_paused` read **false** with `bot_state=running`, scalp + options_scalp enabled. BUT the row's `timestamp` is frozen at **2026-03-11** (stale snapshot or a restart that defaulted to unpaused), and the **last live trade was 2026-06-05 17:47** — i.e. 30 min *before* the explicit `pause` command at 06-05 18:18, and **0 live trades in the last 24h** (`trades` table). So no real money has moved; live is effectively OFF. As a belt-and-suspenders measure I queued a fresh `pause` bot_command (id 319). **Update:** the pause was marked `executed=true` within ~1 min, but `bot_status.is_paused` **stayed false** — so `bot_status` is decoupled from the command processor (stale row; `executed` flipped by a separate worker/trigger). The reliable live-OFF signal is therefore the `trades` table (0 in 24h), NOT the `is_paused` flag, which can't be trusted. **Watch next run:** if any `trades` row appears with timestamp > now, that's a real live-armed alert — don't rely on `is_paused` to tell you.

**Balances & burns** (FUNDED $1,000 each, deposits table shows 0 refills):

| Lab | Funded | Closed P/L | Balance | Burns | Open |
|---|---|---|---|---|---|
| Options (SELL) | $1,000 | +$0.66 | **$1,000.66** | 0× | 39 |
| Futures (aggressive) | $1,000 | −$625.70 | **$374.30** | 0× | 6 |

No refill — both ≫ $50 floor. Futures down −62.6% of bankroll; on this trajectory it will hit the floor and burn within ~1 more hour.

**Per-lane (futures, closed):**

| Lane | Closed | Win% | Net | Avg peak% | Max peak% | Avg hold |
|---|---|---|---|---|---|---|
| **FUT_MOMENTUM_CONF** | 17 | 12% | **−$349.82** | 5.5 | 32.5 | 4.6m |
| FUT_EMA_CONF | 10 | 10% | −$176.85 | 1.6 | 7.7 | 7.6m |
| FUT_DONCHIAN_100X | 1 | 0% | −$49.21 | 0.0 | 0.0 | 0.5m |
| FUT_DONCHIAN_50X | 1 | 0% | −$27.71 | 0.0 | 0.0 | 2.1m |
| FUT_DONCHIAN_CONF | 1 | 0% | −$22.12 | 0.0 | 0.0 | 6.3m |

**Per-lane (options SELL, closed — realized only 6 of 45 trades):**

| Lane | Closed | Win% | Net | Avg peak% | Avg hold |
|---|---|---|---|---|---|
| OPT_SELL_CALL | 1 | 100% | +$0.46 | 31.9 | 1.5m |
| OPT_SELL_NEUTRAL | 2 | 50% | +$0.45 | 15.4 | 29.2m |
| OPT_SELL_CALL_FAR | 1 | 100% | +$0.07 | 30.1 | 6.2m |
| OPT_SELL_PUT | 1 | 100% | +$0.03 | 0.4 | 21.2m |
| OPT_SELL_PUT_FAR | 1 | 0% | −$0.34 | 0.2 | 21.2m |

Best lane: OPT_SELL_CALL +$0.46 (all positive lanes are SELL). Worst: **FUT_MOMENTUM_CONF −$349.82**.

**Futures exit-reason breakdown (this is the whole story):**

| Exit | Cnt | Net | Avg lev | Avg peak% | Avg pnl% (margin) |
|---|---|---|---|---|---|
| paper_stop | 20 | −$547.68 | 43× | 0.5 | −6.7 |
| paper_trail | 8 | −$54.43 | 63× | 11.8 | +3.5 |
| ema21_reclaimed | 2 | −$23.60 | 25× | 2.0 | −2.2 |

**Key findings:**
1. **Aggressive futures = STRATEGY failure, not engine bug (now n=30, confirmed).** 20 of 30 exits are `paper_stop` with avg peak **0.5%** — the trade never went green, just straight to a stop. At 43× avg leverage a −6.7% margin stop ≈ a −0.15% price wiggle. Fees are sane ($12.50 on $12.5k notional = 0.1%). The entries have no edge on a 1–8 min horizon and the leverage converts every micro-wiggle into a realized stop. −$548 of the −$626 is these stops. This is verdict #5/#8 reproducing exactly.
2. **Trail give-back bug persists (now n=8).** paper_trail exits average an 11.8% peak but bank only +3.5% pnl% — i.e. **~30% of peak captured, not the intended ~70%.** Confirmed twice now; worth fixing the give-back band / price-poll cadence. Secondary to the entry problem (even a perfect 70% trail can't rescue a 12%-win lane), but it's leaving ~$50–80 on the table across the trail exits.
3. **Options SELLING (fixed engine) is the only thing not bleeding, but realized sample is starving.** Only 6 of 45 SELL trades have closed; magnitudes are tiny (±$0.50) now that notional is capped and fees are on premium — exactly the fix working. The other 39 are open and accruing theta (holds need hours, by design). We need many more *closes* before crowning — net +$0.66 over 6 is noise.

**What to change:**
1. **Futures stop must scale with leverage/volatility (ATR- or price-based), or cap leverage.** As-is, 25–100× + a fixed −6.7% margin stop = guaranteed churn on sub-0.2% noise. n=20 stops with 0.5% avg peak is now overwhelming evidence. This is the #1 change and it's been the #1 change for 3 check-ins running — nothing in the engine has changed (correctly, per the read-only mandate), so the verdict just keeps hardening.
2. **Strongly consider killing FUT_MOMENTUM_CONF** — it is −$349.82 of the −$625.70 (56%) and matches dead verdict #3 (fast 1-min momentum). The fixed-high-lev Donchian lanes (50×/100×) are also 0% win on tiny samples.
3. **Fix the trail give-back** (band width + poll granularity) so it banks ~70% of peak.
4. **Be patient on SELL** — let the 39 open trades close; the realized sample is what matters, and it's only 6 deep.

**Verdict status:** #6 (OTM selling) 🧪 TESTING — fixed engine behaving, but realized n=6, no edge claim yet. #8 (aggressive-leverage futures) 🧪 TESTING → **now firmly leaning ❌** — −62.6% of bankroll in 2h, 20/30 trades stopped on noise without ever going green. One more sample like this and it earns a ❌ DEAD verdict alongside #5.

### 2026-06-06 20:39 UTC — labs went QUIET; full SELL sample now in `[updated by: Cowork]`

**Live-safety:** `bot_status.is_paused` still reads **false** (stale row, frozen timestamp — same decoupled-flag issue as last run). But **0 `trades` in the last hour AND last 24h**, and the paper engine itself has gone idle (below). Trust the `trades` table, not the flag: **live is effectively OFF.** No alert.

**⚠️ NEW — both paper labs have STALLED.** `now()=20:39 UTC`; **0 open positions on either lab**, and nothing has been *opened* since **19:16 UTC** (~1h23m ago) — last close was 19:24. All the open SELL trades from the 19:38 check-in closed out and the engine has not opened a single new position since. This is why the numbers barely moved vs last run (futures 30→36 closes, options' 39 open all closed). The engine appears to have stopped opening trades (likely tied to the re-pause noted in the prior commit). **This defeats the "keep the labs running forever" goal — no data is being collected.** Restarting/diagnosing the paper engine is the #1 action, but it requires touching the engine/VPS (outside this run's read-only mandate) — flagging for the user.

**Balances & burns** (FUNDED $1,000 each; deposits table shows 0 refills):

| Lab | Funded | Closed P/L | Balance | Burns | Open |
|---|---|---|---|---|---|
| Options (SELL) | $1,000 | −$4.53 | **$995.47** | 0× | 0 |
| Futures (aggressive) | $1,000 | −$628.14 | **$371.86** | 0× | 0 |

No refill — both ≫ $50 floor.

**Per-lane — Options SELL (now FULLY realized, n=45, no open trades left):**

| Lane | Closed | Win% | Net | Avg peak% | Max peak% | Avg hold |
|---|---|---|---|---|---|---|
| **OPT_SELL_CALL** | 9 | 67% | **+$0.96** | 14.8 | 31.9 | 19m |
| OPT_SELL_CALL_FAR | 10 | 40% | +$0.30 | 15.9 | 30.1 | 17m |
| OPT_SELL_PUT_FAR | 7 | 0% | −$1.56 | 1.0 | 7.0 | 11m |
| OPT_SELL_NEUTRAL | 12 | 25% | −$1.86 | 5.4 | 30.6 | 17m |
| OPT_SELL_PUT | 7 | 14% | −$2.36 | 1.1 | 6.8 | 11m |

**Per-lane — Futures (n=36):**

| Lane | Closed | Win% | Net | Avg peak% | Max peak% | Avg hold |
|---|---|---|---|---|---|---|
| **FUT_MOMENTUM_CONF** | 19 | 16% | **−$337.00** | 5.2 | 32.5 | 5m |
| FUT_EMA_CONF | 14 | 14% | −$192.11 | 1.5 | 7.7 | 7m |
| FUT_DONCHIAN_100X | 1 | 0% | −$49.21 | 0.0 | 0.0 | 1m |
| FUT_DONCHIAN_50X | 1 | 0% | −$27.71 | 0.0 | 0.0 | 2m |
| FUT_DONCHIAN_CONF | 1 | 0% | −$22.12 | 0.0 | 0.0 | 6m |

Best lane: **OPT_SELL_CALL +$0.96** (only positive lanes are CALL-side sells). Worst: **FUT_MOMENTUM_CONF −$337.00**.

**Key findings:**
1. **The fixed SELL engine is confirmed SANE — and roughly break-even, not a winner.** With the full sample closed out, every lane's P/L is tiny (±$2.40), exactly as designed once fees are on premium and notional is capped. Net −$4.53 over 45 trades is **noise around flat**, not an edge. The earlier +$0.66 over 6 was small-sample optimism. So the fix worked (no more −$1,455 fee-bug disasters) but the strategy itself hasn't shown a real edge yet — it's harvesting tiny theta and giving most back.
2. **Directional asymmetry exposes residual naked-sell risk.** CALL sells (+$0.96 @67%, +$0.30 @40%) won; PUT sells (−$1.56 @0%, −$2.36 @14%) lost. Spot fell during the window → puts got breached (spot dropped below put strikes) while calls stayed safe. Even with the fixes, naked selling still carries the directional tail #6 warned about — it just no longer detonates the account. Defined-risk spreads remain the real fix.
3. **Aggressive futures unchanged — STRATEGY failure, −$628 (now n=36).** FUT_MOMENTUM_CONF (−$337, 16% win) + FUT_EMA_CONF (−$192, 14% win) are 92% of the loss; matches dead verdicts #3/#5. Nothing new because the lab stalled before adding samples.

**What to change:**
1. **Restart the stalled paper engine** (0 open, none opened in ~90min) so data collection resumes — without it the "run forever" mandate is broken. (Needs engine/VPS access; out of this run's scope — flagged.)
2. **Kill FUT_MOMENTUM_CONF** (−$337 of −$628, dead verdict #3) and **scale the futures stop to leverage/volatility (ATR-based)** — the #1 carry-over for 4 runs straight.
3. **Move option selling to DEFINED-RISK SPREADS** — the naked SELL is sane but edge-less and still directionally exposed (PUT lanes 0–14% win this window). Spreads cap the tail and let theta net out.
4. SELL realized sample is now a real n=45 and says "flat" — stop waiting for naked selling to prove a win; iterate the structure (spreads / strike selection) instead.

**Verdict status:** #6 (OTM selling) 🧪 TESTING → **leaning ⚠️ break-even** — fixed engine is sane but n=45 shows no edge (net −$4.53, tiny magnitudes); needs a structural change (spreads), not more samples. #8 (aggressive-leverage futures) 🧪 TESTING, **firmly ❌-leaning** — −62.8% of bankroll, 33/36 losers concentrated in momentum/EMA; unchanged because the lab is idle.

### 2026-06-06 21:39 UTC — labs RESUMED; high-lev Donchian now confirms loss too `[updated by: Cowork]`

**Live-safety:** `bot_status.is_paused = true` (row stamped 21:37 UTC) — flag now reads OFF cleanly (the prior stale-false issue cleared after the re-pause). No live `options_scalp` trades. **Live is OFF.** No alert.

**✅ STALL RESOLVED — the paper engine is opening trades again.** Last hour: futures **opened 15 / closed 12** (last open 21:38), options **opened 4 / closed 10** (last open 21:19). Both labs have open positions (futures 3, options 4). The ~90-min idle window flagged at 20:39 has ended — data collection has resumed, so the "run forever" mandate is back on track. (No engine change was made from this run; it appears to have restarted on its own / with the re-pause cycle.)

**Balances & burns** (FUNDED $1,000 each; `paper_deposits` shows 0 refills):

| Lab | Funded | Closed P/L | Balance | Burns | Open |
|---|---|---|---|---|---|
| Options (SELL) | $1,000 | −$4.01 | **$995.99** | 0× | 4 |
| Futures (aggressive) | $1,000 | −$850.00 | **$150.01** | 0× | 3 |

No refill — both still ≫ the $50 floor. **Futures is burning ~$220/hr (−$628 → −$850 this hour); at $150 it will likely cross the $50 floor and trigger its first auto-refill within ~1 hour.**

**Per-lane — Options SELL (n=49):**

| Lane | Closed | Win% | Net | Avg peak% | Max peak% | Avg hold |
|---|---|---|---|---|---|---|
| **OPT_SELL_CALL** | 9 | 67% | **+$0.96** | 14.8 | 31.9 | 48m |
| OPT_SELL_CALL_FAR | 10 | 40% | +$0.30 | 15.9 | 30.1 | 43m |
| OPT_SELL_PUT_FAR | 9 | 22% | −$1.45 | 0.8 | 7.0 | 45m |
| OPT_SELL_NEUTRAL | 12 | 25% | −$1.86 | 5.4 | 30.6 | 37m |
| OPT_SELL_PUT | 9 | 33% | −$2.03 | 0.9 | 6.8 | 45m |

**Per-lane — Futures (n=51):**

| Lane | Closed | Win% | Net | Avg peak% | Max peak% | Avg hold |
|---|---|---|---|---|---|---|
| **FUT_MOMENTUM_CONF** | 21 | 14% | **−$365.10** | 4.9 | 32.5 | 5m |
| FUT_EMA_CONF | 14 | 14% | −$192.11 | 1.5 | 7.7 | 7m |
| FUT_DONCHIAN_100X | 6 | 17% | −$185.31 | 7.2 | 28.9 | 2m |
| FUT_DONCHIAN_50X | 5 | 20% | −$60.68 | 5.3 | 12.3 | 3m |
| FUT_DONCHIAN_CONF | 5 | 40% | −$46.78 | 4.5 | 10.4 | 5m |

Best lane: **OPT_SELL_CALL +$0.96** (CALL-side sells are still the only positive lanes). Worst: **FUT_MOMENTUM_CONF −$365.10**.

**Key findings:**
1. **Engine alive again — biggest news of the hour.** The stall is over; both labs added real samples (futures +15 closes, options +4). No further action needed on availability this run.
2. **Futures: high-leverage Donchian lanes now ALSO confirmed as losers (no longer tiny samples).** Last run they were n=1; now FUT_DONCHIAN_100X is n=6 / 17% win / **−$185** and 50X is n=5 / 20% / −$60. Critically, the 100× lane peaks an avg **+7.2% (max +28.9%) and still nets −$185** — it goes green then round-trips through the stop. This is the give-back problem *multiplied by leverage*: the entries aren't even uniformly bad, but with a fixed % stop and no trail/lock-in, every winner reverses into a loss. **Leverage + no profit-lock = guaranteed bleed**, exactly matching verdicts #5/#8.
3. **Options still flat/noise at n=49 (−$4.01).** Unchanged thesis: CALL sells win (+$0.96/+$0.30), PUT sells lose (−$1.45/−$2.03). PUT lanes show **near-zero avg peak (0.8–0.9%)** → spot drifted *down* this window, so the puts were breached almost immediately and never accrued theta, while calls decayed cleanly. The naked sell is sane but directionally one-legged; nothing here is an edge.

**What to change (carry-overs hardening, not new):**
1. **#1 for 5 runs straight — scale the futures stop to leverage/volatility (ATR-based) AND add a profit-lock/trail.** New evidence this run: the 100× lane *reaches* +7–29% peaks before dying. A trail that banks even 50% of peak would flip several of these. Fixed % stop on 50–100× = mathematically doomed.
2. **Kill FUT_MOMENTUM_CONF** — −$365 of the −$850 (43%), 14% win, dead verdict #3.
3. **Move option selling to DEFINED-RISK SPREADS** — caps the one-legged PUT tail and lets theta net; naked SELL is proven flat (n=49) and won't improve with more samples.
4. **Expect a futures auto-refill next run** (~$150 and falling); log it as burn #1 when it trips.

**Verdict status:** #6 (OTM selling) **⚠️ break-even** — n=49, net −$4.01, no edge; needs structural change (spreads), not samples. #8 (aggressive-leverage futures) 🧪 → **now ❌-leaning hard** — −85% of bankroll, and the previously-untested fixed-high-lev Donchian lanes (50×/100×) have now joined the losers (17–20% win), so the loss is no longer just momentum/EMA. One more hour like this earns a full ❌ DEAD alongside #5.

### 2026-06-06 22:39 UTC — futures bankroll fully burned → FIRST AUTO-REFILL (burn #1) `[updated by: Cowork]`

**Live-safety:** `bot_status.is_paused = true` (row stamped 22:37 UTC), `pause_reason = "PAPER-ONLY mode (no live trading)"`, **0** live `options_scalp` trades in the last hour. **Live is OFF.** No alert.

**Engine alive:** last hour futures **opened 15 / last open 22:30 / last close 22:38**, options **opened 7 / last open 22:10**. DB `now()` = 22:38:56 — closes land within ~50s of now, so both labs are actively trading. No stall.

**🔥 AUTO-REFILL FIRED — as predicted last run.** Futures crossed the $50 floor and went negative. Inserted `paper_deposits(futures, 1000, 'refill', 'auto-refill burn #1 …')` (id 3). Futures FUNDED $1,000 → **$2,000**; post-refill balance **$770.40**.

**Balances & burns:**

| Lab | Funded | Closed P/L | Balance | Burns | Open |
|---|---|---|---|---|---|
| Options (SELL) | $1,000 | +$0.66 | **$1,000.66** | 0× | 50 |
| Futures (aggressive) | $2,000* | −$1,229.60 | **$770.40** | **1×** | 6 |

*\*$1,000 original + $1,000 refill. Pre-refill balance was −$229.60.*

**⚠️ Data note — options closed sample reset.** Last run options were n=49 closed; this run only **n=6 closed + 50 open**. The prior closed history was cleared and a fresh 50-position fleet opened this hour. So the +$0.66 is a brand-new tiny sample, not a continuation of the n=49 series. Funding/burns unaffected (still 0 refills, $1,000).

**Per-lane — Futures (n=60, aggregated by setup):**

| Lane | Closed | Win% | Net | Avg peak% | Max peak% | Avg hold |
|---|---|---|---|---|---|---|
| **FUT_MOMENTUM_CONF** | 25 | 16% | **−$500.35** | 6.0 | 32.5 | 6m |
| FUT_DONCHIAN_100X | 8 | 13% | −$244.63 | 7.3 | 28.9 | 3m |
| FUT_EMA_CONF | 14 | 7% | −$244.55 | 2.3 | 7.7 | 8m |
| FUT_DONCHIAN_50X | 7 | 14% | −$143.28 | 5.5 | 12.3 | 8m |
| FUT_DONCHIAN_CONF | 6 | 33% | −$96.80 | 4.5 | 10.4 | 11m |

**Per-lane — Options SELL (n=6, fresh sample):** all five touched lanes flat-to-tiny-green — OPT_SELL_CALL +$0.46, OPT_SELL_NEUTRAL +$0.45, OPT_SELL_CALL_FAR +$0.07, OPT_SELL_PUT +$0.03, OPT_SELL_PUT_FAR −$0.34. Net **+$0.66**. Noise at this n.

Best lane: **FUT_DONCHIAN_CONF −$96.80** (least-bad; only positive-ish futures lane). Worst: **FUT_MOMENTUM_CONF −$500.35** (41% of the loss).

**Key findings:**
1. **Futures aggressive ladder is fully dead — it burned the entire $1,000 bankroll in ~30h.** All 5 lanes negative, total −$1,229.60 closed. This is the textbook give-back, now quantified across the whole book: **avg peak +5.0% vs avg realized −2.7%; 17 of 60 trades peaked ≥+5% then closed red.** Avg leverage 55×. STRATEGY verdict (not an engine bug): entries reach profit but a fixed % stop with no trail/profit-lock round-trips every winner into a loss, and leverage multiplies the bleed. Fees/exits/sizing all behaving as designed — the *design* is the loser.
2. **Auto-refill mechanism works** — floor detection + insert fired cleanly on the first real burn. Refill bookkeeping (FUNDED vs BALANCE vs burns) is correct.
3. **Options is a non-result this hour** — sample was reset to n=6; +$0.66 is noise. Carry the n=49 "flat, no edge, needs spreads" thesis forward; do not over-read the fresh green.

**What to change (single highest-leverage move):**
1. **Neuter the aggressive futures ladder now** — it has spent a full bankroll proving fixed-stop high-leverage = guaranteed bleed. Minimum: kill FUT_MOMENTUM_CONF (−$500, worst lane) and cap leverage ≤10× until an ATR-scaled stop **+ profit-lock/trail** is in place. Banking even 50% of the +5–7% avg peak flips most of these.
2. Carry-overs: ATR stop + trail (#1 for 6 runs), move option selling to defined-risk spreads, expect futures burn #2 within ~3–4h at the current ~$220/hr bleed (now from the $2,000 base).

**Verdict status:** #8 (aggressive-leverage futures) 🧪 → **❌ DEAD.** Full $1,000 bankroll burned; all five lanes (momentum, EMA, Donchian 50×/100×/CONF) negative; the give-back is now a whole-book statistic (peak +5.0% → realized −2.7%), not a per-lane artifact. Joins #5. #6 (OTM selling) **⚠️ break-even** unchanged — options sample reset to n=6 this hour, no new signal; thesis (flat, needs spreads) stands on the prior n=49.

### 2026-06-06 23:39 UTC — burn #1 still bleeding the refill; no burn #2 yet `[updated by: Cowork]`

**Engine alive:** last hour futures **opened 8 / closed 6**, options **opened 3 / closed 4**. DB `now()` = 23:39:31; bot_status `is_paused=true` (last @ 23:37); **0 `options_scalp` trades in last hour** → LIVE confirmed OFF. Both labs actively trading.

**Balances & burns:**

| Lab | Funded | Closed P/L | Balance | Burns | Open |
|---|---|---|---|---|---|
| Options (SELL) | $1,000 | −$1.03 | **$998.97** | 0× | 10 |
| Futures (aggressive) | $2,000* | −$1,393.35 | **$606.65** | **1×** | 2 |

*\*$1,000 original + $1,000 refill (burn #1).* No lab at/under the $50 floor → **no auto-refill this hour.**

**Hour-over-hour:** Futures balance $770.40 → **$606.65 (−$163.75, +6 closed trades)** — bleed continues at ~$160/hr, slightly under the ~$220/hr projection; burn #2 not yet reached (needs another ~$557 of losses, ≈3–4h). Options unchanged-noise; sample grew n=6 → n=10, still −$1.03 total.

**Per-lane — Futures (n=66, aggregated by setup):**

| Lane | Closed | Win% | Net | Avg peak% | Max peak% | Avg hold |
|---|---|---|---|---|---|---|
| **FUT_MOMENTUM_CONF** | 28 | 14% | **−$606.90** | 5.49 | 32.48 | 6.1m |
| FUT_EMA_CONF | 17 | 6% | −$301.74 | 2.01 | 7.65 | 8.4m |
| FUT_DONCHIAN_100X | 8 | 13% | −$244.63 | 7.40 | 28.87 | 2.5m |
| FUT_DONCHIAN_50X | 7 | 14% | −$143.28 | 5.52 | 12.35 | 8.7m |
| FUT_DONCHIAN_CONF | 6 | 33% | −$96.80 | 4.78 | 10.42 | 10.8m |

**Per-lane — Options SELL (n=10):** all lanes flat/tiny — OPT_SELL_CALL +$0.46 (n=1), OPT_SELL_NEUTRAL +$0.07, OPT_SELL_PUT −$0.18, OPT_SELL_CALL_FAR −$0.58, OPT_SELL_PUT_FAR −$0.80. Net −$1.03. Noise at this n.

Best lane: **FUT_DONCHIAN_CONF −$96.80** (least-bad, 33% win). Worst: **FUT_MOMENTUM_CONF −$606.90** (44% of the whole futures loss, now 28 trades at 14% win).

**Key findings:**
1. **Nothing changed in the engine, so the bleed is mechanical and predictable.** Futures lost another ~$164 this hour exactly as the dead-strategy thesis predicts: momentum lane keeps reaching big peaks (avg +5.49%, max +32.48%) on 28 trades and round-tripping through the fixed stop at a 14% win rate. STRATEGY verdict stands — no engine bug; fees/exits/sizing all behaving as designed, the *design* is the loser.
2. **FUT_MOMENTUM_CONF is now unambiguously the single worst lane** (−$606.90, 44% of futures losses). It is the textbook profit-lock candidate: highest avg+max peaks of any lane, lowest realized.
3. **Options remains a non-result** — n=10, −$1.03, no lane with meaningful sample. Thesis (flat, needs defined-risk spreads) unchanged.

**What to change (single highest-leverage move):**
1. **Kill FUT_MOMENTUM_CONF and cap leverage ≤10× until an ATR-scaled stop + profit-lock/trail exists** — unchanged from last 7 runs; the lane has now spent $607 re-proving it. Banking 50% of the +5.49% avg peak flips most of these.
2. Carry-overs: ATR stop + trail (#1 priority), defined-risk spreads on options, expect futures burn #2 in ~3–4h at the current ~$160/hr bleed from the $2,000 base.

**Verdict status:** unchanged. #8 (aggressive futures) **❌ DEAD**; #6 (OTM selling) **⚠️ break-even** (n=10, no signal); #5 still dead. No new verdict changes this hour.

---

### 2026-06-07 00:39 UTC — worst futures hour yet (−$477); burn #2 now imminent `[updated by: Cowork]`

**Engine alive:** last hour futures **opened 25 / closed 24**, options **opened 8** (sample n grew 10→67 as prior open SELLs expired/closed). DB `now()` = 00:39; bot_status `is_paused=true` (last @ 00:37); **0 `options_scalp` trades in last hour** → LIVE confirmed OFF. 0 positions open at this instant (batch just closed), both labs actively cycling.

**Balances & burns:**

| Lab | Funded | Closed P/L | Balance | Burns | Open |
|---|---|---|---|---|---|
| Options (SELL) | $1,000 | −$8.90 | **$991.10** | 0× | 0 |
| Futures (aggressive) | $2,000* | −$1,834.82 | **$165.18** | **1×** | 0 |

*\*$1,000 original + $1,000 refill (burn #1).* Lowest balance **$165.18 > $50 floor → no auto-refill this hour.**

**Hour-over-hour:** Futures balance $606.65 → **$165.18 (−$441.47, +24 closed)** — **the worst hour on record, ~3× the prior ~$160/hr bleed.** This hour's 24 closed futures = **−$476.76, every one of the 5 lanes negative.** Burn #2 is now imminent: only **~$115 of buffer** above the $50 floor → expect the second full-bankroll burn **next hour** at this pace. Options unchanged-noise.

**Per-lane — Futures (n=99, aggregated by setup):**

| Lane | Closed | Win% | Net | Avg peak% | Max peak% | Avg hold |
|---|---|---|---|---|---|---|
| **FUT_MOMENTUM_CONF** | 38 | 18% | **−$743.48** | 5.65 | 32.48 | 6.1m |
| FUT_DONCHIAN_100X | 13 | 8% | −$405.36 | 7.32 | 28.87 | 2.4m |
| FUT_EMA_CONF | 26 | 23% | −$302.22 | 2.54 | 9.36 | 7.9m |
| FUT_DONCHIAN_50X | 12 | 17% | −$230.46 | 5.61 | 12.35 | 11.0m |
| FUT_DONCHIAN_CONF | 10 | 30% | −$155.49 | 4.29 | 10.42 | 10.0m |

**This hour's bleed leaders:** FUT_DONCHIAN_100X −$160.73 (5 closed, avg peak +7.2%) and FUT_MOMENTUM_CONF −$154.95 (7 closed, avg peak +7.3%) — i.e. **the two highest-peak lanes round-tripped the hardest.** FUT_EMA_CONF was nearly flat (−$5.35), the low-peak lane.

**Per-lane — Options SELL (n=67):** all five lanes slightly negative, none with edge — OPT_SELL_CALL_FAR −$0.40, OPT_SELL_CALL −$0.73 (55% win), OPT_SELL_NEUTRAL −$2.09 (35%), OPT_SELL_PUT −$2.82, OPT_SELL_PUT_FAR −$2.95. Net −$8.90 (≈−$0.13/trade). Flat noise at a now-respectable n.

Best lane: **FUT_DONCHIAN_CONF −$155.49** (least-bad, 30% win). Worst: **FUT_MOMENTUM_CONF −$743.48** (40% of the whole futures loss).

**Key findings:**
1. **The no-profit-lock thesis is now ironclad at n=99.** Across **all five** futures lanes the average peak P/L is **positive** (+2.5% to +7.3%) yet **every lane's realized net is deeply negative.** Trades reach the money, the engine holds, and they round-trip through the fixed stop. This hour proved it cleanly: the two highest-peak lanes (100X +7.3%, MOMENTUM +7.3% intraperiod) lost the most; the lowest-peak lane (EMA +2.5%) was nearly flat. **The loss is monotonic in unrealized-peak magnitude — pure round-tripping, not direction.**
2. **STRATEGY verdict, not an engine bug.** Fees/sizing/liq/holds all behave as designed (holds 2–11m, sane; high-lev 100X exits fastest at 2.4m on stops). The *design* lacks a take-profit/trailing exit — the single missing component.
3. **FUT_MOMENTUM_CONF remains the worst lane for the 9th straight run** (−$743, 40% of futures losses, 38 trades at 18% win, biggest peaks).
4. **Options is a clean non-result** — n=67, −$8.90, no lane with edge. Thesis (flat; needs defined-risk spreads) holds, now with real sample.

**What to change (single highest-leverage move):**
1. **Add an ATR-scaled stop + trailing profit-lock that banks ~50% of peak, and kill FUT_MOMENTUM_CONF / cap leverage ≤10×.** Unchanged for 9 runs; the n=99 peak-vs-realized data is now the proof: banking half of each lane's +2.5–7.3% avg peak flips the majority of these trades positive. This is the one change that matters.
2. Carry-overs: defined-risk spreads on options (stop bleeding theta tests with no edge). **Expect futures burn #2 next hour** (~$115 buffer at −$440/hr).

**Verdict status:** unchanged. #8 (aggressive futures) **❌ DEAD**; #6 (OTM selling) **⚠️ break-even** (n=67, still no signal); #5 still dead. No new verdict changes this hour.

---

### 2026-06-07 01:39 UTC — BURN #2 fired; exit-reason split shows the bleed is WRONG ENTRIES, not round-tripping `[updated by: Cowork]`

**Live OFF** (`is_paused=true`, last @ 01:39 UTC; **0 `options_scalp` trades last hour**). Locks: none.

**Balances & burns:**

| Lab | Funded | Closed P/L | Balance | Burns | Open |
|---|---|---|---|---|---|
| Options (SELL) | $1,000 | −$16.39 | **$983.61** | 0× | 6 |
| Futures (aggressive) | $3,000* | −$2,912.03 | **$87.97** | **2×** | 0 |

*\*$1,000 original + $1,000 burn-#1 + $1,000 burn-#2 refill this run (note `auto-refill burn #2 2026-06-07 01:39 UTC`). Pre-refill balance was **−$912.03 ≤ $50 → AUTO-REFILL fired**, restoring to +$87.97.*

**Hour-over-hour:** Futures $165.18 → **−$912.03 before refill** — **this hour closed 39 futures for −$1,041.91, the single worst hour on record (~2.4× the prior −$442 worst).** The burn-#1 refill plus ~$900 more evaporated in one hour. Options −$12.71 (25 closed) — noise.

**Per-lane — Futures (n=129):**

| Lane | Closed | Win% | Net | Avg peak% | Max peak% | Avg hold |
|---|---|---|---|---|---|---|
| **FUT_MOMENTUM_CONF** | 47 | 15% | **−$1,077.57** | 6.83 | 35.37 | 5.2m |
| FUT_DONCHIAN_100X | 20 | 10% | −$729.71 | 6.55 | 29.41 | 2.1m |
| FUT_EMA_CONF | 26 | 15% | −$404.81 | 2.45 | 9.36 | 8.5m |
| FUT_DONCHIAN_CONF | 17 | 24% | −$377.89 | 5.26 | 29.41 | 10.3m |
| FUT_DONCHIAN_50X | 19 | 21% | −$322.05 | 6.41 | 35.89 | 8.0m |

**Per-lane — Options SELL (n=44):** OPT_SELL_PUT_FAR −$5.81 (7% win), OPT_SELL_PUT −$3.70 (21%), OPT_SELL_CALL −$2.82 (33%), OPT_SELL_CALL_FAR −$2.16 (33%), OPT_SELL_NEUTRAL −$1.89 (20%). Net −$16.39 (≈−$0.37/trade). Flat noise.

Best lane: **FUT_DONCHIAN_50X −$322** (least-bad on $). Worst: **FUT_MOMENTUM_CONF −$1,077** (37% of all futures losses; worst lane for the 10th straight run).

**Key findings — exit-reason breakdown finally isolates the bleed (n=129):**

| Exit reason | Closed | Net | Avg peak% | Avg realized% |
|---|---|---|---|---|
| **paper_stop** | 78 | **−$2,787.00** | **+1.31** | **−8.23** |
| paper_trail | 43 | −$78.58 | +13.45 | +5.90 |
| ema21_lost | 3 | −$44.30 | +2.54 | −3.41 |
| ema21_reclaimed | 3 | −$36.65 | +2.11 | −2.39 |
| donchian_mid_revert | 1 | −$12.72 | +4.93 | −2.59 |
| paper_max_hold | 1 | +$47.23 | +27.42 | +23.89 |

1. **96% of the entire futures loss is `paper_stop` (78 trades, −$2,787), and their avg PEAK is only +1.31%.** These entries go **against almost immediately** and never reach the money, then exit at −8.23% realized under leverage. **This corrects last hour's "pure round-tripping" read:** the dominant failure is **wrong-direction entries with no edge**, not winners giving back gains.
2. **The `paper_trail` cohort is actually FINE** — 43 trades, avg peak +13.45%, **avg realized +5.90%**, net only −$78.58. When a trade goes the right way the trailing exit banks ~44% of peak. **Exit logic works; entries do not.**
3. **STRATEGY verdict confirmed (not engine bug).** Fees/sizing/liq/holds all sane. Defect = the entry filter (breakouts chopped on crypto noise) amplified by 25–100× leverage → −8% per wrong entry.
4. **Options clean non-result** at n=44, −$16.39 — no lane with edge.

**What to change (single highest-leverage move):**
1. **Attack the entries, not the exits.** Require a pullback/retest before breakout entry (stop chasing) and cap leverage ≤10× so a wrong entry costs ~−2% not −8%. The profitable `paper_trail` winners prove the exit side already works — fix entries and the lab flips. Throttle/kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (60% of the loss).
2. Carry-over: defined-risk spreads on options.

**Verdict status:** unchanged. #8 (aggressive futures) **❌ DEAD** (now **2 full-bankroll burns**); #6 (OTM selling) **⚠️ break-even** (n=44, no signal); #5 dead. New actionable signal: the `paper_stop` +1.31% avg-peak data points the fix at entry quality + leverage, not exit logic.

---

### 2026-06-08 22:39 UTC - check-in `[updated by: Cowork]`

**What's happening:** Bot LIVE OFF (`is_paused=true`, reason "PAPER-ONLY mode"; uptime ~49h). 2 active strategies (scalp + options_scalp). Market regime TRENDING_DOWN, chop 0.46. Open now: **3 futures** (1 MOMENTUM, 2 EMA), **8 options SELL**. Live delta balance $27.08, 0 live positions.

**What happened since last check (gap ~45h since 06-07 01:39):** Huge sample growth, not an hourly tick.
- **Futures:** +890 closed, **-$16,029**. Cumulative now **n=1,019 closed, net ~-$18,941**, win 13-33% by lane.
- **Options SELL:** +509 closed, **-$287**. Cumulative **n=591 closed, net -$307.77**, win 6.6-18.3%.
- Worst lane unchanged for the 11th run: **FUT_MOMENTUM_CONF -$8,315** (44% of futures loss; n=441, 13.4% win, avg lev 67.6x).

| FUT lane | Closed | Win% | Net | Avg lev | Avg peak% | Hold |
|---|---|---|---|---|---|---|
| FUT_MOMENTUM_CONF | 441 | 13.4 | **-8,315** | 67.6 | 8.98 | 4.8m |
| FUT_DONCHIAN_100X | 117 | 15.4 | -4,179 | 100 | 9.45 | 2.3m |
| FUT_DONCHIAN_CONF | 111 | 23.4 | -2,335 | 56.5 | 7.66 | 5.6m |
| FUT_DONCHIAN_50X | 112 | 19.6 | -2,123 | 50 | 6.65 | 5.0m |
| FUT_EMA_CONF | 238 | 33.2 | -1,989 | 29.8 | 5.76 | 9.8m |

**The new thing - exit-reason split now overwhelming (n=1,019 FUT):**

| Exit | Closed | Net | Avg peak% | Avg realized% |
|---|---|---|---|---|
| **paper_stop** | 569 | **-20,985** | +1.51 | -8.65 |
| paper_trail | 390 | **+819** | +15.77 | +6.91 |
| paper_max_hold | 18 | **+1,712** | +51.44 | +43.88 |
| ema21_lost/reclaimed | 40 | -460 | ~2.2 | ~-2.1 |

1. **The entry-quality thesis is now ironclad.** `paper_stop` = 569 trades, -$20,985 (more than the entire net loss; the book is only -$18.9k because trail/max_hold are positive). Their avg PEAK is just **+1.51%** - these entries go wrong-direction immediately and exit at -8.65% under leverage. Pure bad entries, not round-tripping winners.
2. **Both exit cohorts that let trades breathe are net POSITIVE:** paper_trail +$819 (realized +6.91%) and paper_max_hold +$1,712 (realized +43.88% on 18 survivors). Exit logic works; the entry filter does not.
3. **Options is a clean non-result** at real n=591: -$307.77, no lane with edge, avg peak <3% everywhere.

**Engine-bug status (vs known issues 2026-06-06):**
- **sell_breached "fires on nearly all sells in 15-25m" - appears FIXED.** Now only **50/591 (8.5%)** of option exits; `sell_take_profit` is dominant (382). Bug resolved or greatly reduced.
- **Option-sell fee drag - STILL PRESENT.** `sell_take_profit` books +0.50% gross avg yet nets **-$73.40 over 382 trades (-$0.19/trade)**; avg fees ~$0.58-0.59/trade eat the entire TP edge. Fees still computed on underlying notional.
- **Futures paper_max_hold ~30m scalp-cap - mostly moot.** Holds are 2.3-9.8m; stops fire first, so max_hold rarely triggers (18/1,019). The 18 that survive return +43.88% - direct evidence that capping winners early is leaving money on the table.

**What we should change:**
1. **Fix entries, not exits (STRATEGY).** Require pullback/retest before breakout entry and cap leverage <=10x so a wrong entry costs ~-2% not -8.65%. The +EV trail/max_hold cohorts prove the exit side already works; entry quality + leverage is 100% of the bleed.
2. **Kill/throttle FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X** (together -$12,495 = 66% of futures loss).
3. **ENGINE BUG: recompute option-sell fees on premium/margin, not underlying notional** - this alone flips the 382-trade TP cohort from -$73 to clearly positive.

**Verdict status:** #8 (aggressive futures) **DEAD** (now ~-$18.9k, n=1,019). #6 (OTM option selling) **break-even-negative** - at n=591 the strategy has no directional edge and is additionally bled by the unresolved fee bug. #5 still dead. New: sell_breached bug looks fixed; fee-drag bug confirmed still live.

---

### 2026-06-08 23:39 UTC - check-in `[updated by: Cowork]`

**What's happening:** Bot LIVE OFF (`is_paused=true`, "PAPER-ONLY mode"; uptime ~50.3h). 2 active strategies (scalp + options_scalp), 0 live positions, delta balance $27.08. Regime TRENDING_DOWN, chop 0.571. Open now: **8 futures** (3 MOMENTUM incl 1x100lev + 1x50lev, 5 EMA @25lev), **46 options SELL**.

**What happened since last check (gap ~1h since 22:39):** Quiet hour, no burn.
- **Futures:** +12 closed, **-$141.63** (n=1,019->1,031; net -$18,941 -> **-$19,082.63**). Bleed led by FUT_EMA_CONF -$64 (3 closed) and FUT_DONCHIAN_100X -$41 (1 closed). MOMENTUM near-flat this hour (-$1.89, 6 closed).
- **Options SELL:** net **-$313.36** (n=570 on my filter `setup_type ilike '%SELL%'`; ~-$0.55/trade). Note: prior entry's "591/-$307.77" used a looser count - flagging the filter mismatch, not a data loss. Still flat noise.

| FUT lane | Closed | Win% | Net | Avg lev | Avg peak% | Hold |
|---|---|---|---|---|---|---|
| FUT_MOMENTUM_CONF | 447 | 13.6 | **-8,316.89** | 67.5 | 9.10 | 4.9m |
| FUT_DONCHIAN_100X | 118 | 15.3 | -4,219.74 | 100 | 9.37 | 2.3m |
| FUT_DONCHIAN_CONF | 112 | 23.2 | -2,337.10 | 56.5 | 7.66 | 5.7m |
| FUT_DONCHIAN_50X | 113 | 19.5 | -2,155.55 | 50 | 6.59 | 4.9m |
| FUT_EMA_CONF | 241 | 32.8 | -2,053.35 | 29.9 | 5.70 | 9.8m |

**The new thing - exit-reason splits, both books:**

FUT (n=1,031):
| Exit | Closed | Net | Avg peak% | Avg real% |
|---|---|---|---|---|
| **paper_stop** | 577 | **-21,203.73** | +1.50 | -8.62 |
| paper_trail | 393 | **+799.21** | +15.75 | +6.89 |
| paper_max_hold | 19 | **+1,808.32** | +52.26 | +43.99 |
| ema21_lost/reclaimed | 40 | -459.61 | ~2.2 | ~-2.1 |

OPT SELL (n=570):
| Exit | Closed | Net | Avg hold | Avg fee |
|---|---|---|---|---|
| sell_take_profit | 391 | -76.51 | 35.8m | $0.584 |
| sell_stop | 126 | -179.10 | 33.3m | $0.589 |
| sell_breached | 53 | -57.74 | 11.9m | $0.593 |

1. **Entry-quality thesis still ironclad (FUT).** `paper_stop` = 577 trades, **-$21,203** (larger than the whole -$19.1k book; trail +$799 and max_hold +$1,808 are the only green). Avg peak of stopped trades is just +1.50% -> wrong-direction entries dying at -8.62% under leverage. Exits work (trail bank ~44% of peak; the 19 max_hold runners avg +44% realized). Entries do not.
2. **BUG UPDATE - sell_breached looks FIXED.** It was "firing on nearly all sell trades in 15-25min"; now it's only **53 of 570 (9%)** at 11.9m avg hold. `sell_take_profit` (391, 69%, 35.8m) now dominates options exits. The premature-breach exit is no longer the driver.
3. **BUG STILL PRESENT - options fee drag.** Avg fee ~$0.585/trade on ~$984 notional; book loses ~$0.55/trade -> **fees are ~100% of the loss** (gross PnL ~breakeven). Fee charged on underlying notional swamps the thin premium edge. Options can't print until this is fixed.
4. **BUG STILL PRESENT - futures leverage/stop.** No engine change; high-lev lanes (MOMENTUM 67x, 100X) keep converting +1.5% adverse moves into -8.6% realized.

**What we should change:**
1. **Options: fix the fee model first.** Charge fees on premium/stake, not underlying notional. At ~$0.58 flat fee the strategy is structurally dead regardless of signal. (Engine bug, not strategy verdict.)
2. **Futures: attack entries + cap leverage <=10x** (pullback/retest before breakout; kill/throttle MOMENTUM_CONF + DONCHIAN_100X = 65% of the loss). Unchanged recommendation; the paper_stop +1.50%-peak data keeps pointing here. (Strategy verdict, exit logic already works.)
3. Consider loosening `paper_max_hold` - the 19 trades that reached it averaged +44% realized; the cap may be clipping the rare big winners.

**Verdict status:** unchanged. #8 (aggressive futures) **DEAD** (2 prior burns; quiet -$142 hour, no new burn); #6 (OTM selling) **break-even/fee-capped** - now flagged as an engine fee bug, not just "no edge." No new verdicts; samples are large enough (FUT n=1,031, OPT n=570) but no lane has shown a real edge.

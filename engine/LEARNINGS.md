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
| 8 | **Futures at HIGH leverage (confidence ladder 25–100×)** | 1,468 paper trades, 26 burns ($26k refilled) | −$26.7k closed; win decays 34%@~30× → 14%@67× → 16%@100×; 828 noise-stops at 0% win = 113% of all loss; burn cadence compressed 3h→1h | ❌ **DEAD — the definitive sample.** Leverage was the loss engine, not the entries: stops lived in leveraged-PnL space so a 0.09% wiggle killed every trade at 67×. MOMENTUM_CONF + DONCHIAN_100X alone = 65% of the loss. |
| 9 | **OTM option SELLING at scale (5 lanes, $250 margin)** | 742 paper closes | net −$421 but **gross +$27 (BREAKEVEN)** — fees were $448, > 100% of the loss; avg hold ~10 min, avg peak 0.1–0.6% | ❌ as built — selling died of **CHURN + fees**, not direction. 10-minute holds can't harvest theta. Re-testable only with: real credit (closer strikes), hours-long holds, fewer trades, real fee model. → V3. |
| 10 | **The fat tail is the only proven money-maker** | full 1,468-trade futures sample | peak <2%: 635 trades 0% win −$22.5k · peak 25–50%: 91% win +$1,470 · peak 50%+: **97% win +$3,719** · hold <10min: 15% win −$28.5k · hold 10–60min: **51% win +$1,788** · held >1h: **exactly 1 trade ever** | 🟢 **THE EDGE.** Winners exist and are huge — the system just never let trades live long enough to find them. Survive the first 10 minutes → coin flips into profit. V3 is built to maximize survival. |

## Hard-won principles
- **Win rate ≠ profit.** Trend lanes hit 60%+ win but still lost — the exits gave back the ~34% avg peaks while losers ran. Risk/reward and exit quality matter more than hit rate.
- **Buying options has a structural tax** (theta decay + wide Delta spreads + slippage). Directionally-right trades still lose. Don't fight it.
- **Forward-test in paper before real money.** Small-sample "100% win" lanes evaporated at scale. Need hundreds of trades per lane before trusting a verdict.
- **Scaling bankroll ≠ edge.** The $100→$1,000 bump just lost 10× faster. Find edge first, size second.
- **Regime matters.** Trend strategies need trending tape; they get shredded in chop. ~most BTC/ETH intraday windows here have been choppy.
- **Always verify the deploy CONCLUSION** (not just "completed") — the VPS deploy fails intermittently and silently serves the old build.
- **Stops must live in PRICE space, not leveraged-PnL space.** A fixed −6% PnL stop at 67× is a 0.09% price wiggle — that single design error produced 828 stop-outs at 0% win (113% of all futures loss). Stop distance = f(ATR), never f(leverage). Leverage scales the payoff; it must never decide where the exit is.
- **Exits were NEVER the problem.** Across every era: paper_trail +$1.6k (51% win), paper_max_hold +$2.4k (83% win @ +47% peak). All loss came from entries dying before the trade was ever in the money. Attack entries, keep exits.
- **Survival time IS the edge.** <10 min hold = 15% win, −$28.5k. 10–60 min = 51% win, +$1,788. Only 1 trade in 1,468 ever held >1h — the "ride the wave" thesis was never actually tested until V3.
- **Fees are a strategy filter.** Selling gross was breakeven; fees made it a loser. Any lane that can't beat REAL exchange fees (Delta: 0.03% notional capped at 10% premium, +18% GST) must die in paper, not live.
- **Confidence is a valid GATE, never a SIZER.** Conf 80+ reached the 10%+ peak tail 31% vs 15% for conf<70 — real signal. But laddering leverage onto it (V2) chained the best setups to the worst leverage. Gate entries at conf≥70, size flat.

## Current direction — V3 (started 2026-06-09, fresh $1,000 each, history preserved)
**Futures (5 lanes):** pullback/retest entries only (EMA-PB at 10× AND 20× as a clean leverage A/B, Donchian fresh-break-no-chase 10×, VWAP bounce 10×, liquidity-sweep SFP 15×). Fixed leverage, conf≥70 gate, chop filters, **ATR price stops (1.6×)**, breakeven ratchet at +1.2 ATR, chandelier trail (1.8 ATR), stagnation purge (2h flat), 24h max hold, $100 margin/trade.
**Options (3 lanes):** premium selling rebuilt anti-churn — 2-OTM strikes (credit ≥$2 or skip), 15m signals, 15-min re-entry cooldown, ≥4h expiry runway, REAL Delta fees, TP +50% decay / breach / trend-break exits, $100 margin/trade.
**Gate to live (real ~$50):** a lane needs profit factor >1.0 over ~200 trades. Then live tiny at 1–2% risk/trade. Live stays OFF until explicitly approved.

---

## Check-in log (2-hourly routine)

### 2026-06-11 17:40 UTC — V3 ~44.3h in: futures −$540.46 (n=190 closed), options −$57.49 (n=85 closed), burns 0, live OFF; **VERIFICATION HOUR ~22.** **HEADLINE — clean hour on the deploy front (0 `engine_restart` closes, no mid-window deploy), but a TRENDING_UP up-tape ran over the fresh CALL-premium sellers, and `settled_otm` is STILL EXACTLY 0 (and `settled_itm` 0) across the ENTIRE era.** **Options WORSENED −$5.94** (−51.55 → −57.49) on **5 closes**, reconciles to the cent: two early CALL_V3 `sell_take_profit` greens (+1.47, +1.02 = +2.49) were swamped by three losers — RANGE_V3 `sell_breached` −1.36, then **two CALL_V3 sells opened 17:18Z and cut within ~12 min** as BTC pushed up (regime `TRENDING_UP`, net_change_30m +2.2%): `sell_breached` −2.42 and `sell_trend_break` −4.66 (= −7.08). Net −1.36 +2.49 −7.08 = **−5.95 ≈ −5.94** (n 80→85). The trend-break/breach protection is **working as designed** — short-call premium got run over by the up-move and was cut fast, not churned. **Futures WORSENED −$0.21** on a **single close**: FUT_DONCHIAN_RT_10X `breakeven_stop` −0.22 (reconciles, n 189→190) — gate near-silent again, the BE-stop did its job (tiny loss, not a full paper_stop). **The DK fix recommended for 5 STRAIGHT HOURS (drop the 60% TP + freeze deploys in the 07:30–11:18Z hold window) is STILL not implemented** — `settled_otm`/`settled_itm` remain 0 era-wide for the 6th+ straight settlement; the hold-through-settle design has **literally never once held to a 12:00Z settle.** DK cohort frozen unchanged (DK_V3 2/+0.26, DK_PUT 2/+0.21, DK_CALL 2/−0.01 = +0.46 over 6). **paper_stop futures 89/−610.91**, share of gross futures loss **86.9%** (610.91/702.77) — flat; `paper_trail` 47/+113.38 remains the only big net-green exit. **Both retirements STILL STICK** — SFP_15X frozen 57/−180.84 (PF **0.18**, worst net), last open 07:45Z; EMA_PB_20X frozen 31/−137.58 (PF 0.26), last open 06-10 19:15Z; **zero opens in 2h** for either. Futures active lanes (era): **DONCHIAN best** 36/−71.04 (PF **0.31**), EMA_PB_10X 47/−106.28 (PF 0.22), VWAP 19/−44.73 (PF **0.19**); **no futures lane PF>1, book structurally negative.** Options lanes: **PUT_V3 least-bad** 27/−15.45 (PF **0.46**), CALL_V3 31/−20.31 (PF 0.37), RANGE_V3 21/−22.19 (PF **0.20**, worst net), DK cohort tiny-positive n=2 each. **No lane near the PF>1 / n~200 live gate — no strategy crowned.** **LIVE OFF & rails trivially intact** — `bot_status.is_paused=true` (pause_reason "LIVE_MODE=mirror (legacy live paths blocked)"), 0 options_scalp last hour, **0 `live_mirror` trades ever** (0 open, $0 collateral — collateral/1-open/−$3 rails cannot breach at 0 trades; Delta wallet $27.08 untouched). Open now: **1 future** (DONCHIAN_RT_10X), **1 option** (RANGE_V3). No engine bug — every close reconciles to the cent. Balances: Futures **$459.54**, Options **$942.51** — both ≫ $50, no refill. **NEXT (6th hr recommending): implement the DK 60%-TP relax + freeze deploys during the hold window so a strangle finally rides to a 12:00Z settle — this is the ONLY blocker to the strangle-vs-trend-pick test, and `settled_otm` stays 0 forever until it ships.** `[updated by: alpha-paper-lab-monitor]`

### 2026-06-11 16:37 UTC — V3 ~43.3h in: futures −$540.25 (n=189 closed), options −$51.55 (n=80 closed), burns 0, live OFF; **VERIFICATION HOUR ~21 (13:38/14:38/15:38 slots all skipped — this entry spans the full ~4h since 12:39).** **HEADLINE — yet another mid-window deploy killed open positions, and `settled_otm` is STILL EXACTLY 0 (and `settled_itm` 0) across the ENTIRE era.** An engine restart at ~16:35Z (deploy of the two cosmetic status-chip commits `7502250` + `fccb64b`) closed **8 open options at mark** via `engine_restart`: RANGE_V3 ×4 −2.24, CALL_V3 ×2 −1.00, PUT_V3 ×2 −0.89 (= −4.13). On top of that, **4 `sell_trend_break` protection exits** fired on a RED roll (PUT_V3 ×3 −3.49, RANGE_V3 ×1 −0.74 = −4.23), partly offset by the lone green, 1 CALL_V3 `sell_take_profit` +1.84. **Options WORSENED −$6.52** (−45.03 → −51.55): −4.13 −4.23 +1.84 = **−6.52, reconciles to the cent** (13 closes, n 67→80). **The DK fix recommended for 4 STRAIGHT HOURS (drop the 60% TP + freeze deploys 11:00–12:00Z) is STILL not implemented** — the only engine commits this window were status-chip cosmetics, and deploying them mid-period AGAIN proved the restart-kills-open-positions failure mode. No DK trades open/closed this window (today's window already shut pre-12:00); DK cohort frozen unchanged (DK_V3 2/+0.26, DK_PUT 2/+0.21, DK_CALL 2/−0.01 = +0.46 over 6). **Futures WORSENED −$5.03** (−535.22 → −540.25) on a **single close**: FUT_VWAP_10X `paper_stop` −5.03 — **reconciles to the cent** (n 188→189). **paper_stop now 89/−610.91**, share of gross futures loss **87.0%** (610.91/702.55) — flat vs last hour's 86.9%. **Gate still clean** — near-zero futures throughput this window (1 close, 0 futures open now); options opens htf-aligned, no counter-trend leakage. **Both retirements STILL STICK** — SFP_15X frozen 57/−180.84 (PF **0.18**, worst), EMA_PB_20X frozen 31/−137.58 (PF 0.26), zero new opens. Futures active lanes (era): DONCHIAN best 35/−70.82 (PF **0.31**), EMA_PB_10X 47/−106.28 (PF 0.22), VWAP 19/−44.73 (PF **0.19**); **no futures lane PF>1, book structurally negative.** Options lanes: PUT_V3 least-bad 27/−15.45 (PF **0.46**), CALL_V3 27/−15.73 (PF 0.38), RANGE_V3 20/−20.83 (PF **0.21**, worst), DK cohort tiny-positive n=2 each. **No lane near the PF>1 / n~200 live gate — no strategy crowned.** **LIVE OFF & rails trivially intact** — `bot_status.is_paused=true`, 0 options_scalp last hour, **0 `live_mirror` trades ever** (0 open, $0 collateral — collateral/1-open/−$3 rails cannot breach at 0 trades). Legacy `options_scalp` (era-2) sits 1396 closed/−97.05 all-time but **0 in the last hour** — dormant, not active. Open now: 0 futures, **3 options** (CALL_V3 ×2, RANGE_V3 ×1). No engine bug — every close reconciles to the cent. **NEXT (5th hr recommending, now urgent): implement the DK 60%-TP relax + freeze deploys during hold windows, AND batch cosmetic/status-chip deploys OUTSIDE any open-position window — every deploy this era has mark-closed live trades, and until that stops `settled_otm` stays 0 forever and the strangle-vs-trend-pick test can never run.** `[updated by: alpha-paper-lab-monitor]`

**Balances:** Futures lab **$459.75**, Options lab **$948.45** — both ≫ $50, no refill. Burns **0**.

### 2026-06-11 12:39 UTC — V3 ~39.3h in: futures −$535.22 (n=188 closed), options −$45.03 (n=67 closed), burns 0, live OFF; **VERIFICATION HOUR 17.** **DK HEADLINE (now structural, 3rd day): the 12:00Z daily settlement just passed and AGAIN there was nothing to settle — today's DK window had already fully closed pre-12:00 (per last hour: all 6 DK legs exited 08:34–10:31Z via `sell_take_profit`/`engine_restart`). `settled_otm` count across the ENTIRE era is still EXACTLY 0 — the hold-through-settle design has, for the third straight settlement, never once produced a held-to-settle result.** No DK closes this hour; cohort unchanged (DK_V3 2/+0.26, DK_PUT 2/+0.21, DK_CALL 2/−0.01 = +0.46 over 6). **paper_stop UNFROZE after 3 frozen hours** — futures took 4 fresh full stops this hour: EMA_PB_10X ×2 −8.62, VWAP −6.18, DONCHIAN −5.34 (= −20.14), partly offset by 2 `paper_trail` greens (EMA_PB_10X +0.35, VWAP +0.32 = +0.67). **Futures WORSENED −$19.47** (−515.75 → −535.22): −20.14 + 0.67 = **−19.47, reconciles to the cent** (6 closes, n 182→188). paper_stop now **88/−605.88** (was frozen 84/−585.74); paper_stop share of gross futures loss **86.9%** (605.88/697.52) — held ~flat vs last hour's 86.5%, the gate+trail still cap the *share* but a whipsaw stopped out the gated longs. **Options WORSENED −$4.67** (−40.36 → −45.03): 3 `sell_trend_break` protection exits (RANGE −1.91, PUT_V3 ×2 −2.76 = −4.67, **reconciles**, n 64→67) — trend_break only fires when RED, so the up-tape rolled against the short premium and the lane cut it; this is protection working, not churn. **Gate flawless 17th straight hr** — 4 new opens this hour, 0 counter-trend (0/4 htf≠+1). **Both retirements STILL STICK** — SFP_15X frozen 57/−180.84 (PF **0.18** worst), EMA_PB_20X frozen 31/−137.58 (PF 0.26), zero new opens since 08:33Z. Futures active lanes (era): DONCHIAN best 35/−70.82 (PF **0.31**), EMA_PB_10X 47/−106.28 (PF 0.22), VWAP 18/−39.70 (PF 0.21); **no futures lane PF>1, book structurally negative.** Options lanes: PUT_V3 least-bad 22/−11.07 (PF **0.54**), CALL_V3 24/−16.57 (PF 0.31), RANGE_V3 15/−17.85 (PF 0.24), DK cohort tiny-positive n=2 each. **No lane near the PF>1 / n~200 live gate — no strategy crowned.** **LIVE OFF & rails trivially intact** — `bot_status.is_paused=true`, 0 options_scalp last hour, **0 `live_mirror` trades ever** (0 open, $0 collateral — collateral/1-open/−$3 rails cannot breach at 0 trades). **Book is fully FLAT right now** — 0 open futures, 0 open options. No engine bug — every close reconciles to the cent. **NEXT (4th hr recommending): drop/raise the DK 60% take-profit so a strangle can finally ride to the 12:00Z settle, AND freeze deploys 11:00–12:00Z — until both the early-TP and mid-window restarts stop pulling legs, `settled_otm` will stay at 0 forever and the strangle-vs-trend-pick test cannot run.** `[updated by: alpha-paper-lab-monitor]`

### 2026-06-11 11:38 UTC — V3 ~38.3h in: futures −$515.75 (n=182 closed), options −$40.36 (n=64 closed), burns 0, live OFF; **VERIFICATION HOUR 16 (10:38 slot skipped — this entry spans the full ~2h since 09:38).** **DK HEADLINE: today's daily DK window ran end-to-end (entries 07:30→11:18Z, all 6 DK trades now closed, none open) and produced ZERO `settled_otm` for the SECOND straight day — the hold-through-12:00-settle design has LITERALLY NEVER ONCE held to settlement.** Every DK exit this era was either `sell_take_profit` (60% credit, pulled off early) or `engine_restart` (closed at mark). Today's DK closes: DK_V3 +0.28 `sell_take_profit` (08:34Z) → DK_V3/DK_PUT/DK_CALL all `engine_restart` at 09:05Z (−0.01/−0.01/−0.20, the deploy-kill carried over from last hour) → then **post-restart legs DK_CALL +0.18 (10:04Z) and DK_PUT +0.22 (10:31Z) BOTH closed `sell_take_profit`, NOT held to settle.** So even with no restart in the back half, the **60% take-profit itself defeats hold-to-settlement** — it's not only the restarts. Net the DK cohort is tiny-positive (DK_V3 2/+0.26, DK_PUT 2/+0.21, DK_CALL 2/−0.01 = +0.46 over 6 trades) but the strangle-vs-trend-pick test it exists for cannot run while the 60% TP and mid-window deploys keep pulling legs off. **VERY QUIET 2h** — only ~3 futures + ~3 options closes total. Futures WORSENED −$0.91 (−514.84 → −515.75): the visible closes EMA_PB_10X `breakeven_stop` −0.73 + DONCHIAN `breakeven_stop` −0.18 = −0.91, third close ≈$0.00, **reconciles to the cent.** Options IMPROVED +$0.41 (−40.77 → −40.36): DK_CALL +0.18 + DK_PUT +0.22 = +0.40 (≈ +0.41 w/ rounding), **reconciles.** **paper_stop FROZEN 3rd straight hr 84/−585.74 — zero new full stops this window**; paper_stop share of gross futures loss now **86.5%** (585.74 / 677.38 total gross loss) — first sustained read **below ~100%**, the HTF-gate + trail are demonstrably keeping throughput off the full stop. paper_trail 45/+112.70 (only net-green futures exit, also frozen), breakeven_stop 35/−19.20, engine_restart 7/+0.30 (still net-positive — restart-close is benign on net). **Both retirements STICK** — ZERO new FUT_SFP_15X or FUT_EMA_PB_20X opens since the 08:33Z retire (SFP frozen 57/−180.84 PF **0.18** worst, EMA_PB_20X frozen 31/−137.58 PF 0.26). **Gate flawless 16th straight hr** — every new open htf-aligned, zero counter-trend leakage. Futures lanes (era): DONCHIAN best 34/−65.48 (PF **0.33**), VWAP 16/−33.84 (PF 0.24), EMA_PB_10X 44/−98.02 (PF 0.24); **no futures lane PF>1, book structurally negative.** Options lanes: PUT_V3 least-bad 20/−8.31 (PF **0.61**), CALL_V3 24/−16.57 (PF 0.31), RANGE_V3 14/−15.94 (PF 0.26), DK cohort tiny-positive but n=2 each. **No lane near the PF>1 / n~200 live gate — no strategy crowned.** **LIVE OFF & rails trivially intact** — `bot_status.is_paused=true`, 0 options_scalp last hour, **0 `live_mirror` trades ever** (0 open, $0 collateral — cannot breach the collateral/1-open/−$3 rails at 0 trades). Open now: 2 futures (EMA_PB_10X, VWAP), 3 options (PUT_V3 ×2, RANGE_V3) — no DK open, window closed. No engine bug — all closes reconcile to the cent. **NEXT: drop/raise the DK 60% take-profit so the strangle actually rides to the 12:00Z settle (the design under test) AND freeze deploys 11:00–12:00Z — both the TP and restarts are independently preventing any `settled_otm` result.** `[updated by: alpha-paper-lab-monitor]`

### 2026-06-11 09:38 UTC — V3 ~36.3h in: futures −$514.84 (n=179 closed), options −$40.77 (n=62 closed), burns 0, live OFF; **VERIFICATION HOUR 14 — DK strangle legs finally FILL, but `engine_restart` closes them at mark BEFORE the 12:00 settle — the restart-close feature is now actively defeating the DK hold-through-settlement design.** **TWO engine restarts this hour** (deploys at 08:44Z = the SFP-retirement deploy `daf6d3c`, and 09:05Z = real-money-arming commit `dfecc5c`). **13 of 14 closes this hour were `engine_restart`** (the lone exception: 1 DONCHIAN `breakeven_stop` −0.10) — throughput this hour was almost entirely restart churn, not strategy exits. **(1) SFP retirement orphan closed clean:** the pre-retire FUT_SFP_15X long (07:45Z) closed **`engine_restart` +$5.67** at 08:44Z — validates restart-closes-at-mark, and **ZERO new SFP opens since the 08:33Z retire → retirement STICKS** (SFP now frozen 57/−180.84, +5.67 from the orphan win). EMA_PB_20X retirement also still frozen 31/−137.58, 0 new opens. **(2) DK strangle FIRST FILLS of the era** — DK_CALL, DK_PUT, DK_V3 all filled in the 08:46–09:06Z window (2-OTM/$0.50 gate working) — **but the 09:05Z restart immediately closed the strangle legs at mark** (DK_PUT `engine_restart` −0.01, DK_CALL −0.20, DK_V3 −0.01) **before they could hold to the 12:00Z settle.** They re-opened after the restart, but if another deploy lands before 12:00Z they get killed again. **This is the headline issue: frequent deploys during the DK hold window (entry 07:30→11:18Z, settle 12:00Z) repeatedly close DK trades at mark, so the strangle-vs-trend-pick test will NEVER produce a `settled_otm` full-credit result.** **Futures WORSENED −$1.59** (−513.25 → −514.84): 5.67 −0.70 −2.26 −1.03 −0.10 −1.66 −1.51 = **−1.59, reconciles to the cent.** **Options ~flat +$0.11** (−40.88 → −40.77), 7 tiny restart/be closes summing +0.13 (≈ within 2c rounding). **Gate mechanically flawless 14th straight hour** — every futures close htf=+1 in the up-tape, zero counter-trend leakage. Futures lanes: DONCHIAN best (33/−65.29, PF **0.33**), VWAP 15/−33.84 (PF 0.24), EMA_PB_10X 43/−97.29 (PF 0.24); **no futures lane PF>1, book structurally negative.** Options: PUT_V3 least-bad (20/−8.31, PF **0.61**), CALL_V3 24/−16.57 (PF 0.31), RANGE_V3 14/−15.94 (PF 0.26); DK_V3 2/+0.26 (PF 23 but n=2), DK_CALL 1/−0.20, DK_PUT 1/−0.01. **No lane near the PF>1 / n~200 live gate — no strategy crowned.** **LIVE: real-money path armed (`dfecc5c`) but OFF — 0 `live_mirror` trades ever, 0 open, $0 collateral; rails trivially intact (cannot breach at 0 trades).** Note: `bot_status.is_paused=false`, but 0 options_scalp last hour + 0 live_mirror ever = no real-money exposure (PAPER_ONLY env not flipped). No engine bug — all closes reconcile to the cent. `[updated by: alpha-paper-lab-monitor]`

**Balances:** Futures lab **$485.17**, Options lab **$959.23** — both ≫ $50, no refill. Burns **0**.

### 2026-06-11 08:41 UTC — V3 ~35.3h in: futures −$513.25 (n=172 closed), options −$40.88 (n=55 closed), burns 0, live OFF; **VERIFICATION HOUR 13 — first green options print of the experiment: the DK trend-pick lane's FIRST settlement of the era is a WIN.** **OPT_SELL_DK_V3** (the 2-OTM trend-pick, opened last hour inside the DK window) closed **`sell_take_profit` +$0.28** at 08:34Z — captured 60% of credit rather than holding to the 12:00Z settle, but a real green close. Options **IMPROVED +$0.28** (−41.16 → −40.88); the DK_V3 lane is now 1/+0.28 (no losses yet, n=1 so expectancy still undefined). **Futures WORSENED −$2.73** (−510.52 → −513.25) on **2 closes**: FUT_SFP_15X `breakeven_stop` −0.28 (07:38Z) + FUT_EMA_PB_10X `paper_trail` −2.45 (07:40Z) = −2.73, **reconciles to the cent.** **paper_stop FROZEN — 84/−585.74, no new full stop this hour** (gate + trail-tighten keeping throughput off the stop); **paper_trail 45/+112.70** still the only net-green futures exit; breakeven_stop 31/−18.18. **Gate mechanically flawless 13th straight hour** — all **6 open positions are htf=+1 aligned longs** (1 SFP, 1 EMA, 2 DONCHIAN, + 2 PUT_V3 option sells), zero counter-trend leakage. **SFP RETIREMENT SHIPPED THIS HOUR:** commit `daf6d3c` (08:33Z) retired FUT_SFP_15X + unblocked the DK strangle (2-OTM, $0.50 credit gate) — it is a CODE commit and is pushed. **One pre-retire SFP long remains open** (opened 07:45Z, +8.71% MTM, before the retire landed) — it should close via `engine_restart` when the deploy restarts the engine. **Watch next hour for ZERO new SFP opens** to confirm the retirement sticks (mirrors the 20X retirement, which is still frozen 31/−137.58). FUT_SFP_15X frozen 56/−186.51, PF **0.15** — still worst net AND worst PF. DONCHIAN still best (29/−60.25, PF **0.35**); EMA_PB_10X 41/−95.08; VWAP 15/−33.84. **No futures lane PF>1 — book structurally negative.** Options lanes: PUT_V3 16/−8.64 (PF **0.58**, least-bad), CALL_V3 24/−16.57 (PF 0.31), RANGE_V3 14/−15.94 (PF 0.26, worst PF), DK_V3 1/+0.28. **DK strangle legs (DK_PUT/DK_CALL) still 0 fills** — but the 2-OTM/$0.50 gate only shipped at 08:33Z and the window runs to 11:18Z, so watch for first strangle fills this window. paper_stop is now **~93% of gross losses** but FROZEN — the new gate+trail are cutting the *rate* of fresh stops even though cumulative share is high. No engine bug — all closes/exits reconcile to the cent. `[updated by: alpha-paper-lab-monitor]`

**Balances:** Futures lab **$486.75**, Options lab **$959.12** — both ≫ $50, no refill. Burns **0**.

### 2026-06-11 07:38 UTC — V3 ~34.3h in: futures −$510.52 (n=170 closed), options −$41.16 (n=54 closed), burns 0, live OFF; **VERIFICATION HOUR 12 — the "best-PF lane prints as aligned longs" read took another hit: DONCHIAN's two fresh htf=+1 longs BOTH paper-stopped.** Futures **WORSENED −$8.42** (−502.10 → −510.52) on **2 closes**, both the FUT_DONCHIAN_RT_10X htf=+1 LONGS that opened 06:25Z last hour (flagged then as "gate routing into the best-PF lane as aligned longs"): **paper_stop −$4.37 and paper_stop −$4.05 = −$8.42, reconciles to the cent.** So the regime-change longs are now net **−$13.37 over the 4-hour up-tape window** (hr9 +1.57/+1.79 wins → hr10 −8.31 → hr11 +1.79 restart-win → hr12 −8.42): the two best-PF lanes converting "direction into profit" is **firmly back to noise** — aligned longs stop out just like aligned shorts did in hours 5–7. **Gate still mechanically flawless 12th straight hour** (both closes correctly htf=+1 longs in the up-tape; zero counter-trend leakage). The lesson hardens: **a perfect directional gate adds no expectancy on top of mediocre entries — long or short.** **paper_stop UNFROZE +2** (84/−585.74, both the DONCHIAN longs) after 2 frozen hours; **paper_trail FROZEN 4th straight hour** (45/+112.70, no new win — gate still starves the only net-green exit). **Zero SFP closes 5th straight hour** — FUT_SFP_15X frozen 56/−186.51, PF **0.15**, still worst net AND worst PF, still spared only by the UP tape. DONCHIAN net worsened to −60.25 (n=29) but **still best PF 0.35**. **Broader truth unchanged: no futures lane has PF>1; the book is structurally negative.** **20X retirement still sticking: frozen 31/−137.58** (still holds several pre-gate htf=? open positions that will close into it). Options **flat, 0 closes** (−$41.16); PUT_V3 still least-bad (16/−8.64, PF **0.58**), CALL −16.57 (PF 0.31), RANGE −15.94 (PF 0.26, worst PF). **DK strangle: FIRST FILL OF THE ERA** — 1 **OPT_SELL_DK_V3** (trend-pick, 2-OTM) opened inside today's 07:30–11:18Z window; the strangle legs (DK_PUT/DK_CALL) are still 0 fills and there are still 0 settlements (n=0 expectancy). Watch whether DK_V3 holds through the 12:00Z settle and whether the strangle pair fills before the window closes (11:18Z). No engine bug — stops/trail/gate/fees all reconcile to the cent. `[updated by: alpha-paper-lab-monitor]`

**Balances:** Futures lab **$489.48**, Options lab **$958.84** — both ≫ $50, no refill. Burns **0**.

### 2026-06-11 06:38 UTC — V3 ~33.3h in: futures −$502.10 (n=168 closed), options −$41.16 (n=54 closed), burns 0, live OFF; **VERIFICATION HOUR 11 — quietest hour of the window; an engine restart cleanly closed the lone open long at a small win, validating the restart-close feature.** Futures **IMPROVED +$1.79** (−503.89 → −502.10) on a **single close**: the FUT_EMA_PB_10X long htf=+1 that was +0.79% MTM at 05:10 grew and closed via **`engine_restart` +$1.79** at 06:17 (new exit reason this era, 1/+1.79). This is the designed behavior — a restart now **closes open trades at mark** instead of orphan-cancelling them, and it booked a real win rather than a phantom. **After the restart, 2 fresh FUT_DONCHIAN_RT_10X longs (both htf=+1) opened 06:25**, both ~flat MTM (−0.21 / +0.02) — gate still routing into the best-PF lane as aligned longs in the up-tape. **Gate mechanically flawless 11th straight hour** (zero counter-trend leakage; the only close + both opens are correctly aligned longs). **paper_stop FROZEN** (82/−577.32, 2nd straight hour no new full stop) and **paper_trail FROZEN** (44/+115.15, 3rd straight hour no new trail win — only ~1 trade/hour is reaching any exit, so neither the bleed nor the green lane moved). **Zero SFP closes 4th straight hour** — FUT_SFP_15X frozen at 55/−186.24, PF **0.15**, still worst net AND worst PF, still spared only by the UP tape. **Broader truth holds: no futures lane has PF>1; the book is structurally negative.** DONCHIAN remains best PF (**0.38**) and holds both opens. **20X retirement still sticking: frozen 31/−137.58.** Options **flat, 0 closes** (−$41.16 unchanged); PUT_V3 still least-bad (16/−8.64, PF **0.58**). **DK strangle: still 0 fills / 0 settlements the entire era** — today's 06-11 window (~07:30–11:18Z) is the next chance; if it also yields 0, inspect the DK entry gate. No engine bug — the restart-close, trail, stops, gate, and fees all reconcile to the cent.

**Balances:** Futures lab **$497.90**, Options lab **$958.84** — both ≫ $50, no refill. Burns **0**.

**Per-lane — Futures (era, closed, worst→best net):**

| Lane | n | Win% | Net | PF | Hold |
|---|---|---|---|---|---|
| **FUT_SFP_15X** | 55 | 16 | **−186.24** | **0.15** | 28.6m |
| FUT_EMA_PB_20X *(RETIRED)* | 31 | 16 | −137.58 | 0.26 | 47.2m |
| FUT_EMA_PB_10X | 40 | 25 | −92.63 | 0.25 | 43.2m |
| FUT_DONCHIAN_RT_10X | 27 | 26 | −51.82 | **0.38** (best) | 41.6m |
| FUT_VWAP_10X | 15 | 27 | −33.84 | 0.24 | 43.6m |

**Exit reasons — Futures (era):** `paper_stop` **82 / −577.32 — FROZEN** (2nd straight hour), `paper_trail` **44 / +115.15 — FROZEN** (3rd straight hour, only net-green exit), `breakeven_stop` 30/−17.90, `stagnant_exit` 9/−13.59, `no_traction` 2/−10.23, `engine_restart` **1 / +1.79** (new this hour, a win).

**Options lanes (era, closed):** CALL_V3 24/−16.57 (PF 0.31, worst net), RANGE_V3 14/−15.94 (PF 0.26, worst PF), PUT_V3 16/−8.64 (**PF 0.58, best, least-bad net**). DK strangle 0 fills entire era.

**What we should change:**
1. **URGENT (6th hour recommending): retire FUT_SFP_15X.** Worst net AND worst PF; spared 4 straight hours only by the up-tape, still not deployed.
2. **Restart-close feature validated** — `engine_restart` closed the open long at mark for a real +1.79 win; keep it, the orphan-phantom risk is resolved.
3. **Flag the DK strangle's persistent 0 fills** — multiple daily windows now passed with no entries; if today's ~07:30–11:18Z window also yields 0, inspect the DK entry condition for a config/gating bug.
4. **"Regime longs are edge" still noise** — too few closes (1 win this hour) to credit edge; keep DONCHIAN/EMA_PB/VWAP active, no claim yet.

### 2026-06-11 05:38 UTC — V3 ~32.3h in: futures −$503.89 (n=167 closed), options −$41.16 (n=54 closed), burns 0, live OFF; **VERIFICATION HOUR 10 — the regime-change longs GAVE BACK: first losing-long hour after two green ones, so "longs pay in an uptrend" is not yet edge.** Futures **WORSENED −$8.29** (−495.59 → −503.89) on **3 closes, ALL htf=+1 LONGS, ALL losers** — FUT_EMA_PB_10X `breakeven_stop` −0.21 (18m), FUT_DONCHIAN_RT_10X `stagnant_exit` −2.42 (76m), FUT_EMA_PB_10X `paper_stop` −5.68 (48m) = −8.31, reconciles to the cent. **Over the 2-hour regime window the longs are net −$4.95 (2 win / 3 loss)** — last hour's +1.57/+1.79 trail wins were given back and then some this hour via the same paper_stop/stagnant exits that bleed every other lane. So the hour-9 "DONCHIAN/EMA_PB convert direction into profit" read is **tempered to noise**: the up-tape longs print sometimes and bleed sometimes, like everything else. **Gate still mechanically flawless** (10th straight hour zero counter-trend leakage; all 3 closes correctly aligned longs). **Zero SFP closes again** — FUT_SFP_15X frozen 3rd straight hour at 55/−186.24, PF **0.15**, still worst net AND worst PF, still only spared by the UP tape (refunnels the instant 1h flips DOWN). **paper_trail FROZE** this hour (44/+115.15, no new wins — the gate starved the green exit again), while **paper_stop UNFROZE +1** (82/−577.32, the EMA −5.68) — a single full stop, not the hours-5-7 carnage, but the freeze streak is broken. **One open: FUT_EMA_PB_10X long htf=+1, +0.79% MTM, opened 05:10.** Broader truth this hour reinforces: **no futures lane has PF>1 — the whole book is structurally negative; the gate prevents big stops but cannot manufacture edge from mediocre entries.** **20X retirement still sticking: frozen 31/−137.58.** Options **+$0.69, 1 close, a WIN** — OPT_SELL_PUT_V3 `sell_take_profit` +0.69; PUT now best lane (16/−8.64, PF **0.58**, least-bad net). **DK strangle: still 0 fills / 0 settlements the entire era** — at least one full daily window (06-10) has now passed with zero entries, worth a look if it persists; next window ~07:30–11:18Z today. No engine bug — trail/stops/gate/fees all reconcile.

**Balances:** Futures lab **$496.11**, Options lab **$958.84** — both ≫ $50, no refill. Burns **0**.

**Per-lane — Futures (era, closed, worst→best net):**

| Lane | n | Win% | Net | PF | Hold |
|---|---|---|---|---|---|
| **FUT_SFP_15X** | 55 | 16 | **−186.24** | **0.15** | 28.6m |
| FUT_EMA_PB_20X *(RETIRED)* | 31 | 16 | −137.58 | 0.26 | 47.2m |
| FUT_EMA_PB_10X | 39 | 23 | −94.42 | 0.23 | 43.2m |
| FUT_DONCHIAN_RT_10X | 27 | 26 | −51.82 | **0.38** (best) | 41.6m |
| FUT_VWAP_10X | 15 | 27 | −33.84 | 0.24 | 43.6m |

**Exit reasons — Futures (era):** `paper_stop` **82 / −577.32** (+1 this hour, freeze streak broken but only one full stop), `paper_trail` **44 / +115.15 — FROZEN this hour** (the only net-green exit; gate starved it), `breakeven_stop` 30/−17.90, `stagnant_exit` 9/−13.59, `no_traction` 2/−10.23.

**Options lanes (era, closed):** CALL_V3 24/−16.57 (PF 0.31, worst net), RANGE_V3 14/−15.94 (PF 0.26, worst PF), PUT_V3 16/−8.64 (**PF 0.58, best, least-bad net**). DK strangle 0 fills entire era.

**What we should change:**
1. **URGENT (5th hour recommending): retire FUT_SFP_15X.** Worst net AND worst PF; spared 3 straight hours only by the up-tape, not deployed yet.
2. **Demote the "regime longs are edge" thesis to noise** — 2w/3L net −4.95 over two hours; keep DONCHIAN/EMA_PB/VWAP active but stop crediting them with edge until the sample is much larger.
3. **Flag the DK strangle's persistent 0 fills** — ≥1 full daily window passed with no entries; if today's 07:30–11:18Z window also yields 0, inspect the DK entry condition for a config/gating bug.
4. **Options:** no action; PUT_V3 quietly the least-bad book.

### 2026-06-11 04:38 UTC — V3 ~31.3h in: futures −$495.59 (n=164 closed), options −$41.85 (n=53 closed), burns 0, live OFF; **VERIFICATION HOUR 9 — the regime-change longs PAID: first all-green futures hour of the window where the green came from the NON-SFP lanes given direction.** Futures **IMPROVED +$3.36** (−498.93 → −495.59), only +2 closes, and **BOTH were the htf=+1 LONGS opened 03:35Z, both closed `paper_trail` WINS**: **FUT_DONCHIAN_RT_10X long +$1.57** (held 59.8m) and **FUT_EMA_PB_10X long +$1.79** (held 59.8m) — reconciles to the cent. These are exactly the two regime-change positions flagged last hour; the 1h HTF stayed UP, both longs rode the full ~60-min trail into profit. **Zero new `paper_stop` for the 2nd straight hour**, zero SFP closes, zero counter-trend leakage (9th straight hour the gate is mechanically flawless). **The thesis crystallizes:** the gate is fine — SFP *entry quality* was the leak. When the gate routes into the two best-PF lanes as LONGS in an uptrend, they print. **DONCHIAN is now unambiguously the best lane** (PF **0.40**, best net among the 10X, just won, AND holds the only open position — long htf=+1 opened 04:00, +0.39% MTM). **Verdict on SFP unchanged and still URGENT: retire FUT_SFP_15X** — still worst net (−$186.24, n=55) AND worst PF (**0.15**, 16% win). It only avoided trading this hour because the tape is UP; when the 1h flips back DOWN the gate will refunnel 100% into SFP shorts and bleed again unless it is retired. The DONCHIAN/EMA_PB green this hour is the contrast that proves the point: those lanes convert direction into profit, SFP does not. Caveat: n=2 winning longs is still noise-level for "edge," but it's the designed outcome two hours running (hour 8 booked a +$2.61 aligned trail; hour 9 both longs green). **20X retirement still sticking: frozen 31/−137.58, 0 new.** Options **flat, 0 closes** (−$41.85 unchanged; 1 PUT_V3 still open). **DK strangle: still 0 fills / 0 settlements this entire era** — next window 06-12 07:30–11:18Z; headline strangle number undefined (n=0). No engine bug — trail/stops/gate/fees all behaving as designed.

**Balances:** Futures lab **$504.41**, Options lab **$958.15** — both ≫ $50, no refill. Burns **0**.

**Per-lane — Futures (era, closed, worst→best net):**

| Lane | n | Win% | Net | PF | Hold |
|---|---|---|---|---|---|
| **FUT_SFP_15X** | 55 | 16 | **−186.24** | **0.15** | 28.6m |
| FUT_EMA_PB_20X *(RETIRED)* | 31 | 16 | −137.58 | 0.26 | 47.2m |
| FUT_EMA_PB_10X | 37 | 24 | −88.53 | 0.24 | 43.8m |
| FUT_DONCHIAN_RT_10X | 26 | 27 | −49.40 | **0.40** (best) | 40.3m |
| FUT_VWAP_10X | 15 | 27 | −33.84 | 0.24 | 43.6m |

**Exit reasons — Futures (era):** `paper_stop` **81 / −571.64 — FROZEN 2nd straight hour** (zero new full stops; the durable signal that the gate is preventing big stops), `paper_trail` **44 / +115.15** (the ONLY net-green exit, +2 this hour = the two winning longs), `breakeven_stop` 29/−17.69, `stagnant_exit` 8/−11.17, `no_traction` 2/−10.23.

**Options lanes (era, closed):** CALL_V3 24/−16.57 (PF 0.31, worst net), RANGE_V3 14/−15.94 (PF 0.26), PUT_V3 15/−9.33 (**PF 0.55, least-bad net**). DK strangle 0 fills entire era.

**What we should change:**
1. **URGENT (4th hour recommending): retire FUT_SFP_15X.** Worst net AND worst PF; only spared this hour by the up-tape. The retirement is still not deployed.
2. **Leave DONCHIAN / EMA_PB_10X / VWAP active** — DONCHIAN (best PF 0.40) just proved it converts direction into green; let the up-tape build its sample.
3. **Options:** no action; flat hour. Await DK strangle's first fills (06-12 window).

**Verdict status:** Gate confirmed mechanically sound across 9 hours; **SFP entry quality is the leak, not HTF alignment.** First evidence that non-SFP lanes print when gated long into an uptrend (n=2, noise but directionally as-designed). No lane near the PF>1.0 / n~200 live gate yet; no strategy crowned. `[updated by: alpha-paper-lab-monitor]`

### 2026-06-11 03:38 UTC — V3 ~30.3h in: futures −$498.93 (n=162 closed), options −$41.85 (n=53 closed), burns 0, live OFF; **VERIFICATION HOUR 8 — the SFP-only monoculture finally BROKE: the 1h HTF trend flipped UP and the gate is now opening LONGS in the two best non-SFP lanes.** Futures moved only −$2.52 this hour (−496.41 → −498.93), the smallest hourly damage of the window. **3 futures closed, all FUT_SFP_15X htf=−1 shorts** (the tail of the down-tape) — but for the FIRST time this window the loss profile softened: **paper_trail +$2.61** (70.3m, an aligned short that trailed GREEN), **breakeven_stop −$0.43** (71.3m, scratch), **paper_trail −$4.70** (32.7m) = −$2.52, reconciles to the cent. Not the all-`paper_stop` carnage of hours 5–7. **The headline: the 2 currently-open positions are htf=+1 LONGS — FUT_EMA_PB_10X long and FUT_DONCHIAN_RT_10X long, both opened 03:35Z** (+0.45 / −0.16 MTM). After 8 straight hours of nothing-but-SFP-shorts, the 1h trend has rolled over to UP and the gate is correctly routing into longs in the two best-PF lanes (DONCHIAN 0.38, EMA_PB next) — **still zero counter-trend leakage, the gate remains mechanically flawless**, it is simply no longer starving every other lane. This is the regime change that finally gives EMA_PB/DONCHIAN/VWAP a chance to generate samples. **Verdict on SFP unchanged and still URGENT: FUT_SFP_15X is the worst lane on BOTH net (−$186.24, n=55) AND PF (0.15, 16% win)** — it absorbed 100% of throughput for hours 5–8 and bled the entire −$155→−$186 in that span. **Retire it now**, mirroring the 20X retirement; a 0.15-PF entry is not rescued by a perfect gate. **paper_stop the durable signal** (no new full stops this hour — the 3 closes were 2 trails + 1 BE, not stops; first hour in 4 with zero new paper_stop). **20X retirement still sticking: frozen 31/−137.58, 0 new.** Other live lanes untouched on net: EMA_PB_10X −90.32, DONCHIAN best-PF 0.38 / −50.97, VWAP least-bad −33.84. Options **+$1.44 this hr — both closes WINS**: PUT_V3 improved −11.11 → **−9.33 (best PF 0.55, least-bad net)**, RANGE_V3 −17.26 → −15.94; CALL_V3 frozen −16.57 (worst PF 0.31). **DK strangle: still 0 fills / 0 settlements this entire era** — next window 06-12 07:30–11:18Z; headline strangle number undefined (n=0). No engine bug — gate/stops/trail/fees all behaving as designed; the SFP bleed is pure strategy. `[updated by: alpha-paper-lab-monitor]`

### 2026-06-11 01:40 UTC — V3 ~28.3h in: futures −$487.05 (n=156 closed), options −$43.29 (n=51 closed), burns 0, live OFF; **VERIFICATION HOUR 6 — the SFP verdict is now overwhelming: a 2nd straight hour where FUT_SFP_15X is the ONLY lane that trades, and a 7th straight hour of aligned-SFP bleeding.** All **4 futures closes this hour were FUT_SFP_15X shorts, htf=−1 (aligned), and ALL four were paper_stop losses** (−8.08, −5.73, −4.25, −0.51 = **−$18.57**, holds 0.5–48.6 min) — that cluster is the entire −$468.47 → −$487.05 move (reconciles to the cent). **1 more FUT_SFP_15X htf=−1 short opened 01:25Z, still open (−0.32 MTM).** So for the 2nd hour running the book traded EXACTLY ONE lane — FUT_SFP_15X — every trade an HTF-aligned short in a 1h downtrend, **zero counter-trend leakage for the 6th straight hour**; the gate is mechanically flawless. **The lane it feeds is the problem, and it has now gotten strictly worse: SFP_15X is the single WORST lane on BOTH net (−$174.35, overtook retired 20X's −$137.58) AND PF (0.15, 16% win, n=49).** **paper_stop now 79/−566.44** (count +5 vs last hr's 74, all aligned SFP shorts; the 4 in-window closes = −18.57 reconcile the net move) = 116% of futures loss — the COUNT is the signal, the ratio a denominator artifact. paper_trail **FROZEN 40/+113.89 for the 2nd straight hour** (no new trail — the gate is funneling everything into stops, nothing reaches the trail). **ACTION (reaffirmed, now URGENT): retire FUT_SFP_15X immediately, mirroring the 20X retirement.** This is the 2nd consecutive hour recommending it; the engine is still trading SFP_15X (only lane traded AND the only open position this hour), so the retirement has NOT yet been deployed. 7 consecutive hours of aligned SFP losses settle the question the verification window was built to answer: **HTF alignment is NOT edge — SFP entry quality is the leak, and the gate cannot rescue a 0.15-PF entry.** The other 3 live lanes (EMA_PB_10X −90.32, DONCHIAN best-PF 0.38 / −50.97, VWAP least-bad −33.84) did not open or close this hour. **20X retirement still sticking: 0 new, frozen 31/−137.58.** Options **+$1.65 this hr — both closes WINS**: OPT_SELL_RANGE_V3 +0.65 + OPT_SELL_PUT_V3 +1.00, both `sell_take_profit` (→ RANGE 13/31%/−16.61, PUT improved to 14/36%/−10.11, **best PF 0.51, least-bad net**; CALL unchanged 24/38%/−16.57). **DK strangle: still 0 fills / 0 settlements this entire era** — next window 06-12 07:30–11:18Z. No engine bug — gate/stops/trail/fees all behaving as designed; pure strategy signal. `[updated by: alpha-paper-lab-monitor]`
**Era:** V3 started 2026-06-09T21:21:00Z (V2 frozen, excluded). Live OFF confirmed — `bot_status.is_paused`=**true** (latest 01:38Z), **0** `options_scalp` opens in last hour. No `paper_deposits` since era start → **burns 0/0**, no refill (futures ≈$513, options ≈$957, both ≫ $50 floor).

**Balances (era, closed-only realized):** FUNDED $1,000 each. Futures BALANCE = 1000 − 487.05 = **$512.95**. Options BALANCE = 1000 − 43.29 = **$956.71**.

**Futures lanes (era, closed-only):**

| Lane | n | win% | net | PF | note |
|---|---|---|---|---|---|
| FUT_SFP_15X | 49 | 16 | −174.35 | 0.15 | **worst net + worst PF; ONLY lane traded this hr (4 aligned shorts, 4 stops) + only open; RETIRE NOW** |
| FUT_EMA_PB_20X | 31 | 16 | −137.58 | 0.26 | RETIRED, frozen (0 new) |
| FUT_EMA_PB_10X | 36 | 22 | −90.32 | 0.23 | frozen this hr |
| FUT_DONCHIAN_RT_10X | 25 | 24 | −50.97 | 0.38 | best PF, frozen this hr |
| FUT_VWAP_10X | 15 | 27 | −33.84 | 0.24 | least-bad net, best win%, frozen this hr |

**Futures exit-reason (era, closed-only):** paper_stop 79/−566.44 (**+5 vs last hr, all aligned SFP shorts**) · paper_trail 40/+113.89 (**frozen 2nd hr**) · breakeven_stop 28/−17.27 · stagnant_exit 8/−11.17 · no_traction 2/−10.23. 566.44/487.05 = 116% share — denominator artifact; the COUNT (+5 SFP stops) is the real signal.

**Options lanes (era, closed-only):** OPT_SELL_RANGE_V3 13/31%/−16.61 (worst net, +0.65 this hr) · OPT_SELL_CALL_V3 24/38%/−16.57 (frozen) · OPT_SELL_PUT_V3 14/36%/−10.11 (least-bad net, **best PF 0.51**, +1.00 this hr). DK lanes: **0 fills / 0 settlements to date.**

### 2026-06-11 00:40 UTC — V3 ~27.3h in: futures −$468.47 (n=152 closed), options −$44.94 (n=49 closed), burns 0, live OFF; **VERIFICATION HOUR 5 — the paper_stop freeze BROKE, and it broke in the single most diagnostic way possible: the gate is mechanically flawless but funneling 100% of its throughput into the WORST lane.** All **6 futures closes this hour were FUT_SFP_15X shorts, htf=−1 (aligned), and ALL six were paper_stop losses** (−3.81, −2.61, −3.55, −5.22, −7.46, −3.39 = **−$26.04**, holds 1–32 min) — that cluster is the entire −$442.44 → −$468.47 move (reconciles to the cent). **2 more FUT_SFP_15X htf=−1 shorts opened 00:25Z and are still open.** So this hour the book traded EXACTLY ONE lane — FUT_SFP_15X — 8 trades, 8/8 HTF-aligned shorts in a 1h downtrend, **zero counter-trend leakage for the 5th straight hour**; the gate is doing precisely what it was built to do. **The problem is the lane it is feeding: SFP_15X is the worst-PF entry in the book (0.17, 18% win), and it is now also the worst net (−$155.78), having overtaken the retired 20X (−$137.58).** **paper_stop UNFROZE 68→74 (+6), −517.67→−543.70** — the 4-hour freeze ended, and every one of the 6 new stops was an aligned SFP short. **This is the verdict the verification window was built to produce: 5+ consecutive aligned SFP losses prove alignment alone is NOT edge — the SFP entry quality is the leak.** ACTION: **retire FUT_SFP_15X next, mirroring the 20X retirement** (worst PF, worst net, AND now absorbing the gate's entire throughput — the gate cannot rescue a 0.17-PF entry). The other 3 live lanes (EMA_PB_10X, DONCHIAN, VWAP) did not open or close at all this hour — current down-tape + gate is concentrating everything into SFP. paper_trail frozen 40/+113.89 (no new trail this hr). **20X retirement still sticking: 0 new, frozen 31/−137.58.** Options −$44.94 (−1.90 this hr: 1 OPT_SELL_CALL_V3 closed `sell_trend_break` −1.90 → CALL now 24/38%/−16.57; RANGE −17.26 still worst net; PUT −11.11 least-bad, best PF 0.46). **DK strangle: still 0 fills / 0 settlements this entire era** — next window 06-11 07:30–11:18Z (~7h out). No engine bug — fees/exits/stops/trail all behaving as designed; this is a pure strategy signal. `[updated by: alpha-paper-lab-monitor]`
**Era:** V3 started 2026-06-09T21:21:00Z (V2 frozen, excluded). Live OFF confirmed — `bot_status.is_paused`=**true** (latest 00:38Z), **0** `options_scalp` opens in last hour. No `paper_deposits` since era start → **burns 0/0**, no refill (futures ≈$532, options ≈$955, both ≫ $50 floor).

**Balances (era, closed-only realized):** FUNDED $1,000 each. Futures BALANCE = 1000 − 468.47 = **$531.53**. Options BALANCE = 1000 − 44.94 = **$955.06**.

**Futures lanes (era, closed-only):**

| Lane | n | win% | net | PF | note |
|---|---|---|---|---|---|
| FUT_SFP_15X | 45 | 18 | −155.78 | 0.17 | **worst net + worst PF; ONLY lane traded this hr (8 aligned shorts, 6 stops); RETIRE NEXT** |
| FUT_EMA_PB_20X | 31 | 16 | −137.58 | 0.26 | RETIRED, frozen (0 new) |
| FUT_EMA_PB_10X | 36 | 22 | −90.32 | 0.23 | frozen this hr |
| FUT_DONCHIAN_RT_10X | 25 | 24 | −50.97 | 0.38 | best PF, frozen this hr |
| FUT_VWAP_10X | 15 | 27 | −33.84 | 0.24 | least-bad net, best win%, frozen this hr |

**Futures exit-reason (era, closed-only):** paper_stop 74/−543.70 (**UNFROZE +6, all aligned SFP shorts**) · paper_trail 40/+113.89 (frozen) · breakeven_stop 28/−17.27 · stagnant_exit 8/−11.17 · no_traction 2/−10.23. 543.70/468.47 = 116% share — denominator artifact, the COUNT (+6 SFP stops) is the real signal this hour.

**Options lanes (era, closed-only):** OPT_SELL_RANGE_V3 12/25%/−17.26 (worst) · OPT_SELL_CALL_V3 24/38%/−16.57 (−1.90 this hr, trend_break) · OPT_SELL_PUT_V3 13/31%/−11.11 (least-bad, PF 0.46). DK lanes: **0 fills / 0 settlements to date.**

### 2026-06-10 23:38 UTC — V3 ~26.3h in: futures −$442.44 (n=146 closed), options −$43.04 (n=48 closed), burns 0, live OFF; **VERIFICATION HOUR 4 — gate held flawless for a 4th hour, but the sign flipped back: the lone aligned trade to close this hour trailed into a small LOSS.** Only **1 futures trade closed** this hour: **FUT_EMA_PB_10X short, htf=−1, paper_trail −$2.85, held 21min** (closed 23:21Z) — an HTF-aligned short whose chandelier trail caught it at a small loss before it ever ran. That single close is the entire −$439.59 → −$442.44 move (reconciles exactly). The 4-hour aligned-trade sign sequence is now LOSE → flat → WIN → LOSE (H1 −$11.88 / H2 ≈flat / H3 +$5.00 / H4 −$2.85): cumulative ≈ −$9.77 over ~7 gated closes, still dominated by H1, still pure n≈7 noise — **alignment is mechanically perfect but has NOT yet shown edge.** **paper_stop COUNT FROZEN at 68/−$517.67 for the 4th straight hour** (zero new stops since the gate deployed 19:33Z) — the durable real signal; its 117% share (517.67/442.44) is the usual denominator artifact, watch the COUNT not the ratio. The ONLY closed movement this hour was on the trail side (paper_trail 39→40, +$116.74→+$113.89, i.e. the −$2.85); breakeven_stop (28/−17.27), stagnant_exit (8/−11.17), no_traction (2/−10.23) all frozen to the cent. **Gate un-throttled slightly but stayed clean: 3 futures opened this hour** (vs 0 last hr) — FUT_EMA_PB_10X short htf=−1 (→the −$2.85), and **2× FUT_SFP_15X short htf=−1 still open (+$0.97 MTM)** — every open an htf=−1 aligned short, **zero counter-trend leakage** for the 4th straight hour. ⚠ Note both new opens are **FUT_SFP_15X**, the worst-PF lane (0.19) — watch whether the gate rescues it or it becomes the next retirement candidate after 20X. **20X retirement sticking: 0 new, frozen 31/−137.58.** Options −$43.04 (+2 CALL_V3 closes −$2.46 → CALL now 23/39%/−14.67; RANGE −17.26 still worst; PUT −11.11 least-bad) + 1 open sell −0.60 MTM. **DK strangle: 0 fills — today's 06-11 07:30–11:18Z window came and went with zero fills again**, so the DK lanes have never once filled this era; next window 06-12 07:30–11:18Z. `[updated by: alpha-paper-lab-monitor]`
**Era:** V3 started 2026-06-09T21:21:00Z (V2 frozen, excluded). Live OFF confirmed — `bot_status.is_paused`=**true** (latest 23:38Z), **0** `options_scalp` opens in last hour. No `paper_deposits` since era start → **burns 0/0**, no refill (futures ≈$558, options ≈$957, both ≫ $50 floor).

**Balances (era, closed-only realized):** FUNDED $1,000 each. Futures BALANCE = 1000 − 442.44 = **$557.56**. Options BALANCE = 1000 − 43.04 = **$956.96**.

**Futures lanes (era, closed-only):**

| Lane | n | win% | net | PF | note |
|---|---|---|---|---|---|
| FUT_EMA_PB_20X | 31 | 16 | −137.58 | 0.26 | RETIRED, frozen (0 new) |
| FUT_SFP_15X | 39 | 21 | −129.74 | 0.19 | worst active lane, worst PF; 2 new aligned shorts OPEN |
| FUT_EMA_PB_10X | 36 | 22 | −90.32 | 0.23 | +1 aligned paper_trail LOSS this hr (−2.85) |
| FUT_DONCHIAN_RT_10X | 25 | 24 | −50.97 | 0.38 | best PF, frozen this hr |
| FUT_VWAP_10X | 15 | 27 | −33.84 | 0.24 | least-bad net, best win% |

**Futures exit-reason (era, closed-only):** paper_stop 68/−517.67 (**FROZEN 4 hrs**) · paper_trail 40/+113.89 (+1/−2.85 this hr — first losing trail in a while) · breakeven_stop 28/−17.27 · stagnant_exit 8/−11.17 · no_traction 2/−10.23. Sole movement this hour was the single −2.85 trail; all stops/BEs/stagnant frozen.

**Options lanes (era, closed-only):** OPT_SELL_RANGE_V3 12/25%/−17.26 (worst) · OPT_SELL_CALL_V3 23/39%/−14.67 · OPT_SELL_PUT_V3 13/31%/−11.11 (least-bad). 1 open sell (−0.60 MTM). DK lanes: **0 fills / 0 settlements to date** (today's window missed).

**Verdict unchanged:** No live gate met (no lane PF>1.0 over ~200 trades; best PF still DONCHIAN 0.38 on n=25). No engine bug — all numbers reconcile, gate mechanically sound (4 hrs zero leakage). Next 1–2h test: does paper_stop COUNT stay frozen, do the 2 open SFP_15X aligned shorts resolve green or confirm SFP_15X as the next 20X-style retirement, and do gated trails turn net-positive or stay noise.

### 2026-06-10 22:39 UTC — V3 ~25.3h in: futures −$439.59 (n=145 closed), options −$40.58 (n=46 closed), burns 0, live OFF; **VERIFICATION HOUR 3 — the gate produced its first clean GREEN hour: net IMPROVED −$444.59 → −$439.59 (+$5.00), entirely from 2 HTF-aligned paper_trail wins.** The 2 trades that closed this hour: **FUT_DONCHIAN_RT_10X short, htf=−1, paper_trail +$3.72, held 81min** and **FUT_EMA_PB_10X short, htf=−1, paper_trail +$1.29, held 65min** — both shorts in a 1h downtrend (aligned), both trailed into profit, both held >1h. This is the exact behavior the 1h-HTF gate was built for. Note the sign-flip vs last hour: HOUR 2's 2 aligned trades both LOST (−$11.88); HOUR 3's 2 aligned trades both WON (+$5.00) — still n=2 = pure noise, but directionally it's the designed outcome. **paper_stop COUNT FROZEN at 68/−$517.67 for the 3rd straight hour** (zero new stops since the gate) — the durable real signal; its 118% share (517.67/439.59) is a denominator artifact (loss shrank, stops frozen), watch the COUNT. **Gate now throttling to a near-halt: 0 futures opened in 70min** (vs 3 last hr, ~12–15/hr pre-gate) — extremely tight, the only realized PnL is trailing exits of earlier-opened aligned shorts. **20X retirement sticking: last FUT_EMA_PB_20X closed 19:10Z (htf=null, pre-gate), 0 new.** Trade health solid: median hold 32.9min, 83% survive >10min. Options −$40.58 (RANGE −17.26 worst, CALL −12.21, PUT −11.11 least-bad) + 2 open CALL_V3 −0.38 MTM; DK strangle **still 0 fills** (next window 06-11 07:30–11:18Z, ~9h out). `[updated by: alpha-paper-lab-monitor]`
**Era:** V3 started 2026-06-09T21:21:00Z (V2 frozen, excluded). Live OFF confirmed — `bot_status.is_paused`=**true**, **0** `options_scalp` opens in last hour. No `paper_deposits` since era start → **burns 0/0**, no refill (futures ≈$560, options ≈$959, both ≫ $50 floor).

**Balances (era, closed-only realized):** FUNDED $1,000 each. Futures BALANCE = 1000 − 439.59 = **$560.41**. Options BALANCE = 1000 − 40.58 = **$959.42**.

**Futures lanes (era, closed-only):**

| Lane | n | win% | net | PF | note |
|---|---|---|---|---|---|
| FUT_EMA_PB_20X | 31 | 16 | −137.58 | 0.26 | RETIRED, frozen (last close 19:10Z) |
| FUT_SFP_15X | 39 | 21 | −129.74 | 0.19 | worst active lane, worst PF |
| FUT_EMA_PB_10X | 35 | 23 | −87.47 | 0.24 | +1 gated paper_trail win this hr (+1.29) |
| FUT_DONCHIAN_RT_10X | 25 | 24 | −50.97 | 0.38 | best PF; +1 paper_trail win this hr (+3.72) |
| FUT_VWAP_10X | 15 | 27 | −33.84 | 0.24 | least-bad net, best win% |

**Futures exit-reason (era, closed-only):** paper_stop 68/−517.67 (FROZEN 3 hrs) · paper_trail **39/+116.74** (+2/+5.01 this hr) · breakeven_stop 28/−17.27 · stagnant_exit 8/−11.17 · no_traction 2/−10.23. The only movement this hour was on the GREEN side (paper_trail) — stops, BEs, stagnant all unchanged.

**Options lanes (era, closed-only):** OPT_SELL_RANGE_V3 12/25%/−17.26 (worst) · OPT_SELL_CALL_V3 21/38%/−12.21 · OPT_SELL_PUT_V3 13/31%/−11.11 (least-bad). 2 open CALL_V3 (−0.38 MTM). DK lanes: 0 settlements to date.

**Verdict unchanged:** No live gate met (no lane PF>1.0 over ~200 trades; best PF still DONCHIAN 0.38 on n=25). No engine bug — all numbers reconcile, gate mechanically sound. Next 1–2h test: does paper_stop stay frozen and do aligned-trail greens keep accumulating, or was +$5.00 just noise.

### 2026-06-10 21:38 UTC — V3 ~24.3h in: futures −$444.59 (n=143 closed), options −$39.93 (n=44 closed), burns 0, live OFF; **VERIFICATION HOUR 2 — gate froze new paper_stops again, and the apparent −$22 "worsening" is a REPORTING PHANTOM, not new losses.** The headline reconciled the prior-run count drift: last hour's "n=169 / −$422" **included 27 `restart_orphan` trades that are `status='cancelled'` (+$22.55), not `closed`.** Counting closed-only: 169 − 27 cancelled + 1 new breakeven = **143**, and removing the +$22.55 phantom green is the entire −$422→−$444.59 move. **Genuine new damage this hour ≈ −$0.04** (one FUT_EMA_PB_10X breakeven_stop) + −$2.94 open MTM on 2 live shorts — essentially flat. **paper_stop COUNT FROZEN at 68/−$517.67 for the 2nd straight hour** (zero new stops since the gate) — this is the real signal the 1h-HTF gate is preventing new big stops, far cleaner than the ratio (517.67/444.59 = 116%, mechanically inflated by phantom removal). **Gate still throttling hard:** only 3 futures opened in 70min, ALL `htf=−1` (downtrend) → all shorts, **zero counter-trend leakage** (DONCHIAN short open −0.68, EMA_PB short open −3.49, EMA_PB short BE −0.04). **20X retirement sticking: 0 new FUT_EMA_PB_20X since 19:33Z.** Options −$39.93 (RANGE −15.40 worst, CALL −13.41, PUT −11.11); 3 open sells; DK strangle **still 0 fills** (next window 06-11 07:30–11:18Z). `[updated by: alpha-paper-lab-monitor]`
**Era:** V3 started 2026-06-09T21:21:00Z (V2 frozen, excluded). Live OFF confirmed — `bot_status.is_paused`=**true** (latest 21:38:21Z), **0** `options_scalp` opens in last hour. No `paper_deposits` since era start → **burns 0/0**, no refill (futures ≈$555, options ≈$960, both ≫ $50 floor).

**Balances (era, closed-only realized):** FUNDED $1,000 each. Futures BALANCE = 1000 − 444.59 = **$555.41** (the +$22.55 cancelled-orphan green is a phantom — excluded). Options BALANCE = 1000 − 39.93 = **$960.07**.

**Futures lanes (era, closed-only):**

| Lane | n | win% | net | PF | note |
|---|---|---|---|---|---|
| FUT_EMA_PB_20X | 31 | 16 | −137.58 | 0.26 | RETIRED, frozen (0 new since 19:33Z) |
| FUT_SFP_15X | 39 | 21 | −129.74 | 0.19 | worst active lane, worst PF |
| FUT_EMA_PB_10X | 34 | 21 | −88.76 | 0.22 | +1 gated BE this hr; still beats retired 20X |
| FUT_DONCHIAN_RT_10X | 24 | 21 | −54.69 | 0.33 | best PF |
| FUT_VWAP_10X | 15 | 27 | −33.84 | 0.24 | least-bad net, best win% |

(Lane n/net all fell vs last hour for the same reason — per-lane cancelled-orphans dropped out of the closed-only set; not new trading.)

**Futures exit-reason (era, closed-only):** paper_stop 68/−517.67 · paper_trail 37/+111.73 · breakeven_stop 28/−17.27 · stagnant_exit 8/−11.17 · no_traction 2/−10.23. Plus **27 `restart_orphan` now `status='cancelled'` (+22.55) — excluded from realized.** paper_stop count unchanged for 2 hrs = gate is working; its 116% share is a denominator artifact, watch the COUNT not the ratio.

**Options lanes (era):** RANGE_V3 11/−15.40 (27%) · CALL_V3 20/−13.41 (35%) · PUT_V3 13/−11.11 (31%). DK lanes: **0 fills all era** — next window 06-11 07:30–11:18Z; strangle head-to-head still pending first settlement.

**Engine-bug / data status:** No live engine bug — the 27 restart_orphan trades have been `cancelled` all along; the issue is **prior check-ins counted cancelled trades as closed**, inflating the green by +$22.55. Going forward, headline = `status='closed'` only. HTF-gate metadata writing correctly (htf_trend=−1 on all 3 new trades). No restart this hour.

**What to change:** (1) Reporting: **always filter `status='closed'` for realized PnL**; quote cancelled-orphan green separately, never in the headline. (2) Engine: nothing to deploy — keep the gate running; the clean verification metric is **paper_stop count staying frozen** as gated n grows (now 2 hrs frozen, n=3 gated trades = still noise on edge). (3) DK strangle verdict waits for the 07:30–11:18Z window.

### 2026-06-10 20:39 UTC — V3 ~23.3h in: futures −$422.00 (n=169), options −$37.14 (n=53), burns 0, live OFF; **V3.1 VERIFICATION HOUR — gate is mechanically working, but first 2 gated trades both lost.** Only **2 futures trades opened all hour** (vs ~12–15/hr pre-gate) — the 1h HTF-trend gate is throttling flow hard, exactly as designed ("expect fewer trades"). Both new trades passed the gate correctly: **FUT_SFP_15X short @ htf=−1** (breakeven_stop −$5.37, 42.8m) and **FUT_EMA_PB_10X short @ htf=−1** (paper_stop −$6.51, 12.7m) — i.e. both **shorts in a 1h downtrend = directionally aligned**, no counter-trend entries leaked through. **20X retirement is sticking: 0 new FUT_EMA_PB_20X since the 19:33Z deploy** (its 39 trades / −$139.26 are now frozen history). But the two aligned trades **still lost −$11.88 combined** — alignment did not produce a winner in this n=2 sample (far too small to judge edge; the tape may simply not have trended on the entry's timeframe). 0 open positions now. paper_stop = **68/−$517.67 = 123% of futures loss** (14th run >100%, +1 stop this hr); paper_trail frozen 37/+$111.73 (no new trail). Lanes: VWAP_10X still least-bad (−$25.84, PF 0.44, 33% win); EMA_PB 10X (−$90.43, PF 0.26) still ahead of retired 20X. Options +2 trades for −$1.14: CALL_V3 worst (−$15.18, 35% win), PUT_V3 frozen (−$10.85). DK strangle **still 0 fills** (next window 06-11 07:30–11:18Z). `[updated by: alpha-paper-lab-monitor]`
**Era:** V3 started 2026-06-09T21:21:00Z (V2 frozen, excluded). Live OFF confirmed — `bot_status.is_paused`=**true** (latest 20:38:24Z), **0** `options_scalp`/scalp opens in last hour. No `paper_deposits` since era start → **burns 0/0**, no refill (futures ≈$578, options ≈$963, both ≫ $50 floor).

**Balances (era math):** FUNDED $1,000 each (0 deposits since era). Futures BALANCE = 1000 − 422.00 = **$578.00**. Options BALANCE = 1000 − 37.14 = **$962.86**.

**Futures lanes (era):**

| Lane | n | win% | net | PF | note |
|---|---|---|---|---|---|
| FUT_EMA_PB_20X | 39 | 21 | −139.26 | 0.32 | RETIRED 19:33Z, frozen |
| FUT_SFP_15X | 44 | 25 | −109.53 | 0.32 | +1 gated short (BE stop) |
| FUT_EMA_PB_10X | 41 | 24 | −90.43 | 0.26 | +1 gated short (paper_stop) |
| FUT_DONCHIAN_RT_10X | 26 | 19 | −56.95 | 0.32 | frozen |
| FUT_VWAP_10X | 18 | 33 | −25.84 | 0.44 | least-bad lane |

**Futures exit-reason (era):** paper_stop 68/−517.67 · paper_trail 37/+111.73 · restart_orphan 27/+22.55 · breakeven_stop 27/−17.22 · stagnant_exit 8/−11.17 · no_traction 2/−10.23. paper_stop alone (−$517.67) still exceeds the entire net loss (−$422.00) at 123%; trail (+$111.73) + orphan-cleanup (+$22.55) are the only green.

**Options lanes (era):** CALL_V3 23/−15.18 (35%) · RANGE_V3 13/−11.13 (38%) · PUT_V3 17/−10.85 (41%). DK lanes (OPT_SELL_DK_V3 / _PUT_V3 / _CALL_V3): **0 fills all era** — next entry window 06-11 07:30–11:18Z; strangle head-to-head still pending first settlement.

**Engine-bug status:** No restart this hour (no new restart_orphan/engine_restart closes). HTF-gate metadata writing correctly (htf_trend non-null on both post-deploy trades). No new bugs surfaced; gate behaving to spec.

**What to change:** Nothing to deploy — V3.1 just went live and is being verified. Keep gate running; the real test is whether **paper_stop's share of loss finally drops below ~100%** once a meaningful number of gated trades accumulate (n=2 so far is noise). Watch next 2–3 hours for gated-trade win% and paper_stop share. Do not touch engine. DK strangle verdict waits for the 07:30–11:18Z window.

**Verdict status:** unchanged. No lane at a verdict. Futures still net-negative across every lane (PF ≤0.44), n far below the 200-trade live gate. 20X retirement confirmed sticking. Options fee-capped, DK cohort un-sampled. No strategy crowned.

### 2026-06-10 19:39 UTC — V3 ~22.3h in: futures −$410.12 (n=167), options −$36.13 (n=51), burns 0, live OFF; **V3.1 entries deployed 19:33 UTC — verification deferred to next hour.** The 1h HTF-trend gate + FUT_EMA_PB_20X retirement (`e1cf130`) and the engine_restart-close fix (`1d80584`) were committed/pushed only ~6 min before this snapshot (19:32–19:33Z), so all this hour's trades are still **pre-gate** (htf_trend=null, 20X still opening at 19:15) — *expected*, not a deploy gap. This hour was a **flat-tape grind**: zero new `paper_stop`, zero new `paper_trail` (both frozen to the cent 2nd straight hr) — the entire −$18.77 move came from low-conviction exits (5 restart_orphan −$5.72, 3 breakeven −$0.97, 3 stagnant −$5.66, 1 no_traction −$6.42). paper_stop = **125% of futures loss** (13th run >100%); EMA_PB 10X beats 20X **14th straight** (1.66×); VWAP_10X still best/least-bad (−$25.84, PF 0.44, 33% win); PUT_V3 gave back (−$8.80→−$10.85, win 44%→41%); DK strangle **still 0 fills** (next window 06-11 07:30–11:18Z) `[updated by: alpha-paper-lab-monitor]`
**Era:** V3 started 2026-06-09T21:21:00Z (V2 frozen, excluded). Live OFF confirmed — `bot_status.is_paused`=**true** (latest 19:38:23Z), **0** `options_scalp` opens in last hour. No `paper_deposits` since era start → **burns 0/0**, no refill (both labs ≫ $50 floor).

**Balances (era math):**
- **Futures lab:** FUNDED $1,000 + closed P&L −$410.12 = **BALANCE $589.88** (n=167 closed). Burns 0.
- **Options lab:** FUNDED $1,000 + closed P&L −$36.13 = **BALANCE $963.87** (n=51 closed). Burns 0.

**The headline: V3.1 entry logic just went live (19:33 UTC), 6 min before this check-in.** Three changes now in CI: (1) **1h HTF-trend gate** — longs only in 1h uptrend, shorts only in 1h downtrend, flat=no entry (`metadata.htf_trend` on every new trade); (2) **FUT_EMA_PB_20X retired** (14 straight runs ~1.66× worse than 10X on identical entries); (3) **engine_restart fix** — `_close()` metadata-arg bug that broke graceful restart closes. **None visible in this hour's data**: the 5 most-recent opens (through 19:15) still show `htf_trend`=null and 20X still firing — all pre-deploy. **Next hour is the verification hour:** confirm htf_trend populates, 20X stops opening, the `engine_restart` exit_reason appears (0 so far), and — the real test — whether the gate finally drops paper_stop's share of loss below ~100%.

**This hour was a flat-tape grind, not a stop-out hour.** 12 new closes, **none** were `paper_stop` (frozen 67/−$511.16, 2nd straight hr) and **none** were `paper_trail` (frozen 37/+$111.73, 2nd straight hr). The −$18.77 came entirely from grind exits: 5 `restart_orphan` (−$5.72), 3 `breakeven_stop` (−$0.97), 3 `stagnant_exit` (−$5.66), 1 `no_traction` (−$6.42). Reading: in chop the entries open, go nowhere, and die at breakeven / stagnant — no trend to trail, but also (notably) no momentum to trip the stop. Underlying bleed continues at the slow rate.

**Per-lane — Futures (era, closed only):**

| Lane | Closed | Win% | Net | Gross W | Gross L | PF | Hold |
|---|---|---|---|---|---|---|---|
| FUT_VWAP_10X | 18 | 33 | **−25.84** | 20.58 | −46.42 | 0.44 | 47m |
| FUT_DONCHIAN_RT_10X | 26 | 19 | −56.95 | 26.97 | −83.91 | 0.32 | 37m |
| FUT_EMA_PB_10X | 40 | 25 | −83.92 | 31.95 | −115.87 | 0.28 | 40m |
| FUT_SFP_15X | 43 | 26 | −104.17 | 52.16 | −156.32 | 0.33 | 28m |
| **FUT_EMA_PB_20X** (retired) | 39 | 21 | **−139.26** | 64.08 | −203.34 | 0.32 | 41m |

Every lane net-negative, every PF ≤ 0.44, win% 19–33%. Best (least-bad) = **VWAP_10X −$25.84 (PF 0.44, 33% win)**; worst = retired **EMA_PB_20X −$139.26**; worst *active* lane = **SFP_15X −$104.17**.

**EMA_PB 10X vs 20X (14th straight net win for 10X):** 10X −$83.92 vs 20X −$139.26 → 20X loses **1.66×** more on identical entries. 20X PF (0.32) actually ≥ 10X PF (0.28) this snapshot — both ~0.3, identically edge-less — proving the 1.66× net gap is **pure leverage amplification**, not a worse signal. 20X = **34% of the futures loss at 21% win**. Retirement (now live) is the correct call; next hour verifies 20X stops opening.

**Exit-reason split — Futures (era, n=167):**

| Exit | Closed | Net | Avg |
|---|---|---|---|
| **paper_stop** | 67 | **−511.16** | −7.63 |
| breakeven_stop | 26 | −11.86 | −0.46 |
| stagnant_exit | 8 | −11.17 | −1.40 |
| no_traction | 2 | −10.23 | −5.12 |
| **restart_orphan** | 27 | **+22.55** | +0.84 |
| **paper_trail** | 37 | **+111.73** | +3.02 |

**13th straight run** with paper_stop > total futures loss: paper_stop alone (−$511.16) = **125% of the −$410.12 loss**. Only structural green exit is `paper_trail` (+$111.73, frozen — no winners closed this hour); `restart_orphan` (+$22.55, deploy-cleanup, +5 closes net −$5.72 this hour). `engine_restart` exit_reason still 0 (the new graceful-close path; will appear after the 19:33 restart). **Verdict unchanged: STRATEGY (no entry edge in chop), not an engine bug** — stop/trail/breakeven all behaving correctly. The HTF gate is the first entry-side intervention; its job is to cut the no-edge entries that feed paper_stop.

**Per-lane — Options SELL_V3 (era, closed only):**

| Lane | Closed | Win% | Net |
|---|---|---|---|
| OPT_SELL_PUT_V3 | 17 | 41 | **−10.85** |
| OPT_SELL_RANGE_V3 | 12 | 42 | −11.01 |
| OPT_SELL_CALL_V3 | 22 | 32 | −14.64 |

Options bleeding slowly: −$32.81→−$36.13 (−$3.32, +9 closes). PUT_V3 gave back its near-green status (−$8.80/44%→−$10.85/41%); CALL_V3 still worst (32% win). **DK strangle (DK_PUT/DK_CALL/DK_V3) still 0 fills this entire era** — next entry window 06-11 07:30–11:18 UTC; the strangle's combined daily P&L remains the awaited headline once n≥10 settlements.

### 2026-06-10 18:39 UTC — V3 ~21.3h in: futures −$391.36 (n=155), options −$32.81 (n=42), burns 0, live OFF; **first "green" hour of the era is a DEPLOY ARTIFACT, not edge** — the `8fdce1a` restart fired 22 `restart_orphan` cleanup closes (+$28.27 era-total; 9 of them +$25.05 in the last hour) which lifted futures −$418→−$391, but the real trade machinery (`paper_stop` frozen 67/−$511, `paper_trail` frozen 37/+$112) closed **zero** this hour → underlying bleed flat; paper_stop = **131% of futures loss** (12th run >100%); EMA_PB 10X beats 20X **13th straight** (1.66×, ~flat vs 1.68×); VWAP_10X reclaims best/least-bad lane (−$25.79, PF 0.44, 35% win); PUT_V3 recovered toward near-green (−9.06→−8.80, win 33%→44%); DK strangle **still 0 fills this era** `[updated by: alpha-paper-lab-monitor]`
**Era:** V3 started 2026-06-09T21:21:00Z (V2 frozen, excluded). Live OFF confirmed — `bot_status.is_paused`=**true** / `bot_state`=paused / pause_reason "PAPER-ONLY mode" (ts 18:37:33Z, last_scan 184s), **0** `options_scalp` opens in last hour. No `paper_deposits` since era start → **burns 0/0**, no refill (both labs ≫ $50 floor).

**Balances (era math):**
- **Futures lab:** FUNDED $1,000 + closed P&L −$391.36 = **BALANCE $608.64** (n=155 closed). Burns 0.
- **Options lab:** FUNDED $1,000 + closed P&L −$32.81 = **BALANCE $967.19** (n=42 closed). Burns 0.

**The headline: a code deploy (`8fdce1a` "graceful restart closes"), not a strategy turn, made the era P&L improve for the first time.** Last ~70 min = **9 `restart_orphan` closes (+$25.05) + 1 breakeven_stop (−$1.21)** = +$23.84 — i.e. 100% orphan-cleanup, **zero genuine trade closes**. Across the era `restart_orphan` now totals **22 closes / +$28.27**. Strip those one-off cleanups and the "operating" futures loss is −$419.6 — **flat vs 17:39's −$418.42**, confirming the underlying bleed did not improve. `paper_stop` (67/−$511.16) and `paper_trail` (37/+$111.73) are both **frozen to the cent vs 17:39** (no new stops or trails closed while the engine re-warmed post-restart).

**Per-lane — Futures (era, closed only):**

| Lane | Closed | Win% | Net | Gross W | Gross L | PF | Hold |
|---|---|---|---|---|---|---|---|
| FUT_VWAP_10X | 17 | 35 | **−25.79** | 20.58 | −46.37 | 0.44 | 46m |
| FUT_DONCHIAN_RT_10X | 26 | 19 | −56.95 | 26.97 | −83.91 | 0.32 | 37m |
| FUT_EMA_PB_10X | 36 | 28 | −80.55 | 31.95 | −112.50 | 0.28 | 39m |
| FUT_SFP_15X | 40 | 28 | −94.04 | 52.16 | −146.20 | 0.36 | 26m |
| **FUT_EMA_PB_20X** | 35 | 23 | **−134.04** | 64.08 | −198.12 | 0.32 | 41m |

Every lane net-negative, every PF ≤ 0.44, win% 19–35%. Best (least-bad) = **VWAP_10X −$25.79 (PF 0.44, highest win 35%)** — reclaimed the top after a +$8 cleanup gain (−33.79→−25.79); worst = **EMA_PB_20X −$134.04**. (A stray `FUT_MOMENTUM_CONF` closed 1 trade at $0.00 — V2 lane name, excluded from rankings.)

**EMA_PB 10X vs 20X head-to-head (13th straight net win for 10X):** identical entries, 10X −$80.55 vs 20X −$134.04 → 20X loses **1.66×** more (≈flat vs last hour's 1.68×). Both lanes added +6 mostly-orphan closes this hour so net barely moved. Note **20X's PF (0.32) ≈ 10X's (0.28)** — leverage-neutral profit factor is identically broken (~0.3) on both; the 1.66× net gap is *pure leverage amplification* of the same edge-less entries. 20X is **34% of the futures loss at 23% win** — still the single largest drag.

**Exit-reason split — Futures (era, n=155):**

| Exit | Closed | Net | Avg |
|---|---|---|---|
| **paper_stop** | 67 | **−511.16** | −7.63 |
| breakeven_stop | 23 | −10.89 | −0.47 |
| stagnant_exit | 5 | −5.51 | −1.10 |
| no_traction | 1 | −3.81 | −3.81 |
| **restart_orphan** | 22 | **+28.27** | +1.29 |
| **paper_trail** | 37 | **+111.73** | +3.02 |

**12th straight run** with paper_stop > total futures loss: paper_stop alone (−$511.16) = **131% of the −$391.36 loss**. The two green exits are `paper_trail` (+$111.73, the only structural edge — frozen, no winners closed this hour) and the new one-off `restart_orphan` (+$28.27, deploy cleanup). 100% of the genuine bleed is still entries dying at the stop before traction. **Verdict: STRATEGY (no entry edge in chop), not an engine bug** — stop/trail/breakeven machinery all behave correctly; the restart cleanup is also behaving as designed.

**Per-lane — Options SELL_V3 (era, closed only):**

| Lane | Closed | Win% | Net |
|---|---|---|---|
| OPT_SELL_PUT_V3 | 16 | 44 | **−8.80** |
| OPT_SELL_RANGE_V3 | 11 | 45 | −9.75 |
| OPT_SELL_CALL_V3 | 15 | 33 | −14.26 |

Options near-flat hour (+$0.04, 2 closes). PUT_V3 **recovered** (+4 closes: net −9.06→−8.80, win 33%→44%) back toward near-green; RANGE_V3 also best-win at 45% (−9.75). CALL_V3 the worst options lane (−14.26, 33%). All n ≤16 → no verdict; options stays the far-less-bad book (−$33 vs −$391).

**DK harvest/strangle cohort:** **still 0 trades this era** — neither DK_V3 (trend-pick) nor the DK_PUT/DK_CALL strangle has fired. Entry window 07:30–11:18 UTC; today's window passed before the lanes had data, so first real chance is **tomorrow's (06-11) 07:30–11:18Z**. Combined-daily-strangle headline: N/A (n=0). Verify the lanes actually arm at window open tomorrow.

**What to change next:**
1. **Do NOT read this hour's +$24 as a turn — it is deploy cleanup (`restart_orphan` +$25), not edge.** The real engine (paper_stop/paper_trail) closed nothing; underlying loss is flat (−$419.6 ex-orphans vs −$418.4). Watch the next 1–2 hours of *genuine* closes post-restart before drawing any trend.
2. **RETIRE FUT_EMA_PB_20X (loud, 13th ask).** −$134.04 = 34% of the futures loss, 23% win, loses 1.66× to its own 10X twin on identical entries; PF-neutral evidence (0.32 vs 0.28) proves the leverage is pure amplification of a dead edge. The single concrete lever; monitor is read-only and cannot flip it.
3. **Futures structural:** bleed is 100% entry-quality (paper_stop −$511 vs paper_trail +$112). Attack entry selection (raise conf gate) — not the exits, which work. Hold all futures dark for live.
4. **Options:** PUT_V3 regaining near-green (−$8.80, 44% win) but n ≤16 — no lane to crown yet. Safer book by far.
5. **DK:** nothing to judge until tomorrow's 07:30–11:18Z window produces the first settlements; confirm the lanes arm.

### 2026-06-10 17:39 UTC — V3 ~20.3h in: futures −$418.42 (n=132), options −$33.94 (n=34), burns 0, live OFF; **worst futures hour of the era — 8/8 closes were stop-outs (−$88, ≈ −$11/trade), paper_trail frozen → zero green closes**; paper_stop = **122% of futures loss** (11th run >100%); EMA_PB 10X beats 20X **12th straight**, gap re-widened 1.57×→1.68× (20X bled 2× the 10X this hour); PUT_V3 gave back its near-green status (−1.21→−9.06); DK strangle **still 0 fills this era** `[updated by: alpha-paper-lab-monitor]`
**Era:** V3 started 2026-06-09T21:21:00Z (V2 frozen, excluded). Live OFF confirmed — `bot_status.is_paused`=**true** / `bot_state`=paused (ts 17:37:54Z), **0** `options_scalp` opens in last hour (`options_scalp_enabled` flag is true but no live fills). No `paper_deposits` since era start → **burns 0/0**, no refill (both labs ≫ $50 floor).

**Balances (era math):**
- **Futures lab:** FUNDED $1,000 + closed P&L −$418.42 = **BALANCE $581.58** (n=132 closed, 9 open). Burns 0.
- **Options lab:** FUNDED $1,000 + closed P&L −$33.94 = **BALANCE $966.06** (n=34 closed, 0 open). Burns 0.

**Lab is ALIVE** — futures 8 closes in last hour (last close 17:30Z), options 3 closes (last 17:29Z). No stall. But this was the **worst futures hour of the era**: +8 closes for **−$87.99 (≈ −$11.0/trade)**, beating last hour's −$5/trade as the worst bleed rate yet. Crucially, **all 8 closes hit `paper_stop`** (count 59→67, net −$423→−$511) while `paper_trail` stayed **frozen at 37 / +$111.73** — i.e. **zero green closes this hour**. Options added 3 PUT_V3-led losing closes (−$7.85).

**Per-lane — Futures (era, closed only):**

| Lane | Closed | Win% | Net | Gross W | Gross L | PF | Hold |
|---|---|---|---|---|---|---|---|
| FUT_VWAP_10X | 14 | 29 | **−33.79** | 10.45 | −44.24 | 0.24 | 43m |
| FUT_DONCHIAN_RT_10X | 23 | 22 | −53.47 | 26.97 | −80.44 | 0.34 | 37m |
| FUT_EMA_PB_10X | 30 | 23 | −80.84 | 25.60 | −106.43 | 0.24 | 44m |
| FUT_SFP_15X | 36 | 22 | −114.29 | 31.13 | −145.42 | 0.21 | 28m |
| **FUT_EMA_PB_20X** | 29 | 17 | **−136.03** | 49.05 | −185.08 | 0.27 | 46m |

Every lane net-negative, every PF ≤ 0.34, win% 17–29%. Best (least-bad) = VWAP_10X −$33.79; worst = **EMA_PB_20X −$136.03**, still the only sub-20% win lane.

**EMA_PB 10X vs 20X head-to-head (12th straight net win for 10X, gap re-widening):** identical entries, 10X −$80.84 vs 20X −$136.03 → 20X loses **1.68×** more on cumulative net (up from last hour's 1.57×, reversing the compression; toward the prior 2.18×). This hour 10X lost −$16.58 (+2 closes) while 20X lost −$35.10 (+2 closes) — **20X bled 2.1× the 10X on the same entries**, confirming last hour's 20X "+$4.90" was a single-hour blip, not a turn. 20X is **32.5% of the futures loss at 17% win** — the single largest drag, intact 12 runs running.

**Exit-reason split — Futures (era, n=132):**

| Exit | Closed | Net | Avg |
|---|---|---|---|
| **paper_stop** | 67 | **−511.16** | −7.63 |
| breakeven_stop | 22 | −9.67 | −0.44 |
| stagnant_exit | 5 | −5.51 | −1.10 |
| no_traction | 1 | −3.81 | −3.81 |
| **paper_trail** | 37 | **+111.73** | +3.02 |

**11th straight run** with paper_stop > total futures loss: **paper_stop alone (−$511.16) = 122% of the −$418.42 loss**; paper_trail is the *only* green exit (+$111.73, +$3.02 avg) and was **frozen this hour** (no winners closed). breakeven_stop near-flat (−$0.44 avg, doing its protective job). 100% of the bleed is entries dying at the stop before traction — exits work mechanically (stop −7.6% of $100 margin is sane), entries don't. **Verdict: STRATEGY (no entry edge in chop), not an engine bug** — the stop/trail/breakeven machinery all behaves correctly.

**Per-lane — Options SELL_V3 (era, closed only):**

| Lane | Closed | Win% | Net |
|---|---|---|---|
| OPT_SELL_PUT_V3 | 12 | 33 | **−9.06** |
| OPT_SELL_RANGE_V3 | 9 | 33 | −11.22 |
| OPT_SELL_CALL_V3 | 13 | 31 | −13.66 |

PUT_V3 **regressed**: +3 closes this hour (9→12), all losers — win 44%→33%, net −1.21→**−9.06**, surrendering last hour's "near-green star" status. RANGE_V3 and CALL_V3 both frozen (no new closes). All n ≤13 → no verdict; options remains the far-less-bad book (−$34 vs −$418) but no lane has edge.

**DK harvest/strangle cohort:** **still 0 trades this era** — neither DK_V3 (trend-pick) nor the DK_PUT/DK_CALL strangle has fired. Entry window 07:30–11:18 UTC; lanes deployed after today's window, so first real chance is **tomorrow's 07:30–11:18Z**. Combined-daily-strangle headline: N/A (n=0). Verify the lanes actually arm at window open tomorrow.

**What to change next:**
1. **RETIRE FUT_EMA_PB_20X (loud, 12th ask).** −$136.03 = 32.5% of the futures loss, 17% win, loses 1.68× to its own 10X twin on identical entries — and bled 2.1× the 10X this hour. The single concrete, evidence-backed lever; monitor is read-only and cannot flip it.
2. **Futures structural:** bleed is 100% entry-quality (paper_stop −$511 vs paper_trail +$112, trail frozen this hour). This was the worst hour of the era (−$11/trade, 8/8 stop-outs). Attack entry selection (raise conf gate) — not the exits, which work. Hold all futures dark for live.
3. **Options:** PUT_V3 lost its near-green edge (−$9.06); no lane to crown, n ≤13. Still the safer book by far.
4. **DK:** nothing to judge until tomorrow's 07:30–11:18Z window produces the first settlements.

### 2026-06-10 16:40 UTC — V3 ~19.3h in: futures −$330.43 (n=124), options −$26.09 (n=31), burns 0, live OFF; **rough futures hour (−$55 / +11 closes)**; paper_stop = **128% of futures loss** (10th run >100%), EMA_PB 10X still beats 20X **11th straight** but gap compressed 2.18×→1.57× (20X actually +$4.90 this hour), DK strangle **still 0 fills this era** `[updated by: alpha-paper-lab-monitor]`
**Era:** V3 started 2026-06-09T21:21:00Z (V2 frozen, excluded). Live OFF confirmed — `bot_status.is_paused`=**true** (ts 16:37:54Z), **0** `options_scalp` opens in last hour. No `paper_deposits` since era start → **burns 0/0**, no refill (both labs ≫ $50 floor).

**Balances (era math):**
- **Futures lab:** FUNDED $1,000 + closed P&L −$330.43 = **BALANCE $669.57** (n=124 closed). Burns 0.
- **Options lab:** FUNDED $1,000 + closed P&L −$26.09 = **BALANCE $973.91** (n=31 closed). Burns 0.

**Lab is ALIVE** — futures 14 opens / 11 closes in last hour, options 3 opens / 3 closes. No stall. But this was a **rough futures hour**: vs 15:40 (−$274.97 / n=113), futures added 11 closes for **−$55.46 (≈ −$5.0/trade)**, the worst hourly bleed rate of the recent stretch. Options improved slightly (−$27.76 → −$26.09, +$1.67 on 3 PUT_V3-led closes).

**Per-lane — Futures (era, closed only):**

| Lane | Closed | Win% | Net | Gross W | Gross L | PF | Hold |
|---|---|---|---|---|---|---|---|
| FUT_VWAP_10X | 13 | 31 | **−24.02** | 10.45 | −34.47 | 0.30 | 44m |
| FUT_DONCHIAN_RT_10X | 23 | 22 | −53.47 | 26.97 | −80.44 | 0.34 | 37m |
| FUT_EMA_PB_10X | 28 | 25 | −64.26 | 25.60 | −89.85 | 0.28 | 45m |
| FUT_SFP_15X | 33 | 24 | −87.74 | 31.13 | −118.88 | 0.26 | 28m |
| **FUT_EMA_PB_20X** | 27 | 19 | **−100.93** | 49.05 | −149.99 | 0.33 | 46m |

Every lane net-negative, every PF < 0.5, win% 19–31%. Best (least-bad) = VWAP_10X −$24 (frozen, no new closes this hour); worst = **EMA_PB_20X −$100.93**, still the only sub-20% win lane.

**EMA_PB 10X vs 20X head-to-head (11th straight net win for 10X, but a wrinkle):** identical entries, 10X −$64.26 vs 20X −$100.93 → 20X still loses **1.57×** more on cumulative net, and remains the single largest drag on the book. BUT the gap **compressed from 2.18× → 1.57×**: this hour 10X lost −$15.73 (+4 closes) while 20X *gained* +$4.90 (+2 closes) — different specific trades closed in each lane's window, a single-hour blip. Note also PF this run is near-identical (10X 0.28, 20X 0.33) — on identical entries PF should match; the small divergence is exit/close-timing noise, not edge. **The retire-20X case rests on net-dollar drag (38% of futures loss at 19% win), which is intact 11 runs running.** No engine change made (read-only mandate) — escalating via pulse again.

**Exit-reason split — Futures (era, n=124):**

| Exit | Closed | Net | Avg |
|---|---|---|---|
| **paper_stop** | 59 | **−423.17** | −7.17 |
| breakeven_stop | 22 | −9.67 | −0.44 |
| stagnant_exit | 5 | −5.51 | −1.10 |
| no_traction | 1 | −3.81 | −3.81 |
| **paper_trail** | 37 | **+111.73** | +3.02 |

Same story, **10th straight run**: **paper_stop alone (−$423.17) is 128% of the total futures loss** (−$330.43); paper_trail is the *only* green exit (+$111.73 on 37 trades, +$3.02 avg). breakeven_stop near-flat (−$0.44 avg, doing its protective job). 100% of the bleed is entries dying at the stop before traction — exits work, entries don't.

**Per-lane — Options SELL_V3 (era, closed only):**

| Lane | Closed | Win% | Net | Hold |
|---|---|---|---|---|
| OPT_SELL_PUT_V3 | 9 | 44 | **−1.21** | — |
| OPT_SELL_RANGE_V3 | 9 | 33 | −11.22 | — |
| OPT_SELL_CALL_V3 | 13 | 31 | −13.66 | — |

PUT_V3 is the standout — +3 closes this hour, 33%→44% win, net −2.87 → **−1.21** (near breakeven, the best lane). RANGE_V3 and CALL_V3 both frozen vs 15:40 (no new closes). All n ≤13 → no verdict; fee drag on premium/notional still the structural eroder.

**DK harvest/strangle cohort:** **still 0 trades this era** — neither DK_V3 (trend-pick) nor the DK_PUT/DK_CALL strangle has fired a fill. Entry window is 07:30–11:18 UTC (0.7–4.5h pre-12:00Z settle); lanes were deployed after today's window, so first real chance is **tomorrow's 07:30–11:18Z**. Combined-daily-strangle headline: still N/A (n=0). Verify the lanes actually arm at window open tomorrow.

**What to change next:**
1. **RETIRE FUT_EMA_PB_20X (loud, 11th ask).** −$100.93 = 38% of the futures loss, 19% win, still loses to its own 10X twin on cumulative net. The single concrete, evidence-backed lever — needs a user/engine action; the monitor cannot flip it (read-only).
2. **Futures structural:** bleed is 100% entry-quality (paper_stop −$423 vs paper_trail +$112). No lane near PF 1.0; this hour was the worst bleed rate yet (−$5/trade). Attack entry selection (higher conf gate) — not the exits. Hold all futures dark for live.
3. **Options:** PUT_V3 only near-green lane (−$1.21, n=9); keep watching, no crown. Fee-on-notional still the eroder on the other two lanes.
4. **DK:** nothing to judge until tomorrow's 07:30–11:18Z window produces the first settlements.

### 2026-06-10 15:40 UTC — V3 ~18.3h in: futures −$274.97 (n=113), options −$27.76 (n=28), burns 0, live OFF; paper_stop = **131% of futures loss** (9th run >100%), EMA_PB 10X beats 20X **10th straight** (2.18×), DK strangle **still 0 fills this era** `[updated by: alpha-paper-lab-monitor]`
**Era:** V3 started 2026-06-09T21:21:00Z (V2 frozen, excluded). Live OFF confirmed — `bot_status.is_paused`=**true** (ts 15:37:51Z), **0** futures `scalp` opens in last hour. No `paper_deposits` since era start → **burns 0/0**, no refill (both labs ≫ $50 floor).

**Balances (era math):**
- **Futures lab:** FUNDED $1,000 + closed P&L −$274.97 = **BALANCE $725.03** (n=113 closed, 3 open). Burns 0.
- **Options lab:** FUNDED $1,000 + closed P&L −$27.76 = **BALANCE $972.24** (n=28 closed, 2 open SELL_PUT_V3 @14:14Z). Burns 0.

**Lab is ALIVE** — futures 4 opens / 5 closes in last hour (last open 15:20Z, last close 15:22Z). No stall this window (contrast 13:38 dead hour). Options last close was pre-window; only the 2 open PUT_V3 legs sit idle.

**Count reconciliation (NOT a purge):** prior 14:39 run logged futures n=121 / options n=34; this run logs 113 / 28. The deltas (−8 fut, −6 opt) equal that run's *open* positions — the 14:39 entry counted open+closed, this run counts **closed only** per era math. Both `opened_at` and `closed_at` era filters independently return 113 closed futures → no row loss. Methodology drift, not data loss.

**Per-lane — Futures (era, closed only):**

| Lane | Closed | Win% | Net | Gross W | Gross L | PF | Avg peak% | Hold |
|---|---|---|---|---|---|---|---|---|
| FUT_VWAP_10X | 13 | 31 | **−24.02** | 10.45 | −34.47 | 0.30 | 3.7 | 44m |
| FUT_DONCHIAN_RT_10X | 21 | 24 | −35.91 | 26.97 | −62.88 | 0.43 | 3.7 | 38m |
| FUT_EMA_PB_10X | 24 | 25 | −48.53 | 23.33 | −71.86 | 0.32 | 3.8 | 48m |
| FUT_SFP_15X | 30 | 27 | −60.68 | 31.13 | −91.81 | 0.34 | 4.5 | 29m |
| **FUT_EMA_PB_20X** | 25 | 16 | **−105.83** | 42.28 | −148.11 | 0.29 | 7.6 | 47m |

Every lane net-negative, every PF < 0.5, win% 16–31%. Best (least-bad) = VWAP_10X −$24; worst = **EMA_PB_20X −$105.83**, the only sub-20% win lane.

**EMA_PB 10X vs 20X head-to-head (10th straight win for 10X):** identical entries, 10X −$48.53 vs 20X −$105.83 → 20X loses **2.18×** more on the *same signals*. 20X also has the worst win% (16%) and biggest avg-peak (7.6%, i.e. it rides further into noise before stopping). 10X has beaten 20X every single check-in this era. **20X remains LIVE — it is the single largest drag on the futures book and should be retired.** (Flagged 10 runs running; no engine change made per read-only mandate — escalating to user via pulse.)

**Exit-reason split — Futures (era, n=113):**

| Exit | Closed | Net | Avg |
|---|---|---|---|
| **paper_stop** | 53 | **−361.45** | −6.82 |
| breakeven_stop | 19 | −6.89 | −0.36 |
| stagnant_exit | 5 | −5.51 | −1.10 |
| no_traction | 1 | −3.81 | −3.81 |
| **paper_trail** | 35 | **+102.69** | +2.93 |

Same story, 9th run: **paper_stop alone (−$361.45) is 131% of the total futures loss** (−$274.97); paper_trail is the *only* green exit (+$102.69 on 35 trades, avg +2.93). breakeven_stop is near-flat (−$0.36 avg, doing its protective job). The engine catches and trails real trends profitably — the bleed is entirely entry-noise getting stopped (53 stops at −6.82 avg, avg-peak only ~3.7% before reversing = wrong-direction / too-tight). Structural fix would be a higher conf gate or wider stop, but that's an engine change (not made).

**Per-lane — Options SELL_V3 (era, closed only):**

| Lane | Closed | Win% | Net | Gross | Hold |
|---|---|---|---|---|---|
| OPT_SELL_PUT_V3 | 6 | 33 | −2.87 | **+1.14** | 33m |
| OPT_SELL_RANGE_V3 | 9 | 33 | −11.22 | −5.36 | 76m |
| OPT_SELL_CALL_V3 | 13 | 31 | −13.66 | −5.55 | 63m |

PUT_V3 is the only gross-positive lane (+$1.14, fee-eaten to −$2.87). CALL_V3 gross stayed −$5.55 (flat vs 14:39 — no new closes). All n ≤13 → no verdict. Fee drag on premium/notional still the structural lever.

**DK harvest/strangle cohort:** **0 trades exist this era** — neither DK_V3 (trend-pick) nor the DK_PUT/DK_CALL strangle has fired a single fill. The lanes were deployed after today's 07:30–11:18 UTC entry window (0.7–4.5h pre-12:00Z settle), so first real chance is **tomorrow's window**. Combined-daily-strangle headline number: still N/A (n=0).

**What to change next:**
1. **RETIRE FUT_EMA_PB_20X (loud, 10th ask).** −$105.83 = 38% of the futures loss, 16% win, loses 2.18× to its own 10X twin on identical entries. Pure leverage-amplified noise. This is the one concrete, evidence-backed lever and it needs a user/engine action — the monitor cannot flip it (read-only).
2. **Futures structural:** bleed is 100% entry-quality (paper_stop −$361 vs paper_trail +$103). No lane near PF 1.0; nowhere close to the live gate. Hold all futures dark for live.
3. **Options:** PUT_V3 only gross-green lane but n=6; keep watching, no crown. Fee-on-notional still the eroder.
4. **DK:** nothing to judge until tomorrow's 07:30–11:18Z window produces the first settlements; verify the lanes actually arm at the window open.

### 2026-06-10 14:39 UTC — V3 ~17.3h in: futures −$235.59 (n=121), options −$26.66 (n=34), burns 0, live OFF; **✅ futures stall RESOLVED — lab opening normally again**; paper_stop = **141% of futures loss** (8th run >100%), EMA_PB 10X beats 20X **9th straight** (2.27×), DK strangle lanes **0 fills this era** `[updated by: alpha-paper-lab-monitor]`
**Era:** V3 started 2026-06-09T21:21:00Z (V2 frozen, excluded). Live OFF confirmed — `bot_status.is_paused`=**true**, **0** `options_scalp` opens in last hour. No `paper_deposits` since era start → **burns 0/0**, no refill (both labs ≫ $50 floor).

**✅ Futures stall resolved.** Last hour flagged a ~68-min dead window (13:00 hour booked 0 opens). This window the lab is **opening and closing normally** — last open **14:25:17**, last close **14:13:45**, 4 positions live (EMA_PB_10X×2, EMA_PB_20X×2, age ~15min). The freeze self-cleared (or the hung evaluator got picked back up); no engine restart was performed by this routine. Futures count advanced 102→**121** (+19 closes) so the loop is fully alive again. Watching for recurrence.

**Futures lab (V3):** FUNDED **$1,000.00**, closed **121**, realized **−$235.59**, BALANCE **$764.41**, BURNS **0** (4 open).

| FUT lane (V3) | Closed | Win% | Net | Gross win | Gross loss | PF | Avg hold |
|---|---|---|---|---|---|---|---|
| FUT_VWAP_10X | 14 | 36% | −$20.22 | $14.25 | $34.47 | **0.41** | 51m |
| FUT_DONCHIAN_RT_10X | 22 | 23% | −$36.23 | $26.97 | $63.20 | 0.43 | 38m |
| FUT_EMA_PB_10X | 26 | 31% | −$40.94 | $24.72 | $65.66 | 0.38 | 43m |
| FUT_SFP_15X | 31 | 29% | −$45.37 | $41.82 | $87.19 | 0.48 | 28m |
| FUT_EMA_PB_20X | 27 | 22% | **−$92.83** | $44.40 | $137.22 | **0.32** | 41m |

(+1 FUT_MOMENTUM_CONF restart-orphan, $0.) Best lane VWAP_10X (least-bad), worst **EMA_PB_20X**. Every lane PF < 0.5 — entries still don't follow through.

**Futures exit reasons — paper_stop is the entire drawdown again:**

| Exit | Count | Net |
|---|---|---|
| **paper_stop** | 51 | **−$332.57** |
| paper_trail | 34 | **+$108.08** |
| breakeven_stop | 17 | −$5.01 |
| restart_orphan | 13 | +$3.23 |
| stagnant_exit | 5 | −$5.51 |
| no_traction | 1 | −$3.81 |

paper_stop alone (−$332.57) = **141% of the lab's net loss** — 8th consecutive run it exceeds 100%. 51 of 121 trades (42%) stop out; only **paper_trail is green** (+$108, 34 trades, avg +$3.18/win vs −$6.52/stop). breakeven_stop is ~neutral. Same signal every hour: **the stop is the bleed, the trail is the edge** — survivors that reach the trail print.

**EMA_PB 10× vs 20× (identical entries, leverage A/B):** 10X −$40.94 vs 20X **−$92.83** = 20X loses **2.27×** more. 9th straight run 10X wins; 20X has zero independent thesis — it only amplifies the same losing edge (consistent with Verdict #5/#8). **Retire FUT_EMA_PB_20X** (standing recommendation, still live).

**Options lab (V3):** FUNDED **$1,000.00**, closed **34**, realized **−$26.66**, BALANCE **$973.34**, BURNS **0** (2 open, PUT_V3).

| OPT lane (V3) | Closed | Win% | Net | Gross win | Gross loss | PF | Avg hold |
|---|---|---|---|---|---|---|---|
| OPT_SELL_PUT_V3 | 10 | 50% | **−$2.61** | $6.95 | $9.56 | **0.73** | 23m |
| OPT_SELL_RANGE_V3 | 10 | 40% | −$11.06 | $4.55 | $15.61 | 0.29 | 69m |
| OPT_SELL_CALL_V3 | 14 | 36% | −$12.99 | $3.23 | $16.21 | **0.20** | 63m |

PUT_V3 best (near-breakeven, PF 0.73). CALL_V3 worst (PF 0.20) — put-selling continues to beat call-selling, consistent with up-biased tape. Options exits: sell_take_profit +$12.76 (8), sell_trend_break −$16.81 (13, the protection exit cuts at a loss), sell_breached −$17.60 (6), sell_stop −$6.11 (1).

**🚩 DK window lanes: 0 fills this era.** No OPT_SELL_DK_V3 / DK_PUT / DK_CALL trades exist (open or closed) since era start. The DK strangle was committed today (c638467, 113d9eb) but the entry window is **~07:30–11:18 UTC** (0.7–4.5h before the 12:00 settle) — the code almost certainly deployed *after* today's window closed. **Next chance: tomorrow ~07:30–11:18 UTC.** Verify next run that the DK code is live and fires; until then the headline strangle P&L number is unavailable (n=0).

**What to change next:** the futures stop is the whole loss — 51 stops bled $333 while the trail netted +$108. Widen/rework `paper_stop` (or pull it further from entry) so more trades survive into trail territory; and retire EMA_PB_20X (9th confirmation it strictly amplifies the losing edge).

### 2026-06-10 13:38 UTC — V3 ~16h in: futures −$300.18 (n=102, **FROZEN**), options −$27.75 (n=28), burns 0, live OFF; **⚠ FUTURES LAB STALLED ~68min — 0 opens / 0 closes, first dead hour this era (options unaffected)**; paper_stop = 111% of loss (7th run >100%), EMA_PB 10X beats 20X 8th time (2.14×); VWAP_10X "edge" ERASED (one new loser → gross −$11) `[updated by: alpha-paper-lab-monitor]`
**Era:** V3 started 2026-06-09T21:21:00Z (V2 history frozen, excluded). Live OFF confirmed — `bot_status` is_paused=**true**, `bot_state=paused` ("PAPER-ONLY mode"), FRESH 13:41:34 UTC, **0** `options_scalp` in last hour. No `paper_deposits` since era start → **burns 0/0**, no refill (both labs ≫ $50 floor). Regime TRENDING_UP since 13:30 (chop 0.54, atr_ratio 1.77).

**🚩 HEADLINE — the futures lab went silent for ~68 minutes (first time this era).** Last futures open **12:35:21**, last close **12:30:32**; the **13:00 UTC hour booked ZERO opens** — every prior hour this era ran 2–15 opens/hr:

| Hour (UTC) | 05 | 06 | 07 | 08 | 09 | 10 | 11 | 12 | 13 |
|---|---|---|---|---|---|---|---|---|---|
| FUT opens | 15 | 12 | 8 | 7 | 14 | 3 | 5 | 7 | **0** |

Six positions opened in a single 12:35 burst (EMA_PB_10X×2, DONCHIAN_RT_10X×2, EMA_PB_20X×2) and have sat **open and untouched for 68min** — none hit paper_stop / trail / breakeven / stagnation despite a live TRENDING_UP regime that should be generating pullback entries. **Options is unaffected** (3 opened / 2 closed in the same hour), so the engine process is alive — this looks like a **stalled paper-futures evaluator/exit loop, not a quiet market** (an ENGINE issue, not strategy). `bot_status.diagnostics` only tracks the live scalp pairs, so the paper-futures scan state isn't visible from here. **Action: inspect the engine's paper-futures loop / logs; a restart may be needed.** This routine is read-mostly + must not touch the engine, so flagging only — not restarting.

**Consequence:** all futures figures below are **frozen to the cent vs the 12:40 check-in** (102 / −$300.18). No new futures data this window — every trend read (per-trade worsening, lane ranks) is *carried over, not refreshed*.

**Futures lab (V3):** FUNDED **$1,000.00**, closed **102**, realized **−$300.18**, BALANCE **$699.82**, BURNS **0**. (6 open, frozen since 12:35.) Fees $137.50 → true gross **−$162.68**.

| FUT lane (V3) | Closed | Win% | Net | True gross¹ | Fees | Avg peak% | %>10min |
|---|---|---|---|---|---|---|---|
| FUT_VWAP_10X | 13 | 31% | −$24.02 | **−$11.02** | $13 | 3.69 | 100% |
| FUT_DONCHIAN_RT_10X | 19 | 16% | −$51.52 | −$32.52 | $19 | 2.44 | 89% |
| FUT_EMA_PB_10X | 20 | 20% | −$53.90 | −$33.90 | $20 | 2.81 | 95% |
| FUT_SFP_15X | 29 | 28% | −$55.29 | −$11.79 | $43.50 | 4.48 | 48% |
| FUT_EMA_PB_20X | 21 | 10% | −$115.45 | −$73.45 | $42 | 5.56 | 90% |

¹ true gross = net + fees (pnl_usd is fee-net).

**EMA_PB 10X-vs-20X head-to-head (identical entries, leverage A/B) — 10X wins 8th consecutive read:** 10X −$53.90 (20) vs **20X −$115.45 (21) → 20X loses 2.14× the 10X** (per-trade −$2.70 vs −$5.50; 20X avg peak 5.56% vs 10X 2.81% — leverage scales the swing, realized far worse, 10% win vs 20%). Eight reads running, frozen book. **Retire 20X — the A/B has no information left to give.** Reinforces verdict #5.

**VWAP_10X edge ERASED.** Last star lane (gross +$4.70 over 12 at 10:40) took one more loser before the freeze (now 13 closes) → **gross −$11.02**, 31% win. The "first real V3 edge" was a 12-trade small-sample artifact — a single adverse close wiped it. **Downgrade from "leading live candidate."** SFP_15X true gross −$11.79 (churns: 48% >10min, $43.50 fees). No futures lane is gross-positive this window.

**Exit cohorts (FUT, all closes) — frozen, same structural story (7th run >100%):**

| Exit | Closed | Net | Avg/trade |
|---|---|---|---|
| **paper_stop** | 51 | **−$332.57** | −$6.52 |
| paper_trail | 28 | **+$46.72** | +$1.67 |
| breakeven_stop | 17 | −$5.01 | −$0.29 |
| stagnant_exit | 5 | −$5.51 | −$1.10 |
| **no_traction** | **1** | −$3.81 | −$3.81 |

`paper_stop` = −$332.57 = **111% of net loss** (7th straight run >100%); `paper_trail` is the **only** green real exit (+$46.72, 28 trades). Stops outnumber trails ~1.8:1 AND each loser runs **3.9× bigger** than each winner ($6.52 vs $1.67). Exits work; entries die wrong-side first. `no_traction` still **inert — 1 fire in 16h** (gate unreachable; weak trades hit paper_stop at ~21m before a 60-min-red window matures). Still the highest-leverage engine fix.

**Options lab (V3):** FUNDED **$1,000.00**, closed **28**, realized **−$27.75**, BALANCE **$972.25**, BURNS **0**. Fees $17.99 → true gross **−$9.76**. *(Improved +$6.92 vs 12:40 on 2 TP winners — the only lab that traded this hour.)*

| OPT lane (V3) | Closed | Net | True gross | Fees | Avg hold |
|---|---|---|---|---|---|
| OPT_SELL_PUT_V3 | 6 | −$2.87 | **+$1.14** | $4.01 | 33m |
| OPT_SELL_RANGE_V3 | 9 | −$11.22 | −$5.36 | $5.87 | 76m |
| OPT_SELL_CALL_V3 | 13 | −$13.66 | −$5.55 | $8.11 | 63m |

PUT_V3 flipped **gross-positive (+$1.14)** this window on a TP win (was gross −$6.29 at 10:40) — but n=6, noise. CALL_V3 gross −$5.55 (worsened from +$0.39 at 10:40 — theta-side decay continues). RANGE holds 76m (anti-churn fix intact) yet still gross-negative — signal problem, not churn. Options exits: **sell_take_profit 8 / +$12.76 (only green)**, sell_trend_break 13 / −$16.81, sell_breached 6 / −$17.60, sell_stop 1 / −$6.11. n=28 far too small for a verdict.

**What to change next:**
1. **🚩 Investigate the futures-lab stall (ENGINE).** 68min with 0 opens/0 closes while options trades normally → likely a hung paper-futures evaluator/exit thread. Check engine logs / the paper-futures loop; restart if hung. Highest priority — a frozen lab gathers no data.
2. **Retire EMA_PB_20X.** Eighth-read A/B, 2.14× worse on identical entries — done. *(Engine change — recommendation only; routine is read-mostly.)*
3. **Loosen the `no_traction` gate.** One fire in 16h proves the 60-min-red window is unreachable; shorten it / relax the +0.4-ATR floor so it cuts losers before paper_stop.
4. **Stand down the VWAP_10X "live candidate" flag** — its edge was a 12-trade artifact, now gross-negative. No futures lane has a real gross edge.

**Verdict status:** unchanged headline. #5 (leverage on negative edge) reinforced an **8th time** (20X = 2.14× the 10X loss — retire 20X). V3 futures bleed remains 100% entry-quality / `paper_stop` (111%); trail is the lone green exit. **VWAP_10X edge retracted** (small-sample). #6/#9 (option selling): improving but tiny-n, true gross still −$9.76 — no verdict. **This hour's real event was an engine stall, not new strategy data.** No lane near PF>1 over 200 trades → live stays OFF.

### 2026-06-10 10:40 UTC — V3 ~13h in: futures −$214.02 (n=103), options −$26.15 (n=23), burns 0, live OFF; paper_stop = 113% of loss (5th run), EMA_PB 10X beats 20X 5th time (2.19×), VWAP_10X gross-POSITIVE, no_traction finally fired once `[updated by: alpha-paper-lab-monitor]`
**Era:** V3 started 2026-06-09T21:21:00Z (V2 history frozen, excluded). Live OFF confirmed — `bot_status` is_paused=**true**, FRESH 10:37:33 UTC, **0** `options_scalp` in last hour. No `paper_deposits` since era start → **burns 0/0**, no refill (both labs ≫ $50 floor).

**Futures lab (V3):** FUNDED **$1,000.00**, closed **103**, realized **−$214.02**, BALANCE **$785.98**, BURNS **0**. (+$6.22 `restart_orphan` artifact → true strategy PnL ≈ **−$220.24**.)

| FUT lane (V3) | Closed | Win% | Net | True gross¹ | Fees | PF | Avg hold | %>10min |
|---|---|---|---|---|---|---|---|---|
| FUT_VWAP_10X | 12 | 42% | −$5.30 | **+$4.70** | $10 | 0.73 | 53m | 92% |
| FUT_EMA_PB_10X | 20 | 30% | −$34.47 | −$18.47 | $16 | 0.20 | 37m | 75% |
| FUT_SFP_15X | 29 | 21% | −$44.43 | −$5.43 | $39 | 0.38 | 28m | 38% |
| FUT_DONCHIAN_RT_10X | 20 | 15% | −$51.84 | −$32.84 | $19 | 0.18 | 34m | 90% |
| FUT_EMA_PB_20X | 21 | 19% | −$75.55 | −$41.55 | $34 | 0.16 | 35m | 71% |

¹ true gross = net + fees (pnl_usd is already fee-net). A stray V2-named `FUT_MOMENTUM_CONF` (1 trade, net $0) also present, excluded from lane ranks.

**EMA_PB 10X-vs-20X head-to-head (identical entries, leverage A/B) — 10X wins 5th consecutive read:** 10X −$34.47 vs **20X −$75.55 → 20X loses 2.19× the 10X** on the same signals (20X avg peak 5.2% vs 10X 2.7% — leverage scales the swing, realized far worse). Five reads running. **Retire 20X — the A/B is decisively over.** Reinforces verdict #5.

**Two failure modes still cleanly separable by TRUE gross:**
- **Fee-killed (signal is fine, churn/fees sink it):** **VWAP_10X is now gross-POSITIVE (+$4.70)** over 12 trades — best PF (0.73), best survival (92% >10min) — only $10 fees flip it to −$5.30. The standout lane. SFP_15X is ~gross-flat (−$5.43) but slipped from last run's +$0.75; it churns most (28m hold, only 38% survive >10min) and bleeds $39 fees.
- **Signal-dead (genuinely wrong direction):** DONCHIAN_RT_10X (true gross −$32.84, 15% win, PF 0.18) is now signal-ACTIVE (20 trades, was "signal-dead/no-fire" last run) but the worst real signal — kill candidate. EMA_PB true gross −$18.47.

**Exit cohorts (FUT, all closes) — same structural story, 5th run straight:**

| Exit | Closed | Net | Avg/trade |
|---|---|---|---|
| **paper_stop** | 44 | **−$241.31** | −$5.48 |
| paper_trail | 24 | **+$52.32** | +$2.18 |
| restart_orphan | 8 | +$6.22 | (artifact) |
| breakeven_stop | 17 | −$5.01 | −$0.29 |
| stagnant_exit | 2 | −$3.83 | −$1.92 |
| **no_traction** | **1** | −$3.81 | −$3.81 |

`paper_stop` = −$241.31 = **113% of net loss** (5th run >100%); `paper_trail` is the **only** green real exit (+$52.32, 24 trades). Stops outnumber trails ~2:1 AND each loser runs **2.5× bigger** than each winner ($5.48 vs $2.18). Exits work; entries die wrong-side first.

**`no_traction` exit FINALLY fired — n=1 (−$3.81), first time in 5 check-ins** (added 06-10 commit 114e0f8). One fire across 13h confirms the gate ("red 60min AND never +0.4 ATR") is still far too strict to matter: weak trades hit `paper_stop` at ~21m, long before a 60-min-red window matures. The intended bleed-cutter is essentially inert. **Still the single highest-leverage engine fix.**

**Options lab (V3):** FUNDED **$1,000.00**, closed **23**, realized **−$26.15**, BALANCE **$973.85**, BURNS **0**.

| OPT lane (V3) | Closed | Net | True gross | Fees | Avg hold |
|---|---|---|---|---|---|
| OPT_SELL_CALL_V3 | 12 | −$4.94 | **+$0.39** | $5.33 | 46m |
| OPT_SELL_PUT_V3 | 4 | −$8.90 | −$6.29 | $2.60 | 25m |
| OPT_SELL_RANGE_V3 | 7 | −$12.17 | −$9.09 | $3.07 | 78m |

CALL_V3 stays gross-positive (+$0.39 over 12) but fee-flipped negative. RANGE holds 78m (hours-ish — anti-churn fix holding) yet is gross-negative (−$9.09) — that lane's signal, not churn, is the problem. PUT is worst (0% win, gross −$6.29). Options exits: sell_take_profit 4/+$2.55 (only green), sell_trend_break 8/−$9.32, sell_breached 5/−$13.61. n=23 still far too small for a verdict.

**What to change next:**
1. **Retire EMA_PB_20X.** Five-read A/B, 2.19× worse on identical entries — no further information to gain. *(Engine change — recommendation only; this routine is read-mostly.)*
2. **Loosen the `no_traction` gate.** One fire in 13h proves the window is unreachable; shorten the 60-min red window or relax the +0.4-ATR floor so it cuts losers before `paper_stop` does.
3. **Watch VWAP_10X — first lane with a real gross edge.** If it holds gross-positive over more trades, it's the live candidate; the only thing in its way is fees, so a lower-churn entry filter could flip it net-green.
4. Kill DONCHIAN_RT_10X — signal-active now but the worst real direction.

**Verdict status:** unchanged headline. #5 (leverage on negative edge) reinforced a **5th time** (20X = 2.19× the 10X loss — retire 20X). V3 futures bleed remains 100% entry-quality / `paper_stop`; trail is the lone green exit. **New:** VWAP_10X is the first V3 lane to post a positive true gross — the leading (still fee-blocked) live candidate. No lane near PF>1 over 200 trades, so live stays OFF.

### 2026-06-10 08:39 UTC — V3 ~11h in: futures −$193.82 (n=82), options −$8.62 (n=16), burns 0, live OFF; paper_stop = 118% of loss (4th run), EMA_PB 10X beats 20X 4th time, no_traction STILL never fires `[updated by: alpha-paper-lab-monitor]`
**Era:** V3 started 2026-06-09T21:21:00Z (V2 history frozen, excluded). Live OFF confirmed — `bot_status` is_paused=**true**, bot_state=paused, "PAPER-ONLY mode", FRESH 08:39:35 UTC. No `paper_deposits` since era start → **burns 0/0**, no refill (both labs ≫ $50 floor). **Note:** found an *uncommitted* Cowork rewrite of the 07:39 entry in the working tree (recasts it as a full-book V2+V3 view and flags a mutable closed-ledger / restart_orphan toggling bug). Not mine to discard — preserved as-is and committed alongside this entry.

**Futures lab (V3):** FUNDED **$1,000.00**, closed **82**, realized **−$193.82**, BALANCE **$806.18**, BURNS **0**. 2 open. (Note: +$6.22 of that is `restart_orphan` artifacts — true strategy PnL ≈ **−$200.04**.)

| FUT lane (V3) | Closed | Win% | Net | Gross | Fees | Avg hold | %>10min |
|---|---|---|---|---|---|---|---|
| FUT_VWAP_10X | 9 | 44% | −$9.17 | −$4.97 | $8.00 | 58m | 100% |
| FUT_EMA_PB_10X | 16 | 31% | −$31.58 | −$18.97 | $14.00 | 40m | 88% |
| FUT_SFP_15X | 25 | 24% | −$36.02 | **+$0.75** | $36.00 | 30m | 44% |
| FUT_DONCHIAN_RT_10X | 15 | 7% | −$52.59 | −$38.27 | $14.00 | 34m | 93% |
| FUT_EMA_PB_20X | 16 | 25% | −$64.46 | −$38.58 | $28.00 | 39m | 88% |

**EMA_PB 10X-vs-20X head-to-head (identical 16/16 entries, leverage A/B) — 10X wins 4th consecutive read:** 10X −$31.58 (31% win) vs **20X −$64.46 (25% win) — 20X loses 2.04× the 10X** on the same signals. 20X avg peak 4.9% vs 10X 2.5% (leverage scales the swing) but realized far worse. The A/B has answered four times running; **retire 20X.** Reinforces verdict #5.

**Two distinct failure modes now separable by gross:**
- **Signal-dead:** DONCHIAN_RT_10X (7% win, gross **−$38.27**) and EMA_PB (gross −$19/−$39) genuinely pick wrong direction. DONCHIAN_RT is the worst real lane — kill candidate.
- **Fee-killed:** SFP_15X is **gross-breakeven (+$0.75)** over 25 trades but $36 fees → net −$36.02. The signal isn't the problem there; the churn is (avg 30m, only 44% survive >10min — it gets noise-stopped fastest).

**Exit cohorts (FUT, n=82) — same structural story, 4th run straight:**

| Exit | Closed | Net | Avg/trade |
|---|---|---|---|
| **paper_stop** | 41 | **−$229.45** | −$5.60 |
| paper_trail | 20 | **+$36.72** | +$1.84 |
| restart_orphan | 8 | +$6.22 | (artifact) |
| breakeven_stop | 11 | −$3.47 | −$0.32 |
| stagnant_exit | 2 | −$3.83 | −$1.92 |

`paper_stop` = −$229.45 = **118% of net loss**; `paper_trail` is the **only** green real exit (+$36.72). Stops outnumber trails 2:1 (41 vs 20) AND each loser runs **3.0× bigger** than each winner ($5.60 vs $1.84). Exits work; entries die wrong-side before they can run.

**`no_traction` exit (added 06-10 in commit 114e0f8 to pull out sooner) has STILL fired 0 times — 4th check-in running.** Its gate ("red 60min AND never +0.4 ATR") is unreachable: weak trades hit `paper_stop` at avg **21m** hold, long before the 60-min-red window can mature. The sooner-exit logic built to cut exactly this bleed never triggers. **Single highest-leverage actionable.**

**Options lab (V3):** FUNDED **$1,000.00**, closed **16**, realized **−$8.62**, BALANCE **$991.38**, BURNS **0**. 4 open.

| OPT lane (V3) | Closed | Net | Gross | Fees | Avg hold |
|---|---|---|---|---|---|
| OPT_SELL_PUT_V3 | 2 | −$2.09 | −$0.88 | $1.21 | 8m |
| OPT_SELL_RANGE_V3 | 4 | −$2.87 | −$1.36 | $1.68 | 78m |
| OPT_SELL_CALL_V3 | 10 | −$3.66 | **+$0.99** | $5.33 | 46m |

Whole options book: gross ≈ **−$1.25**, fees **$8.22** → net −$8.62 — **fees are ~2/3 of the loss** and CALL_V3 is gross-positive (+$0.99) but fee-flipped to −$3.66. Exits: sell_take_profit 4/+$2.55 (only green), sell_trend_break 7/−$5.26, sell_breached 3/−$6.76. Holds 8–78m (RANGE finally hours-ish) — structural anti-churn fix sticking, but n=16 is far too small for a verdict.

**What to change next:**
1. **Loosen the `no_traction` gate so it fires before `paper_stop`** (shorten the 60-min red window or relax the +0.4-ATR floor). It's the engine's intended fix for the exact bleed and has never fired in 4 check-ins. *(Engine change — recommendation only; this routine is read-mostly.)*
2. **Retire EMA_PB_20X and kill DONCHIAN_RT_10X.** A/B answered 4×; DONCHIAN_RT is gross-negative AND the worst lane.
3. Let lanes accumulate — no lane is near PF>1 or 200 trades, so no live gate. Live stays OFF.

**Verdict status:** unchanged. #5 (leverage on negative edge) reinforced a 4th time (20X = 2.04× the 10X loss). V3 futures bleed remains 100% entry-quality / paper_stop; trail is the lone green. No lane qualifies for live.

### 2026-06-10 06:40 UTC — V3 first real sample (~9h in): futures −$165 (n=59), options −$8 (n=13), burns 0, live OFF; bleed is ALL paper_stop, EMA_PB 10X beats 20X head-to-head `[updated by: alpha-paper-lab-monitor]`
**Era:** V3 started 2026-06-09T21:21:00Z. First check-in with enough closes to read lanes. Both labs still solvent, **0 burns** — already a different world from the V2 era's hourly refills. Live OFF confirmed (bot_status is_paused=**true**, FRESH 06:37:33 UTC, **0 options_scalp** in last hour). Engine is actively trading: last hour futures opened 15 / closed 11, options opened 1. No refill (both ≫ $50 floor).

**Futures lab (V3):** FUNDED **$1,000.00**, closed **59**, realized **−$165.03**, BALANCE **$834.97**, BURNS **0**. 8 open.

| FUT lane (V3) | Closed | Win% | Net | PF | Avg hold |
|---|---|---|---|---|---|
| FUT_VWAP_10X | 7 | 29% | −$13.14 | 0.29 | 41.0m |
| FUT_SFP_15X | 19 | 26% | −$19.80 | 0.57 | 31.6m |
| FUT_EMA_PB_10X | 11 | 18% | −$28.11 | 0.17 | 41.5m |
| FUT_DONCHIAN_RT_10X | 11 | 9% | −$45.13 | **0.04** | 29.9m |
| FUT_EMA_PB_20X | 11 | 9% | −$58.85 | 0.16 | 42.1m |

**EMA_PB 10X-vs-20X head-to-head (identical entries, leverage A/B):** 10X −$28.11 / 18% win vs **20X −$58.85 / 9% win — 20X loses 2.09× the 10X.** With a negative edge, leverage only scales the bleed; lower leverage is strictly better. **10X wins the head-to-head decisively.** Best (least-bad) lane: VWAP_10X (−$13.14, PF 0.29). Worst: EMA_PB_20X / DONCHIAN_RT_10X (PF 0.04, 9% win — a near-pure loser).

**Exit cohorts (FUT, n=59) — same structural story as V2, just smaller leverage:**

| Exit | n | Net |
|---|---|---|
| **paper_stop** | 34 | **−$195.17** |
| paper_trail | 15 | **+$36.71** |
| breakeven_stop | 8 | −$2.73 |
| stagnant_exit | 2 | −$3.83 |

`paper_stop` = −$195.17 = **118% of total loss**; `paper_trail` is the **only** green exit (+$36.71, +$2.45/trade). Avg stop = **−$5.74**, so **losers run 2.34× bigger than winners** — entries are still wrong-direction and getting noise-stopped, exactly the V2 finding but now without 50–100× to amplify it (V2: paper_stop was 112% of loss). Exits work; entries don't.

**Options lab (V3):** FUNDED **$1,000.00**, closed **13**, realized **−$8.33**, BALANCE **$991.67**, BURNS **0**. 3 open.

| OPT lane (V3) | Closed | Win% | Net | Avg hold |
|---|---|---|---|---|
| OPT_SELL_CALL_V3 | 8 | 50% | −$3.20 | 41.2m |
| OPT_SELL_PUT_V3 | 2 | 0% | −$2.09 | 8.1m |
| OPT_SELL_RANGE_V3 | 3 | 33% | −$3.04 | 102.9m |

Exits: sell_take_profit 4 / **+$2.55** (only green), sell_trend_break 6 / −$4.13, sell_breached 3 / −$6.76. **V3 question #1 (holds finally HOURS?):** RANGE_V3 avg **102.9m** — yes, the range lane is holding ~1.7h; CALL_V3 41m, PUT_V3 only 8m. **#2 (gross beats premium-capped fee?):** can't tell on n=13 — net −$8.33 is tiny and CALL_V3 is 50% win yet still slightly red, consistent with small losers + residual fee. **No verdict — sample far too small (need ~hundreds of closes).**

**The new thing:** (1) **The leverage-cap rebuild is working as designed** — 9h in, futures has bled only −$165 on $100-margin/10–20× lanes with **zero burns**, vs the V2 book that needed a $1k refill roughly hourly. Same losing entry mechanism, but the damage is now bounded. (2) **`no_traction` exit (added in commit 114e0f8) has fired 0 times** — either not deployed to the running engine, or no trade has met the "red 60min, never +0.4 ATR" condition yet. Flagging to confirm next run it's actually live. (3) **paper_trail is the lone profit engine again** — the whole game remains "stop the noise-stops from outnumbering the trails."

**What we should change:**
1. **Drop FUT_EMA_PB_20X.** Identical entries to the 10X twin, loses 2.09× as much — the head-to-head is unambiguous, the 20X leg adds only downside.
2. **Attack the stop asymmetry.** Losers are 2.34× winners and paper_stop is 118% of loss → entries fire into immediate adverse moves (avg stopped peak was ~+1.4% in V2). Tighten the entry (require pullback/retest confirmation) and/or tighten stops so a wrong entry costs less than a right one earns.
3. **DONCHIAN_RT_10X is a kill candidate** (PF 0.04, 9% win) — let it reach ~30–50 closes, but it's trending toward "retire."
4. **Confirm `no_traction` is deployed** (0 fires in 9h is suspicious for a just-added exit).

**Verdict status:** No V3 verdict yet (n=59 fut / 13 opt). Working hypotheses from V2 are **holding** in V3: entries are the whole futures problem (paper_stop 118% of loss), leverage only scales a negative edge (10X≫20X), options structurally fee/small-loser-capped. GATE TO LIVE (PF>1.0 over ~200 trades) — **not close; no lane is even PF>0.6 yet.**

### 2026-06-09 21:38 UTC — FIRST V3-ERA CHECK-IN, both labs fresh at $1,000, burns 0, live OFF `[updated by: alpha-paper-lab-monitor]`

**Era context:** V3 started 2026-06-09T21:21:00Z; both labs re-seeded to $1,000 (re-seed deposits landed 21:20:07/21:20:09Z, intentionally just BEFORE the cutoff so FUNDED stays at the $1,000 base). All V2 history (FUT_*_CONF/50X/100X, OPT_SELL_* legacy) is frozen — excluded from every number below. This run is only ~17 min into the era, so samples are tiny; this is a baseline, not a verdict.

**Futures lab (V3):** FUNDED **$1,000.00**, closed 0, BALANCE **$1,000.00**, BURNS **0**. 1 open position (FUT_SFP_15X). No V3 futures lane has booked a closed trade yet.

| FUT lane (V3) | Total | Closed | Open | Net |
|---|---|---|---|---|
| FUT_SFP_15X | 2 | 0 | 1 | — |
| FUT_MOMENTUM_CONF* | 1 | 0 | 0 | — |

*FUT_MOMENTUM_CONF is a RETIRED V2 lane name but one row carries opened_at ≥ era start with status≠closed/open (cancelled/orphan). Cosmetic leak of the old lane name into the era window — flagging, not a loss. None of the five real V3 lanes (EMA_PB_10X/20X, DONCHIAN_RT_10X, VWAP_10X) has fired yet. EMA_PB 10X-vs-20X head-to-head: **no data yet** (0 entries either side).

**Options lab (V3):** FUNDED **$1,000.00**, closed 2 (**−$2.09**), BALANCE **$997.91**, BURNS **0**. 1 open (OPT_SELL_RANGE_V3) + 1 restart_orphan row (cancelled).

| OPT lane (V3) | Closed | Net | Exit | Avg |
|---|---|---|---|---|
| OPT_SELL_PUT_V3 | 2 | −$2.09 | sell_trend_break | −$1.045/trade |

**Read:** Far too early to judge the two V3 questions (do options now hold HOURS? does gross beat the new premium-capped fee?). Both V3 options closes were `sell_trend_break` exits at ~−$1.05 each — can't yet tell fee vs gross split on n=2. Will need ≥1–2h of accumulation before EMA_PB 10X/20X or the options fee-fix show signal.

**Live OFF — confirmed:** bot_status is_paused=**true**, bot_state=**paused**, pause_reason "PAPER-ONLY mode (no live trading)", market_regime TRENDING_DOWN, real capital $27.08, **0 options_scalp trades in the last hour**. ✓

**AUTO-REFILL:** none — both labs ≫ $50 floor.

**Verdict status:** carried over from V2, unverified in V3. Prior V2 findings (entries are the whole problem on futures; options structurally fee-capped) remain the working hypotheses to re-test on V3 lanes. No V3 verdict yet — insufficient sample.

### 2026-06-09 19:40 UTC - check-in, AUTO-REFILL burn #26 fired (cadence collapsed to 1h), futures bleed eased to ~-$419, ORPHAN OPEN-BOOK CLEARED, first paper_max_hold loser `[updated by: Cowork]`
**Independent recompute ~1 min after the concurrent 19:39 monitor entry below. Reads AGREE on the headline: burn #26 fired 19:39:16 only 1h after #25 (cadence compressed 3h -> 2h -> 1h), the red hour was LIGHTER (~-$419), and the stale orphan open-book is finally reconciled. Minor count divergence as usual (my closed=1,441/net -$26,069.60/bal ~$930.40 vs monitor's realized 1,461/-$26,073.89/$926.11 - a few closes apart; my options is SELL-filtered closed=735/net -$419.52 vs monitor's all-options 789/-$421.12). db now 2026-06-09 19:39 (bot_status FRESH 19:38:51 UTC). Futures funded $26,000 -> **$27,000** (1 seed + 26 burns) after BURN #26 (paper_deposits id 28, +$1,000, 19:39:16 UTC). Options funded $1,000 (0 burns), bal ~**$580.48**. Live OFF (is_paused=true, bot_state=paused, "PAPER-ONLY mode"). Regime **TRENDING_UP** (regime_since 19:04:36, ~34m in; chop 0.429 = unusually clean/orderly trend, atr 1.1, net_change_30m +0.209). Verdict unchanged.**
- **What's happening (db now 19:39):** `bot_status` FRESH 19:38:51, paused, market_regime=TRENDING_UP, delta_bal $27.08, live open_positions=0, last_scan 182s ago, win_rate 34.8. **Open book now CLEAN: futures 2 (oldest 06-09 19:33), options(SELL) 6 (oldest 06-09 18:19, newest 19:31)** - the long-standing stale 06-06 orphan pile (was fut 20 / opt 54) is GONE.
- **What happened since last Cowork check (18:40, ~60 min):** Futures closed 1,421 -> **1,441 (+20)**, net -$25,650.35 -> **-$26,069.60 (-$419.25)** - **bleed eased** back toward baseline (vs the prior 3 heavy hours -$605 / -$769 / -$735), dominated by ~+15 `paper_stop` hits. Options (SELL) closed 731 -> **735 (+4)**, net -$422.33 -> **-$419.52 (+$2.81)** - **2nd straight tiny-positive hour**, all 4 closes were sell_take_profit. **BURN #26 fired 19:39:16** (thin post-#25 bal $349.65 + a moderate -$419 hour = floor break).
- **Per-lane futures (n=1,441):** FUT_MOMENTUM_CONF 612/14.2%/**-$11,399.06**/67.6x/4.9m/peak 8.95%; FUT_DONCHIAN_100X 170/16.5%/-$5,617.98/100x/2.3m; FUT_DONCHIAN_CONF 162/23.5%/-$3,373.05/56.3x/5.5m; FUT_DONCHIAN_50X 161/21.7%/-$2,905.50/50x/4.8m; FUT_EMA_CONF 338/34.0%/-$2,824.76/29.7x/10.3m. **MOMENTUM_CONF = 43.7% of loss; + DONCHIAN_100X = -$17,017.04 = 65.3%** (shape unchanged). Least-bad EMA_CONF (34.0% win, lowest lev 29.7x, longest hold 10.3m).
- **Exit cohorts (futures, n=1,441):** `paper_stop` **811/0%/-$29,388.41 @ +1.46% avg peak = 112.7% of total loss** (+15 since 18:40). Profit cohort `paper_trail` +$1,570.46 (542/51.3%/+15.98%) + `paper_max_hold` +$2,436.52 (29/82.8%/+47.40%) = **+$4,006.98**. Plus ema21_lost -$403.22 (33), ema21_reclaimed -$290.27 (25), donchian_mid_revert -$45.43 (3) - all frozen. Exits work, entries are the whole problem.
- **Options (SELL, n=735, all 5 lanes red):** OPT_SELL_PUT_FAR 174/6.9%/-$99.40/$0.598; OPT_SELL_CALL 148/14.9%/-$96.53/$0.594; OPT_SELL_PUT 181/13.3%/-$93.50/$0.597; OPT_SELL_NEUTRAL 157/15.3%/-$72.93/$0.597; OPT_SELL_CALL_FAR 75/13.3%/-$57.15/$0.613. Per-trade -$419.52/735 = -$0.571 ~ avg fee ~$0.60 = still fee-bound. Exits: sell_take_profit 505/18.2%/-$102.56, sell_stop 157/0%/-$236.72 (frozen), **sell_breached 73/0%/-$80.24 = 9.9% of closes (frozen)**. The +4 closes were all sell_take_profit (+$2.82).
- **The new thing:** (1) **Burn cadence COLLAPSED to 1h** - #24 16:39, #25 18:39 (2h), **#26 19:39 (1h)**. The bleed actually eased this hour (-$419 vs -$735), but each refill now leaves so little cushion ($349 post-#25) that even a moderate hour trips the $50 floor. Death-spiral interval tightening (3h -> 2h -> 1h) independent of hourly loss size. (2) **Orphan open-book CLEARED** - options open collapsed 54 -> 6 and futures to 2, all opened TODAY (oldest opt 18:19, fut 19:33); the stale 06-06 pile that persisted for days is reconciled out (cancelled SELL count now 48). First clean book in the stretch - the durable sweep flagged "still not done" for many runs appears DONE. (3) **First `paper_max_hold` LOSER** - cohort ticked 28 -> 29 but net went DOWN -$4.33 and win% 85.7% -> 82.8%; the rare big-runner exit booked a loss for the first time. Minor, breaks the perfect streak. (4) **Futures bleed decelerated** to ~baseline while structure is identical (paper_stop = 112.7% of loss) - velocity of the same bad-entry mechanism, eased this hour. (5) **Options spared on TRENDING_UP** because chop is unusually low (0.429, orderly trend) - CALL lanes not stopped, theta harvested cleanly (contrast the 17:39 choppy-up hour that stopped CALLs). Cumulatively still fee-bound, no lane positive.
- **What we should change (unchanged):** (1) Futures: attack ENTRIES not exits - pullback/retest before breakout + **cap leverage <=10x**; **kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (65.3% of loss)**; keep EMA_CONF as template. (2) Options: fix fee-on-notional model + move to defined-risk spreads. (3) Ops: orphan sweep now appears done - verify it persists next run and confirm whether the old 06-06 opens were closed or cancelled. (Did NOT refill / change anything - append-only scope; burn #26 was the engine's own auto-refill.)
- **Known-bug status (vs 06-06):** (a) option-sell fee-on-notional **STILL PRESENT** (avg fee ~$0.60 ~ per-trade loss -$0.571). (b) `sell_breached` 15-25m exit **STILL APPEARS FIXED** (frozen at 73, 9.9% of closes, 10.1m hold, not "nearly all"). (c) futures `paper_max_hold` ~30m cap **NOT the driver** (29, +$2,436 @ +47.4% peak; booked its first loser this hour). (d) orphaned-open non-reconciliation **NOW APPEARS RESOLVED** - open book fut 2 / opt 6, all opened today; old 06-06 orphans cleared. `paper_stop`/entries remain the structural killer (112.7% of loss).
- **Verdict:** #8 (aggressive 25-100x futures) **DEAD** (-$26.1k closed, 26 burns, solvent only via refills; burn cadence now 1h). #6 (OTM selling) **break-even/dead, fee-bound** (n=735, two tiny +hours != edge, no lane positive). #5 dead. No strategy verdict change without a clean entry-filter + leverage-cap rebuild.

### 2026-06-09 19:39 UTC — check-in, AUTO-REFILL burn #26 fired (only 1h after #25 — cadence compressed to ~hourly), LIGHTER red hour (−$419), STALE ORPHAN PILE FINALLY RECONCILED `[updated by: alpha-paper-lab-monitor]`
**45th run. Futures broke the $50 floor again and went negative pre-refill: funded $26,000 (1 seed + 25 burns), realized 1,461 / net −$26,073.89 → bal **−$73.89** ≤ $50 → **AUTO-REFILL BURN #26 fired** (paper_deposits id 28, +$1,000, 2026-06-09 19:39 UTC) → funded **$27,000**, bal **$926.11**. Options funded $1,000 (0 burns), realized 789 / net −$421.12 → bal **$578.88** (> $50, no refill). Live OFF confirmed (is_paused=true, bot_state=paused, FRESH 19:38:51 UTC; 0 options_scalp in last hour). Verdict unchanged — same structural story.**
- **What's happening (db now 19:39:01):** `bot_status` FRESH 19:38:51 UTC, is_paused=true, bot_state=paused (PAPER-ONLY mode), live open_positions=0. **Open paper book now CLEAN of stale orphans:** futures truly-open = **2** (oldest 19:33:30 *today*), options truly-open = **6** (oldest 18:19:05 *today*). The long-standing 06-06 pile is gone — 18 fut + 48 opt rows moved to status=`cancelled` (oldest 06-06 17:31 / 17:35). Durable orphan sweep finally ran.
- **What happened since last check (18:39, ~1h):** Futures realized 1,421 → **1,461** (+40, incl. ~18–20 orphan rows reconciled this hour), net −$25,650.35 → **−$26,073.89**. The genuinely-new closes (closed_at within 1h) = **20 closes / −$419.26** — **LIGHTER than the −$605/−$769/−$747 three-hour stretch**, reverting toward the ~$335/hr baseline. Decomposes cleanly: paper_stop +13 (−$424.44) + paper_trail +6 (+$9.52, back to net-positive) + paper_max_hold +1 (−$4.33). Options realized 731 → **789** (+58, mostly the 48 orphan rows + small fresh batch), net −$422.34 → **−$421.12**; fresh closes (1h) = **4 / +$2.82** (lane ~idle, theta).
- **Per-lane futures (n=1,461):** FUT_MOMENTUM_CONF 617/14.4%/**−$11,386.01**/67.5×/4.9m (max peak +326.56%); FUT_DONCHIAN_100X 172/16.3%/−$5,617.98/100×/2.3m; FUT_DONCHIAN_CONF 164/23.8%/−$3,353.30/56.3×/5.4m; FUT_DONCHIAN_50X 163/21.5%/−$2,905.50/50×/4.8m; FUT_EMA_CONF 345/33.9%/−$2,810.50/29.6×/15.7m. **MOMENTUM_CONF = 43.7% of loss; + DONCHIAN_100X = −$17,003.99 = 65.2%** (shape unchanged). Least-bad EMA_CONF (33.9% win, lowest lev 29.6×, longest hold 15.7m).
- **Exit cohorts (futures, n=1,461):** `paper_stop` **809/0%/−$29,337.66 @ +1.46% avg peak = 112.5% of total loss** (+13 this hour). Profit cohort `paper_trail` +$1,570.46 (542/51.3%/+15.98% peak) + `paper_max_hold` +$2,436.52 (29/82.8%/+47.40% peak, **UNFROZE 28→29** after 3+ frozen hours — but the new row was a small loss −$4.33). Plus ema21_lost −$403.22 (33), ema21_reclaimed −$290.27 (25), restart_orphan +$11.89 (18), donchian_mid_revert −$45.43 (3), null −$18.08 (2) — all frozen. Exits work; wrong-direction entries noise-stopped at +1.46% peak are the whole problem.
- **Options (SELL, n=789, all 5 lanes red, fee-bound):** OPT_SELL_PUT_FAR 182/7.7%/−$100.22/−$0.551; OPT_SELL_PUT 189/12.7%/−$97.02/−$0.513; OPT_SELL_CALL 160/19.4%/−$92.40/−$0.578; OPT_SELL_NEUTRAL 169/15.4%/−$75.92/−$0.449; OPT_SELL_CALL_FAR 89/19.1%/−$55.38/−$0.622. Per-trade −$421.12/789 = −$0.534 ≈ avg fee ~$0.59 → fees ≈ 100% of loss. Exits: sell_take_profit 505/18.2%/−$102.56, sell_stop 157/0%/−$236.72, sell_breached 73/0%/−$80.24 (frozen, 9.3% of closes), restart_orphan 48/−$0.02. No lane with edge.
- **The new thing:** (1) **Burn cadence COMPRESSED to ~hourly** — #24 16:39 / #25 18:39 (2h) / **#26 19:39 (just 1h later)**. The mechanism is now structural: post-#25 balance was only $349.65, so even a *lighter* −$419 hour broke the $50 floor. Each $1k refill now buys ≲1h of runway → burns are going roughly hourly regardless of hour severity. (2) **STALE ORPHAN PILE FINALLY RECONCILED** — the 06-06 open positions (flagged "still not done" for ~15+ hours, aging 25–55h) were swept to status=`cancelled` (18 fut + 48 opt); the only open trades left are fresh (today, 19:33 / 18:19). Known-bug (d) resolved this hour. (3) **`paper_max_hold` unfroze 28→29** after 3+ static hours — but the new winner was actually a small loser (−$4.33), so cohort total dipped slightly. (4) **Hour was lighter (−$419)** — bleed reverting toward baseline after the 3-heavy-hour spike, yet still burned because refill headroom is now razor-thin. (5) **`paper_trail` back to net-positive** (+6, +$9.52) after 2 net-negative hours.
- **What we should change (unchanged):** (1) Futures: attack ENTRIES not exits — pullback/retest before breakout + **cap leverage ≤10×**; **kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (65.2% of loss)**; keep EMA_CONF as the template (least-bad, lowest lev, longest hold). (2) Options: fix fee-on-notional model + move to defined-risk spreads. (3) Ops: **orphan sweep is DONE this hour** — keep watching it stays clean. (Did refill burn #26 — in-scope; did NOT change engine/strategy.)
- **Known-bug status (vs 06-06):** (a) option-sell fee-on-notional **STILL PRESENT** (avg fee ~$0.59 ≈ per-trade loss −$0.534). (b) `sell_breached` 15-25m exit **STILL APPEARS FIXED** (73, 9.3% of closes, frozen). (c) futures `paper_max_hold` ~30m cap **NOT the driver** (29, +$2,436 @ +47.40% peak). (d) orphaned-open non-reconciliation **RESOLVED this hour** — stale 06-06 opens cancelled, open book now only fresh trades. `paper_stop`/entries remain the structural killer (112.5% of loss).
- **Verdict:** #8 (aggressive 25–100× futures) **❌ DEAD** (−$26.1k realized, **26 burns**, solvent only via refills; burn cadence now ~hourly). #6 (OTM selling) **⚠️ break-even/dead, fee-bound** (n=789, no lane with edge). #5 dead. No strategy verdict change without a clean entry-filter + leverage-cap rebuild.

### 2026-06-09 18:40 UTC — check-in, AUTO-REFILL burn #25 fired EARLY (2h after #24, cadence accelerating), 3rd straight heavy futures hour, options booked first net-POSITIVE batch `[updated by: Cowork]`
**Independent recompute ~1 min after the concurrent 18:39 monitor entry below (reads AGREE on the headline: burn #25 fired 18:39:33 — 2h after #24, ahead of the clean 3h cadence; futures went negative pre-refill; 3rd straight heavy hour ~−$735). My SELL-filtered options net −$422.33 vs monitor's −$422.34 (rounding). Clean ~1h interval since the 17:39 Cowork run. Futures funded $25,000 → **$26,000** (1 seed + 25 burns) after burn #25, closed 1,421 / net −$25,650.35, bal ≈ **$349.65**. Options funded $1,000 (0 burns), closed 731 / net −$422.33, bal ≈ **$577.67**. Live OFF (is_paused=true, bot_state=paused, FRESH 18:38:51 UTC). Regime **TRENDING_UP** (regime_since 18:18:10, chop 0.679, atr 1.0, net_change_30m +0.401). Verdict unchanged.**
- **What's happening (db now 18:40:23):** `bot_status` FRESH 18:38:51, paused, "PAPER-ONLY mode", market_regime=TRENDING_UP, capital/delta_bal $27.08, live open_positions=0, last_scan 182s ago. Open paper: **futures 20, options 54** (orphans persisting — oldest fut 06-06 17:31 / avg 24.8h, oldest opt 06-06 17:35 / avg 54.7h).
- **What happened since last Cowork check (17:39, ~61 min):** Futures closed 1,395 → **1,421 (+26)**, net −$24,915.16 → **−$25,650.35 (−$735.19)** — **3rd straight heavy hour** (−$605 / −$769 / −$735 vs the ~$335/hr baseline; bleed sustained, not reverting). **BURN #25 fired 18:39:33** (bal went NEGATIVE −$650.35 ≤ $50 → +$1,000, funded $25k→$26k). The +26 closes = paper_stop +21 (−$713.90) + paper_trail +5 (−$21.29, net-NEGATIVE) + paper_max_hold +0. Options (SELL) closed 726 → **731 (+5)**, net −$426.38 → **−$422.33 (+$4.05)** — **first net-POSITIVE options batch in the recent stretch** (all 5 closes were sell_take_profit wins).
- **Per-lane futures (n=1,421):** FUT_MOMENTUM_CONF 603/14.4%/**−$11,174.46**/67.5×/4.9m; FUT_DONCHIAN_100X 168/16.7%/−$5,527.84/100×/2.3m; FUT_DONCHIAN_CONF 160/23.8%/−$3,319.08/56.6×/5.5m; FUT_DONCHIAN_50X 159/22.0%/−$2,843.14/50×/4.8m; FUT_EMA_CONF 331/33.5%/−$2,785.83/29.8×/10.2m. **MOMENTUM_CONF = 43.6% of loss; + DONCHIAN_100X = −$16,702.30 = 65.1%** (shape unchanged). Least-bad EMA_CONF (33.5% win, lowest lev 29.8×, longest hold 10.2m).
- **Exit cohorts (futures, n=1,421):** `paper_stop` **796/0%/−$28,913.22 @ +1.47% avg peak = 112.7% of total loss** (+21 since 17:39). Profit cohort `paper_trail` +$1,560.94 (536/51.1%/+16.05%) + `paper_max_hold` +$2,440.85 (28/85.7%/+48.94%) = **+$4,001.79**. Plus ema21_lost −$403.22 (33), ema21_reclaimed −$290.27 (25), donchian_mid_revert −$45.43 (3) — all frozen. Exits work, entries are the whole problem.
- **Options (SELL, n=731, all 5 lanes red):** OPT_SELL_PUT_FAR 173/6.4%/−$100.11/$0.594; OPT_SELL_CALL 148/14.9%/−$96.53/$0.594; OPT_SELL_PUT 180/12.8%/−$95.18/$0.594; OPT_SELL_NEUTRAL 155/14.8%/−$73.36/$0.589; OPT_SELL_CALL_FAR 75/13.3%/−$57.15/$0.613. Per-trade −$422.33/731 = −$0.578 ≈ avg fee ~$0.59 = still fee-bound overall. Exits: sell_take_profit 501/17.8%/−$105.38, sell_stop 157/0%/−$236.72, **sell_breached 73/0%/−$80.24 = 10.0% of closes (frozen)**. The +5 closes = sell_take_profit +5 (+$4.05); sell_stop & sell_breached unchanged.
- **The new thing:** (1) **Burn cadence ACCELERATED 3h → 2h** — #21 07:39 / #22 10:39 / #23 13:39 / #24 16:39 were all clean 3h apart; **#25 came at 18:39, only 2h after #24**, and futures was actually NEGATIVE (−$650) pre-refill. The three heavy hours (−$605/−$769/−$735) are eating bankroll faster than the prior rhythm, so refills are pulling forward. (2) **Options booked its first net-positive hour in the stretch** — +5 closes, all sell_take_profit, +$4.05; theta harvested cleanly while the up-move stayed orderly (contrast the 17:39 hour where TRENDING_UP stopped sold CALLs for −$3.37/trade). Single small batch, not a trend — cumulative still fee-bound. (3) **`paper_trail` net-negative AGAIN** (+5 trails, −$21.29) — 2nd straight hour trails gave back rather than booked. (4) **`paper_max_hold` FROZEN at 28** (3rd+ hour, no new winner) — runner-clipping add stalled. (5) **Bleed is sustained, not mean-reverting** — 3 heavy hours running with identical structural decomposition; velocity of the same bad-entry mechanism.
- **What we should change (unchanged):** (1) Futures: attack ENTRIES not exits — pullback/retest before breakout + **cap leverage ≤10×**; **kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (65.1% of loss)**; keep EMA_CONF as template. (2) Options: fix fee-on-notional model + move to defined-risk spreads. (3) Ops: orphan opens back at fut 20 / opt 54 (oldest 06-06, avg 25–55h) — durable sweep still not done. (Did NOT refill / change anything — append-only scope; burn #25 was the engine's own auto-refill.)
- **Known-bug status (vs 06-06):** (a) option-sell fee-on-notional **STILL PRESENT** (avg fee ~$0.59 ≈ per-trade loss −$0.578). (b) `sell_breached` 15-25m exit **STILL APPEARS FIXED** (frozen at 73, 10.0% of closes, not "nearly all"). (c) futures `paper_max_hold` ~30m cap **NOT the driver** (28, +$2,441 @ +48.94% peak; frozen). `paper_stop`/entries remain the structural killer (112.7% of loss). (d) orphaned-open non-reconciliation **STILL PRESENT** (fut 20 / opt 54, oldest 06-06).
- **Verdict:** #8 (aggressive 25–100× futures) **❌ DEAD** (−$25.7k closed, 25 burns, solvent only via refills; burn cadence now accelerating to 2h). #6 (OTM selling) **⚠️ break-even/dead, fee-bound** (n=731, one +$4 batch ≠ edge, no lane positive). #5 dead. No strategy verdict change without a clean entry-filter + leverage-cap rebuild.

### 2026-06-09 18:39 UTC — check-in, AUTO-REFILL burn #25 fired (futures went insolvent −$650, refilled; #25 came 2h after #24, ahead of the 3h cadence), 3rd straight heavy hour (~−$735), options flat `[updated by: alpha-paper-lab-monitor]`
**44th run. Futures dropped through the $50 floor this hour and was actually NEGATIVE pre-refill: funded $25,000 (1 seed + 24 burns), closed 1,421 / net −$25,650.35 → bal **−$650.35** ≤ $50 → **AUTO-REFILL BURN #25 fired** (paper_deposits id 27, +$1,000, 2026-06-09 18:39:33 UTC) → funded $26,000, bal **$349.65**. Options funded $1,000 (0 burns), closed 731 / net −$422.34 → bal **$577.66** (> $50, no refill). Live OFF confirmed (is_paused=true, bot_state=paused, FRESH 18:36:51 UTC; 0 options_scalp in last hour). Verdict unchanged — same structural story.**
- **What's happening (db now 18:39:27):** `bot_status` FRESH 18:36:51 UTC, is_paused=true, bot_state=paused, pause_reason "PAPER-ONLY mode (no live trading)", **market_regime=TRENDING_UP** (regime_since 18:18:10, ~21 min in; chop 0.679, atr_ratio 1.05, net_change_30m +0.304), live open_positions=0, delta_bal $27.08. Paper-only, no live exposure.
- **What happened since last monitor check (17:39, ~1h):** Futures net −$24,903.28 → **−$25,650.35 (−$747.07)** — **3rd straight heavy hour** (−$605, −$769, now −$747 vs the prior ~$335/hr baseline; bleed is sustained, not reverting). This hour's closes decompose cleanly: **paper_stop +21 (−$713.90)** + **paper_trail +5 (−$21.28, cohort net-NEGATIVE 2nd hour running)** = −$735.18 (residual vs −$747 = the `restart_orphan` cohort, 18 rows, folded/reclassified out of the breakdown this snapshot — see Known-bug d). Options (all SELL) net −$423.30 → **−$422.34 (+$0.96 = noise, lane idle)**. **Burn #25 fired** (bal −$650.35 ≤ $50 → +$1,000).
- **Per-lane futures (n=1,421):** FUT_MOMENTUM_CONF 603/14.4%/**−$11,174.46**/67.5×/4.9m (avg peak +9.02%, max +326.56%); FUT_DONCHIAN_100X 168/16.7%/−$5,527.84/100×/2.3m; FUT_DONCHIAN_CONF 160/23.8%/−$3,319.08/56.6×/5.5m; FUT_DONCHIAN_50X 159/22.0%/−$2,843.14/50×/4.8m; FUT_EMA_CONF 331/33.5%/−$2,785.83/29.8×/10.2m. **MOMENTUM_CONF = 43.6% of loss; + DONCHIAN_100X = −$16,702.30 = 65.1%** (shape unchanged). Least-bad EMA_CONF (33.5% win, lowest lev 29.8×, longest hold 10.2m).
- **Exit cohorts (futures, n=1,421):** `paper_stop` **796/0%/−$28,913.22 @ +1.47% avg peak = 112.7% of total loss** (+21 this hour). Profit cohort `paper_trail` +$1,560.94 (536/51.1%/+16.05% peak) + `paper_max_hold` +$2,440.85 (28/85.7%/+48.94% peak, **frozen at 28 again**) = **+$4,001.79**. Plus ema21_lost −$403.22 (33), ema21_reclaimed −$290.27 (25), donchian_mid_revert −$45.43 (3) — all frozen. Exits work; wrong-direction entries noise-stopped at +1.47% peak are the whole problem.
- **Options (SELL, n=731, all 5 lanes red, idle, fee-bound):** OPT_SELL_PUT_FAR 173/6.4%/−$100.11/31.8m; OPT_SELL_CALL 148/14.9%/−$96.53/28.9m; OPT_SELL_PUT 180/12.8%/−$95.18/30.7m; OPT_SELL_NEUTRAL 155/14.8%/−$73.36/34.0m; OPT_SELL_CALL_FAR 75/13.3%/−$57.15/46.6m. Per-trade −$422.34/731 = −$0.578 ≈ avg fee ~$0.59 → fees ≈ 100% of the loss. No lane with edge.
- **The new thing:** (1) **Burn #25 fired, and futures was genuinely insolvent (−$650.35) before the refill** — the −$747 hour blew clean through the $50 floor. **Cadence broke**: #25 landed 2h after #24 (16:39 → 18:39), ahead of the clean 3h rhythm — three consecutive heavy hours are pulling burns forward, exactly as flagged last run. (2) **`paper_trail` net-negative for the 2nd straight hour** (+5 trails, cohort −$21.28) — trailing exits are giving back, not booking; cohort total slipped $1,582.23 → $1,560.94. (3) **`paper_max_hold` frozen at 28** (3rd+ hour, no new winner — the rare big-runner add has stalled). (4) **`restart_orphan` (18 rows, +$11.89 last run) no longer appears as a distinct exit cohort** — folded/reclassified; net effect on totals negligible but worth noting for reconciliation.
- **What we should change (unchanged):** (1) Futures: attack ENTRIES not exits — pullback/retest before breakout + **cap leverage ≤10×**; **kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (65.1% of loss)**; keep EMA_CONF as the template (least-bad, lowest lev, longest hold). (2) Options: fix fee-on-notional model + move to defined-risk spreads. (3) Ops: durable orphan-open sweep still not done. (Did refill burn #25 — that is in-scope; did NOT change engine/strategy.)
- **Known-bug status (vs 06-06):** (a) option-sell fee-on-notional **STILL PRESENT** (avg fee ~$0.59 ≈ per-trade loss −$0.578). (b) `sell_breached` 15-25m exit **STILL APPEARS FIXED** (not the driver). (c) futures `paper_max_hold` ~30m cap **NOT the driver** (28 trades, +$2,441 @ +49% peak; frozen this hour — clipping rare big winners, not bleeding). (d) **`restart_orphan` cohort vanished from the breakdown** (was 18 rows / +$11.89 last run) — orphan reconciliation/reclassification is moving rows around; track whether the open-orphan pile (was fut 18 / opt 54) is actually being cleared. `paper_stop`/entries remain the structural killer (112.7% of loss).
- **Verdict:** #8 (aggressive 25–100× futures) **❌ DEAD** (−$25.7k closed, **25 burns**, solvent only via refills; went insolvent −$650 this hour). #6 (OTM selling) **⚠️ break-even/dead, fee-bound** (n=731, no lane with edge). #5 dead. No strategy verdict change without a clean entry-filter + leverage-cap rebuild.

### 2026-06-09 17:39 UTC — check-in, NO burn yet but futures near-insolvent ($84.84), heaviest hour of the stretch (−$769), trails turned net-negative, options went directional on TRENDING_UP `[updated by: Cowork]`
**Independent recompute alongside the concurrent 17:39 monitor entry below (reads AGREE on the headline: heaviest hour −$769, no burn yet, futures on the insolvency threshold, burn #25 imminent). DIVERGENCE in counts as before: my futures closed=1,395/net −$24,915.16/bal $84.84 vs monitor's 1,413/−$24,903.28/$96.72 (snapshot a few min/closes apart); my options is SELL-filtered closed=726/net −$426.38 vs monitor's all-options 780/−$423.30. db now 17:39:50 UTC. Futures funded $25,000 (1 seed + 24 burns, NO new burn — #24 still 16:39:11). Options funded $1,000 (0 burns), bal ~$573.62. Live OFF (is_paused=true, paused, FRESH 17:38:52 UTC). Regime **TRENDING_UP** (regime_since 16:43:34, held ~1h, no round-trip; chop 0.607, atr 1.0, net_change_30m +0.381). Verdict unchanged.**
- **What's happening:** `bot_status` FRESH 17:38:52, paused, "PAPER-ONLY mode", market_regime=TRENDING_UP, delta_bal $27.08, live open_positions=0. Open paper: **futures 18, options 54** (orphans persisting — oldest fut 06-06 17:31, oldest opt 06-06 17:35; newest opt 17:20 = lane active atop stale book).
- **What happened since last Cowork check (16:40, ~59 min):** Futures closed 1,367 → **1,395 (+28)**, net −$24,146.13 → **−$24,915.16 (−$769.03)** — heaviest hour of the stretch (vs −$605 prior, ~$335/hr baseline; 2nd straight accelerating hour). Options (SELL) closed 719 → **726 (+7)**, net −$402.76 → **−$426.38 (−$23.62 = −$3.37/trade, ABOVE the ~$0.59 fee → directional)**. **No new burn** (bal $84.84 > $50, but ~3 min from ≤$50). The +28 futures closes = paper_stop +18 (−$690.38) + paper_trail +10 (cohort −$78.65, net-NEGATIVE) + paper_max_hold +0.
- **Per-lane futures (n=1,395):** FUT_MOMENTUM_CONF 588/14.8%/**−$10,729.18**/67.6×/5.0m; FUT_DONCHIAN_100X 166/16.9%/−$5,427.84/100×/2.3m; FUT_DONCHIAN_CONF 158/24.1%/−$3,239.44/56.5×/5.5m; FUT_DONCHIAN_50X 157/22.3%/−$2,771.73/50×/4.9m; FUT_EMA_CONF 326/33.4%/−$2,746.97/29.8×/10.2m. **MOMENTUM_CONF = 43.1% of loss; + DONCHIAN_100X = −$16,157.02 = 64.8%** (shape unchanged). Least-bad EMA_CONF (33.4% win, lowest lev 29.8×, longest hold 10.2m).
- **Exit cohorts (futures, n=1,395):** `paper_stop` **775/0%/−$28,199.32 @ +1.50% avg peak = 113.2% of total loss** (+18 since 16:40). Profit cohort `paper_trail` +$1,582.23 (531/51.2%/+16.08%) + `paper_max_hold` +$2,440.85 (28/85.7%/+48.94%) = **+$4,023.08**. Plus ema21_lost −$403.22 (33), ema21_reclaimed −$290.27 (25), donchian_mid_revert −$45.43 (3) — all frozen. Exits work, entries are the whole problem.
- **Options (SELL, n=726, all 5 lanes red):** OPT_SELL_PUT_FAR 171/5.8%/−$100.49/$0.587; OPT_SELL_PUT 178/12.4%/−$97.06/$0.587; OPT_SELL_CALL 148/14.9%/−$96.53/$0.594; OPT_SELL_NEUTRAL 154/14.3%/−$75.15/$0.585; OPT_SELL_CALL_FAR 75/13.3%/−$57.15/$0.613. Cumulative −$426.38/726 = −$0.587 ≈ avg fee = fee-bound overall. Exits: sell_take_profit 496/−$109.43, sell_stop 157/0%/−$236.72, **sell_breached 73/0%/−$80.24 = 10.1% of closes**. The +7 closes = sell_stop +4 (−$16.15), sell_breached +1 (−$8.43), sell_take_profit +2 (+$0.95).
- **The new thing:** (1) **Futures near-insolvent without a burn** — bal $84.84 after the −$769 hour; ~3 min from ≤$50, so burn #25 is imminent and will likely fire OFF the clean 3h cadence (early; #24 was 16:39). (2) **`paper_trail` turned net-negative for the hour** — +10 trails but cohort dropped −$78.65; trailing exits gave back rather than booked, first time trails were a net drag in the recent stretch. (3) **`paper_max_hold` FROZEN at 28** — no new winner after several +1 hours; runner-clipping add paused. (4) **Options went directional on the up-move** — −$3.37/trade (4× sell_stop), CALL (+2/−$13.71) and CALL_FAR (+4/−$11.82) took the hits while PUT/PUT_FAR sat idle. Mirror of the 14:39 TRENDING_DOWN hour that stopped sold puts: the side facing the trending move gets stopped. Regime move, not theta. (5) **Regime TRENDING_UP held ~1h** (no round-trip this snapshot).
- **What we should change (unchanged):** (1) Futures: attack ENTRIES not exits — pullback/retest before breakout + **cap leverage ≤10×**; **kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (64.8% of loss)**; keep EMA_CONF as template. (2) Options: fix fee-on-notional model + move to defined-risk spreads. (3) Ops: orphan opens back to fut 18 / opt 54 (oldest 06-06) — durable sweep still not done. (Did NOT refill / change anything — append-only scope.)
- **Known-bug status (vs 06-06):** (a) option-sell fee-on-notional **STILL PRESENT** (avg fee ~$0.59 ≈ cumulative per-trade −$0.587). (b) `sell_breached` 15-25m exit **STILL APPEARS FIXED** (73, 10.1% of closes, not "nearly all"). (c) futures `paper_max_hold` ~30m cap **NOT the driver** (28, +$2,441 @ +48.94% peak; frozen this hour). `paper_stop`/entries remain the structural killer (113.2% of loss). (d) orphaned-open non-reconciliation **STILL PRESENT** (fut 18 / opt 54, oldest 06-06).
- **Verdict:** #8 (aggressive 25–100× futures) **❌ DEAD** (−$24.9k closed, 24 burns, solvent only via refills; bal $84.84, burn #25 imminent). #6 (OTM selling) **⚠️ break-even/dead, fee-bound** (n=726, no lane with edge). #5 dead. No strategy verdict change without a clean entry-filter + leverage-cap rebuild.

### 2026-06-09 17:39 UTC — check-in, NO burn yet but futures bled to ~$97 (2nd heavy hour running, burn #25 imminent), options idle `[updated by: alpha-paper-lab-monitor]`
**43rd run. No refill fired this hour but both labs still solvent on the threshold: futures funded $25,000 (1 seed + 24 burns), closed 1,413 / net −$24,903.28 → bal **$96.72** (> $50, no auto-refill — but a −$769 hour dropped it from ~$904 last hour, so burn #25 is imminent, likely within the next hour). Options funded $1,000 (0 burns), closed 780 / net −$423.30 → bal **$576.70**. Live OFF confirmed (is_paused=true, bot_state=paused, FRESH 17:38:52 UTC; 0 options_scalp in last hour). Verdict unchanged — same structural story.**
- **What's happening (db now ~17:39):** `bot_status` FRESH 17:38:52 UTC, is_paused=true, bot_state=paused (PAPER-ONLY mode). Paper-only, no live exposure.
- **What happened since last check (~1h):** Futures closed +28, **−$769.03** (heavy red again; bal ~$904 → **$96.72**). Options closed +8, **−$24.45** (lane ~idle). **Two consecutive heavy hours** (−$605 then −$769) vs the prior ~$335/hr baseline — tape chewing high-lev entries faster; bleed is accelerating, not reverting.
- **Per-lane futures (n=1,413):** FUT_MOMENTUM_CONF 593/15.0%/**−$10,716.13**/67.5×/5.0m; FUT_DONCHIAN_100X 168/16.7%/−$5,427.84/100×/2.3m; FUT_DONCHIAN_CONF 160/24.4%/−$3,237.28/56.4×/5.5m; FUT_DONCHIAN_50X 159/22.0%/−$2,771.73/50×/4.8m; FUT_EMA_CONF 333/33.3%/−$2,750.30/29.7×/15.8m. **MOMENTUM_CONF = 43.0% of loss; + DONCHIAN_100X = −$16,143.97 = 64.8%** (shape unchanged). Least-bad EMA_CONF (33.3% win, lowest lev 29.7×, longest hold 15.8m).
- **Exit cohorts (futures, n=1,413):** `paper_stop` **775/0%/−$28,199.32 @ +1.50% avg peak / −8.40% real = 113.2% of total loss**. Profit cohort `paper_trail` +$1,582.23 (531/+16.08% peak/+7.23% real) + `paper_max_hold` +$2,440.85 (28/+48.94% peak/+40.58% real) = **+$4,023.08**. Plus ema21_lost −$403.22 (33), ema21_reclaimed −$290.27 (25), restart_orphan +$11.89 (18), donchian_mid_revert −$45.43 (3). Exits work; wrong-direction entries noise-stopped at +1.5% peak are the whole problem.
- **Options (SELL, n=780, all 5 lanes red, ~idle, fee-bound):** OPT_SELL_PUT_FAR 179/6.7%/−$100.27/$0.587; OPT_SELL_PUT 186/12.4%/−$97.46/$0.587; OPT_SELL_CALL 160/19.4%/−$92.40/$0.594; OPT_SELL_NEUTRAL 166/15.7%/−$76.99/$0.585; OPT_SELL_CALL_FAR 89/19.1%/−$55.38/$0.613. Per-trade −$423.30/780 = −$0.54 ≈ avg fee ~$0.59 → fees ≈ 100% of the loss.
- **The new thing:** (1) **No burn this hour, but futures sit at $96.72** — second straight heavy hour (−$769 after −$605) means burn #25 is pulling *forward* of the clean 3h cadence (#24 was 16:39; cadence would say ~19:39, but at this rate the $50 floor breaks sooner). (2) **`paper_max_hold` frozen at 28** (no new winner this hour, cohort still +48.94% peak). (3) Loss is accelerating above baseline while the structural decomposition is identical — it's volume/velocity of the same bad-entry mechanism, not a new failure mode.
- **What we should change (unchanged):** (1) Futures: attack ENTRIES not exits — pullback/retest before breakout + **cap leverage ≤10×**; **kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (64.8% of loss)**; keep EMA_CONF as the template (least-bad, lowest lev, longest hold). (2) Options: fix fee-on-notional model + move to defined-risk spreads. (Append-only scope: did NOT refill or change engine — both labs above the $50 floor.)
- **Known-bug status (vs 06-06):** (a) option-sell fee-on-notional **STILL PRESENT** (avg fee ~$0.59 ≈ per-trade loss −$0.54). (b) `sell_breached` 15-25m exit **STILL APPEARS FIXED** (not the driver). (c) futures `paper_max_hold` ~30m cap **NOT the driver** (28 trades, +$2,441 @ +49% peak — likely clipping rare big winners, not bleeding). `paper_stop`/entries remain the structural killer (113.2% of loss).
- **Verdict:** #8 (aggressive 25–100× futures) **❌ DEAD** (−$24.9k closed, 24 burns, solvent only via refills, #25 imminent). #6 (OTM selling) **⚠️ break-even/dead, fee-bound** (n=780, no lane with edge). #5 dead. No strategy verdict change without a clean entry-filter + leverage-cap rebuild.

### 2026-06-09 16:40 UTC — check-in, AUTO-REFILL burn #24 fired (3h cadence held as predicted), heaviest futures hour in the stretch, options SELL ~idle `[updated by: Cowork]`
**Independent recompute ~1 min after the concurrent 16:39 monitor entry below. Reads AGREE on the headline: burn #24 fired ~16:39 on the predicted 3h cadence, futures had a heavy red hour, `paper_max_hold` ticked to its 28th winner (+$11.49). Two DIVERGENCES worth flagging: (1) regime — I read **TRENDING_DOWN** (regime_since 16:38:45, FRESH 16:38:53) vs the monitor's TRENDING_UP, so the regime round-tripped within the same ~1–2 min window. (2) options closes — my SELL-filtered query shows only **+1 close** (718→719, −$0.82, lane ~idle) vs the monitor's "+52 closes"; the gap is almost certainly a filter/scope difference (monitor likely counting opens or non-SELL rows), since SELL-lane closed count moved only by 1. Clean ~1h interval since the 15:39 Cowork run. Futures funded $24,000 → **$25,000** (1 seed + 24 burns) after BURN #24 (paper_deposits id 26, +$1,000, 16:39:11 UTC), closed 1,367 / net −$24,146.13, bal ~$853.87. Options funded $1,000 (0 burns), closed 719 / net −$402.76, bal ~$597.24. Live OFF. Verdict unchanged.**
- **What's happening (db now 16:40:19):** `bot_status` FRESH 16:38:53 UTC, is_paused=true, bot_state=paused, pause_reason "PAPER-ONLY mode (no live trading)", **market_regime=TRENDING_DOWN** (regime_since 16:38:45), chop 0.643, atr_ratio 1.15, net_change_30m −0.455, live open_positions=0. Paper-only. Open paper: futures 2, options 4 (CALL 2 / CALL_FAR 2) — small open book, no orphan pile-up this snapshot.
- **What happened since last Cowork check (15:39, ~61 min):** Futures closed 1,333 → **1,367 (+34)**, net −$23,540.89 → **−$24,146.13 (−$605.24)**. Options (SELL) closed 718 → **719 (+1)**, net −$401.94 → **−$402.76 (−$0.82)**. **BURN #24 fired 16:39:11** (bal dipped ≤ $50 → +$1,000, funded $24k→$25k). The +34 futures closes decompose exactly: paper_stop +20 (−$728.26) + paper_trail +13 (+$111.53) + paper_max_hold +1 (+$11.49) = −$605.24. Stop-driven hour, not a fee hour.
- **Per-lane futures (n=1,367):** FUT_MOMENTUM_CONF 577/14.6%/**−$10,578.90**/67.5×/5.0m; FUT_DONCHIAN_100X 162/17.3%/−$5,239.16/100×/2.3m; FUT_DONCHIAN_CONF 154/24.7%/−$3,060.11/56.3×/5.6m; FUT_EMA_CONF 321/33.6%/−$2,636.03/29.6×/10.3m; FUT_DONCHIAN_50X 153/22.9%/−$2,631.93/50×/5.0m. **MOMENTUM_CONF = 43.8% of loss; + DONCHIAN_100X = −$15,818.06 = 65.5%** (shape unchanged). Least-bad EMA_CONF (33.6% win, lowest lev 29.6×, longest hold 10.3m).
- **Exit cohorts (futures, n=1,367):** `paper_stop` **757/0%/−$27,508.94 @ +1.52% avg peak = 113.9% of total loss** (+20 since 15:39). Profit cohort `paper_trail` +$1,660.88 (521/51.4%/+16.09%) + `paper_max_hold` +$2,440.85 (28/85.7%/+48.94%) = **+$4,101.73**. Plus ema21_lost −$403.22 (33), ema21_reclaimed −$290.27 (25), donchian_mid_revert −$45.43 (3). Exits work, entries are the whole problem.
- **Options (SELL, n=719, all 5 lanes red, ~idle):** OPT_SELL_PUT_FAR 171/5.8%/−$100.49/$0.587; OPT_SELL_PUT 178/12.4%/−$97.06/$0.587; OPT_SELL_CALL 146/15.1%/−$82.82/$0.586; OPT_SELL_NEUTRAL 153/13.7%/−$77.06/$0.582; OPT_SELL_CALL_FAR 71/14.1%/−$45.33/$0.581 (the lone +1 close, −$0.83). Per-trade −$402.76/719 = −$0.56 ≈ avg fee $0.58 = fee-bound. Exits: sell_take_profit 494/−$110.38, sell_stop 153/0%/−$220.57, **sell_breached 72/0%/−$71.81 = 10.0% of closes (frozen).**
- **The new thing:** (1) **Burn #24 fired exactly on the predicted 3h cadence** (#21 07:39 / #22 10:39 / #23 13:39 / #24 16:39); 15:39 flagged ~16:50–17:10, actual 16:39 — refill rhythm is reliable and pinned to the futures bleed. (2) **Heaviest futures hour in the recent stretch** — −$605.24 vs the ~$335/hr prior baseline, almost entirely +20 `paper_stop` hits; tape chewing through high-lev entries faster. (3) **Options/regime read drift vs the concurrent monitor** — flagged above; my SELL-closed delta is +1 (idle), regime TRENDING_DOWN. Worth a closer look at whether the monitor's "+52" is opens vs closes, to keep the two agents' options accounting consistent. (4) **`paper_max_hold` 28th winner** (+$11.49, cohort +48.94% avg peak) — runner-clipping signal still paying.
- **What we should change (unchanged):** (1) Futures: attack ENTRIES not exits — pullback/retest before breakout + **cap leverage ≤10×**; **kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (65.5% of loss)**; keep EMA_CONF as template. (2) Options: fix fee-on-notional model + move to defined-risk spreads. (3) Reconcile the Cowork-vs-monitor options-close count (+1 vs +52) so both lanes report the same basis. (Did NOT refill / change anything — append-only scope; burn #24 was the engine's own auto-refill.)
- **Known-bug status (vs 06-06):** (a) option-sell fee-on-notional **STILL PRESENT** (avg fee ~$0.58 ≈ per-trade loss −$0.56). (b) `sell_breached` 15-25m exit **STILL APPEARS FIXED** (frozen at 72, 10.0% of closes, not "nearly all"). (c) futures `paper_max_hold` ~30m cap **NOT the driver** (28 trades, +$2,441 @ +49% peak; lanes hold 2.3–10.3m — likely clipping rare big winners). `paper_stop`/entries remain the structural killer (113.9% of loss). (d) no orphan pile-up this snapshot (fut 2 / opt 4 open).
- **Verdict:** #8 (aggressive 25–100× futures) **❌ DEAD** (−$24.1k closed, 24 burns, solvent only via refills). #6 (OTM selling) **⚠️ break-even/dead, fee-bound** (n=719, no lane with edge). #5 dead. No strategy verdict change without a clean entry-filter + leverage-cap rebuild.

### 2026-06-09 16:39 UTC — check-in, AUTO-REFILL burn #24 fired (3h cadence intact), heavier red futures hour, options lane woke up `[updated by: monitor]`
**42nd monitor run. Burn #24 fired exactly on the 3h cadence (#21/#22/#23/#24 all ~3h apart; #23 was 13:39, #24 at 16:39 — landed where 15:39's "next ~17:00" prediction pointed). Futures bled −$552 this hour (46 closes / 15 wins) from bal ~$457 to −$95.59 (≤$50) → auto-funded $1,000 (24th refill), bal now $904.41. Heavier than the prior ~−$337/hr quiet hours. Options lane WOKE UP again (+52 closes / −$7.04 → bal $591.02) after an idle hour — confirms the intermittent burst pattern. `paper_max_hold` ticked to its 28th winner (+$11.49). Same structural story, 42nd confirmation: `paper_stop` = the entire loss; exits work, entries are the whole problem. Live OFF (is_paused=true, bot_state paused FRESH 16:36 UTC, regime flipped TRENDING_UP, 0 scalp/0 options_scalp last hr). Verdict unchanged.**
- **What's happening (db now 16:39):** `bot_status` FRESH 16:36:53 UTC, is_paused=true, bot_state=paused, pause_reason "PAPER-ONLY mode", **market_regime=TRENDING_UP** (regime_since 16:33:09, flipped from TRENDING_DOWN; chop 0.679, atr_ratio 1.05, net_change_30m +0.499), capital/delta_bal $27.08, live open_positions=0, **0 options_scalp trades in last hour**. Paper-only confirmed.
- **Balances:** Futures funded **$25,000** (1 seed + 24 burns), net −$24,095.59, pre-refill bal **−$95.59 (≤$50 → AUTO-REFILL burn #24, +$1,000)**, post-refill **bal $904.41**. Options funded $1,000 (0 burns), net −$408.98, **bal $591.02** (>$50, no refill).
- **This hour (~60 min):** Futures −$552.48 / 46 closes / 15 wins (33%) — heavier than the prior two ~−$337 hours, which tipped bal negative and triggered the burn. Options **+52 closes / −$7.04** (lane woke from last hour's idle; net −$401.94 → −$408.98).
- **Per-lane futures (n=1,385):** FUT_MOMENTUM_CONF 582/14.8%/**−$10,565.85**/max-peak 326.6%; FUT_DONCHIAN_100X 164/17.1%/−$5,239.16; FUT_DONCHIAN_CONF 156/25.0%/−$3,057.95; FUT_EMA_CONF 328/33.5%/−$2,639.36; FUT_DONCHIAN_50X 155/22.6%/−$2,631.93. **MOMENTUM_CONF = 43.8% of loss; + DONCHIAN_100X = −$15,805.01 = 65.6%** (shape unchanged). Least-bad EMA_CONF (33.5% win, highest win-rate, lowest lev) — keep as template.
- **Exit cohorts (futures, n=1,385):** `paper_stop` **757/0%/−$27,508.94 @ +1.52% avg peak = 114.2% of total loss** (wrong-direction entries noise-stopped before ever in money; +21 since 15:39). Profit cohort `paper_trail` +$1,660.88 (521/51.4%/+16.09%) + `paper_max_hold` +$2,440.85 (**28**/85.7%/+48.94%) = **+$4,101.73**, plus restart_orphan +$11.89. Bleeders ema21_lost −$403.22 (33), ema21_reclaimed −$290.27 (25), donchian_mid_revert −$45.43 (3). Exits work, entries are the whole problem.
- **Options (n=770, all 5 SELL lanes red, fee-bound):** OPT_SELL_PUT_FAR 177/5.6%/−$101.71; OPT_SELL_PUT 184/12.0%/−$99.45; OPT_SELL_NEUTRAL 163/14.1%/−$79.37; OPT_SELL_CALL 160/20.6%/−$77.15; OPT_SELL_CALL_FAR 86/22.1%/−$41.78. Per-trade −$408.98/770 = −$0.53 ≈ avg fee = still fee-bound (~100% of options loss is fees). This hour's +52 closes only added −$7.04 (some wins offset fees) — but cumulative still fee-capped.
- **The new thing:** (1) **Burn #24 on schedule** — the 3h cadence (#21/#22/#23/#24) held; 15:39's −$337/hr projection of ~17:00 was close (came 16:39 on a heavier −$552 hour). (2) **Options lane intermittent confirmed** — idle hour → +52-close burst, the same on/off pattern seen 14:39→15:39. Not a durable resumption. (3) **`paper_max_hold` 27→28** (+$11.49) — slower add than prior hours but still drifting up; runner-loosening signal persists. (4) **Regime flipped TRENDING_DOWN→TRENDING_UP** — paper_stop still 114% of loss regardless of regime.
- **Known-bug status (unchanged):** (a) option-sell fee-on-notional **STILL PRESENT** (~$0.53/trade ≈ ~100% of options loss). (b) futures high-lev stop converts +1.52%-peak adverse moves into full liquidations under 50–100× — `paper_stop`/entries remain the structural killer (114.2% of loss). (c) `paper_max_hold` ~30m cap **NOT a leak but likely clipping winners** (28 trades, +$2,441 @ +49% peak).
- **What we should change (unchanged):** (1) Futures: attack ENTRIES not exits — pullback/retest before breakout + **cap leverage ≤10×**; **kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (65.6% of loss)**; keep EMA_CONF as template. (2) Options: fix fee-on-notional model + move to defined-risk spreads. (3) Consider loosening `paper_max_hold` — the 28 trades that reached it avg +49% peak. (Only action taken: auto-refill burn #24 per scope; no code/strategy change.)
- **Verdict:** #8 (aggressive 25–100× futures) **❌ DEAD** (−$24.1k closed, 24 burns, solvent only via refills). #6 (OTM selling) **⚠️ break-even/dead, fee-bound** (n=770, no lane with edge). #5 dead. No strategy verdict change without a clean entry-filter + leverage-cap rebuild.

### 2026-06-09 15:39 UTC — check-in, no burn (bal ~$459), options lane idle again, orphan opens swept to 3/5, regime re-TRENDING_DOWN `[updated by: Cowork]`
**Independent recompute alongside the concurrent 15:39 monitor entry below (reads agree within drift: my futures net −$23,540.89 / bal ~$459.11 vs monitor's −$336.80-hr / bal $456.89; both catch options idle, both max_hold n→27 +$108.76). Clean ~1h interval since the 14:39 Cowork run. Futures funded $24,000 (1 seed + 23 burns, NO new burn — last deposit #23 still 13:39:22), closed 1,333 / net −$23,540.89, bal ~$459.11 (>$50, no refill). Options funded $1,000 (0 burns), closed 718 / net −$401.94, bal $598.06 — byte-identical to 14:39 = lane fully idle this hour. Live OFF (is_paused=true, bot_state paused, FRESH 15:39:06 UTC). Regime TRENDING_DOWN, regime_since re-stamped 15:28:19 (round-tripped off and back since 14:39's 14:00 stamp). Verdict unchanged.**
- **What's happening (db now 15:39:06):** `bot_status` FRESH 15:39:06 UTC, is_paused=true, bot_state=paused, pause_reason "PAPER-ONLY mode", **market_regime=TRENDING_DOWN** (regime_since 15:28:19), chop 0.429, atr_ratio 1.05, net_change_30m −0.962, capital/delta_bal $27.08, live open_positions=0. Paper-only. Open paper: **futures 3, options 5** (down from 14:39's 12/44 — orphan opens swept again; oldest fut open 06-08 08:10, oldest opt open 06-06 22:10).
- **What happened since last Cowork check (14:39, ~60 min):** Futures closed 1,307 → **1,333 (+26)**, net −$23,206.31 → **−$23,540.89 (−$334.58)**. Options closed 718 → **718 (+0)**, net flat at **−$401.94** — lane dormant again after last hour's +10 wake-up. **No new burn** (futures bal ~$459.11 > $50). The +26 futures closes = 14 paper_stop (−$463.89) + 11 paper_trail (+$20.55) + 1 paper_max_hold (+$108.76); stops drove the hour, trails near-breakeven.
- **Per-lane futures (n=1,333):** FUT_MOMENTUM_CONF 566/14.3%/**−$10,374.42**/67.7×/5.0m; FUT_DONCHIAN_100X 156/17.3%/−$5,050.92/100×/2.4m; FUT_DONCHIAN_CONF 148/24.3%/−$2,938.91/56.4×/5.7m; FUT_EMA_CONF 316/32.9%/−$2,652.00/29.7×/10.3m; FUT_DONCHIAN_50X 147/22.4%/−$2,524.63/50×/5.0m. **MOMENTUM_CONF = 44.1% of loss; + DONCHIAN_100X = −$15,425.34 = 65.5%** (shape unchanged). Least-bad EMA_CONF (32.9% win, lowest lev 29.7×, longest hold 10.3m).
- **Exit cohorts (futures, n=1,333):** `paper_stop` **737/0%/−$26,780.68 @ +1.49% avg peak = 113.8% of total loss** (+14 since 14:39; drift up from 113.4%). Profit cohort `paper_trail` +$1,549.35 (508/50.6%/+16.07%) + `paper_max_hold` +$2,429.36 (27/85.2%/+50.33%) = **+$3,978.71** (+1 max_hold winner, +$108.76). Plus ema21_lost −$403.22 (33), ema21_reclaimed −$290.27 (25), donchian_mid_revert −$45.43 (3). Exits work, entries are the whole problem.
- **Options (n=718, all 5 SELL lanes red, byte-identical to 14:39 = idle):** OPT_SELL_PUT_FAR 171/5.8%/−$100.49/$0.587; OPT_SELL_PUT 178/12.4%/−$97.06/$0.587; OPT_SELL_CALL 146/15.1%/−$82.82/$0.586; OPT_SELL_NEUTRAL 153/13.7%/−$77.06/$0.582; OPT_SELL_CALL_FAR 70/14.3%/−$44.50/$0.572. Per-trade −$401.94/718 = −$0.56 ≈ avg fee $0.58 = fee-bound. Exits: sell_take_profit 493/17.2%/−$109.55, sell_stop 153/0%/−$220.57, **sell_breached 72/0%/−$71.81 = 10.0% of closes.**
- **The new thing:** (1) **Options lane went dormant again** — last hour's +10-close wake-up did not continue; 0 closes, every lane number unchanged to the cent. Lane is intermittent (idle → 10-close burst → idle), not a durable resumption. (2) **Orphan opens swept hard** — open book fut 12→3 / opt 44→5 without closes advancing (opt closed flat at 718), so ~9 futures + ~39 options left the open book via reconciliation, not realization. Same transient-sweep behavior as 12:39 (which then reverted by 13:40); watch whether it holds next interval. (3) **No burn, cadence pressure building** — bal ~$459 bleeding ~$335/hr → burn #24 plausibly ~16:50–17:10 (would break the clean 3h #21/#22/#23 spacing slightly early). (4) **Regime round-tripped** — TRENDING_DOWN re-stamped 15:28 after the 14:00 stamp; paper_stop still 113.8% of loss regardless of regime.
- **What we should change (unchanged):** (1) Futures: attack ENTRIES not exits — pullback/retest before breakout + **cap leverage ≤10×**; **kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (65.5% of loss)**; keep EMA_CONF as template. (2) Options: fix fee-on-notional model + move to defined-risk spreads. (3) Ops: orphan sweep appears to have run again (3/5 opens) — confirm it holds rather than reverting like 12:39→13:40. (Did NOT refill / change anything — append-only scope.)
- **Known-bug status (vs 06-06):** (a) option-sell fee-on-notional **STILL PRESENT** (avg fee ~$0.58 ≈ per-trade loss −$0.56; lane idle this hour so purely fee-bound). (b) `sell_breached` 15-25m exit **STILL APPEARS FIXED** (frozen at 72, 10.0% of closes, not "nearly all"). (c) futures `paper_max_hold` ~30m cap **NOT the driver** (27 trades, +$2,429 @ +50% peak; lanes hold 2.4–10.3m — likely clipping rare big winners, not leaking). `paper_stop`/entries remain the structural killer (113.8% of loss). (d) orphaned-open non-reconciliation **PARTIALLY RESOLVED this snapshot** (opens 12/44→3/5; durability unconfirmed given the 12:39→13:40 revert).
- **Verdict:** #8 (aggressive 25–100× futures) **❌ DEAD** (−$23.5k closed, 23 burns, solvent only via refills). #6 (OTM selling) **⚠️ break-even/dead, fee-bound** (n=718, no lane with edge). #5 dead. No strategy verdict change without a clean entry-filter + leverage-cap rebuild.

### 2026-06-09 15:39 UTC — check-in, quiet red futures hour (no burn), options lane idle again, max_hold +1 winner `[updated by: monitor]`
**41st monitor run. No new burn — futures bled −$336.80 (24 closes / 6 wins) to bal $456.89 (>$50), #23 (13:39) still the last refill. Balance is getting thin: at ~$337/hr bleed, futures is ~1.3h from insolvency → next burn ~17:00 UTC if the rate holds. Options went idle again (0 closes) after last hour's brief +10 burst, bal unchanged $598.06. `paper_max_hold` picked up another winner (n 26→27, +$108.76) — the runner-loosening signal paying out a third hour running. Same structural story, 41st confirmation: `paper_stop` cohort = the entire loss; exits work, entries are the whole problem. Live OFF (is_paused=true, bot_state paused FRESH 15:37 UTC, regime TRENDING_DOWN, 0 scalp/hr). Verdict unchanged.**
- **What's happening (db now 15:39):** `bot_status` FRESH 15:37:05 UTC, is_paused=true, bot_state=paused, pause_reason "PAPER-ONLY mode", **market_regime=TRENDING_DOWN**, live open_positions=0, **0 options_scalp trades in last hour**. Paper-only confirmed.
- **Balances:** Futures funded $24,000 (1 seed + 23 burns), net −$23,543.11, **bal $456.89** (>$50, no refill — but thinning). Options funded $1,000 (0 burns), net −$401.94, **bal $598.06** (>$50, no refill).
- **This hour (60 min):** Futures −$336.80 / 24 closes / 6 wins (25%). Options 0 closes (idle again after last hour's +10 burst; lane remains intermittent).
- **Per-lane futures (n=1,331):** FUT_MOMENTUM_CONF 565/14%/**−$10,354.25**/5.0m; FUT_DONCHIAN_100X 156/17%/−$5,050.92/2.4m; FUT_DONCHIAN_CONF 148/24%/−$2,938.91/5.7m; FUT_EMA_CONF 315/33%/−$2,674.39/10.3m; FUT_DONCHIAN_50X 147/22%/−$2,524.63/5.0m. **MOMENTUM_CONF = 44.0% of loss; + DONCHIAN_100X = −$15,405.17 = 65.4%** (shape unchanged). Least-bad EMA_CONF (33% win, lowest lev, longest hold 10.3m).
- **Exit cohorts (futures, n=1,331):** `paper_stop` **736/0%/−$26,760.51 @ +1.49% avg peak = 113.7% of total loss** (wrong-direction entries noise-stopped before ever in money; +13 since 14:39). Profit cohort `paper_trail` +$1,526.96 (507/50%/+16.06%) + `paper_max_hold` +$2,429.36 (**27**/85%/+50.33%) = **+$3,956.32**. Plus ema21_lost −$403.22 (33), ema21_reclaimed −$290.27 (25), donchian_mid_revert −$45.43 (3). Exits work, entries are the whole problem.
- **Options (n=718, all 5 SELL lanes red, fee-bound):** OPT_SELL_PUT_FAR 171/6%/−$100.49/−$0.588; OPT_SELL_PUT 178/12%/−$97.06/−$0.545; OPT_SELL_CALL 146/15%/−$82.82/−$0.567; OPT_SELL_NEUTRAL 153/14%/−$77.06/−$0.504; OPT_SELL_CALL_FAR 70/14%/−$44.50/−$0.636. Per-trade −$401.94/718 = −$0.56 ≈ fee = still fee-bound (~100% of options loss is fees).
- **The new thing:** (1) **`paper_max_hold` gained its 27th trade (+$108.76)** — third consecutive hour adding a runner that reached the ~30m cap mid-profit (cohort now +50.33% avg peak, up from +49.23%); reinforces the standing suggestion to loosen the max-hold cap so rare big winners aren't clipped. (2) **Options idle again** — 0 closes after last hour's +10; the lane closes in bursts, not steadily. (3) **No burn but thinning** — futures bal $456.89; #23 (13:39) still last refill, next ~17:00 UTC if −$337/hr holds.
- **Known-bug status (unchanged):** (a) option-sell fee-on-notional **STILL PRESENT** (~$0.56/trade ≈ ~100% of options loss). (b) futures high-lev stop converts +1.49%-peak adverse moves into full liquidations under 50–100× — `paper_stop`/entries remain the structural killer (113.7% of loss). (c) `paper_max_hold` ~30m cap **NOT a leak but likely clipping winners** (27 trades, +$2,429 @ +50% peak).
- **What we should change (unchanged):** (1) Futures: attack ENTRIES not exits — pullback/retest before breakout + **cap leverage ≤10×**; **kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (65.4% of loss)**; keep EMA_CONF as template. (2) Options: fix fee-on-notional model + move to defined-risk spreads. (3) Consider loosening `paper_max_hold` — the 27 trades that reached it avg +50% peak. (Did NOT refill / change anything — append-only scope; no lab ≤ $50.)
- **Verdict:** #8 (aggressive 25–100× futures) **❌ DEAD** (−$23.5k closed, 23 burns, solvent only via refills). #6 (OTM selling) **⚠️ break-even/dead, fee-bound** (n=718, no lane with edge). #5 dead. No strategy verdict change without a clean entry-filter + leverage-cap rebuild.

### 2026-06-09 14:39 UTC — check-in, no burn (3h cadence intact), options lane woke up, regime flipped to TRENDING_DOWN `[updated by: Cowork]`
**Corroborates the concurrent 14:39 monitor entry below (ran within the same minute; reads agree within drift — my futures 1,307 closed / −$23,206.31 vs monitor's −$210.52/40-close hour; both bal $793.69, both catch options +10 / −$21.8 and paper_max_hold n→26). Clean ~1h interval since the 13:40 Cowork run. Futures funded $24,000 (1 seed + 23 burns, NO new burn — last deposit #23 at 13:39:22), closed 1,307 / net −$23,206.31, bal $793.69 (>$50, no refill). Options funded $1,000 (0 burns), closed 718 / net −$401.94, bal $598.06. Live OFF (is_paused=true, bot_state paused, FRESH 14:39:06 UTC). Regime flipped CHOPPY→TRENDING_DOWN (regime_since 14:00:30) on a sharp down leg (net_change_30m −1.213, chop 0.429). Verdict unchanged.**
- **What's happening (db now 14:39:52):** `bot_status` FRESH 14:39:06 UTC, is_paused=true, bot_state=paused, pause_reason "PAPER-ONLY mode", **market_regime=TRENDING_DOWN** (regime_since 14:00:30, flipped from CHOPPY), chop 0.429, atr_ratio 1.15, net_change_30m −1.213, capital/delta_bal $27.08, live open_positions=0. Paper-only. Open paper: **futures 12, options 44** (newest futures open 14:40:19 = seconds old, lane actively opening; oldest still the 06-06 orphans).
- **What happened since last Cowork check (13:40, ~59 min):** Futures closed 1,268 → **1,307 (+39)**, net −$22,986.66 → **−$23,206.31 (−$219.65, ~0 wins)**. Options closed 708 → **718 (+10)**, net −$380.15 → **−$401.94 (−$21.79)**. **No new burn** (futures bal $793.69 > $50). Burn cadence #21 07:39 / #22 10:39 / #23 13:39 = clean ~3h spacing → next burn ~16:39 if bleed rate holds. Futures still the bulk of the bleed, but options contributed a real −$21.79 (first material options hour in 4 checks).
- **Per-lane futures (n=1,307):** FUT_MOMENTUM_CONF 553/14.3%/**−$10,236.46**/68.0×/5.0m (crossed −$10.2k); FUT_DONCHIAN_100X 153/17.0%/−$4,947.97/100×/2.4m; FUT_DONCHIAN_CONF 145/24.1%/−$2,882.54/56.6×/5.8m; FUT_EMA_CONF 312/32.7%/−$2,666.89/29.6×/10.3m; FUT_DONCHIAN_50X 144/22.2%/−$2,472.45/50×/5.1m. **MOMENTUM_CONF = 44.1% of loss; + DONCHIAN_100X = −$15,184.43 = 65.4%** (shape unchanged). Least-bad EMA_CONF (32.7% win, lowest lev 29.6×, longest hold 10.3m).
- **Exit cohorts (futures, n=1,307):** `paper_stop` **723/0%/−$26,316.79 @ +1.49% avg peak = 113.4% of total loss** (+19 since 13:40; drift up from 111.3%). Profit cohort `paper_trail` +$1,528.80 (497/50.5%/+16.10%) + `paper_max_hold` +$2,320.60 (26/84.6%/+49.23%) = **+$3,849.40**. Plus ema21_lost −$403.22 (33), ema21_reclaimed −$290.27 (25), donchian_mid_revert −$45.43 (3). Exits work, entries are the whole problem.
- **Options (n=718, all 5 SELL lanes red):** OPT_SELL_PUT_FAR 171/5.8%/−$100.49/$0.587 (crossed −$100); OPT_SELL_PUT 178/12.4%/−$97.06/$0.587; OPT_SELL_CALL 146/15.1%/−$82.82/$0.586; OPT_SELL_NEUTRAL 153/13.7%/−$77.06/$0.582; OPT_SELL_CALL_FAR 70/14.3%/−$44.50/$0.572. Cumulative per-trade −$401.94/718 = −$0.56 ≈ avg fee $0.58 = still fee-bound overall. Exits: sell_take_profit 493/17.2%/−$109.55, sell_stop 153/0%/−$220.57, **sell_breached 72/0%/−$71.81 = 10.0% of closes.**
- **The new thing:** (1) **Options lane woke up** — +10 closes after 3 near-idle hours (prior hours +1/+0/+1). Breakdown of the 10: sell_stop +6 (147→153), sell_take_profit +4 (489→493), **sell_breached +0 (frozen at 72)**. The −$21.79 = −$2.18/trade is ABOVE the ~$0.58 fee baseline — this hour's options loss was driven by 6 directional `sell_stop` hits, not pure theta/fee drag. First non-fee-dominated options hour in the recent stretch, and it lines up with the regime flip to TRENDING_DOWN (a real down move stopping out sold puts). (2) **No burn, 3h cadence intact** (#21/#22/#23 at 07:39/10:39/13:39); next ~16:39. (3) **Futures lane confirmed actively opening** (newest open 14:40:19, seconds old) — open-count fut 12 / opt 44 is fresh-on-top-of-orphans, not frozen.
- **What we should change (unchanged):** (1) Futures: attack ENTRIES not exits — pullback/retest before breakout + **cap leverage ≤10×**; **kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (65.4% of loss)**; keep EMA_CONF as template. (2) Options: fix fee-on-notional model + move to defined-risk spreads. (3) Ops: orphan reconciliation still not done (fut 12 / opt 44, oldest 06-06). (Did NOT refill / change anything — append-only scope.)
- **Known-bug status (vs 06-06):** (a) option-sell fee-on-notional **STILL PRESENT** (avg fee ~$0.58; cumulative per-trade −$0.56 ≈ fee — though THIS hour was stop-driven, not fee-driven). (b) `sell_breached` 15-25m exit **STILL APPEARS FIXED** (frozen at 72, 0 of this hour's 10 closes; 10.0% overall, not "nearly all"). (c) futures `paper_max_hold` ~30m cap **NOT the driver** (26 trades, +$2,321 @ +49% peak; lanes hold 2.4–10.3m). `paper_stop`/entries remain the structural killer (113.4% of loss). (d) orphaned-open non-reconciliation **STILL PRESENT** (fut 12 / opt 44, oldest 06-06 17:31/17:35).
- **Verdict:** #8 (aggressive 25–100× futures) **❌ DEAD** (−$23.2k closed, 23 burns, solvent only via refills). #6 (OTM selling) **⚠️ break-even/dead, fee-bound** (n=718, no lane with edge). #5 dead. No strategy verdict change without a clean entry-filter + leverage-cap rebuild.

### 2026-06-09 14:39 UTC — check-in, quiet red futures hour (no burn), options lane WOKE UP (+10 closes), max_hold +1 winner `[updated by: monitor]`
**40th monitor run. No new burn — futures bled −$210.52 (40 closes) to bal $793.69 (>$50), #23 still the last refill. Two small new things this hour: (1) the options lane finally closed trades again — **+10 closes / −$21.78** after 3 straight near-idle hours (0–1/hr); (2) `paper_max_hold` picked up one more winner (n 25→26, +$110.86), the runner-loosening signal paying out again. Same structural story, 40th confirmation: `paper_stop` cohort = the entire loss; exits work, entries are the whole problem. Live OFF (is_paused=true, bot_state paused FRESH 14:37 UTC, regime TRENDING_DOWN, 0 scalp/hr). Verdict unchanged.**
- **What's happening (db now 14:38):** `bot_status` FRESH 14:37:06 UTC, is_paused=true, bot_state=paused, pause_reason "PAPER-ONLY mode", **market_regime=TRENDING_DOWN**, scalp_enabled/options_scalp_enabled true but **0 options_scalp trades in last hour**, live open_positions=0. Paper-only confirmed.
- **Balances:** Futures funded $24,000 (1 seed + 23 burns), net −$23,206.31, **bal $793.69** (>$50, no refill). Options funded $1,000 (0 burns), net −$401.94, **bal $598.06** (>$50, no refill).
- **This hour (60 min):** Futures −$210.52 / 40 closes. Options −$21.78 / 10 closes (−$2.18/trade — these recent closes ran worse than the −$0.56 lifetime avg; lane active again after 3 idle hours).
- **Per-lane futures (n=1,307):** FUT_MOMENTUM_CONF 553/14%/**−$10,236.46**; FUT_DONCHIAN_100X 153/17%/−$4,947.97; FUT_DONCHIAN_CONF 145/24%/−$2,882.54; FUT_EMA_CONF 312/33%/−$2,666.89; FUT_DONCHIAN_50X 144/22%/−$2,472.45. **MOMENTUM_CONF = 44.1% of loss; + DONCHIAN_100X = −$15,184.43 = 65.4%** (shape unchanged). Least-bad EMA_CONF (33% win, lowest lev, longest hold).
- **Exit cohorts (futures, n=1,307):** `paper_stop` **723/0%/−$26,316.79 @ +1.49% avg peak = 113.4% of total loss** (wrong-direction entries noise-stopped before ever in money; +19 since 13:39). Profit cohort `paper_trail` +$1,528.80 (497/51%/+16.10%) + `paper_max_hold` +$2,320.60 (**26**/85%/+49.23%) = **+$3,849.40**. Plus ema21_lost −$403.22 (33), ema21_reclaimed −$290.27 (25), donchian_mid_revert −$45.43 (3). Exits work, entries are the whole problem.
- **Options (n=718, all 5 SELL lanes red, fee-bound):** OPT_SELL_PUT_FAR 171/6%/−$100.49/−$0.588; OPT_SELL_PUT 178/12%/−$97.06/−$0.545; OPT_SELL_CALL 146/15%/−$82.82/−$0.567; OPT_SELL_NEUTRAL 153/14%/−$77.06/−$0.504; OPT_SELL_CALL_FAR 70/14%/−$44.50/−$0.636. Per-trade −$401.94/718 = −$0.56 ≈ fee = still fee-bound (~100% of options loss is fees).
- **The new thing:** (1) **options lane resumed closing** — +10 closes this hour after 3 hours at 0–1; PnL impact small (−$21.78) but it confirms the lane isn't dead-stuck, just intermittent. (2) **`paper_max_hold` gained its 26th trade (+$110.86)** — another runner that reached the ~30m cap mid-profit (cohort still +49% avg peak); reinforces the standing suggestion to loosen the max-hold cap so rare big winners aren't clipped.
- **Known-bug status (unchanged):** (a) option-sell fee-on-notional **STILL PRESENT** (~$0.56/trade ≈ ~100% of options loss). (b) futures high-lev stop converts +1.49%-peak adverse moves into full liquidations under 50–100× — `paper_stop`/entries remain the structural killer (113% of loss). (c) `paper_max_hold` ~30m cap **NOT a leak but likely clipping winners** (26 trades, +$2,321 @ +49% peak).
- **What we should change (unchanged):** (1) Futures: attack ENTRIES not exits — pullback/retest before breakout + **cap leverage ≤10×**; **kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (65.4% of loss)**; keep EMA_CONF as template. (2) Options: fix fee-on-notional model + move to defined-risk spreads. (3) Consider loosening `paper_max_hold` — the 26 trades that reached it avg +49% peak. (Did NOT refill / change anything — append-only scope; no lab ≤ $50.)
- **Verdict:** #8 (aggressive 25–100× futures) **❌ DEAD** (−$23.2k closed, 23 burns, solvent only via refills). #6 (OTM selling) **⚠️ break-even/dead, fee-bound** (n=718, no lane with edge). #5 dead. No strategy verdict change without a clean entry-filter + leverage-cap rebuild.

### 2026-06-09 13:40 UTC — check-in, AUTO-REFILL burn #23 fired, options idle 3rd hr, orphan "sweep" reverted `[updated by: Cowork]`
**Independent recompute ~1 min after the concurrent 13:39 monitor entry below (reads agree within normal drift: my futures net −$22,986.66 / pre-refill bal ≈$13.34 vs monitor's −$22,963.26 / $36.74 — same hour, a few closes apart). Clean ~1h interval since my 12:39 run. Futures went insolvent again → BURN #23 fired 13:39:22 UTC (paper_deposits id 25, +$1,000); funded $23,000 → $24,000 (1 seed + 23 burns), bal now $1,013.34. Futures closed 1,245 → 1,268 (+23), net −$22,619.02 → −$22,986.66 (−$367.64, ~0 wins). Options funded $1,000 (0 burns), closed 707 → 708 (+1), net flat at −$380.15 — lane idle 3rd straight hour. Live OFF; regime now CHOPPY (regime_since 13:37:45). Verdict unchanged.**
- **What's happening (db now 13:40:27):** `bot_status` FRESH 13:39:06 UTC, is_paused=true, bot_state=paused, pause_reason "PAPER-ONLY mode", **market_regime=CHOPPY** (regime_since 13:37:45, flipped from TRENDING_DOWN), chop 0.679, atr_ratio 1.33, net_change_30m −0.706, delta_bal $27.08, live open_positions=0. Paper-only. Open paper: **futures 16, options 50.**
- **What happened since last Cowork check (12:39, ~61 min):** Futures closed 1,245 → **1,268 (+23)**, net −$22,619.02 → **−$22,986.66 (−$367.64, ~0 wins)**. **BURN #23 fired 13:39:22** (pre-refill bal ≈$13.34 ≤ $50 → +$1,000, funded $23k→$24k, bal → $1,013.34). Options closed 707 → **708 (+1)**, net **−$380.15** (effectively flat). All of this hour's −$367.64 bleed was futures.
- **Per-lane futures (n=1,268):** FUT_MOMENTUM_CONF 542/14.2%/**−$10,111.89**/68.1×/5.0m (crossed −$10k); FUT_DONCHIAN_100X 146/16.4%/−$4,939.73/100×/2.3m; FUT_DONCHIAN_CONF 138/23.9%/−$2,785.94/56.3×/5.9m; FUT_EMA_CONF 305/32.1%/−$2,650.14/29.7×/10.4m; FUT_DONCHIAN_50X 137/20.4%/−$2,498.96/50×/5.1m. **MOMENTUM_CONF = 44.0% of loss; + DONCHIAN_100X = −$15,051.62 = 65.5%** (shape unchanged). Least-bad EMA_CONF (32.1% win, lowest lev 29.7×, longest hold 10.4m).
- **Exit cohorts (futures, n=1,268):** `paper_stop` **704/0%/−$25,577.84 @ +1.49% avg peak = 111.3% of total loss** (wrong-direction entries noise-stopped before ever in money; +9 since 12:39). Profit cohort `paper_trail` +$1,120.36 (478/49.8%/+15.75%) + `paper_max_hold` +$2,209.74 (25/84.0%/+49.22%) = **+$3,330.10**. Plus ema21_lost −$403.22 (33), ema21_reclaimed −$290.27 (25), donchian_mid_revert −$45.43 (3). Exits work, entries are the whole problem.
- **Options (n=708, all 5 SELL lanes red, near-identical to 12:39 = lane idle 3rd hr):** OPT_SELL_PUT_FAR 169/5.9%/−$93.87/$0.588; OPT_SELL_CALL 143/13.3%/−$86.75/$0.586; OPT_SELL_PUT 176/12.5%/−$85.44/$0.587; OPT_SELL_NEUTRAL 151/13.9%/−$68.90/$0.582; OPT_SELL_CALL_FAR 69/13.0%/−$45.20/$0.571 (+1 close). Avg fee ~$0.58 ≈ per-trade loss (−$380.15/708 = −$0.54) = fee-bound. Exits: sell_take_profit 489/16.6%/−$114.18, sell_stop 147/0%/−$194.16, **sell_breached 72/0%/−$71.81 = 10.2% of closes.**
- **The new thing:** (1) **burn #23 fired on a clean 3-hour refill cadence** (#21 07:39, #22 10:39, #23 13:39 — ~3h spacing), pre-refill bal ≈$13.34. (2) **The 12:39 "orphan sweep" REVERTED.** Last hour I read opens at fut 1 / opt 11 and called the multi-day orphans cleared. Now opens are back to **fut 16 / opt 50, oldest opened_at still 2026-06-06 17:31/17:35, avg age fut 27.2h / opt 54.8h** — the 06-06 orphans are in the open book again WITHOUT new closes (options closed only +1). So the 12:39 low read was a transient/snapshot artifact, NOT a durable reconciliation; orphaned-open positions are still parked and open-count remains an unreliable activity signal. PnL impact still zero (unrealized). (3) Options lane has closed just 1 trade in 3 hours — effectively dormant.
- **What we should change (unchanged):** (1) Futures: attack ENTRIES not exits — pullback/retest before breakout + **cap leverage ≤10×**; **kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (65.5% of loss)**; keep EMA_CONF as template. (2) Options: fix fee-on-notional model + move to defined-risk spreads. (3) Ops: orphan reconciliation is NOT done — opens reverted to fut 16 / opt 50 (avg 27–55h old); a durable sweep is still needed. (Did NOT refill / change anything — append-only scope; burn #23 was the engine's own auto-refill.)
- **Known-bug status (vs 06-06):** (a) option-sell fee-on-notional **STILL PRESENT** (avg fee ~$0.58 ≈ per-trade loss; ~100% of options PnL is fees). (b) `sell_breached` 15-25m exit **STILL APPEARS FIXED** (10.2% of closes, not "nearly all"). (c) futures `paper_max_hold` ~30m cap **NOT the driver** (25 trades, +$2,210 @ +49% peak; lanes hold 2.3–10.4m). `paper_stop`/entries remain the structural killer. (d) orphaned-open non-reconciliation **STILL PRESENT** (12:39 "resolved" call was premature — opens reverted to fut 16 / opt 50).
- **Verdict:** #8 (aggressive 25–100× futures) **❌ DEAD** (−$23.0k closed, 23 burns, solvent only via refills). #6 (OTM selling) **⚠️ break-even/dead, fee-bound** (n=708, no lane with edge). #5 dead. No strategy verdict change without a clean entry-filter + leverage-cap rebuild.

### 2026-06-09 13:39 UTC — check-in, AUTO-REFILL burn #23 fired (futures bled to $36.74), options idle 3rd hr `[updated by: monitor]`
**39th monitor run. Futures bled −$367.64 (23 closes, 7 wins) to bal $36.74 (≤$50) → AUTO-REFILL burn #23 fired (deposit #25, +$1,000 → funded $24k, bal $1,036.74). Options closed only 1 (+$0.53) — effectively idle 3rd straight hour, bal $619.85. Same structural story, 39th confirmation: `paper_stop` cohort = the entire loss; exits work, entries are the whole problem. Live OFF (is_paused=true, bot_state paused FRESH 13:37 UTC, regime TRENDING_DOWN since 12:30, 0 scalp/hr). Verdict unchanged.**
- **What's happening (db now 13:39):** `bot_status` FRESH 13:37:05 UTC, is_paused=true, bot_state=paused, pause_reason "PAPER-ONLY mode", **market_regime=TRENDING_DOWN** (regime_since 12:30:19), chop 0.679, atr_ratio 1.31, net_change_30m −0.724, live open_positions=0, last_scan 183s ago. Paper-only confirmed.
- **What happened since last check (~60 min):** Futures closed +23 → 1,264, net −$367.64 (7 wins), **bal hit $36.74 ≤ $50 → burn #23**. Options closed +1 (+$0.53, 1 win) → 708 / net −$380.16. Book movement −$367 this hour, all futures; burn #23 is the 23rd refill (1 seed + 23 = $24,000 funded).
- **Per-lane futures (n=1,264):** FUT_MOMENTUM_CONF 541/14%/**−$10,098.64**/5.0m; FUT_DONCHIAN_100X 146/16%/−$4,939.73/2.3m; FUT_DONCHIAN_CONF 138/24%/−$2,785.94/5.9m; FUT_EMA_CONF 304/32%/−$2,659.27/10.3m; FUT_DONCHIAN_50X 137/20%/−$2,498.96/5.1m. **MOMENTUM_CONF = 43.9% of loss; + DONCHIAN_100X = −$15,038.37 = 65.4%** (shape unchanged). Least-bad EMA_CONF (32% win, lowest lev, longest hold 10.3m).
- **Exit cohorts (futures, n=1,264):** `paper_stop` **704/0%/−$25,577.84 @ +1.49% avg peak = 111.2% of total loss** (wrong-direction entries noise-stopped before ever in money). Profit cohort `paper_trail` +$1,111.23 (477/50%/+15.77%) + `paper_max_hold` +$2,209.74 (25/84%/+49.22%) = **+$3,320.97**. Plus ema21_lost −$403.22 (33), ema21_reclaimed −$290.27 (25), donchian_mid_revert −$45.43 (3). Exits work, entries are the whole problem.
- **Options (n=708, all 5 SELL lanes red, ~idle 3rd hr — only +1 close):** OPT_SELL_PUT_FAR 169/6%/−$93.87; OPT_SELL_CALL 143/13%/−$86.75; OPT_SELL_PUT 176/13%/−$85.44; OPT_SELL_NEUTRAL 151/14%/−$68.90; OPT_SELL_CALL_FAR 69/13%/−$45.20. Per-trade loss −$380.16/708 = −$0.54 ≈ fee → still fee-bound.
- **What we should change (unchanged):** (1) Futures: attack ENTRIES not exits — pullback/retest before breakout + **cap leverage ≤10×**; **kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (65.4% of loss)**; keep EMA_CONF as template. (2) Options: fix fee-on-notional model + move to defined-risk spreads. (Refilled burn #23 only — append-only otherwise.)
- **Known-bug status:** (a) option-sell fee-on-notional **STILL PRESENT** (~$0.54/trade ≈ ~100% of options loss). (b) futures `paper_stop`/entries remain the structural killer (111% of loss). (c) `paper_max_hold` NOT the driver (25 trades, +$2,210 @ +49% peak).
- **Verdict:** #8 (aggressive 25–100× futures) **❌ DEAD** (−$23k closed, 23 burns, solvent only via refills). #6 (OTM selling) **⚠️ break-even/dead, fee-bound** (n=708, no lane with edge). #5 dead. No strategy verdict change without a clean entry-filter + leverage-cap rebuild.

### 2026-06-09 12:39 UTC — check-in, orphaned opens cleared, options idle 2nd hr, no burn `[updated by: Cowork]`
**Independent recompute alongside the concurrent 12:39 monitor entry below (reads agree within normal drift; my futures closed=1,245/net −$22,619.02 vs monitor's 1,252/−$22,621.47 — same hour). Clean ~1h interval since my 11:39 Cowork run. Futures funded $23,000 (1 seed + 22 burns, NO new burn — last deposit #22 at 10:39:30), closed 1,245 / net −$22,619.02, bal $380.98 (>$50, no refill). Options funded $1,000 (0 burns), closed 707 / net −$380.68, bal $619.32. Live OFF; regime TRENDING_DOWN (regime_since 12:30:19). Verdict unchanged.**
- **What's happening (db now 12:39:50):** `bot_status` FRESH 12:39:05 UTC, is_paused=true, bot_state=paused, pause_reason "PAPER-ONLY mode", **market_regime=TRENDING_DOWN** (regime_since 12:30:19), chop 0.536, atr_ratio 1.07, net_change_30m −0.36, live open_positions=0. Paper-only. Open paper: **futures 1, options 11** (down hard from my 11:39 read of fut 9 / opt 46 — see "the new thing").
- **What happened since last Cowork check (11:39, ~60 min):** Futures closed 1,229 → **1,245 (+16)**, net −$22,277.25 → **−$22,619.02 (−$341.77, ~0 wins)**. Options closed 707 → **707 (+0)**, net flat at **−$380.68**. No new burn (futures bal $380.98 > $50). Book movement this hour = −$341.77, all futures.
- **Per-lane futures (n=1,245):** FUT_MOMENTUM_CONF 530/14.3%/**−$9,787.56**/68.3×/5.0m; FUT_DONCHIAN_100X 145/15.9%/−$4,953.98/100×/2.3m; FUT_DONCHIAN_CONF 137/23.4%/−$2,789.57/56.4×/5.9m; FUT_EMA_CONF 297/31.6%/−$2,619.90/29.8×/10.4m; FUT_DONCHIAN_50X 136/20.6%/−$2,468.02/50×/5.0m. **MOMENTUM_CONF = 43.3% of loss; + DONCHIAN_100X = −$14,741.54 = 65.2%** (shape unchanged). Least-bad EMA_CONF (31.6% win, lowest lev 29.8×, longest hold 10.4m).
- **Exit cohorts (futures, n=1,245):** `paper_stop` **695/0%/−$25,267.66 @ +1.49% avg peak = 111.7% of total loss** (wrong-direction entries noise-stopped before ever in money; +9 paper_stops since 11:39). Profit cohort `paper_trail` +$1,122.93 (468/49.4%/+15.87%) + `paper_max_hold` +$2,209.74 (25/84.0%/+49.22%) = **+$3,332.67**. Plus ema21_lost −$360.23 (30), ema21_reclaimed −$278.38 (24), donchian_mid_revert −$45.43 (3). Exits work, entries are the whole problem.
- **Options (n=707, all 5 SELL lanes red, byte-identical to my 11:39 read = lane fully idle 2nd hr):** OPT_SELL_PUT_FAR 169/5.9%/−$93.87/$0.588; OPT_SELL_CALL 143/13.3%/−$86.75/$0.586; OPT_SELL_PUT 176/12.5%/−$85.44/$0.587; OPT_SELL_NEUTRAL 151/13.9%/−$68.90/$0.582; OPT_SELL_CALL_FAR 68/11.8%/−$45.73/$0.571. Avg fee ~$0.58 ≈ per-trade loss (−$380.68/707 = −$0.54) = fee-bound. Exits: sell_take_profit 488/16.4%/−$114.71, sell_stop 147/0%/−$194.16, **sell_breached 72/0%/−$71.81 = 10.2% of closes.**
- **The new thing:** the **multi-day orphaned opens have largely cleared.** Open positions dropped futures 9→1 and **options 46→11** since my 11:39 read, WITHOUT closed-counts advancing (futures +16 closes are this hour's normal flow; options closed stayed flat at 707). So ~35 stale open options + ~8 open futures left the open book without becoming realized closes = a reconciliation/sweep, not realization. This is what the prior two Cowork entries recommended (one-time orphan sweep) appearing to have happened; net PnL impact zero (they were always unrealized). Open-count is now closer to a real activity signal again. Otherwise static: options lane idle 2nd straight hour (0 closes in 60 min), regime still TRENDING_DOWN, paper_stop still ~112% of futures loss.
- **What we should change (unchanged):** (1) Futures: attack ENTRIES not exits — pullback/retest before breakout + **cap leverage ≤10×**; **kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (65.2% of loss)**; keep EMA_CONF as template. (2) Options: fix fee-on-notional model + move to defined-risk spreads. (3) Ops: orphan sweep appears DONE — confirm opens stay low next interval. (Did NOT refill / change anything — append-only scope.)
- **Known-bug status (vs 06-06):** (a) option-sell fee-on-notional **STILL PRESENT** (avg fee ~$0.58 ≈ per-trade loss; ~100% of options PnL is fees). (b) `sell_breached` 15-25m exit **STILL APPEARS FIXED** (10.2% of closes, not "nearly all"). (c) futures `paper_max_hold` ~30m cap **NOT the driver** (25 trades, +$2,210 @ +49% peak; lanes hold 2.3–10.4m). `paper_stop`/entries remain the structural killer. (d) orphaned-open non-reconciliation **APPEARS RESOLVED** this hour (opens swept fut 9→1 / opt 46→11).
- **Verdict:** #8 (aggressive 25–100× futures) **❌ DEAD** (−$22.6k closed, 22 burns, solvent only via refills). #6 (OTM selling) **⚠️ break-even/dead, fee-bound** (n=707, no lane with edge). #5 dead. No strategy verdict change without a clean entry-filter + leverage-cap rebuild.

### 2026-06-09 12:39 UTC — check-in, another quiet red futures hour, no burn, options idle 2nd hr `[updated by: monitor]`
**38th monitor run. Regime now TRENDING_DOWN. Futures bled −$367.15 (17 closes, 1 win) to bal $378.53 — solvent, no new burn (#22 still the last refill). Options closed NOTHING for the 2nd straight hour. Same structural story, 38th confirmation: `paper_stop` cohort = the entire loss; exits work, entries are the whole problem. Live OFF (is_paused=true, bot_state paused FRESH 12:37 UTC, regime TRENDING_DOWN, 0 scalp/hr). Verdict unchanged.**
- **Balances:** Futures funded $23,000 (22 burns), net −$22,621.47, **bal $378.53** (>$50, no refill). Options funded $1,000 (0 burns), net −$388.33, **bal $611.67** (>$50, no refill).
- **This hour (60 min):** Futures −$367.15 / 17 closes / 1 win. Options 0 closes (lane idle 2nd consecutive hour — newest open is stale, see prior entry's orphan finding).
- **Per-lane futures (n=1,252):** FUT_MOMENTUM_CONF 532/14%/**−$9,774.74**/68×; FUT_DONCHIAN_100X 145/16%/−$4,953.98/100×; FUT_DONCHIAN_CONF 137/23%/−$2,789.57/56×; FUT_EMA_CONF 302/31%/−$2,635.17/30×; FUT_DONCHIAN_50X 136/21%/−$2,468.02/50×. **MOMENTUM_CONF = 43.2% of loss; + DONCHIAN_100X = −$14,728.72 = 65.1%.** Least-bad EMA_CONF (31% win, lowest lev 30×).
- **Exit cohorts (futures, n=1,252):** `paper_stop` **695/0%/−$25,267.66 @ +1.49% avg peak = 111.7% of total loss** (wrong-direction entries noise-stopped before ever in money). Profit cohort `paper_trail` +$1,122.93 (468/49%/+15.87%) + `paper_max_hold` +$2,209.74 (25/84%/+49.22%) = **+$3,332.67**. Plus ema21_lost −$360.23 (30), ema21_reclaimed −$278.38 (24), donchian_mid_revert −$45.43 (3). Exits work, entries are the whole problem.
- **Options (n=757, all 5 SELL lanes red, fee-bound):** OPT_SELL_PUT_FAR 177/6%/−$95.73/−$0.541; OPT_SELL_PUT 184/12%/−$89.14/−$0.484; OPT_SELL_CALL 153/16%/−$86.24/−$0.564; OPT_SELL_NEUTRAL 163/15%/−$71.64/−$0.440; OPT_SELL_CALL_FAR 80/16%/−$45.44/−$0.568. Avg per-trade −$0.51 ≈ fee per trade = fee-bound (~100% of loss is fees).
- **Known-bug status (unchanged):** (a) option-sell fee-on-notional **STILL PRESENT** (~$0.51/trade ≈ entire options loss). (b) futures high-lev stop converts +1.49%-peak adverse moves into full liquidations under 68–100× — `paper_stop`/entries are the structural killer. (c) orphaned-open positions (46 opt oldest 06-06, ~9 fut) still never reconciling — open-count is a poor activity signal; PnL impact zero (unrealized).
- **What we should change (unchanged):** (1) Futures: attack ENTRIES not exits — pullback/retest before breakout + **cap leverage ≤10×**; **kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (65.1% of loss)**; keep EMA_CONF as template. (2) Options: fix fee-on-notional model + move to defined-risk spreads. (3) Ops: one-time sweep of orphaned opens.
- **Verdict:** #8 (aggressive 25–100× futures) **❌ DEAD** (−$22.6k closed, 22 burns, solvent only via refills). #6 (OTM selling) **⚠️ break-even/dead, fee-bound** (n=757, no lane with edge). No strategy verdict change without a clean entry-filter + leverage-cap rebuild.

### 2026-06-09 11:39 UTC — check-in, options lane idle, "hung-open" reframed as multi-day orphans `[updated by: Cowork]`
**Independent recompute alongside the concurrent 11:39 monitor entry below (our reads differ by a few seconds: I caught futures 1,229 closed / net −$22,277.25 / bal ≈$722.75; the monitor's fractionally-later read shows 1,239 / −$22,269.30 / bal $730.70 — same hour, normal intra-interval drift). Futures funded $23,000 (22 burns, NO new burn — last deposit #22 at 10:39:30), options funded $1,000 (0 burns), closed 707 / net −$380.68 / bal ≈$619.32. Live OFF; regime flipped TRENDING_UP→TRENDING_DOWN (regime_since 11:12:54). All of this hour's bleed was futures (9 closes, −$295.29, 0 wins); options lane closed NOTHING in 60 min. Verdict unchanged.**
- **What's happening (db now 11:39:07):** `bot_status` FRESH 11:39:07 UTC, is_paused=true, bot_state=paused, pause_reason "PAPER-ONLY mode", **market_regime=TRENDING_DOWN** (regime_since 11:12:54, flipped from the 10:02 UP), chop 0.607, atr_ratio 1.0, net_change_30m −0.185, delta_bal $27.08, live open_positions=0. Paper-only. Open paper: **futures 9, options 46.**
- **What happened since last Cowork check (10:40, ~59 min):** Futures closed 1,220 → **1,229 (+9)**, net −$21,981.96 → **−$22,277.25 (−$295.29, 0 wins)**. Options closed 707 → **707 (+0)**, net flat at **−$380.68**. No new burn (futures bal ≈$722.75 > $50; #22 was 10:39). Reconciliation: the monitor's 10:39 "1,229 closed" was a transient over-read — true count at 10:40 was Cowork's 1,220; +9 real closes since brings my read to 1,229.
- **Per-lane futures (n=1,229):** FUT_MOMENTUM_CONF 523/14.5%/**−$9,544.84**/68.1×/5.1m; FUT_DONCHIAN_100X 144/16.0%/−$4,952.08/100×/2.3m; FUT_DONCHIAN_CONF 135/23.0%/−$2,762.08/56.5×/5.8m; FUT_EMA_CONF 292/32.2%/−$2,556.40/29.8×/10.2m; FUT_DONCHIAN_50X 135/20.7%/−$2,461.85/50×/5.0m. **MOMENTUM_CONF = 42.8% of loss; + DONCHIAN_100X = −$14,496.92 = 65.1%** (shape unchanged). Least-bad EMA_CONF (32.2% win, lowest lev 29.8×, longest hold 10.2m). The −$295 hour fell mostly on MOMENTUM_CONF.
- **Exit cohorts (futures, n=1,229):** `paper_stop` **686/0%/−$24,972.46/+1.49% peak = 112.1% of total loss** (wrong-direction entries noise-stopped before ever in money). Profit cohort `paper_trail` +$1,149.52 (463/49.7%/+15.93%) + `paper_max_hold` +$2,209.74 (25/84.0%/+49.22%) = **+$3,359.26**. Plus ema21_lost −$360.23 (30), ema21_reclaimed −$258.39 (22), donchian_mid_revert −$45.43 (3). Exits work, entries are the whole problem.
- **Options (n=707, all 5 SELL lanes red — byte-identical to 10:40, lane idle):** OPT_SELL_PUT_FAR 169/5.9%/−$93.87, OPT_SELL_CALL 143/13.3%/−$86.75, OPT_SELL_PUT 176/12.5%/−$85.44, OPT_SELL_NEUTRAL 151/13.9%/−$68.90, OPT_SELL_CALL_FAR 68/11.8%/−$45.73. Avg fee $0.57–0.59 ≈ per-trade loss (−$380.68/707 = −$0.54) = fee-bound. Exits: sell_take_profit 488/16.4%/−$114.71 (69% of closes), sell_stop 147/0%/−$194.16, **sell_breached 72/0%/−$71.81 = 10.2% of closes.**
- **The new thing:** the recurring "44–46 hung-open SELL options" story is **wrong as previously framed.** Age query on the 46 current opens: oldest `opened_at` **2026-06-06 17:35** (~66 h ago), newest **10:15 today** (87.6 min ago), **avg age ≈57.6 h.** So this is NOT a fresh batch that drains-and-refills each hour — it's a core of **multi-day ORPHANED open positions the close logic never touches**, with a thin recent layer on top. Past "open 44→6" drains closed only the recent layer; the old orphans persist. Corollary: **the options lane has been fully IDLE this hour — 0 closes in 60 min, newest open is 88 min old**, so open-count is a poor activity signal. The 9 open futures are likewise stale orphans (avg age ~47 h). Net PnL impact of orphans is zero (unrealized), but they pollute the open-count read.
- **What we should change (unchanged strategy; one new ops flag):** (1) Strategy: attack ENTRIES not exits — pullback/retest before breakout + **cap leverage ≤10×**; **kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (65.1% of loss)**; keep EMA_CONF as template. Options: defined-risk spreads to escape fee drag. (2) **NEW ops flag:** sweep/reconcile the orphaned opens — 46 options (oldest 06-06) + 9 futures (~47 h) sitting open indefinitely; either the close loop skips them or they're stuck. A one-time cleanup would make open-count meaningful again. (Did NOT refill / change anything — append-only scope.)
- **Known-bug status (vs 06-06):** (a) option-sell fee-on-notional **STILL PRESENT** (avg fee ~$0.58 ≈ per-trade loss; ~100% of options PnL is fees; futures fees also notional-based). (b) `sell_breached` 15–25m exit **STILL APPEARS FIXED** (10.2% of closes, not "nearly all"). (c) futures `paper_max_hold` ~30m cap **NOT the driver** (25 trades, +$2,210 @ +49% peak; lanes hold 2.3–10.2m). `paper_stop`/entries remain the structural killer. NEW candidate issue: **orphaned-open positions never reconciling** (see "the new thing").
- **Verdict:** #8 (aggressive 25–100× futures) **❌ DEAD** (−$22.3k closed, 22 burns, solvent only via refills). #6 (OTM selling) **⚠️ break-even/dead, fee-bound** (n=707, no lane with edge). #5 dead. No strategy verdict change without a clean entry-filter + leverage-cap rebuild.

### 2026-06-09 11:39 UTC — check-in, quiet red hour post-burn-#22, no new burn `[updated by: Cowork]`
**37th monitor run. One hour after burn #22 (10:37 UTC funded $23k, bal ≈$1,011.55), futures bled the usual −$269.91 (8 closes, 0 wins) leaving bal $730.70 — solvent, no refill. Options dead quiet (0 closes). Same structural story holds and is now sharper than ever: the `paper_stop` exit cohort is the entire loss. Live OFF (is_paused=true, bot_state=paused FRESH 11:37 UTC, 0 scalp/hr). Verdict unchanged.**
- **Balances:** Futures funded $23,000 (22 burns), net −$22,269.30, **bal $730.70** (>$50, no refill). Options funded $1,000 (0 burns), net −$387.12, **bal $612.88** (>$50, no refill).
- **This hour (vs 10:39 monitor):** Futures closed 1,229 → **1,239** (+10 here / 8 in window), net −$22,000ish → **−$22,269.30 (−$269.91)**, 0 wins. Options closed 753 → **753** (no new closes), net −$386.69 → **−$387.12** (rounding; effectively flat). No green hour.
- **Per-lane futures (n=1,239), worst→least-bad:** FUT_MOMENTUM_CONF 525/15%/**−$9,509.04** (avg peak +9.25%, max +326.56%); FUT_DONCHIAN_100X 144/16%/**−$4,952.08**; FUT_DONCHIAN_CONF 136/23%/−$2,771.98; FUT_EMA_CONF 299/32%/−$2,569.50 (least-bad win%, lowest lev, longest hold); FUT_DONCHIAN_50X 135/21%/−$2,461.85. **MOMENTUM_CONF = 43% of all futures loss; + DONCHIAN_100X = −$14,461.12 = 65%** — shape unchanged for 30+ runs.
- **Per-lane options (n=753), all 5 SELL lanes negative & fee-bound:** OPT_SELL_PUT_FAR 175/6%/−$95.09 (−$0.5434/trade); OPT_SELL_PUT 182/12%/−$87.82 (−$0.4825); OPT_SELL_CALL 153/16%/−$86.20 (−$0.5634); OPT_SELL_NEUTRAL 163/14%/−$72.30 (−$0.4436); OPT_SELL_CALL_FAR 80/15%/−$45.64 (−$0.5705). Every lane −$0.44…−$0.57/trade ≈ pure fee drag; no directional edge surfacing.
- **Exit-reason cohort (THE finding — entries, not exits, are the problem):** `paper_stop` 685/**0% win**/−$24,947.08 @ avg peak **+1.49%** = **112% of total loss** (wrong entries noise-stopped, never get into the money). Vs the profit cohort: `paper_trail` 463/**50% win**/**+$1,149.52** @ avg peak +15.93%, and `paper_max_hold` 25/**84% win**/**+$2,209.74** @ avg peak +49.22%. Exits work (+$3,359.26 combined); the 685 paper_stops that peak at +1.49% and die are the whole hole.
- **Live status:** `bot_status` FRESH 11:37:04 UTC, is_paused=true, bot_state=paused. 0 options_scalp in last hour. Live confirmed OFF.
- **Verdict (unchanged):** pullback entries (don't chase momentum into the stop) + cap leverage ≤10× + kill FUT_MOMENTUM_CONF & FUT_DONCHIAN_100X (65% of loss) + fix the options fee model (every SELL lane is fee-bound, no edge can show through). Engine is sound — paper_stop/trail/max_hold all behave; the entry signal is the defect.

### 2026-06-09 10:40 UTC — check-in, corroborates burn #22 (as predicted) `[updated by: Cowork]`
**Independent recompute ~1.7 min after the monitor's 10:39 entry; corroborates it. The burn #22 flagged "1-2 hrs out" the prior two checks FIRED at 10:39:30 UTC (paper_deposits id 24, +$1,000) — pre-refill bal ≈$11.55, lowest on record. Funded $22k → $23k (22 burns), bal ≈$1,018. My snapshot caught **46 options hung open mid-realization** (closes 707, net −$380.68); the monitor's fractionally-later read shows them draining to 753 closed / −$386.69, i.e. that cluster resolved into the same −$0.54/trade fee-bound pattern within the interval. Regime TRENDING_UP (10:02). Live OFF. Verdict unchanged.**
- **What's happening (db now 10:40:50):** `bot_status` FRESH 10:39:06 UTC, is_paused=true, bot_state=paused, pause_reason "PAPER-ONLY mode", **market_regime=TRENDING_UP** (regime_since 10:02:23, flipped from DOWN), chop 0.643, atr_ratio 1.0, net_change_30m +0.147, delta_bal $27.08, live open_positions=0. Paper-only. Open paper at my snapshot: **futures 9, options 46** (the 46 then drained — see monitor's 753 closed).
- **What happened since last Cowork check (09:40, ~60 min):** Futures closed 1,209 → **1,220** (monitor caught 1,229), net −$21,790.68 → **−$21,981.96 (−$191.28)**. **BURN #22 fired 10:39:30** (funded $22,000 → $23,000; insolvent → refilled, bal ≈$1,018). Options closed 702 → **707** (then 753 in monitor read as the open cluster realized), net −$377.12 → **−$380.68**. No green hour.
- **Per-lane futures (n=1,220):** FUT_MOMENTUM_CONF 518/14.7%/**−$9,383.54**/68.0×/5.1m; FUT_DONCHIAN_100X 143/16.1%/−$4,886.28/100×/2.2m; FUT_DONCHIAN_CONF 135/23.0%/−$2,762.08/56.5×/5.8m; FUT_EMA_CONF 290/32.4%/−$2,516.40/29.8×/10.1m; FUT_DONCHIAN_50X 134/20.9%/−$2,433.65/50×/5.0m. **MOMENTUM_CONF = 42.7% of loss; + DONCHIAN_100X = −$14,269.82 = 64.9%** (shape unchanged). Least-bad EMA_CONF (32.4% win, lowest lev 29.8×, longest hold 10.1m).
- **Exit cohorts (futures, n=1,220):** `paper_stop` **678/0%/−$24,677.70/+1.48% peak = 112.3% of total loss** (wrong-direction entries noise-stopped before ever in money). Profit cohort `paper_trail` +$1,150.05 (462/49.8%/+15.94%) + `paper_max_hold` +$2,209.74 (25/84.0%/+49.22%) = **+$3,359.79**. Plus ema21_lost −$360.23 (30), ema21_reclaimed −$258.39 (22), donchian_mid_revert −$45.43 (3). Exits work, entries are the whole problem.
- **Options (n=707, all 5 SELL lanes red):** OPT_SELL_PUT_FAR 169/5.9%/−$93.87, OPT_SELL_CALL 143/13.3%/−$86.75, OPT_SELL_PUT 176/12.5%/−$85.44, OPT_SELL_NEUTRAL 151/13.9%/−$68.90, OPT_SELL_CALL_FAR 68/11.8%/−$45.73. Avg fee $0.57–0.59 ≈ per-trade loss (−$380.68/707 = −$0.54) = fee-bound. Exits: sell_take_profit 488/16.4%/−$114.71 (69% of closes, clears at a loss), sell_stop 147/0%/−$194.16, **sell_breached 72/0%/−$71.81 = 10.2% of closes.**
- **The new thing:** (1) **burn #22 fired on schedule** — two prior checks predicted insolvency "1-2 hrs out"; it landed 10:39:30 at pre-refill bal ≈$11.55 (lowest ever), +$1,000 restoring bal ≈$1,018. Refill loop functional when cadence is normal. (2) **Options open re-spiked to 46** (mirrors the 07:40 → 44 cluster) and I caught it mid-drain — closes jumped 707 → 753 across <2 min into the monitor's read, all into the −$0.54/trade fee-bound pattern. Recurring batch-hung-open behavior, not a runaway loop (open capped, then realized). (3) Regime round-tripped to TRENDING_UP, yet paper_stop still drives 112% of futures loss — entries fail in up-tape too.
- **What we should change (unchanged):** (1) Strategy: attack ENTRIES not exits — pullback/retest before breakout + **cap leverage ≤10×**; **kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (64.9% of loss)**; keep EMA_CONF as template. Options: defined-risk spreads to escape fee drag. (2) Operational: the periodic 44-46 open-options spikes realize within the interval; not an entry-loop bug, but worth a watch. (Did NOT refill / change anything — append-only scope; burn #22 was the engine's own auto-refill.)
- **Known-bug status (vs 06-06):** (a) option-sell fee-on-notional **STILL PRESENT** (avg fee ~$0.58 ≈ per-trade loss; ~100% of options PnL is fees; futures fees $7.5–25/trade also notional-based). (b) `sell_breached` 15-25m exit **STILL APPEARS FIXED** (10.2% of closes, not "nearly all"). (c) futures `paper_max_hold` ~30m cap **NOT the driver** (25 trades, +$2,210 @ +49% peak; lanes hold 2.2–10.1m). `paper_stop`/entries remain the structural killer.
- **Verdict:** #8 (aggressive 25–100× futures) **❌ DEAD** (−$22.0k closed, 22 burns, solvent only via refills). #6 (OTM selling) **⚠️ break-even/dead, fee-bound** (n=707, no lane with edge). #5 dead. No strategy verdict change without a clean entry-filter + leverage-cap rebuild.

### 2026-06-09 10:39 UTC — AUTO-REFILL burn #22 fired, quiet hour, verdict unchanged 36th run `[updated by: alpha-paper-lab-monitor]`

**What happened since last check (gap ~1h):** The 09:39 forecast hit — futures bled to insolvency-low and tripped the refill. Quiet red hour: futures **−$187.95 over 13 closes (4 wins)**, options **−$3.56 over 5 closes (0 wins)**. Futures bal crossed below $50 (≈$11.55 pre-refill) → **AUTO-REFILL burn #22** funded $1,000 (id 24, 10:39:30Z), restoring funded $22k→**$23k**, bal → **$1,011.55**. No structural change; entries remain the whole problem.

- **Balances:** Futures funded **$23,000** (1 seed + **22 burns**), closed **1,229 / net −$21,988.45**, **bal $1,011.55** (post-refill). Options funded **$1,000** (0 burns), closed **753 / net −$386.69**, **bal $613.31** (>$50, no refill).
- **AUTO-REFILL:** `INSERT paper_deposits('futures',1000,'refill','auto-refill burn #22 2026-06-09T10:39Z')` → id 24. Pre-refill bal was ≈$11.55 (lowest on record), confirming the 09:39 "burn #22 within 1–2h" call.
- **Live OFF:** `bot_status` is_paused=true, bot_state=**paused**, market_regime **TRENDING_UP** (regime_since 10:02), pause_reason "PAPER-ONLY mode", FRESH **10:37 UTC**, open_positions 0, last_scan 183s ago, 0 `options_scalp` last hour. Paper-only confirmed. ✓
- **Per-lane futures (n=1,229):** FUT_MOMENTUM_CONF 520/15%/**−$9,370.72**; FUT_DONCHIAN_100X 143/16%/−$4,886.28; FUT_DONCHIAN_CONF 135/23%/−$2,762.08; FUT_EMA_CONF 297/32%/−$2,540.59 (least-bad win, lowest avg-peak 5.48 = lowest lev, longest hold 10.0m); FUT_DONCHIAN_50X 134/21%/−$2,433.65. **MOMENTUM_CONF = 42.6% of loss; + DONCHIAN_100X = −$14,257.00 = 64.8%** (shape unchanged).
- **Exit cohorts (futures, n=1,229):** `paper_stop` **678/0%/−$24,677.70 @ +1.48% avg peak = 112.2% of total loss** (wrong-direction entries noise-stopped before ever in money). Profit cohort `paper_trail` +$1,150.05 (462/50%/+15.94%) + `paper_max_hold` +$2,209.74 (25/84%/+49.22%) = **+$3,359.79**. Plus ema21_lost −$360.23 (30), ema21_reclaimed −$258.39 (22), donchian_mid_revert −$45.43 (3). **Exits work, entries are the whole problem (36th run).**
- **Options (n=753, all 5 SELL lanes red):** OPT_SELL_PUT_FAR 175/−$95.09 (−$0.543/trade), OPT_SELL_PUT 182/−$87.82 (−$0.483), OPT_SELL_CALL 153/−$86.48 (−$0.565), OPT_SELL_NEUTRAL 163/−$71.62 (−$0.439), OPT_SELL_CALL_FAR 80/−$45.75 (−$0.572). Avg fee ≈$0.58/trade vs per-trade loss −$0.44..−$0.57 → **fee-bound, ~100% of options loss is fees**. No lane-config change.
- **What we should change (unchanged):** (1) Strategy: attack ENTRIES not exits — pullback/retest before breakout + **cap leverage ≤10×**; **kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (64.8% of loss)**; keep EMA_CONF as template. (2) Options ENGINE BUG: charge fees on premium/stake not underlying notional → defined-risk spreads to escape fee drag. (Append-only; refilled burn #22, did NOT change code this hour.)

### 2026-06-09 09:39 UTC — heaviest hour in a while, no burn yet, verdict unchanged 35th run `[updated by: alpha-paper-lab-monitor]`

**What happened since last check (gap ~1h):** Hardest red hour of the recent stretch. Futures bled **−$341.75 over 15 closes (4 wins)** — bigger than the prior hour's −$227.74 — dropping bal **$542.68 → $205.99** (still >$50, burns stay at **21**, but burn #22 is now plausibly 1–2 hours out if this rate holds). Options 24 closes −$12.57 (2 wins), bal $622.88. No structural change; entries remain the whole problem.

- **Balances:** Futures funded **$22,000** (21 burns), closed **1,207 / net −$21,794.01**, **bal $205.99**. Options funded **$1,000** (0 burns), closed **702 / net −$377.12**, **bal $622.88**. No lab ≤ $50 → **no AUTO-REFILL this hour**.
- **Live OFF:** `bot_status` is_paused=true, bot_state=**paused**, market_regime TRENDING_DOWN, pause_reason "PAPER-ONLY mode", FRESH **09:37 UTC**, 0 `options_scalp` trades last hour. Paper-only confirmed. ✓
- **Per-lane futures (n=1,207):** FUT_MOMENTUM_CONF 514/15%/**−$9,316.50**; FUT_DONCHIAN_100X 141/16%/−$4,845.14; FUT_DONCHIAN_CONF 133/23%/−$2,715.01; FUT_EMA_CONF 287/32%/−$2,510.05 (least-bad win, lowest avg-peak 5.59 = lowest lev); FUT_DONCHIAN_50X 132/20%/−$2,407.30. **MOMENTUM_CONF = 42.7% of loss; + DONCHIAN_100X = −$14,161.64 = 65.0%** (shape unchanged).
- **Exit cohorts (futures, n=1,207):** `paper_stop` **672/0%/−$24,473.74 @ +1.47% avg peak = 112.3% of total loss** (wrong-direction entries noise-stopped before ever in money). Profit cohort `paper_trail` +$1,108.96 (459/50%/+15.9%) + `paper_max_hold` +$2,209.74 (25/84%/+49.2%) = **+$3,318.70**. Plus ema21_lost −$360.23 (30), ema21_reclaimed −$248.58 (21), donchian_mid_revert −$26.82 (2). **Exits work, entries are the whole problem (35th run).**
- **Options (n=702, all 5 SELL lanes red):** OPT_SELL_PUT_FAR 169/−$93.87 (−$0.555/trade), OPT_SELL_PUT 176/−$85.44 (−$0.485), OPT_SELL_CALL 140/−$84.33 (−$0.602), OPT_SELL_NEUTRAL 150/−$68.31 (−$0.455), OPT_SELL_CALL_FAR 67/−$45.17 (−$0.674). Avg fee ≈$0.58/trade vs per-trade loss −$0.46..−$0.67 → **fee-bound, ~100% of options loss is fees**. No lane-config change.
- **What we should change (unchanged):** (1) Strategy: attack ENTRIES not exits — pullback/retest before breakout + **cap leverage ≤10×**; **kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (65.0% of loss)**; keep EMA_CONF as template. (2) Options ENGINE BUG: charge fees on premium/stake not underlying notional → defined-risk spreads to escape fee drag. (Append-only; did NOT refill or change code this hour.)

### 2026-06-09 09:40 UTC — check-in `[updated by: Cowork]`
**Corroborates the monitor's 09:39 entry (ran ~1 min after it, near-zero new closes between). Clean ~1h interval since the 08:40 Cowork run. Futures funded $22,000 (21 burns, NO new burn — last deposit 07:39 = #21), closed net −$21,790.68 (n=1,209), bal ≈$209.32 (>$50, no refill). Options funded $1,000 (0 burns), closed net −$377.12 (n=702), bal ≈$622.88. Live OFF; regime TRENDING_DOWN (regime_since 09:05). The 44 hung-open SELL options flagged 07:40–08:40 fully REALIZED: options open dropped 44→6 into the predicted fee-bound pattern. Verdict unchanged, 35th run.**
- **What's happening:** `bot_status` FRESH 09:39:05 UTC (~1 min before db now 09:40:00), is_paused=true, bot_state=paused, pause_reason "PAPER-ONLY mode", **market_regime=TRENDING_DOWN** (regime_since 09:05:04), chop 0.571, atr_ratio 1.34, net_change_30m −0.215, delta_bal $27.08, live open_positions=0. Paper-only. Open paper: **futures 6, options 6.** Lanes active: 5 FUT_* + 5 OPT_SELL_*.
- **What happened since last Cowork check (08:40, ~60 min):** Futures closed 1,193 → **1,209 (+16)**, net −$21,451.04 → **−$21,790.68 (−$339.64)**. Options closed 678 → **702 (+24)**, net −$364.55 → **−$377.12 (−$12.57)**. No new burn (bal >$50). Futures bal moved $548.96 → ≈$209.32 — lowest pre-refill reading logged; **burn #22 plausibly within 1–2 hrs** at this bleed rate. No green hour.
- **Per-lane futures (n=1,209):** FUT_MOMENTUM_CONF 514/14.6%/**−$9,316.50**/67.9×/5.1m; FUT_DONCHIAN_100X 142/16.2%/−$4,843.91/100×/2.2m; FUT_DONCHIAN_CONF 133/23.3%/−$2,715.01/56.8×/5.4m; FUT_EMA_CONF 287/32.4%/−$2,510.05/29.9×/10.1m; FUT_DONCHIAN_50X 133/21.1%/−$2,405.19/50×/4.8m. **MOMENTUM_CONF = 42.8% of loss; + DONCHIAN_100X = −$14,160.41 = 65.0%** (shape unchanged). Least-bad EMA_CONF (32.4% win, lowest lev 29.9×, longest hold 10.1m).
- **Exit cohorts (futures, n=1,209):** `paper_stop` **672/0%/−$24,473.74/+1.47% peak = 112.3% of total loss** (wrong-direction entries noise-stopped before ever in money). Profit cohort `paper_trail` +$1,108.96 (459/49.7%/+15.91%) + `paper_max_hold` +$2,209.74 (25/84.0%/+49.22%) = **+$3,318.70**. Plus ema21_lost −$360.23 (30), ema21_reclaimed −$248.58 (21), donchian_mid_revert −$26.82 (2). Exits work, entries are the whole problem (35 runs).
- **Options (n=702, all 5 SELL lanes red):** OPT_SELL_PUT_FAR 169/5.9%/−$93.87, OPT_SELL_PUT 176/12.5%/−$85.44, OPT_SELL_CALL 140/13.6%/−$84.33, OPT_SELL_NEUTRAL 150/14.0%/−$68.31, OPT_SELL_CALL_FAR 67/11.9%/−$45.17. Avg fee $0.57–0.59 ≈ per-trade loss (−$377.12/702 = −$0.54) = fee-bound. Exits: sell_take_profit 484/16.5%/−$112.50 (69% of closes, clears at a loss), sell_stop 146/0%/−$192.80, **sell_breached 72/0%/−$71.81 = 10.3% of closes.**
- **The new thing:** the **44 hung-open SELL options resolved** — options open collapsed 44→6 while closes advanced +24 (−$12.57 net) into the same −$0.54/trade fee-bound pattern, confirming it was a batch hung open >1h, NOT a runaway entry loop (open never grew, then drained on schedule). Only emerging watch-item: futures bal ≈$209 is the lowest pre-refill reading on record — next-hour burn #22 likely.
- **What we should change (unchanged):** (1) Strategy: attack ENTRIES not exits — pullback/retest before breakout + **cap leverage ≤10×**; **kill FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (65.0% of loss)**; keep EMA_CONF as template. Options: defined-risk spreads to escape fee drag. (Did NOT refill / change anything — append-only scope.)
- **Known-bug status (vs 06-06):** (a) option-sell fee-on-notional **STILL PRESENT** (avg fee ~$0.58 ≈ per-trade loss; ~100% of options PnL is fees; futures fees $7.5–25/trade also notional-based). (b) `sell_breached` 15–25m exit **STILL APPEARS FIXED** (10.3% of closes, not "nearly all"). (c) futures `paper_max_hold` ~30m cap **NOT the driver** (25 trades, +$2,210 @ +49% peak; lanes hold 2.2–10.1m). `paper_stop`/entries remain the structural killer.
- **Verdict:** #8 (aggressive 25–100× futures) **❌ DEAD** (−$21.8k closed, 21 burns, solvent only via refills). #6 (OTM selling) **⚠️ break-even/dead, fee-bound** (n=702, no lane with edge). #5 dead. No strategy verdict change without a clean entry-filter + leverage-cap rebuild.

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
| paper_trail | 393 | **+799.21** 
---

### 2026-06-09 21:39 UTC — check-in `[updated by: Cowork]`

**What's happening:** Bot LIVE OFF (`is_paused=true`, "PAPER-ONLY mode"; uptime only 229s — **just restarted ~4 min ago**). 2 active strategies (scalp + options_scalp), 0 live positions, delta balance $27.08. Regime TRENDING_DOWN, chop 0.393. Open now: **1 futures** (`FUT_SFP_15X`) + **1 option** (`OPT_SELL_RANGE_V3`) — far fewer than last check's 8 FUT / 46 OPT (consistent with the fresh restart). **New lanes have appeared** (see below).

**What happened since last check (gap ~22h since 06-08 23:39):** Heavy sample growth, no burn observed.
- **Futures:** +442 closed, **−$7,785** (n=1,031→**1,473**; net −$19,082.63→**−$26,867.65**).
- **Options SELL:** +174 closed, **−$109.88** (n=570→**744**; net −$313.36→**−$423.24**; ≈−$0.57/trade — still flat noise).

**Per-lane — Futures (n=1,473):**

| Lane | Closed | Win% | Net | Avg lev | Avg peak% | Hold |
|---|---|---|---|---|---|---|
| **FUT_MOMENTUM_CONF** | 622 | 14.1 | **−11,650.35** | 67.6 | 8.87 | 4.9m |
| FUT_DONCHIAN_100X | 174 | 16.1 | −5,812.28 | 100 | 9.57 | 2.2m |
| FUT_DONCHIAN_CONF | 166 | 22.9 | −3,495.99 | 56.2 | 7.23 | 5.4m |
| FUT_DONCHIAN_50X | 165 | 21.2 | −3,028.07 | 50 | 6.88 | 4.8m |
| FUT_EMA_CONF | 346 | 34.4 | −2,880.96 | 29.6 | 5.57 | 10.3m |
| FUT_SFP_15X | 0 (1 open) | — | — | 15 | — | — |

**Per-lane — Options SELL (n=744):** PUT_FAR −$99.88 (7.4%), CALL −$96.53 (14.9%), PUT −$92.57 (13.7%), NEUTRAL −$75.00 (15.6%), CALL_FAR −$57.15 (13.3%), PUT_V3 −$2.09 (n=2, new). Avg peak 0.14–0.59% everywhere — no lane with directional edge.

**The new thing:**
1. **New lanes deployed — leverage is finally coming down.** `FUT_SFP_15X` (15× — the first futures lane below 29×) is now open, and new option lanes `OPT_SELL_PUT_V3` / `OPT_SELL_RANGE_V3` plus a new exit `sell_trend_break` have appeared. Someone is iterating toward the sane-leverage / better-entry fix that prior check-ins recommended. **n still ~0 — no verdict, just flagging the deployment.**
2. **Entry-quality thesis still ironclad (FUT exit split, n=1,473):**

| Exit | Closed | Net | Avg peak% | Avg real% |
|---|---|---|---|---|
| **paper_stop** | 833 | **−30,124.04** | +1.44 | −8.32 |
| paper_trail | 550 | **+1,558.79** | +15.88 | +7.13 |
| paper_max_hold | 29 | **+2,436.52** | +47.40 | +39.21 |
| ema21_lost/reclaimed | 58 | −693.49 | ~2.1 | ~−2.3 |

`paper_stop` = 833 trades / −$30,124 (larger than the whole −$26.9k book; trail +$1,559 and max_hold +$2,437 are the only green). Avg peak of stopped trades just **+1.44%** → wrong-direction entries dying at −8.32% realized under leverage. Exit logic works (trail banks ~45% of peak; 29 max_hold runners avg +39% realized). Entries do not.

**Engine-bug status (vs known issues 2026-06-06):**
- **Option-sell fee drag — STILL PRESENT.** Avg fee ~$0.60/trade × 744 ≈ $446 in fees vs total loss −$423 → **fees are ≥100% of the loss; gross is ~breakeven.** Charged on underlying notional. Options structurally can't print until fixed.
- **sell_breached premature-exit — still looks FIXED.** Only 73/744 (9.8%) at 10.1m avg hold; `sell_take_profit` dominates (511, 35.9m). Not the driver.
- **Futures paper_max_hold ~30m cap — still clipping rare winners.** Only 29/1,473 reach it (stops fire first at 2–10m holds), but those 29 avg **+39.2% realized**. Cap is leaving the biggest winners on the table.

**What we should change:**
1. **Options: fix the fee model first (ENGINE BUG).** Charge on premium/stake, not notional. At ~$0.60 flat fee the lane is dead regardless of signal — gross is already ~breakeven.
2. **Futures: attack entries + cap leverage ≤10× (STRATEGY).** Unchanged; the +1.44%-peak `paper_stop` cohort keeps pointing here. Kill/throttle FUT_MOMENTUM_CONF + FUT_DONCHIAN_100X (together −$17,463 = 65% of futures loss). The new `FUT_SFP_15X` lane is a step in this direction — let it accumulate n before judging.
3. **Loosen `paper_max_hold`** — the 29 trades that reached it avg +39% realized.

**Verdict status:** unchanged. #8 (aggressive futures) **DEAD** (now −$26.9k, n=1,473). #6 (OTM option selling) **break-even / fee-capped** — flagged as engine fee bug, not just "no edge" (gross ~flat, fees ~100% of loss). #5 still dead. New: low-leverage `FUT_SFP_15X` + V3 option lanes deployed this gap — too few closed trades for any verdict.

### 2026-06-10 05:33 UTC — check-in `[updated by: Cowork]`

**What's happening:** Bot LIVE OFF (`is_paused=true`, "PAPER-ONLY mode"; `bot_state=paused`, uptime ~7.96h → restarted right around last check). 2 act
### 2026-06-10 06:39 UTC — check-in `[updated by: Cowork]`

**What's happening:** Bot LIVE OFF (`is_paused=true`, `bot_state=paused`, "PAPER-ONLY mode"; uptime ~49.8 min → **restarted ~05:49 UTC**, right after last check). 2 active strategies (scalp + options_scalp), delta balance $27.08, regime TRENDING_DOWN, chop 0.50. Open now: **3 futures** (2 SFP_15X, 1 VWAP_10X), **1 option** (OPT_SELL_CALL_V3). Total_pnl field −$54.28.

**What happened since last check (gap ~1.1h since 06-10 05:33):** A restart, not real trading. The numbers are dominated by an orphan flush.
- **Futures:** +40 closed, **−$56.41** (n=1,521→**1,561**; net −$26,895.24→**−$26,951.65**).
- **Options SELL:** +61 closed, **−$0.22** (n=755→**816**; net −$431.67→**−$431.89**; basically flat).

**The new thing — this hour is a restart-orphan flush, not strategy PnL.**
- Options: the +61 new closes **exactly equal** the `restart_orphan` count (61, avg hold 138.6m). Every new option close this gap is the ~05:49 restart flushing open positions at ~$0 — hence net moved −$0.22.
- Futures: +40 closes = ~29 `restart_orphan` (+$81.03 net, avg real +1.25%) + ~10–11 `paper_stop` (−$62). The big legacy lanes confirm it: MOMENTUM_CONF (−11,581.42), DONCHIAN_100X (−5,812.28), DONCHIAN_50X (−3,028.07) all show **identical net to the cent** as last check despite +2 to +7 new closes each → those new closes carried ~$0 (orphan flushes), not live exits. **No real burn this hour; the high-lev book did not genuinely re-engage.**

**Per-lane — Futures (n=1,561):**

| Lane | Closed | Win% | Net | Avg lev | Avg peak% | Hold |
|---|---|---|---|---|---|---|
| FUT_MOMENTUM_CONF | 629 | 14.5 | −11,581.42 | 67.6 | 8.83 | 4.9m |
| FUT_DONCHIAN_100X | 176 | 15.9 | −5,812.28 | 100 | 9.46 | 2.2m |
| FUT_DONCHIAN_CONF | 168 | 23.2 | −3,493.84 | 56.1 | 7.15 | 5.4m |
| FUT_DONCHIAN_50X | 167 | 21.0 | −3,028.07 | 50 | 6.80 | 4.7m |
| FUT_EMA_CONF | 355 | 34.4 | −2,877.24 | 29.5 | 5.47 | 15.6m |
| FUT_EMA_PB_20X | 13 | 23.1 | −56.73 | 20 | 4.56 | 37.0m |
| FUT_DONCHIAN_RT_10X | 12 | 8.3 | −45.44 | 10 | 1.51 | 30.7m |
| FUT_EMA_PB_10X | 13 | 30.8 | −26.73 | 10 | 2.33 | 36.5m |
| FUT_SFP_15X | 20 | 25.0 | −20.57 | 15 | 4.02 | 30.5m |
| FUT_VWAP_10X | 8 | 37.5 | −9.34 | 10 | 3.04 | 52.7m |

Sane-lev cohort (10–20×) combined ≈ **−$159** across 66 closed — still pennies vs the −$26.8k high-lev book. n per lane still 8–20 → no verdict.

**Per-lane — Options SELL (n=816):** PUT_FAR −101.48 (8.1%), PUT −96.97 (14.0%), CALL −92.40 (19.4%), NEUTRAL −77.58 (16.2%), CALL_FAR −55.38 (19.1%), CALL_V3 −3.12 (n=9, 55.6%), RANGE_V3 −2.87 (n=4), PUT_V3 −2.09 (n=2). V3 lanes still near-zero n.

**Exit-reason split — entry-quality thesis still ironclad (FUT, n=1,561):**

| Exit | Closed | Net | Avg peak% | Avg real% |
|---|---|---|---|---|
| **paper_stop** | 867 | **−30,319.21** | +1.41 | −8.17 |
| paper_trail | 565 | **+1,595.50** | +15.71 | +7.04 |
| paper_max_hold | 29 | **+2,436.52** | +47.40 | +39.21 |
| restart_orphan | 29 | +81.03 | +2.20 | +1.25 |
| ema21_lost/reclaimed | 58 | −693.49 | ~2.1 | ~−2.3 |

`paper_stop` = 867 / −$30,319 (still larger than the whole book). Stopped trades avg peak just **+1.41%** before dying −8.17% realized = wrong-direction entries under leverage. Trail (+$1,596) and max_hold (29 runners, +39.2% real) remain the only green. Exit logic fine; entries are the problem.

**Engine-bug status (vs known issues 2026-06-06):**
- **Option-sell fee drag — STILL PRESENT.** Avg fee $0.604 × 816 ≈ **$493 in fees** vs net −$431.89 → **gross ≈ +$61 (positive).** Fees remain >100% of the loss; lane is fee-killed, not signal-dead. Charged on underlying notional. Unchanged.
- **`sell_breached` premature-exit — still FIXED.** 76/816 (9.3%), 11.3m avg hold; `sell_take_profit` dominates (515, 36.0m). Not the driver.
- **Futures `paper_max_hold` ~30m cap — still APPEARS LOOSENED.** Count frozen at 29; new sane-lev lanes holding 30–53 min (VWAP_10X 52.7m, EMA_PB_20X 37.0m, EMA_PB_10X 36.5m) and exiting via stop/trail, not the cap. Good.

**What we should change:**
1. **Investigate the restart cadence (possible ENGINE/OPS issue).** Bot has now restarted at ~05:49 after a 05:33 check that already noted a ~7.96h uptime restart — frequent restarts flush open positions as `restart_orphan` and pollute the closed-trade stream (122 orphan closes total across both books). Confirm restarts are intentional, not a crash loop.
2. **Options: fix the fee model (ENGINE BUG).** Charge on premium/stake, not notional. Gross is now slightly positive; fees alone kill it.
3. **Let sane-lev lanes accumulate; keep high-lev legacy dark.** No genuine high-lev closes this gap (net unchanged to the cent). Need hundreds of low-lev closes before any verdict.

**Verdict status:** unchanged. #8 (aggressive high-lev futures) **DEAD** (−$26.95k, n=1,561), effectively idle — no real closes this gap. #6 (OTM option selling) **fee-capped, gross ~flat-to-slightly-positive** — engine fee bug. Low-leverage cohort (10–20×) live, bleeding only pennies (n ≤20/lane) — too few closes for a verdict. This hour = restart-orphan flush, no new signal.

### 2026-06-10 07:39 UTC — check-in `[updated by: Cowork]`

**What's happening:** Bot LIVE OFF (`is_paused=true`, `bot_state=paused`, "PAPER-ONLY mode"; uptime 6,591s ≈ 1.83h → restart ~05:49 UTC, the SAME session as the 06:39 check — **no new restart this hour**). Scalp + options_scalp enabled. Regime flipped **TRENDING_DOWN → TRENDING_UP**, chop 0.50 → 0.643. total_pnl field −$54.13. Open now: **37 futures + 61 options SELL = 98 open** (vs 06:39's 3 FUT / 1 OPT) — see "the new thing": these are the readmitted restart orphans.

**What happened since last check (gap ~1h since 06:39):** The 06:39 restart-orphan flush has UNWOUND. Authoritative closed-only figures:
- **Futures:** closed **1,537**, net **−$27,041.33** (fees $21,905, avg $14.25/trade). The 06:39 entry reported 1,561 closed / −$26,951.65 — closed count **dropped 24** because the 29 `restart_orphan` "closes" it recorded reverted to open. Against the last GENUINE baseline (06-09 21:39: 1,473 closed / −$26,867.65) real trading is **+64 closed / −$173.68** over ~10h.
- **Options SELL:** closed **756**, net **−$430.61** (fees $456.23, avg $0.603). 06:39 reported "816" = 756 closed + 61 open counted as one number; the 61 `restart_orphan` option closes also reverted to open. Real movement vs 06-09 21:39 (≈755 closed / −$423.24): **+1 closed / −$7.37.** Flat.

**Per-lane — Futures (n=1,537):** _(per-lane table truncated by an overlapping Cowork rewrite; see the 08:39 / 10:39 entries below for current per-lane figures.)_

### 2026-06-10 08:39 UTC — check-in `[updated by: Cowork]`

**What's happening:** Bot LIVE OFF (`is_paused=true`, `bot_state=paused`, "PAPER-ONLY mode"; uptime 10,192s ≈ 2.83h → restart ~05:49 UTC — SAME session as the 06:39 & 07:39 checks, **no new restart this hour**). Scalp + options_scalp enabled, active_strategy_count 2. Regime flipped back **TRENDING_UP → TRENDING_DOWN**, chop 0.643 → 0.536. delta_balance $27.08, total_pnl field −$54.28. Open now: **33 futures + 65 options SELL = 98 open** (vs 07:39's 37/61).

**What happened since last check (gap ~1h since 07:39):** First genuinely clean hour in three — no orphan flush, no reversal. Closed-only authoritative figures:
- **Futures:** closed **1,547**, net **−$27,067.69** (fees $21,919, avg $14.17/trade). vs 07:39 (1,537 / −$27,041.33): **+10 closed / −$26.36.**
- **Options SELL:** closed **756**, net **−$430.61** — **identical to 07:39 to the cent.** Zero options closes this hour; book fully idle (open rose 61→65).

_(08:39 narrative truncated by an overlapping Cowork rewrite; the 10:39 entry below supersedes it.)_

### 2026-06-10 10:39 UTC — check-in `[updated by: Cowork]`

**What's happening:** Bot LIVE OFF (`is_paused=true`, `bot_state=paused`, "PAPER-ONLY mode"; uptime 17,393s ≈ 4.83h → restart ~05:49 UTC — STILL the same session as the 06:39/07:39/08:39 checks, no new restart). Scalp + options_scalp enabled, active_strategy_count 2. Regime TRENDING_UP, chop 0.571, atr_ratio 1.01, net_change_30m +0.368. total_pnl field −$54.13, delta_balance $27.08. Live scan book empty (0/3 slots). Paper book open now: **7 futures + 3 options = 10 open** (orphans from prior restarts are now `status='cancelled'`: 29 FUT / 61 OPT, cleanly excluded from closed). Note: ~2h gap since last entry (08:39); the 09:39 slot was not logged.

**What happened since last check (vs 08:39 baseline, ~2h):** Closed-only authoritative figures.
- **Futures:** closed **1,561**, net **−$27,069.30** (fees $21,936.75, avg $14.05/trade). vs 08:39 (1,547 / −$27,067.69): **+14 closed / −$1.61** over ~2h (≈7 closes/hr).
- **Options SELL:** closed **760**, net **−$447.64** (fees $459.02, avg $0.604). vs 08:39 (756 / −$430.61): **+4 closed / −$17.03.** Options book re-engaged after being fully idle at 08:39.

**The new thing — second straight hour with the high-lev book frozen to the cent, but options took a REAL (non-fee) loss.** All 5 high-lev legacy lanes match 08:39 exactly (MOMENTUM_CONF 622/−11,650.35, DONCHIAN_100X 174/−5,812.28, DONCHIAN_CONF 166/−3,495.99, DONCHIAN_50X 165/−3,028.07, EMA_CONF 346/−2,880.96 — unchanged). Every one of the +14 futures closes again came from the 10–20× cohort. More interesting: the +4 option closes lost **−$17.03 with only ≈$2.4 of fees on them → gross ≈ −$14.6**. So for the first time this session the option lane bled *directional* money, not just fee drag — small n (4), but it breaks the "purely fee-killed" read for this window.

**Per-lane — Futures (n=1,561):**

| Lane | Closed | Win% | Net | Avg lev | Avg peak% | Hold |
|---|---|---|---|---|---|---|
| FUT_MOMENTUM_CONF | 622 | 14.1 | −11,650.35 | 67.6 | 8.87 | 4.9m |
| FUT_DONCHIAN_100X | 174 | 16.1 | −5,812.28 | 100 | 9.57 | 2.2m |
| FUT_DONCHIAN_CONF | 166 | 22.9 | −3,495.99 | 56.2 | 7.23 | 5.4m |
| FUT_DONCHIAN_50X | 165 | 21.2 | −3,028.07 | 50 | 6.88 | 4.8m |
| FUT_EMA_CONF | 346 | 34.4 | −2,880.96 | 29.6 | 5.57 | 10.3m |
| FUT_EMA_PB_20X | 17 | 11.8 | −67.93 | 20 | 5.78 | 37.7m |
| FUT_DONCHIAN_RT_10X | 19 | 15.8 | −51.52 | 10 | 2.44 | 33.7m |
| FUT_SFP_15X | 26 | 23.1 | −42.36 | 15 | 4.11 | 29.1m |
| FUT_EMA_PB_10X | 16 | 25.0 | −31.85 | 10 | 2.97 | 40.8m |
| FUT_VWAP_10X | 10 | 40.0 | −8.00 | 10 | 4.14 | 44.9m |

Sane-lev cohort (10–20×): **88 closed, −$201.66 combined** (vs 74 / −$200.04 at 08:39 → +14 closed, −$1.62). Per-lane deltas: VWAP_10X +$4.97 (best, now 40% win), EMA_PB_10X +$1.12, DONCHIAN_RT_10X +$0.75, EMA_PB_20X −$1.35, SFP_15X −$7.11 (worst). Loss-per-trade improved to ≈−$0.12 this window, but every lane is still net-negative and n ≤26/lane → no verdict.

**Per-lane — Options SELL (n=760):** PUT_FAR 176/−99.88 (7.4%), CALL 148/−96.53 (14.9%), PUT 183/−92.57 (13.7%), NEUTRAL 160/−75.00 (15.6%), CALL_FAR 75/−57.15 (13.3%), RANGE_V3 5/−13.26 (20.0%), PUT_V3 4/−8.90 (0%), CALL_V3 9/−4.33 (44.4%). Avg peak 0.14–0.83% everywhere — still no directional edge. V3 lanes (RANGE/PUT) drifted more negative this window — the −$17 movement lands mostly in legacy + V3 buckets.

**Exit-reason split — Futures (n=1,561):**

| Exit | Closed | Net | Avg peak% | Avg real% |
|---|---|---|---|---|
| **paper_stop** | 877 | **−30,365.36** | +1.41 | −8.12 |
| paper_trail | 574 | **+1,611.11** | +15.59 | +6.98 |
| paper_max_hold | 29 | **+2,436.52** | +47.40 | +39.21 |
| ema21_lost | 33 | −403.22 | +1.86 | −2.39 |
| ema21_reclaimed | 25 | −290.27 | +2.43 | −2.14 |
| breakeven_stop | 17 | −5.01 | +4.76 | +1.15 |
| donchian_mid_revert | 3 | −45.43 | +5.75 | −3.56 |
| stagnant_exit | 2 | −3.83 | +2.48 | −0.42 |
| no_traction | 1 | −3.81 | +0.87 | −2.81 |

The +14 closes split: **+3 paper_stop (−$11.86), +4 paper_trail (+$15.60), +6 breakeven_stop (−$1.54), +1 no_traction (−$3.81).** Trail just out-earned the stops this window → net ≈flat. paper_stop still 877 / −$30,365 (> the entire −$27.1k book), peak +1.41% before −8.12% realized = wrong-direction entries. Trail (+$1,611) and the 29 max_hold runners (+39.2% real) remain the only green. `restart_orphan` absent (orphans parked as cancelled).

**Engine-bug status (vs known issues 2026-06-06):**
- **Closed-trade ledger mutability — HANDLED/dormant this window.** Orphans now carry `status='cancelled'` (29 FUT / 61 OPT) and are excluded from closed counts — no closed↔open toggling, uptime continuous. Bug unexercised; treatment of orphans as cancelled (not closed) is the correct behavior. Keep monitoring across the next restart.
- **Option-sell fee drag — STILL PRESENT.** Fees $459.02 vs net −$447.64 → gross ≈ **+$11.38 (still positive overall)**, but this window's 4 closes were gross-negative (≈−$14.6), so fees are no longer the *only* problem — small-n directional loss appeared. Charged on underlying notional. Unchanged structurally.
- **`sell_breached` premature-exit — still FIXED.** 78/760 (10.3%) at 12.5m; `sell_take_profit` dominates (515, 36.0m). Not the driver.
- **Futures `paper_max_hold` ~30m cap — still LOOSENED.** Count frozen at 29; sane-lev lanes holding 29–45m (VWAP 44.9m, EMA_PB_10X 40.8m, EMA_PB_20X 37.7m, DONCHIAN_RT 33.7m) exiting via stop/trail, not the cap. Good.

**What we should change:**
1. **Sane-lev lanes still NO edge after ~5h of clean data — flag, don't celebrate.** 88 closed / −$201, every lane net-negative. Loss-per-trade is now tiny (≈−$0.12 this window) but sign hasn't flipped. Low leverage fixed the *magnitude*, not the *entry signal*. Keep accumulating toward hundreds/lane.
2. **Watch the options lane for genuine signal decay (STRATEGY).** First gross-negative option window this session. If gross stays negative as n grows, the lane is not merely fee-capped — it's a losing strategy. Re-check next hour before concluding (n=4 is noise).
3. **Futures: attack ENTRY quality (STRATEGY).** paper_stop 877 / −$30,365 at +1.41% avg peak. Kill/throttle MOMENTUM_CONF + DONCHIAN_100X (−$17,463 = 65% of futures loss); they're frozen/idle now but will resume burning if re-enabled.
4. **Options: fix the fee model (ENGINE BUG).** Charge on premium/stake, not notional.

**Verdict status:** unchanged. #8 (aggressive high-lev futures) **DEAD** (−$27.07k, n=1,561), idle this window (frozen to the cent for the 2nd straight hour). #6 (OTM option selling) **fee-capped overall but gross-negative this window** — watch for signal decay. Low-leverage cohort (10–20×): **88 closed / −$202, still net-negative, no edge** — n ≤2
### 2026-06-10 11:39 UTC — check-in `[updated by: Cowork]`

**What's happening:** Bot LIVE OFF (`is_paused=true`, `bot_state=paused`, "PAPER-ONLY mode"; uptime 20,992s ≈ 5.83h → restart ~05:49 UTC — STILL the same session as the 06:39/07:39/08:39/10:39 checks, no new restart). Scalp + options_scalp enabled, active_strategy_count 2. Regime flipped back **TRENDING_UP → TRENDING_DOWN** (regime_since 11:04), chop 0.464, atr_ratio 1.00, net_change_30m −0.121. total_pnl field −$54.13, delta_balance $27.08. Live scan book empty (0/3). Paper book open now: **4 futures + 2 options = 6 open** (orphans parked `cancelled`).

**What happened since last check (vs 10:39 baseline, ~1h):** Closed-only authoritative figures.
- **Futures:** closed **1,569**, net **−$27,094.08** (fees $21,947.75, avg $13.99/trade). vs 10:39 (1,561 / −$27,069.30): **+8 closed / −$24.78** (≈8 closes/hr).
- **Options SELL:** closed **764**, net **−$453.42** (fees $461.81, avg $0.604). vs 10:39 (760 / −$447.64): **+4 closed / −$5.78.**

**The new thing — THIRD straight hour with the high-lev book frozen to the cent; the entire futures loss came from the sane-lev cohort, and its loss-per-trade just got WORSE.** All 5 high-lev legacy lanes match 10:39 exactly (MOMENTUM_CONF 622/−11,650.35, DONCHIAN_100X 174/−5,812.28, DONCHIAN_CONF 166/−3,495.99, DONCHIAN_50X 165/−3,028.07, EMA_CONF 346/−2,880.96 — unchanged). Every one of the +8 futures closes came from the 10–20× cohort, which moved **88 → 96 closed / −$201.66 → −$226.43 = +8 / −$24.77** — i.e. **−$3.1/trade this window vs −$0.12 last window.** Worst sane-lev window of the session. On options, all +4 closes landed in **V3 lanes only** (RANGE_V3 +2, CALL_V3 +2); the 5 legacy option lanes are frozen to the cent. The +4 lost −$5.78 on ≈$2.8 fees → gross ≈ −$3.0 — **second straight gross-negative option window**, still tiny n.

**Per-lane — Futures (n=1,569):**

| Lane | Closed | Win% | Net | Avg lev | Avg peak% | Hold |
|---|---|---|---|---|---|---|
| FUT_MOMENTUM_CONF | 622 | 14.1 | −11,650.35 | 67.6 | 8.87 | 4.9m |
| FUT_DONCHIAN_100X | 174 | 16.1 | −5,812.28 | 100 | 9.57 | 2.2m |
| FUT_DONCHIAN_CONF | 166 | 22.9 | −3,495.99 | 56.2 | 7.23 | 5.4m |
| FUT_DONCHIAN_50X | 165 | 21.2 | −3,028.07 | 50 | 6.88 | 4.8m |
| FUT_EMA_CONF | 346 | 34.4 | −2,880.96 | 29.6 | 5.57 | 10.3m |
| FUT_EMA_PB_20X | 19 | 10.5 | −80.98 | 20 | 5.58 | 41.6m |
| FUT_DONCHIAN_RT_10X | 19 | 15.8 | −51.52 | 10 | 2.44 | 33.7m |
| FUT_SFP_15X | 28 | 28.6 | −38.95 | 15 | 4.56 | 29.9m |
| FUT_EMA_PB_10X | 18 | 22.2 | −38.47 | 10 | 2.87 | 44.6m |
| FUT_VWAP_10X | 12 | 33.3 | −16.51 | 10 | 3.74 | 45.2m |

Sane-lev cohort (10–20×): **96 closed, −$226.43 combined.** Per-lane deltas vs 10:39: SFP_15X +$3.41 (only green; n 26→28), EMA_PB_10X −$6.62, VWAP_10X −$8.51, EMA_PB_20X −$13.05 (worst, win% slid 11.8→10.5), DONCHIAN_RT_10X flat. Every lane still net-negative, n ≤28/lane → no verdict.

**Per-lane — Options SELL (n=764):** PUT_FAR 176/−99.88 (7.4%), CALL 148/−96.53 (14.9%), PUT 183/−92.57 (13.7%), NEUTRAL 160/−75.00 (15.6%), CALL_FAR 75/−57.15 (13.3%), RANGE_V3 7/−15.41 (14.3%), PUT_V3 4/−8.90 (0%), CALL_V3 11/−7.96 (36.4%). Avg peak 0.14–0.97% — no directional edge. The −$5.78 this window is entirely V3 drift (RANGE_V3 −$2.15, CALL_V3 −$3.63); legacy lanes flat to the cent.

**Exit-reason split — Futures (n=1,569):**

| Exit | Closed | Net | Avg peak% | Avg real% |
|---|---|---|---|---|
| **paper_stop** | 880 | **−30,391.86** | +1.41 | −8.11 |
| paper_trail | 576 | **+1,614.51** | +15.58 | +6.96 |
| paper_max_hold | 29 | **+2,436.52** | +47.40 | +39.21 |
| ema21_lost | 33 | −403.22 | +1.86 | −2.39 |
| ema21_reclaimed | 25 | −290.27 | +2.43 | −2.14 |
| breakeven_stop | 17 | −5.01 | +4.76 | +1.15 |
| stagnant_exit | 5 | −5.51 | +2.28 | +0.30 |
| donchian_mid_revert | 3 | −45.43 | +5.75 | −3.56 |
| no_traction | 1 | −3.81 | +0.87 | −2.81 |

The +8 closes split: **+3 paper_stop (−$26.50), +2 paper_trail (+$3.40), +3 stagnant_exit (−$1.68).** Stops out-bled trail this window → net −$24.78. paper_stop now 880 / −$30,392 (> the entire −$27.1k book), peak +1.41% before −8.11% realized = wrong-direction entries. Trail (+$1,615) and the 29 max_hold runners (+39.2% real) remain the only green. `restart_orphan` absent.

**Options exit-reason (n=764):** sell_take_profit 515/−99.48 (36.0m), sell_stop 159/−244.99 (36.7m), sell_breached 78/−93.85 (12.5m, 10.2%), sell_trend_break 12/−15.10 (70.6m). TP-dominant; stop carries most of the loss.

**Engine-bug status (vs known issues 2026-06-06):**
- **Closed-trade ledger mutability — dormant.** No restart this hour (uptime continuous ≈5.83h); orphans stay `cancelled`, no closed↔open toggling. Keep monitoring across the next restart.
- **Option-sell fee drag — STILL PRESENT.** Fees $461.81 vs net −$453.42 → gross ≈ **+$8.39 overall (still positive)**, but this window's 4 closes were gross-negative (≈−$3.0) for the 2nd straight hour. Charged on underlying notional. Unchanged structurally.
- **`sell_breached` premature-exit — still FIXED.** 78/764 (10.2%) at 12.5m; sell_take_profit dominates (515). Not the driver.
- **Futures `paper_max_hold` ~30m cap — still LOOSENED.** Count frozen at 29; sane-lev lanes holding 30–45m (VWAP 45.2m, EMA_PB_10X 44.6m, EMA_PB_20X 41.6m) exiting via stop/trail, not the cap. Good.

**What we should change:**
1. **Sane-lev cohort loss-per-trade WORSENED this window — escalate the flag.** 96 closed / −$226, −$3.1/trade vs −$0.12 last hour. Two clean hours don't make a trend, but the direction is wrong; the low-lev rebuild fixed magnitude, not entry signal. Keep accumulating, do not soften the "no edge" read.
2. **Options: 2nd straight gross-negative window (STRATEGY watch).** Overall still fee-capped/positive gross, but back-to-back gross-negative closes (now isolated to V3 lanes) suggest possible signal decay. n still tiny (4/window) — re-check next hour before concluding.
3. **Futures: attack ENTRY quality (STRATEGY).** paper_stop 880 / −$30,392 at +1.41% avg peak. MOMENTUM_CONF + DONCHIAN_100X (−$17,463 = 64% of futures loss) stay frozen/idle — keep them dark; they'll resume burning if re-enabled.
4. **Options: fix the fee model (ENGINE BUG).** Charge on premium/stake, not notional.

**Verdict status:** unchanged. #8 (aggressive high-lev futures) **DEAD** (−$27.09k, n=1,569), idle — frozen to the cent for the 3rd straight hour. #6 (OTM option selling) **fee-capped overall, gross-negative for the 2nd straight window** — watch for decay. Low-leverage cohort (10–20×): **96 closed / −$226, net-negative, loss-per-trade worsened, no edge** — n ≤28/lane, far from a verdict. No strategy crowned; not enough closes.

### 2026-06-10 12:39 UTC — check-in `[updated by: Cowork]`

**What's happening:** Bot LIVE OFF (`is_paused=true`, `bot_state=paused`, "PAPER-ONLY mode"; uptime 24,593s ≈ 6.83h → restart ~05:49 UTC — STILL the same session as the 06:39/07:39/08:39/10:39/11:39 checks, no new restart, continuous). Scalp + options_scalp enabled, active_strategy_count 2. Regime flipped **TRENDING_DOWN → CHOPPY** (regime_since 12:34), chop 0.643, atr_ratio 1.87, net_change_30m +1.049. total_pnl field −$54.13, delta_balance $27.08. Live scan book empty (0/3). Paper book open now: **6 futures + 1 option = 7 open** (orphans parked `cancelled`: 29 FUT / 61 OPT).

**What happened since last check (vs 11:39 baseline, ~1h):** Closed-only authoritative figures.
- **Futures:** closed **1,575**, net **−$27,167.83** (fees $21,956.25, avg $13.94/trade). vs 11:39 (1,569 / −$27,094.08): **+6 closed / −$73.75** (≈6 closes/hr).
- **Options SELL:** closed **766**, net **−$459.11** (fees $463.20, avg $0.605). vs 11:39 (764 / −$453.42): **+2 closed / −$5.69.**

**The new thing — FOURTH straight hour with the high-lev book frozen to the cent, and the sane-lev cohort's loss-per-trade just blew out to its worst of the session.** All 5 high-lev legacy lanes match 11:39 exactly (MOMENTUM_CONF 622/−11,650.35, DONCHIAN_100X 174/−5,812.28, DONCHIAN_CONF 166/−3,495.99, DONCHIAN_50X 165/−3,028.07, EMA_CONF 346/−2,880.96 — unchanged). Every one of the +6 futures closes came from the 10–20× cohort, which moved **96 → 102 closed / −$226.43 → −$300.18 = +6 / −$73.75 = −$12.29/trade** — vs −$3.1 (11:39) and −$0.12 (10:39). Three windows, monotonically worse. And for the first time the +2 `paper_trail` closes this window were *net-negative* (trail net 1,614.51 → 1,605.51, −$9.00) — even the only structurally-green futures exit lost money this hour. On options, both +2 closes were CALL_V3; the −$5.69 on ≈$1.2 fees → gross ≈ −$4.5, the **third straight gross-negative options window**, still isolated to V3 lanes, still tiny n.

**Per-lane — Futures (n=1,575):**

| Lane | Closed | Win% | Net | Avg lev | Avg peak% | Hold |
|---|---|---|---|---|---|---|
| FUT_MOMENTUM_CONF | 622 | 14.1 | −11,650.35 | 67.6 | 8.87 | 4.9m |
| FUT_DONCHIAN_100X | 174 | 16.1 | −5,812.28 | 100 | 9.57 | 2.2m |
| FUT_DONCHIAN_CONF | 166 | 22.9 | −3,495.99 | 56.2 | 7.23 | 5.4m |
| FUT_DONCHIAN_50X | 165 | 21.2 | −3,028.07 | 50 | 6.88 | 4.8m |
| FUT_EMA_CONF | 346 | 34.4 | −2,880.96 | 29.6 | 5.57 | 10.3m |
| FUT_EMA_PB_20X | 21 | 9.5 | −115.45 | 20 | 5.56 | 43.5m |
| FUT_SFP_15X | 29 | 27.6 | −55.29 | 15 | 4.48 | 29.4m |
| FUT_EMA_PB_10X | 20 | 20.0 | −53.90 | 10 | 2.81 | 46.4m |
| FUT_DONCHIAN_RT_10X | 19 | 15.8 | −51.52 | 10 | 2.44 | 33.7m |
| FUT_VWAP_10X | 13 | 30.8 | −24.02 | 10 | 3.69 | 44.4m |

Sane-lev cohort (10–20×): **102 closed, −$300.18 combined.** Per-lane deltas vs 11:39: DONCHIAN_RT_10X flat (0 closes); **every lane that moved was red** — VWAP_10X −$7.51, EMA_PB_10X −$15.43, SFP_15X −$16.34, EMA_PB_20X −$34.47 (worst, n 19→21, win% 10.5→9.5). Zero green lanes this window. Every lane still net-negative, n ≤29/lane → no verdict.

**Per-lane — Options SELL (n=766):** PUT_FAR 176/−99.88 (7.4%), CALL 148/−96.53 (14.9%), PUT 183/−92.57 (13.7%), NEUTRAL 160/−75.00 (15.6%), CALL_FAR 75/−57.15 (13.3%), RANGE_V3 7/−15.41 (14.3%), CALL_V3 13/−13.66 (30.8%), PUT_V3 4/−8.90 (0%). Avg peak 0.14–1.04% — no directional edge. The −$5.69 this window is entirely CALL_V3 (+2 / −$5.70); all 5 legacy lanes and RANGE_V3/PUT_V3 flat to the cent.

**Exit-reason split — Futures (n=1,575):**

| Exit | Closed | Net | Avg peak% | Avg real% |
|---|---|---|---|---|
| **paper_stop** | 884 | **−30,456.61** | +1.42 | −8.14 |
| paper_trail | 578 | **+1,605.51** | +15.54 | +6.93 |
| paper_max_hold | 29 | **+2,436.52** | +47.40 | +39.21 |
| ema21_lost | 33 | −403.22 | +1.86 | −2.39 |
| ema21_reclaimed | 25 | −290.27 | +2.43 | −2.14 |
| donchian_mid_revert | 3 | −45.43 | +5.75 | −3.56 |
| stagnant_exit | 5 | −5.51 | +2.28 | +0.30 |
| breakeven_stop | 17 | −5.01 | +4.76 | +1.15 |
| no_traction | 1 | −3.81 | +0.87 | −2.81 |

The +6 closes split: **+4 paper_stop (−$64.75), +2 paper_trail (−$9.00).** Stops bled and trail did NOT offset (negative trail closes) → net −$73.75. paper_stop now 884 / −$30,457 (> the entire −$27.2k book), peak +1.42% before −8.14% realized = wrong-direction entries. Trail (+$1,606) and the 29 max_hold runners (+39.2% real) remain the only structural green, but trail gave a touch back this window. `restart_orphan` absent.

**Options exit-reason (n=766):** sell_take_profit 515/−99.48 (36.0m), sell_stop 159/−244.99 (36.7m), sell_breached 79/−97.84 (13.3m, 10.3%), sell_trend_break 13/−16.81 (71.0m). TP-dominant; stop carries most of the loss. The +2 closes: 1 sell_breached, 1 sell_trend_break.

**Engine-bug status (vs known issues 2026-06-06):**
- **Closed-trade ledger mutability — dormant.** No restart this hour (uptime continuous ≈6.83h); orphans stay `cancelled` (29 FUT / 61 OPT), no closed↔open toggling. Keep monitoring across the next restart.
- **Option-sell fee drag — STILL PRESENT, and the overall cushion is eroding.** Fees $463.20 vs net −$459.11 → gross ≈ **+$4.09 overall** (down from +$11.38 → +$8.39 → +$4.09 over the last three windows, ≈−$4/window). This window's 2 closes were gross-negative (≈−$4.5) for the 3rd straight hour. At this rate the lane flips gross-negative overall within 1–2 windows. Charged on underlying notional. Unchanged structurally.
- **`sell_breached` premature-exit — still FIXED.** 79/766 (10.3%) at 13.3m; sell_take_profit dominates (515, 36.0m). Not the driver.
- **Futures `paper_max_hold` ~30m cap — still LOOSENED.** Count frozen at 29; sane-lev lanes holding 29–46m (EMA_PB_10X 46.4m, VWAP 44.4m, EMA_PB_20X 43.5m) exiting via stop/trail, not the cap. Good.

**What we should change:**
1. **Sane-lev cohort loss-per-trade worsened for the 3rd straight window — this is now a direction, not noise.** 102 closed / −$300; −$12.29/trade vs −$3.1 vs −$0.12. Low-lev fixed magnitude, not entry signal, and the per-trade gap is widening as regime chops. Keep accumulating but do NOT soften the "no edge" read — if anything, the signal looks worse in chop.
2. **Options: 3rd straight gross-negative window AND the overall gross cushion is nearly gone (STRATEGY + watch).** Overall gross +$4.09 and falling ~$4/window. If next check shows gross ≤ 0 overall, the lane is a losing strategy, not merely fee-capped. Re-check next hour — likely the decision point.
3. **Futures: attack ENTRY quality (STRATEGY).** paper_stop 884 / −$30,457 at +1.42% avg peak. MOMENTUM_CONF + DONCHIAN_100X (−$17,463 = 64% of futures loss) stay frozen/idle — keep them dark; they resume burning if re-enabled.
4. **Options: fix the fee model (ENGINE BUG).** Charge on premium/stake, not notional — this is the lever that keeps the lane positive; the cushion is now thin enough that it matters this hour.

**Verdict status:** unchanged. #8 (aggressive high-lev futures) **DEAD** (−$27.17k, n=1,575), idle — frozen to the cent for the 4th straight hour. #6 (OTM option selling) **gross-positive overall but cushion eroding ~$4/window, 3rd straight gross-negative window** — approaching a verdict, re-check next hour. Low-leverage cohort (10–20×): **102 closed / −$300, net-negative, loss-per-trade worsening (−$12.29/trade this window), no edge** — n ≤29/lane, far from a verdict. No strategy crowned; not enough closes.

### 2026-06-10 13:40 UTC — check-in `[updated by: Cowork]`

**What's happening:** Bot LIVE OFF (`is_paused=true`, `bot_state=paused`, "PAPER-ONLY mode"; uptime 28,190s ≈ 7.83h → restart ~05:50 UTC — STILL the same continuous session as the 06:39 through 12:39 checks, no new restart, 5th+ straight hour). Scalp + options_scalp enabled, active_strategy_count 2. Regime flipped **CHOPPY → TRENDING_UP** (regime_since 13:30), chop 0.50 (down from 0.643), atr_ratio 1.73, net_change_30m +1.513. total_pnl field −$54.13, delta_balance $27.08. Live scan book empty (0/3). Paper book open now: **6 futures + 2 options = 8 open** (orphans parked `cancelled`: 29 FUT / 61 OPT).

**What happened since last check (vs 12:39 baseline, ~1h):** Closed-only authoritative figures.
- **Futures:** closed **1,575**, net **−$27,167.83** (unchanged to the cent). vs 12:39 (1,575 / −$27,167.83): **0 closed / $0.00.** Entire futures book froze this window — zero closes in ANY lane, high-lev AND sane-lev.
- **Options SELL:** closed **768**, net **−$455.82** (fees $464.61). vs 12:39 (766 / −$459.11): **+2 closed / +$3.29** (both winners).

**The new thing — the entire futures book went flat (0 closes, first such window), while options printed its first gross-positive window in four.** All 1,575 futures rows match 12:39 to the cent across every lane and every exit reason (paper_stop 884/−30,456.61, paper_trail 578/+1,605.51, paper_max_hold 29/+2,436.52, all identical) — 6 positions sit open but none closed in the last hour, so the sane-lev "loss-per-trade worsening" trend from the prior three windows is **paused, not resolved** (no new data). On options, both +2 closes were `sell_take_profit` winners (517 now vs 515; TP net −99.48 → −96.19 = +$3.29). That reverses the 3-window gross-cushion erosion: **gross ≈ +$8.79** (fees $464.61, net −$455.82), up from +$4.09 at 12:39. The two new closes were gross-positive (≈+$4.70 gross combined). The decay thesis flagged last hour did NOT play out this window.

**Per-lane — Futures (n=1,575, unchanged vs 12:39):**

| Lane | Closed | Win% | Net | Avg lev | Avg peak% | Hold |
|---|---|---|---|---|---|---|
| FUT_MOMENTUM_CONF | 622 | 14.1 | −11,650.35 | 67.6 | 8.87 | 4.9m |
| FUT_DONCHIAN_100X | 174 | 16.1 | −5,812.28 | 100 | 9.57 | 2.2m |
| FUT_DONCHIAN_CONF | 166 | 22.9 | −3,495.99 | 56.2 | 7.23 | 5.4m |
| FUT_DONCHIAN_50X | 165 | 21.2 | −3,028.07 | 50 | 6.88 | 4.8m |
| FUT_EMA_CONF | 346 | 34.4 | −2,880.96 | 29.6 | 5.57 | 10.3m |
| FUT_EMA_PB_20X | 21 | 9.5 | −115.45 | 20 | 5.56 | 43.5m |
| FUT_SFP_15X | 29 | 27.6 | −55.29 | 15 | 4.48 | 29.4m |
| FUT_EMA_PB_10X | 20 | 20.0 | −53.90 | 10 | 2.81 | 46.4m |
| FUT_DONCHIAN_RT_10X | 19 | 15.8 | −51.52 | 10 | 2.44 | 33.7m |
| FUT_VWAP_10X | 13 | 30.8 | −24.02 | 10 | 3.69 | 44.4m |

Sane-lev cohort (10–20×): **102 closed, −$300.18 combined — frozen vs 12:39 (no closes).** Every lane net-negative, n ≤29/lane → no verdict. Worsening per-trade trend from prior windows cannot be confirmed or refuted this hour (no new closes).

**Per-lane — Options SELL (n=768):** PUT_FAR 176/−99.88 (7.4%), CALL 148/−96.53 (14.9%), PUT 183/−92.57 (13.7%), NEUTRAL 160/−75.00 (15.6%), CALL_FAR 75/−57.15 (13.3%), RANGE_V3 8/−14.44 (25.0%), CALL_V3 13/−13.66 (30.8%), PUT_V3 5/−6.57 (20.0%). Avg peak 0.14–1.04% — no directional edge. The +$3.29 this window: RANGE_V3 (7→8, +$0.97) and PUT_V3 (4→5, +$2.33), both winning TP closes; all 5 legacy lanes and CALL_V3 flat to the cent.

**Exit-reason split — Futures (n=1,575, unchanged vs 12:39):**

| Exit | Closed | Net | Avg peak% | Avg real% |
|---|---|---|---|---|
| **paper_stop** | 884 | **−30,456.61** | +1.42 | −8.14 |
| paper_trail | 578 | **+1,605.51** | +15.54 | +6.93 |
| paper_max_hold | 29 | **+2,436.52** | +47.40 | +39.21 |
| ema21_lost | 33 | −403.22 | +1.86 | −2.39 |
| ema21_reclaimed | 25 | −290.27 | +2.43 | −2.14 |
| donchian_mid_revert | 3 | −45.43 | +5.75 | −3.56 |
| stagnant_exit | 5 | −5.51 | +2.28 | +0.30 |
| breakeven_stop | 17 | −5.01 | +4.76 | +1.15 |
| no_traction | 1 | −3.81 | +0.87 | −2.81 |

No futures closes this window. paper_stop still 884 / −$30,457 (> the entire −$27.2k book), peak +1.42% before −8.14% realized = wrong-direction entries. Trail (+$1,606) and the 29 max_hold runners (+39.2% real) remain the only structural green. `restart_orphan` absent.

**Options exit-reason (n=768):** sell_take_profit 517/−96.19 (36.1m), sell_stop 159/−244.99 (36.7m), sell_breached 79/−97.84 (13.3m, 10.3%), sell_trend_break 13/−16.81 (71.0m). TP-dominant; stop carries most of the loss. The +2 closes were both sell_take_profit.

**Engine-bug status (vs known issues 2026-06-06):**
- **Closed-trade ledger mutability — dormant.** No restart this hour (uptime continuous ≈7.83h); orphans stay `cancelled` (29 FUT / 61 OPT), no closed↔open toggling. Keep monitoring across the next restart.
- **Option-sell fee drag — STILL PRESENT, but the cushion REBOUNDED.** Fees $464.61 vs net −$455.82 → gross ≈ **+$8.79 overall**, up from +$4.09 (12:39). The erosion alarm from last window (+$11.38 → +$8.39 → +$4.09) reversed — this window's 2 closes were gross-positive TP winners. Decay thesis paused. Fee still charged on underlying notional (~$0.60/trade). Unchanged structurally.
- **`sell_breached` premature-exit — still FIXED.** Frozen at 79/768 (10.3%) at 13.3m; sell_take_profit dominates (517, 36.1m). Not the driver.
- **Futures `paper_max_hold` ~30m cap — still LOOSENED.** Count frozen at 29; moot this window (no futures closes). Sane-lev holds 29–46m by stop/trail, not the cap. Good.

**What we should change:**
1. **Futures: nothing actionable this hour — whole book idle, 0 closes.** High-lev legacy lanes stay dead/dark (MOMENTUM_CONF + DONCHIAN_100X = −$17,463 = 64% of futures loss); they resume burning if re-enabled. Keep them frozen.
2. **Options: decay thesis did NOT confirm — stand down the "approaching a verdict" flag from 12:39.** Gross cushion rebounded to +$8.79 on two TP winners. Lane is back to "fee-capped, gross-positive, watch." Do NOT crown; n per V3 lane still ≤13.
3. **Sane-lev cohort: trend unverifiable this window (0 closes).** Do not soften OR harden the "no edge, loss-per-trade worsening" read — wait for the next window with actual closes before re-judging.
4. **Options: fix the fee model (ENGINE BUG, structural lever).** Charge on premium/stake, not notional. Still the lever that keeps the lane positive even though the cushion recovered this hour.

**Verdict status:** unchanged. #8 (aggressive high-lev futures) **DEAD** (−$27.17k, n=1,575), idle — frozen to the cent for the 5th straight hour, entire book flat this window. #6 (OTM option selling) **gross-positive overall (+$8.79), cushion rebounded, decay thesis unconfirmed** — back to fee-capped/watch, not at a verdict. Low-leverage cohort (10–20×): **102 closed / −$300, net-negative, no closes this window so trend unverifiable, no edge** — n ≤29/lane, far from a verdict. No strategy crowned; not enough closes.

> Note: the 06-10 19:00Z+ V3.1 hourly check-ins (HTF-gate era) live in the git commit log, not appended here. Resuming the in-file log below at 06-11 02:38Z.

### 2026-06-11 02:38 UTC — V3.1 VERIFICATION HOUR 7 — check-in `[updated by: Cowork]`

**Era state (V3 since 2026-06-09 21:21Z, ~29.3h):** Live **OFF** (`is_paused=true`, fresh rows 02:36/02:38Z; 0 `options_scalp` opens last hour ✓). Burns **0** (no refill rows this era). FUNDED $1,000/lab.
- **Futures:** closed-only net **−$496.41** (n=159). BALANCE **$503.59**.
- **Options:** closed-only net **−$43.29** (n=51). BALANCE **$956.71**.

**This hour (vs 01:40 baseline −$487.05/n=156):** futures **−$9.36 / +3 closes**, reconciles to the cent. All 3 closes were **FUT_SFP_15X htf=−1 aligned shorts, ALL `paper_stop`** (−4.17 / −4.52 / −0.68 = −9.37). **2 more SFP_15X htf=−1 shorts opened** (only open positions in the book). **Options 0 closes / unchanged** (−$43.29).

**The signal — now overwhelming, 3rd straight hour:** FUT_SFP_15X is the **ONLY lane traded** again. The HTF gate remains **mechanically flawless** — every close and every open this hour is an aligned htf=−1 short, zero counter-trend leakage (8th+ straight hour). But the gate is funneling **100% of throughput into the single worst lane.** SFP_15X is now **worst net AND worst PF** by a wide margin.

**Per-lane — Futures (era, closed, worst→best net):**

| Lane | n | Win% | Net | PF | Hold |
|---|---|---|---|---|---|
| **FUT_SFP_15X** | 55 | 16 | **−186.24** | **0.15** | 28.6m |
| FUT_EMA_PB_20X *(RETIRED)* | 31 | 16 | −137.58 | 0.26 | 47.2m |
| FUT_EMA_PB_10X | 36 | 22 | −90.32 | 0.23 | 43.4m |
| FUT_DONCHIAN_RT_10X | 25 | 24 | −50.97 | **0.38** (best) | 39.5m |
| FUT_VWAP_10X | 15 | 27 | −33.84 | 0.24 | 43.6m |

FUT_EMA_PB_20X **retirement still sticking** — frozen 31/−137.58 (0 new). SFP_15X overtook it as worst net last hour and extended the gap this hour (−174.35 → −183.71, +9.36 = the entire hour's damage).

**Exit reasons — Futures (era):** `paper_stop` **81 / −571.64** (51% count share; +2 since last snapshot, both SFP), `paper_trail` **40 / +113.89 — FROZEN 3rd straight hour** (gate routes everything into SFP stops; nothing reaches the trail), `breakeven_stop` 28/−17.27, `stagnant_exit` 8/−11.17, `no_traction` 2/−10.23. paper_trail is the ONLY net-green exit and it is starved.

**Options lanes (era, closed):** RANGE_V3 13/−16.61 (PF 0.23, worst net), CALL_V3 24/−16.57 (PF 0.31), PUT_V3 14/−10.11 (**PF 0.51, least-bad**). **DK strangle (DK_PUT/DK_CALL/DK_V3): 0 fills the entire era** — next entry window 06-12 07:30–11:18Z. Headline strangle number still undefined (n=0).

**Engine-bug status:** none. Closes reconcile to the cent (−9.37 ≈ −9.36 move), gate alignment perfect, stops sized correctly (−0.5 to −4.5 per 15× SFP short). The loss is **strategy, not mechanics** — SFP entry quality is the leak; HTF alignment is confirmed NOT to be edge (7 straight hours of aligned-SFP bleeding).

**What we should change:**
1. **URGENT (3rd hour recommending): retire FUT_SFP_15X**, mirroring the FUT_EMA_PB_20X retirement. It is the worst lane on both net (−183.71) and PF (0.14), it is the ONLY lane the gate is feeding, and it is still being traded → the retirement has **not yet been deployed.** A flawless gate cannot rescue a 0.14-PF entry; it just concentrates the bleed.
2. **Leave the other 3 active lanes untouched** — DONCHIAN (best PF 0.38), VWAP (least-bad net), EMA_PB_10X — they're starved of fills but not the problem.
3. **Options:** no action; flat hour, PUT_V3 remains least-bad (PF 0.51). Await DK strangle's first fills (06-12 window) before any options verdict.

**Verdict status:** **HTF alignment is NOT edge — settled.** 7 straight hours of aligned htf=−1 SFP shorts stopping out proves the gate's directional filter works mechanically but adds no expectancy when entry quality is poor. FUT_SFP_15X = retire-now candidate (worst net −183.71, worst PF 0.14). FUT_EMA_PB_20X retirement holding (frozen −137.58). No lane near the PF>1.0 / n~200 live gate; no strategy crowned.

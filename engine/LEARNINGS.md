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

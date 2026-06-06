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

### 2026-06-06 17:10 UTC — first check-in after the reset

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

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
| 6 | **OTM option SELLING** (collect theta/premium) | — | not yet tested | 🧪 TESTING NOW — the logical flip: if buying bleeds theta, selling should harvest it. |
| 7 | **Futures at SANE leverage (3–5×) on trend signals** | — | not yet tested | 🧪 TESTING NOW — strips theta+spread; tests whether the directional reads have any real edge. |

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

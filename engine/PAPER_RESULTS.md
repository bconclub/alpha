# Alpha — Paper Results Snapshot

> Point-in-time dump of paper-lab results, kept in the codebase so we can pull it
> up anytime. Pairs with `LEARNINGS.md` (verdicts/principles). Regenerate by
> re-querying `paper_options_trades` / `paper_futures_trades` and updating below.

## Snapshot — 2026-06-06 (selling + sane-futures round, pre-reset #2)

Both labs reset to $1,000 and ran OPTION SELLING + SANE-LEVERAGE (3–5×) futures. **Both lost.**

### Options — SELLING naked OTM premium
| Lane | Closed | Win% | Net | Max peak |
|---|---|---|---|---|
| OPT_SELL_NEUTRAL | 3 | 0% | −$99.90 | 46% |
| OPT_SELL_PUT | 10 | 0% | −$225.43 | 34% |
| OPT_SELL_CALL | 14 | 0% | −$320.94 | 44% |
| OPT_SELL_CALL_FAR | 14 | 0% | −$368.86 | 44% |
| OPT_SELL_PUT_FAR | 11 | 0% | −$439.43 | 35% |

**0% realized win.** Theta worked — peaks of +34–46% mean the premium WAS decaying in our favor — but every position reversed and hit the −100% stop before the +50% take-profit. Lessons: (1) TP at +50% is too greedy; peaks ~46% reverse → take profit earlier (~+30–35%). (2) Naked short tail risk is brutal in fast crypto → needs **defined-risk spreads** to be viable.

### Futures — sane leverage 3–5×
| Lane | Closed | Win% | Net | Lev | Max peak |
|---|---|---|---|---|---|
| FUT_DONCHIAN_3X | 7 | 14% | −$19.26 | 3× | 4% |
| FUT_DONCHIAN_5X | 7 | 14% | −$23.29 | 5× | 7% |
| FUT_EMA_4X | 21 | 0% | −$58.47 | 4× | 3% |
| FUT_MOMENTUM_4X | 23 | 17% | −$70.15 | 4× | 3% |

Trend entries 0–17% win in chop; tiny peaks (3–7%) = no follow-through. Sane leverage just loses slowly. Next round cranks to confidence-ladder **25–100×** (user request) — prior data says this amplifies losses, but we test it in paper.

## Snapshot — 2026-06-06 (pre-reset, end of the BUYING era)

Balances were reset to a clean **$1,000 each** after this snapshot, switching the
options lab to SELLING and futures to sane leverage. The numbers below are the
full record of the option-BUYING experiment + reckless-leverage futures, so the
lessons survive the reset.

### Paper OPTIONS — BUYING (all lanes, closed trades)
Account $1,000 (mixed $100/$1,000 scale across the run). **Only Donchian was green.**

| Lane | Closed | Win% | Net | Avg peak |
|---|---|---|---|---|
| OPT_DONCHIAN (ATM breakout) | 34 | 68% | **+$29.20** | 37% |
| OPT_VWAP_PULLBACK | 30 | 40% | −$22.57 | 18% |
| OPT_ORB | 6 | 50% | −$41.60 | 22% |
| OPT_MACD | 63 | 51% | −$74.61 | 35% |
| OPT_MEAN_REVERT | 45 | 47% | −$82.30 | 29% |
| OPT_DONCHIAN_OTM | 32 | 50% | −$138.43 | 39% |
| OPT_EMA_PULLBACK | 53 | 42% | −$171.01 | 30% |
| OPT_TREND_RIDE | 84 | 60% | −$185.07 | 34% |
| OPT_TREND_RUNNER | 57 | 49% | −$243.89 | 42% |
| OPT_SUPERTREND | 95 | 57% | −$270.04 | 32% |
| OPT_MOMENTUM | 185 | 24% | −$335.25 | 18% |
| OPT_TREND_RIDE_OTM | 100 | 36% | −$397.79 | 32% |
| **TOTAL (buying)** | ~784 | ~45% | **≈ −$1,930** | — |

Takeaways:
- **Buying short-dated options loses** even with 50–68% win rates — theta + spread + give-back. Confirmed.
- **ATM beats OTM** every time (Donchian ATM +$29 vs OTM −$138; Trend Ride ATM −$185 vs OTM −$398).
- **Donchian breakout** is the single most resilient *entry* — the only positive buy lane.
- **Momentum (fast)** and **far-OTM trend** are the worst — confirmed dead.

### Paper FUTURES — reckless confidence-ladder leverage (all lanes, closed)
| Lane | Closed | Win% | Net | Avg lev |
|---|---|---|---|---|
| PREMIUM_WAVE (twin) | 8 | 50% | −$0.57 | 5× |
| MOVE_PULLBACK | 2 | 0% | −$0.99 | 5× |
| TREND_FLOW | 6 | 17% | −$1.85 | 5× |
| EMA_PULLBACK | 83 | 28% | −$23.16 | 11.6× |
| DONCHIAN_BREAKOUT | 48 | 38% | −$45.72 | 33.7× |
| MOMENTUM_IMPULSE | 166 | 23% | −$332.23 | 61.5× |
| **TOTAL** | ~313 | ~26% | **≈ −$404** | — |

Takeaway: **loss scales directly with leverage** (5× ≈ flat, 61× momentum = −$332). Validates the sane-leverage (3–5×) pivot.

## Active experiments (post-reset, fresh $1,000 each)
- **Options = SELLING premium** (theta harvest): OPT_SELL_PUT / SELL_CALL / SELL_NEUTRAL + far-OTM variants. TP +50% credit, SL −100%, ride to near-expiry.
- **Futures = sane leverage trend**: FUT_DONCHIAN_3X / 5X, FUT_EMA_4X, FUT_MOMENTUM_4X (control).
- Hypotheses: (1) selling harvests the theta buying bled; (2) Donchian/trend entries pay at 3–5× without option drag.
- The 2-hourly routine ranks all lanes. Crown a winner only after a real sample (hundreds of trades).

## Live snapshot — 2026-06-07 03:39 UTC (post-burn-#3, engine running)
Balances: Options **$968.98** (−$31.02, n=109, 0 open) · Futures **$299.07** (−$3,700.93 closed, n=172, 0 open). Burns: Options 0× · Futures **3×** (funded $4,000 = $1,000 seed + 3 refills). Lowest $299.07 > $50 floor → no refill this hour. Live OFF. **Burn #4 likely within ~1hr (~$249 buffer, −$441/hr).**

| Lane | Closed | Win% | Net | Avg peak% | Avg lev |
|---|---|---|---|---|---|
| OPT_SELL_CALL_FAR | 13 | — | −$1.94 | — | — |
| OPT_SELL_CALL | 11 | — | −$2.33 | — | — |
| OPT_SELL_NEUTRAL | 25 | — | −$5.65 | — | — |
| OPT_SELL_PUT | 25 | — | −$7.01 | — | — |
| OPT_SELL_PUT_FAR | 35 | — | −$14.06 | — | — |
| FUT_DONCHIAN_50X | 21 | 19% | −$384.12 | 5.9 | 50× |
| FUT_DONCHIAN_CONF | 19 | 21% | −$459.73 | 4.7 | 55× |
| FUT_EMA_CONF | 44 | 23% | −$533.29 | 3.5 | 31× |
| FUT_DONCHIAN_100X | 22 | 9% | −$843.22 | 6.0 | 100× |
| FUT_MOMENTUM_CONF | 66 | 15% | −$1,478.70 | 6.4 | 66× |

Read: options flat/noise at n=109 (no lane with edge, −$0.28/trade). Futures bleed across ALL lanes — MOMENTUM_CONF worst (−$1,479, 40% of loss, 66× lev). **Exit-reason split, n=100 on paper_stop: −$3,556 of the loss is paper_stop at avg peak just +1.27% (entries never reach the money); paper_trail cohort (n=56) is +5.69% realized.** Settled diagnosis = wrong entries × high leverage, NOT exits. Need (engine code): pullback/retest entry filter + cap leverage ≤10× + kill MOMENTUM_CONF/DONCHIAN_100X. Options: defined-risk spreads. See LEARNINGS check-in log for detail.

# Alpha — Paper Results Snapshot

> Point-in-time dump of paper-lab results, kept in the codebase so we can pull it
> up anytime. Pairs with `LEARNINGS.md` (verdicts/principles). Regenerate by
> re-querying `paper_options_trades` / `paper_futures_trades` and updating below.

## FINAL Snapshot — 2026-06-09 21:00 UTC (end of ERA 2: aggressive 25–100× futures + $250 selling)

Both labs re-seeded to $1,000 for V3 via additive `paper_deposits` rows — **no rows deleted, full history preserved.** Era totals below are the permanent record.

### Futures — confidence-ladder / fixed high leverage (n=1,468 closed, −$26,742, 26 burns, $27k funded)
| Lane | Closed | Win% | Net | Avg lev | Avg peak | Avg hold |
|---|---|---|---|---|---|---|
| FUT_MOMENTUM_CONF | 620 | 14.2% | −$11,587 | 67.6× | 8.9% | 4.9m |
| FUT_DONCHIAN_100X | 174 | 16.1% | −$5,812 | 100× | 9.6% | 2.2m |
| FUT_DONCHIAN_CONF | 166 | 22.9% | −$3,496 | 56.2× | 7.2% | 5.4m |
| FUT_DONCHIAN_50X | 165 | 21.2% | −$3,028 | 50× | 6.9% | 4.8m |
| FUT_EMA_CONF | 343 | 34.7% | −$2,819 | 29.7× | 5.6% | 10.3m |

**The three tables that define V3:**
- **Exit cohorts:** paper_stop 828/0%/−$29,999 @ +1.45% avg peak (= 112% of ALL loss) · paper_trail 550/51.5%/+$1,559 · paper_max_hold 29/82.8%/+$2,437 @ +47.4% peak. Exits printed money; entries+leverage burned it.
- **Peak buckets:** <2%: 635/0%/−$22,456 · 2–10%: 498/18%/−$9,401 · 10–25%: 243/55%/−$75 · 25–50%: 58/**91%**/+$1,470 · 50%+: 34/**97%**/+$3,719.
- **Hold buckets:** <10min: 1,226/15%/−$28,518 · 10–60min: 241/**51%**/+$1,788 · >1h: **1 trade in the entire era.**

### Options — naked OTM selling, $250 margin (n=742 closed, −$421, fees $448 → GROSS +$27 = breakeven)
| Lane | Closed | Win% | Net | Fees | Avg peak |
|---|---|---|---|---|---|
| OPT_SELL_PUT_FAR | 176 | 7.4% | −$99.88 | $106.41 | 0.14% |
| OPT_SELL_CALL | 148 | 14.9% | −$96.53 | $87.88 | 0.45% |
| OPT_SELL_PUT | 183 | 13.7% | −$92.57 | $110.47 | 0.22% |
| OPT_SELL_NEUTRAL | 160 | 15.6% | −$75.00 | $97.30 | 0.42% |
| OPT_SELL_CALL_FAR | 75 | 13.3% | −$57.15 | $45.96 | 0.59% |

Read: **selling lost to churn + fees, not direction.** ~10-min average holds collected dust credits that real(istic) fees fully consumed. V3 sells closer strikes (credit ≥$2), signals on 15m, cools down 15min between trades, holds for hours of actual decay, and uses the true Delta fee model.

### V3 lanes now running (fresh $1,000 each, $100 margin/trade)
Futures: FUT_EMA_PB_10X · FUT_EMA_PB_20X (leverage A/B on identical entries) · FUT_DONCHIAN_RT_10X · FUT_VWAP_10X · FUT_SFP_15X — ATR price stops, breakeven ratchet, chandelier trail, stagnation purge, conf≥70, 24h max hold.
Options: OPT_SELL_PUT_V3 · OPT_SELL_CALL_V3 · OPT_SELL_RANGE_V3.
Gate to live ($50 real): profit factor >1.0 over ~200 trades in a lane.

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

## Live snapshot — 2026-06-07 05:40 UTC (post-burn-#4, engine paused)
Balances: Options **$956.85** (−$43.15, n=92, 0 open) · Futures **$1,001.07** post-refill (−$3,998.93 closed, n=194, 0 open). Burns: Options 0× · Futures **4×** (funded $5,000 = $1,000 seed + 4 refills). Pre-refill futures $1.07 ≤ $50 → **AUTO-REFILL burn #4 fired** (id 6). Live OFF (`is_paused=true`, `bot_state=paused`).

| Lane | Closed | Win% | Net | Avg peak% |
|---|---|---|---|---|
| OPT_SELL_CALL_FAR | 4 | 25% | −$3.63 | — |
| OPT_SELL_CALL | 4 | 25% | −$4.98 | — |
| OPT_SELL_NEUTRAL | 22 | 9% | −$7.57 | — |
| OPT_SELL_PUT | 25 | 12% | −$8.85 | — |
| OPT_SELL_PUT_FAR | 37 | 3% | −$18.11 | — |
| FUT_DONCHIAN_50X | 24 | 21% | −$411.92 | 6.4 |
| FUT_DONCHIAN_CONF | 22 | 27% | −$446.09 | 6.0 |
| FUT_EMA_CONF | 46 | 28% | −$531.52 | 4.4 |
| FUT_DONCHIAN_100X | 25 | 12% | −$870.64 | 7.6 |
| FUT_MOMENTUM_CONF | 77 | 16% | −$1,738.75 | 7.0 |

Read: options flat/noise at n=92 (no lane with edge, −$0.47/trade). Futures bleed across ALL lanes — MOMENTUM_CONF worst (−$1,739, 43% of loss). **Exit-reason split (n=194): paper_stop −$4,046.73 over 114 trades at avg peak just +1.23% (entries never reach the money); paper_trail cohort (n=69) now NET POSITIVE +$142.00 at +14.76% avg peak.** Settled diagnosis = wrong entries × high leverage, NOT exits — paper_trail being profitable proves exits make money. Need (engine code): pullback/retest entry filter + cap leverage ≤10× + kill MOMENTUM_CONF/DONCHIAN_100X. Options: defined-risk spreads. See LEARNINGS check-in log for detail.

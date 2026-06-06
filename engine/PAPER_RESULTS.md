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

## Live snapshot — 2026-06-06 21:39 UTC (post-reset, engine resumed)
Balances: Options **$995.99** (−$4.01, n=49, 4 open) · Futures **$150.01** (−$850.00, n=51, 3 open). Burns 0× each (both > $50 floor; futures near burn). Live OFF.

| Lane | Closed | Win% | Net | Avg peak% |
|---|---|---|---|---|
| OPT_SELL_CALL | 9 | 67% | +$0.96 | 14.8 |
| OPT_SELL_CALL_FAR | 10 | 40% | +$0.30 | 15.9 |
| OPT_SELL_PUT_FAR | 9 | 22% | −$1.45 | 0.8 |
| OPT_SELL_NEUTRAL | 12 | 25% | −$1.86 | 5.4 |
| OPT_SELL_PUT | 9 | 33% | −$2.03 | 0.9 |
| FUT_DONCHIAN_CONF | 5 | 40% | −$46.78 | 4.5 |
| FUT_DONCHIAN_50X | 5 | 20% | −$60.68 | 5.3 |
| FUT_DONCHIAN_100X | 6 | 17% | −$185.31 | 7.2 |
| FUT_EMA_CONF | 14 | 14% | −$192.11 | 1.5 |
| FUT_MOMENTUM_CONF | 21 | 14% | −$365.10 | 4.9 |

Read: options flat/noise (CALL+ / PUT−, directional not edge); futures bleeding across ALL lanes — high-lev Donchian now confirmed losers, 100× peaks +7% avg then round-trips through the fixed stop. Need: ATR/leverage-scaled stop + profit-lock on futures; defined-risk spreads on options. See LEARNINGS check-in log for detail.

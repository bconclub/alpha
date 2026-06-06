# Alpha — Paper Results Snapshot

> Point-in-time dump of paper-lab results, kept in the codebase so we can pull it
> up anytime. Pairs with `LEARNINGS.md` (verdicts/principles). Regenerate by
> re-querying `paper_options_trades` / `paper_futures_trades` and updating below.

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

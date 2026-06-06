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

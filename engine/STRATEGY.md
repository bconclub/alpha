# Alpha Options — Strategy (price-action board)

> Compiled 2026-06-05. The single reference for how the options engine should behave.
> Build against this. If code and this doc disagree, fix one of them on purpose.

## Account reality (locked)
- Live Delta balance: **~$29** (₹6,000 ≈ $70 deposited since Feb; total P&L −$54).
- **Buy-only.** No option selling/writing at this size — Delta margin to write one BTC/ETH
  option exceeds the whole account, and it's the opposite (theta/range) edge from this thesis.
  Revisit selling only at ~$500+ as a separate, paper-tested lane.
- Minimal/no futures leverage until the buy-side price-action edge is proven green in the paper lab.
- Risk per trade: small ($3–4 notional premium), but sized by price action, not fixed.

## Core philosophy
A **price-action board**. It watches two things only: the **underlying** price structure and the
**option premium** structure. When price action offers an opportunity it enters — on a *low*
premium, never a peak. It rides while the move is alive, takes what the move gives, and
re-enters on the next premium dip if the contract is still good.

**No clocks anywhere.** No cooldowns, no minimum holds, no warmups, no "wait N seconds",
no fixed candle bars as gates. Every entry/exit DECISION is driven by price structure.
(Rolling lookbacks used only to *measure* velocity are not gates and may stay.)

## The flaws this replaces
1. **Enter at the peak, exit on noise** — chased lifted premiums, shaken out by ±15% option breathing.
2. **"Patience" built as a timer, not structure** — the 180s warmup *disabled* the stop, so noise
   free-fell to −16/−24% market fills. Worse than cutting early.
3. **Churn** — 5 entry engines + ~8 exit paths + cooldowns → 20 trades/day paying fees both ways.
4. **Inverted R:R** — wins capped (+0.22 avg), losses uncapped (−0.46 avg); +19% peaks given back to 0.
5. **In-memory guards wiped by 21 restarts/day** — re-bought the same dying strike 3–5× in a row.

## Entry — ONE engine
Two questions, both pure price-action. Enter only when both are true:
1. **Is the underlying moving with conviction, now?** (spot velocity + structure → call/put direction)
2. **Is the premium LOW within that move?** (pulled back from its recent local high while the
   underlying thesis still holds → buy the dip, never the spike)

No setup taxonomy. No per-setup cooldown. No max-age. No fill-wait loop.
Take **every** opportunity the board offers that passes the spread/liquidity gate.

### Strike selection (dynamic ATM → slightly OTM)
- Pick the strike by the **expected move**, not a fixed ATM rule.
  - Strong impulse → reach **slightly OTM** (cheaper, rides harder, affordable on $29).
  - Marginal move → stay **ATM** (higher delta, safer).
- **Never deep OTM** — noisier in %, fast theta decay, and far strikes are illiquid with wide spreads.
- **Spread/liquidity is the hard gate**, not distance. If the spread is wide, skip the strike —
  wide-spread fills are what produced the −24% slippage. This caps how far OTM we go.

## Exit — ONE structural model
Replace the entire A–E ladder + harvest + micro-protect + warmup + dead-timer with:
- **Hard catastrophic stop, always on** (≈ premium −10/−12%). The "thesis is wrong" net the
  warmup removed. Active from tick one — no warmup, no defer.
- **Ride** while premium prints higher-highs and the underlying still supports. Do nothing.
- **Trail** under premium structure once in profit — floor scales with peak (small peaks
  protected tighter, moonshots looser). A +15% peak must never round-trip to 0.
- **Cut** when premium makes a structural lower-low **AND** the underlying stops supporting
  → exit at market. The "AND underlying" is the buffer against pure premium noise.

## Re-entry — first-class
While the **underlying move is alive** and the **contract is tradeable** (liquid, not near expiry):
every time the **premium dips to a fresh local low**, that's a buy — as many times as offered.
No lockout, no cooldown. The only gate is "move still alive + contract still good." When the
underlying thesis breaks, re-entry stops automatically (entry question #1 fails).

## What gets ripped out (time-based gates)
Delete or convert to price conditions:
`PHASE_A_THESIS_WARMUP_SEC`, `DEAD_MIN_HOLD_SEC`, `PHASE_B_DEVELOPMENT_MAX_SEC`,
`PHASE1_HANDS_OFF_SEC`, `PHASE_TRAIL_CONFIRM_TICKS`, `PULLBACK_CONFIRMATION_TICKS`,
`PREMIUM_WAVE_COOLDOWN_SEC`, `TREND_FLOW_COOLDOWN_SEC`, `FVG_CHOCH_COOLDOWN_SEC`,
`FVG_CHOCH_ZONE_COOLDOWN_SEC`, `MOVE_PULLBACK_MAX_AGE_SEC`, `MOVE_PULLBACK_WAKE_COOLDOWN_SEC`,
`SQUEEZE_FILL_WAIT_SEC`, `FAST_ENTRY_FILL_WAIT_SEC`, `REENTRY_WATCH_SEC`,
`_no_fill_cooldown_until`, `_POSITION_GONE_COOLDOWN_SEC`, and the phase A–E peak ladder.
Keep: measurement lookbacks (spot/premium velocity windows), OHLCV cache.

## Fee discipline
One engine + ride-the-move = far fewer round-trips. Win condition shifts from "scalp 20× for
+$0.20" to "catch the 2–4 real moves a day and ride each." The churn IS the fee leak.

## Survive restarts
Persist live trade thesis (direction, entry premium, running peak, what we're riding) to the DB /
`options_state` so the 21 restarts/day don't wipe it. Separately: fix *why* it restarts 21×/day.

## Build order
1. Exit rewrite → the one structural model (always-on hard stop + scaling premium trail +
   "premium LL AND underlying quits" cut). Highest impact; stops today's bleed.
2. Strip all time gates/cooldowns/min-holds.
3. Collapse 5 entry engines → 1 price-action engine + dynamic strike selection.
4. First-class re-entry loop on premium dips.
5. Persist thesis across restarts; fix restart root cause.
6. (Later) run new engine in paper-futures lab before any real futures/leverage or selling.

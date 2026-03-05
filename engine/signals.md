**Last updated: v0.4.9 — 2026-03-05**

# Alpha Trade Signals — Complete Reference

How the bot decides when to enter, how it manages positions, and when it exits.

---

## Two-Tier Entry System (v3.20.1)

The bot has **two entry paths** — the traditional momentum path and the anticipatory tier 1 path.

### Momentum Path (existing)

Every 5 seconds the bot computes all 11 indicators from 30 x 1m candles. If momentum >= 0.12% fires (Gate 0), direction is locked by momentum sign and entry requires **3/4 signals minimum** aligned in that direction. Order is placed immediately.

### Tier 1 Path (anticipatory — confirm before order)

When Gate 0 blocks (momentum < 0.12%), the bot checks for **leading signals** that precede the move. These are TIER 1 signals — institutional loading patterns detected before price moves. Direction comes from **order flow** (BB position + EMA ribbon), not past momentum.

If 2+ T1 signals fire (or 1 T1 + 2 T2), the signals are stored as **PENDING** — **no order is placed**. On each subsequent 5s tick, the bot checks if momentum confirms (0.10%+ in the pending direction). Only when confirmed does the order execute. This means zero fees and zero loss on unconfirmed setups.

**Pending T1 lifecycle (no order until confirmed):**
- `T1_CONFIRMED`: momentum >= 0.15% in pending direction → execute order, entry_path = "tier1" (raised from 0.10%)
- `T1_REJECTED`: momentum >= 0.10% AGAINST pending direction → clear pending (zero cost, lowered from 0.15%)
- `T1_EXPIRED`: T1 signals no longer present → clear pending (zero cost)
- `T1_TIMEOUT`: 30s with no confirmation → clear pending (zero cost)

---

## 12-Signal Arsenal

### Core 4 Signals (Tier 2 — confirming)

| # | Signal | Tag | Long Condition | Short Condition |
|---|--------|-----|---------------|-----------------|
| 1 | **Momentum 60s** | MOM | momentum_60s >= +0.12% | momentum_60s <= -0.12% |
| 2 | **Volume Spike** | VOL | vol_ratio >= 0.8x AND mom > 0 | vol_ratio >= 0.8x AND mom < 0 |
| 3 | **RSI Extremes** | RSI | RSI(14) < 40 | RSI(14) > 60 |
| 4 | **Bollinger Band** | BB | bb_position <= 0.15 (bottom 15%) | bb_position >= 0.85 (top 15%) |

### Bonus 8 Signals (Tier 2 — confirming)

| # | Signal | Tag | Condition |
|---|--------|-----|-----------|
| 5 | **Momentum 5m** | MOM5m | \|momentum_300s\| >= 0.30% — catches slow sustained moves |
| 6 | **Trend Continuation** | TCONT | New 15-candle high/low + volume >= 1.0x average |
| 7 | **VWAP + EMA Alignment** | VWAP | Long: price > VWAP(30) AND EMA(9) > EMA(21). Short: inverse |
| 8 | **BB Squeeze Breakout** | BBSQZ | BB inside Keltner Channel (squeeze) + price breaks out with volume |
| 9 | ~~**Liquidity Sweep**~~ | ~~LIQSWEEP~~ | **DISABLED in code** (`if False`) — poor performance |
| 10 | **Fair Value Gap** | FVG | 3-candle imbalance gap >= 0.05%, price fills the gap |
| 11 | **Volume Divergence** | VOLDIV | Price rising + volume declining 20% (hollow pump), or price falling + volume declining 20% (exhausted sellers) |
| 12 | **Breakout Pullback Reload Continue** | BPRC | Candle-based breakout → pullback → reload pattern with continuation |

### Tier 1 Signals (leading/anticipatory)

| Signal | Tag | Long Condition | Short Condition |
|--------|-----|---------------|-----------------|
| **Volume Anticipation** | T1:VOL_ANTIC | vol >= 1.5x AND \|mom\| < 0.10% + BB low (<=0.30) or EMA 9>21 | vol >= 1.5x AND \|mom\| < 0.10% + BB high (>=0.70) or EMA 9<21 |
| **BB Squeeze** | T1:BBSQZ | BB inside Keltner Channel + EMA 9 > EMA 21 | BB inside KC + EMA 9 < EMA 21 |
| **RSI Approach** | T1:RSI_APPROACH | RSI in 32-38 (approaching oversold) | RSI in 62-68 (approaching overbought) |

**T1 entry requires 3+ T1 signals** (raised from 2 to filter coin-flip entries).

**Direction from order flow** (not past momentum):
- Volume + lower BB (<=0.30) → LONG, Volume + upper BB (>=0.70) → SHORT
- Volume + BB mid → use EMA ribbon (EMA9 > EMA21 → LONG)
- Squeeze + EMA9 > EMA21 → LONG, Squeeze + EMA9 < EMA21 → SHORT
- RSI 32-38 → LONG, RSI 62-68 → SHORT
- If T1 signals disagree on direction → skip (conflicting order flow)

---

## Entry Gate

### Momentum Path — Gate 0

Momentum must be above the **0.12% minimum** (Gate 0). Direction is locked:
- `momentum_60s > 0` → `mom_direction = "long"` — only long entries allowed
- `momentum_60s < 0` → `mom_direction = "short"` — only short entries allowed

If Gate 0 blocks, the bot **falls through to Tier 1** detection instead of stopping.

### Tier 1 Path — Entry Requirements

When Gate 0 blocks (momentum < 0.12%), the bot checks for leading signals:
- **3+ T1 signals** in the same direction → enter (anticipatory, raised from 2)
- **1 T1 + 2 T2 signals** in the same direction → enter (confluence)
- Entry path set to `"tier1"`, confirmation required during Phase 1

### Momentum Strength Tiers

| Tier | Momentum | Required Signals | Meaning |
|------|----------|-----------------|---------|
| **STRONG** | >= 0.20% | 3/4 | High conviction, standard entry |
| **MODERATE** | 0.12% - 0.20% | 3/4 | Above gate, standard entry |
| **WEAK** | < 0.12% | 4/4 | Requires full signal confluence |
| Below gate | < 0.12% | — | Falls through to Tier 1 path |

### RSI Override

RSI < 30 or RSI > 70 triggers **immediate entry** bypassing the 3/4 signal count, but still requires momentum in the matching direction (Gate 0 must pass — momentum path only).

### Big Size Signal Gate

Positions exceeding **50 contracts** require **4/4 signals** — no exceptions.

### Large Position Momentum Gate

Large positions (per-pair thresholds below) require **0.12%+ momentum**:

| Pair | Threshold |
|------|-----------|
| XRP | >= 50 contracts |
| ETH | >= 3 contracts |
| BTC | >= 2 contracts |
| SOL | >= 3 contracts |

### Entry Requirements Summary

```
MOMENTUM PATH:
  Standard:    4/4 signals + momentum >= 0.12% + direction match (all pairs)
  RSI <30:     immediate long entry (still needs mom >= 0.12% + direction match)
  RSI >70:     immediate short entry (still needs mom >= 0.12% + direction match)
  >50 contracts: 4/4 signals required (BIG_SIZE_GATE)
  Large pos:   momentum >= 0.12% required (LARGE_POS_GATE)
  Counter-trend: 4/4 signals (longing in TRENDING_DOWN or shorting in TRENDING_UP)
  5m counter (soft): 4/4 when 5m opposes at > 0.15%
  5m counter (hard): BLOCK when 5m opposes at > 0.40%
  High vol:    4/4 signals required
  Weak mom:    4/4 signals required (momentum 0.08-0.12%)
  2nd pos:     3/4+ signal strength, 60% reduced allocation
  Post-streak: 3/4 signal strength (first trade after 3 consecutive losses)
  Dir low WR:  4/4 signals required if direction win rate < 30% over last 5

ALL ENTRIES (momentum + tier1):
  Stale momentum: 10s real-time momentum must be >= 0.08% in entry direction
    (prevents entering after the move is already over — 60s mom is lagging)
  Deceleration filter: 10s momentum must exceed 0.08% floor in entry direction

TIER 1 PATH (no momentum needed):
  3+ T1 signals:     enter with confirmation window (raised from 2, needs 0.15% momentum confirm in 30s)
  1 T1 + 2 T2:       enter with confirmation window
  Direction:          from order flow (BB position, EMA ribbon, RSI approach)
  Sizing:             80-100% of base allocation (see below)
```

### Fixed Leverage

All futures entries use **fixed 20x leverage**. Dynamic leverage (50x/30x tiers) was removed for capital safety.

| Exchange | Leverage |
|----------|----------|
| **Bybit** | 20x |
| **Delta India** | 20x |
| **Kraken Futures** | 20x |
| **Binance Spot** | 1x (no leverage) |

### Idle Threshold Widening

After 30 minutes with no entry, thresholds loosen by 20%:
- Momentum: 0.12% → 0.096%
- Volume: 0.8x → 0.64x
- RSI thresholds widen proportionally

---

## Setup Classification (v3.19.1+)

The combination of signals determines the **primary** setup type. First match wins — **no fallthrough**. If the primary setup is disabled via dashboard, the trade is **skipped entirely**.

| Priority | Setup Type | Trigger |
|----------|------------|---------|
| 1 | `RSI_OVERRIDE` | RSI < 30 or RSI > 70 (extreme RSI) |
| 2 | `TIER1_ANTICIPATORY` | T1: prefix (anticipatory leading signals) |
| 3 | `BB_SQUEEZE` | BBSQZ: tag |
| 4 | `MOMENTUM_BURST` | MOM + VOL signals fire together |
| 5 | `MEAN_REVERT` | BB + RSI signals (band bounce) |
| 6 | `TREND_CONT` | TCONT: tag |
| 7 | `VWAP_RECLAIM` | VWAP: tag |
| 8 | `LIQ_SWEEP` | LIQSWEEP: tag (signal disabled in code — never triggers) |
| 9 | `FVG_FILL` | FVG: tag |
| 10 | `VOL_DIVERGENCE` | VOLDIV: tag |
| 11 | `BPRC_RELOAD` | BPRC: tag (Breakout Pullback Reload Continue) |
| 12 | `MULTI_SIGNAL` | 4+ signals but no specific pattern matched |
| 13 | `MIXED` | Final fallback |

**No hardcoded disables** — all setup toggling is via dashboard `setup_config` table. The `LIQSWEEP` signal is disabled in signal detection code (`if False`) so the tag never appears.

**`signals_fired` field** (v3.19.1): Every trade stores the raw reason string with all signal tags for analysis, regardless of which setup_type was selected as primary.

---

## Momentum Riding Exit System

Replaces the old tight trailing stop with a two-mode system: **ride momentum** with a wide ratchet floor, or **exit immediately** on signal reversal.

### Always Active (ALL phases)

| Exit Type | Trigger |
|-----------|---------|
| **Hard SL** | Price hits SL floor (ATR-dynamic, see table below) |
| **Hard TP** | Capital PnL >= 10% (safety net) |
| **Ratchet Floor** | PnL drops below locked floor → instant exit (`RATCHET`) |

### Ratchet Floor Table

Floors are based on **price PnL %** (not capital %). Floor only moves UP — once locked, it never decreases.

| Peak PnL % Reached | Floor Locks At | Capital at 20x |
|---------------------|----------------|----------------|
| +0.20% | +0.08% | +1.6% |
| +0.30% | +0.15% | +3.0% |
| +0.50% | +0.30% | +6.0% |
| +1.00% | +0.60% | +12.0% |
| +2.00% | +1.20% | +24.0% |
| +3.00% | +2.00% | +40.0% |
| +5.00% | +3.50% | +70.0% |

### Phase 1: Hands-Off (0-30 seconds)

All entries (momentum AND tier1) arrive **pre-confirmed**. Tier 1 confirmation happens BEFORE order placement via the pending check system — no unconfirmed positions ever exist.

Only hard SL, ratchet floors, and Hard TP fire. Protects against fill slippage.

Exception: If peak PnL >= +0.5%, skip immediately to Phase 2.

**Stop Loss Distances (ATR-dynamic):**

| Pair | SL Floor | SL Cap | Capital at 20x |
|------|----------|--------|----------------|
| BTC | 0.30% | 0.50% | 6-10% |
| ETH | 0.35% | 0.50% | 7-10% |
| XRP | 0.50% | 0.70% | 10-14% |
| SOL | 0.40% | 0.60% | 8-12% |
| Spot | 2.0% | 3.0% | 2-3% (1x) |

Dynamic SL: `max(pair_floor, ATR_14 * 1.5)`, capped at the SL Cap.
**Risk cap:** Max SL loss never exceeds 5% of total balance → contracts capped accordingly.

### Phase 2: Momentum Riding (30s - 10 minutes)

**MODE 1 — RIDING (momentum aligned + profitable):**
- Momentum_60s is in the same direction as the position → **STAY IN**
- Ratchet floor protects profits passively
- Breakeven safety: if peak was >= +0.30% and price returns to entry → exit `BREAKEVEN`

**MODE 2 — SIGNAL REVERSAL (exit immediately):**

Three reversal triggers (any one fires → exit at market):

| Trigger | Condition | Confirm Time |
|---------|-----------|-------------|
| **Momentum Flip** | Long + mom counter 0.10%+, or Short + mom counter 0.10%+ | 60 seconds (immediate at pnl < -0.20%) |
| **Momentum Dying** | abs(momentum_60s) < 0.02% | immediate |
| **Momentum Fade** | Momentum fading for 90s + losing only (90s min hold, 120s if trend-aligned) | 90 seconds |
| **RSI Extreme Cross** | Long + RSI crosses above 70, or Short + RSI crosses below 30 | immediate |
| **Dead Momentum** | abs(momentum) flat for 3+ min (5 min min hold) | immediate |

Reversal exit fires **regardless of P&L** (min profit requirement removed — exit on reversal at any level).

### Phase 2: Spot Profit Protection

| Exit Type | Trigger |
|-----------|---------|
| **Pullback** | Peak >= +0.50% AND current < peak x 50% |
| **Decay** | Peak >= +0.40% AND current < +0.15% |
| **Breakeven** | Peak >= +0.30% AND current <= +0.05% |

### Phase 3: Trail or Cut (10 - 30 minutes)

| Exit Type | Trigger |
|-----------|---------|
| **Flatline** | 10+ min hold AND \|PnL\| < 0.05% — **ONLY if losing** |
| **Timeout** | 30 min hold AND not trailing — **ONLY if losing** |
| **Safety** | 30 min hold AND PnL < 0% (cut losers) |

**Winners are NEVER closed by flatline or timeout.** Only ratchet floor, reversal, or hard TP can close a winner.

### Price-Only Exits (WebSocket tick — `check_exits_immediate`)

Every price tick also checks (no OHLCV/momentum needed):
- Hard SL
- Hard TP (10% capital)
- Ratchet floor (updates peak + checks floor)
- Breakeven (if peaked high enough)
- Phase 3 flatline/timeout

### Fee-Aware Minimum

Discretionary exits are skipped if gross profit < $0.10. **Protective exits always execute regardless of gross amount:**

| Always Execute | Fee Check Applies |
|----------------|-------------------|
| SL, TRAIL, BREAKEVEN, PROFIT_LOCK | REVERSAL |
| HARD_TP, HARD_TP_10PCT, RATCHET, SAFETY | FLAT, TIMEOUT |

---

## Capital Allocation (v3.20.0)

### Dynamic Position Sizing — Tier-Aware

Sizing flow:
1. Get allocation % for pair (performance-based, adaptive)
2. **Apply tier-based multiplier** (tier1 entries get reduced sizing)
3. **Apply survival mode cap** (balance < $20 → cap 30%)
4. Reduce for 2nd simultaneous position (60% factor)
5. Calculate collateral from allocation
6. Safety cap: never use more than 80% of balance on one position
7. Total exposure cap: never exceed risk manager max_position_pct
8. Calculate notional at leverage, convert to contracts (round down)
9. Minimum 1 contract — if can't afford, skip (`INSUFFICIENT_CAPITAL`)
10. Large position gate: per-pair contract thresholds require 0.12% momentum
11. Big size gate: >50 contracts requires 4/4 signals

### Tier-Based Sizing Multiplier

| Entry Path | T1 Count | Multiplier | Effective Alloc |
|-----------|----------|------------|-----------------|
| momentum (existing) | — | 1.0x | 100% of base |
| tier1 | 3+ T1 | 1.0x | 100% of base |
| tier1 | 2 T1 | 1.0x | 100% of base |
| tier1 | 1 T1 + 2 T2 | 0.80x | 80% of base |

### Survival Mode (v3.20.0)

When `exchange_capital < $20.00` → allocation capped at **30%** regardless of tier or pair. Prevents blowing the last $20 on one aggressive entry.

### Per-Pair Base Allocation (% of exchange capital)

| Pair | Allocation | Rationale |
|------|------------|-----------|
| XRP | **35%** | Best performer, SLs at large size costly |
| ETH | 30% | Mixed, catches big moves |
| BTC | 20% | Lowest win rate, diversification |
| SOL | 15% | Newer, building data |

### Performance Adjustment (last 5 trades per pair)

- Win rate < 20%: reduce to 25% of base (minimum 5%)
- Win rate > 60%: boost by 20% (capped at 70%)

**Note:** Tier1 entries that don't confirm (T1_TIMEOUT, T1_REJECTED, T1_EXPIRED) never place an order — zero fees, zero loss, not counted anywhere.

### Balance Refresh

Exchange balance is refreshed from API every 60 seconds before sizing decisions, so new deposits are picked up automatically.

---

## Risk Management

### Position Limits

| Rule | Value |
|------|-------|
| Max concurrent (futures) | 3 per exchange (allocation % handles sizing) |
| Max concurrent (spot) | 1 |
| Max per pair | 1 (no scaling) |
| Max total exposure | 90% of balance |
| 2nd position strength | 3/4+ signals |

### Daily Loss Limit

Stop all trading if daily PnL <= -(capital x 20%).

### Rate Limit

Max 10 trades per hour.

### Cooldowns (Per-Pair)

| Event | Cooldown |
|-------|----------|
| After SL hit | 2 minutes |
| After 3 consecutive losses | 5 minutes |
| First trade after streak pause | requires 3/4 signals |
| After reversal exit | 3 minutes (same direction only) |
| After phantom cleared | 60 seconds |

**Tier1 pending:** T1 signals that don't confirm (T1_TIMEOUT/T1_REJECTED/T1_EXPIRED) never place an order — zero cost, no cooldown impact.

### Regime Gate

`CHOPPY` market regime blocks all new entries. Detected via chop score and ATR ratio analysis.

---

## Fee Structure

### Per-Exchange Fees

| Exchange | Taker/side | Maker/side | Mixed RT | Notes |
|----------|-----------|-----------|----------|-------|
| **Bybit** | 0.055% | 0.02% | 0.075% | No GST — global exchange |
| **Delta India** | 0.059% | 0.024% | 0.083% | Includes 18% GST |
| **Kraken Futures** | 0.05% | 0.02% | 0.07% | No GST — global exchange |
| **Binance Spot** | 0.10% | 0.10% | 0.20% | Flat fee |

### Exit Fee Optimization

Non-urgent exits use **limit-then-market** strategy:
1. Place limit order at current price (maker fee)
2. Wait 3 seconds for fill
3. If not filled → cancel limit, execute market order (taker fee)

Urgent exits (SL, HARD_TP, SL_EXCHANGE) always use immediate market orders.

---

## Complete Trade Lifecycle

```
SCANNING (every 5s)
  |
  +-- Fetch 30x 1m candles
  +-- Compute all 12 indicators (RSI, BB, KC, EMA, VWAP, momentum, volume, BPRC)
  +-- Gate 0: momentum >= 0.12%?
  |     |
  |     +-- YES (Momentum Path):
  |     |     +-- Direction locked by momentum sign
  |     |     +-- Momentum tier: STRONG/MODERATE/WEAK -> sets required signals
  |     |     +-- Count bull/bear signals (each signal fires for one direction)
  |     |     +-- Gate: signal_count >= required? OR RSI override?
  |     |     +-- YES -> Build entry (entry_path = "momentum", confirmed = true)
  |     |
  |     +-- NO (Tier 1 Path — PENDING system):
  |           +-- Check T1 signals: Volume Anticipation, BB Squeeze, RSI Approach
  |           +-- Direction from order flow (BB pos + EMA ribbon + RSI approach)
  |           +-- 2+ T1 signals OR 1 T1 + 2 T2?
  |           +-- YES -> Store as _pending_tier1 (NO order placed, T1_PENDING skip)
  |           +-- NO -> NO_MOMENTUM skip
  |
  +-- Pending T1 check (every 5s tick, before new entry scan):
  |     |
  |     +-- _pending_tier1 exists?
  |     |     +-- Age >= 30s? -> T1_TIMEOUT (clear, zero cost)
  |     |     +-- Momentum 0.10%+ in pending direction? -> T1_CONFIRMED
  |     |     |     +-- Build entry (entry_path = "tier1"), proceed to entry signal below
  |     |     +-- Momentum 0.15%+ AGAINST pending direction? -> T1_REJECTED (clear, zero cost)
  |     |     +-- T1 signals still present? (re-detect)
  |     |     |     +-- NO -> T1_EXPIRED (clear, zero cost)
  |     |     |     +-- YES -> Still waiting, skip new entry scan this tick
  |     |     +-- No pending -> normal entry scan
  |
  +-- Entry signal? (from momentum path OR confirmed T1)
  |     |
  |     +-- Stale momentum check: 10s momentum >= 0.05% in direction?
  |     |     +-- NO -> STALE_MOMENTUM skip (move is over)
  |     +-- Fixed leverage: 20x (all futures entries)
  |     +-- Setup type classification (first-match priority, no fallthrough)
  |     +-- Setup disabled via dashboard? -> skip
  |     +-- Per-pair strength gate (3/4 for all)
  |     +-- Dynamic position sizing (tier-aware + survival mode, fixed 20x leverage)
  |     +-- Big size gate: >50 contracts -> 4/4?
  |     +-- Large pos gate: threshold + 0.12% momentum?
  |     +-- Risk manager: daily loss? balance? cooldowns?
  |     |
  |     +-- YES -> Execute order
  |           |
  |           +-- Fill confirmed -> Track position
  |                 |
  |                 +-- Phase 1 (0-30s): HANDS OFF for all entries
  |                 |     +-- All entries arrive pre-confirmed (momentum or T1_CONFIRMED)
  |                 |     +-- Only hard SL + ratchet + hard TP checked
  |                 |     +-- Exception: peak >= +0.5% -> skip to Phase 2
  |                 |
  |                 +-- Phase 2 (30s-10m): Momentum riding / signal reversal
  |                 |     +-- MODE 1: momentum aligned -> RIDE (stay in)
  |                 |     +-- MODE 2: momentum flip/dying/RSI -> REVERSAL EXIT
  |                 |
  |                 +-- Phase 3 (10-30m): Flatline/timeout (losers only)
  |                       |
  |                       +-- EXIT triggered
  |                             +-- Protective exits (SL/RATCHET/BREAKEVEN): always
  |                             +-- Discretionary exits: skip if gross < $0.10
  |                             +-- Record P&L (gross - fees = net)
  |                             +-- Update win/loss streak
  |                             +-- Apply cooldowns if loss
  |                             +-- Resume scanning
  |
  +-- NO -> Wait 5s, scan again
```

---

## Exit Reason Codes

| Code | Meaning |
|------|---------|
| `SL` | Stop loss hit |
| `SL_EXCHANGE` | SL filled by exchange |
| `RATCHET` | Ratchet floor breached (locked profit dropped below floor) |
| `REVERSAL` | Signal reversal exit (momentum flip, dying, or RSI extreme cross) |
| `HARD_TP_10PCT` | 10% capital gain safety net |
| `TP` | Take profit hit |
| `TP_EXCHANGE` | TP filled by exchange |
| `BREAKEVEN` | Breakeven protection (peaked high, returned to entry) |
| `FLAT` | Flatline (no movement 10m, losers only) |
| `TIMEOUT` | Hard timeout 30m (losers only) |
| `SAFETY` | Losing after timeout |
| `SPOT_PULLBACK` | Spot: profit pulled back > 50% from peak |
| `SPOT_DECAY` | Spot: profit decayed below 0.15% after peaking |
| `SPOT_BREAKEVEN` | Spot: profit decayed to near-zero after peaking |
| `MANUAL` | Manual close from dashboard |
| `DUST` | Dust balance cleanup |
| `ORPHAN` | Orphaned strategy closed |
| `PHANTOM` | Phantom position cleared |
| `POSITION_GONE` | Position not found |
| `CLOSED_BY_EXCHANGE` | Closed externally |
| `EXPIRY` | Delta daily contract expiry |

---

## Skip Reason Codes

When the bot decides NOT to enter, the reason is tracked and shown on the dashboard:

| Code | Meaning |
|------|---------|
| `NO_MOMENTUM` | abs(momentum_60s) < 0.12% AND no tier 1 signals |
| `STRENGTH_GATE` | Signal count below minimum (e.g., 2/4 < 3/4) |
| `DIRECTION_BLOCK` | Signals fire against momentum direction |
| `INSUFFICIENT_CAPITAL` | Can't afford 1 contract with current allocation |
| `LARGE_POS_GATE` | Large position needs 0.12%+ momentum |
| `BIG_SIZE_GATE` | >50 contracts needs 4/4 signals |
| `SETUP_DISABLED` | Setup type disabled via dashboard (no hardcoded blocks) |
| `POSITION_SIZE_ZERO` | Sizing returned zero |
| `WEAK_COUNTER_TREND` | Weak momentum against 15m trend |
| `REGIME_CHOPPY` | Choppy market regime blocks entries |
| `REVERSAL_COOLDOWN` | Within 2m cooldown after reversal exit (ALL directions on pair) |
| `DIR_LOW_WR` | Per-direction win rate < 30% over last 5 trades → needs 4/4 signals |
| `RISK_CAP` | Contracts capped so max SL loss doesn't exceed 5% of total balance |
| `STREAK_PAUSE` | 3 consecutive losses on this pair |
| `LOW_BALANCE` | Balance below minimum |
| `SPREAD_TOO_WIDE` | Bid-ask spread exceeds max |
| `PHANTOM_COOLDOWN` | Within 60s after phantom position cleared |
| `SURVIVAL_MODE` | Balance < $20, allocation capped at 30% |
| `STALE_MOMENTUM` | 60s momentum passed but 10s momentum < 0.05% — move already over |
| `T1_PENDING` | Tier 1 signals detected, waiting for momentum confirmation (no order placed) |
| `T1_TIMEOUT` | Pending T1 not confirmed within 30s (zero cost, no order was placed) |
| `T1_REJECTED` | Pending T1 rejected — counter-momentum 0.15%+ against direction (zero cost) |
| `T1_EXPIRED` | Pending T1 signals faded before confirmation (zero cost) |

---

## Key Thresholds Reference

| Parameter | Futures | Spot |
|-----------|---------|------|
| Entry gate (momentum path) | 4/4 signals all pairs (4/4 if >50 contracts) | 4/4 |
| Entry gate (tier1 path) | 3+ T1 or 1 T1 + 2 T2 | same |
| Momentum minimum (Gate 0) | **0.12%** (60s) | same |
| T1 pending confirm threshold | 0.15% momentum in direction (pre-order check) | same |
| T1 pending reject threshold | 0.10% counter-momentum (pre-order check) | same |
| T1 pending timeout | 30s (no order placed, zero cost) | same |
| Momentum direction | must match signal direction (momentum path) | same |
| Tier1 direction | from order flow (BB + EMA + RSI approach) | same |
| Leverage | Fixed 20x (dynamic leverage removed) | 1x |
| SL distance (BTC) | 0.30% floor, 0.50% cap | 2.0% floor, 3.0% cap |
| SL distance (ETH) | 0.35% floor, 0.50% cap | — |
| SL distance (XRP) | 0.50% floor, 0.70% cap | — |
| SL distance (SOL) | 0.40% floor, 0.60% cap | — |
| Exit system | **Momentum riding + ratchet floor** | Spot trail + pullback protection |
| Hard TP | 10% capital | same |
| Ratchet floors | +0.20%→0.08%, +0.30%→0.15%, +0.50%→0.30%, +1.00%→0.60%, +2.00%→1.20%, +3.00%→2.00%, +5.00%→3.50% | N/A |
| Trail activation | +0.25% peak (2 min min hold, instant at +0.30%) | +0.80% peak |
| Reversal exit | momentum flip (60s confirm, instant at -0.20%) / dying < 0.02% / fade (90s, losers only) / RSI cross 70/30 | N/A |
| Reversal min profit | None (fires at any P&L) | N/A |
| Breakeven trigger | +0.30% peak | +0.30% peak |
| Fee minimum | gross > $0.10 (discretionary exits only) | same |
| Flatline | 10 min, losers only | same |
| Timeout | 30 min, losers only | same |
| Daily loss stop | 20% drawdown | same |
| Rate limit | 10 trades/hour | same |
| Max concurrent | 3 per exchange (sizing caps exposure) | 1 |
| XRP allocation | 35% | N/A |
| ETH allocation | 30% | N/A |
| BTC allocation | 20% | N/A |
| SOL allocation | 15% | N/A |
| Max collateral | 80% of balance per position | N/A |
| Max total exposure | 90% of balance across all positions | N/A |
| 2nd position | 60% of normal allocation | N/A |
| Tier1 sizing (3+ T1) | 100% of base | same |
| Tier1 sizing (2 T1) | 100% of base | same |
| Tier1 sizing (1 T1+2 T2) | 80% of base | same |
| Survival mode | balance < $20 → cap 30% | same |
| Max SL loss (risk cap) | 5% of total balance → contracts capped accordingly | N/A |
| Big size gate | >50 contracts → 4/4 signals | N/A |
| Large pos gate | Per-pair threshold → 0.12% momentum | N/A |
| Direction low WR gate | <30% WR over last 5 trades in direction → 4/4 required | same |
| Counter-trend (regime) | 4/4 signals (allowed, not blocked) | same |
| Counter-trend (5m soft) | 4/4 signals when 5m opposes > 0.15% | same |
| Counter-trend (5m hard) | BLOCKED when 5m opposes > 0.40% | same |
| Reversal cooldown | 2 min ALL directions on pair after REVERSAL exit | same |
| RSI override | < 30 or > 70 (momentum path only) | same |
| RSI signals (T2) | < 40 long / > 60 short | same |
| RSI approach (T1) | 32-38 long / 62-68 short (tier1 path) | same |
| Volume min (T2) | 0.8x average | same |
| Volume anticipation (T1) | 1.5x with mom < 0.10% | same |
| Stale momentum (10s check) | 0.08% in entry direction over last 10s | same |
| Mixed RT fee (Bybit) | 0.075% | ~0.20% |
| Mixed RT fee (Delta) | 0.083% | — |
| Mixed RT fee (Kraken) | 0.07% | — |

---

## Options Scalp (Delta Exchange)

### Entry Requirements
- **Signal source:** 2-of-4+ momentum signals from futures scalp strategy
- **Setup whitelist:** MOMENTUM_BURST and BB_SQUEEZE only
- **Trend alignment:** TRENDING_UP → CALLs only, TRENDING_DOWN → PUTs only
- **Counter-trend:** Allowed at 4/4 signal strength (new)
- **Candle-based momentum:** 3+ directional candles out of last 5, cumulative move >= 0.10%

### Strike & Premium
- ATM strikes, max 3 OTM strikes walked
- BTC: nearest $50, ETH: nearest $20
- Min premium: $0.01 (skip illiquid), Max premium: $40 (skip expensive)
- Leverage: 50x (Delta options)

### Exit System
- **TP:** +30% premium gain
- **SL:** -50% premium loss
- **Trail:** Activates at +15% premium gain, 5% trail distance
- **Pullback:** Exit if lost 40% of peak gain (activates at +8%)
- **Decay:** Exit if faded to +3% after peaking +10%+
- **Ratchet floors:** Early breakeven + small-winner premium protection

---

## Acceleration Entry (WebSocket Layer 1)

Real-time price velocity detection via WebSocket ticks — enters before candle-based signals.

### Velocity Thresholds
- Min velocity: 0.08% in 5s (XRP: 0.06%)
- Min acceleration: +0.01% positive
- Min ticks: 3 in 5s window (1 for slow exchanges like Delta)
- Cooldown: 30s between accel entries per pair
- Requires 2/4 cached indicator support (XRP: 3/4)

### Exchange-Aware Tuning
- Fast exchanges (Bybit/Kraken): 5s velocity window, 3 min ticks
- Slow exchanges (Delta): 10s velocity window, 1 min tick, 0.10% velocity floor

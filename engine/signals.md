# Alpha Trade Signals — Complete Reference

How the bot decides when to enter, how it manages positions, and when it exits.

---

## 11-Signal Arsenal

Every 5 seconds the bot computes all 11 indicators from 30 x 1m candles. Each signal fires independently as bullish or bearish. Entry requires **3/4 signals minimum** aligned in the same direction as momentum.

### Core 4 Signals

| # | Signal | Tag | Long Condition | Short Condition |
|---|--------|-----|---------------|-----------------|
| 1 | **Momentum 60s** | MOM | momentum_60s >= +0.08% | momentum_60s <= -0.08% |
| 2 | **Volume Spike** | VOL | vol_ratio >= 0.8x AND mom > 0 | vol_ratio >= 0.8x AND mom < 0 |
| 3 | **RSI Extremes** | RSI | RSI(14) < 35 | RSI(14) > 65 |
| 4 | **Bollinger Band** | BB | bb_position <= 0.15 (bottom 15%) | bb_position >= 0.85 (top 15%) |

### Bonus 7 Signals

| # | Signal | Tag | Condition |
|---|--------|-----|-----------|
| 5 | **Momentum 5m** | MOM5m | \|momentum_300s\| >= 0.30% — catches slow sustained moves |
| 6 | **Trend Continuation** | TCONT | New 15-candle high/low + volume >= 1.0x average |
| 7 | **VWAP + EMA Alignment** | VWAP | Long: price > VWAP(30) AND EMA(9) > EMA(21). Short: inverse |
| 8 | **BB Squeeze Breakout** | BBSQZ | BB inside Keltner Channel (squeeze) + price breaks out with volume |
| 9 | **Liquidity Sweep** | LIQSWEEP | Sweep past swing H/L (12 candles) then reclaim + RSI divergence |
| 10 | **Fair Value Gap** | FVG | 3-candle imbalance gap >= 0.05%, price fills the gap |
| 11 | **Volume Divergence** | VOLDIV | Price rising + volume declining 20% (hollow pump), or price falling + volume declining 20% (exhausted sellers) |

---

## Entry Gate

### Gate 0 — Momentum Direction Lock

Momentum must be above the 0.08% minimum (Gate 0). Direction is locked:
- `momentum_60s > 0` → `mom_direction = "long"` — only long entries allowed
- `momentum_60s < 0` → `mom_direction = "short"` — only short entries allowed

If signals fire against the momentum direction, the entry is **blocked** and logged:
```
[BTC/USD:USD] DIRECTION BLOCK: 3 bear signals but mom is +0.150% (long)
```

### Momentum Strength Tiers

After Gate 0, momentum is scored to set the signal bar:

| Tier | Momentum | Required Signals | Meaning |
|------|----------|-----------------|---------|
| **STRONG** | >= 0.20% | 3/4 | High conviction, standard entry |
| **MODERATE** | 0.12% - 0.20% | 3/4 | Normal, standard entry |
| **WEAK** | 0.08% - 0.12% | **4/4** | Just passed gate, need full confirmation |
| Below gate | < 0.08% | — | Blocked by Gate 0, no entry possible |

### RSI Override

RSI < 30 or RSI > 70 triggers **immediate entry** bypassing the 3/4 signal count, but still requires momentum in the matching direction.

### Entry Requirements Summary

```
Standard:  3/4 signals + momentum direction match (STRONG/MODERATE)
Weak mom:  4/4 signals + momentum direction match (0.08-0.12%)
RSI <30:   immediate long entry (still needs mom_direction == "long")
RSI >70:   immediate short entry (still needs mom_direction == "short")
2nd pos:   3/4+ signal strength
Post-streak: 3/4 signal strength (first trade after 3 consecutive losses)
```

### Disabled Setups

These setup types are **hardcoded off** — the engine will never enter on them:
- `TREND_CONT` — trend continuation
- `BB_SQUEEZE` — Bollinger squeeze breakout

If a signal combination maps to a disabled setup, entry is blocked and logged:
```
[ETH/USD:USD] SETUP_BLOCKED: TREND_CONT — hardcoded disable
```

### Idle Threshold Widening

After 30 minutes with no entry, thresholds loosen by 20%:
- Momentum: 0.08% → 0.064%
- Volume: 0.8x → 0.64x
- RSI thresholds widen proportionally

---

## Setup Classification

The combination of signals that fire determines the setup type:

| Setup Type | Trigger |
|------------|---------|
| `RSI_OVERRIDE` | RSI < 30 or RSI > 70 (immediate entry) |
| `MOMENTUM_BURST` | MOM + VOL signals fire together |
| `MEAN_REVERT` | BB + RSI signals (band bounce) |
| `VWAP_RECLAIM` | VWAP signal active |
| ~~`TREND_CONT`~~ | ~~TCONT signal~~ — **DISABLED** |
| ~~`BB_SQUEEZE`~~ | ~~BBSQZ signal~~ — **DISABLED** |
| `LIQ_SWEEP` | LIQSWEEP signal (liquidity sweep) |
| `FVG_FILL` | FVG signal (fair value gap) |
| `VOL_DIVERGENCE` | VOLDIV signal (volume divergence) |
| `MULTI_SIGNAL` | 4+ signals fired simultaneously |
| `MIXED` | Default fallback |

---

## 3-Phase Exit System

### Always Active (ALL phases)

| Exit Type | Trigger |
|-----------|---------|
| **Hard SL** | Price hits SL floor (0.25% all pairs, capped at 0.50% futures / 3.0% spot) |
| **Ratchet Floor** | Capital PnL drops below locked floor → instant exit |
| **Hard TP** | Capital PnL >= 10% AND trail NOT active (safety net) |

### Ratcheting Profit Floors

Floors only go up — once locked, they never decrease.

| Capital PnL Reached | Floor Locks At |
|---------------------|----------------|
| +6% | 0% (breakeven) |
| +10% | +4% |
| +15% | +8% |
| +20% | +12% |

If current capital PnL drops below the locked floor → **EXIT IMMEDIATELY** (market order, reason: `PROFIT_LOCK`).

### Phase 1: Hands-Off (0-30 seconds)

Only hard SL, ratchet floors, and Hard TP fire. Protects against fill slippage.

Exception: If peak PnL >= +0.5%, skip immediately to Phase 2.

**Stop Loss Distances:**

| Pair | SL Floor | SL Cap |
|------|----------|--------|
| BTC | 0.25% | 0.50% (futures) |
| ETH | 0.25% | 0.50% (futures) |
| XRP | 0.25% | 0.50% (futures) |
| SOL | 0.25% | 0.50% (futures) |
| Spot | 2.0% | 3.0% |

Dynamic SL: `max(pair_floor, ATR_14 * 1.5)`, capped at the SL Cap.

### Phase 2: Watch & Trail (30s - 10 minutes)

| Exit Type | Trigger |
|-----------|---------|
| **Trailing Stop** | Peak PnL >= +0.25% activates trail (futures) / +0.80% (spot) |
| **Breakeven** | Peak >= +0.20% AND price returns to entry |
| **Decay Emergency** | Peak capital >= +3% AND current < peak x 40% (lost 60%+) |
| **Signal Reversal** | In profit >= +0.30% AND RSI flips (>70 for long, <30 for short) or momentum reverses |

### Phase 3: Trail or Cut (10 - 30 minutes)

| Exit Type | Trigger |
|-----------|---------|
| **Trailing** | Continues from Phase 2 |
| **Decay Emergency** | Same as Phase 2 (repeated check) |
| **Flatline** | 10+ min hold AND \|PnL\| < 0.05% — **ONLY if losing** |
| **Timeout** | 30 min hold AND not trailing — **ONLY if losing** |
| **Safety** | 30 min hold AND PnL < 0% (cut losers) |

**Winners are NEVER closed by flatline or timeout.** Only trail, ratchet, or decay emergency can close a winner.

### Fee-Aware Minimum

Discretionary exits are skipped if gross profit < $0.10. **Protective exits always execute regardless of gross amount:**

| Always Execute | Fee Check Applies |
|----------------|-------------------|
| SL, TRAIL, BREAKEVEN, PROFIT_LOCK | DECAY_EMERGENCY, REVERSAL |
| HARD_TP, RATCHET, SAFETY | FLAT, TIMEOUT |

---

## Trailing Stop Tiers

Trail activates at +0.25% peak PnL (futures) or +0.80% (spot). Distance widens as profit grows — never tightens:

### Futures Trail Tiers

| Peak PnL | Trail Distance | Locks Min At | Capital at 20x |
|----------|----------------|--------------|----------------|
| +0.25% | 0.10% | +0.15% | +3% |
| +0.50% | 0.15% | +0.35% | +7% |
| +1.00% | 0.20% | +0.80% | +16% |
| +2.00% | 0.30% | +1.70% | +34% |

### Spot Trail

| Parameter | Value |
|-----------|-------|
| Activation | +0.80% peak |
| Distance | 0.40% behind peak |

Trail tracks from **peak** price, not current price.

---

## Risk Management

### Position Limits

| Rule | Value |
|------|-------|
| Max concurrent (futures) | 2 per exchange |
| Max concurrent (spot) | 1 |
| Max per pair | 1 (no scaling) |
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
| After phantom cleared | 60 seconds |

---

## Capital Allocation

### Per-Pair Base Allocation (% of exchange capital)

| Pair | Allocation | Rationale |
|------|------------|-----------|
| XRP | 50% | Best performer |
| ETH | 30% | Mixed, catches big moves |
| BTC | 20% | Lowest win rate, diversification |
| SOL | 15% | Newer, building data |

### Performance Adjustment (last 5 trades per pair)

- Win rate < 20%: reduce to minimum
- Win rate > 60%: boost allocation

### Contract Sizing (Delta Futures)

| Pair | Contract Size | Max Contracts |
|------|--------------|---------------|
| BTC/USD:USD | 0.001 BTC | 1 |
| ETH/USD:USD | 0.01 ETH | 2 |
| XRP/USD:USD | 1.0 XRP | 50 |
| SOL/USD:USD | varies | 1 |

### Spot Sizing (Binance)

- 50% of available Binance USDT balance
- Minimum notional: $6.00

---

## Fee Structure

### Delta India (including 18% GST)

| Type | Rate |
|------|------|
| Maker | 0.02% x 1.18 = 0.024% |
| Taker | 0.05% x 1.18 = 0.059% |
| Mixed round-trip | 0.024% + 0.059% = 0.083% |

### Exit Fee Optimization

Non-urgent exits use **limit-then-market** strategy:
1. Place limit order at current price (maker fee: 0.024%)
2. Wait 3 seconds for fill
3. If not filled → cancel limit, execute market order (taker fee: 0.059%)

Urgent exits (SL, HARD_TP, SL_EXCHANGE) always use immediate market orders.

---

## Complete Trade Lifecycle

```
SCANNING (every 5s)
  │
  ├── Fetch 30x 1m candles
  ├── Compute all 11 indicators (RSI, BB, KC, EMA, VWAP, momentum, volume)
  ├── Gate 0: momentum >= 0.08%? → sets direction (long/short)
  ├── Momentum tier: STRONG/MODERATE/WEAK → sets required signals (3 or 4)
  ├── Count bull/bear signals (each signal fires for one direction)
  ├── Setup blocked? (TREND_CONT, BB_SQUEEZE disabled)
  ├── Gate: signal_count >= required? OR RSI override?
  │
  ├── YES → Build entry signal
  │     │
  │     ├── Direction matches momentum? (bull signals + long mom, or bear + short mom)
  │     │     ├── NO → DIRECTION BLOCK (logged, no entry)
  │     │     └── YES ↓
  │     │
  │     ├── Risk manager approves?
  │     │     ├── Daily loss limit OK?
  │     │     ├── Position limits OK?
  │     │     ├── Balance available?
  │     │     └── Cooldowns clear?
  │     │
  │     └── YES → Execute order
  │           │
  │           └── Fill confirmed → Track position
  │                 │
  │                 ├── Phase 1 (0-30s): SL + ratchet + hard TP only
  │                 ├── Phase 2 (30s-10m): Trail + breakeven + decay + reversal
  │                 └── Phase 3 (10-30m): Trail + flat/timeout (losers only)
  │                       │
  │                       └── EXIT triggered
  │                             ├── Protective exits (TRAIL/SL/RATCHET/etc): always execute
  │                             ├── Discretionary exits: skip if gross < $0.10
  │                             ├── Record P&L (gross - fees = net)
  │                             ├── Update win/loss streak
  │                             ├── Apply cooldowns if loss
  │                             └── Resume scanning
  │
  └── NO → Wait 5s, scan again
```

---

## Exit Reason Codes

| Code | Meaning |
|------|---------|
| `TRAIL` | Trailing stop triggered |
| `PROFIT_LOCK` | Ratchet floor breached (locked profit) |
| `TP` | Take profit hit |
| `HARD_TP` | 10% capital gain safety (if not trailing) |
| `TP_EXCHANGE` | TP filled by exchange |
| `MANUAL` | Manual close from dashboard |
| `SL` | Stop loss hit |
| `SL_EXCHANGE` | SL filled by exchange |
| `DECAY_EMERGENCY` | Lost 60%+ of peak profit |
| `REVERSAL` | Signal reversal exit |
| `FLAT` | Flatline (no movement 10m, losers only) |
| `TIMEOUT` | Hard timeout 30m (losers only) |
| `BREAKEVEN` | Breakeven protection |
| `SAFETY` | Losing after timeout |
| `DUST` | Dust balance cleanup |
| `ORPHAN` | Orphaned strategy closed |
| `PHANTOM` | Phantom position cleared |
| `POSITION_GONE` | Position not found |
| `CLOSED_BY_EXCHANGE` | Closed externally |
| `EXPIRY` | Delta daily contract expiry |

---

## Key Thresholds Reference

| Parameter | Futures | Spot |
|-----------|---------|------|
| Entry gate | 3/4 signals (4/4 if weak mom) | same |
| Momentum direction | must match signal direction | same |
| Leverage | 20x (capped) | 1x |
| SL distance | 0.25% floor, 0.50% cap | 2.0% floor, 3.0% cap |
| Trail activation | +0.25% peak | +0.80% peak |
| Trail start distance | 0.10% | 0.40% |
| Hard TP | 10% capital (if not trailing) | same |
| Ratchet floors | +6%→0%, +10%→4%, +15%→8%, +20%→12% | N/A |
| Breakeven trigger | +0.20% peak | +0.30% peak |
| Decay emergency | peak >= 3% cap, current < peak x 40% | same |
| Fee minimum | gross > $0.10 (discretionary exits only) | same |
| Flatline | 10 min, losers only | same |
| Timeout | 30 min, losers only | same |
| Daily loss stop | 20% drawdown | same |
| Rate limit | 10 trades/hour | same |
| Max concurrent | 2 per exchange | 1 |
| RSI override | < 30 or > 70 | same |
| Momentum min | 0.08% (60s) | same |
| Momentum WEAK | 0.08-0.12% → requires 4/4 | same |
| Volume min | 0.8x average | same |
| Disabled setups | TREND_CONT, BB_SQUEEZE | same |
| Mixed RT fee | 0.083% | ~0.20% |

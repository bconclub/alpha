# Alpha — Live Strategy Plan (evidence-based, ready to deploy on approval)

> Built from deep analysis of ALL paper + live data (≈2,800 live option trades,
> ≈1,400 paper futures, ≈700 paper options). NOT live yet — `PAPER_ONLY` stays
> ON until explicitly approved. This is the spec to flip on when you say go.

## 1. What every experiment taught us (the evidence)

| Approach | Verdict | Proof |
|---|---|---|
| Live options BUYING | ❌ dead | 1,396 trades, −$95, 28% win, profit factor 0.36 |
| Paper options BUYING (12 TA strategies) | ❌ dead | every lane negative on real samples; theta + spread tax |
| Paper options SELLING (naked, all sizes) | ❌ dead | profit factor **0.07–0.20**; avg peak 0.1–0.6% — sold options barely move our way before stopping |
| Futures FAST momentum (1m) | ❌ dead | 13–14% win, biggest loser every time |
| Futures HIGH leverage (25–100×) | ❌ ruin | 19 burns, −$20k; win rate 34%@25× → **15%@100×** |
| **Futures TREND, EMA (low concept)** | 🟢 **the one edge** | see below |

## 2. The one real edge — and why it's been losing

**It's a trend-following system, and the money is in the fat tail:**

| Peak reached | Trades | Win% | Net |
|---|---|---|---|
| <2% | 576 | 0% | −$20,355 |
| 2–10% | 460 | 17% | −$8,678 |
| 10–25% | 230 | 56% | +$15 |
| 25–50% | 57 | **91%** | **+$1,450** |
| 50%+ | 34 | **97%** | **+$3,719** |

- Trades that **reach 10%+ are profitable**; 25%+ is 91–97% win. The winners exist and are huge.
- The loss is **1,036 junk entries that never get going (<10% peak)**, made catastrophic by leverage.
- **Confidence predicts the tail:** conf 80+ reaches 10%+ **31%** of the time vs **15%** for conf <70 (avg peak 11.7% vs 5.5%). The signal is real — but it's currently shackled to high leverage, which stops it on noise.
- **EMA trend is the best entry** (FUT_EMA_CONF: 34% win, profit factor 0.35 — least-bad, highest win).
- **Exits already work:** `paper_trail` +$730 and `paper_max_hold` +$1,506 are net positive. Don't touch the exit logic.

**Diagnosis:** good directional signal + working exits, destroyed by (a) over-leverage causing noise stop-outs and (b) too many low-conviction entries in chop.

## 3. The strategy (what to deploy)

**Instrument:** Delta BTC/ETH perpetual **futures only.** (Options are dead both ways — drop them from the live plan.)

**Entry:**
- **EMA 8/21 trend** + pullback-to-EMA8 + follow-through candle (the EMA lane, best win rate).
- **Confidence gate ≥ 75** (reaches the profitable tail 24–31% of the time vs 15%).
- **Regime filter:** only in a trending tape (skip chop — that's where the <2% junk lives). e.g. require ADX/structure or EMA-gap above a floor.
- Both **long and short** (edge is symmetric: 20% vs 23% win).

**Leverage:** FIXED **3–5×** (NOT confidence-laddered, NOT 25–100×). Decouple conviction from size. Low leverage = the stop survives noise and junk losses stay small.

**Stop:** **ATR-based** (~1.5–2× ATR), not a flat −6% (which at high lev is a hair-trigger). Let the thesis breathe.

**Exit (ride the tail):** trail under structure once in profit; **hold winners toward 25–50%+** — the fat tail is the whole edge. Keep the existing trail/max-hold logic; do not add a tight time cap.

**Sizing / risk (real $50 account):** risk ~**1–2% of equity per trade** (~$0.50–$1), **max 1–2 concurrent.** Tiny absolute size, but proportional — the edge compounds if real.

## 4. Explicitly OUT
Options (buy AND sell), leverage > ~5–8×, 1-minute momentum, mean-reversion / counter-trend, far-OTM premium selling. All proven losers.

## 5. Go-live sequence (honest gate)
**Nothing tested is yet net-positive** — every config so far was over-leveraged. This spec is the **best-evidenced hypothesis**, not a proven winner. So:
1. **Paper-validate first:** run THIS exact config (futures, EMA-trend, conf≥75, 3–5× fixed, ATR stop, ride tail) in the paper lab.
2. **Gate:** require **net-positive + profit factor > 1.0 over ~200 trades** before any real money.
3. **Then go live tiny:** the real $50, 3–5×, 1–2% risk/trade, watched closely.
4. Scale only if the live sample stays green.

When you say "go": I'll (a) reconfigure the paper futures lab to this exact spec to validate, then (b) on a green gate, flip `PAPER_ONLY=0` for futures only with the live sizing above. Live stays OFF until step 3.

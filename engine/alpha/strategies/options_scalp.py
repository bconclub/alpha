"""Alpha Options Scalp — Dynamic Breakout Entry (GPFC #21).

═══════════════════════════════════════════════════════════════
 ENTRY: DYNAMIC BREAKOUT STRATEGY (GPFC #21 — Fast + Smart)
═══════════════════════════════════════════════════════════════

 STEP 1 — DETECT BB SQUEEZE (every scan tick, ~30s):
   - Bollinger Bands (20 period, 2 std dev) + Keltner Channel (20 period, 1.5×ATR)
   - SQUEEZE = BB upper < KC upper AND BB lower > KC lower
   - BB width < 1.0% (ETH) / 0.7% (BTC) for valid squeeze
   - Log SQUEEZE_SCAN, do nothing else — wait for breakout

 STEP 2 — DETECT BREAKOUT (when BB leaves KC):
   - BB_upper > KC_upper → breakout UP → buy CALL
   - BB_lower < KC_lower → breakout DOWN → buy PUT
   - Record breakout_premium_ask at detection moment
   - Calculate breakout_velocity = % price move in last 3 candles
   - Log BREAKOUT_DETECTED: dir=UP/DOWN velocity=X% confirmation=Xs

 STEP 3 — DYNAMIC CONFIRMATION WINDOW (GPFC #21 + #24):
   Based on breakout velocity:
   - velocity >= 0.3% in 3 candles → confirmation = 0s (enter immediately)
   - velocity 0.15-0.3% → confirmation = 20s
   - velocity < 0.15% → confirmation = 60s (weak, wait)

   During confirmation window, check every 10s:
   - If premium drops > 5% → BREAKOUT_FAKEOUT, abort immediately
   - If premium rises > 15% → BREAKOUT_OVERPRICED, don't chase

   At end of window (GPFC #24):
   - Premium must be >= start premium (within 2% tolerance)
   - If premium fell > 2% during confirmation → BREAKOUT_FAKEOUT, abort
   - Only enter if premium is rising or held stable → BREAKOUT_CONFIRMED

 STEP 4 — ENTRY:
   - Place limit at current ask, wait 5 min for fill
   - No cooldown after no-fill

 CONFIDENCE SCORING:
   - Tightness: BB_width < 0.5% = 1.0 | < 0.75% = 0.7 | < 1.0% = 0.4
   - Cheapness: bottom 10% of range = 1.0 | 25% = 0.7 | else = 0.4
   - Volume: > 1.5× avg = 1.0 | > 1.0× = 0.7 | below = 0.4
   - Final = average, BTC ×0.7, skip if < 0.6

 SIZING:
   - Confidence-based contract scaling (GPFC #17)
   - Max OTM = 1 (ATM or 1 OTM only)
   - Survival mode: balance < $5 → max 5 contracts

═══════════════════════════════════════════════════════════════

Exit (GPFC #63 — gain-locking, no time gates):
  1. EXPIRED_WORTHLESS  (premium = 0)
  2. OPT_HARD_SL        (flat -15%, no age tightening)
  3. OPT_TRAIL          (premium below tiered absolute floor, peak ≥ 4%)
  4. OPT_PEAK_TRAIL     (confirmed pullback ≥ 30% from peak ≥ 4%)
  5. OPT_BREAKEVEN_STOP (peak ≥ 8% reverted to ≤ +0.5%)
  Worthless-expiry safety: ticker fail with < 5 min to expiry → POSITION_GONE.

Expected: 2–5 entries/day, premium $3–8, 70% lose small / 30% gain 200–400%.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import TYPE_CHECKING, Any

import ccxt.async_support as ccxt

from alpha.config import config
from alpha.db import Database
from alpha.strategies.base import BaseStrategy, MarketCondition, Signal, StrategyName
from alpha.utils import setup_logger

if TYPE_CHECKING:
    from alpha.risk_manager import RiskManager
    from alpha.strategies.scalp import ScalpStrategy
    from alpha.trade_executor import TradeExecutor

logger = setup_logger("options_scalp")

IST = timezone(timedelta(hours=5, minutes=30))


# ── GPFC #79: exit-reason display map ──────────────────────────────────────
# DB stores snake_case keys. Dashboard / logs format via format_exit_reason().
EXIT_REASON_DISPLAY: dict[str, str] = {
    "stop_phase_a": "Stop Phase A",
    "stop_phase_b": "Stop Phase B",
    "stop_phase_c": "Stop Phase C",
    "stop_phase_d": "Stop Phase D",
    "stop_phase_e": "Stop Phase E",
    "trail_phase_c": "Trail Phase C",
    "trail_phase_d": "Trail Phase D",
    "trail_phase_e": "Trail Phase E",
    "profit_harvest": "Profit Harvest",
    "breakeven": "Breakeven",
    "dead": "Dead",
    "pre_expiry": "Pre-Expiry",
    "expired_itm": "Expired ITM",
    "expired_otm": "Expired OTM",
    "expired_worthless": "Expired Worthless",
    "ticker_dropout": "Ticker Dropout",
    "reconcile_gone": "Reconcile Gone",
    "peak": "Peak",  # legacy
}


def format_exit_reason(raw: str) -> str:
    """Render a stored snake_case exit_reason as a human-readable label."""
    if not raw:
        return ""
    return EXIT_REASON_DISPLAY.get(raw, raw.replace("_", " ").title())


def canonical_option_exit_reason(exit_type: str | None) -> str:
    """Return the strategy-native exit key that should be stored in DB."""
    exit_key = (exit_type or "").strip().lower()
    if not exit_key or exit_key == "unknown":
        return "unknown"
    return exit_key


class OptionsScalpStrategy(BaseStrategy):
    """Buy CALLs/PUTs during BB squeeze — buy cheap premium, hold through breakout."""

    name = StrategyName.OPTIONS_SCALP
    check_interval_sec = 5  # 5-second ticks

    # ── Class-level shared state ──────────────────────────────────────
    _global_in_position: bool = False  # legacy mirror; do not gate cross-asset entries
    _global_position_asset: str | None = None

    # ── Delta Exchange contract multiplier (options) ─────────────
    CONTRACT_MULTIPLIER: dict[str, float] = {"ETH": 0.01, "BTC": 0.001}

    # ── Option chain refresh ──────────────────────────────────────
    CHAIN_REFRESH_INTERVAL = 30 * 60  # Refresh every 30 min
    MIN_EXPIRY_HOURS = 5.0  # Must be 5+ hours to expiry
    EXPIRY_SWITCH_HOURS = (
        3.0  # Switch to next-day expiry when < 3h remain on current day
    )
    CLOSE_BEFORE_EXPIRY_HOURS = 0.5  # Close 30 min before expiry
    EXPIRY_MODE_HOURS = 8.0  # Switch to expiry-mode exit when < 8h to expiry

    # ── Strike selection ──────────────────────────────────────────
    BTC_STRIKE_ROUND = 200  # BTC: nearest $200
    ETH_STRIKE_ROUND = 20  # ETH: nearest $20
    MAX_OTM_STRIKES = 1  # ATM or 1 OTM only — further OTM is dead money

    # ── Premium limits ────────────────────────────────────────────
    OPTIONS_LEVERAGE = 50  # Delta options are 50x leveraged
    MIN_PREMIUM_USD = (
        5.00  # Skip strikes < $5 — too little delta, premium doesn't respond
    )

    # ── BB Squeeze detection ──────────────────────────────────────
    BB_PERIOD = 20  # Bollinger Band period
    BB_STD_MULT = 2.0  # BB standard deviation multiplier
    KC_PERIOD = 20  # Keltner Channel period
    KC_ATR_MULT = 1.5  # KC ATR multiplier
    SQUEEZE_BB_WIDTH_ETH = 1.0  # ETH: BB width must be < 1.0% for valid squeeze
    SQUEEZE_BB_WIDTH_BTC = 0.7  # BTC: BB width must be < 0.7% (tighter price action)
    SQUEEZE_FILL_WAIT_SEC = 300  # Wait up to 5 min for fill
    SQUEEZE_FILL_POLL_SEC = 3  # Poll every 3s so highest_premium tracking starts fast after fill
    FAST_ENTRY_FILL_WAIT_SEC = 5  # TREND/MOM/PULLBACK must fill now or cancel
    FAST_ENTRY_FILL_POLL_SEC = 1
    FAST_ENTRY_MAX_SPOT_AGAINST_PCT = 0.05
    FAST_ENTRY_LIMIT_CROSS_PCT = 8.0  # Cross the ask enough so fast option moves actually fill.
    FAST_ENTRY_SETUPS = frozenset({"MOM_BURST", "MOVE_PULLBACK", "TREND_FLOW", "FVG_CHOCH", "PREMIUM_WAVE"})
    PAPER_FUTURES_ENABLED = True
    PAPER_FUTURES_ACCOUNT_USD = 100.0
    PAPER_FUTURES_ALLOC_PCT = 0.25
    PAPER_FUTURES_LEVERAGE = 5.0
    PAPER_FUTURES_FEE_RATE = 0.0005
    SQUEEZE_CHEAP_PERCENTILE = 0.25  # Buy bottom 25% of 30-min premium range
    SQUEEZE_HISTORY_MIN = 30  # Track premium history for 30 min
    # Dynamic confirmation window thresholds (GPFC #21) — UPDATED
    # velocity >= 0.3% → 20s, 0.15-0.3% → 40s, < 0.15% → 60s
    BREAKOUT_CONFIRM_HIGH_VELOCITY = 0.3  # >= 0.3% → 20s confirmation
    BREAKOUT_CONFIRM_MED_VELOCITY = 0.15  # 0.15-0.3% → 40s confirmation
    BREAKOUT_CONFIRM_SEC_HIGH = 20  # Fast for strong moves
    BREAKOUT_CONFIRM_SEC_MED = 40  # Medium wait for medium moves
    BREAKOUT_CONFIRM_SEC_MAX = 60  # Max wait for weak moves
    BREAKOUT_FAKEOUT_DROP_PCT = 5.0  # Premium drop > 5% from breakout = fakeout
    BREAKOUT_OVERPRICED_RISE_PCT = 15.0  # Premium rise > 15% = overpriced, abort
    # GPFC #69: 0.05 → 0.06 (slight tighten — winners had ≥0.05 aligned mom;
    # #3279 slipped through with und_mom -0.008 ≈ zero).
    MOMENTUM_BURST_THRESHOLD_PCT = 0.10  # GPFC #87: require fresher real movement; 0.06 bought stale tails.
    MOMENTUM_BURST_MIN_ASK_RISE_PCT = 1.5  # cumulative % rise across 3 ATM ticks
    # GPFC #83: anti-chase entry guard. The losing 100-confidence trades were
    # buying after option ask spikes had already expanded 15-17% over 3 ticks.
    # Keep momentum entries, but reject entries where the option premium has
    # already repriced too far before our limit order lands.
    MOM_BURST_MAX_LAST_ASK_RISE_PCT = 9.5
    MOM_BURST_MAX_CUM_ASK_RISE_PCT = 14.0
    # GPFC #85: MOM_BURST needs deeper books than SQUEEZE. Recent ETH entries
    # barely clearing the generic $2M floor could peak green but could not exit
    # near breakeven because the bid vanished. Keep the generic floor for
    # SQUEEZE, but require stronger turnover before momentum entries.
    MOM_BURST_MIN_TURNOVER_USD = 5_000_000
    # GPFC #99: premium-wave entry. When the higher-timeframe tape is already
    # directional and the option premium itself starts lifting, enter the wave
    # directly instead of waiting for squeeze/pullback/momentum gates to align
    # perfectly. This is real-options only and uses only spot/options data.
    PREMIUM_WAVE_MIN_5M_RISE_PCT = 12.0
    PREMIUM_WAVE_MIN_15M_RISE_PCT = 18.0
    PREMIUM_WAVE_MIN_UNDERLYING_5M_PCT = 0.25
    PREMIUM_WAVE_MIN_UNDERLYING_15M_PCT = 0.45
    PREMIUM_WAVE_MIN_TURNOVER_USD = 750_000
    PREMIUM_WAVE_MAX_SPREAD_PCT = 8.0
    PREMIUM_WAVE_MAX_MARK_GAP_PCT = 9.0
    PREMIUM_WAVE_MIN_DELTA_ABS = 0.20
    PREMIUM_WAVE_MIN_IV = 0.20
    PREMIUM_WAVE_COOLDOWN_SEC = 300.0
    PREMIUM_WAVE_MAX_LAST_RISE_PCT = 11.0
    PREMIUM_WAVE_MAX_CUM_RISE_PCT = 22.0
    PREMIUM_WAVE_MAX_FROM_5M_LOW_PCT = 24.0
    # If spread is wider than the phase-A stop, the trade is born near/under
    # stop before thesis can play out. Keep entries tighter than the -3% phase-A
    # guard so we do not buy options that immediately stop on bid/ask alone.
    ENTRY_MAX_SPREAD_PCT = 2.5
    ENTRY_MAX_MARK_GAP_PCT = 4.0
    # GPFC #92: option-quality brain. Momentum entries must have enough
    # expected option movement to pay for spread, mark gap, fees, and normal
    # quote noise. This prevents buying contracts whose first expected peak is
    # smaller than the microstructure cost of getting in/out.
    ENTRY_MIN_CONTRACT_SCORE = 70.0
    ENTRY_MIN_EXPECTED_EDGE_PCT = 9.0
    ENTRY_EDGE_SPREAD_MULT = 2.5
    ENTRY_EDGE_MARK_GAP_MULT = 1.0
    ENTRY_NOISE_BUFFER_PCT = 3.0
    # Freshness gate — the 60s move must be CONCENTRATED in the last 20s rather
    # than fading. This rejects "tail-end" moves (premium already priced the move)
    # without forcing us to wait for a bigger move to develop.
    # Ratio = |move_last_20s| / |move_last_60s|. Linear move = 0.33, accelerating
    # move = 0.6+, fading move = 0.0–0.3. We require the last 20s to contain
    # >= 50% of the net move, i.e. the move is at least linear-or-fresher.
    # ── Dynamic option sizing ──────────────────────────────────────
    # NEW: Fixed 20-30% capital allocation per trade (GPFC #20)
    # allocation_pct = 0.20 + (confidence * 0.10)  # 20% at conf=0.0, 30% at conf=1.0
    CAPITAL_PER_TRADE_MIN_PCT = 0.20  # 20% minimum per trade (low confidence)
    CAPITAL_PER_TRADE_MAX_PCT = 0.30  # 30% maximum per trade (high confidence)
    OPT_SURVIVAL_BALANCE = 20.0  # below this, cap allocation at 30%
    OPT_SURVIVAL_MAX_ALLOC = 30.0

    # ── Exit thresholds ────────────────
    SL_PREMIUM_LOSS_PCT = 15.0  # Hard stop at -15% premium drop (was -20%)
    # GPFC #63: trail activates at peak +4% to catch any meaningful peak (was 8%).
    # Format: (peak_threshold_pct, exit_floor_pct). When peak hits threshold,
    # exit if premium drops below floor (absolute %-from-entry).
    OPT_TRAIL_TIERS: list[tuple[float, float]] = [
        (10.0, 5.0),    # peak +10%  → lock ~5%
        (15.0, 10.0),   # peak +15%  → lock ~10%
        (22.0, 16.0),   # peak +22%  → lock ~16%
        (30.0, 23.0),   # peak +30%  → lock ~23%
        (45.0, 36.0),   # peak +45%  → lock ~36%
        (60.0, 50.0),   # peak +60%  → lock ~50%
        (100.0, 85.0),  # peak +100% → lock ~85%
    ]
    # GPFC #75: PEAK pullback mirrors trail-tier-0 activation (10%).
    # Backup behind tiered TRAIL — trail should fire first because it's
    # tier-aware; PEAK pullback catches if trail misses.
    PULLBACK_EXIT_PCT = 30.0  # Exit when 30% of peak gain given back
    PULLBACK_ACTIVATE_PCT = 10.0  # Arm at peak ≥ 10% (GPFC #75 breathing room)
    # Confirmation before firing OPT_PEAK_TRAIL — absorbs single-tick illiquidity
    # wicks in the option premium. Require the pullback condition to persist for
    # N consecutive ticks (ticks are ~10s apart).
    PULLBACK_CONFIRMATION_TICKS = 2
    # Spot-momentum veto — if the underlying is still actively pushing in our
    # favour on the short window, defer the trail exit. The underlying is the
    # cleaner signal; option premium is a noisy derivative with theta + spread.
    # Units: %. For a call, veto when spot_mom_20s >= +this; for a put, veto
    # when spot_mom_20s <= -this.
    # GPFC #64: spot-direction veto threshold — require ≥0.10% aligned move
    # over 60s to defer PEAK/TRAIL exits. 0.05 was noise-level.
    PULLBACK_SPOT_VETO_PCT = 0.10
    # Breakeven safety net: once peak is meaningful, never let trade go red
    BREAKEVEN_STOP_ACTIVATE_PCT = 8.0  # arm once peak hits +8%
    BREAKEVEN_STOP_EXIT_PCT = 0.5      # exit if pnl drops to +0.5% or lower

    PHASE1_HANDS_OFF_SEC = 30
    # GPFC #95/#98: do not let ordinary bid/ask noise kill a fresh options
    # entry within seconds. Phase A only becomes active after this warmup unless
    # the premium loss is catastrophic; -8/-15% is normal options noise in fast
    # Delta books and was cutting trades in 20-30s before the thesis developed.
    PHASE_A_THESIS_WARMUP_SEC = 180.0
    PHASE_A_EMERGENCY_SL_PCT = -50.0
    PHASE_A_DYNAMIC_FAIL_PCT = -8.0
    PHASE_A_DYNAMIC_HARD_FAIL_PCT = -12.0

    # ── GPFC #67: DEAD-on-arrival cutter ──────────────────────────────
    # Catches trades that NEVER moved up AND underlying turned against us.
    # Fires before STOP so we cut at ~ -8% rather than letting it bleed to
    # the -15% flat SL. All three conditions required, no time gates.
    DEAD_PEAK_MAX_PCT = 3.0         # GPFC #72: 0.5 → 3.0; catches the sub-3% peak trades that bled to -16% SL
    DEAD_PREMIUM_DROP_PCT = -8.0    # premium dropped ≥ 8% from entry
    DEAD_UNDERLYING_AGAINST_PCT = 0.05  # underlying moved > 0.05% against us in 60s
    DEAD_MIN_HOLD_SEC = 180.0

    # ── GPFC #78 / #79: phase-based exits (regime-switching by peak P&L) ─
    # GPFC #79 tightens phase-B/C/D/E backstops since trail is the primary
    # exit in C/D/E. Phases keyed off peak P&L:
    #   A: peak <  3%  → tight -3% SL
    #   B: peak 3-9%   → breakeven exit at +0.5% retrace OR -5% SL backstop
    #   C: peak 9-15%  → trail at 45% of peak OR -8% SL backstop
    #   D: peak 15-50% → trail at 60% of peak OR -8% SL backstop
    #   E: peak ≥ 50%  → trail at 75% of peak OR -8% SL backstop (moonshots)
    PHASE_A_PEAK_MAX_PCT = 3.0
    PHASE_A_SL_PCT = -3.0
    PHASE_B_PEAK_MAX_PCT = 9.0
    PHASE_B_SL_PCT = -12.0
    PHASE_B_BREAKEVEN_ARM_PCT = 8.0
    # GPFC #85: treat dashboard-rounded +8% peaks as armed, then protect while
    # the option is still green. Waiting until +0.5%/red was too late in thin
    # ETH books; the limit often missed and market fallback filled much lower.
    PHASE_B_BREAKEVEN_ARM_BUFFER_PCT = 0.15
    PHASE_B_BREAKEVEN_EXIT_PCT = 4.0
    # GPFC #93: small-peak protection. A +5-8% option peak is not a real runner
    # yet, but it is enough edge to stop round-tripping to a red phase-B stop.
    PHASE_B_MICRO_PROTECT_ARM_PCT = 8.0
    PHASE_B_MICRO_PROTECT_EXIT_PCT = -4.0
    PHASE_B_DEVELOPMENT_ARM_PCT = 5.0
    PHASE_B_DEVELOPMENT_MAX_SEC = 900.0
    PHASE_B_DEVELOPMENT_SL_PCT = -12.0
    PHASE_C_PEAK_MAX_PCT = 15.0
    PHASE_C_TRAIL_FRAC = 0.45
    PHASE_C_SL_PCT = -8.0          # GPFC #79: was -15 (trail is primary)
    PHASE_D_PEAK_MAX_PCT = 50.0
    PHASE_D_TRAIL_FRAC = 0.60
    PHASE_D_SL_PCT = -8.0          # GPFC #79: explicit per-phase
    PHASE_E_TRAIL_FRAC = 0.75
    PHASE_E_SL_PCT = -8.0          # GPFC #79: explicit per-phase
    PHASE_TRAIL_SPOT_VETO_PCT = 0.08
    PHASE_TRAIL_MAX_DEFER_TICKS = 2

    # ── GPFC #80: momentum confirmation on Phase A/B SL ───────────────────
    # Defer the SL trigger when spot is still moving in our trade direction —
    # premium dip is likely IV / spread / tick lag, not thesis failure. This
    # is a MOMENTUM check, not a clock gate. Hold ticks until spot turns.
    PHASE_A_SPOT_FAVORABLE_BPS = 0.05   # % move in our favor over lookback (NOT basis points)
    PHASE_A_SPOT_LOOKBACK_SEC = 30      # rolling window for spot movement

    # GPFC #87: small-account options need profit capture before a thin book can
    # give back the whole move between 5s polls. A +12% option peak is already
    # meaningful at current size; harvest while at least +10% is still quoted.
    PROFIT_HARVEST_ARM_PCT = 30.0
    PROFIT_HARVEST_EXIT_PCT = 24.0

    # ── GPFC #67: entry-quality filters (winner-pattern analysis) ─────
    # Winners cluster at |delta| 0.42-0.61, IV 0.41-0.54, turnover $2.84M-$13.68M.
    # Block entries outside these bands.
    ENTRY_MIN_TURNOVER_USD = 2_000_000
    ENTRY_DELTA_MIN_ABS = 0.40
    ENTRY_DELTA_MAX_ABS = 0.65
    ENTRY_MIN_IV = 0.40
    SQUEEZE_MIN_IV = 0.20
    MOVE_PULLBACK_MIN_IV = 0.35
    TREND_FLOW_MIN_IV = 0.35
    # GPFC #72: confidence floor — sub-60 zone was 0/3 in last 20 trades, with
    # two -16% catastrophic stops. Block entries below this score; no behavior
    # change above 60.
    # GPFC #81: confidence model collapsed to aligned_mom only — gate at 60
    # now means aligned_mom >= 0.60% (after the /0.20 cap scale, the top
    # tercile of historical 60s underlying moves).
    CONFIDENCE_MIN_ENTRY = 60.0

    # GPFC #82: SQUEEZE re-enabled, gated by IV regime. SQUEEZE only fires
    # in low-vol regimes (IV < SQUEEZE_MAX_IV_FOR_ENTRY); MOM_BURST only
    # fires when vol is at least MOM_BURST_MIN_IV_FOR_ENTRY. The two paths
    # are mutually-exclusive by IV, so the bot picks the right setup for
    # the regime instead of forcing one strategy onto every market.
    ENABLED_SETUPS: frozenset[str] = frozenset({
        "MOM_BURST",
        "SQUEEZE",
        "MOVE_PULLBACK",
        "TREND_FLOW",
        "PREMIUM_WAVE",
    })

    # GPFC #82: IV-regime gates per setup. mark_vol is read from
    # ticker.info.mark_vol (Delta returns it as a decimal: 0.30 = 30%).
    SQUEEZE_REQUIRES_LOW_VOL = True
    SQUEEZE_MAX_IV_FOR_ENTRY = 0.40   # block SQUEEZE above this IV
    MOM_BURST_MIN_IV_FOR_ENTRY = 0.25  # block MOM_BURST below this IV

    # GPFC #86: websocket-driven move/pullback entry.
    # MOM_BURST was often skipping the best move as "chase", then buying the
    # stale tail. This setup detects the impulse from the underlying WS, waits
    # for a controlled retrace, and enters on re-confirmation instead of buying
    # the first premium spike.
    MOVE_PULLBACK_MOM_60S_PCT = 0.25
    MOVE_PULLBACK_MOM_20S_PCT = 0.08
    MOVE_PULLBACK_MIN_IMPULSE_PCT = 0.30
    MOVE_PULLBACK_MIN_RETRACE_FRAC = 0.20
    MOVE_PULLBACK_MAX_RETRACE_FRAC = 0.55
    MOVE_PULLBACK_RECONFIRM_20S_PCT = 0.08
    MOVE_PULLBACK_SECOND_LEG_PCT = 0.10
    MOVE_PULLBACK_MAX_AGE_SEC = 360.0
    MOVE_PULLBACK_WAKE_COOLDOWN_SEC = 2.0
    MOVE_PULLBACK_MIN_TURNOVER_USD = 5_000_000
    MOVE_PULLBACK_MAX_SPREAD_PCT = 2.5
    MOVE_PULLBACK_FAST_MOVE_MAX_SPREAD_PCT = 6.5
    MOVE_PULLBACK_MAX_MARK_GAP_PCT = 7.0

    # GPFC #95: trend-first regime guard. In a strong 15m/45m trend, stop
    # taking tiny countertrend option scalps and only allow entries with the
    # dominant tape unless the higher-timeframe trend actually flips.
    TREND_REGIME_15M_PCT = 0.60
    TREND_REGIME_45M_PCT = 1.00
    TREND_REGIME_STRONG_15M_PCT = 0.85
    TREND_COUNTER_BLOCK_ENABLED = True
    ANALYZER_COUNTER_BLOCK_ADX = 25.0
    ANALYZER_COUNTER_BLOCK_1H_PCT = 0.50
    ANALYZER_COUNTER_BLOCK_24H_PCT = 1.50

    # GPFC #88: directional staircase entry. This catches the market shape
    # where several 5m candles walk one way without a clean pullback trigger.
    TREND_FLOW_15M_PCT = 0.75
    TREND_FLOW_5M_PCT = 0.25
    TREND_FLOW_MAX_15M_PCT = 1.00
    TREND_FLOW_MAX_5M_PCT = 0.90
    TREND_FLOW_CONTINUATION_60S_PCT = 0.30
    TREND_FLOW_CONTINUATION_20S_PCT = 0.12
    TREND_FLOW_MIN_TURNOVER_USD = 4_000_000
    TREND_FLOW_MAX_SPREAD_PCT = 2.5
    TREND_FLOW_FAST_MOVE_MAX_SPREAD_PCT = 6.5
    TREND_FLOW_MAX_MARK_GAP_PCT = 6.0
    TREND_FLOW_MIN_ALIGNED_60S_PCT = 0.18
    TREND_FLOW_MIN_ALIGNED_20S_PCT = 0.07
    TREND_FLOW_MIN_ACCEL_RATIO = 0.50
    TREND_FLOW_TREND_REVERSE_TOLERANCE_PCT = 0.08
    TREND_FLOW_COOLDOWN_SEC = 900.0
    FAST_MOVE_SPREAD_60S_PCT = 0.45
    FAST_MOVE_SPREAD_20S_PCT = 0.20
    EXPLOSIVE_MOVE_SPREAD_60S_PCT = 0.75
    EXPLOSIVE_MOVE_SPREAD_20S_PCT = 0.35
    EXPLOSIVE_MOVE_MAX_SPREAD_PCT = 18.0
    ACTIVE_MOVE_SPREAD_60S_PCT = 0.30
    ACTIVE_MOVE_SPREAD_20S_PCT = 0.12
    ACTIVE_MOVE_MAX_SPREAD_PCT = 4.5

    # GPFC #94: second-chance reload after a good momentum idea stops out.
    # If the same contract gets materially cheaper, re-enter only after the
    # underlying and option quote both turn back in our direction. This catches
    # the "right idea, early/mistimed entry" case without blind revenge buys.
    REENTRY_WATCH_SEC = 600.0
    REENTRY_MIN_ORIGINAL_PEAK_PCT = 3.0
    REENTRY_MIN_DISCOUNT_PCT = 20.0
    REENTRY_MIN_OPTION_REBOUND_PCT = 4.0
    REENTRY_MIN_ALIGNED_60S_PCT = 0.10
    REENTRY_MIN_ALIGNED_20S_PCT = 0.06
    REENTRY_MIN_ACCEL_RATIO = 0.45
    REENTRY_MIN_EXPECTED_EDGE_PCT = 8.0
    REENTRY_ALLOWED_SETUPS = frozenset({"MOM_BURST", "TREND_FLOW", "MOVE_PULLBACK"})

    # GPFC #95: BTC options have much larger absolute premiums than ETH. With
    # a ~$10 account, ATM/near-OTM BTC options frequently require $7-$12
    # collateral for one contract, so the old 30% allocation meant "BTC can
    # never trade" during the exact waterfall we wanted. Allow one BTC contract
    # when collateral fits most of a tiny account, and scan further OTM strikes.
    BTC_SMALL_ACCOUNT_MAX_ALLOC = 0.90
    BTC_AFFORDABLE_OTM_SCAN = 6
    BTC_SMALL_ACCOUNT_MIN_DELTA_ABS = 0.25
    BTC_SMALL_ACCOUNT_MIN_SCORE = 62.0
    BTC_SMALL_ACCOUNT_MIN_TURNOVER_USD = 2_000_000

    # GPFC #91: ICT-style location + structure setup.
    # The bot may only enter after price reacts at a 15m fair-value-gap midpoint,
    # prints a 1m change of character, then retests the 1m FVG that caused it.
    FVG_CHOCH_MIN_15M_GAP_PCT = 0.06
    FVG_CHOCH_MIN_1M_GAP_PCT = 0.015
    FVG_CHOCH_ZONE_LOOKBACK_15M = 72
    FVG_CHOCH_CHOCH_LOOKBACK_1M = 12
    FVG_CHOCH_RETEST_TOLERANCE_PCT = 0.04
    FVG_CHOCH_MAX_ZONE_AGE_15M = 48
    FVG_CHOCH_MIN_TURNOVER_USD = 4_000_000
    FVG_CHOCH_MIN_IV = 0.25
    FVG_CHOCH_MAX_SPREAD_PCT = 2.5
    FVG_CHOCH_MAX_MARK_GAP_PCT = 6.0
    FVG_CHOCH_COOLDOWN_SEC = 900.0
    FVG_CHOCH_ZONE_COOLDOWN_SEC = 3600.0

    # GPFC #60 (round 2): time-gate constants removed.
    # OPT_HARD_MAX_HOLD_HOURS, PHASE_BREATHING_SEC, EXPIRY_GUARD_HOURS,
    # EXPIRY_GUARD_MIN_MIN deleted — exits are momentum-driven, not clock-driven.
    # _EXPIRY_CLOSE_MINUTES (instance var, 5 min) still protects against
    # worthless-expiry tickers, which is a price-of-zero condition not a clock.

    # ── Dynamic ratchet floor (GPFC #26 — tiered by peak_pnl_pct in _compute_dynamic_floor)

    # ── Position limits ───────────────────────────────────────────
    MAX_OPTION_POSITIONS = 1  # 1 option at a time

    def __init__(
        self,
        pair: str,
        executor: TradeExecutor,
        risk_manager: RiskManager,
        options_exchange: Any = None,
        futures_exchange: Any = None,
        scalp_strategy: ScalpStrategy | None = None,
        market_analyzer: Any = None,
        db: Database | None = None,
    ) -> None:
        super().__init__(pair, executor, risk_manager)
        self.options_exchange: ccxt.Exchange | None = options_exchange
        self.futures_exchange: ccxt.Exchange | None = futures_exchange
        self._scalp = scalp_strategy
        self._market_analyzer = market_analyzer
        self._db = db
        self._exchange_id = "delta"

        # Asset info
        self._base_asset = "BTC" if "BTC" in pair else "ETH"

        # Option chain cache
        self._option_chain: list[dict[str, Any]] = []
        self._chain_last_refresh: float = 0.0
        self._selected_expiry: datetime | None = None
        self._available_strikes: list[float] = []

        # Position state
        self.in_position = False
        self.option_side: str | None = None  # "call" or "put"
        self.option_symbol: str | None = None  # ccxt unified symbol
        self.entry_premium: float = 0.0
        self.entry_time: float = 0.0
        self._contracts: int = 1  # dynamic — set by _calculate_option_contracts
        self._candle_alloc_pct: float = 35.0  # dynamic — set by signal strength
        self.highest_premium: float = 0.0
        self._trailing_active: bool = False
        # GPFC #71: ratcheted absolute floor (only goes UP). Set on every TRAIL
        # tick to max(prev_locked, tier_floor_for_current_peak). Reset on entry.
        self._locked_trail_floor_pct: float = 0.0
        # GPFC #71: last trail floor pct already persisted to trades.metadata.
        # Bumped each time the locked floor escalates to a new tier so the
        # dashboard can show {trail_armed: true, trail_floor_pct: X} without
        # spamming a write every tick.
        self._last_trail_floor_pct_written: float = -1.0
        # Pending-tick counter for OPT_PEAK_TRAIL confirmation. Incremented on
        # each tick where the pullback condition is met, reset when it isn't.
        # Exit only fires once this reaches PULLBACK_CONFIRMATION_TICKS AND the
        # spot-momentum veto doesn't hold.
        self._peak_trail_pending_ticks: int = 0
        # GPFC #78: live tracking for phase-based exit (set each exit tick).
        self._peak_pnl_pct: float = 0.0
        self._current_pnl_pct: float = 0.0
        self._exit_in_progress: bool = False
        # GPFC #80: count Phase A/B SL deferrals while spot remains favorable.
        # Resets on entry; persisted to trades.metadata each defer.
        self._sl_defer_count: int = 0
        self._phase_trail_defer_count: int = 0
        self.strike_price: float = 0.0
        self.expiry_dt: datetime | None = None

        # Stats
        self._tick_count: int = 0
        self.hourly_wins: int = 0
        self.hourly_losses: int = 0
        self.hourly_pnl: float = 0.0

        # Skip-logging throttle
        self._last_skip_reason: str = ""
        self._last_skip_time: float = 0.0
        self._SKIP_LOG_INTERVAL = 5 * 60  # 5 minutes

        # Last-action timestamp (wall-clock) for dashboard "X seconds ago" display
        self._last_action_at: float = 0.0

        # Dashboard state write interval
        self._STATE_WRITE_INTERVAL = 30  # Write to DB every 30 seconds
        self._last_state_write: float = 0.0

        # Ticker failure tracking
        self._consecutive_ticker_failures: int = 0
        self._MAX_TICKER_FAILURES = 6
        self._EXPIRY_CLOSE_MINUTES = 5

        # Last known premium — used as exit price when position disappears
        self._last_known_premium: float = 0.0
        self._last_spot_price: float = 0.0
        self._entry_context: str = ""
        # GPFC #47: monotonic timestamp of last non-absurd ticker fetch — used
        # to gate the last_known fallback so one bad tick doesn't freeze writes.
        self._last_good_ticker_at: float = 0.0
        # GPFC #74 FIX: cached ticker for on_fill_fallback (sync context).
        self._last_option_ticker: dict | None = None

        # Cooldowns
        self._position_gone_cooldown_until: float = 0.0
        self._POSITION_GONE_COOLDOWN_SEC = 300
        self._no_fill_cooldown_until: float = 0.0

        # DB trade ID
        self._db_trade_id: int | None = None
        self._paper_futures_id: int | None = None
        self._paper_futures_entry_spot: float = 0.0
        self._paper_futures_peak_pct: float = 0.0
        self._paper_futures_direction: str | None = None

        # Regime skip logging throttle
        self._last_regime_log: float = 0.0
        self._current_regime: str | None = None

        # Position verification
        self._position_verify_tick: int = 0
        self._position_verify_failures: int = 0
        self._MAX_VERIFY_FAILURES = 10
        # GPFC #44: require 2 consecutive empty positions API responses before
        # treating a position as "gone". A single empty response was closing
        # real winners due to transient Delta positions-API staleness.
        self._position_verify_empty_count: int = 0
        self._MIN_VERIFY_EMPTY_CYCLES = 2

        # Dynamic ratchet floor (computed from peak + energy)
        self._opt_ratchet_floor: float = 0.0

        # ── Squeeze state ──────────────────────────────────────────
        # Rolling premium history for cheap-threshold computation: (monotonic_time, ask)
        self._premium_history: deque[tuple[float, float]] = deque(maxlen=360)
        # True when current position was entered on a squeeze signal
        self._is_squeeze_entry: bool = False
        # Monotonic time when confirmed breakout entry was placed
        self._squeeze_breakout_time: float | None = None

        # ── Breakout confirmation state (GPFC #21 — Dynamic Breakout) ─────────────────
        # True while waiting for dynamic confirmation window to complete
        self._breakout_pending: bool = False
        # "UP" or "DOWN"
        self._breakout_direction: str | None = None
        # Monotonic time when breakout was first detected
        self._breakout_time: float | None = None
        # Premium ask at the moment breakout was detected
        self._breakout_entry_ask: float = 0.0
        # Option symbol selected at breakout detection
        self._breakout_symbol: str | None = None
        # Strike selected at breakout detection
        self._breakout_strike: float | None = None
        # "call" or "put"
        self._breakout_option_type: str | None = None
        # Number of contracts calculated at breakout detection
        self._breakout_contracts: int = 0
        # Confidence score at breakout detection
        self._breakout_confidence: float = 0.0
        # BB width at breakout detection (for logging)
        self._breakout_bb_width: float = 0.0
        # Velocity of breakout: % price move in last 3 candles (GPFC #21)
        self._breakout_velocity_pct: float = 0.0
        # Dynamic confirmation window in seconds (GPFC #21)
        self._breakout_confirmation_secs: int = 60
        # Last spot price when breakout was detected (for velocity calc)
        self._breakout_spot_price: float = 0.0
        # Entry setup tag for pending execution path
        self._pending_entry_setup: str = "SQUEEZE"

        # Dashboard chain panel cached state
        self._cached_candle_momentum: dict | None = None
        self._cached_bot_state: str = "scanning"
        self._cached_target_strike: float | None = None

        # ── Dashboard signals panel state ─────────────────────────
        self._squeeze_status: str = "WAITING"  # ACTIVE / WAITING
        self._bb_width_pct: float = 0.0  # Current BB width %
        self._last_kc_width_pct: float = 0.0  # GPFC #61: last computed KC width %
        self._bb_position: float = 0.5  # Where price sits in bands (0-1)
        self._direction_bias: str = "NEUTRAL"  # CALL / PUT / NEUTRAL
        self._premium_current_ask: float = 0.0  # Current ATM ask
        self._premium_cheap_threshold: float = 0.0  # Cheap threshold price
        self._last_action: str = "SCANNING"  # SQUEEZE_FILL / SQUEEZE_NO_FILL / SCANNING
        self._squeeze_duration_candles: int = 0  # How long squeeze has been active
        self._squeeze_active_since: float | None = None  # When squeeze started
        self._position_opened_at: str | None = (
            None  # ISO timestamp when position was entered
        )

        # ── GPFC #21: Breakout state for dashboard ─────────────────
        self._breakout_state: str = "NONE"  # NONE/DETECTED/CONFIRMED/FAKEOUT

        # ── GPFC #22 Part 2: Momentum tracking for "let winners ride" ─────────────────
        self._momentum_price_history: deque[tuple[float, float]] = deque(
            maxlen=20
        )  # (time, price)
        self._premium_energy_history: deque[tuple[float, float]] = deque(
            maxlen=20
        )  # (time, option premium)
        self._MOMENTUM_CHECK_WINDOW_SEC = 60.0  # Look back 60s for momentum
        self._MOMENTUM_THRESHOLD_PCT = 0.1  # Min 0.1% momentum to ride
        # GPFC #52: per-trade tracking for dynamic exits.
        # ``_spot_at_entry`` is the underlying spot at fill; ``_entry_underlying_move``
        # is the 60s underlying %-move at fill (sets dynamic thesis tolerance);
        # ``_peak_timestamp`` is the monotonic timestamp of the highest premium.
        self._spot_at_entry: float = 0.0
        self._entry_underlying_move: float = 0.0
        self._peak_timestamp: float = 0.0
        self._prev_highest_premium: float = 0.0
        self._position_premium_history: deque[tuple[float, float]] = deque(maxlen=180)
        # GPFC #26: premium ~30s ago for ratchet velocity (fast reversal vs slow drift)
        self._last_30s_premium: float | None = None
        self._atm_call_ask: float = 0.0
        self._atm_put_ask: float = 0.0
        self._prev_call_ask: float = 0.0
        self._prev_put_ask: float = 0.0
        self._prev2_call_ask: float = 0.0
        self._prev2_put_ask: float = 0.0
        self._atm_call_history: deque[tuple[float, float, float]] = deque(maxlen=240)
        self._atm_put_history: deque[tuple[float, float, float]] = deque(maxlen=240)

        # ── Caching for squeeze detection ─────────────────────────
        # Cache OHLCV data to avoid refetching within same scan tick
        self._cached_ohlcv: list[list[float]] | None = None
        self._cached_ohlcv_time: float = 0.0
        self._OHLCV_CACHE_SEC = 25  # Cache valid for 25 seconds

        # ── GPFC #60 round 2 / #63: regime classifier + entry-signal capture ───
        # Regime classifier cache — recomputed every 30s.
        self._cached_regime: str = "UNKNOWN"
        self._regime_cache_at: float = 0.0
        # Captured entry signal snapshot — built at entry, written to DB metadata.
        self._pending_entry_signals: dict[str, Any] | None = None
        self._last_entry_quality: dict[str, Any] | None = None
        self._pending_entry_path_override: str | None = None
        self._position_setup_type: str | None = None

        # GPFC #86: websocket impulse/pullback state.
        self._move_pullback_state: dict[str, Any] | None = None
        self._last_ws_wake_at: float = 0.0
        self._last_trend_flow_entry_at: float = 0.0
        self._last_premium_wave_entry_at: float = 0.0
        self._reentry_watch: dict[str, Any] | None = None
        self._last_fvg_choch_entry_at: float = 0.0
        self._fvg_choch_zone_cooldowns: dict[str, float] = {}
        self._last_fvg_choch_signal: dict[str, Any] | None = None
        self._last_fvg_choch_state: dict[str, Any] = {
            "status": "WAITING",
            "reason": "waiting_for_15m_fvg_response",
        }
        self._fvg_choch_pending: dict[str, Any] | None = None
        self._cached_ohlcv_15m: list[list[float]] | None = None
        self._cached_ohlcv_15m_time: float = 0.0


    # ==================================================================
    # ACTIVITY LOGGING
    # ==================================================================

    async def _log_activity(
        self,
        event_type: str,
        description: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log an event to activity_log (visible on dashboard Live Activity)."""
        if self._db:
            try:
                await self._db.log_activity(
                    event_type=event_type,
                    pair=self.pair,
                    description=description,
                    exchange="delta",
                    metadata=metadata,
                )
            except Exception as e:
                self.logger.debug("[%s] activity_log write failed: %s", self.pair, e)

    async def _log_skip(
        self, reason: str, metadata: dict[str, Any] | None = None
    ) -> None:
        """Log an options skip event (throttled to avoid spam)."""
        now = time.monotonic()
        if (
            reason == self._last_skip_reason
            and (now - self._last_skip_time) < self._SKIP_LOG_INTERVAL
        ):
            return
        self._last_skip_reason = reason
        self._last_skip_time = now
        await self._log_activity("options_skip", reason, metadata)

    def on_underlying_ws_tick(self, price: float) -> bool:
        """Consume Delta underlying WS ticks and wake the option loop on a setup.

        The WS handler stays synchronous and cheap: it updates spot momentum,
        maintains the MOVE_PULLBACK state machine, and wakes the normal async
        check loop only when a pullback has re-confirmed.
        """
        if price <= 0:
            return False

        self._last_spot_price = float(price)
        self._update_momentum_history(float(price))

        if self.in_position:
            return False
        if "MOVE_PULLBACK" not in self.ENABLED_SETUPS:
            return False

        now = time.monotonic()
        momentum_60s = self._underlying_momentum_pct()
        momentum_20s = self._underlying_short_momentum_pct(20.0)
        direction: str | None = None
        if (
            momentum_60s >= self.MOVE_PULLBACK_MOM_60S_PCT
            and momentum_20s >= self.MOVE_PULLBACK_MOM_20S_PCT
        ):
            direction = "UP"
        elif (
            momentum_60s <= -self.MOVE_PULLBACK_MOM_60S_PCT
            and momentum_20s <= -self.MOVE_PULLBACK_MOM_20S_PCT
        ):
            direction = "DOWN"

        state = self._move_pullback_state
        if direction:
            if not state or state.get("direction") != direction:
                impulse_start = self._get_spot_price_at(self._MOMENTUM_CHECK_WINDOW_SEC) or price
                state = {
                    "direction": direction,
                    "start_price": impulse_start,
                    "extreme_price": price,
                    "detected_at": now,
                    "ready": False,
                    "retraced": False,
                    "retrace_frac": 0.0,
                    "reconfirm_pct": 0.0,
                }
                self._move_pullback_state = state
                self.logger.info(
                    "[%s] MOVE_PULLBACK_DETECTED dir=%s ws60=%+.2f%% ws20=%+.2f%% spot=%.2f",
                    self.pair,
                    direction,
                    momentum_60s,
                    momentum_20s,
                    price,
                )
            else:
                if direction == "UP":
                    state["extreme_price"] = max(float(state["extreme_price"]), price)
                else:
                    state["extreme_price"] = min(float(state["extreme_price"]), price)

        state = self._move_pullback_state
        if not state:
            return False

        age = now - float(state.get("detected_at", now))
        if age > self.MOVE_PULLBACK_MAX_AGE_SEC:
            self._move_pullback_state = None
            return False

        direction = str(state.get("direction"))
        start_price = float(state.get("start_price") or 0)
        extreme_price = float(state.get("extreme_price") or 0)
        if start_price <= 0 or extreme_price <= 0:
            return False

        if direction == "UP":
            impulse_pct = (extreme_price - start_price) / start_price * 100.0
            retrace_pct = (extreme_price - price) / start_price * 100.0
            reconfirm_pct = momentum_20s
        elif direction == "DOWN":
            impulse_pct = (start_price - extreme_price) / start_price * 100.0
            retrace_pct = (price - extreme_price) / start_price * 100.0
            reconfirm_pct = -momentum_20s
        else:
            return False

        if impulse_pct < self.MOVE_PULLBACK_MIN_IMPULSE_PCT:
            return False

        retrace_frac = retrace_pct / impulse_pct if impulse_pct > 0 else 0.0
        if (
            self.MOVE_PULLBACK_MIN_RETRACE_FRAC
            <= retrace_frac
            <= self.MOVE_PULLBACK_MAX_RETRACE_FRAC
            and not state.get("retraced")
        ):
            state["retraced"] = True
            state["retrace_frac"] = retrace_frac
            state["retraced_at"] = now
            state["retrace_price"] = price
            return False

        if not state.get("retraced"):
            return False

        retrace_price = float(state.get("retrace_price") or price)
        if retrace_price <= 0:
            return False
        if direction == "UP":
            second_leg_pct = (price - retrace_price) / retrace_price * 100.0
        else:
            second_leg_pct = (retrace_price - price) / retrace_price * 100.0
        if second_leg_pct < self.MOVE_PULLBACK_SECOND_LEG_PCT:
            return False

        if reconfirm_pct < self.MOVE_PULLBACK_RECONFIRM_20S_PCT:
            return False

        state["ready"] = True
        state["reconfirm_pct"] = reconfirm_pct
        state["second_leg_pct"] = second_leg_pct
        if now - self._last_ws_wake_at < self.MOVE_PULLBACK_WAKE_COOLDOWN_SEC:
            return False

        self._last_ws_wake_at = now
        self.wake()
        return True

    # ==================================================================
    # LIFECYCLE
    # ==================================================================

    async def on_start(self) -> None:
        """Load option markets on startup + restore position state from DB."""
        self.logger.info(
            "[CONFIDENCE] GPFC #88 model: event entries use aligned_mom; "
            "Gate ≥ %.0f. Setups enabled: %s.",
            self.CONFIDENCE_MIN_ENTRY,
            ",".join(sorted(self.ENABLED_SETUPS)),
        )
        if self.options_exchange:
            try:
                await self.options_exchange.load_markets()
                opt_count = sum(
                    1
                    for m in self.options_exchange.markets.values()
                    if m.get("type") == "option"
                )
                self.logger.info(
                    "[%s] Options exchange loaded — %d option markets",
                    self.pair,
                    opt_count,
                )
            except Exception as e:
                self.logger.error(
                    "[%s] Failed to load options markets: %s", self.pair, e
                )

        await self._refresh_option_chain()

        # Restore position state from DB if engine restarted with open option trade
        await self._restore_position_from_db()

        # GPFC: Startup check for stuck positions
        if self.in_position:
            startup_signals = await self._startup_stuck_position_check()
            # Note: Can't return signals from on_start, but force exit is now pending if needed

        _bb_w = (
            self.SQUEEZE_BB_WIDTH_BTC
            if self._base_asset == "BTC"
            else self.SQUEEZE_BB_WIDTH_ETH
        )
        self.logger.info(
            "[%s] OPTIONS SCALP ACTIVE — BB_SQUEEZE strategy (GPFC #23) | "
            "BB_width<%.1f%% KC_squeeze fill_wait=%ds "
            "SL=%d%% Trail=%d%%/%d%% Pullback=%d%% Phase1=%ds Alloc=%s%s",
            self.pair,
            _bb_w,
            self.SQUEEZE_FILL_WAIT_SEC,
            int(self.SL_PREMIUM_LOSS_PCT),
            int(self.OPT_TRAIL_TIERS[0][0]),
            int(self.OPT_TRAIL_TIERS[0][1]),
            int(self.PULLBACK_EXIT_PCT),
            self.PHASE1_HANDS_OFF_SEC,
            f"{int(self.CAPITAL_PER_TRADE_MIN_PCT * 100)}-{int(self.CAPITAL_PER_TRADE_MAX_PCT * 100)}% per trade",
            f" | RESTORED: {self.option_side} {self.option_symbol}"
            if self.in_position
            else "",
        )

    async def _restore_position_from_db(self) -> None:
        """Restore in-memory position state from DB after engine restart."""
        if not self._db or not self._db.is_connected:
            return

        try:
            open_trades = await self._db.get_open_trades(pair=None)
            for trade in open_trades:
                if trade.get("strategy") != "options_scalp":
                    continue
                trade_pair = trade.get("pair", "")
                trade_asset = trade_pair.split("/")[0] if "/" in trade_pair else ""
                if trade_asset != self._base_asset:
                    continue

                # Found our open option trade — restore state
                self._position_premium_history.clear()
                self._last_30s_premium = None
                self.in_position = True
                OptionsScalpStrategy._global_in_position = True
                OptionsScalpStrategy._global_position_asset = self._base_asset
                self.option_symbol = trade_pair
                self.entry_premium = trade.get("entry_price", 0)
                self.entry_time = time.monotonic()
                metadata = trade.get("metadata") or {}
                try:
                    self._spot_at_entry = float(
                        metadata.get("spot_at_entry") or self._last_spot_price or 0
                    )
                except (TypeError, ValueError):
                    self._spot_at_entry = float(self._last_spot_price or 0)
                self._entry_underlying_move = 0.15  # conservative mid-band tolerance
                self._peak_timestamp = self.entry_time
                self._prev_highest_premium = self.entry_premium
                self._phase_trail_defer_count = 0
                self._position_opened_at = (
                    trade.get("opened_at") or datetime.now(timezone.utc).isoformat()
                )
                # Restore peak from DB if available, else use current_price
                stored_peak_pnl = trade.get("peak_pnl", 0) or 0
                if stored_peak_pnl > 0 and self.entry_premium > 0:
                    # Calculate highest_premium from stored peak_pnl percentage
                    peak_premium = self.entry_premium * (1 + stored_peak_pnl / 100)
                    self.highest_premium = max(
                        self.highest_premium, peak_premium, self.entry_premium
                    )
                else:
                    self.highest_premium = max(
                        self.highest_premium,
                        self.entry_premium,
                        trade.get("current_price") or self.entry_premium,
                    )

                # Restore dynamic floor based on recovered highest premium.
                if self.entry_premium > 0:
                    restored_peak_pct = (
                        (self.highest_premium - self.entry_premium)
                        / self.entry_premium
                        * 100
                    )
                    self._opt_ratchet_floor = self._compute_dynamic_floor(
                        restored_peak_pct, 1.0
                    )

                if trade_pair.endswith("-C"):
                    self.option_side = "call"
                elif trade_pair.endswith("-P"):
                    self.option_side = "put"
                else:
                    self.option_side = "call"

                self._trailing_active = trade.get("position_state") == "trailing"
                self.strike_price = trade.get("stop_loss", 0) or 0

                parts = trade_pair.split("-")
                if len(parts) >= 3:
                    try:
                        self.strike_price = float(parts[-2])
                    except ValueError:
                        pass

                if len(parts) >= 2:
                    try:
                        expiry_str = parts[-3] if len(parts) >= 4 else parts[1]
                        self.expiry_dt = datetime.strptime(
                            expiry_str, "%y%m%d"
                        ).replace(
                            hour=12,
                            tzinfo=timezone.utc,
                        )
                    except (ValueError, IndexError):
                        pass

                self._contracts = max(1, int(trade.get("contracts") or trade.get("amount") or 1))

                self.logger.info(
                    "[%s] RESTORED from DB: %s x%d %s strike=$%.0f entry=$%.4f peak=$%.4f trail=%s",
                    self.pair,
                    self.option_side,
                    self._contracts,
                    self.option_symbol,
                    self.strike_price,
                    self.entry_premium,
                    self.highest_premium,
                    self._trailing_active,
                )
                break

        except Exception as e:
            self.logger.error(
                "[%s] Failed to restore position from DB: %s", self.pair, e
            )

    async def _startup_stuck_position_check(self) -> list[Signal]:
        """On startup, check if restored position is stuck with large loss."""
        if not self.in_position or not self.option_symbol:
            return []

        # Check exchange for actual position
        try:
            positions = await self.options_exchange.fetch_positions()
            has_position = any(
                pos.get("symbol") == self.option_symbol
                and float(pos.get("contracts", 0) or 0) != 0
                for pos in positions
            )

            if not has_position:
                self.logger.info(
                    "[%s] STARTUP_CHECK: Position not found on exchange — already closed",
                    self.option_symbol,
                )
                return []

            # Position exists — check if it's stuck (P&L < -5%)
            current_bid = self._last_known_premium
            try:
                ticker = await self.options_exchange.fetch_ticker(self.option_symbol)
                # GPFC #47: mark-first, never `last`.
                current_bid = (
                    self._get_option_premium(ticker)
                    or float(ticker.get("bid") or 0)
                    or self.entry_premium
                )
            except Exception:
                pass

            if self.entry_premium > 0 and current_bid > 0:
                pnl_pct = (current_bid - self.entry_premium) / self.entry_premium * 100

                if pnl_pct < -5.0:
                    self.logger.critical(
                        "[%s] STARTUP_CRITICAL: Restored position stuck at %.1f%% — normal exit logic will handle",
                        self.option_symbol,
                        pnl_pct,
                    )
                    return []
                else:
                    self.logger.info(
                        "[%s] STARTUP_CHECK: Position OK at %.1f%% — normal monitoring",
                        self.option_symbol,
                        pnl_pct,
                    )

        except Exception as e:
            self.logger.warning(
                "[%s] STARTUP_CHECK: Failed to verify position: %s",
                self.option_symbol,
                e,
            )

        return []

    async def _update_position_state_in_db(self, current_premium: float) -> None:
        """Write live position state to the trades table so dashboard shows real P&L."""
        if not self._db or not self._db.is_connected:
            return
        if not self.in_position or not self.option_symbol:
            return

        # GPFC #45: PREMIUM_SANITY guard — a real option premium physically
        # cannot move 500% in a single tick. Values like that are a corrupt
        # ticker (underlying spot leaking in, stale cache, etc.). Refuse to
        # write anything for this tick so the DB keeps its last good state.
        if (
            self.entry_premium > 0
            and current_premium > 0
            and abs(current_premium - self.entry_premium) / self.entry_premium > 5.0
        ):
            self.logger.warning(
                "[%s] PREMIUM_SANITY_REJECT current=$%.4f entry=$%.4f "
                "(move=%.0f%%) — not writing",
                self.option_symbol,
                current_premium,
                self.entry_premium,
                abs(current_premium - self.entry_premium) / self.entry_premium * 100,
            )
            return

        try:
            pnl_pct = 0.0
            if self.entry_premium > 0:
                pnl_pct = (
                    (current_premium - self.entry_premium) / self.entry_premium * 100
                )

            peak_pnl = 0.0
            if self.entry_premium > 0:
                peak_pnl = (
                    (self.highest_premium - self.entry_premium)
                    / self.entry_premium
                    * 100
                )

            state = "trailing" if self._trailing_active else "holding"

            open_trade = await self._db.get_open_trade(
                pair=self.option_symbol,
                exchange="delta",
                strategy="options_scalp",
            )
            if open_trade:
                live_pnl = self._calc_options_pnl(
                    self.entry_premium,
                    current_premium,
                    self._contracts,
                )

                await self._db.update_trade(
                    open_trade["id"],
                    {
                        "position_state": state,
                        "current_price": round(current_premium, 8),
                        "current_pnl": round(pnl_pct, 4),
                        "peak_pnl": round(peak_pnl, 4),
                        "pnl": round(live_pnl, 8),
                        "pnl_pct": round(pnl_pct, 4),
                    },
                )
        except Exception as e:
            self.logger.debug("[%s] position state DB update failed: %s", self.pair, e)

    # ==================================================================
    # OPTIONS P&L HELPER
    # ==================================================================

    @staticmethod
    def _get_option_premium(ticker: dict[str, Any]) -> float:
        """GPFC #47: return best-estimate premium for an option.

        Delta's ``last`` field is unreliable for thinly-traded options — it
        returns ``None`` or occasionally the underlying spot price when no
        recent trade exists. ``info.mark_price`` is always correct. Prefer:
        mark_price → mid(bid, ask) → bid → ask. Never use ``last``.
        """
        if not ticker:
            return 0.0
        info = ticker.get("info")
        if isinstance(info, dict):
            for key in (
                "mark_price",
                "mark",
                "index_price",
                "mp",
                "settlement_price",
            ):
                v = info.get(key)
                if v is not None:
                    try:
                        fv = float(v)
                    except (TypeError, ValueError):
                        continue
                    if fv > 0:
                        return fv
        for key in (
            "mark",
            "indexPrice",
            "index",
            "settle",
            "settlementPrice",
        ):
            v = ticker.get(key)
            if v is not None:
                try:
                    fv = float(v)
                except (TypeError, ValueError):
                    continue
                if fv > 0:
                    return fv
        bid = float(ticker.get("bid") or 0)
        ask = float(ticker.get("ask") or 0)
        if bid > 0 and ask > 0:
            return (bid + ask) / 2.0
        if bid > 0:
            return bid
        if ask > 0:
            return ask
        return 0.0

    @staticmethod
    def _long_option_mtm_premium(ticker: dict[str, Any]) -> float:
        """Back-compat wrapper — delegates to GPFC #47 ``_get_option_premium``.

        Previously had a ``last``-price fallback which was the root cause of
        spot-price leakage into option P&L (#3070, #3071). Now routes through
        the safe helper so every caller gets mark-first pricing.
        """
        return OptionsScalpStrategy._get_option_premium(ticker)

    def _calc_options_pnl(
        self,
        entry_premium: float,
        exit_premium: float,
        contracts: int,
    ) -> float:
        """Calculate gross P&L for an options trade using contract multiplier."""
        multiplier = self.CONTRACT_MULTIPLIER.get(self._base_asset, 0.01)
        return (exit_premium - entry_premium) * contracts * multiplier

    # ==================================================================
    # OPTION CHAIN MANAGEMENT
    # ==================================================================

    async def _refresh_option_chain(self) -> None:
        """Fetch available option contracts, filter for valid expiries."""
        now = time.monotonic()
        if (
            now - self._chain_last_refresh < self.CHAIN_REFRESH_INTERVAL
            and self._option_chain
        ):
            return

        if not self.options_exchange:
            return

        try:
            if self._chain_last_refresh > 0:
                await self.options_exchange.load_markets(True)

            markets = self.options_exchange.markets
            now_utc = datetime.now(timezone.utc)
            min_expiry = now_utc + timedelta(hours=self.MIN_EXPIRY_HOURS)

            chain: list[dict[str, Any]] = []
            for symbol, market in markets.items():
                if market.get("type") != "option":
                    continue
                if market.get("base") != self._base_asset:
                    continue
                if not market.get("active", True):
                    continue

                expiry_ts = market.get("expiry")
                if expiry_ts is None:
                    continue
                expiry_dt = datetime.fromtimestamp(expiry_ts / 1000, tz=timezone.utc)
                if expiry_dt < min_expiry:
                    continue

                chain.append(
                    {
                        "symbol": symbol,
                        "strike": float(market.get("strike", 0)),
                        "option_type": (market.get("optionType") or "").lower(),
                        "expiry": expiry_dt,
                    }
                )

            chain.sort(key=lambda x: (x["expiry"], x["strike"]))
            self._option_chain = chain
            self._chain_last_refresh = now

            if chain:
                self._selected_expiry = chain[0]["expiry"]
                hours_away = (self._selected_expiry - now_utc).total_seconds() / 3600

                if hours_away < self.EXPIRY_SWITCH_HOURS:
                    next_expiries = sorted(
                        set(
                            c["expiry"]
                            for c in chain
                            if c["expiry"] > self._selected_expiry
                        )
                    )
                    if next_expiries:
                        old_exp = self._selected_expiry
                        self._selected_expiry = next_expiries[0]
                        new_hours = (
                            self._selected_expiry - now_utc
                        ).total_seconds() / 3600
                        self.logger.info(
                            "[%s] EXPIRY_SWITCH: nearest %s only %.1fh away — "
                            "switching to %s (%.1fh away)",
                            self.pair,
                            old_exp.strftime("%b %d %H:%M UTC"),
                            hours_away,
                            self._selected_expiry.strftime("%b %d %H:%M UTC"),
                            new_hours,
                        )
                        hours_away = new_hours

                self._available_strikes = sorted(
                    set(
                        c["strike"]
                        for c in chain
                        if c["expiry"] == self._selected_expiry
                    )
                )
                self.logger.info(
                    "[%s] Option chain refreshed: %d contracts, "
                    "selected expiry=%s (%.1fh away), %d strikes",
                    self.pair,
                    len(chain),
                    self._selected_expiry.strftime("%b %d %H:%M UTC"),
                    hours_away,
                    len(self._available_strikes),
                )
            else:
                self._selected_expiry = None
                self._available_strikes = []
                self.logger.warning("[%s] No valid option contracts found", self.pair)

        except Exception as e:
            self.logger.error("[%s] Failed to refresh option chain: %s", self.pair, e)

    # ==================================================================
    # STRIKE SELECTION
    # ==================================================================

    def _get_atm_strike(self, current_price: float) -> float | None:
        """Find the ATM strike nearest to spot price."""
        if not self._available_strikes:
            return None
        return min(self._available_strikes, key=lambda s: abs(s - current_price))

    def _get_otm_candidates(
        self,
        atm_strike: float,
        option_type: str,
        extra: int = 0,
    ) -> list[float]:
        """Get sorted OTM strikes away from ATM (up for calls, down for puts)."""
        if option_type == "call":
            candidates = sorted(s for s in self._available_strikes if s > atm_strike)
        else:
            candidates = sorted(
                (s for s in self._available_strikes if s < atm_strike),
                reverse=True,
            )
        if extra > 0:
            start = self.MAX_OTM_STRIKES
            return candidates[start : start + extra]
        return candidates[: self.MAX_OTM_STRIKES]

    def _entry_candidate_strikes(self, atm_strike: float, option_type: str) -> list[float]:
        """Return strikes to try for an entry, ordered by affordability."""
        if self._base_asset == "BTC":
            strikes = list(self._get_otm_candidates(
                atm_strike,
                option_type,
                extra=self.BTC_AFFORDABLE_OTM_SCAN,
            ))
            strikes = list(self._get_otm_candidates(
                atm_strike,
                option_type,
            )) + strikes
            strikes.append(atm_strike)
        else:
            strikes = [atm_strike]
            for strike in self._get_otm_candidates(atm_strike, option_type):
                strikes.append(strike)

        out: list[float] = []
        for strike in strikes:
            if strike not in out:
                out.append(strike)
        return out

    def _is_btc_small_account_mode(self) -> bool:
        capital = self.risk_manager.get_exchange_capital(self._exchange_id)
        return self._base_asset == "BTC" and 0 < capital < self.OPT_SURVIVAL_BALANCE

    def _btc_small_account_score_floor(self) -> float | None:
        return self.BTC_SMALL_ACCOUNT_MIN_SCORE if self._is_btc_small_account_mode() else None

    def _setup_turnover_floor(self, setup_floor: float) -> float:
        if self._is_btc_small_account_mode():
            return min(setup_floor, self.BTC_SMALL_ACCOUNT_MIN_TURNOVER_USD)
        return setup_floor

    def _record_atm_premium_history(
        self,
        *,
        call_ask: float,
        put_ask: float,
        spot_price: float,
    ) -> None:
        """Track real ATM option asks so entries can react to option premium waves."""
        now = time.monotonic()
        cutoff = now - 20 * 60
        if call_ask > 0:
            self._atm_call_history.append((now, call_ask, spot_price))
        if put_ask > 0:
            self._atm_put_history.append((now, put_ask, spot_price))
        while self._atm_call_history and self._atm_call_history[0][0] < cutoff:
            self._atm_call_history.popleft()
        while self._atm_put_history and self._atm_put_history[0][0] < cutoff:
            self._atm_put_history.popleft()

    @staticmethod
    def _history_value_at_least_seconds_ago(
        history: deque[tuple[float, float, float]],
        seconds: float,
    ) -> tuple[float, float] | None:
        if not history:
            return None
        now = time.monotonic()
        target = now - seconds
        candidate = None
        for t, premium, spot in reversed(history):
            if t <= target:
                candidate = (premium, spot)
                break
        if candidate is None and history:
            _, premium, spot = history[0]
            candidate = (premium, spot)
        return candidate

    def _premium_wave_snapshot(self, option_type: str) -> dict[str, float] | None:
        history = self._atm_call_history if option_type == "call" else self._atm_put_history
        current = self._atm_call_ask if option_type == "call" else self._atm_put_ask
        if current <= 0 or len(history) < 2:
            return None

        five = self._history_value_at_least_seconds_ago(history, 300.0)
        fifteen = self._history_value_at_least_seconds_ago(history, 900.0)
        if not five or not fifteen:
            return None
        prem_5m, spot_5m = five
        prem_15m, spot_15m = fifteen
        spot_now = self._last_spot_price
        if prem_5m <= 0 or prem_15m <= 0 or spot_now <= 0 or spot_5m <= 0 or spot_15m <= 0:
            return None

        premium_5m = (current - prem_5m) / prem_5m * 100.0
        premium_15m = (current - prem_15m) / prem_15m * 100.0
        now = time.monotonic()
        recent_premiums = [
            float(premium)
            for t, premium, _spot in history
            if premium > 0 and now - t <= 300.0
        ]
        recent_low = min(recent_premiums) if recent_premiums else current
        premium_from_5m_low = (
            (current - recent_low) / recent_low * 100.0
            if recent_low > 0
            else 0.0
        )
        option_dir = 1.0 if option_type == "call" else -1.0
        underlying_5m = option_dir * ((spot_now - spot_5m) / spot_5m * 100.0)
        underlying_15m = option_dir * ((spot_now - spot_15m) / spot_15m * 100.0)
        return {
            "premium_5m_pct": premium_5m,
            "premium_15m_pct": premium_15m,
            "premium_from_5m_low_pct": premium_from_5m_low,
            "premium_5m_low": recent_low,
            "underlying_5m_pct": underlying_5m,
            "underlying_15m_pct": underlying_15m,
            "premium_now": current,
            "premium_5m_ago": prem_5m,
            "premium_15m_ago": prem_15m,
        }

    def _htf_trend_direction(self, ohlcv: list[list[float]] | None) -> tuple[str | None, float, float]:
        """Return dominant 1m-derived 15m/45m direction for entry filtering."""
        if not ohlcv or len(ohlcv) < 46:
            return None, 0.0, 0.0
        try:
            close_now = float(ohlcv[-1][4])
            close_15m_ago = float(ohlcv[-16][4])
            close_45m_ago = float(ohlcv[-46][4])
        except (TypeError, ValueError, IndexError):
            return None, 0.0, 0.0
        if close_now <= 0 or close_15m_ago <= 0 or close_45m_ago <= 0:
            return None, 0.0, 0.0

        move_15m = (close_now - close_15m_ago) / close_15m_ago * 100.0
        move_45m = (close_now - close_45m_ago) / close_45m_ago * 100.0

        if (
            move_15m <= -self.TREND_REGIME_STRONG_15M_PCT
            or (
                move_15m <= -self.TREND_REGIME_15M_PCT
                and move_45m <= -self.TREND_REGIME_45M_PCT
            )
        ):
            return "DOWN", move_15m, move_45m
        if (
            move_15m >= self.TREND_REGIME_STRONG_15M_PCT
            or (
                move_15m >= self.TREND_REGIME_15M_PCT
                and move_45m >= self.TREND_REGIME_45M_PCT
            )
        ):
            return "UP", move_15m, move_45m
        return None, move_15m, move_45m

    def _direction_allowed_by_trend(
        self,
        direction: str,
        ohlcv: list[list[float]] | None,
        setup_type: str,
    ) -> bool:
        """Block countertrend entries while the higher-timeframe tape is clear."""
        if not self.TREND_COUNTER_BLOCK_ENABLED:
            return True
        trend_dir, move_15m, move_45m = self._htf_trend_direction(ohlcv)
        if not trend_dir or trend_dir == direction:
            return True
        self.logger.info(
            "[%s] %s_COUNTERTREND_SKIP: dir=%s blocked by %s trend "
            "(15m=%+.2f%% 45m=%+.2f%%)",
            self.pair,
            setup_type,
            direction,
            trend_dir,
            move_15m,
            move_45m,
        )
        return False

    def _direction_allowed_by_analyzer(self, direction: str, setup_type: str) -> bool:
        """Block tiny bounce entries against the broader analyzed market tape."""
        if not self.TREND_COUNTER_BLOCK_ENABLED or not self._market_analyzer:
            return True
        try:
            analysis = self._market_analyzer.last_analysis_for(self.pair)
        except Exception:
            analysis = None
        if not analysis:
            return True

        condition = getattr(analysis, "condition", None)
        condition_value = getattr(condition, "value", condition)
        analyzer_dir = str(getattr(analysis, "direction", "neutral") or "neutral").lower()
        if condition != MarketCondition.TRENDING and condition_value != MarketCondition.TRENDING.value:
            return True
        if analyzer_dir not in {"bullish", "bearish"}:
            return True

        desired = "bullish" if direction == "UP" else "bearish"
        if analyzer_dir == desired:
            return True

        try:
            adx = float(getattr(analysis, "adx", 0.0) or 0.0)
            change_1h = float(getattr(analysis, "price_change_1h", 0.0) or 0.0)
            change_24h = float(getattr(analysis, "price_change_24h", 0.0) or 0.0)
        except (TypeError, ValueError):
            return True

        signed_1h = change_1h if analyzer_dir == "bullish" else -change_1h
        signed_24h = change_24h if analyzer_dir == "bullish" else -change_24h
        if (
            adx >= self.ANALYZER_COUNTER_BLOCK_ADX
            and (
                signed_1h >= self.ANALYZER_COUNTER_BLOCK_1H_PCT
                or signed_24h >= self.ANALYZER_COUNTER_BLOCK_24H_PCT
            )
        ):
            self.logger.info(
                "[%s] %s_ANALYZER_COUNTERTREND_SKIP: dir=%s blocked by %s analyzer "
                "(ADX=%.1f 1h=%+.2f%% 24h=%+.2f%%)",
                self.pair,
                setup_type,
                direction,
                analyzer_dir.upper(),
                adx,
                change_1h,
                change_24h,
            )
            return False
        return True

    def _build_option_symbol(
        self,
        strike: float,
        option_type: str,
        expiry: datetime,
    ) -> str | None:
        """Find the ccxt unified symbol for the given option parameters."""
        target_type = option_type.lower()
        for opt in self._option_chain:
            if (
                opt["strike"] == strike
                and opt["option_type"] == target_type
                and opt["expiry"] == expiry
            ):
                return opt["symbol"]

        # Fallback: construct manually
        expiry_str = expiry.strftime("%y%m%d")
        strike_str = str(int(strike))
        cp = "C" if target_type == "call" else "P"
        symbol = f"{self._base_asset}/USD:USD-{expiry_str}-{strike_str}-{cp}"
        self.logger.warning(
            "[%s] Option not in chain, constructed: %s",
            self.pair,
            symbol,
        )
        return symbol

    # ==================================================================
    # DASHBOARD STATE
    # ==================================================================

    async def _write_dashboard_state(self) -> None:
        """Write current options state to DB for dashboard every 30 seconds."""
        now = time.monotonic()
        if now - self._last_state_write < self._STATE_WRITE_INTERVAL:
            return
        self._last_state_write = now

        if not self._db:
            return

        # ── Signal state from scalp ──
        signal_strength = 0
        signal_side: str | None = None
        signal_reason = ""
        spot_price = 0.0

        if self._scalp and hasattr(self._scalp, "last_signal_state"):
            ss = self._scalp.last_signal_state
            if ss:
                signal_strength = ss.get("strength", 0)
                signal_side = ss.get("side")
                signal_reason = ss.get("reason", "")
                spot_price = ss.get("current_price", 0)

        # Fallback: fetch spot price from futures exchange
        if spot_price <= 0 and self.futures_exchange:
            try:
                ticker = await self.futures_exchange.fetch_ticker(self.pair)
                spot_price = ticker.get("last") or ticker.get("bid") or 0
            except Exception:
                pass

        if spot_price > 0:
            self._last_spot_price = float(spot_price)
            self._update_momentum_history(float(spot_price))

        # ── Expiry info ──
        expiry_label: str | None = None
        expiry_ts: str | None = None
        atm_strike: float | None = None
        call_premium: float | None = None
        put_premium: float | None = None

        if self._selected_expiry:
            now_utc = datetime.now(timezone.utc)
            hours_away = (self._selected_expiry - now_utc).total_seconds() / 3600
            expiry_label = (
                f"{self._selected_expiry.strftime('%b %d %H:%M UTC')} — "
                f"{int(hours_away)}h away"
            )
            expiry_ts = self._selected_expiry.isoformat()

            if self._available_strikes and spot_price > 0:
                atm_strike = min(
                    self._available_strikes, key=lambda s: abs(s - spot_price)
                )

                raw_call_ask: float = 0.0
                raw_put_ask: float = 0.0

                try:
                    call_sym = self._build_option_symbol(
                        atm_strike,
                        "call",
                        self._selected_expiry,
                    )
                    if call_sym and self.options_exchange:
                        t = await self.options_exchange.fetch_ticker(call_sym)
                        # GPFC #47: never fall back to `last` — Delta leaks spot there.
                        raw_call_ask = float(t.get("ask") or t.get("bid") or 0)
                        call_premium = raw_call_ask or None
                except Exception:
                    pass

                try:
                    put_sym = self._build_option_symbol(
                        atm_strike,
                        "put",
                        self._selected_expiry,
                    )
                    if put_sym and self.options_exchange:
                        t = await self.options_exchange.fetch_ticker(put_sym)
                        # GPFC #47: never fall back to `last` — Delta leaks spot there.
                        raw_put_ask = float(t.get("ask") or t.get("bid") or 0)
                        put_premium = raw_put_ask or None
                except Exception:
                    pass

                # Keep premium_current_ask live during scan phase (raw ask, not last price)
                if (
                    not self.in_position
                    and not self._breakout_pending
                    and raw_call_ask > 0
                ):
                    self._premium_current_ask = raw_call_ask

                if raw_call_ask > 0 or raw_put_ask > 0:
                    if raw_call_ask > 0:
                        self._prev2_call_ask = self._prev_call_ask
                        self._prev_call_ask = self._atm_call_ask
                        self._atm_call_ask = raw_call_ask
                    if raw_put_ask > 0:
                        self._prev2_put_ask = self._prev_put_ask
                        self._prev_put_ask = self._atm_put_ask
                        self._atm_put_ask = raw_put_ask
                    self._record_atm_premium_history(
                        call_ask=raw_call_ask,
                        put_ask=raw_put_ask,
                        spot_price=float(spot_price or 0),
                    )
                    self.logger.info(
                        "[%s] SQUEEZE_SCAN: %s ATM_call_ask=$%.2f ATM_put_ask=$%.2f strike=%s",
                        self.pair,
                        self._base_asset,
                        raw_call_ask,
                        raw_put_ask,
                        atm_strike,
                    )

        # ── Chain data: top 5 calls + puts near ATM ──
        chain_calls: list[dict] = []
        chain_puts: list[dict] = []

        if (
            self._available_strikes
            and atm_strike is not None
            and spot_price > 0
            and self._selected_expiry
            and self.options_exchange
        ):
            call_strikes = sorted(
                s for s in self._available_strikes if s >= atm_strike
            )[:5]
            for strike in call_strikes:
                try:
                    sym = self._build_option_symbol(
                        strike, "call", self._selected_expiry
                    )
                    if sym:
                        t = await self.options_exchange.fetch_ticker(sym)
                        chain_calls.append(
                            {
                                "strike": strike,
                                "bid": t.get("bid") or 0,
                                "ask": t.get("ask") or 0,
                            }
                        )
                except Exception:
                    chain_calls.append({"strike": strike, "bid": 0, "ask": 0})

            put_strikes = sorted(
                (s for s in self._available_strikes if s <= atm_strike),
                reverse=True,
            )[:5]
            for strike in put_strikes:
                try:
                    sym = self._build_option_symbol(
                        strike, "put", self._selected_expiry
                    )
                    if sym:
                        t = await self.options_exchange.fetch_ticker(sym)
                        chain_puts.append(
                            {
                                "strike": strike,
                                "bid": t.get("bid") or 0,
                                "ask": t.get("ask") or 0,
                            }
                        )
                except Exception:
                    chain_puts.append({"strike": strike, "bid": 0, "ask": 0})

        # ── Balance ──
        balance: float | None = None
        try:
            balance = self.risk_manager.get_exchange_capital(self._exchange_id)
        except Exception:
            pass

        # ── Position info ──
        position_side: str | None = None
        position_strike: float | None = None
        position_symbol: str | None = None
        entry_prem: float | None = None
        current_prem: float | None = None
        pnl_pct: float | None = None
        pnl_usd: float | None = None
        trailing_active = False
        highest_prem: float | None = None

        if self.in_position and self.option_symbol:
            position_side = self.option_side
            position_strike = self.strike_price
            position_symbol = self.option_symbol
            entry_prem = self.entry_premium
            highest_prem = self.highest_premium
            trailing_active = self._trailing_active

            try:
                if self.options_exchange:
                    ticker = await self.options_exchange.fetch_ticker(
                        self.option_symbol
                    )
                    # GPFC #47: mark-first, never `last`.
                    current_prem = self._get_option_premium(ticker) or None
                    if not current_prem:
                        current_prem = float(ticker.get("bid") or 0) or None
                    if current_prem and entry_prem and entry_prem > 0:
                        pnl_pct = (current_prem - entry_prem) / entry_prem * 100
                        pnl_usd = (current_prem - entry_prem) * self._contracts
            except Exception:
                pass

        # ── Squeeze info for dashboard ──
        squeeze_info: dict[str, Any] | None = None
        if self._is_squeeze_entry:
            squeeze_info = {
                "is_squeeze_entry": True,
                "breakout_time": self._squeeze_breakout_time,
            }

        # ── MB entry-quality telemetry (GPFC #38 / #38b) ──
        # Acceleration ratio: |move_last_20s| / |move_last_60s|. Useful for
        # post-hoc review of why MB did or didn't fire.
        mb_acceleration = round(self._underlying_acceleration_ratio(), 3)
        try:
            htf_trend_dir, htf_trend_15m, htf_trend_45m = self._htf_trend_direction(ohlcv)
        except Exception:
            htf_trend_dir, htf_trend_15m, htf_trend_45m = None, 0.0, 0.0

        # ── GPFC #62/#63: post-#60 signals — regime, KC width, in-position telemetry ──
        kc_w = self._last_kc_width_pct
        bb_kc_ratio = (
            round(self._bb_width_pct / kc_w, 3)
            if kc_w > 0 and self._bb_width_pct > 0
            else None
        )
        # Position-only telemetry — None when flat so the frontend can hide.
        if self.in_position and self.option_side and self.entry_premium > 0:
            our_dir = 1.0 if self.option_side == "call" else -1.0
            underlying_vs_position = round(
                our_dir * self._underlying_momentum_pct(), 3
            )
            premium_velocity_pct = round(self._calc_premium_velocity(), 4)
            peak_pnl_for_trail = (
                (self.highest_premium - self.entry_premium)
                / self.entry_premium
                * 100
            ) if self.highest_premium > 0 else 0.0
            trail_armed = peak_pnl_for_trail >= self.OPT_TRAIL_TIERS[0][0]
        else:
            underlying_vs_position = None
            premium_velocity_pct = None
            trail_armed = False

        # ── Signals panel state ──
        signals_panel = {
            "bb_width_pct": round(self._bb_width_pct, 3),
            "bb_width_threshold": (
                self.SQUEEZE_BB_WIDTH_BTC
                if self._base_asset == "BTC"
                else self.SQUEEZE_BB_WIDTH_ETH
            ),
            # GPFC #61/#62: KC width + BB/KC tightness ratio (< 0.5 ≈ true squeeze)
            "kc_width_pct": round(kc_w, 3),
            "bb_kc_width_ratio": bb_kc_ratio,
            # GPFC #60r2: regime classifier (log-only gating, dashboard display)
            "regime": self._cached_regime,
            "momentum_60s_pct": round(self._underlying_momentum_pct(), 3),
            "momentum_entry_score": round(
                max(
                    0.0,
                    min(100.0, abs(self._underlying_momentum_pct()) / 0.20 * 100.0),
                ),
                1,
            ),
            "confidence_min_entry": self.CONFIDENCE_MIN_ENTRY,
            # GPFC #62: spot freshness — mom_20s / mom_60s. Same field as
            # momentum_acceleration_ratio; aliased here for clarity in the UI.
            "momentum_freshness_ratio": mb_acceleration,
            "momentum_acceleration_ratio": mb_acceleration,
            "momentum_burst_threshold_pct": self.MOMENTUM_BURST_THRESHOLD_PCT,
            "trend_direction": htf_trend_dir,
            "trend_15m_pct": round(htf_trend_15m, 3),
            "trend_45m_pct": round(htf_trend_45m, 3),
            "trend_strong_15m_pct": self.TREND_REGIME_STRONG_15M_PCT,
            "trend_regime_15m_pct": self.TREND_REGIME_15M_PCT,
            "trend_regime_45m_pct": self.TREND_REGIME_45M_PCT,
            "squeeze_status": self._squeeze_status,
            "bb_position": round(self._bb_position, 2),
            "direction_bias": self._direction_bias,
            "premium_current_ask": round(self._premium_current_ask, 4)
            if self._premium_current_ask > 0
            else None,
            "premium_cheap_threshold": round(self._premium_cheap_threshold, 4)
            if self._premium_cheap_threshold > 0
            else None,
            "last_action": self._last_action,
            "squeeze_duration_candles": self._squeeze_duration_candles,
            # GPFC #63: in-position telemetry (None when flat)
            "premium_velocity_pct": premium_velocity_pct,
            "underlying_vs_position_pct": underlying_vs_position,
            "trail_armed": trail_armed,
            "trail_first_activation_pct": self.OPT_TRAIL_TIERS[0][0],
            "fvg_choch": self._last_fvg_choch_state,
        }

        state = {
            "spot_price": spot_price or None,
            "expiry": expiry_ts,
            "expiry_label": expiry_label,
            "atm_strike": atm_strike,
            "call_premium": call_premium,
            "put_premium": put_premium,
            "signal_strength": signal_strength,
            "signal_side": signal_side,
            "signal_reason": signal_reason,
            "position_side": position_side,
            "position_strike": position_strike,
            "position_symbol": position_symbol,
            "entry_premium": entry_prem,
            "current_premium": current_prem,
            "pnl_pct": round(pnl_pct, 2) if pnl_pct is not None else None,
            "pnl_usd": round(pnl_usd, 4) if pnl_usd is not None else None,
            "trailing_active": trailing_active,
            "highest_premium": highest_prem,
            "position_opened_at": self._position_opened_at,
            "chain_calls": chain_calls,
            "chain_puts": chain_puts,
            "bot_state": self._cached_bot_state,
            "target_strike": self._cached_target_strike,
            "balance": round(balance, 2) if balance is not None else None,
            "squeeze_info": squeeze_info,
            "signals_panel": signals_panel,
            # ── Exit/entry config snapshot (GPFC #38 / #38b) ─────────────
            # Echoes the live values so we can confirm on the dashboard that
            # the deployed bot is actually running the tuned thresholds and
            # review behaviour later without digging into source.
            "exit_config": {
                "sl_premium_loss_pct": self.SL_PREMIUM_LOSS_PCT,
                "pullback_activate_pct": self.PULLBACK_ACTIVATE_PCT,
                "pullback_exit_pct": self.PULLBACK_EXIT_PCT,
                "pullback_confirmation_ticks": self.PULLBACK_CONFIRMATION_TICKS,
                "pullback_spot_veto_pct": self.PULLBACK_SPOT_VETO_PCT,
                "breakeven_stop_activate_pct": self.BREAKEVEN_STOP_ACTIVATE_PCT,
                "breakeven_stop_exit_pct": self.BREAKEVEN_STOP_EXIT_PCT,
                "phase_b_protect_arm_pct": self.PHASE_B_BREAKEVEN_ARM_PCT,
                "phase_b_protect_arm_buffer_pct": self.PHASE_B_BREAKEVEN_ARM_BUFFER_PCT,
                "phase_b_protect_exit_pct": self.PHASE_B_BREAKEVEN_EXIT_PCT,
            },
            "peak_trail_pending_ticks": self._peak_trail_pending_ticks,
            "spot_momentum_20s_pct": round(self._underlying_short_momentum_pct(20.0), 3),
            "entry_config": {
                "mb_threshold_pct": self.MOMENTUM_BURST_THRESHOLD_PCT,
                "mb_min_ask_rise_pct": self.MOMENTUM_BURST_MIN_ASK_RISE_PCT,
                "mb_min_turnover_usd": self.MOM_BURST_MIN_TURNOVER_USD,
                "confidence_min_entry": self.CONFIDENCE_MIN_ENTRY,
                "entry_min_turnover_usd": self.ENTRY_MIN_TURNOVER_USD,
                "fvg_choch_min_turnover_usd": self.FVG_CHOCH_MIN_TURNOVER_USD,
                "fvg_choch_min_iv": self.FVG_CHOCH_MIN_IV,
                "phase_b_protect_arm_pct": self.PHASE_B_BREAKEVEN_ARM_PCT,
                "phase_b_protect_arm_buffer_pct": self.PHASE_B_BREAKEVEN_ARM_BUFFER_PCT,
                "phase_b_protect_exit_pct": self.PHASE_B_BREAKEVEN_EXIT_PCT,
            },
            # Phase-B protection arm state for the current position. True when
            # the trade's peak is close enough to the 8% arm threshold that a
            # retrace to the protected green floor will flatten it.
            "breakeven_stop_armed": (
                self.in_position
                and self.highest_premium > 0
                and self.entry_premium > 0
                and (
                    (self.highest_premium - self.entry_premium) / self.entry_premium * 100
                ) >= (
                    self.PHASE_B_BREAKEVEN_ARM_PCT
                    - self.PHASE_B_BREAKEVEN_ARM_BUFFER_PCT
                )
            ),
            # Top-level squeeze fields (read directly by dashboard)
            "bb_width_pct": round(self._bb_width_pct, 3),
            "bb_width_threshold": (
                self.SQUEEZE_BB_WIDTH_BTC
                if self._base_asset == "BTC"
                else self.SQUEEZE_BB_WIDTH_ETH
            ),
            "momentum_60s_pct": round(self._underlying_momentum_pct(), 3),
            "squeeze_active": self._squeeze_status == "ACTIVE",
            "bb_position": round(self._bb_position, 2),
            "direction_bias": self._direction_bias,
            "premium_current_ask": round(self._premium_current_ask, 4)
            if self._premium_current_ask > 0
            else None,
            "premium_cheap_threshold": round(self._premium_cheap_threshold, 4)
            if self._premium_cheap_threshold > 0
            else None,
            "last_squeeze_action": self._last_action,
            "last_action_at": (
                datetime.fromtimestamp(
                    self._last_action_at, tz=timezone.utc
                ).isoformat()
                if self._last_action_at > 0
                else None
            ),
            # Breakout confirmation state (GPFC #21)
            "breakout_state": self._breakout_state
            if self._breakout_state
            else (
                "DETECTED"
                if self._breakout_pending
                else (
                    self._last_action
                    if self._last_action
                    in ("BREAKOUT_CONFIRMED", "BREAKOUT_FAKEOUT", "BREAKOUT_NO_FILL")
                    else "NONE"
                )
            ),
            "breakout_direction": self._breakout_direction,
            "breakout_velocity_pct": round(self._breakout_velocity_pct * 100, 3)
            if self._breakout_velocity_pct > 0
            else None,
            "breakout_confirmation_secs_remaining": (
                max(
                    0,
                    int(
                        self._breakout_confirmation_secs
                        - (time.monotonic() - self._breakout_time)
                    ),
                )
                if self._breakout_pending and self._breakout_time is not None
                else None
            ),
            "breakout_detected_at": (
                datetime.fromtimestamp(self._breakout_time, tz=timezone.utc).isoformat()
                if self._breakout_time
                else None
            ),
            "breakout_premium_at_detection": round(self._breakout_entry_ask, 6)
            if self._breakout_entry_ask > 0
            else None,
            # 30-min premium range (actual low/high from history)
            "premium_lowest_ask": (
                round(min(a for _, a in self._premium_history), 4)
                if self._premium_history
                else None
            ),
            "premium_highest_ask": (
                round(max(a for _, a in self._premium_history), 4)
                if self._premium_history
                else None
            ),
        }

        # GPFC #22 Part 1: Wrap options_state upsert in try/except — never crash the bot
        try:
            await self._db.upsert_options_state(self.pair, state)
        except Exception as e:
            self.logger.warning(
                "[%s] options_state upsert failed (non-critical): %s", self.pair, e
            )

    # ==================================================================
    # MAIN CHECK LOOP
    # ==================================================================

    async def check(self) -> list[Signal]:
        """Main tick: refresh chain, check for entry/exit."""
        self._tick_count += 1

        # Log capital utilization periodically (every 10 ticks ≈ 50 seconds)
        if self._tick_count % 10 == 0:
            total_capital = self.risk_manager.get_exchange_capital(self._exchange_id)
            available = self.risk_manager.get_available_capital(self._exchange_id)
            if total_capital > 0:
                utilization = (total_capital - available) / total_capital * 100
                self.logger.info(
                    "CAPITAL_UTIL: %s %.1f%% deployed, $%.2f free / $%.2f total",
                    self.pair,
                    utilization,
                    available,
                    total_capital,
                )

        # Periodic chain refresh
        await self._refresh_option_chain()

        # GPFC #60 round 2: classify regime once per tick (cached 30s, log-only).
        try:
            await self._classify_regime()
        except Exception as e:
            self.logger.debug("[%s] regime classify failed: %s", self.pair, e)

        # Pre-compute bot state BEFORE dashboard write so timers are fresh
        self._precompute_bot_state()

        # Write dashboard state every 30 seconds
        await self._write_dashboard_state()

        # In position: manage exit
        if self.in_position:
            self._cached_bot_state = "in_position"

            # GPFC #76 Part 4: force-close 5 minutes before contract expiry.
            # This eliminates the largest source of POSITION_GONE ghosts — holding
            # options to expiry where Delta settles silently and the bot has no fill.
            if self.expiry_dt:
                _secs_to_expiry = (
                    self.expiry_dt - datetime.now(timezone.utc)
                ).total_seconds()
                if 0 < _secs_to_expiry <= 300:
                    self.logger.info(
                        "[%s] pre_expiry — %ds to expiry, closing at market now",
                        self.pair,
                        int(_secs_to_expiry),
                    )
                    _pre_exp_premium = self._last_known_premium or self.entry_premium or 0.0
                    _pre_exp_pnl_pct = (
                        (_pre_exp_premium - self.entry_premium) / self.entry_premium * 100
                        if self.entry_premium > 0 else 0.0
                    )
                    return await self._do_option_exit(
                        _pre_exp_premium, _pre_exp_pnl_pct, "pre_expiry"
                    )

            return await self._check_option_exit()

        # Not in position: look for squeeze entry
        return await self._check_option_entry()

    def _precompute_bot_state(self) -> None:
        """Set _cached_bot_state for cooldown timers before dashboard write."""
        if self.in_position:
            self._cached_bot_state = "in_position"
            return

        # GPFC #21: No cooldown after no-fill (removed for dynamic breakout)
        # Keeping check for compatibility with other strategies
        if time.monotonic() < self._no_fill_cooldown_until:
            remaining = self._no_fill_cooldown_until - time.monotonic()
            self._cached_bot_state = f"blocked:no_fill_cooldown:{int(remaining)}s"
            return

        # Position-gone cooldown
        if time.monotonic() < self._position_gone_cooldown_until:
            remaining = self._position_gone_cooldown_until - time.monotonic()
            self._cached_bot_state = f"blocked:position_gone_cooldown:{int(remaining)}s"
            return

        if self._cached_bot_state.startswith(
            "blocked:position_gone_cooldown"
        ) or self._cached_bot_state.startswith("blocked:no_fill_cooldown"):
            self._cached_bot_state = "scanning"

    # ==================================================================
    # BB SQUEEZE DETECTION
    # ==================================================================

    async def _get_ohlcv_for_squeeze(self) -> list[list[float]] | None:
        """Fetch OHLCV data with caching to avoid refetching within same scan tick."""
        now = time.monotonic()
        if (
            self._cached_ohlcv
            and (now - self._cached_ohlcv_time) < self._OHLCV_CACHE_SEC
        ):
            return self._cached_ohlcv

        if not self.futures_exchange:
            return None

        try:
            # Fetch 60 candles to have enough for BB(20) + KC(20) + ATR calc
            ohlcv = await self.futures_exchange.fetch_ohlcv(self.pair, "1m", limit=60)
            if not ohlcv or len(ohlcv) < 30:
                return None
            self._cached_ohlcv = ohlcv
            self._cached_ohlcv_time = now
            return ohlcv
        except Exception as e:
            self.logger.debug("[%s] fetch_ohlcv failed: %s", self.pair, e)
            return None

    async def _detect_squeeze(
        self,
    ) -> tuple[bool, float, float, float, int, float, float, float, float] | None:
        """Detect BB Squeeze: BB width < threshold and BB contained within KC.

        Returns:
            (is_squeeze, bb_width_pct, bb_position, avg_vol_ratio, candles_used,
             bb_upper, bb_lower, kc_upper, kc_lower)
            or None if data unavailable
        """
        ohlcv = await self._get_ohlcv_for_squeeze()
        if not ohlcv or len(ohlcv) < self.BB_PERIOD:
            return None

        # Use last 30 candles for squeeze detection
        candles = ohlcv[-30:]
        closes = [c[4] for c in candles]
        highs = [c[2] for c in candles]
        lows = [c[3] for c in candles]
        volumes = [c[5] for c in candles]

        if len(closes) < self.BB_PERIOD:
            return None

        # Calculate BB
        bb_window = closes[-self.BB_PERIOD :]
        sma = mean(bb_window)
        std = (sum((x - sma) ** 2 for x in bb_window) / len(bb_window)) ** 0.5
        bb_upper = sma + self.BB_STD_MULT * std
        bb_lower = sma - self.BB_STD_MULT * std
        bb_width_pct = (bb_upper - bb_lower) / sma * 100 if sma > 0 else 0

        # Calculate BB position (0 = at lower band, 1 = at upper band, 0.5 = middle)
        current_price = closes[-1]
        bb_position = (
            (current_price - bb_lower) / (bb_upper - bb_lower)
            if (bb_upper - bb_lower) > 0
            else 0.5
        )
        bb_position = max(0.0, min(1.0, bb_position))  # Clamp to [0, 1]

        # Calculate ATR for KC
        tr_list = []
        for i in range(1, len(candles)):
            prev_close = candles[i - 1][4]
            curr_high = candles[i][2]
            curr_low = candles[i][3]
            tr1 = curr_high - curr_low
            tr2 = abs(curr_high - prev_close)
            tr3 = abs(curr_low - prev_close)
            tr_list.append(max(tr1, tr2, tr3))

        atr_window = tr_list[-self.KC_PERIOD :]
        atr = mean(atr_window) if atr_window else 0

        # Calculate Keltner Channel
        kc_upper = sma + self.KC_ATR_MULT * atr
        kc_lower = sma - self.KC_ATR_MULT * atr

        # Squeeze condition: BB contained within KC
        is_squeeze = bb_upper < kc_upper and bb_lower > kc_lower

        # Volume ratio vs last 30 min average
        avg_vol = mean(volumes[:-5]) if len(volumes) > 5 else mean(volumes)
        recent_vol = mean(volumes[-5:])
        avg_vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1.0

        return (
            is_squeeze,
            bb_width_pct,
            bb_position,
            avg_vol_ratio,
            len(candles),
            bb_upper,
            bb_lower,
            kc_upper,
            kc_lower,
        )

    def _compute_squeeze_confidence(
        self,
        bb_width_pct: float,
        current_ask: float,
        lowest_ask: float,
        highest_ask: float,
        vol_ratio: float,
    ) -> float:
        """Compute entry confidence based on squeeze tightness, premium cheapness, and volume.

        Returns confidence score 0-1. Skip if < 0.6
        """
        # Tightness score
        if bb_width_pct < 0.5:
            tightness_score = 1.0
        elif bb_width_pct < 0.75:
            tightness_score = 0.7
        elif bb_width_pct < 1.0:
            tightness_score = 0.4
        else:
            tightness_score = 0.2

        # Cheapness score
        if highest_ask > lowest_ask:
            cheapness_pct = (current_ask - lowest_ask) / (highest_ask - lowest_ask)
            if cheapness_pct <= 0.10:
                cheapness_score = 1.0
            elif cheapness_pct <= 0.25:
                cheapness_score = 0.7
            elif cheapness_pct <= 0.50:
                cheapness_score = 0.4
            else:
                cheapness_score = 0.2
        else:
            cheapness_score = 0.5

        # Volume score
        if vol_ratio >= 1.5:
            volume_score = 1.0
        elif vol_ratio >= 1.0:
            volume_score = 0.7
        else:
            volume_score = 0.4

        # Average the three scores
        confidence = (tightness_score + cheapness_score + volume_score) / 3.0
        return confidence

    # ==================================================================
    # DYNAMIC CONFIRMATION HELPERS (GPFC #21)
    # ==================================================================

    async def _calculate_breakout_velocity(self) -> float:
        """Calculate % price move in last 3 candles for breakout velocity (GPFC #21).

        Returns velocity as decimal (e.g., 0.003 = 0.3% move).
        """
        ohlcv = await self._get_ohlcv_for_squeeze()
        if not ohlcv or len(ohlcv) < 4:
            return 0.0

        # Use last 4 candles to calculate move over last 3 periods
        # Velocity = |current close - close 3 candles ago| / close 3 candles ago
        recent_candles = ohlcv[-4:]
        old_close = recent_candles[0][4]  # Close 3 candles ago
        new_close = recent_candles[-1][4]  # Most recent close

        if old_close <= 0:
            return 0.0

        velocity = abs(new_close - old_close) / old_close
        return velocity

    def _get_confirmation_secs(self, velocity_pct: float) -> int:
        """Get dynamic confirmation window based on breakout velocity (GPFC #21) — UPDATED.

        velocity >= 0.3% → 20s (was 0s)
        velocity 0.15-0.3% → 40s (was 20s)
        velocity < 0.15% → 60s (unchanged)
        """
        velocity_pct_actual = velocity_pct * 100  # Convert to percentage

        if velocity_pct_actual >= self.BREAKOUT_CONFIRM_HIGH_VELOCITY:
            return self.BREAKOUT_CONFIRM_SEC_HIGH
        elif velocity_pct_actual >= self.BREAKOUT_CONFIRM_MED_VELOCITY:
            return self.BREAKOUT_CONFIRM_SEC_MED
        else:
            return self.BREAKOUT_CONFIRM_SEC_MAX

    # ==================================================================
    # ENTRY LOGIC
    # ==================================================================

    async def _check_option_entry(self) -> list[Signal]:
        """BB Squeeze breakout entry — scan for squeeze, wait for breakout, confirm, then enter."""
        self._cached_bot_state = "scanning"
        self._cached_target_strike = None

        # GLOBAL POSITION LOCK — only 1 option across all assets (BTC+ETH)
        if False and OptionsScalpStrategy._global_in_position and not self.in_position:
            if self._tick_count % 6 == 0:
                self.logger.info(
                    "[%s] OPTIONS GLOBAL_LOCK — %s has an open option",
                    self.pair,
                    OptionsScalpStrategy._global_position_asset or "another asset",
                )
            self._cached_bot_state = "blocked:other_asset_in_position"
            return []

        reentry_signals = await self._check_second_chance_reentry()
        if reentry_signals:
            return reentry_signals

        # POSITION_GONE cooldown
        if time.monotonic() < self._position_gone_cooldown_until:
            remaining = self._position_gone_cooldown_until - time.monotonic()
            if self._tick_count % 6 == 0:
                self.logger.info(
                    "[%s] OPTIONS COOLDOWN after POSITION_GONE — %.0fs remaining",
                    self.pair,
                    remaining,
                )
            self._cached_bot_state = f"blocked:position_gone_cooldown:{int(remaining)}s"
            return []

        # STEP 3: If breakout detected, run confirmation window check
        if self._breakout_pending:
            return await self._check_breakout_confirmation()

        premium_wave_signals = await self._check_premium_wave_entry()
        if premium_wave_signals:
            return premium_wave_signals

        fvg_choch_signals = await self._check_fvg_choch_entry()
        if fvg_choch_signals:
            return fvg_choch_signals

        move_pullback_signals = await self._check_move_pullback_entry()
        if move_pullback_signals:
            return move_pullback_signals

        trend_flow_signals = await self._check_trend_flow_entry()
        if trend_flow_signals:
            return trend_flow_signals

        # STEP 1: DETECT BB SQUEEZE
        squeeze_result = await self._detect_squeeze()
        if squeeze_result is None:
            self._squeeze_status = "WAITING"
            self._direction_bias = "NEUTRAL"
            return []

        (
            is_squeeze,
            bb_width_pct,
            bb_position,
            avg_vol_ratio,
            _candles_used,
            bb_upper,
            bb_lower,
            kc_upper,
            kc_lower,
        ) = squeeze_result
        bb_width_threshold = (
            self.SQUEEZE_BB_WIDTH_BTC
            if self._base_asset == "BTC"
            else self.SQUEEZE_BB_WIDTH_ETH
        )

        # Update dashboard signals panel
        self._bb_width_pct = bb_width_pct
        # GPFC #61: capture KC width % alongside BB width for entry-signals snapshot.
        kc_mid = (kc_upper + kc_lower) / 2.0 if (kc_upper + kc_lower) else 0.0
        kc_width_pct = ((kc_upper - kc_lower) / kc_mid * 100) if kc_mid > 0 else 0.0
        self._last_kc_width_pct = kc_width_pct
        self._bb_position = bb_position

        if self._tick_count % 6 == 0:
            self.logger.info(
                "[%s] SQUEEZE_SCAN: BB_width=%.3f%% squeeze=%s (thresh=%.1f%%) "
                "atm_ask=$%.2f strike=%s",
                self.pair,
                bb_width_pct,
                is_squeeze,
                bb_width_threshold,
                self._premium_current_ask,
                self._cached_target_strike,
            )

        if not is_squeeze:
            # STEP 2: Was squeeze active? Check for breakout direction before resetting state.
            if self._squeeze_active_since is not None:
                await self._handle_squeeze_breakout(
                    bb_upper,
                    bb_lower,
                    kc_upper,
                    kc_lower,
                    bb_width_pct,
                    avg_vol_ratio,
                )
                if self._breakout_pending:
                    return []

            momentum_signals = await self._check_momentum_burst_entry()
            if momentum_signals:
                return momentum_signals

            self._squeeze_status = "WAITING"
            self._squeeze_active_since = None
            self._squeeze_duration_candles = 0
            self._direction_bias = "NEUTRAL"
            self._cached_bot_state = "scanning:no_squeeze"
            return []

        # Track squeeze duration
        if self._squeeze_active_since is None:
            self._squeeze_active_since = time.monotonic()
        self._squeeze_duration_candles += 1

        # Check if BB width is tight enough
        if bb_width_pct >= bb_width_threshold:
            self._squeeze_status = "ACTIVE"
            self._direction_bias = "NEUTRAL"
            self._cached_bot_state = "scanning:bb_too_wide"
            return []

        self._squeeze_status = "ACTIVE"
        self._direction_bias = "NEUTRAL"  # No bias until breakout is confirmed
        if self._tick_count % 6 == 0:
            self.logger.info(
                "[%s] SQUEEZE_DETECTED: BB_width=%.3f%% KC_contains_BB=true — waiting for breakout",
                self.pair,
                bb_width_pct,
            )
        self._cached_bot_state = "squeeze:waiting_for_breakout"
        return []

    async def _check_second_chance_reentry(self) -> list[Signal]:
        """Reload a recently stopped momentum contract only after reconfirmation."""
        watch = self._reentry_watch
        if not watch or self.in_position:
            return []

        now = time.monotonic()
        expires_at = float(watch.get("expires_at") or 0.0)
        symbol = str(watch.get("symbol") or "")
        option_type = str(watch.get("option_type") or "")
        setup_type = str(watch.get("setup_type") or "MOM_BURST")
        direction = str(watch.get("direction") or "")
        if not symbol or option_type not in {"call", "put"} or now > expires_at:
            self._reentry_watch = None
            return []
        if setup_type not in self.REENTRY_ALLOWED_SETUPS or setup_type not in self.ENABLED_SETUPS:
            self._reentry_watch = None
            return []
        if int(watch.get("attempts") or 0) >= 1:
            self._reentry_watch = None
            return []
        if not self.options_exchange:
            return []

        try:
            ticker = await self.options_exchange.fetch_ticker(symbol)
        except Exception as e:
            self.logger.debug("[%s] REENTRY ticker failed for %s: %s", self.pair, symbol, e)
            return []

        try:
            ask = float(ticker.get("ask") or 0)
            bid = float(ticker.get("bid") or 0)
        except (TypeError, ValueError):
            return []
        if ask < self.MIN_PREMIUM_USD:
            return []

        original_entry = float(watch.get("original_entry") or 0.0)
        lowest_ask = float(watch.get("lowest_ask") or ask)
        if ask > 0 and (lowest_ask <= 0 or ask < lowest_ask):
            watch["lowest_ask"] = ask
            watch["lowest_at"] = now
            lowest_ask = ask

        if original_entry <= 0 or lowest_ask <= 0:
            return []

        discount_pct = (original_entry - ask) / original_entry * 100.0
        rebound_pct = (ask - lowest_ask) / lowest_ask * 100.0
        if discount_pct < self.REENTRY_MIN_DISCOUNT_PCT:
            if self._tick_count % 6 == 0:
                self.logger.info(
                    "[%s] REENTRY_WAIT: %s discount %.1f%% < %.1f%%",
                    self.pair,
                    symbol,
                    discount_pct,
                    self.REENTRY_MIN_DISCOUNT_PCT,
                )
            return []
        if rebound_pct < self.REENTRY_MIN_OPTION_REBOUND_PCT:
            if self._tick_count % 6 == 0:
                self.logger.info(
                    "[%s] REENTRY_WAIT: %s cheap but not lifting yet "
                    "(ask=$%.4f low=$%.4f rebound=%.1f%%/%.1f%%)",
                    self.pair,
                    symbol,
                    ask,
                    lowest_ask,
                    rebound_pct,
                    self.REENTRY_MIN_OPTION_REBOUND_PCT,
                )
            return []

        dir_sign = 1.0 if option_type == "call" else -1.0
        aligned_60s = dir_sign * self._calc_underlying_mom(60.0)
        aligned_20s = dir_sign * self._calc_underlying_mom(20.0)
        accel = self._underlying_acceleration_ratio()
        if (
            aligned_60s < self.REENTRY_MIN_ALIGNED_60S_PCT
            or aligned_20s < self.REENTRY_MIN_ALIGNED_20S_PCT
            or accel < self.REENTRY_MIN_ACCEL_RATIO
        ):
            if self._tick_count % 6 == 0:
                self.logger.info(
                    "[%s] REENTRY_WAIT: %s discount %.1f%% rebound %.1f%% "
                    "but thesis not back (60s=%+.2f%%/%.2f%% 20s=%+.2f%%/%.2f%% accel=%.2f/%.2f)",
                    self.pair,
                    symbol,
                    discount_pct,
                    rebound_pct,
                    aligned_60s,
                    self.REENTRY_MIN_ALIGNED_60S_PCT,
                    aligned_20s,
                    self.REENTRY_MIN_ALIGNED_20S_PCT,
                    accel,
                    self.REENTRY_MIN_ACCEL_RATIO,
                )
            return []

        if bid > 0:
            spread_pct = (ask - bid) / ask * 100.0
            if spread_pct > self.ENTRY_MAX_SPREAD_PCT:
                self.logger.info(
                    "[%s] REENTRY_SPREAD_SKIP: %s spread=%.1f%% > %.1f%%",
                    self.pair,
                    symbol,
                    spread_pct,
                    self.ENTRY_MAX_SPREAD_PCT,
                )
                return []

        passes_quality, skip_reason = self._passes_entry_quality(
            ticker,
            min_iv=self.MOM_BURST_MIN_IV_FOR_ENTRY,
        )
        if not passes_quality:
            self.logger.info(
                "[%s] REENTRY_QUALITY_SKIP: %s (%s)",
                self.pair,
                skip_reason,
                symbol,
            )
            return []

        quality_ok, quality_reason, quality_snapshot = self._score_option_entry(
            ticker,
            ask,
            option_type,
            setup_type,
            min_expected_edge_pct=self.REENTRY_MIN_EXPECTED_EDGE_PCT,
        )
        if not quality_ok:
            self.logger.info(
                "[%s] REENTRY_SCORE_SKIP: %s %s edge=%.1f%% cost=%.1f%% score=%.1f",
                self.pair,
                symbol,
                quality_reason,
                quality_snapshot.get("entry_expected_edge_pct", 0.0),
                quality_snapshot.get("entry_cost_floor_pct", 0.0),
                quality_snapshot.get("entry_quality_score", 0.0),
            )
            return []

        contracts = self._calculate_option_contracts(ask, confidence=0.78)
        if contracts < 1:
            return []

        self._breakout_direction = direction or ("UP" if option_type == "call" else "DOWN")
        self._breakout_option_type = option_type
        self._breakout_symbol = symbol
        self._breakout_strike = float(watch.get("strike") or 0.0)
        self._breakout_contracts = contracts
        self._breakout_confidence = 0.78
        self._breakout_bb_width = self._bb_width_pct
        self._breakout_velocity_pct = abs(aligned_60s)
        self._pending_entry_setup = setup_type
        self._pending_entry_path_override = "mom_reentry"
        self._last_entry_quality = {
            **quality_snapshot,
            "reentry_original_entry": round(original_entry, 4),
            "reentry_lowest_ask": round(lowest_ask, 4),
            "reentry_discount_pct": round(discount_pct, 2),
            "reentry_rebound_pct": round(rebound_pct, 2),
            "reentry_after_exit_type": watch.get("exit_type"),
        }
        watch["attempts"] = int(watch.get("attempts") or 0) + 1

        self.logger.info(
            "[%s] SECOND_CHANCE_REENTRY: %s %s original=$%.4f ask=$%.4f "
            "discount=%.1f%% low=$%.4f rebound=%.1f%% 60s=%+.2f%% 20s=%+.2f%%",
            self.pair,
            setup_type,
            symbol,
            original_entry,
            ask,
            discount_pct,
            lowest_ask,
            rebound_pct,
            aligned_60s,
            aligned_20s,
        )
        return await self._execute_breakout_entry(ask)

    async def _get_ohlcv_15m_for_fvg(self) -> list[list[float]] | None:
        """Fetch 15m candles for FVG/CHoCH location detection."""
        now = time.monotonic()
        if (
            self._cached_ohlcv_15m
            and (now - self._cached_ohlcv_15m_time) < self._OHLCV_CACHE_SEC
        ):
            return self._cached_ohlcv_15m
        if not self.futures_exchange:
            return None
        try:
            ohlcv = await self.futures_exchange.fetch_ohlcv(
                self.pair, "15m", limit=self.FVG_CHOCH_ZONE_LOOKBACK_15M
            )
            if not ohlcv or len(ohlcv) < 20:
                return None
            self._cached_ohlcv_15m = ohlcv
            self._cached_ohlcv_15m_time = now
            return ohlcv
        except Exception as e:
            self.logger.debug("[%s] fetch_ohlcv 15m failed: %s", self.pair, e)
            return None

    def _find_fvg_zones(
        self,
        candles: list[list[float]],
        *,
        min_gap_pct: float,
        max_age: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return bullish/bearish fair-value gaps from OHLCV candles."""
        zones: list[dict[str, Any]] = []
        if len(candles) < 3:
            return zones
        last_idx = len(candles) - 1
        for i in range(2, len(candles)):
            c1 = candles[i - 2]
            c3 = candles[i]
            if max_age is not None and last_idx - i > max_age:
                continue
            c1_high = float(c1[2])
            c1_low = float(c1[3])
            c3_high = float(c3[2])
            c3_low = float(c3[3])
            if c1_high <= 0 or c1_low <= 0 or c3_high <= 0 or c3_low <= 0:
                continue

            if c1_high < c3_low:
                gap_low = c1_high
                gap_high = c3_low
                mid = (gap_low + gap_high) / 2.0
                gap_pct = (gap_high - gap_low) / mid * 100.0 if mid > 0 else 0.0
                if gap_pct >= min_gap_pct:
                    zones.append({
                        "type": "bullish",
                        "direction": "UP",
                        "low": gap_low,
                        "high": gap_high,
                        "mid": mid,
                        "gap_pct": gap_pct,
                        "index": i,
                        "age": last_idx - i,
                        "ts": c3[0],
                    })
            if c1_low > c3_high:
                gap_low = c3_high
                gap_high = c1_low
                mid = (gap_low + gap_high) / 2.0
                gap_pct = (gap_high - gap_low) / mid * 100.0 if mid > 0 else 0.0
                if gap_pct >= min_gap_pct:
                    zones.append({
                        "type": "bearish",
                        "direction": "DOWN",
                        "low": gap_low,
                        "high": gap_high,
                        "mid": mid,
                        "gap_pct": gap_pct,
                        "index": i,
                        "age": last_idx - i,
                        "ts": c3[0],
                    })
        return zones

    def _active_15m_fvg_response(
        self,
        zones: list[dict[str, Any]],
        candles_1m: list[list[float]],
    ) -> dict[str, Any] | None:
        """Find a recent 15m FVG midpoint response aligned with current price."""
        if not zones or len(candles_1m) < 3:
            return None
        last = candles_1m[-1]
        recent = candles_1m[-3:]
        close = float(last[4])
        best: dict[str, Any] | None = None
        for zone in reversed(zones):
            low = float(zone["low"])
            high = float(zone["high"])
            mid = float(zone["mid"])
            direction = str(zone["direction"])
            touched = any(float(c[2]) >= low and float(c[3]) <= high for c in recent)
            if not touched:
                continue
            if direction == "DOWN":
                rejected = any(float(c[2]) >= mid for c in recent) and close <= mid
            else:
                rejected = any(float(c[3]) <= mid for c in recent) and close >= mid
            if not rejected:
                continue
            zone_id = (
                f"{self._base_asset}:{zone['type']}:{int(zone['ts'])}:"
                f"{low:.2f}:{high:.2f}"
            )
            if self._fvg_choch_zone_cooldowns.get(zone_id, 0.0) > time.monotonic():
                self._last_fvg_choch_state = {
                    "status": "COOLDOWN",
                    "reason": "zone_cooldown",
                    "direction": direction,
                    "zone_mid": round(mid, 4),
                }
                continue
            candidate = dict(zone)
            candidate["zone_id"] = zone_id
            best = candidate
            break
        return best

    def _detect_1m_choch_retest(
        self,
        candles: list[list[float]],
        direction: str,
    ) -> dict[str, Any] | None:
        """Detect 1m CHoCH and a retest into the FVG that produced the break."""
        lookback = max(self.FVG_CHOCH_CHOCH_LOOKBACK_1M, 6)
        if len(candles) < lookback + 4:
            return None

        recent = candles[-(lookback + 4):]
        last = recent[-1]
        prev = recent[:-1]
        close = float(last[4])

        pending = self._fvg_choch_pending
        if pending and pending.get("direction") == direction:
            age = int((float(last[0]) - float(pending.get("created_ts", last[0]))) / 60_000)
            if age > 10:
                self._fvg_choch_pending = None
            else:
                low = float(pending["fvg_low"])
                high = float(pending["fvg_high"])
                mid = float(pending["fvg_mid"])
                if direction == "UP":
                    retested = float(last[3]) <= high and close >= mid
                else:
                    retested = float(last[2]) >= low and close <= mid
                if retested:
                    result = dict(pending)
                    result["retest_age_bars"] = age
                    self._fvg_choch_pending = None
                    return result

        if direction == "UP":
            structure_level = max(float(c[2]) for c in prev[-lookback:])
            if close <= structure_level:
                return None
            option_type = "call"
        elif direction == "DOWN":
            structure_level = min(float(c[3]) for c in prev[-lookback:])
            if close >= structure_level:
                return None
            option_type = "put"
        else:
            return None

        zones = self._find_fvg_zones(
            recent,
            min_gap_pct=self.FVG_CHOCH_MIN_1M_GAP_PCT,
            max_age=8,
        )
        zones = [z for z in zones if z["direction"] == direction]
        if not zones:
            return None
        zone = zones[-1]
        low = float(zone["low"])
        high = float(zone["high"])
        mid = float(zone["mid"])

        impulse_low = min(float(c[3]) for c in recent[-lookback:])
        impulse_high = max(float(c[2]) for c in recent[-lookback:])
        if impulse_high <= impulse_low:
            return None
        if direction == "UP":
            fib_618 = impulse_high - 0.618 * (impulse_high - impulse_low)
        else:
            fib_618 = impulse_low + 0.618 * (impulse_high - impulse_low)
        tolerance = close * self.FVG_CHOCH_RETEST_TOLERANCE_PCT / 100.0
        fib_aligned = (low - tolerance) <= fib_618 <= (high + tolerance)
        if not fib_aligned:
            return None

        self._fvg_choch_pending = {
            "direction": direction,
            "option_type": option_type,
            "structure_level": structure_level,
            "fvg_low": low,
            "fvg_high": high,
            "fvg_mid": mid,
            "fvg_gap_pct": float(zone["gap_pct"]),
            "fib_618": fib_618,
            "impulse_low": impulse_low,
            "impulse_high": impulse_high,
            "created_ts": last[0],
        }
        return None

    async def _check_fvg_choch_entry(self) -> list[Signal]:
        """Enter only after 15m FVG response + 1m CHoCH + 1m FVG retest."""
        if "FVG_CHOCH" not in self.ENABLED_SETUPS:
            return []
        now = time.monotonic()
        if now - self._last_fvg_choch_entry_at < self.FVG_CHOCH_COOLDOWN_SEC:
            self._last_fvg_choch_state = {
                "status": "COOLDOWN",
                "reason": "setup_cooldown",
            }
            return []
        if not self._selected_expiry or not self.options_exchange:
            return []

        candles_15m = await self._get_ohlcv_15m_for_fvg()
        candles_1m = await self._get_ohlcv_for_squeeze()
        if not candles_15m or not candles_1m:
            return []

        zones_15m = self._find_fvg_zones(
            candles_15m,
            min_gap_pct=self.FVG_CHOCH_MIN_15M_GAP_PCT,
            max_age=self.FVG_CHOCH_MAX_ZONE_AGE_15M,
        )
        active_zone = self._active_15m_fvg_response(zones_15m, candles_1m)
        if not active_zone:
            self._last_fvg_choch_state = {
                "status": "WAITING",
                "reason": "waiting_for_15m_fvg_response",
                "zones_15m": len(zones_15m),
            }
            return []

        choch = self._detect_1m_choch_retest(candles_1m, str(active_zone["direction"]))
        if not choch:
            pending = self._fvg_choch_pending or {}
            self._last_fvg_choch_state = {
                "status": "ARMED",
                "reason": (
                    "waiting_for_1m_fvg_retest"
                    if pending else "waiting_for_1m_choch"
                ),
                "direction": active_zone["direction"],
                "zone_mid": round(float(active_zone["mid"]), 4),
                "fvg_1m_mid": (
                    round(float(pending["fvg_mid"]), 4)
                    if pending.get("fvg_mid") is not None else None
                ),
            }
            return []

        option_type = str(choch["option_type"])
        direction = str(choch["direction"])
        spot = float(self._last_spot_price or candles_1m[-1][4])
        if spot <= 0:
            return []
        self._last_spot_price = spot
        atm_strike = self._get_atm_strike(spot)
        if atm_strike is None:
            return []
        self._cached_target_strike = atm_strike
        selected_symbol = self._build_option_symbol(
            atm_strike, option_type, self._selected_expiry
        )
        if not selected_symbol:
            return []

        try:
            ticker = await self.options_exchange.fetch_ticker(selected_symbol)
            entry_ask = float(ticker.get("ask") or ticker.get("bid") or 0)
        except Exception as e:
            self.logger.debug("[%s] FVG_CHOCH ticker failed for %s: %s", self.pair, selected_symbol, e)
            return []
        if entry_ask < self.MIN_PREMIUM_USD:
            return []

        bid = 0.0
        try:
            bid = float(ticker.get("bid") or 0)
        except (TypeError, ValueError):
            bid = 0.0
        if bid > 0:
            spread_pct = (entry_ask - bid) / entry_ask * 100.0
            if spread_pct > self.FVG_CHOCH_MAX_SPREAD_PCT:
                self.logger.info(
                    "[%s] FVG_CHOCH_SPREAD_SKIP: %s spread=%.1f%% > %.1f%%",
                    self.pair, selected_symbol, spread_pct, self.FVG_CHOCH_MAX_SPREAD_PCT,
                )
                return []

        exec_snapshot = self._entry_execution_snapshot(ticker, entry_ask, option_type)
        mark_gap_pct = exec_snapshot.get("entry_mark_gap_pct")
        if mark_gap_pct is not None and mark_gap_pct > self.FVG_CHOCH_MAX_MARK_GAP_PCT:
            self.logger.info(
                "[%s] FVG_CHOCH_EXEC_SKIP: %s ask too far above mark "
                "(gap=%.2f%% > %.2f%%)",
                self.pair, selected_symbol, mark_gap_pct, self.FVG_CHOCH_MAX_MARK_GAP_PCT,
            )
            return []

        passes_quality, skip_reason = self._passes_entry_quality(
            ticker,
            min_iv=self.FVG_CHOCH_MIN_IV,
        )
        if not passes_quality:
            self.logger.info(
                "[%s] ENTRY_QUALITY_SKIP — %s (FVG_CHOCH %s)",
                self.pair, skip_reason, selected_symbol,
            )
            return []

        info = ticker.get("info") or {}
        try:
            turnover_usd = float(info.get("turnover_usd", 0) or 0)
        except (TypeError, ValueError):
            turnover_usd = 0.0
        if turnover_usd < self.FVG_CHOCH_MIN_TURNOVER_USD:
            self.logger.info(
                "[%s] FVG_CHOCH_LIQUIDITY_SKIP: %s turnover=$%.2fM < $%.2fM",
                self.pair, selected_symbol, turnover_usd / 1_000_000,
                self.FVG_CHOCH_MIN_TURNOVER_USD / 1_000_000,
            )
            return []

        contracts = self._calculate_option_contracts(entry_ask, confidence=0.72)
        if contracts < 1:
            return []

        confidence = 72.0
        zone_gap = float(active_zone.get("gap_pct", 0.0) or 0.0)
        one_min_gap = float(choch.get("fvg_gap_pct", 0.0) or 0.0)
        if zone_gap >= self.FVG_CHOCH_MIN_15M_GAP_PCT * 2:
            confidence += 8.0
        if one_min_gap >= self.FVG_CHOCH_MIN_1M_GAP_PCT * 2:
            confidence += 5.0
        confidence = min(confidence, 88.0)

        self._last_fvg_choch_signal = {
            "confidence": confidence,
            "direction": direction,
            "option_type": option_type,
            "zone_id": active_zone["zone_id"],
            "zone_type": active_zone["type"],
            "zone_low": round(float(active_zone["low"]), 4),
            "zone_high": round(float(active_zone["high"]), 4),
            "zone_mid": round(float(active_zone["mid"]), 4),
            "zone_gap_pct": round(zone_gap, 4),
            "choch_level": round(float(choch["structure_level"]), 4),
            "fvg_1m_low": round(float(choch["fvg_low"]), 4),
            "fvg_1m_high": round(float(choch["fvg_high"]), 4),
            "fvg_1m_mid": round(float(choch["fvg_mid"]), 4),
            "fib_618": round(float(choch["fib_618"]), 4),
        }

        self._breakout_direction = direction
        self._breakout_option_type = option_type
        self._breakout_symbol = selected_symbol
        self._breakout_strike = atm_strike
        self._breakout_contracts = contracts
        self._breakout_confidence = confidence / 100.0
        self._breakout_bb_width = self._bb_width_pct
        self._breakout_velocity_pct = abs(self._calc_underlying_mom(60.0))
        self._pending_entry_setup = "FVG_CHOCH"
        self._cached_bot_state = f"fvg_choch:entering:{direction}"
        self._last_fvg_choch_entry_at = now
        self._fvg_choch_zone_cooldowns[str(active_zone["zone_id"])] = (
            now + self.FVG_CHOCH_ZONE_COOLDOWN_SEC
        )
        self._last_fvg_choch_state = {
            "status": "ENTRY",
            "reason": "15m_fvg_1m_choch_retest",
            **self._last_fvg_choch_signal,
        }

        self.logger.info(
            "[%s] FVG_CHOCH_ENTRY: dir=%s zone=%s %.2f-%.2f mid=%.2f "
            "1m_fvg=%.2f-%.2f fib618=%.2f %s $%.0f ask=$%.4f turnover=$%.2fM conf=%.0f",
            self.pair,
            direction,
            active_zone["type"],
            float(active_zone["low"]),
            float(active_zone["high"]),
            float(active_zone["mid"]),
            float(choch["fvg_low"]),
            float(choch["fvg_high"]),
            float(choch["fib_618"]),
            option_type.upper(),
            atm_strike,
            entry_ask,
            turnover_usd / 1_000_000,
            confidence,
        )
        return await self._execute_breakout_entry(entry_ask)

    async def _check_premium_wave_entry(self) -> list[Signal]:
        """Enter when real option premium momentum confirms the HTF direction."""
        if "PREMIUM_WAVE" not in self.ENABLED_SETUPS:
            return []
        now = time.monotonic()
        if now - self._last_premium_wave_entry_at < self.PREMIUM_WAVE_COOLDOWN_SEC:
            return []
        if not self._selected_expiry or not self.options_exchange:
            return []

        now_utc = datetime.now(timezone.utc)
        hours_to_expiry = (self._selected_expiry - now_utc).total_seconds() / 3600
        if hours_to_expiry < self.MIN_EXPIRY_HOURS:
            return []

        ohlcv = self._cached_ohlcv or await self._get_ohlcv_for_squeeze()
        trend_dir, trend_15m, trend_45m = self._htf_trend_direction(ohlcv)
        if trend_dir not in {"UP", "DOWN"}:
            return []

        option_type = "call" if trend_dir == "UP" else "put"
        snapshot = self._premium_wave_snapshot(option_type)
        if not snapshot:
            return []

        premium_5m = float(snapshot.get("premium_5m_pct", 0.0))
        premium_15m = float(snapshot.get("premium_15m_pct", 0.0))
        premium_from_low = float(snapshot.get("premium_from_5m_low_pct", 0.0))
        underlying_5m = float(snapshot.get("underlying_5m_pct", 0.0))
        underlying_15m = float(snapshot.get("underlying_15m_pct", 0.0))
        premium_lifting = (
            premium_5m >= self.PREMIUM_WAVE_MIN_5M_RISE_PCT
            or premium_15m >= self.PREMIUM_WAVE_MIN_15M_RISE_PCT
        )
        underlying_aligned = (
            underlying_5m >= self.PREMIUM_WAVE_MIN_UNDERLYING_5M_PCT
            or underlying_15m >= self.PREMIUM_WAVE_MIN_UNDERLYING_15M_PCT
        )
        if not premium_lifting or not underlying_aligned:
            return []
        if premium_from_low > self.PREMIUM_WAVE_MAX_FROM_5M_LOW_PCT:
            self._cached_bot_state = "blocked:premium_wave_extended"
            self.logger.info(
                "[%s] PREMIUM_WAVE_EXTENSION_SKIP: dir=%s premium is %.1f%% "
                "above recent 5m low (max %.1f%%) -- wait for pullback/re-lift",
                self.pair,
                trend_dir,
                premium_from_low,
                self.PREMIUM_WAVE_MAX_FROM_5M_LOW_PCT,
            )
            return []

        spot = float(self._last_spot_price or 0.0)
        if spot <= 0 and self.futures_exchange:
            try:
                spot_ticker = await self.futures_exchange.fetch_ticker(self.pair)
                spot = float(spot_ticker.get("last") or spot_ticker.get("bid") or 0)
            except Exception:
                spot = 0.0
        if spot <= 0:
            return []
        self._last_spot_price = spot

        atm_strike = self._get_atm_strike(spot)
        if atm_strike is None:
            return []
        self._cached_target_strike = atm_strike

        selected_symbol: str | None = None
        selected_strike: float | None = None
        selected_ticker: dict[str, Any] | None = None
        entry_ask = 0.0
        entry_quality: dict[str, Any] = dict(snapshot)
        max_spread_pct = max(
            self.PREMIUM_WAVE_MAX_SPREAD_PCT,
            self._adaptive_entry_max_spread_pct(
                option_type,
                base_max_spread_pct=self.ENTRY_MAX_SPREAD_PCT,
                fast_move_max_spread_pct=self.PREMIUM_WAVE_MAX_SPREAD_PCT,
            ),
        )

        for strike in self._entry_candidate_strikes(atm_strike, option_type):
            symbol = self._build_option_symbol(strike, option_type, self._selected_expiry)
            if not symbol:
                continue
            try:
                ticker = await self.options_exchange.fetch_ticker(symbol)
                ask = float(ticker.get("ask") or ticker.get("bid") or 0)
                bid = float(ticker.get("bid") or 0)
            except Exception as e:
                self.logger.debug("[%s] PREMIUM_WAVE ticker failed for %s: %s", self.pair, symbol, e)
                continue
            if ask < self.MIN_PREMIUM_USD:
                continue
            contracts = self._calculate_option_contracts(ask, confidence=0.76)
            if contracts < 1:
                continue
            if bid > 0:
                spread_pct = (ask - bid) / ask * 100.0
                if spread_pct > max_spread_pct:
                    self.logger.info(
                        "[%s] PREMIUM_WAVE_SPREAD_SKIP: %s spread=%.1f%% > %.1f%%",
                        self.pair,
                        symbol,
                        spread_pct,
                        max_spread_pct,
                    )
                    continue

            exec_snapshot = self._entry_execution_snapshot(ticker, ask, option_type)
            last_rise_pct = exec_snapshot.get("premium_last_rise_pct")
            cum_rise_pct = exec_snapshot.get("premium_cum_rise_pct")
            if (
                last_rise_pct is not None
                and last_rise_pct > self.PREMIUM_WAVE_MAX_LAST_RISE_PCT
            ):
                self.logger.info(
                    "[%s] PREMIUM_WAVE_CHASE_SKIP: %s last premium candle %.1f%% "
                    "> %.1f%% -- too close to local top",
                    self.pair,
                    symbol,
                    last_rise_pct,
                    self.PREMIUM_WAVE_MAX_LAST_RISE_PCT,
                )
                continue
            if (
                cum_rise_pct is not None
                and cum_rise_pct > self.PREMIUM_WAVE_MAX_CUM_RISE_PCT
            ):
                self.logger.info(
                    "[%s] PREMIUM_WAVE_CHASE_SKIP: %s cumulative premium jump %.1f%% "
                    "> %.1f%% -- wait for pullback",
                    self.pair,
                    symbol,
                    cum_rise_pct,
                    self.PREMIUM_WAVE_MAX_CUM_RISE_PCT,
                )
                continue
            mark_gap_pct = exec_snapshot.get("entry_mark_gap_pct")
            if mark_gap_pct is not None and mark_gap_pct > self.PREMIUM_WAVE_MAX_MARK_GAP_PCT:
                self.logger.info(
                    "[%s] PREMIUM_WAVE_EXEC_SKIP: %s ask too far above mark "
                    "(gap=%.2f%% > %.2f%%)",
                    self.pair,
                    symbol,
                    mark_gap_pct,
                    self.PREMIUM_WAVE_MAX_MARK_GAP_PCT,
                )
                continue

            passes_quality, skip_reason = self._passes_entry_quality(
                ticker,
                min_iv=self.PREMIUM_WAVE_MIN_IV,
                min_delta_abs=self.PREMIUM_WAVE_MIN_DELTA_ABS,
                min_turnover_usd=self.PREMIUM_WAVE_MIN_TURNOVER_USD,
            )
            if not passes_quality:
                self.logger.info(
                    "[%s] PREMIUM_WAVE_QUALITY_SKIP: %s (%s)",
                    self.pair,
                    skip_reason,
                    symbol,
                )
                continue

            selected_symbol = symbol
            selected_strike = strike
            selected_ticker = ticker
            entry_ask = ask
            entry_quality.update(exec_snapshot)
            break

        if not selected_symbol or selected_strike is None or not selected_ticker or entry_ask <= 0:
            self._cached_bot_state = "blocked:premium_wave_quality"
            self.logger.info(
                "[%s] PREMIUM_WAVE_SKIP: dir=%s premium5=%+.1f%% premium15=%+.1f%% "
                "underlying5=%+.2f%% underlying15=%+.2f%% no candidate passed",
                self.pair,
                trend_dir,
                premium_5m,
                premium_15m,
                underlying_5m,
                underlying_15m,
            )
            return []

        confidence = 0.78 if premium_15m >= 30.0 or premium_5m >= 18.0 else 0.72
        contracts = self._calculate_option_contracts(entry_ask, confidence=confidence)
        if contracts < 1:
            return []

        self._breakout_direction = trend_dir
        self._breakout_option_type = option_type
        self._breakout_symbol = selected_symbol
        self._breakout_strike = selected_strike
        self._breakout_contracts = contracts
        self._breakout_confidence = confidence
        self._breakout_bb_width = self._bb_width_pct
        self._breakout_velocity_pct = max(abs(trend_15m), abs(underlying_15m))
        self._pending_entry_setup = "PREMIUM_WAVE"
        self._last_entry_quality = entry_quality
        self._cached_bot_state = f"premium_wave:entering:{trend_dir}"
        self._last_premium_wave_entry_at = now

        self.logger.info(
            "[%s] PREMIUM_WAVE_ENTRY: dir=%s trend15=%+.2f%% trend45=%+.2f%% "
            "premium5=%+.1f%% premium15=%+.1f%% underlying5=%+.2f%% underlying15=%+.2f%% "
            "%s $%.0f ask=$%.4f conf=%.2f",
            self.pair,
            trend_dir,
            trend_15m,
            trend_45m,
            premium_5m,
            premium_15m,
            underlying_5m,
            underlying_15m,
            option_type.upper(),
            selected_strike,
            entry_ask,
            confidence,
        )
        return await self._execute_breakout_entry(entry_ask)

    async def _check_move_pullback_entry(self) -> list[Signal]:
        """Enter after a websocket-detected impulse retraces and re-confirms."""
        state = self._move_pullback_state
        if not state or not state.get("ready"):
            return []

        if "MOVE_PULLBACK" not in self.ENABLED_SETUPS:
            self._move_pullback_state = None
            return []

        age = time.monotonic() - float(state.get("detected_at", time.monotonic()))
        if age > self.MOVE_PULLBACK_MAX_AGE_SEC:
            self._move_pullback_state = None
            return []

        if not self._selected_expiry or not self.options_exchange:
            return []

        now_utc = datetime.now(timezone.utc)
        hours_to_expiry = (self._selected_expiry - now_utc).total_seconds() / 3600
        if hours_to_expiry < self.MIN_EXPIRY_HOURS:
            return []

        direction = str(state.get("direction") or "")
        if direction not in ("UP", "DOWN"):
            self._move_pullback_state = None
            return []

        option_type = "call" if direction == "UP" else "put"
        spot = float(self._last_spot_price or 0)
        if spot <= 0 and self.futures_exchange:
            try:
                ticker = await self.futures_exchange.fetch_ticker(self.pair)
                spot = float(ticker.get("last") or ticker.get("bid") or 0)
            except Exception:
                spot = 0.0
        if spot <= 0:
            return []
        self._last_spot_price = spot

        ohlcv = self._cached_ohlcv or await self._get_ohlcv_for_squeeze()
        if not self._direction_allowed_by_trend(direction, ohlcv, "MOVE_PULLBACK"):
            self._move_pullback_state = None
            return []
        if not self._direction_allowed_by_analyzer(direction, "MOVE_PULLBACK"):
            self._move_pullback_state = None
            return []

        retrace_price = float(state.get("retrace_price") or 0)
        if retrace_price > 0:
            if direction == "UP":
                second_leg_pct = (spot - retrace_price) / retrace_price * 100.0
            else:
                second_leg_pct = (retrace_price - spot) / retrace_price * 100.0
            if second_leg_pct < self.MOVE_PULLBACK_SECOND_LEG_PCT:
                self.logger.info(
                    "[%s] MOVE_PULLBACK_STALE_SKIP: dir=%s second_leg=%+.3f%% < %.3f%% "
                    "(spot=%.2f retrace=%.2f)",
                    self.pair,
                    direction,
                    second_leg_pct,
                    self.MOVE_PULLBACK_SECOND_LEG_PCT,
                    spot,
                    retrace_price,
                )
                return []

        atm_strike = self._get_atm_strike(spot)
        if atm_strike is None:
            return []
        self._cached_target_strike = atm_strike

        strikes_to_try = self._entry_candidate_strikes(atm_strike, option_type)

        selected_symbol: str | None = None
        selected_strike: float | None = None
        selected_ticker: dict[str, Any] | None = None
        entry_ask = 0.0

        for strike in strikes_to_try:
            symbol = self._build_option_symbol(strike, option_type, self._selected_expiry)
            if not symbol:
                continue
            try:
                ticker = await self.options_exchange.fetch_ticker(symbol)
                ask = float(ticker.get("ask") or ticker.get("bid") or 0)
            except Exception as e:
                self.logger.debug("[%s] MOVE_PULLBACK ticker failed for %s: %s", self.pair, symbol, e)
                continue
            if ask < self.MIN_PREMIUM_USD:
                continue
            contracts = self._calculate_option_contracts(ask, confidence=0.75)
            if contracts >= 1:
                selected_symbol = symbol
                selected_strike = strike
                selected_ticker = ticker
                entry_ask = ask
                break

        if not selected_symbol or selected_strike is None or entry_ask <= 0:
            self.logger.info(
                "[%s] MOVE_PULLBACK_SKIP dir=%s: no affordable strike",
                self.pair,
                direction,
            )
            self._move_pullback_state = None
            return []

        bid = 0.0
        max_spread_pct = self._adaptive_entry_max_spread_pct(
            option_type,
            base_max_spread_pct=self.MOVE_PULLBACK_MAX_SPREAD_PCT,
            fast_move_max_spread_pct=self.MOVE_PULLBACK_FAST_MOVE_MAX_SPREAD_PCT,
        )
        try:
            bid = float((selected_ticker or {}).get("bid") or 0)
        except (TypeError, ValueError):
            bid = 0.0
        if bid > 0:
            spread_pct = (entry_ask - bid) / entry_ask * 100.0
            if spread_pct > max_spread_pct:
                self._cached_bot_state = (
                    f"blocked:move_pullback_spread:{spread_pct:.1f}%>{max_spread_pct:.1f}%"
                )
                self.logger.info(
                    "[%s] MOVE_PULLBACK_SPREAD_SKIP: %s spread=%.1f%% > %.1f%%",
                    self.pair,
                    selected_symbol,
                    spread_pct,
                    max_spread_pct,
                )
                return []

        exec_snapshot = self._entry_execution_snapshot(
            selected_ticker,
            entry_ask,
            option_type,
        )
        mark_gap_pct = exec_snapshot.get("entry_mark_gap_pct")
        if mark_gap_pct is not None and mark_gap_pct > self.MOVE_PULLBACK_MAX_MARK_GAP_PCT:
            self._cached_bot_state = (
                f"blocked:move_pullback_mark_gap:{mark_gap_pct:.1f}%>{self.MOVE_PULLBACK_MAX_MARK_GAP_PCT:.1f}%"
            )
            self.logger.info(
                "[%s] MOVE_PULLBACK_EXEC_SKIP: %s ask too far above mark "
                "(gap=%.2f%% > %.2f%%)",
                self.pair,
                selected_symbol,
                mark_gap_pct,
                self.MOVE_PULLBACK_MAX_MARK_GAP_PCT,
            )
            return []

        passes_quality, skip_reason = self._passes_entry_quality(
            selected_ticker,
            min_iv=self.MOVE_PULLBACK_MIN_IV,
            min_delta_abs=(
                self.BTC_SMALL_ACCOUNT_MIN_DELTA_ABS
                if self._is_btc_small_account_mode()
                else None
            ),
        )
        if not passes_quality:
            self._cached_bot_state = "blocked:move_pullback_quality"
            self.logger.info(
                "[%s] ENTRY_QUALITY_SKIP — %s (MOVE_PULLBACK %s)",
                self.pair,
                skip_reason,
                selected_symbol,
            )
            return []

        info = (selected_ticker or {}).get("info") or {}
        try:
            turnover_usd = float(info.get("turnover_usd", 0) or 0)
        except (TypeError, ValueError):
            turnover_usd = 0.0
        turnover_floor = self._setup_turnover_floor(self.MOVE_PULLBACK_MIN_TURNOVER_USD)
        if turnover_usd < turnover_floor:
            self._cached_bot_state = (
                f"blocked:move_pullback_liquidity:{turnover_usd / 1_000_000:.1f}M<{turnover_floor / 1_000_000:.1f}M"
            )
            self.logger.info(
                "[%s] MOVE_PULLBACK_LIQUIDITY_SKIP: %s turnover=$%.2fM < $%.2fM",
                self.pair,
                selected_symbol,
                turnover_usd / 1_000_000,
                turnover_floor / 1_000_000,
            )
            return []

        quality_ok, quality_reason, quality_snapshot = self._score_option_entry(
            selected_ticker,
            entry_ask,
            option_type,
            "MOVE_PULLBACK",
            min_score=self._btc_small_account_score_floor(),
            max_spread_pct=max_spread_pct,
        )
        if not quality_ok:
            self._cached_bot_state = "blocked:move_pullback_quality_score"
            self.logger.info(
                "[%s] MOVE_PULLBACK_QUALITY_SKIP: %s %s edge=%.1f%% cost=%.1f%% score=%.1f",
                self.pair,
                selected_symbol,
                quality_reason,
                quality_snapshot.get("entry_expected_edge_pct", 0.0),
                quality_snapshot.get("entry_cost_floor_pct", 0.0),
                quality_snapshot.get("entry_quality_score", 0.0),
            )
            return []

        try:
            conf_score, _ = self._calculate_confidence(selected_ticker, option_type)
            if conf_score < self.CONFIDENCE_MIN_ENTRY:
                self.logger.info(
                    "[%s] ENTRY_BLOCKED confidence=%.0f below floor %.0f "
                    "(MOVE_PULLBACK %s)",
                    self.pair,
                    conf_score,
                    self.CONFIDENCE_MIN_ENTRY,
                    selected_symbol,
                )
                return []
        except Exception:
            self.logger.debug("[%s] confidence gate failed pre-order (MOVE_PULLBACK)", selected_symbol)

        contracts = self._calculate_option_contracts(entry_ask, confidence=0.75)
        if contracts < 1:
            return []

        self._breakout_direction = direction
        self._breakout_option_type = option_type
        self._breakout_symbol = selected_symbol
        self._breakout_strike = selected_strike
        self._breakout_contracts = contracts
        self._breakout_confidence = 0.75
        self._breakout_bb_width = self._bb_width_pct
        self._breakout_velocity_pct = abs(self._underlying_momentum_pct())
        self._pending_entry_setup = "MOVE_PULLBACK"
        self._last_entry_quality = quality_snapshot
        self._cached_bot_state = f"move_pullback:entering:{direction}"

        self.logger.info(
            "[%s] MOVE_PULLBACK_ENTRY: dir=%s retrace=%.0f%% second_leg=%+.2f%% reconfirm=%+.2f%% "
            "spot=%.2f %s $%.0f ask=$%.4f turnover=$%.2fM quality=%.1f edge=%.1f%% cost=%.1f%%",
            self.pair,
            direction,
            float(state.get("retrace_frac", 0.0)) * 100,
            float(state.get("second_leg_pct", 0.0)),
            float(state.get("reconfirm_pct", 0.0)),
            spot,
            option_type.upper(),
            selected_strike,
            entry_ask,
            turnover_usd / 1_000_000,
            quality_snapshot.get("entry_quality_score", 0.0),
            quality_snapshot.get("entry_expected_edge_pct", 0.0),
            quality_snapshot.get("entry_cost_floor_pct", 0.0),
        )
        self._move_pullback_state = None
        return await self._execute_breakout_entry(entry_ask)

    async def _check_trend_flow_entry(self) -> list[Signal]:
        """Enter on sustained 5m/15m directional flow without waiting for pullback."""
        if "TREND_FLOW" not in self.ENABLED_SETUPS:
            return []
        now = time.monotonic()
        if now - self._last_trend_flow_entry_at < self.TREND_FLOW_COOLDOWN_SEC:
            return []
        if not self._selected_expiry or not self.options_exchange:
            return []

        ohlcv = await self._get_ohlcv_for_squeeze()
        if not ohlcv or len(ohlcv) < 20:
            return []

        try:
            close_now = float(ohlcv[-1][4])
            close_5m_ago = float(ohlcv[-6][4])
            close_15m_ago = float(ohlcv[-16][4])
        except (TypeError, ValueError, IndexError):
            return []
        if close_now <= 0 or close_5m_ago <= 0 or close_15m_ago <= 0:
            return []

        move_5m = (close_now - close_5m_ago) / close_5m_ago * 100.0
        move_15m = (close_now - close_15m_ago) / close_15m_ago * 100.0
        direction: str | None = None
        if move_15m <= -self.TREND_FLOW_15M_PCT and move_5m <= -self.TREND_FLOW_5M_PCT:
            direction = "DOWN"
        elif move_15m >= self.TREND_FLOW_15M_PCT and move_5m >= self.TREND_FLOW_5M_PCT:
            direction = "UP"
        if not direction:
            return []
        trend_dir, trend_15m, trend_45m = self._htf_trend_direction(ohlcv)
        if not self._direction_allowed_by_trend(direction, ohlcv, "TREND_FLOW"):
            return []
        trend_aligned = trend_dir == direction
        option_type = "call" if direction == "UP" else "put"
        direction_sign = 1.0 if direction == "UP" else -1.0
        aligned_60s = direction_sign * self._calc_underlying_mom(60.0)
        aligned_20s = direction_sign * self._calc_underlying_mom(20.0)
        accel = self._underlying_acceleration_ratio()
        freshness_failed = (
            aligned_60s < self.TREND_FLOW_MIN_ALIGNED_60S_PCT
            or aligned_20s < self.TREND_FLOW_MIN_ALIGNED_20S_PCT
            or accel < self.TREND_FLOW_MIN_ACCEL_RATIO
        )
        reversing_now = (
            aligned_60s < -self.TREND_FLOW_TREND_REVERSE_TOLERANCE_PCT
            or aligned_20s < -self.TREND_FLOW_TREND_REVERSE_TOLERANCE_PCT
        )
        if freshness_failed and (not trend_aligned or reversing_now):
            self.logger.info(
                "[%s] TREND_FLOW_FRESHNESS_SKIP: dir=%s 60s=%+.2f%%/%.2f%% "
                "20s=%+.2f%%/%.2f%% accel=%.2f/%.2f trend=%s 15m=%+.2f%% 45m=%+.2f%%",
                self.pair,
                direction,
                aligned_60s,
                self.TREND_FLOW_MIN_ALIGNED_60S_PCT,
                aligned_20s,
                self.TREND_FLOW_MIN_ALIGNED_20S_PCT,
                accel,
                self.TREND_FLOW_MIN_ACCEL_RATIO,
                trend_dir or "NONE",
                trend_15m,
                trend_45m,
            )
            return []
        if freshness_failed and trend_aligned:
            self.logger.info(
                "[%s] TREND_FLOW_TREND_CONTINUATION: dir=%s accepted despite "
                "micro freshness 60s=%+.2f%% 20s=%+.2f%% accel=%.2f "
                "(trend 15m=%+.2f%% 45m=%+.2f%%)",
                self.pair,
                direction,
                aligned_60s,
                aligned_20s,
                accel,
                trend_15m,
                trend_45m,
            )
        extended = (
            abs(move_15m) > self.TREND_FLOW_MAX_15M_PCT
            or abs(move_5m) > self.TREND_FLOW_MAX_5M_PCT
        )
        if extended and (
            aligned_60s < self.TREND_FLOW_CONTINUATION_60S_PCT
            or aligned_20s < self.TREND_FLOW_CONTINUATION_20S_PCT
        ) and (not trend_aligned or reversing_now):
            self.logger.info(
                "[%s] TREND_FLOW_EXTENDED_SKIP: dir=%s 15m=%+.2f%%/%.2f%% "
                "5m=%+.2f%%/%.2f%% continuation 60s=%+.2f%%/%.2f%% "
                "20s=%+.2f%%/%.2f%% trend=%s",
                self.pair,
                direction,
                move_15m,
                self.TREND_FLOW_MAX_15M_PCT,
                move_5m,
                self.TREND_FLOW_MAX_5M_PCT,
                aligned_60s,
                self.TREND_FLOW_CONTINUATION_60S_PCT,
                aligned_20s,
                self.TREND_FLOW_CONTINUATION_20S_PCT,
                trend_dir or "NONE",
            )
            return []
        if extended:
            self.logger.info(
                "[%s] TREND_FLOW_CONTINUATION_OK: dir=%s extended 15m=%+.2f%% "
                "5m=%+.2f%% but fresh 60s=%+.2f%% 20s=%+.2f%%",
                self.pair,
                direction,
                move_15m,
                move_5m,
                aligned_60s,
                aligned_20s,
            )

        now_utc = datetime.now(timezone.utc)
        hours_to_expiry = (self._selected_expiry - now_utc).total_seconds() / 3600
        if hours_to_expiry < self.MIN_EXPIRY_HOURS:
            return []

        spot = float(self._last_spot_price or close_now)
        if spot <= 0:
            return []
        self._last_spot_price = spot

        atm_strike = self._get_atm_strike(spot)
        if atm_strike is None:
            return []
        self._cached_target_strike = atm_strike

        candidate_strikes = self._entry_candidate_strikes(atm_strike, option_type)

        selected_symbol: str | None = None
        selected_strike: float | None = None
        ticker: dict[str, Any] | None = None
        entry_ask = 0.0
        best_quality: dict[str, Any] | None = None
        best_score = -1.0

        for strike in candidate_strikes:
            symbol = self._build_option_symbol(strike, option_type, self._selected_expiry)
            if not symbol:
                continue
            try:
                candidate_ticker = await self.options_exchange.fetch_ticker(symbol)
                candidate_ask = float(candidate_ticker.get("ask") or candidate_ticker.get("bid") or 0)
            except Exception as e:
                self.logger.debug("[%s] TREND_FLOW ticker failed for %s: %s", self.pair, symbol, e)
                continue
            if candidate_ask < self.MIN_PREMIUM_USD:
                continue

            max_spread_pct = self._adaptive_entry_max_spread_pct(
                option_type,
                base_max_spread_pct=self.TREND_FLOW_MAX_SPREAD_PCT,
                fast_move_max_spread_pct=self.TREND_FLOW_FAST_MOVE_MAX_SPREAD_PCT,
            )
            quality_ok, _quality_reason, quality_snapshot = self._score_option_entry(
                candidate_ticker,
                candidate_ask,
                option_type,
                "TREND_FLOW",
                min_score=self._btc_small_account_score_floor(),
                min_expected_edge_pct=10.0 if extended else None,
                max_spread_pct=max_spread_pct,
                trend_edge_pct=(
                    abs(move_15m) * 12.0 + abs(move_5m) * 8.0
                    if trend_aligned
                    else None
                ),
            )
            candidate_score = float(quality_snapshot.get("entry_quality_score", 0.0))
            if quality_ok and candidate_score > best_score:
                selected_symbol = symbol
                selected_strike = strike
                ticker = candidate_ticker
                entry_ask = candidate_ask
                best_quality = quality_snapshot
                best_score = candidate_score

        if not selected_symbol or selected_strike is None or not ticker or entry_ask <= 0:
            self._cached_bot_state = "blocked:trend_flow_quality"
            self.logger.info(
                "[%s] TREND_FLOW_QUALITY_SKIP: no candidate passed option-quality gate "
                "(dir=%s candidates=%s)",
                self.pair,
                direction,
                ",".join(str(int(s)) for s in candidate_strikes),
            )
            return []

        bid = 0.0
        max_spread_pct = self._adaptive_entry_max_spread_pct(
            option_type,
            base_max_spread_pct=self.TREND_FLOW_MAX_SPREAD_PCT,
            fast_move_max_spread_pct=self.TREND_FLOW_FAST_MOVE_MAX_SPREAD_PCT,
        )
        try:
            bid = float(ticker.get("bid") or 0)
        except (TypeError, ValueError):
            bid = 0.0
        if bid > 0:
            spread_pct = (entry_ask - bid) / entry_ask * 100.0
            if spread_pct > max_spread_pct:
                self._cached_bot_state = (
                    f"blocked:trend_flow_spread:{spread_pct:.1f}%>{max_spread_pct:.1f}%"
                )
                self.logger.info(
                    "[%s] TREND_FLOW_SPREAD_SKIP: %s spread=%.1f%% > %.1f%%",
                    self.pair,
                    selected_symbol,
                    spread_pct,
                    max_spread_pct,
                )
                return []

        exec_snapshot = self._entry_execution_snapshot(ticker, entry_ask, option_type)
        mark_gap_pct = exec_snapshot.get("entry_mark_gap_pct")
        if mark_gap_pct is not None and mark_gap_pct > self.TREND_FLOW_MAX_MARK_GAP_PCT:
            self._cached_bot_state = (
                f"blocked:trend_flow_mark_gap:{mark_gap_pct:.1f}%>{self.TREND_FLOW_MAX_MARK_GAP_PCT:.1f}%"
            )
            self.logger.info(
                "[%s] TREND_FLOW_EXEC_SKIP: %s ask too far above mark "
                "(gap=%.2f%% > %.2f%%)",
                self.pair,
                selected_symbol,
                mark_gap_pct,
                self.TREND_FLOW_MAX_MARK_GAP_PCT,
            )
            return []

        passes_quality, skip_reason = self._passes_entry_quality(
            ticker,
            min_iv=self.TREND_FLOW_MIN_IV,
            min_delta_abs=(
                self.BTC_SMALL_ACCOUNT_MIN_DELTA_ABS
                if self._is_btc_small_account_mode()
                else None
            ),
        )
        if not passes_quality:
            self._cached_bot_state = "blocked:trend_flow_quality"
            self.logger.info(
                "[%s] ENTRY_QUALITY_SKIP — %s (TREND_FLOW %s)",
                self.pair,
                skip_reason,
                selected_symbol,
            )
            return []

        info = ticker.get("info") or {}
        try:
            turnover_usd = float(info.get("turnover_usd", 0) or 0)
        except (TypeError, ValueError):
            turnover_usd = 0.0
        turnover_floor = self._setup_turnover_floor(self.TREND_FLOW_MIN_TURNOVER_USD)
        if turnover_usd < turnover_floor:
            self._cached_bot_state = (
                f"blocked:trend_flow_liquidity:{turnover_usd / 1_000_000:.1f}M<{turnover_floor / 1_000_000:.1f}M"
            )
            self.logger.info(
                "[%s] TREND_FLOW_LIQUIDITY_SKIP: %s turnover=$%.2fM < $%.2fM",
                self.pair,
                selected_symbol,
                turnover_usd / 1_000_000,
                turnover_floor / 1_000_000,
            )
            return []

        contracts = self._calculate_option_contracts(entry_ask, confidence=0.72)
        if contracts < 1:
            return []

        self._breakout_direction = direction
        self._breakout_option_type = option_type
        self._breakout_symbol = selected_symbol
        self._breakout_strike = selected_strike
        self._breakout_contracts = contracts
        self._breakout_confidence = 0.72
        self._breakout_bb_width = self._bb_width_pct
        self._breakout_velocity_pct = abs(move_15m)
        self._pending_entry_setup = "TREND_FLOW"
        self._last_entry_quality = best_quality
        self._cached_bot_state = f"trend_flow:entering:{direction}"
        self._last_trend_flow_entry_at = now

        self.logger.info(
            "[%s] TREND_FLOW_ENTRY: dir=%s 15m=%+.2f%% 5m=%+.2f%% spot=%.2f "
            "%s $%.0f ask=$%.4f turnover=$%.2fM quality=%.1f edge=%.1f%% cost=%.1f%%",
            self.pair,
            direction,
            move_15m,
            move_5m,
            spot,
            option_type.upper(),
            selected_strike,
            entry_ask,
            turnover_usd / 1_000_000,
            (best_quality or {}).get("entry_quality_score", 0.0),
            (best_quality or {}).get("entry_expected_edge_pct", 0.0),
            (best_quality or {}).get("entry_cost_floor_pct", 0.0),
        )
        return await self._execute_breakout_entry(entry_ask)

    async def _check_momentum_burst_entry(self) -> list[Signal]:
        """Immediate entry when 60s momentum and ATM premium trend align (outside squeeze)."""
        momentum_60s = self._underlying_momentum_pct()
        if abs(momentum_60s) < self.MOMENTUM_BURST_THRESHOLD_PCT:
            return []

        # Don't fire momentum burst during active squeeze — let squeeze handle breakout
        if self._squeeze_status == "ACTIVE":
            return []

        # Freshness gate: require the last 20s to contain >= 50% of the net
        # 60s move. Filters stale tail-end moves (where premium is already
        # priced and edge is gone) without forcing a bigger absolute move.
        accel = self._underlying_acceleration_ratio()
        if accel > 0 and accel < 0.70:
            if self._tick_count % 10 == 0:
                self.logger.info(
                    "[%s] MB_STALE: 60s_mom=%+.2f%% but only %.0f%% in last 20s "
                    "(need >=50%%) — move is fading, skipping",
                    self.pair, momentum_60s, accel * 100,
                )
            return []

        # GPFC #52: continuation check — the recent 20s half of the move must
        # go the SAME direction as the net 60s. Catches the "move already over"
        # case where spot popped then reversed in the last 20s.
        mom_20s = self._underlying_short_momentum_pct(20.0)
        if abs(mom_20s) < self.MOMENTUM_BURST_THRESHOLD_PCT:
            if self._tick_count % 10 == 0:
                self.logger.info(
                    "[%s] MB_WEAK_RECENT: 20s=%+.2f%% below %.2f%% — skipping stale tail",
                    self.pair,
                    mom_20s,
                    self.MOMENTUM_BURST_THRESHOLD_PCT,
                )
            return []
        same_dir = (
            (momentum_60s > 0 and mom_20s > 0)
            or (momentum_60s < 0 and mom_20s < 0)
        )
        if not same_dir:
            if self._tick_count % 10 == 0:
                self.logger.info(
                    "[%s] MB_DIRECTION_MISMATCH: 60s=%+.2f%% vs 20s=%+.2f%% "
                    "— recent half reversed, skipping",
                    self.pair, momentum_60s, mom_20s,
                )
            return []

        if not self._selected_expiry or not self.options_exchange:
            return []

        now_utc = datetime.now(timezone.utc)
        hours_to_expiry = (self._selected_expiry - now_utc).total_seconds() / 3600
        if hours_to_expiry < self.MIN_EXPIRY_HOURS:
            return []

        spot = self._last_spot_price
        if spot <= 0 and self.futures_exchange:
            try:
                ticker = await self.futures_exchange.fetch_ticker(self.pair)
                spot = float(ticker.get("last") or ticker.get("bid") or 0)
            except Exception:
                spot = 0.0
        if spot <= 0:
            return []
        self._last_spot_price = spot

        atm_strike = self._get_atm_strike(spot)
        if atm_strike is None:
            return []
        self._cached_target_strike = atm_strike

        # Require BOTH a strict rise AND a meaningful cumulative climb across the
        # 3 ticks (default ≥5%) so micro-jitters in illiquid options don't qualify.
        min_rise = self.MOMENTUM_BURST_MIN_ASK_RISE_PCT / 100.0
        if (
            momentum_60s >= self.MOMENTUM_BURST_THRESHOLD_PCT
            and self._prev2_call_ask > 0
            and self._prev_call_ask > 0
            and self._atm_call_ask > self._prev_call_ask > self._prev2_call_ask
            and (self._atm_call_ask - self._prev2_call_ask) / self._prev2_call_ask >= min_rise
        ):
            option_type = "call"
            direction = "UP"
            entry_ask = self._atm_call_ask
            prev_ask = self._prev_call_ask
        elif (
            momentum_60s <= -self.MOMENTUM_BURST_THRESHOLD_PCT
            and self._prev2_put_ask > 0
            and self._prev_put_ask > 0
            and self._atm_put_ask > self._prev_put_ask > self._prev2_put_ask
            and (self._atm_put_ask - self._prev2_put_ask) / self._prev2_put_ask >= min_rise
        ):
            option_type = "put"
            direction = "DOWN"
            entry_ask = self._atm_put_ask
            prev_ask = self._prev_put_ask
        else:
            return []

        ohlcv = self._cached_ohlcv or await self._get_ohlcv_for_squeeze()
        if not self._direction_allowed_by_trend(direction, ohlcv, "MOM_BURST"):
            return []

        # ═════════════════════════════════════════════════════════════════════
        # GPFC #42: REGIME GATE — reject counter-trend MB entries.
        #
        # User observation: "If it's trending up, it'll take calls and once
        # call is done, it sees a momentum put it again enters." The 60s
        # momentum flips on every minor pullback, so without a higher-timeframe
        # filter MB was flip-flopping call→put→call against the prevailing
        # 5-minute trend. This gate blocks counter-regime entries while still
        # allowing MB to scalp when the 5-min trend is sideways (|pct| < thr).
        #
        # Threshold 0.10% over 5min ≈ same price-per-time conviction as the
        # 60s MB threshold (0.15%/60s ≈ 0.12%/5min) but slightly looser to
        # avoid blocking legitimate momentum at the start of a fresh trend.
        # ═════════════════════════════════════════════════════════════════════
        regime_threshold = 0.10
        ohlcv = self._cached_ohlcv
        if ohlcv and len(ohlcv) >= 6:
            try:
                close_now = float(ohlcv[-1][4])
                close_5m_ago = float(ohlcv[-6][4])
                if close_5m_ago > 0:
                    regime_pct = (close_now - close_5m_ago) / close_5m_ago * 100
                    counter_call = (
                        option_type == "call" and regime_pct <= -regime_threshold
                    )
                    counter_put = (
                        option_type == "put" and regime_pct >= regime_threshold
                    )
                    if counter_call or counter_put:
                        if self._tick_count % 5 == 0:
                            self.logger.info(
                                "[%s] MB_REGIME_REJECT: 5min=%+.2f%% vs wanted %s "
                                "(60s=%+.2f%%) — counter-trend, skipping",
                                self.pair, regime_pct, option_type.upper(),
                                momentum_60s,
                            )
                        return []
                    # Log successful alignment at INFO so we can audit post-deploy.
                    self.logger.info(
                        "[%s] MB_REGIME_OK: 5min=%+.2f%% aligned with %s (60s=%+.2f%%)",
                        self.pair, regime_pct, option_type.upper(), momentum_60s,
                    )
            except (ValueError, TypeError, IndexError):
                pass

        selected_symbol = self._build_option_symbol(atm_strike, option_type, self._selected_expiry)
        if not selected_symbol:
            return []
        if entry_ask < self.MIN_PREMIUM_USD:
            return []

        # GPFC #52: Spread guard — wide spread = guaranteed instant -4% entry.
        # Fetch live bid/ask and skip if (ask - bid) / ask > 8%.
        spread_ticker: dict[str, Any] | None = None
        try:
            spread_ticker = await self.options_exchange.fetch_ticker(selected_symbol)
            _bid = float(spread_ticker.get("bid") or 0)
            _ask = float(spread_ticker.get("ask") or 0)
            if _ask > 0 and _bid > 0:
                spread_pct = (_ask - _bid) / _ask
                if spread_pct > self.ENTRY_MAX_SPREAD_PCT / 100.0:
                    if self._tick_count % 5 == 0:
                        self.logger.info(
                            "[%s] MB_SPREAD_WIDE: %s bid=$%.4f ask=$%.4f "
                            "spread=%.1f%% > %.1f%% - skipping",
                            self.pair, selected_symbol, _bid, _ask,
                            spread_pct * 100, self.ENTRY_MAX_SPREAD_PCT,
                        )
                    return []
        except Exception:
            # If spread fetch fails, fall through; don't penalize for tick glitches.
            pass

        exec_snapshot = self._entry_execution_snapshot(
            spread_ticker,
            entry_ask,
            option_type,
        )
        mark_gap_pct = exec_snapshot.get("entry_mark_gap_pct")
        if mark_gap_pct is not None and mark_gap_pct > self.ENTRY_MAX_MARK_GAP_PCT:
            self.logger.info(
                "[%s] MB_EXEC_SKIP: %s ask too far above mark "
                "(gap=%.2f%% > %.2f%%) - skipping",
                self.pair, selected_symbol, mark_gap_pct, self.ENTRY_MAX_MARK_GAP_PCT,
            )
            return []

        last_rise_pct = exec_snapshot.get("premium_last_rise_pct")
        cum_rise_pct = exec_snapshot.get("premium_cum_rise_pct")
        if (
            last_rise_pct is not None
            and last_rise_pct > self.MOM_BURST_MAX_LAST_ASK_RISE_PCT
        ) or (
            cum_rise_pct is not None
            and cum_rise_pct > self.MOM_BURST_MAX_CUM_ASK_RISE_PCT
        ):
            self.logger.info(
                "[%s] MOM_BURST_CHASE_SKIP: %s premium path %.2f->%.2f->%.2f "
                "last=%.2f%%/%.2f%% cum=%.2f%%/%.2f%% - skipping",
                self.pair,
                selected_symbol,
                (self._prev2_call_ask if option_type == "call" else self._prev2_put_ask),
                prev_ask,
                entry_ask,
                last_rise_pct or 0.0,
                self.MOM_BURST_MAX_LAST_ASK_RISE_PCT,
                cum_rise_pct or 0.0,
                self.MOM_BURST_MAX_CUM_ASK_RISE_PCT,
            )
            return []

        # GPFC #67: entry-quality filter (turnover/delta/IV) reusing spread_ticker.
        passes_quality, skip_reason = self._passes_entry_quality(spread_ticker)
        if not passes_quality:
            if self._tick_count % 5 == 0:
                self.logger.info(
                    "[%s] ENTRY_QUALITY_SKIP — %s (MOM_BURST %s)",
                    self.pair, skip_reason, selected_symbol,
                )
            return []

        info = (spread_ticker or {}).get("info") or {}
        try:
            turnover_usd = float(info.get("turnover_usd", 0) or 0)
        except (TypeError, ValueError):
            turnover_usd = 0.0
        if turnover_usd < self.MOM_BURST_MIN_TURNOVER_USD:
            self.logger.info(
                "[%s] MOM_BURST_LIQUIDITY_SKIP: %s turnover=$%.2fM < $%.2fM "
                "- skipping thin book",
                self.pair,
                selected_symbol,
                turnover_usd / 1_000_000,
                self.MOM_BURST_MIN_TURNOVER_USD / 1_000_000,
            )
            return []

        # GPFC #82: IV-regime gate — MOM_BURST needs at least some vol.
        # If IV is below floor, this is a SQUEEZE regime; let SQUEEZE handle it.
        _iv_mb = self._extract_iv(spread_ticker)
        if _iv_mb is not None and _iv_mb < self.MOM_BURST_MIN_IV_FOR_ENTRY:
            if self._tick_count % 5 == 0:
                self.logger.info(
                    "[%s] MOM_BURST blocked — IV %.3f < %.3f, SQUEEZE regime (%s)",
                    self.pair, _iv_mb, self.MOM_BURST_MIN_IV_FOR_ENTRY, selected_symbol,
                )
            return []

        # GPFC #72: confidence gate (≥ 60). Sub-60 zone was a death zone
        # in live data — block before order placement.
        quality_ok, quality_reason, quality_snapshot = self._score_option_entry(
            spread_ticker,
            entry_ask,
            option_type,
            "MOM_BURST",
            min_expected_edge_pct=10.0,
        )
        if not quality_ok:
            self.logger.info(
                "[%s] MOM_BURST_QUALITY_SKIP: %s %s edge=%.1f%% cost=%.1f%% score=%.1f",
                self.pair,
                selected_symbol,
                quality_reason,
                quality_snapshot.get("entry_expected_edge_pct", 0.0),
                quality_snapshot.get("entry_cost_floor_pct", 0.0),
                quality_snapshot.get("entry_quality_score", 0.0),
            )
            return []

        try:
            conf_score, _ = self._calculate_confidence(spread_ticker, option_type)
            if conf_score < self.CONFIDENCE_MIN_ENTRY:
                self.logger.info(
                    "[%s] ENTRY_BLOCKED confidence=%.0f below floor %.0f "
                    "(MOM_BURST %s)",
                    self.pair, conf_score, self.CONFIDENCE_MIN_ENTRY, selected_symbol,
                )
                return []
        except Exception:
            self.logger.debug(
                "[%s] confidence gate failed pre-order (MB), proceeding",
                selected_symbol,
            )

        opt_contracts = self._calculate_option_contracts(entry_ask, confidence=0.7)
        if opt_contracts < 1:
            return []

        # GPFC #69: stop-the-bleed — BB must be only mildly wider than KC for
        # MOM_BURST entries (real compression preceding the move). Live data:
        # bb_kc > 1.5 = 0/4 winners on MB entries, combined -$0.55.
        bb_w = self._bb_width_pct or 0.0
        kc_w = self._last_kc_width_pct or 0.0
        if kc_w > 0 and (bb_w / kc_w) > 1.5:
            self.logger.info(
                "[%s] MOM_BURST_SKIP — bb_kc %.2f > 1.5 (BB %.3f%% / KC %.3f%%)",
                self.pair, bb_w / kc_w, bb_w, kc_w,
            )
            return []

        self.logger.info(
            "[%s] MOMENTUM_BURST: dir=%s mom=%+.2f%% premium=$%.2f→$%.2f→$%.2f — entering %s",
            self.pair,
            direction,
            momentum_60s,
            (self._prev2_call_ask if option_type == "call" else self._prev2_put_ask),
            prev_ask,
            entry_ask,
            option_type.upper(),
        )

        self._breakout_direction = direction
        self._breakout_option_type = option_type
        self._breakout_symbol = selected_symbol
        self._breakout_strike = atm_strike
        self._breakout_contracts = opt_contracts
        self._breakout_confidence = 0.7
        self._breakout_bb_width = self._bb_width_pct
        self._pending_entry_setup = "MOM_BURST"
        self._last_entry_quality = quality_snapshot
        return await self._execute_breakout_entry(entry_ask)

    async def _handle_squeeze_breakout(
        self,
        bb_upper: float,
        bb_lower: float,
        kc_upper: float,
        kc_lower: float,
        bb_width_pct: float,
        avg_vol_ratio: float,
    ) -> None:
        """Called when squeeze ends — determine breakout direction, calc velocity, start dynamic confirmation (GPFC #21)."""
        # GPFC #82: ENABLED_SETUPS check kept as a kill-switch. IV-regime
        # gating (SQUEEZE only fires below SQUEEZE_MAX_IV_FOR_ENTRY) is
        # enforced later, right after the entry-quality filter.
        if "SQUEEZE" not in self.ENABLED_SETUPS:
            if self._tick_count % 30 == 0:
                self.logger.info(
                    "[%s] SQUEEZE entry blocked by config (ENABLED_SETUPS)",
                    self.pair,
                )
            return

        # Determine direction from which band exited KC
        if bb_upper > kc_upper and bb_lower < kc_lower:
            # Both bands outside — pick the side with larger exceedance
            up_excess = bb_upper - kc_upper
            dn_excess = kc_lower - bb_lower
            direction = "UP" if up_excess >= dn_excess else "DOWN"
        elif bb_upper > kc_upper:
            direction = "UP"
        elif bb_lower < kc_lower:
            direction = "DOWN"
        else:
            # Squeeze ended but no clear KC exit yet — skip
            return

        # GPFC #65: block obviously-broken-out squeezes. bb_kc_ratio > 2.0
        # means BB has already expanded to twice the KC width — the move has
        # happened and entering now is post-breakout chasing, not compression.
        kc_mid = (kc_upper + kc_lower) / 2.0 if (kc_upper + kc_lower) else 0.0
        kc_width_pct = ((kc_upper - kc_lower) / kc_mid * 100) if kc_mid > 0 else 0.0
        bb_kc_ratio = bb_width_pct / kc_width_pct if kc_width_pct > 0 else 99.0
        if bb_kc_ratio > 2.0:
            self.logger.info(
                "[%s] SQUEEZE_SKIP — bb_kc_ratio %.2f > 2.0 "
                "(BB width %.3f%% / KC width %.3f%%) — already broken out",
                self.pair, bb_kc_ratio, bb_width_pct, kc_width_pct,
            )
            return

        option_type = "call" if direction == "UP" else "put"

        # ═════════════════════════════════════════════════════════════════════
        # GPFC #70: REGIME GATE on SQUEEZE entries — mirrors GPFC #42 MB logic.
        # Block counter-trend squeeze breakouts where the 5min trend is opposed
        # to the BB-out-of-KC direction. Uses 0.10% / 5min threshold (same as
        # MB regime gate) so a sideways 5min ribbon still allows entries.
        # ═════════════════════════════════════════════════════════════════════
        regime_threshold = 0.10
        ohlcv = self._cached_ohlcv
        if ohlcv and len(ohlcv) >= 6:
            try:
                close_now = float(ohlcv[-1][4])
                close_5m_ago = float(ohlcv[-6][4])
                if close_5m_ago > 0:
                    regime_pct = (close_now - close_5m_ago) / close_5m_ago * 100
                    counter_call = (
                        option_type == "call" and regime_pct <= -regime_threshold
                    )
                    counter_put = (
                        option_type == "put" and regime_pct >= regime_threshold
                    )
                    if counter_call or counter_put:
                        self.logger.info(
                            "[%s] SQUEEZE_SKIP_REGIME — %s blocked, 5m=%+.2f%% "
                            "vs wanted %s (counter-trend)",
                            self.pair, option_type.upper(), regime_pct,
                            direction,
                        )
                        return
                    self.logger.info(
                        "[%s] SQUEEZE_REGIME_OK: 5m=%+.2f%% aligned with %s",
                        self.pair, regime_pct, direction,
                    )
            except (ValueError, TypeError, IndexError):
                pass

        ohlcv = self._cached_ohlcv or await self._get_ohlcv_for_squeeze()
        if not self._direction_allowed_by_trend(direction, ohlcv, "SQUEEZE"):
            return

        # Need current price and exchange data to select strike
        current_price = 0.0
        try:
            price_ticker = await self.futures_exchange.fetch_ticker(self.pair)
            current_price = float(price_ticker.get("last", 0) or 0)
            self._last_spot_price = current_price
        except Exception as e:
            self.logger.debug("[%s] Price fetch for breakout failed: %s", self.pair, e)
            return

        if current_price <= 0:
            return

        # GPFC #21: Calculate breakout velocity from last 3 candles
        velocity_pct = await self._calculate_breakout_velocity()
        self._breakout_velocity_pct = velocity_pct

        # GPFC #21: Set dynamic confirmation window based on velocity
        confirmation_secs = self._get_confirmation_secs(velocity_pct)
        self._breakout_confirmation_secs = confirmation_secs
        self._breakout_spot_price = current_price

        if self._selected_expiry is None:
            return
        hours_to_expiry = (
            self._selected_expiry - datetime.now(timezone.utc)
        ).total_seconds() / 3600
        if hours_to_expiry < self.MIN_EXPIRY_HOURS:
            return

        atm_strike = self._get_atm_strike(current_price)
        if atm_strike is None:
            return
        self._cached_target_strike = atm_strike

        strikes_to_try = self._entry_candidate_strikes(atm_strike, option_type)

        selected_strike: float | None = None
        selected_symbol: str | None = None
        selected_ticker: dict[str, Any] | None = None
        current_ask: float = 0.0

        for strike in strikes_to_try:
            sym = self._build_option_symbol(strike, option_type, self._selected_expiry)
            if sym is None:
                continue
            try:
                ticker = await self.options_exchange.fetch_ticker(sym)
                # GPFC #47: never fall back to `last` — Delta leaks spot there.
                ask = float(ticker.get("ask") or ticker.get("bid") or 0)
            except Exception as e:
                self.logger.debug(
                    "[%s] Ticker fetch failed for %s: %s", self.pair, sym, e
                )
                continue
            if ask < self.MIN_PREMIUM_USD:
                continue
            n = self._calculate_option_contracts(ask, confidence=0.7)
            if n >= 1:
                selected_strike = strike
                selected_symbol = sym
                selected_ticker = ticker
                current_ask = ask
                break

        if selected_strike is None or selected_symbol is None:
            self.logger.info(
                "[%s] SQUEEZE_BREAKOUT dir=%s: no affordable strike — skip",
                self.pair,
                direction,
            )
            return

        # GPFC #67: entry-quality filter on the chosen strike's ticker.
        passes_quality, skip_reason = self._passes_entry_quality(
            selected_ticker,
            min_iv=self.SQUEEZE_MIN_IV,
            min_delta_abs=(
                self.BTC_SMALL_ACCOUNT_MIN_DELTA_ABS
                if self._is_btc_small_account_mode()
                else None
            ),
        )
        if not passes_quality:
            self.logger.info(
                "[%s] ENTRY_QUALITY_SKIP — %s (SQUEEZE %s)",
                self.pair, skip_reason, selected_symbol,
            )
            return

        # GPFC #82: IV-regime gate — SQUEEZE only fires when vol is low.
        # High IV means the breakout is likely already priced in; let MOM_BURST
        # handle that regime instead.
        if self.SQUEEZE_REQUIRES_LOW_VOL:
            _iv_sq = self._extract_iv(selected_ticker)
            if _iv_sq is not None and _iv_sq > self.SQUEEZE_MAX_IV_FOR_ENTRY:
                self.logger.info(
                    "[%s] SQUEEZE blocked — IV %.3f > %.3f, MOM_BURST regime (%s)",
                    self.pair, _iv_sq, self.SQUEEZE_MAX_IV_FOR_ENTRY, selected_symbol,
                )
                return

        # GPFC #72: confidence gate (≥ 60). Sub-60 zone was a death zone
        # in live data — block before setting up the breakout-pending state
        # (which would otherwise fire an order in _execute_breakout_entry).
        try:
            conf_score, _ = self._calculate_confidence(selected_ticker, option_type)
            if conf_score < self.CONFIDENCE_MIN_ENTRY:
                self.logger.info(
                    "[%s] ENTRY_BLOCKED confidence=%.0f below floor %.0f "
                    "(SQUEEZE %s)",
                    self.pair, conf_score, self.CONFIDENCE_MIN_ENTRY, selected_symbol,
                )
                return
        except Exception:
            self.logger.debug(
                "[%s] confidence gate failed pre-order (SQUEEZE), proceeding",
                selected_symbol,
            )

        # Build confidence using squeeze tightness + premium history at breakout
        now_mono = time.monotonic()
        self._premium_history.append((now_mono, current_ask))
        cutoff = now_mono - self.SQUEEZE_HISTORY_MIN * 60
        while self._premium_history and self._premium_history[0][0] < cutoff:
            self._premium_history.popleft()

        hist_asks = [a for _, a in self._premium_history]
        lowest_ask = min(hist_asks) if hist_asks else current_ask
        highest_ask = max(hist_asks) if hist_asks else current_ask
        self._premium_current_ask = current_ask
        cheap_threshold = (
            lowest_ask + (highest_ask - lowest_ask) * self.SQUEEZE_CHEAP_PERCENTILE
            if highest_ask > lowest_ask
            else current_ask
        )
        self._premium_cheap_threshold = cheap_threshold

        entry_confidence = self._compute_squeeze_confidence(
            bb_width_pct,
            current_ask,
            lowest_ask,
            highest_ask,
            avg_vol_ratio,
        )
        if self._base_asset == "BTC":
            entry_confidence *= 0.7

        if entry_confidence < 0.6:
            self.logger.info(
                "[%s] BREAKOUT_DETECTED dir=%s: confidence=%.2f < 0.6 — skip",
                self.pair,
                direction,
                entry_confidence,
            )
            return

        opt_contracts = self._calculate_option_contracts(current_ask, entry_confidence)
        if opt_contracts < 1:
            self.logger.info(
                "[%s] BREAKOUT_DETECTED dir=%s: 0 contracts affordable — skip",
                self.pair,
                direction,
            )
            return

        # Store breakout state — do NOT enter yet (GPFC #21)
        self._breakout_pending = True
        self._breakout_direction = direction
        self._breakout_time = time.monotonic()
        self._breakout_entry_ask = current_ask
        self._breakout_symbol = selected_symbol
        self._breakout_strike = selected_strike
        self._breakout_option_type = option_type
        self._breakout_contracts = opt_contracts
        self._breakout_confidence = entry_confidence
        self._breakout_bb_width = bb_width_pct
        self._pending_entry_setup = "SQUEEZE"
        self._breakout_state = "DETECTED"

        # GPFC #21: Log BREAKOUT_DETECTED with velocity and confirmation window
        self.logger.info(
            "[%s] BREAKOUT_DETECTED: dir=%s velocity=%.2f%% confirmation=%ds — %s $%.0f ask=$%.4f conf=%.2f",
            self.pair,
            direction,
            velocity_pct * 100,
            confirmation_secs,
            option_type.upper(),
            selected_strike,
            current_ask,
            entry_confidence,
        )
        await self._log_activity(
            "options_skip",
            f"{self.pair} — BREAKOUT_DETECTED: dir={direction} velocity={velocity_pct * 100:.2f}% confirmation={confirmation_secs}s",
            {
                "direction": direction,
                "ask": current_ask,
                "strike": selected_strike,
                "confidence": round(entry_confidence, 3),
                "velocity_pct": round(velocity_pct * 100, 2),
                "confirmation_secs": confirmation_secs,
            },
        )
        self._cached_bot_state = f"breakout:confirming:{direction}:{confirmation_secs}s"

    async def _check_breakout_confirmation(self) -> list[Signal]:
        """Check dynamic confirmation window. Enter if premium rising; abort on fakeout (GPFC #24)."""
        if not self._breakout_pending or self._breakout_time is None:
            self._reset_breakout_state()
            return []

        elapsed = time.monotonic() - self._breakout_time

        # Fetch current ask for the selected symbol
        current_ask = 0.0
        try:
            ticker = await self.options_exchange.fetch_ticker(self._breakout_symbol)
            # GPFC #47: never fall back to `last` — Delta leaks spot there.
            current_ask = float(ticker.get("ask") or ticker.get("bid") or 0)
        except Exception as e:
            self.logger.debug("[%s] Confirmation tick fetch failed: %s", self.pair, e)
            remaining = max(0, self._breakout_confirmation_secs - int(elapsed))
            self._cached_bot_state = (
                f"breakout:confirming:{self._breakout_direction}:{remaining}s"
            )
            self._breakout_state = "DETECTED"
            return []

        if current_ask <= 0:
            remaining = max(0, self._breakout_confirmation_secs - int(elapsed))
            self._cached_bot_state = (
                f"breakout:confirming:{self._breakout_direction}:{remaining}s"
            )
            self._breakout_state = "DETECTED"
            return []

        self._premium_current_ask = current_ask

        # GPFC #24: During confirmation window, abort early if premium drops significantly
        drop_pct = (
            (self._breakout_entry_ask - current_ask) / self._breakout_entry_ask * 100
        )
        if drop_pct > self.BREAKOUT_FAKEOUT_DROP_PCT:
            self.logger.info(
                "[%s] BREAKOUT_FAKEOUT: dir=%s premium dropped %.1f%% during confirmation (ask=$%.4f < entry_ask=$%.4f) — abort",
                self.pair,
                self._breakout_direction,
                drop_pct,
                current_ask,
                self._breakout_entry_ask,
            )
            await self._log_activity(
                "options_skip",
                f"{self.pair} — BREAKOUT_FAKEOUT: dir={self._breakout_direction} "
                f"premium dropped {drop_pct:.1f}% during confirmation — aborting",
                {
                    "direction": self._breakout_direction,
                    "ask": current_ask,
                    "entry_ask": self._breakout_entry_ask,
                    "drop_pct": round(drop_pct, 2),
                    "elapsed": round(elapsed, 1),
                },
            )
            self._last_action = "BREAKOUT_FAKEOUT"
            self._last_action_at = time.time()
            self._breakout_state = "FAKEOUT"
            self._reset_breakout_state()
            return []

        # OVERPRICED: premium rose > 15% from breakout ask — don't chase pumped premium
        rise_pct = (
            (current_ask - self._breakout_entry_ask) / self._breakout_entry_ask * 100
        )
        if rise_pct > self.BREAKOUT_OVERPRICED_RISE_PCT:
            self.logger.info(
                "[%s] BREAKOUT_OVERPRICED: dir=%s premium rose %.1f%% (ask=$%.4f > entry_ask=$%.4f * 1.15) — abort, don't chase",
                self.pair,
                self._breakout_direction,
                rise_pct,
                current_ask,
                self._breakout_entry_ask,
            )
            await self._log_activity(
                "options_skip",
                f"{self.pair} — BREAKOUT_OVERPRICED: dir={self._breakout_direction} "
                f"premium rose {rise_pct:.1f}% — aborting, don't chase",
                {
                    "direction": self._breakout_direction,
                    "ask": current_ask,
                    "entry_ask": self._breakout_entry_ask,
                    "rise_pct": round(rise_pct, 2),
                    "elapsed": round(elapsed, 1),
                },
            )
            self._last_action = "BREAKOUT_OVERPRICED"
            self._last_action_at = time.time()
            self._breakout_state = "OVERPRICED"
            self._reset_breakout_state()
            return []

        # Still in window — wait
        if elapsed < self._breakout_confirmation_secs:
            remaining = self._breakout_confirmation_secs - int(elapsed)
            if self._tick_count % 6 == 0:
                self.logger.info(
                    "[%s] BREAKOUT_CONFIRM_WAIT: dir=%s ask=$%.4f vs entry=$%.4f (%.0fs/%ds)",
                    self.pair,
                    self._breakout_direction,
                    current_ask,
                    self._breakout_entry_ask,
                    elapsed,
                    self._breakout_confirmation_secs,
                )
            self._cached_bot_state = (
                f"breakout:confirming:{self._breakout_direction}:{remaining}s"
            )
            self._breakout_state = "DETECTED"
            return []

        change_pct = (
            (current_ask - self._breakout_entry_ask) / self._breakout_entry_ask * 100
        )

        # Premium rising — CONFIRMED, enter now
        self._direction_bias = self._breakout_option_type.upper()
        self._breakout_state = "CONFIRMED"
        self.logger.info(
            "[%s] BREAKOUT_CONFIRMED: dir=%s premium $%.4f → $%.4f (%.1f%%) — entering now",
            self.pair,
            self._breakout_direction,
            self._breakout_entry_ask,
            current_ask,
            change_pct,
        )
        await self._log_activity(
            "options_skip",
            f"{self.pair} — BREAKOUT_CONFIRMED: dir={self._breakout_direction} "
            f"premium ${self._breakout_entry_ask:.4f} → ${current_ask:.4f} ({change_pct:+.1f}%)",
            {
                "direction": self._breakout_direction,
                "ask": current_ask,
                "entry_ask": self._breakout_entry_ask,
                "change_pct": round(change_pct, 2),
                "velocity_pct": round(self._breakout_velocity_pct, 3),
            },
        )
        return await self._execute_breakout_entry(current_ask)

    def _reset_breakout_state(self) -> None:
        """Clear all breakout confirmation state."""
        self._breakout_pending = False
        self._breakout_direction = None
        self._breakout_time = None
        self._breakout_entry_ask = 0.0
        self._breakout_symbol = None
        self._breakout_strike = None
        self._breakout_option_type = None
        self._breakout_contracts = 0
        self._breakout_confidence = 0.0
        self._breakout_bb_width = 0.0
        self._breakout_velocity_pct = 0.0
        self._breakout_confirmation_secs = 60
        self._breakout_spot_price = 0.0
        self._pending_entry_setup = "SQUEEZE"
        self._pending_entry_path_override = None
        self._direction_bias = "NEUTRAL"
        # Note: _breakout_state is preserved until next detection for dashboard visibility

    async def _execute_breakout_entry(self, confirmed_ask: float) -> list[Signal]:
        """Place limit order after breakout is confirmed. Mirrors original fill/poll logic."""
        option_type = self._breakout_option_type or "call"
        selected_symbol = self._breakout_symbol
        selected_strike = self._breakout_strike
        opt_contracts = self._breakout_contracts
        entry_confidence = self._breakout_confidence
        bb_width_pct = self._breakout_bb_width
        if self._pending_entry_setup in self.ENABLED_SETUPS:
            setup_type = self._pending_entry_setup
        elif self._is_squeeze_entry:
            setup_type = "SQUEEZE"
        else:
            setup_type = "MOM_BURST"

        # GPFC #81: belt-and-suspenders — refuse to fire if the resolved
        # setup_type is disabled (e.g. SQUEEZE). _handle_squeeze_breakout
        # already short-circuits, but a stale pending state could still
        # route through here.
        if setup_type not in self.ENABLED_SETUPS:
            self.logger.info(
                "[%s] setup %s disabled by ENABLED_SETUPS — aborting entry",
                self.pair, setup_type,
            )
            self._reset_breakout_state()
            return []

        limit_price = confirmed_ask
        if setup_type in self.FAST_ENTRY_SETUPS:
            limit_price = round(
                confirmed_ask * (1.0 + self.FAST_ENTRY_LIMIT_CROSS_PCT / 100.0),
                4,
            )

        # Recalculate contracts at the actual order cap price.
        opt_contracts = self._calculate_option_contracts(
            limit_price, entry_confidence
        )
        if opt_contracts < 1:
            self.logger.info(
                "[%s] BREAKOUT_CONFIRMED: no affordable contracts at $%.4f — abort",
                self.pair,
                limit_price,
            )
            self._reset_breakout_state()
            return []

        # Get current price for logging/metadata
        current_price = self._last_spot_price
        atm_strike = self._cached_target_strike or selected_strike
        order_spot_price = float(current_price or 0.0)

        exchange_capital = self.risk_manager.get_exchange_capital(self._exchange_id)
        allocation_pct = self.CAPITAL_PER_TRADE_MIN_PCT + (
            entry_confidence
            * (self.CAPITAL_PER_TRADE_MAX_PCT - self.CAPITAL_PER_TRADE_MIN_PCT)
        )
        collateral_usd = exchange_capital * allocation_pct

        self.logger.info(
            "[%s] BREAKOUT_ENTRY: %s $%.0f | BB_width=%.3f%% dir=%s | "
            "ask=$%.4f | conf=%.2f → %d contracts ($%.2f collateral, %.1f%% of $%.2f)",
            self.pair,
            option_type.upper(),
            selected_strike,
            bb_width_pct,
            self._breakout_direction,
            limit_price,
            entry_confidence,
            opt_contracts,
            collateral_usd,
            allocation_pct * 100,
            exchange_capital,
        )

        # GPFC #74: build metadata BEFORE placing the order so the gate is
        # pre-execution. A confidence failure aborts the entry cleanly.
        _pre_ticker: dict[str, Any] | None = None
        try:
            _pre_ticker = await self.options_exchange.fetch_ticker(selected_symbol)
            self._last_option_ticker = _pre_ticker  # GPFC #74 FIX: cache for on_fill_fallback
        except Exception as _te:
            self.logger.debug(
                "[%s] pre-entry ticker fetch failed: %s", self.pair, _te
            )
        try:
            _regime = await self._classify_regime()
        except Exception:
            _regime = "UNKNOWN"
        _entry_path = {
            "SQUEEZE": "squeeze_confirmed",
            "MOVE_PULLBACK": "move_pullback",
            "TREND_FLOW": "trend_flow",
            "FVG_CHOCH": "fvg_choch",
            "PREMIUM_WAVE": "premium_wave",
        }.get(setup_type, "mom_burst")
        if self._pending_entry_path_override:
            _entry_path = self._pending_entry_path_override
        try:
            self._pending_entry_signals = self._build_entry_metadata(
                _pre_ticker, option_type, confirmed_ask,
                entry_path=_entry_path, regime=_regime,
            )
        except Exception as _me:
            self.logger.warning(
                "[%s] %s entry SKIPPED — metadata build failed: %s",
                self.pair, setup_type, _me,
            )
            self._reset_breakout_state()
            return []

        # GPFC #79: confidence gate at the EXECUTION layer — the detection-time
        # gate at _check_breakout_confirmation can pass on stale conditions by
        # the time we actually fire. Re-evaluate freshly-built metadata here so
        # no order goes through with conf < CONFIDENCE_MIN_ENTRY.
        _exec_conf = (self._pending_entry_signals or {}).get("confidence")
        if setup_type == "PREMIUM_WAVE":
            _exec_conf = max(float(_exec_conf or 0.0), entry_confidence * 100.0)
            if self._pending_entry_signals is not None:
                self._pending_entry_signals["confidence"] = round(_exec_conf, 1)
        if _exec_conf is None or _exec_conf < self.CONFIDENCE_MIN_ENTRY:
            self.logger.warning(
                "[%s] ENTRY_BLOCKED conf=%s below floor %.0f (path=execute_breakout_entry, setup=%s)",
                self.pair, _exec_conf, self.CONFIDENCE_MIN_ENTRY, setup_type,
            )
            self._pending_entry_signals = None
            self._reset_breakout_state()
            return []

        preflight_signal = Signal(
            side="buy",
            price=limit_price,
            amount=float(opt_contracts),
            order_type="market",
            reason=f"preflight {setup_type} {option_type.upper()} {selected_symbol}",
            strategy=self.name,
            pair=selected_symbol,
            leverage=self.OPTIONS_LEVERAGE,
            position_type="long",
            exchange_id="delta",
            metadata={
                "setup_type": setup_type,
                "option_type": option_type,
                "contracts": opt_contracts,
                "preflight": True,
            },
        )
        if not self.risk_manager.approve_signal(preflight_signal):
            self.logger.info(
                "[%s] %s entry blocked by risk preflight before order placement",
                self.pair,
                setup_type,
            )
            self._pending_entry_signals = None
            self._reset_breakout_state()
            return []

        self._cached_bot_state = "breakout:placing_order"
        limit_order_id: str | None = None
        try:
            limit_order = await self.options_exchange.create_order(
                symbol=selected_symbol,
                type="limit",
                side="buy",
                amount=float(opt_contracts),
                price=limit_price,
            )
            limit_order_id = limit_order.get("id")
            self.logger.info(
                "[%s] BREAKOUT: limit order %s placed — %d contracts @ $%.4f",
                self.pair,
                limit_order_id,
                opt_contracts,
                limit_price,
            )
        except Exception as e:
            self.logger.info(
                "[%s] BREAKOUT: order placement failed: %s — SKIP", self.pair, e
            )
            self._reset_breakout_state()
            return []

        # GPFC #96: trend/momentum entries are perishable. A TREND_FLOW limit
        # that fills a minute later is no longer the same trade; it is a stale
        # option quote after the move has already changed. SQUEEZE can wait for
        # a planned limit fill, but fast setups must fill immediately or cancel.
        limit_filled = False
        fill_price = limit_price
        _filled_qty = 0.0
        stale_fill = False

        def _fast_entry_spot_against_pct() -> float:
            if setup_type not in self.FAST_ENTRY_SETUPS or order_spot_price <= 0:
                return 0.0
            live_spot = float(self._last_spot_price or order_spot_price)
            if self._breakout_direction == "DOWN":
                return (live_spot - order_spot_price) / order_spot_price * 100.0
            return (order_spot_price - live_spot) / order_spot_price * 100.0

        if setup_type in self.FAST_ENTRY_SETUPS:
            fill_wait_sec = self.FAST_ENTRY_FILL_WAIT_SEC
            fill_poll_sec = self.FAST_ENTRY_FILL_POLL_SEC
        else:
            fill_wait_sec = self.SQUEEZE_FILL_WAIT_SEC
            fill_poll_sec = self.SQUEEZE_FILL_POLL_SEC
        polls = max(1, int(fill_wait_sec // fill_poll_sec))

        for _poll in range(polls):
            await asyncio.sleep(fill_poll_sec)
            if setup_type in self.FAST_ENTRY_SETUPS and order_spot_price > 0:
                live_spot = float(self._last_spot_price or order_spot_price)
                if self._breakout_direction == "DOWN":
                    spot_against_pct = (live_spot - order_spot_price) / order_spot_price * 100.0
                else:
                    spot_against_pct = (order_spot_price - live_spot) / order_spot_price * 100.0
                if spot_against_pct > self.FAST_ENTRY_MAX_SPOT_AGAINST_PCT:
                    self.logger.info(
                        "[%s] %s_STALE_LIMIT_CANCEL: spot moved against before fill "
                        "(%+.3f%% > %.3f%%) order_spot=%.2f live=%.2f",
                        self.pair,
                        setup_type,
                        spot_against_pct,
                        self.FAST_ENTRY_MAX_SPOT_AGAINST_PCT,
                        order_spot_price,
                        live_spot,
                    )
                    break
            try:
                updated = await self.options_exchange.fetch_order(
                    limit_order_id, selected_symbol
                )
                status = updated.get("status", "")
                _filled_qty = float(updated.get("filled", 0) or 0)
                if status == "closed" or _filled_qty >= opt_contracts:
                    fill_price = float(
                        updated.get("average", 0)
                        or updated.get("price", 0)
                        or limit_price
                    )
                    limit_filled = True
                    if setup_type in self.FAST_ENTRY_SETUPS and order_spot_price > 0:
                        live_spot = float(self._last_spot_price or order_spot_price)
                        if self._breakout_direction == "DOWN":
                            spot_against_pct = (live_spot - order_spot_price) / order_spot_price * 100.0
                        else:
                            spot_against_pct = (order_spot_price - live_spot) / order_spot_price * 100.0
                        if spot_against_pct > self.FAST_ENTRY_MAX_SPOT_AGAINST_PCT:
                            stale_fill = True
                            self.logger.warning(
                                "[%s] %s_STALE_FILL: filled after spot moved against "
                                "(%+.3f%% > %.3f%%) order_spot=%.2f live=%.2f",
                                self.pair,
                                setup_type,
                                spot_against_pct,
                                self.FAST_ENTRY_MAX_SPOT_AGAINST_PCT,
                                order_spot_price,
                                live_spot,
                            )
                    self.logger.info(
                        "[%s] BREAKOUT: FILLED @ $%.4f (%d contracts) — poll %d/%d",
                        self.pair,
                        fill_price,
                        opt_contracts,
                        _poll + 1,
                        polls,
                    )
                    break
                elif _filled_qty > 0:
                    self.logger.debug(
                        "[%s] BREAKOUT: partial fill %.1f/%d — poll %d/%d",
                        self.pair,
                        _filled_qty,
                        opt_contracts,
                        _poll + 1,
                        polls,
                    )
            except Exception as e:
                self.logger.debug("[%s] BREAKOUT: poll failed: %s", self.pair, e)

        if not limit_filled and _filled_qty > 0:
            # Partial fill — keep it, cancel residual
            try:
                await self.options_exchange.cancel_order(
                    limit_order_id, selected_symbol
                )
            except Exception:
                pass
            opt_contracts = max(1, int(_filled_qty))
            fill_price = limit_price
            limit_filled = True
            self.logger.info(
                "[%s] BREAKOUT: PARTIAL FILL — %d contracts @ ~$%.4f",
                self.pair,
                opt_contracts,
                fill_price,
            )

        if not limit_filled:
            # No fill — cancel and move on
            try:
                await self.options_exchange.cancel_order(
                    limit_order_id, selected_symbol
                )
            except Exception as _ce:
                try:
                    _fc = await self.options_exchange.fetch_order(
                        limit_order_id, selected_symbol
                    )
                    if (
                        _fc.get("status") == "closed"
                        or float(_fc.get("filled", 0) or 0) >= opt_contracts
                    ):
                        fill_price = float(
                            _fc.get("average", 0) or _fc.get("price", 0) or limit_price
                        )
                        spot_against_pct = _fast_entry_spot_against_pct()
                        if spot_against_pct > self.FAST_ENTRY_MAX_SPOT_AGAINST_PCT:
                            stale_fill = True
                            self.logger.warning(
                                "[%s] %s_STALE_FILL_AFTER_CANCEL: exchange filled while canceling "
                                "(%+.3f%% > %.3f%%)",
                                self.pair,
                                setup_type,
                                spot_against_pct,
                                self.FAST_ENTRY_MAX_SPOT_AGAINST_PCT,
                            )
                        limit_filled = True
                except Exception:
                    pass
                if not limit_filled:
                    self.logger.info(
                        "[%s] BREAKOUT: cancel failed: %s — SKIP",
                        self.pair,
                        _ce,
                    )
                    self._reset_breakout_state()
                    return []

        if not limit_filled:
            self.logger.info(
                "[%s] BREAKOUT_NO_FILL: ask=$%.4f cancelled",
                self.pair,
                limit_price,
            )
            await self._log_skip(
                f"{self.pair} — BREAKOUT_NO_FILL: ask=${limit_price:.4f}",
                {"ask": limit_price, "direction": self._breakout_direction},
            )
            self._last_action = "BREAKOUT_NO_FILL"
            self._last_action_at = time.time()
            self._reset_breakout_state()
            return []

        if stale_fill and self._pending_entry_signals is not None:
            self._pending_entry_signals["stale_fill"] = True

        # Re-fetch for Delta's actual fill price
        try:
            final = await self.options_exchange.fetch_order(
                limit_order_id, selected_symbol
            )
            actual_avg = float(
                final.get("average") or final.get("price") or limit_price
            )
            if actual_avg > 0:
                fill_price = actual_avg
        except Exception:
            pass

        premium = fill_price
        self._limit_entry_filled = True
        self._last_action = {
            "SQUEEZE": "SQUEEZE_FILL",
            "MOVE_PULLBACK": "MOVE_PULLBACK_FILL",
            "TREND_FLOW": "TREND_FLOW_FILL",
            "FVG_CHOCH": "FVG_CHOCH_FILL",
        }.get(setup_type, "MOMENTUM_BURST_FILL")
        self._last_action_at = time.time()

        self.logger.info(
            "[%s] BREAKOUT_FILL: dir=%s premium=$%.4f",
            self.pair,
            self._breakout_direction,
            premium,
        )

        # SET POSITION STATE
        self._position_premium_history.clear()
        self._last_30s_premium = None
        # GPFC #71: reset the ratcheted trail floor for the new position.
        self._locked_trail_floor_pct = 0.0
        self._last_trail_floor_pct_written = -1.0
        self._trailing_active = False
        self._peak_trail_pending_ticks = 0
        self._sl_defer_count = 0  # GPFC #80: reset on entry
        self._phase_trail_defer_count = 0
        self.in_position = True
        self._reentry_watch = None
        self._position_setup_type = setup_type
        OptionsScalpStrategy._global_in_position = True
        OptionsScalpStrategy._global_position_asset = self._base_asset
        self.entry_premium = fill_price
        self._contracts = opt_contracts
        self.option_symbol = selected_symbol
        self.option_side = option_type
        self.entry_time = time.monotonic()
        self._position_opened_at = datetime.now(timezone.utc).isoformat()
        self.highest_premium = fill_price
        self._last_known_premium = fill_price
        self.strike_price = selected_strike
        # GPFC #52: snapshot spot + 60s momentum at fill (drives dynamic exits).
        self._spot_at_entry = float(self._last_spot_price or 0)
        self._entry_underlying_move = abs(self._underlying_momentum_pct())
        self._peak_timestamp = self.entry_time
        self._prev_highest_premium = fill_price
        self._is_squeeze_entry = setup_type == "SQUEEZE"
        self._squeeze_breakout_time = (
            time.monotonic() if self._is_squeeze_entry else None
        )
        if self._selected_expiry:
            self.expiry_dt = self._selected_expiry

        if setup_type == "SQUEEZE":
            self.logger.info(
                "[%s] POSITION LOCKED — %s x%d @ $%.4f (breakout confirmed)",
                self.pair,
                option_type.upper(),
                opt_contracts,
                fill_price,
            )
            self._entry_context = (
                f"BB_SQUEEZE dir={self._breakout_direction} BB_width={bb_width_pct:.3f}% "
                f"ask=${premium:.4f} conf={entry_confidence:.2f}"
            )
        elif setup_type == "MOVE_PULLBACK":
            self.logger.info(
                "[%s] POSITION LOCKED — %s x%d @ $%.4f (move pullback entry)",
                self.pair,
                option_type.upper(),
                opt_contracts,
                fill_price,
            )
            self._entry_context = (
                f"MOVE_PULLBACK dir={self._breakout_direction} mom={self._underlying_momentum_pct():+.2f}% "
                f"ask=${premium:.4f} conf={entry_confidence:.2f}"
            )
        elif setup_type == "TREND_FLOW":
            self.logger.info(
                "[%s] POSITION LOCKED â€” %s x%d @ $%.4f (trend flow entry)",
                self.pair,
                option_type.upper(),
                opt_contracts,
                fill_price,
            )
            self._entry_context = (
                f"TREND_FLOW dir={self._breakout_direction} flow={self._breakout_velocity_pct:.2f}% "
                f"ask=${premium:.4f} conf={entry_confidence:.2f}"
            )
        elif setup_type == "FVG_CHOCH":
            fvg = self._last_fvg_choch_signal or {}
            self.logger.info(
                "[%s] POSITION LOCKED — %s x%d @ $%.4f (FVG CHoCH entry)",
                self.pair,
                option_type.upper(),
                opt_contracts,
                fill_price,
            )
            self._entry_context = (
                f"FVG_CHOCH dir={self._breakout_direction} "
                f"zone_mid={fvg.get('zone_mid')} fvg_mid={fvg.get('fvg_1m_mid')} "
                f"ask=${premium:.4f} conf={float(fvg.get('confidence') or entry_confidence):.2f}"
            )
        else:
            self.logger.info(
                "[%s] POSITION LOCKED — %s x%d @ $%.4f (momentum burst entry)",
                self.pair,
                option_type.upper(),
                opt_contracts,
                fill_price,
            )
            self._entry_context = (
                f"MOMENTUM_BURST dir={self._breakout_direction} mom={self._underlying_momentum_pct():+.2f}% "
                f"ask=${premium:.4f} conf={entry_confidence:.2f}"
            )

        # GPFC #74: metadata was already built before order placement and stored in
        # _pending_entry_signals. Patch sl_price now that we have the real fill price
        # (confirmed_ask was used as the proxy; actual fill may differ slightly).
        if self._pending_entry_signals and fill_price > 0:
            _sl_pct = float(self._pending_entry_signals.get("sl_pct", -self.SL_PREMIUM_LOSS_PCT))
            self._pending_entry_signals["sl_price"] = round(
                fill_price * (1.0 + _sl_pct / 100.0), 4
            )

        # Write DB row NOW — synchronously — so the 60s reconciler sweep
        # can't see an exchange position without a matching DB row and
        # register it as an "ORPHAN POSITION / discovered_by_reconcile".
        # This is the fix for BB_SQUEEZE "zero peak" entries: without it,
        # the reconciler was inserting the trade with a stale mark-price
        # snapshot and the strategy's fire-and-forget insert (in on_fill)
        # was silently lost to the race.
        self._db_trade_id = None
        self._pending_entry_setup = setup_type
        try:
            await self._write_entry_to_db(
                fill_price,
                opt_contracts,
                {"id": limit_order_id} if limit_order_id else {},
                None,
                option_symbol=selected_symbol,
                option_side=option_type,
                strike_price=selected_strike,
                base_asset=self._base_asset,
            )
        except Exception:
            self.logger.exception(
                "[%s] BREAKOUT: signal-path DB write failed — reconciler may backfill",
                self.pair,
            )

        expiry_str = self._selected_expiry.strftime("%b %d %H:%M")
        strike_label = "ATM" if selected_strike == atm_strike else "OTM"

        await self._log_activity(
            "options_entry",
            f"{self.pair} — OPTIONS: {option_type.upper()} {strike_label} ${selected_strike:.0f} | "
            f"premium=${premium:.4f} | expiry={expiry_str} | {setup_type} dir={self._breakout_direction}",
            {
                "option_type": option_type,
                "strike": selected_strike,
                "premium": premium,
                "strike_label": strike_label,
                "expiry": self._selected_expiry.isoformat()
                if self._selected_expiry
                else "",
                "underlying_price": current_price,
                "symbol": selected_symbol,
                "setup_type": setup_type,
                "contracts": opt_contracts,
                "bb_width_pct": round(bb_width_pct, 4),
                "confidence": round(entry_confidence, 3),
                "breakout_direction": self._breakout_direction,
            },
        )

        breakout_dir = self._breakout_direction
        self._reset_breakout_state()

        return self._build_entry_signal(
            option_type=option_type,
            selected_symbol=selected_symbol,
            selected_strike=selected_strike,
            premium=premium,
            strength=0,
            signals_str=f"{setup_type} dir={breakout_dir} width={bb_width_pct:.3f}%",
            current_price=current_price,
            setup_type=setup_type,
            expiry_str=expiry_str,
            strike_label=strike_label,
            contracts=opt_contracts,
            confidence=entry_confidence,
            direction=breakout_dir,
        )

    def _build_entry_signal(
        self,
        option_type: str,
        selected_symbol: str,
        selected_strike: float,
        premium: float,
        strength: int,
        signals_str: str,
        current_price: float,
        setup_type: str,
        expiry_str: str,
        strike_label: str,
        contracts: int = 1,
        confidence: float = 0.7,
        direction: str | None = None,
    ) -> list[Signal]:
        """Build the entry Signal for an option trade."""
        self._contracts = contracts
        already_filled = getattr(self, "_limit_entry_filled", False)
        self._limit_entry_filled = False

        # Calculate sizing info for alert
        exchange_capital = self.risk_manager.get_exchange_capital(self._exchange_id)
        allocation_pct = self.CAPITAL_PER_TRADE_MIN_PCT + (
            confidence
            * (self.CAPITAL_PER_TRADE_MAX_PCT - self.CAPITAL_PER_TRADE_MIN_PCT)
        )
        collateral_usd = exchange_capital * allocation_pct

        reason = (
            f"OPTIONS {option_type.upper()} | BB_SQUEEZE "
            f"({signals_str or 'squeeze_detected'}) | "
            f"{strike_label} Strike=${selected_strike:.0f} "
            f"Exp={expiry_str} "
            f"Premium=${premium:.4f} x{contracts} | "
            f"Sizing: {contracts} contracts (${collateral_usd:.2f}, {allocation_pct:.1%} of capital)"
        )
        self.logger.info(
            "[%s] OPTIONS ENTRY — %s (setup=%s)", self.pair, reason, setup_type
        )

        return [
            Signal(
                side="buy",
                price=premium,
                amount=float(contracts),
                order_type="market",
                reason=reason,
                strategy=self.name,
                pair=selected_symbol,
                leverage=self.OPTIONS_LEVERAGE,
                position_type="long",
                exchange_id="delta",
                metadata={
                    "pending_side": option_type,
                    "pending_amount": float(contracts),
                    "option_type": option_type,
                    "direction": direction,
                    "breakout_direction": direction,
                    "strike": selected_strike,
                    "strike_label": strike_label,
                    "expiry": self._selected_expiry.isoformat()
                    if self._selected_expiry
                    else "",
                    "underlying_price": current_price,
                    "underlying_pair": self.pair,
                    "sl_price": premium * (1 - self.SL_PREMIUM_LOSS_PCT / 100),
                    "setup_type": setup_type,
                    "contracts": contracts,
                    "already_filled": already_filled,
                    "entry_context": self._entry_context,
                    "signals_fired": self._entry_context,
                    "spot_price": self._last_spot_price,
                },
            )
        ]

    async def _start_paper_futures_shadow(
        self,
        *,
        option_trade_id: int | None,
        option_symbol: str,
        setup_type: str,
        direction: str | None,
        entry_spot: float,
    ) -> None:
        """Start a paper futures twin for the filled options signal."""
        if (
            not self.PAPER_FUTURES_ENABLED
            or not self._db
            or not self._db.is_connected
            or self._paper_futures_id
            or entry_spot <= 0
        ):
            return
        fut_direction = "long" if direction == "UP" else "short"
        margin = self.PAPER_FUTURES_ACCOUNT_USD * self.PAPER_FUTURES_ALLOC_PCT
        notional = margin * self.PAPER_FUTURES_LEVERAGE
        now_iso = datetime.now(timezone.utc).isoformat()
        row = {
            "option_trade_id": option_trade_id,
            "option_symbol": option_symbol,
            "pair": self.pair,
            "base_asset": self._base_asset,
            "setup_type": setup_type,
            "direction": fut_direction,
            "status": "open",
            "entry_price": round(entry_spot, 8),
            "current_price": round(entry_spot, 8),
            "paper_account_usd": self.PAPER_FUTURES_ACCOUNT_USD,
            "margin_usd": round(margin, 8),
            "notional_usd": round(notional, 8),
            "leverage": self.PAPER_FUTURES_LEVERAGE,
            "opened_at": now_iso,
            "updated_at": now_iso,
            "metadata": {
                "source": "options_signal_shadow",
                "option_side": self.option_side,
                "contracts": self._contracts,
                "entry_premium": self.entry_premium,
            },
        }
        paper_id = await self._db.log_paper_futures_trade(row)
        if paper_id:
            self._paper_futures_id = paper_id
            self._paper_futures_entry_spot = entry_spot
            self._paper_futures_peak_pct = 0.0
            self._paper_futures_direction = fut_direction
            self.logger.info(
                "[%s] PAPER_FUTURES_OPEN id=%s %s $%.2f margin %.1fx entry=%.2f setup=%s",
                self.pair,
                paper_id,
                fut_direction.upper(),
                margin,
                self.PAPER_FUTURES_LEVERAGE,
                entry_spot,
                setup_type,
            )

    async def _update_paper_futures_shadow(self, spot_price: float) -> None:
        """Mark the paper futures twin to current spot while the option is open."""
        if (
            not self._paper_futures_id
            or not self._db
            or not self._db.is_connected
            or self._paper_futures_entry_spot <= 0
            or spot_price <= 0
        ):
            return
        direction_mult = 1.0 if self._paper_futures_direction == "long" else -1.0
        spot_move_pct = (
            (spot_price - self._paper_futures_entry_spot)
            / self._paper_futures_entry_spot
            * 100.0
            * direction_mult
        )
        pnl_pct = spot_move_pct * self.PAPER_FUTURES_LEVERAGE
        self._paper_futures_peak_pct = max(self._paper_futures_peak_pct, pnl_pct)
        margin = self.PAPER_FUTURES_ACCOUNT_USD * self.PAPER_FUTURES_ALLOC_PCT
        pnl_usd = margin * pnl_pct / 100.0
        await self._db.update_paper_futures_trade(
            self._paper_futures_id,
            {
                "current_price": round(spot_price, 8),
                "pnl_pct": round(pnl_pct, 4),
                "pnl_usd": round(pnl_usd, 8),
                "peak_pnl_pct": round(self._paper_futures_peak_pct, 4),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    async def _close_paper_futures_shadow(
        self,
        *,
        exit_spot: float,
        exit_reason: str,
    ) -> None:
        """Close the paper futures twin when the real option closes."""
        if (
            not self._paper_futures_id
            or not self._db
            or not self._db.is_connected
            or self._paper_futures_entry_spot <= 0
        ):
            self._paper_futures_id = None
            self._paper_futures_entry_spot = 0.0
            self._paper_futures_peak_pct = 0.0
            self._paper_futures_direction = None
            return
        if exit_spot <= 0:
            exit_spot = self._last_spot_price or self._paper_futures_entry_spot
        direction_mult = 1.0 if self._paper_futures_direction == "long" else -1.0
        spot_move_pct = (
            (exit_spot - self._paper_futures_entry_spot)
            / self._paper_futures_entry_spot
            * 100.0
            * direction_mult
        )
        pnl_pct = spot_move_pct * self.PAPER_FUTURES_LEVERAGE
        margin = self.PAPER_FUTURES_ACCOUNT_USD * self.PAPER_FUTURES_ALLOC_PCT
        notional = margin * self.PAPER_FUTURES_LEVERAGE
        gross_pnl = margin * pnl_pct / 100.0
        fees = notional * self.PAPER_FUTURES_FEE_RATE * 2
        net_pnl = gross_pnl - fees
        peak_pct = max(self._paper_futures_peak_pct, pnl_pct)
        await self._db.update_paper_futures_trade(
            self._paper_futures_id,
            {
                "status": "closed",
                "exit_price": round(exit_spot, 8),
                "current_price": round(exit_spot, 8),
                "closed_at": datetime.now(timezone.utc).isoformat(),
                "pnl_pct": round(pnl_pct, 4),
                "gross_pnl_usd": round(gross_pnl, 8),
                "fees_usd": round(fees, 8),
                "pnl_usd": round(net_pnl, 8),
                "peak_pnl_pct": round(peak_pct, 4),
                "exit_reason": exit_reason,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        self.logger.info(
            "[%s] PAPER_FUTURES_CLOSE id=%s exit=%.2f net=$%+.4f pnl=%+.2f%% peak=%+.2f%%",
            self.pair,
            self._paper_futures_id,
            exit_spot,
            net_pnl,
            pnl_pct,
            peak_pct,
        )
        self._paper_futures_id = None
        self._paper_futures_entry_spot = 0.0
        self._paper_futures_peak_pct = 0.0
        self._paper_futures_direction = None

    # ==================================================================
    # DYNAMIC OPTION SIZING
    # ==================================================================

    def _calculate_option_contracts(
        self, premium: float, confidence: float = 0.7
    ) -> int:
        """Dynamic sizing: allocate 20-30% of capital per trade based on confidence.

        Higher confidence = higher allocation (closer to 30%)
        Lower confidence = lower allocation (closer to 20%)
        """
        import math

        exchange_capital = self.risk_manager.get_exchange_capital(self._exchange_id)
        if exchange_capital <= 0 or premium <= 0:
            return 0

        # Scale allocation: 20% + (confidence * 10%) = 20-30% range
        # confidence 0.6 → 26%, confidence 1.0 → 30%
        allocation_pct = self.CAPITAL_PER_TRADE_MIN_PCT + (
            confidence
            * (self.CAPITAL_PER_TRADE_MAX_PCT - self.CAPITAL_PER_TRADE_MIN_PCT)
        )

        # Cap at 30% max per trade
        allocation_pct = min(allocation_pct, self.CAPITAL_PER_TRADE_MAX_PCT)

        # Survival mode: if balance is very low, cap allocation
        if exchange_capital < self.OPT_SURVIVAL_BALANCE:
            allocation_pct = min(allocation_pct, self.OPT_SURVIVAL_MAX_ALLOC / 100)
            if self._base_asset == "BTC":
                allocation_pct = max(allocation_pct, self.BTC_SMALL_ACCOUNT_MAX_ALLOC)

        # Calculate collateral to use (this is the premium we'll pay)
        collateral_usd = exchange_capital * allocation_pct

        # Calculate collateral required per contract
        # collateral_per_contract = premium / leverage
        collateral_per_contract = premium / self.OPTIONS_LEVERAGE
        if collateral_per_contract <= 0:
            return 0

        # Calculate contracts: collateral_usd / collateral_per_contract
        contracts = math.floor(collateral_usd / collateral_per_contract)
        contracts = max(contracts, 0)

        # Check if we have enough capital for meaningful position (at least 1 contract)
        if contracts < 1:
            self.logger.warning(
                "[%s] INSUFFICIENT_CAPITAL: bal=$%.2f, need $%.2f for 1 contract @ $%.4f",
                self.pair,
                exchange_capital,
                collateral_per_contract,
                premium,
            )
            return 0

        # Hard cap on contracts per asset
        hard_cap = 40 if self._base_asset == "ETH" else 999
        if contracts > hard_cap:
            self.logger.info(
                "[%s] SIZE_CAP: %d → %d contracts (hard cap)",
                self.pair,
                contracts,
                hard_cap,
            )
            contracts = hard_cap

        # Safety: ensure max SL loss doesn't exceed 25% of balance
        multiplier = self.CONTRACT_MULTIPLIER.get(self._base_asset, 0.01)
        max_sl_loss = (
            contracts * premium * (self.SL_PREMIUM_LOSS_PCT / 100) * multiplier
        )
        max_allowed_loss = exchange_capital * 0.25
        if max_sl_loss > max_allowed_loss and premium > 0:
            safe_contracts = math.floor(
                max_allowed_loss
                / (premium * (self.SL_PREMIUM_LOSS_PCT / 100) * multiplier)
            )
            self.logger.info(
                "[%s] SL_SAFETY: %d→%d contracts (SL loss $%.2f > 25%% of bal $%.2f)",
                self.pair,
                contracts,
                safe_contracts,
                max_sl_loss,
                exchange_capital,
            )
            contracts = max(safe_contracts, 1)

        self.logger.info(
            "[%s] OPT_SIZING: %d contracts @ $%.4f "
            "(collateral=$%.2f, alloc=%.1f%%, conf=%.2f, bal=$%.2f)",
            self.pair,
            contracts,
            premium,
            collateral_usd,
            allocation_pct * 100,
            confidence,
            exchange_capital,
        )
        return contracts

    # ==================================================================
    # DYNAMIC RATCHET FLOOR
    # ==================================================================

    def _compute_dynamic_floor(self, peak_pnl_pct: float, _energy_score: float = 0.0) -> float:
        """Tiered profit floor from peak PnL % (GPFC #26 — breathe at low peaks, tighten high).

        ``_energy_score`` is kept for call-site compatibility; tiers are peak-only.
        """
        if peak_pnl_pct <= 0:
            return -10.0
        if peak_pnl_pct < 10.0:
            return -8.0
        if peak_pnl_pct < 20.0:
            return 0.0
        if peak_pnl_pct < 35.0:
            return peak_pnl_pct * 0.40
        if peak_pnl_pct < 50.0:
            return peak_pnl_pct * 0.55
        return peak_pnl_pct * 0.65

    def _premium_price_at_least_seconds_ago(self, now: float, seconds: float) -> float | None:
        """Latest stored premium at or before ``now - seconds`` (monotonic clock)."""
        cutoff = now - seconds
        for t, p in reversed(self._position_premium_history):
            if t <= cutoff and p > 0:
                return float(p)
        return None

    def _premium_pct_change_vs_seconds_ago(
        self, current_premium: float, now: float, seconds: float
    ) -> float | None:
        """Return %% change vs premium ``seconds`` ago, or None if unknown."""
        prev = self._premium_price_at_least_seconds_ago(now, seconds)
        if prev is None or prev <= 0:
            return None
        return (current_premium - prev) / prev * 100.0

    # ==================================================================
    # GPFC #22 Part 2: Let Winners Ride — Momentum Check
    # ==================================================================

    def _update_momentum_history(self, current_price: float) -> None:
        """Track price history for momentum calculations."""
        now = time.monotonic()
        self._momentum_price_history.append((now, current_price))

    def _underlying_momentum_pct(self) -> float:
        """Underlying momentum % over the configured momentum window."""
        if len(self._momentum_price_history) < 2:
            return 0.0
        now = time.monotonic()
        cutoff = now - self._MOMENTUM_CHECK_WINDOW_SEC
        old_price = None
        for t, price in reversed(self._momentum_price_history):
            if t <= cutoff:
                old_price = price
                break
        if old_price is None or old_price <= 0:
            return 0.0
        current_price = self._momentum_price_history[-1][1]
        return (current_price - old_price) / old_price * 100

    # ── GPFC #80: spot snapshot + favorability helpers ──────────────────
    def _get_spot_price_at(self, seconds_ago: float) -> float | None:
        """Return the underlying spot price ~`seconds_ago` seconds ago.

        Uses the existing _momentum_price_history deque (which the strategy
        already feeds on every tick). Returns the oldest sample at or beyond
        the requested age, or None if the buffer doesn't reach that far back.
        """
        if len(self._momentum_price_history) < 2:
            return None
        cutoff = time.monotonic() - seconds_ago
        # iterate newest → oldest, pick first sample older than cutoff
        for t, price in reversed(self._momentum_price_history):
            if t <= cutoff and price > 0:
                return float(price)
        return None

    def _underlying_still_favorable(
        self, lookback_sec: float, threshold_pct: float
    ) -> bool:
        """True if spot has moved in our trade direction by ≥ threshold_pct % over
        the lookback window. False = spot flat or turned against us.

        Note: `threshold_pct` is expressed as a percentage (e.g. 0.05 = 0.05%),
        matching the convention of DEAD_UNDERLYING_AGAINST_PCT elsewhere in
        this file. Despite the GPFC #80 constant name suffix `_BPS`, the value
        is a percent, not basis points.
        """
        now_spot = self._last_spot_price
        past_spot = self._get_spot_price_at(seconds_ago=lookback_sec)
        if not now_spot or not past_spot:
            return False  # no data → treat as not favorable
        change_pct = (now_spot - past_spot) / past_spot * 100.0
        if self.option_side == "call":
            return change_pct >= threshold_pct
        if self.option_side == "put":
            return change_pct <= -threshold_pct
        return False

    async def _persist_sl_defer_count(self) -> None:
        """Write current _sl_defer_count to trades.metadata.sl_deferred_count."""
        if not (self._db and self._db_trade_id):
            return
        try:
            await self._db.update_trade_metadata(
                self._db_trade_id,
                {"sl_deferred_count": int(self._sl_defer_count)},
            )
        except Exception:
            self.logger.debug(
                "[%s] sl_deferred_count metadata update failed (non-critical)",
                self.option_symbol or self.pair,
            )

    def _underlying_short_momentum_pct(self, window_secs: float = 20.0) -> float:
        """Spot momentum % over a short window (default 20s).

        Used by OPT_PEAK_TRAIL spot-momentum veto to decide whether the
        underlying is still pushing in our favour. The main 60s window is
        too lagged for this decision — a move can be dying on the 20s window
        while the 60s still looks positive.
        """
        if len(self._momentum_price_history) < 2:
            return 0.0
        now = time.monotonic()
        cutoff = now - window_secs
        old_price: float | None = None
        for t, price in reversed(self._momentum_price_history):
            if t <= cutoff:
                old_price = price
                break
        if old_price is None or old_price <= 0:
            return 0.0
        current_price = self._momentum_price_history[-1][1]
        return (current_price - old_price) / old_price * 100

    def _underlying_acceleration_ratio(self) -> float:
        """Fraction of the |60s move| that occurred in the last 20s.

        Returns:
            0.0 if insufficient history or zero net 60s move.
            ~0.33 for a perfectly linear 60s move.
            >= 0.5 when the move is accelerating into the present (fresh).
            > 1.0 when the recent move overshot a smaller net move (very fresh,
            e.g. dipped then exploded back).

        Used as a freshness filter for momentum-burst entries — keeps us out of
        stale tail-end moves without demanding a bigger headline move (which
        would only buy us latency, not confidence).
        """
        if len(self._momentum_price_history) < 3:
            return 0.0
        now = time.monotonic()
        cutoff_60s = now - self._MOMENTUM_CHECK_WINDOW_SEC
        cutoff_20s = now - 20.0
        p_60s: float | None = None
        p_20s: float | None = None
        for t, price in reversed(self._momentum_price_history):
            if p_20s is None and t <= cutoff_20s:
                p_20s = price
            if t <= cutoff_60s:
                p_60s = price
                break
        if p_60s is None or p_20s is None or p_60s <= 0:
            return 0.0
        p_now = self._momentum_price_history[-1][1]
        move_60s = abs(p_now - p_60s)
        if move_60s <= 0:
            return 0.0
        move_20s = abs(p_now - p_20s)
        return move_20s / move_60s

    def _compute_energy(self, current_premium: float) -> float:
        """Combined energy = abs(underlying momentum) + abs(premium velocity) over 60s."""
        now = time.monotonic()
        cutoff = now - self._MOMENTUM_CHECK_WINDOW_SEC

        underlying_mom = 0.0
        if len(self._momentum_price_history) >= 2:
            old_underlying = None
            for t, price in reversed(self._momentum_price_history):
                if t <= cutoff:
                    old_underlying = price
                    break
            if old_underlying and old_underlying > 0:
                latest_underlying = self._momentum_price_history[-1][1]
                underlying_mom = (
                    (latest_underlying - old_underlying) / old_underlying * 100
                )

        premium_velocity = 0.0
        if len(self._premium_energy_history) >= 2:
            old_premium = None
            for t, premium in reversed(self._premium_energy_history):
                if t <= cutoff:
                    old_premium = premium
                    break
            if old_premium and old_premium > 0:
                premium_velocity = (current_premium - old_premium) / old_premium * 100

        return abs(underlying_mom) + abs(premium_velocity)

    def _premium_regime(self) -> tuple[float, float]:
        """Return (premium_momentum_pct, premium_range_pct) for recent position ticks."""
        if len(self._position_premium_history) < 2:
            return (0.0, 0.0)
        now = time.monotonic()
        cutoff = now - 90.0
        window = [(t, p) for t, p in self._position_premium_history if t >= cutoff]
        if len(window) < 2:
            window = list(self._position_premium_history)
        first_price = window[0][1]
        last_price = window[-1][1]
        if first_price <= 0:
            return (0.0, 0.0)
        prices = [p for _, p in window]
        premium_momentum_pct = (last_price - first_price) / first_price * 100
        premium_range_pct = ((max(prices) - min(prices)) / first_price * 100) if prices else 0.0
        return (premium_momentum_pct, premium_range_pct)

    def _calc_premium_velocity(self) -> float:
        """Per-tick premium velocity %% (current vs previous position tick).

        Returns 0.0 if fewer than 2 in-position ticks recorded. Positive when
        premium is rising tick-over-tick.
        """
        hist = self._position_premium_history
        if len(hist) < 2:
            return 0.0
        prev_p = hist[-2][1]
        curr_p = hist[-1][1]
        if prev_p <= 0:
            return 0.0
        return (curr_p - prev_p) / prev_p * 100.0

    def _calc_underlying_mom(self, window_secs: float = 60.0) -> float:
        """Spot momentum %% over a window. Wraps the existing 60s/short helpers."""
        if window_secs >= 60.0:
            return self._underlying_momentum_pct()
        return self._underlying_short_momentum_pct(window_secs)

    def _underlying_still_supports_position(self) -> tuple[bool, float]:
        """GPFC #64: is the underlying spot still trending in our direction?

        Returns (supports, aligned_mom_pct). True when the 60s aligned move
        exceeds PULLBACK_SPOT_VETO_PCT — used by PEAK and TRAIL to defer
        gain-locking exits while spot is still pushing in our favour.

        Long call: positive mom helps. Long put: negative mom helps. The
        signed product `our_dir * mom_pct` is the aligned move.
        """
        if not self.option_side:
            return False, 0.0
        mom_pct = self._underlying_momentum_pct()  # signed % over 60s
        our_dir = 1.0 if self.option_side == "call" else -1.0
        aligned_move = our_dir * mom_pct
        if aligned_move > self.PHASE_TRAIL_SPOT_VETO_PCT:
            return True, aligned_move

        # After restart the 60s websocket buffer is cold, so use spot-vs-entry
        # as a fallback. This keeps restored winners from exiting just because
        # momentum history has not had a full minute to rebuild.
        if aligned_move == 0.0 and self._spot_at_entry > 0 and self._last_spot_price:
            entry_change = (
                (float(self._last_spot_price) - self._spot_at_entry)
                / self._spot_at_entry
                * 100.0
            )
            aligned_from_entry = our_dir * entry_change
            return (
                aligned_from_entry > self.PHASE_TRAIL_SPOT_VETO_PCT,
                aligned_from_entry,
            )

        return False, aligned_move

    def _extract_iv(self, ticker: dict[str, Any] | None) -> float | None:
        """GPFC #82: pull mark_vol (IV as decimal, e.g. 0.30 = 30%) from ticker.

        Returns None if ticker missing or mark_vol unparseable, so callers can
        treat missing IV as "regime unknown" rather than as a hard zero.
        """
        if not ticker:
            return None
        info = ticker.get("info") or {}
        raw = info.get("mark_vol")
        if raw in (None, ""):
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_mark_price(ticker: dict[str, Any] | None) -> float | None:
        """Pull Delta's raw mark price from ticker info without bid/mid fallback."""
        if not ticker:
            return None
        info = ticker.get("info") or {}
        raw = info.get("mark_price")
        if raw in (None, ""):
            raw = ticker.get("mark")
        try:
            mark = float(raw)
        except (TypeError, ValueError):
            return None
        return mark if mark > 0 else None

    def _entry_execution_snapshot(
        self,
        ticker: dict[str, Any] | None,
        entry_ask: float,
        option_type: str | None,
    ) -> dict[str, float]:
        """Execution-quality snapshot for entry gating and trade metadata."""
        snapshot: dict[str, float] = {}
        if not ticker:
            return snapshot

        try:
            bid = float(ticker.get("bid") or 0)
        except (TypeError, ValueError):
            bid = 0.0
        try:
            ask = float(ticker.get("ask") or entry_ask or 0)
        except (TypeError, ValueError):
            ask = 0.0
        mark = self._extract_mark_price(ticker)

        if bid > 0:
            snapshot["entry_bid"] = round(bid, 4)
        if ask > 0:
            snapshot["entry_ask"] = round(ask, 4)
        if mark is not None:
            snapshot["entry_mark"] = round(mark, 4)
        if ask > 0 and bid > 0:
            snapshot["entry_spread_pct"] = round((ask - bid) / ask * 100.0, 4)
            snapshot["entry_bid_gap_pct"] = snapshot["entry_spread_pct"]
        if ask > 0 and mark is not None:
            snapshot["entry_mark_gap_pct"] = round((ask - mark) / ask * 100.0, 4)

        if option_type == "call":
            prev2_ask = self._prev2_call_ask
            prev_ask = self._prev_call_ask
        elif option_type == "put":
            prev2_ask = self._prev2_put_ask
            prev_ask = self._prev_put_ask
        else:
            prev2_ask = 0.0
            prev_ask = 0.0

        if entry_ask > 0 and prev_ask > 0:
            snapshot["premium_last_rise_pct"] = round(
                (entry_ask - prev_ask) / prev_ask * 100.0,
                4,
            )
        if entry_ask > 0 and prev2_ask > 0:
            snapshot["premium_cum_rise_pct"] = round(
                (entry_ask - prev2_ask) / prev2_ask * 100.0,
                4,
            )
        return snapshot

    def _passes_entry_quality(
        self,
        ticker: dict[str, Any] | None,
        *,
        min_iv: float | None = None,
        min_delta_abs: float | None = None,
        min_turnover_usd: float | None = None,
    ) -> tuple[bool, str]:
        """GPFC #67: liquidity + moneyness + IV gate before any entry fires.

        Returns (passes, skip_reason). Winners cluster at |delta| 0.42-0.61,
        IV 0.41-0.54, turnover $2.84M-$13.68M. Reject anything outside the
        bands so we stop bleeding on illiquid tails / wrong-moneyness picks.
        """
        if not ticker:
            return True, ""  # don't penalize if ticker fetch failed; spread guard already passed
        info = ticker.get("info") or {}
        greeks = info.get("greeks") or {}
        try:
            turnover = float(info.get("turnover_usd", 0) or 0)
        except (TypeError, ValueError):
            turnover = 0.0
        try:
            delta_abs = abs(float(greeks.get("delta", 0) or 0))
        except (TypeError, ValueError):
            delta_abs = 0.0
        try:
            iv = float(info.get("mark_vol", 0) or 0)
        except (TypeError, ValueError):
            iv = 0.0

        skip_reasons: list[str] = []
        turnover_floor = self.ENTRY_MIN_TURNOVER_USD if min_turnover_usd is None else min_turnover_usd
        if turnover < turnover_floor:
            skip_reasons.append(f"turnover_low_${turnover/1e6:.2f}M_min_{turnover_floor/1e6:.2f}M")
        delta_floor = self.ENTRY_DELTA_MIN_ABS if min_delta_abs is None else min_delta_abs
        if delta_abs < delta_floor:
            skip_reasons.append(f"delta_too_low_{delta_abs:.2f}_min_{delta_floor:.2f}")
        if delta_abs > self.ENTRY_DELTA_MAX_ABS:
            skip_reasons.append(f"delta_too_high_{delta_abs:.2f}")
        iv_floor = self.ENTRY_MIN_IV if min_iv is None else min_iv
        if iv < iv_floor:
            skip_reasons.append(f"iv_low_{iv:.2f}_min_{iv_floor:.2f}")

        if skip_reasons:
            return False, ", ".join(skip_reasons)
        return True, ""

    def _score_option_entry(
        self,
        ticker: dict[str, Any] | None,
        entry_ask: float,
        option_type: str,
        setup_type: str,
        *,
        min_score: float | None = None,
        min_expected_edge_pct: float | None = None,
        max_spread_pct: float | None = None,
        trend_edge_pct: float | None = None,
    ) -> tuple[bool, str, dict[str, Any]]:
        """Score an options entry against microstructure cost and expected edge.

        The underlying can move and still be a bad option trade if the selected
        contract's spread/mark gap/noise is larger than the expected first move.
        This gate keeps momentum setups from buying contracts with no room to
        breathe after fees and quote noise.
        """
        snapshot = self._entry_execution_snapshot(ticker, entry_ask, option_type)
        info = (ticker or {}).get("info") or {}
        greeks = info.get("greeks") or {}

        try:
            bid = float((ticker or {}).get("bid") or 0)
        except (TypeError, ValueError):
            bid = 0.0
        try:
            turnover_usd = float(info.get("turnover_usd", 0) or 0)
        except (TypeError, ValueError):
            turnover_usd = 0.0
        try:
            delta_abs = abs(float(greeks.get("delta", 0) or 0))
        except (TypeError, ValueError):
            delta_abs = 0.0
        iv = self._extract_iv(ticker) or 0.0

        our_dir = 1.0 if option_type == "call" else -1.0
        aligned_60s = our_dir * self._calc_underlying_mom(60.0)
        aligned_20s = our_dir * self._calc_underlying_mom(20.0)
        spread_pct = float(snapshot.get("entry_spread_pct") or 0.0)
        mark_gap_pct = max(0.0, float(snapshot.get("entry_mark_gap_pct") or 0.0))
        spread_ceiling_pct = (
            self.ENTRY_MAX_SPREAD_PCT
            if max_spread_pct is None
            else max(0.1, float(max_spread_pct))
        )

        expected_edge_pct = max(0.0, aligned_60s * 42.0 + aligned_20s * 35.0)
        if trend_edge_pct is not None:
            expected_edge_pct = max(expected_edge_pct, max(0.0, trend_edge_pct))
        cost_floor_pct = (
            spread_pct * self.ENTRY_EDGE_SPREAD_MULT
            + mark_gap_pct * self.ENTRY_EDGE_MARK_GAP_MULT
            + self.ENTRY_NOISE_BUFFER_PCT
        )

        spread_score = max(0.0, min(100.0, (spread_ceiling_pct - spread_pct) / spread_ceiling_pct * 100.0))
        mark_score = max(0.0, min(100.0, (self.ENTRY_MAX_MARK_GAP_PCT - mark_gap_pct) / self.ENTRY_MAX_MARK_GAP_PCT * 100.0))
        liquidity_score = max(0.0, min(100.0, turnover_usd / 10_000_000.0 * 100.0))
        if 0.40 <= delta_abs <= 0.65:
            delta_score = 100.0
        elif delta_abs > 0:
            delta_score = max(0.0, 100.0 - abs(delta_abs - 0.52) / 0.25 * 100.0)
        else:
            delta_score = 0.0
        iv_score = max(0.0, min(100.0, iv / 0.45 * 100.0))
        momentum_score = max(0.0, min(100.0, expected_edge_pct / 18.0 * 100.0))

        score = (
            spread_score * 0.25
            + mark_score * 0.15
            + liquidity_score * 0.20
            + delta_score * 0.15
            + iv_score * 0.10
            + momentum_score * 0.15
        )
        score_floor = self.ENTRY_MIN_CONTRACT_SCORE if min_score is None else min_score
        edge_floor = (
            self.ENTRY_MIN_EXPECTED_EDGE_PCT
            if min_expected_edge_pct is None
            else min_expected_edge_pct
        )

        quality = {
            "entry_quality_score": round(score, 1),
            "entry_expected_edge_pct": round(expected_edge_pct, 2),
            "entry_cost_floor_pct": round(cost_floor_pct, 2),
            "entry_aligned_60s_pct": round(aligned_60s, 4),
            "entry_aligned_20s_pct": round(aligned_20s, 4),
            "entry_spread_pct": round(spread_pct, 4),
            "entry_max_spread_pct": round(spread_ceiling_pct, 4),
            "entry_mark_gap_pct": round(mark_gap_pct, 4),
            "entry_bid": round(bid, 4) if bid > 0 else None,
            "entry_ask": round(entry_ask, 4),
            "entry_turnover_usd": round(turnover_usd, 2),
            "entry_delta_abs": round(delta_abs, 4),
            "entry_iv": round(iv, 4),
            "entry_setup_type": setup_type,
        }

        if score < score_floor:
            return False, f"score {score:.1f} < {score_floor:.1f}", quality
        if expected_edge_pct < edge_floor:
            return False, f"expected_edge {expected_edge_pct:.1f}% < {edge_floor:.1f}%", quality
        if expected_edge_pct < cost_floor_pct:
            return False, f"expected_edge {expected_edge_pct:.1f}% < cost_floor {cost_floor_pct:.1f}%", quality
        return True, "", quality

    def _adaptive_entry_max_spread_pct(
        self,
        option_type: str,
        *,
        base_max_spread_pct: float,
        fast_move_max_spread_pct: float,
    ) -> float:
        """Allow wider option spreads only while the underlying is actively moving."""
        our_dir = 1.0 if option_type == "call" else -1.0
        aligned_60s = our_dir * self._calc_underlying_mom(60.0)
        aligned_20s = our_dir * self._calc_underlying_mom(20.0)
        if (
            aligned_60s >= self.EXPLOSIVE_MOVE_SPREAD_60S_PCT
            and aligned_20s >= self.EXPLOSIVE_MOVE_SPREAD_20S_PCT
        ):
            return max(base_max_spread_pct, fast_move_max_spread_pct, self.EXPLOSIVE_MOVE_MAX_SPREAD_PCT)
        if (
            aligned_60s >= self.FAST_MOVE_SPREAD_60S_PCT
            and aligned_20s >= self.FAST_MOVE_SPREAD_20S_PCT
        ):
            return max(base_max_spread_pct, fast_move_max_spread_pct)
        if (
            aligned_60s >= self.ACTIVE_MOVE_SPREAD_60S_PCT
            and aligned_20s >= self.ACTIVE_MOVE_SPREAD_20S_PCT
        ):
            return max(base_max_spread_pct, self.ACTIVE_MOVE_MAX_SPREAD_PCT)
        return base_max_spread_pct

    def _calculate_confidence(
        self,
        ticker: dict[str, Any] | None,
        option_type: str | None,
        *,
        entry_path: str = "unknown",
    ) -> tuple[float, dict[str, float]]:
        """GPFC #81: confidence collapsed to aligned_mom only.

        Historical analysis showed the other 5 components were noise or
        counter-predictive vs win rate / right-tail. The 6-component breakdown
        is still computed and returned so we can observe the components in
        trades.metadata, but the SCORE is now `aligned_mom` alone.

        Components (each scored 0–100, but only aligned_mom counts):
          1. bb_tightness  — observed only
          2. bb_kc_quality — observed only
          3. aligned_mom   — signed underlying 60s momentum vs option side  ★ score
          4. freshness     — observed only
          5. liquidity     — observed only
          6. moneyness     — observed only
        """
        breakdown: dict[str, float] = {}

        # 1. BB tightness — bb_width vs asset threshold
        bb_w = self._bb_width_pct or 0.0
        bb_thr = (
            self.SQUEEZE_BB_WIDTH_BTC
            if self._base_asset == "BTC"
            else self.SQUEEZE_BB_WIDTH_ETH
        )
        if bb_w > 0 and bb_thr > 0:
            breakdown["bb_tightness"] = max(0.0, min(100.0, (1.0 - bb_w / bb_thr) * 100.0))
        else:
            breakdown["bb_tightness"] = 0.0

        # 2. BB/KC ratio — sweet zone is < 1.0 (BB inside KC); ratio ≥ 2 = 0
        kc_w = self._last_kc_width_pct or 0.0
        if kc_w > 0 and bb_w > 0:
            ratio = bb_w / kc_w
            breakdown["bb_kc_quality"] = max(0.0, min(100.0, (2.0 - ratio) / 2.0 * 100.0))
        else:
            breakdown["bb_kc_quality"] = 0.0

        # 3. Aligned momentum — our_dir × 60s spot momentum, capped at 0.20%
        our_dir = 1.0 if option_type == "call" else -1.0 if option_type == "put" else 0.0
        try:
            mom60 = self._underlying_momentum_pct()
        except Exception:
            mom60 = 0.0
        aligned = our_dir * mom60
        breakdown["aligned_mom"] = max(0.0, min(100.0, aligned / 0.20 * 100.0))

        # 4. Freshness — 20s/60s ratio. 0.7+ = perfect, 0.0 = 0.
        try:
            fresh = self._underlying_acceleration_ratio()
        except Exception:
            fresh = 0.0
        breakdown["freshness"] = max(0.0, min(100.0, fresh / 0.70 * 100.0))

        # 5. Liquidity — turnover in USD, capped at $10M
        info = (ticker or {}).get("info") or {}
        try:
            turnover = float(info.get("turnover_usd", 0) or 0)
        except (TypeError, ValueError):
            turnover = 0.0
        breakdown["liquidity"] = max(0.0, min(100.0, turnover / 10_000_000.0 * 100.0))

        # 6. Moneyness — |delta| proximity to 0.50 (zero penalty in [0.40, 0.60])
        greeks = info.get("greeks") or {}
        try:
            delta_abs = abs(float(greeks.get("delta", 0) or 0))
        except (TypeError, ValueError):
            delta_abs = 0.0
        if 0.40 <= delta_abs <= 0.60:
            money = 100.0
        elif delta_abs == 0.0:
            money = 0.0
        else:
            # Linear falloff from sweet zone edges to 0 at 0.20 / 0.80.
            edge_dist = min(abs(delta_abs - 0.40), abs(delta_abs - 0.60))
            money = max(0.0, 100.0 - (edge_dist / 0.20) * 100.0)
        breakdown["moneyness"] = money

        # GPFC #81: score = aligned_mom only (other components observed-only).
        score = round(float(breakdown.get("aligned_mom", 0.0)), 1)
        if entry_path == "trend_flow":
            flow_pct = abs(float(getattr(self, "_breakout_velocity_pct", 0.0) or 0.0))
            # GPFC #88: TREND_FLOW is deliberately a 15m staircase setup.
            # Do not let a flat final 60s window block a valid sustained move.
            flow_score = max(0.0, min(100.0, flow_pct / self.TREND_FLOW_15M_PCT * 60.0))
            breakdown["trend_flow"] = round(flow_score, 1)
            score = max(score, round(flow_score, 1))
        if entry_path == "fvg_choch":
            fvg = self._last_fvg_choch_signal or {}
            fvg_score = float(fvg.get("confidence") or 0.0)
            breakdown["fvg_zone"] = 100.0 if fvg.get("zone_mid") is not None else 0.0
            breakdown["choch"] = 100.0 if fvg.get("choch_level") is not None else 0.0
            breakdown["fvg_retest"] = 100.0 if fvg.get("fvg_1m_mid") is not None else 0.0
            score = max(score, fvg_score)
        if entry_path == "premium_wave":
            wave = self._last_entry_quality or {}
            premium_5m = max(0.0, float(wave.get("premium_5m_pct") or 0.0))
            premium_15m = max(0.0, float(wave.get("premium_15m_pct") or 0.0))
            underlying_5m = max(0.0, float(wave.get("underlying_5m_pct") or 0.0))
            underlying_15m = max(0.0, float(wave.get("underlying_15m_pct") or 0.0))
            breakdown["premium_wave"] = max(
                min(100.0, premium_5m / self.PREMIUM_WAVE_MIN_5M_RISE_PCT * 70.0),
                min(100.0, premium_15m / self.PREMIUM_WAVE_MIN_15M_RISE_PCT * 70.0),
            )
            breakdown["wave_underlying"] = max(
                min(100.0, underlying_5m / self.PREMIUM_WAVE_MIN_UNDERLYING_5M_PCT * 70.0),
                min(100.0, underlying_15m / self.PREMIUM_WAVE_MIN_UNDERLYING_15M_PCT * 70.0),
            )
            wave_score = max(float(getattr(self, "_breakout_confidence", 0.0) or 0.0) * 100.0, 72.0)
            score = max(score, round(wave_score, 1))
        score = max(0.0, min(100.0, score))
        # Round each component for clean storage.
        breakdown = {k: round(v, 1) for k, v in breakdown.items()}
        return score, breakdown

    def _entry_risk_reward_ratio(self, entry_path: str) -> str:
        """Planned risk:reward bucket used for dashboard review."""
        path = (entry_path or "").lower()
        if path == "mom_reentry":
            return "1:3"
        if path == "fvg_choch":
            return "1:3"
        if path in {"mom_burst", "move_pullback", "trend_flow", "premium_wave"}:
            return "1:2"
        if path == "squeeze_confirmed":
            return "1:1"
        return "1:1"

    def _build_entry_metadata(
        self,
        ticker: dict[str, Any] | None,
        option_type: str | None,
        entry_premium: float,
        *,
        entry_path: str = "unknown",
        regime: str = "UNKNOWN",
    ) -> dict[str, Any]:
        """GPFC #74: single source of truth for entry metadata.

        Returns a dict containing the raw signal snapshot plus confidence,
        SL, and trail fields. Raises if confidence cannot be computed — the
        caller must gate entry on success; no silent fallback is permitted.
        """
        info = (ticker or {}).get("info") or {}
        greeks = info.get("greeks") or {}

        def _get(key: str) -> Any:
            v = info.get(key)
            return v if v not in (None, "") else None

        snapshot: dict[str, Any] = {
            # IV / volatility
            "iv": _get("mark_vol"),
            "iv_24h": _get("mark_change_24h"),
            # Open interest / turnover
            "oi": _get("oi"),
            "oi_value_usd": _get("oi_value_usd"),
            "oi_change_6h": _get("oi_change_usd_6h"),
            "turnover_usd": _get("turnover_usd"),
            # Greeks
            "delta": greeks.get("delta"),
            "gamma": greeks.get("gamma"),
            "theta": greeks.get("theta"),
            "vega": greeks.get("vega"),
            # Internal entry context
            "bb_width_pct": round(self._bb_width_pct, 4) if self._bb_width_pct else None,
            "kc_width_pct": (
                round(self._last_kc_width_pct, 4) if self._last_kc_width_pct else None
            ),
            "breakout_velocity_pct": (
                round(self._breakout_velocity_pct, 5)
                if getattr(self, "_breakout_velocity_pct", 0)
                else None
            ),
            "premium_velocity_at_entry": round(self._calc_premium_velocity(), 4),
            "underlying_mom_60s": round(self._calc_underlying_mom(60), 4),
            "regime": regime,
            "spot_at_entry": (
                round(self._last_spot_price, 4) if self._last_spot_price else None
            ),
            "entry_path": entry_path,
            "entry_sequence": "second" if entry_path == "mom_reentry" else "first",
            "is_second_entry": entry_path == "mom_reentry",
            "risk_reward_ratio": self._entry_risk_reward_ratio(entry_path),
            **self._entry_execution_snapshot(ticker, entry_premium, option_type),
        }
        if (
            self._last_entry_quality
            and (
                str(self._last_entry_quality.get("entry_setup_type", "")).lower()
                == entry_path.upper().lower()
                or entry_path == "mom_reentry"
            )
        ):
            snapshot.update(self._last_entry_quality)
        if entry_path == "fvg_choch" and self._last_fvg_choch_signal:
            snapshot["fvg_choch"] = self._last_fvg_choch_signal

        # Confidence + SL + trail — raises on failure; caller decides whether to block.
        score, breakdown = self._calculate_confidence(
            ticker,
            option_type,
            entry_path=entry_path,
        )
        sl_pct = -float(self.SL_PREMIUM_LOSS_PCT)
        sl_price = (
            round(entry_premium * (1.0 + sl_pct / 100.0), 4)
            if entry_premium > 0 else None
        )
        snapshot.update({
            "confidence": score,
            "confidence_breakdown": breakdown,
            "sl_pct": sl_pct,
            "sl_price": sl_price,
            "trail_armed": False,
            "trail_floor_pct": 0.0,
        })
        self.logger.info(
            "[%s] CONFIDENCE=%.0f bb=%.0f bb_kc=%.0f mom=%.0f fresh=%.0f "
            "liq=%.0f money=%.0f fvg=%.0f choch=%.0f retest=%.0f entry_path=%s",
            self.pair, score,
            breakdown.get("bb_tightness", 0),
            breakdown.get("bb_kc_quality", 0),
            breakdown.get("aligned_mom", 0),
            breakdown.get("freshness", 0),
            breakdown.get("liquidity", 0),
            breakdown.get("moneyness", 0),
            breakdown.get("fvg_zone", 0),
            breakdown.get("choch", 0),
            breakdown.get("fvg_retest", 0),
            entry_path,
        )
        return snapshot

    async def _classify_regime(self) -> str:
        """GPFC #60 round 2: classify current market regime from cached OHLCV.

        Returns one of: TRENDING_UP / TRENDING_DOWN / CHOPPY / DEAD.
        Result cached for 30s. Log-only — no entry/exit gating uses this yet;
        we want 30+ tagged trades before learning which regimes win.
        """
        now = time.monotonic()
        if (
            self._cached_regime != "UNKNOWN"
            and now - self._regime_cache_at < 30.0
        ):
            return self._cached_regime

        ohlcv = self._cached_ohlcv or await self._get_ohlcv_for_squeeze()
        if not ohlcv or len(ohlcv) < 20:
            self._cached_regime = "UNKNOWN"
            self._regime_cache_at = now
            return self._cached_regime

        # Last 5 candles direction (sum of close-open signs)
        last5 = ohlcv[-5:]
        dir_signs = [
            1 if float(c[4]) >= float(c[1]) else -1
            for c in last5
        ]
        net_dir = sum(dir_signs)

        # ATR (true range) on last 14, mean of last 20 for comparison
        def _tr(idx: int) -> float:
            high = float(ohlcv[idx][2])
            low = float(ohlcv[idx][3])
            prev_close = float(ohlcv[idx - 1][4]) if idx > 0 else low
            return max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close),
            )

        tr_recent = [_tr(i) for i in range(len(ohlcv) - 14, len(ohlcv))]
        tr_baseline = [_tr(i) for i in range(len(ohlcv) - 20, len(ohlcv))]
        atr_now = sum(tr_recent) / len(tr_recent) if tr_recent else 0.0
        atr_mean = sum(tr_baseline) / len(tr_baseline) if tr_baseline else 0.0

        # Use cached BB / KC widths from latest squeeze detection.
        bb_width = self._bb_width_pct or 0.0
        # Approximate KC width from the BB threshold for the asset; we don't
        # cache KC width directly. BB inside KC ≡ active squeeze.
        bb_inside_kc = self._squeeze_status == "ACTIVE"

        # GPFC #63: regime is TRENDING_UP / TRENDING_DOWN / CHOPPY only.
        # Low-vol contraction is visible in BB width and KC width on the dashboard.
        regime = "CHOPPY"
        if abs(net_dir) >= 4 and atr_mean > 0 and atr_now > atr_mean:
            regime = "TRENDING_UP" if net_dir > 0 else "TRENDING_DOWN"

        self._cached_regime = regime
        self._regime_cache_at = now
        if self._tick_count % 6 == 0:
            self.logger.info(
                "[%s] REGIME=%s net_dir=%+d atr_now=%.4f atr_mean=%.4f "
                "bb_width=%.3f%% squeeze=%s",
                self.pair, regime, net_dir, atr_now, atr_mean,
                bb_width, bb_inside_kc,
            )
        return regime

    def _opt_trail_floor_pct(self, peak_pnl_pct: float) -> float:
        """GPFC #62 / #71: tier-driven absolute floor as %-of-entry.

        Ladder form: walks the (sorted-ascending) tier list, returns the
        highest applicable tier's floor. Tier (12, 7) means once peak hits
        +12%, the absolute exit floor is +7% from entry. Returns 0.0 if
        no tier has activated (caller gates on peak >= first_activation).
        """
        floor_pct = 0.0
        for activation, lock in self.OPT_TRAIL_TIERS:
            if peak_pnl_pct >= activation:
                floor_pct = lock
            else:
                break
        return floor_pct

    def _flat_sl_pct(self) -> float:
        """GPFC #60 round 2: flat stop-loss; previous age-based tightening removed.

        Returns the negative SL percentage (e.g. -15.0). STOP fires when
        premium drops past this threshold from entry.
        """
        return -float(self.SL_PREMIUM_LOSS_PCT)

    # ── GPFC #78: phase-based exit helpers ─────────────────────────────
    def _current_phase(self) -> str:
        """Return current exit phase A-E keyed off peak P&L."""
        peak = self._peak_pnl_pct or 0.0
        if peak < self.PHASE_A_PEAK_MAX_PCT:
            return "A"
        if peak < self.PHASE_B_PEAK_MAX_PCT:
            return "B"
        if peak < self.PHASE_C_PEAK_MAX_PCT:
            return "C"
        if peak < self.PHASE_D_PEAK_MAX_PCT:
            return "D"
        return "E"

    def _phase_trail_floor(self, phase: str) -> float:
        """Trail-floor (as % of entry) for trailing phases C/D/E.

        Returns -999.0 for phases A and B which have no trail floor.
        """
        peak = self._peak_pnl_pct or 0.0
        if phase == "C":
            return peak * self.PHASE_C_TRAIL_FRAC
        if phase == "D":
            return peak * self.PHASE_D_TRAIL_FRAC
        if phase == "E":
            return peak * self.PHASE_E_TRAIL_FRAC
        return -999.0

    def _underlying_turned_against(self, threshold: float) -> bool:
        """True if spot is moving against our option direction by >threshold% in 60s."""
        if not self.option_side:
            return False
        our_dir = 1.0 if self.option_side == "call" else -1.0
        aligned_mom = our_dir * self._underlying_momentum_pct()
        return aligned_mom < -threshold

    def _phase_b_should_develop(
        self,
        peak_pnl_pct: float,
        premium_change_pct: float,
        now: float,
    ) -> tuple[bool, float, bool]:
        """Let early winners breathe before treating a quote dip as failure."""
        if peak_pnl_pct < self.PHASE_B_DEVELOPMENT_ARM_PCT:
            return False, 0.0, False
        if premium_change_pct <= self.PHASE_B_DEVELOPMENT_SL_PCT:
            return False, 0.0, False
        position_age_sec = now - self.entry_time if self.entry_time else 0.0
        if position_age_sec > self.PHASE_B_DEVELOPMENT_MAX_SEC:
            return False, position_age_sec, False
        supports, _aligned = self._underlying_still_supports_position()
        return True, position_age_sec, supports

    # ==================================================================
    # EXIT LOGIC
    # ==================================================================

    async def _check_option_exit(self) -> list[Signal]:
        """Check exit conditions for open option position."""
        if not self.in_position or not self.option_symbol:
            return []

        # Position verification every 3rd tick (~30s)
        self._position_verify_tick += 1
        if self._position_verify_tick % 3 == 0:
            gone = await self._verify_option_position()
            if gone:
                return gone

        # Fetch current premium
        try:
            ticker = await self.options_exchange.fetch_ticker(self.option_symbol)
            # GPFC #47: mark-first pricing; Delta's ``last`` is unreliable.
            current_premium = self._get_option_premium(ticker)
            # GPFC #45 + #47: TICKER_ABSURD — even with mark_price we can get
            # garbage (e.g. stale mark during expiry roll). Only trip on truly
            # impossible values; otherwise skip the tick rather than freezing
            # writes with a stale last_known forever.
            if current_premium > 0:
                absurd = False
                if (
                    self.entry_premium > 0
                    and current_premium > self.entry_premium * 50.0
                ):
                    absurd = True
                spot_px = float(self._last_spot_price or 0)
                if spot_px > 0 and current_premium > spot_px * 0.5:
                    absurd = True
                if absurd:
                    now_mono = time.monotonic()
                    last_good = getattr(self, "_last_good_ticker_at", 0.0)
                    stale_for = now_mono - last_good if last_good > 0 else 0
                    self.logger.warning(
                        "[%s] TICKER_ABSURD symbol=%s premium=$%.4f spot=$%.2f "
                        "entry=$%.4f stale_for=%.0fs — skipping tick",
                        self.pair,
                        self.option_symbol,
                        current_premium,
                        spot_px,
                        self.entry_premium,
                        stale_for,
                    )
                    # Only fall back to last_known after 30s of consecutive
                    # absurd ticks so exit gates (max-hold, expiry) can still
                    # fire on a stale position. Otherwise skip the tick.
                    if last_good > 0 and stale_for > 30 and self._last_known_premium > 0:
                        current_premium = self._last_known_premium
                    else:
                        return []
                else:
                    self._last_good_ticker_at = time.monotonic()
                    self._last_option_ticker = ticker  # GPFC #74 FIX: keep cache fresh
            self._consecutive_ticker_failures = 0
            if current_premium > 0:
                self._last_known_premium = current_premium
        except Exception as e:
            self._consecutive_ticker_failures += 1
            now_utc = datetime.now(timezone.utc)

            if self.expiry_dt:
                mins_to_expiry = (self.expiry_dt - now_utc).total_seconds() / 60
                if mins_to_expiry <= self._EXPIRY_CLOSE_MINUTES:
                    self.logger.warning(
                        "[%s] Ticker failed near expiry (%.1f min) — marking POSITION_GONE",
                        self.option_symbol,
                        mins_to_expiry,
                    )
                    return await self._handle_position_gone("EXPIRED_TICKER_FAIL")

            if self._consecutive_ticker_failures >= self._MAX_TICKER_FAILURES:
                self.logger.warning(
                    "[%s] %d consecutive ticker failures — marking POSITION_GONE",
                    self.option_symbol,
                    self._consecutive_ticker_failures,
                )
                return await self._handle_position_gone("TICKER_FAIL_REPEATED")

            self.logger.warning(
                "[%s] Failed to fetch option ticker (%d/%d): %s",
                self.option_symbol,
                self._consecutive_ticker_failures,
                self._MAX_TICKER_FAILURES,
                e,
            )
            return []

        if current_premium <= 0:
            if self.expiry_dt and datetime.now(timezone.utc) >= self.expiry_dt:
                return await self._do_option_exit(0, -100.0, "expired_worthless")
            return []

        # GPFC #22 Part 2: Update momentum history with spot price
        try:
            if self.futures_exchange:
                spot_ticker = await self.futures_exchange.fetch_ticker(self.pair)
                spot_price = spot_ticker.get("last") or 0
                if spot_price > 0:
                    self._last_spot_price = spot_price
                    self._update_momentum_history(spot_price)
                    await self._update_paper_futures_shadow(float(spot_price))
        except Exception:
            pass  # Non-critical, continue without momentum data

        # Track peak premium (and timestamp of new peak — GPFC #52).
        if current_premium > self.highest_premium:
            self.highest_premium = current_premium
            self._peak_timestamp = time.monotonic()
            self._prev_highest_premium = current_premium
        now = time.monotonic()
        self._position_premium_history.append((now, current_premium))
        self._last_30s_premium = self._premium_price_at_least_seconds_ago(now, 30.0)
        self._premium_energy_history.append((now, current_premium))

        # Write position state to trades table every tick (~10s)
        await self._update_position_state_in_db(current_premium)

        # P&L
        premium_change_pct = (
            ((current_premium - self.entry_premium) / self.entry_premium * 100)
            if self.entry_premium > 0
            else 0
        )

        peak_pnl_pct = (
            ((self.highest_premium - self.entry_premium) / self.entry_premium * 100)
            if self.entry_premium > 0
            else 0
        )
        energy_score = self._compute_energy(current_premium)
        dynamic_floor = self._compute_dynamic_floor(peak_pnl_pct, energy_score)
        self._opt_ratchet_floor = dynamic_floor
        hours_to_expiry = (
            (self.expiry_dt - datetime.now(timezone.utc)).total_seconds() / 3600
            if self.expiry_dt
            else 99.0
        )
        in_expiry_mode = hours_to_expiry < self.EXPIRY_MODE_HOURS
        expiry_tag = f" [EXPIRY {hours_to_expiry:.1f}h]" if in_expiry_mode else ""

        # Heartbeat (every ~60s)
        if self._tick_count % 6 == 0:
            self.logger.info(
                "[%s] %s | $%.4f → $%.4f (%+.1f%%) | peak=$%.4f (+%.1f%%) | "
                "energy=%.3f%% floor=%+.1f%%%s",
                self.option_symbol,
                self.option_side,
                self.entry_premium,
                current_premium,
                premium_change_pct,
                self.highest_premium,
                peak_pnl_pct,
                energy_score,
                dynamic_floor,
                expiry_tag,
            )

        # ══ GPFC #78: phase-based exit evaluation ═════════════════════════════════════════
        # Five phases keyed off peak P&L (A through E). Replaces the
        # OPT_TRAIL_TIERS ladder + OPT_PEAK_TRAIL pullback + OPT_BREAKEVEN_STOP.
        # DEAD detector (peak ≤ 3% AND premium ≤ -8% AND underlying turned
        # against) still fires first as a phase-A early-exit special case.
        self._peak_pnl_pct = peak_pnl_pct
        self._current_pnl_pct = premium_change_pct
        phase = self._current_phase()

        # Heartbeat the phase debug line at the same cadence as the existing
        # heartbeat above (~60s) so logs stay readable.
        if self._tick_count % 6 == 0:
            self.logger.debug(
                "[%s] phase=%s peak=%.1f%% current=%.1f%% trail_floor=%.2f%%",
                self.pair, phase, peak_pnl_pct, premium_change_pct,
                self._phase_trail_floor(phase),
            )

        # ── DEAD (unchanged semantics, helper-based) ──
        position_age_sec = (
            now - self.entry_time
            if self.entry_time
            else self.DEAD_MIN_HOLD_SEC
        )

        if (
            position_age_sec >= self.DEAD_MIN_HOLD_SEC
            and peak_pnl_pct <= self.DEAD_PEAK_MAX_PCT
            and premium_change_pct <= self.DEAD_PREMIUM_DROP_PCT
            and self._underlying_turned_against(self.DEAD_UNDERLYING_AGAINST_PCT)
        ):
            self.logger.info(
                "[%s] dead — peak %+.2f%% never moved, premium %+.2f%%, "
                "underlying against us (>%.2f%% in 60s)",
                self.option_symbol,
                peak_pnl_pct,
                premium_change_pct,
                self.DEAD_UNDERLYING_AGAINST_PCT,
            )
            return await self._do_option_exit(
                current_premium, premium_change_pct, "dead"
            )

        # ── PHASE A: tight SL (-3%) with GPFC #80 momentum confirmation ──
        if phase == "A" and premium_change_pct <= self.PHASE_A_SL_PCT:
            dynamic_failed = (
                premium_change_pct <= self.PHASE_A_DYNAMIC_FAIL_PCT
                and self._underlying_turned_against(self.DEAD_UNDERLYING_AGAINST_PCT)
            )
            dynamic_hard_failed = (
                peak_pnl_pct <= self.PHASE_A_PEAK_MAX_PCT
                and premium_change_pct <= self.PHASE_A_DYNAMIC_HARD_FAIL_PCT
            )
            if (
                position_age_sec < self.PHASE_A_THESIS_WARMUP_SEC
                and (dynamic_failed or dynamic_hard_failed)
            ):
                self.logger.info(
                    "[%s] stop_phase_a DYNAMIC_FAIL -- age=%.0fs<%.0fs "
                    "current=%+.1f%% peak=%+.1f%% against=%s hard=%s",
                    self.option_symbol,
                    position_age_sec,
                    self.PHASE_A_THESIS_WARMUP_SEC,
                    premium_change_pct,
                    peak_pnl_pct,
                    dynamic_failed,
                    dynamic_hard_failed,
                )
                await self._persist_sl_defer_count()
                return await self._do_option_exit(
                    current_premium, premium_change_pct, "stop_phase_a"
                )
            if (
                position_age_sec < self.PHASE_A_THESIS_WARMUP_SEC
                and premium_change_pct > self.PHASE_A_EMERGENCY_SL_PCT
            ):
                self.logger.info(
                    "[%s] stop_phase_a WARMUP_DEFERRED — age=%.0fs<%.0fs "
                    "current=%+.1f%% peak=%+.1f%% emergency=%.1f%%",
                    self.option_symbol,
                    position_age_sec,
                    self.PHASE_A_THESIS_WARMUP_SEC,
                    premium_change_pct,
                    peak_pnl_pct,
                    self.PHASE_A_EMERGENCY_SL_PCT,
                )
                return []
            if self._underlying_still_favorable(
                self.PHASE_A_SPOT_LOOKBACK_SEC,
                self.PHASE_A_SPOT_FAVORABLE_BPS,
            ):
                self._sl_defer_count += 1
                self.logger.info(
                    "[%s] stop_phase_a DEFERRED — spot still favorable, "
                    "current=%+.1f%% peak=%+.1f%% defer_count=%d",
                    self.option_symbol,
                    premium_change_pct,
                    peak_pnl_pct,
                    self._sl_defer_count,
                )
                await self._persist_sl_defer_count()
                return []
            self.logger.info(
                "[%s] stop_phase_a — current %+.1f%% ≤ %.1f%% "
                "(peak=%+.1f%% defers=%d)",
                self.option_symbol,
                premium_change_pct,
                self.PHASE_A_SL_PCT,
                peak_pnl_pct,
                self._sl_defer_count,
            )
            await self._persist_sl_defer_count()
            return await self._do_option_exit(
                current_premium, premium_change_pct, "stop_phase_a"
            )

        # ── PHASE B: breakeven on retrace OR -5% SL backstop ──
        if (
            peak_pnl_pct >= self.PROFIT_HARVEST_ARM_PCT
            and premium_change_pct >= self.PROFIT_HARVEST_EXIT_PCT
        ):
            self.logger.info(
                "[%s] profit_harvest — current %+.1f%% with peak %+.1f%% "
                "(arm=%.1f%% exit>=%.1f%%)",
                self.option_symbol,
                premium_change_pct,
                peak_pnl_pct,
                self.PROFIT_HARVEST_ARM_PCT,
                self.PROFIT_HARVEST_EXIT_PCT,
            )
            return await self._do_option_exit(
                current_premium, premium_change_pct, "profit_harvest"
            )

        if phase == "B":
            phase_b_develop, phase_b_age_sec, phase_b_spot_supports = (
                self._phase_b_should_develop(peak_pnl_pct, premium_change_pct, now)
            )
            phase_b_armed = (
                peak_pnl_pct
                >= self.PHASE_B_BREAKEVEN_ARM_PCT
                - self.PHASE_B_BREAKEVEN_ARM_BUFFER_PCT
            )
            if (
                premium_change_pct <= self.PHASE_B_BREAKEVEN_EXIT_PCT
                and phase_b_armed
            ):
                if phase_b_develop and premium_change_pct > 0:
                    self.logger.info(
                        "[%s] breakeven DEFERRED - Phase B winner still developing "
                        "(age=%.0fs current=%+.1f%% peak=%+.1f%% spot_support=%s)",
                        self.option_symbol,
                        phase_b_age_sec,
                        premium_change_pct,
                        peak_pnl_pct,
                        phase_b_spot_supports,
                    )
                    return []
                self.logger.info(
                    "[%s] breakeven — peak %+.1f%% protected at %+.1f%% "
                    "(arm=%.1f%% buffer=%.2f%% exit≤%.1f%%)",
                    self.option_symbol,
                    peak_pnl_pct,
                    premium_change_pct,
                    self.PHASE_B_BREAKEVEN_ARM_PCT,
                    self.PHASE_B_BREAKEVEN_ARM_BUFFER_PCT,
                    self.PHASE_B_BREAKEVEN_EXIT_PCT,
                )
                return await self._do_option_exit(
                    current_premium, premium_change_pct, "breakeven"
                )
            micro_protect_armed = peak_pnl_pct >= self.PHASE_B_MICRO_PROTECT_ARM_PCT
            if (
                micro_protect_armed
                and premium_change_pct <= self.PHASE_B_MICRO_PROTECT_EXIT_PCT
            ):
                if phase_b_develop and premium_change_pct > self.PHASE_B_SL_PCT:
                    self.logger.info(
                        "[%s] micro_protect DEFERRED - Phase B winner still developing "
                        "(age=%.0fs current=%+.1f%% peak=%+.1f%% spot_support=%s)",
                        self.option_symbol,
                        phase_b_age_sec,
                        premium_change_pct,
                        peak_pnl_pct,
                        phase_b_spot_supports,
                    )
                    return []
                self.logger.info(
                    "[%s] micro_protect — peak %+.1f%% protected before red "
                    "(current=%+.1f%% arm=%.1f%% exit<=%.1f%%)",
                    self.option_symbol,
                    peak_pnl_pct,
                    premium_change_pct,
                    self.PHASE_B_MICRO_PROTECT_ARM_PCT,
                    self.PHASE_B_MICRO_PROTECT_EXIT_PCT,
                )
                return await self._do_option_exit(
                    current_premium, premium_change_pct, "micro_protect"
                )
            if premium_change_pct <= self.PHASE_B_SL_PCT:
                # GPFC #80: same momentum-confirmation rule as Phase A.
                if self._underlying_still_favorable(
                    self.PHASE_A_SPOT_LOOKBACK_SEC,
                    self.PHASE_A_SPOT_FAVORABLE_BPS,
                ):
                    self._sl_defer_count += 1
                    self.logger.info(
                        "[%s] stop_phase_b DEFERRED — spot still favorable, "
                        "current=%+.1f%% peak=%+.1f%% defer_count=%d",
                        self.option_symbol,
                        premium_change_pct,
                        peak_pnl_pct,
                        self._sl_defer_count,
                    )
                    await self._persist_sl_defer_count()
                    return []
                if phase_b_develop:
                    self._sl_defer_count += 1
                    self.logger.info(
                        "[%s] stop_phase_b DEFERRED - Phase B winner still developing "
                        "(age=%.0fs current=%+.1f%% peak=%+.1f%% hard=%.1f%% "
                        "spot_support=%s defer_count=%d)",
                        self.option_symbol,
                        phase_b_age_sec,
                        premium_change_pct,
                        peak_pnl_pct,
                        self.PHASE_B_DEVELOPMENT_SL_PCT,
                        phase_b_spot_supports,
                        self._sl_defer_count,
                    )
                    await self._persist_sl_defer_count()
                    return []
                self.logger.info(
                    "[%s] stop_phase_b — current %+.1f%% ≤ %.1f%% "
                    "(peak=%+.1f%% defers=%d)",
                    self.option_symbol,
                    premium_change_pct,
                    self.PHASE_B_SL_PCT,
                    peak_pnl_pct,
                    self._sl_defer_count,
                )
                await self._persist_sl_defer_count()
                return await self._do_option_exit(
                    current_premium, premium_change_pct, "stop_phase_b"
                )

        # ── PHASE C/D/E: trail is primary, per-phase SL is gap backstop ──
        if phase in ("C", "D", "E"):
            floor = self._phase_trail_floor(phase)
            sl_floor = {
                "C": self.PHASE_C_SL_PCT,
                "D": self.PHASE_D_SL_PCT,
                "E": self.PHASE_E_SL_PCT,
            }[phase]
            tag = phase.lower()
            if premium_change_pct <= floor:
                supports, aligned_move = self._underlying_still_supports_position()
                if (
                    supports
                    and premium_change_pct > sl_floor
                    and self._phase_trail_defer_count < self.PHASE_TRAIL_MAX_DEFER_TICKS
                ):
                    self._phase_trail_defer_count += 1
                    self.logger.info(
                        "[%s] trail_phase_%s DEFERRED - spot still supports position "
                        "(aligned=%+.3f%% current=%+.1f%% floor=%+.2f%% peak=%+.1f%% "
                        "defer=%d/%d)",
                        self.option_symbol,
                        tag,
                        aligned_move,
                        premium_change_pct,
                        floor,
                        peak_pnl_pct,
                        self._phase_trail_defer_count,
                        self.PHASE_TRAIL_MAX_DEFER_TICKS,
                    )
                    return []
                self.logger.info(
                    "[%s] trail_phase_%s — current %+.1f%% ≤ floor %+.2f%% "
                    "(peak=%+.1f%%)",
                    self.option_symbol,
                    tag,
                    premium_change_pct,
                    floor,
                    peak_pnl_pct,
                )
                return await self._do_option_exit(
                    current_premium, premium_change_pct, f"trail_phase_{tag}"
                )
            else:
                self._phase_trail_defer_count = 0
            if premium_change_pct <= sl_floor:
                self.logger.info(
                    "[%s] stop_phase_%s — current %+.1f%% ≤ %.1f%% (peak=%+.1f%%)",
                    self.option_symbol,
                    tag,
                    premium_change_pct,
                    sl_floor,
                    peak_pnl_pct,
                )
                return await self._do_option_exit(
                    current_premium, premium_change_pct, f"stop_phase_{tag}"
                )

        return []

    # ==================================================================
    # OPTIONS DB WRITE
    # ==================================================================

    async def _write_entry_to_db(
        self,
        fill_price: float,
        contracts: int,
        order: dict,
        signal,
        option_symbol: str,
        option_side: str,
        strike_price: float,
        base_asset: str,
    ):
        """Insert a new options trade row into the DB."""
        try:
            # GPFC #76: strict fill-confirmation gate — refuse to INSERT if any
            # of the four conditions fails. Kills optimistic-insert ghosts.
            _guard_order_id = str(order.get("id") or "").strip() if order else ""
            _guard_entry_path = (
                (self._pending_entry_signals or {}).get("entry_path")
                if self._pending_entry_signals else None
            )
            if not (_guard_order_id and fill_price > 0 and contracts > 0 and _guard_entry_path):
                self.logger.warning(
                    "[%s] trade insert ABORTED — incomplete fill confirmation: "
                    "order_id=%s entry_price=%s contracts=%s entry_path=%s",
                    option_symbol,
                    _guard_order_id or "<missing>",
                    fill_price,
                    contracts,
                    _guard_entry_path or "<missing>",
                )
                return

            # GPFC #48: DUPLICATE_INSERT_BLOCKED — the signal path and the
            # on_fill callback can race and insert two rows for the same fill
            # (#3082/#3083). Before inserting, check if an open row already
            # exists for this symbol+strategy within the last 60 s; if so,
            # adopt it and skip the insert.
            order_id_val = str(order.get("id") or "").strip() if order else ""
            try:
                if self._db and self._db.is_connected:
                    existing = await self._db.get_open_trade(
                        pair=option_symbol,
                        exchange="delta",
                        strategy="options_scalp",
                    )
                    if existing and existing.get("id"):
                        existing_id = existing["id"]
                        existing_oid = str(existing.get("order_id") or "").strip()
                        existing_fid = str(existing.get("exchange_fill_id") or "").strip()
                        # Same Delta order ID → definitely the same fill.
                        same_fill = bool(
                            order_id_val
                            and (
                                existing_oid == order_id_val
                                or existing_fid == order_id_val
                            )
                        )
                        recent = False
                        opened_str = existing.get("opened_at", "")
                        if opened_str:
                            try:
                                opened_dt = datetime.fromisoformat(
                                    str(opened_str).replace("Z", "+00:00")
                                )
                                if opened_dt.tzinfo is None:
                                    opened_dt = opened_dt.replace(tzinfo=timezone.utc)
                                recent = (
                                    datetime.now(timezone.utc) - opened_dt
                                ).total_seconds() <= 60
                            except Exception:
                                recent = False
                        if same_fill or recent:
                            self.logger.warning(
                                "[%s] DUPLICATE_INSERT_BLOCKED symbol=%s "
                                "existing_id=%s order_id=%s (same_fill=%s recent=%s) — "
                                "adopting existing row, skipping insert",
                                self.option_symbol or option_symbol,
                                option_symbol,
                                existing_id,
                                order_id_val or "<none>",
                                same_fill,
                                recent,
                            )
                            self._db_trade_id = existing_id
                            # Backfill order_id onto the existing row if missing.
                            if order_id_val and not existing_oid:
                                try:
                                    self.executor.db.client.table("trades").update(
                                        {
                                            "order_id": order_id_val,
                                            "exchange_fill_id": order_id_val,
                                        }
                                    ).eq("id", existing_id).execute()
                                except Exception:
                                    self.logger.debug(
                                        "[%s] failed to backfill order_id on adopted row",
                                        option_symbol,
                                    )
                            # GPFC #71b fix: merge pending entry-signal snapshot
                            # (confidence, sl_pct, trail_*, etc.) into the
                            # adopted row's metadata. Otherwise the reconciler
                            # path's pre-existing row never gets the snapshot.
                            if self._pending_entry_signals:
                                try:
                                    await self._db.update_trade_metadata(
                                        existing_id, self._pending_entry_signals
                                    )
                                    self.logger.info(
                                        "[%s] METADATA_MERGED into adopted row id=%s "
                                        "(confidence=%s)",
                                        option_symbol, existing_id,
                                        self._pending_entry_signals.get("confidence"),
                                    )
                                except Exception:
                                    self.logger.debug(
                                        "[%s] metadata merge into adopted row failed "
                                        "(non-critical)", option_symbol,
                                    )
                                self._pending_entry_signals = None
                            return
            except Exception:
                self.logger.debug(
                    "[%s] dedupe check failed — proceeding with insert",
                    option_symbol,
                )

            mult = self.CONTRACT_MULTIPLIER.get(base_asset, 0.01)
            spot = self._last_spot_price or 0
            entry_fee = round(contracts * mult * spot * 0.000118, 8) if spot else 0
            # Resolve setup_type with ordered fallbacks; every branch evaluated
            # so a present-but-sparse signal.metadata can't shadow _pending_entry_setup.
            setup_type = None
            if signal and hasattr(signal, "metadata") and signal.metadata:
                setup_type = signal.metadata.get("setup_type")
            if not setup_type and self._pending_entry_setup:
                setup_type = self._pending_entry_setup
            if not setup_type and self._is_squeeze_entry:
                setup_type = "SQUEEZE"
            if not setup_type:
                setup_type = "MOM_BURST"

            self.logger.info(
                "[%s] Setup type determined: %s", self.option_symbol, setup_type
            )
            signals_fired = getattr(signal, "metadata", {}).get("signals_fired") or (
                f"option_side={option_side} " + getattr(self, "_entry_context", "")
            )

            row = {
                "pair": option_symbol,
                "exchange": "delta",
                "strategy": "options_scalp",
                "side": "buy",
                "entry_price": 0,
                "contracts": float(contracts),
                "leverage": self.OPTIONS_LEVERAGE,
                "collateral": 0,
                "entry_fee": entry_fee,
                "exit_fee": 0,
                "gross_pnl": 0,
                "net_pnl": 0,
                "pnl": 0,
                "pnl_pct": 0,
                "status": "open",
                "setup_type": setup_type,
                "signals_fired": signals_fired,
                "opened_at": datetime.utcnow().isoformat() + "Z",
            }
            # GPFC #48: persist Delta order id so the unique index on
            # (exchange, exchange_fill_id) can enforce dedup at the DB level.
            if order_id_val:
                row["order_id"] = order_id_val
                row["exchange_fill_id"] = order_id_val
            # GPFC #60 round 2: attach entry-signal snapshot if captured.
            if self._pending_entry_signals:
                row["metadata"] = self._pending_entry_signals
                self._pending_entry_signals = None

            try:
                result = self.executor.db.client.table("trades").insert(row).execute()
            except Exception as insert_err:
                # Unique-index violation from (exchange, exchange_fill_id) —
                # another coroutine beat us to the insert. Adopt that row.
                err_str = str(insert_err).lower()
                if "unique" in err_str or "duplicate" in err_str or "23505" in err_str:
                    self.logger.warning(
                        "[%s] DUPLICATE_INSERT_BLOCKED via DB unique constraint "
                        "order_id=%s — looking up winner",
                        option_symbol, order_id_val,
                    )
                    try:
                        existing = await self._db.get_open_trade(
                            pair=option_symbol,
                            exchange="delta",
                            strategy="options_scalp",
                        )
                        if existing and existing.get("id"):
                            self._db_trade_id = existing["id"]
                            # GPFC #71b fix: same metadata-merge path as the
                            # pre-insert dedup branch above, for the case where
                            # we lost the race at the DB layer rather than the
                            # app layer.
                            if self._pending_entry_signals:
                                try:
                                    await self._db.update_trade_metadata(
                                        existing["id"], self._pending_entry_signals
                                    )
                                    self.logger.info(
                                        "[%s] METADATA_MERGED into race-adopted "
                                        "row id=%s (confidence=%s)",
                                        option_symbol, existing["id"],
                                        self._pending_entry_signals.get("confidence"),
                                    )
                                except Exception:
                                    self.logger.debug(
                                        "[%s] metadata merge into race-adopted "
                                        "row failed (non-critical)", option_symbol,
                                    )
                                self._pending_entry_signals = None
                            return
                    except Exception:
                        pass
                raise
            if result.data:
                self._db_trade_id = result.data[0].get("id")
            else:
                self.logger.error(
                    "[%s] OPTIONS DB ENTRY returned no data", option_symbol
                )
                return

            signal_price = getattr(signal, "price", 0) or 0
            actual_fill = await self._resolve_fill_price(order, option_symbol)

            if actual_fill and actual_fill > 0:
                collateral = actual_fill * contracts * mult
                self.executor.db.client.table("trades").update(
                    {
                        "entry_price": round(actual_fill, 8),
                        "collateral": round(collateral, 4),
                    }
                ).eq("id", self._db_trade_id).execute()

                self.entry_premium = actual_fill
                self.highest_premium = max(self.highest_premium, actual_fill)

                self.logger.info(
                    "[%s] DB entry_price updated: signal=$%.4f fill=$%.4f id=%s x%d fee=$%.6f",
                    option_symbol,
                    signal_price,
                    actual_fill,
                    self._db_trade_id,
                    contracts,
                    entry_fee,
                )
            else:
                collateral = fill_price * contracts * mult
                self.executor.db.client.table("trades").update(
                    {
                        "entry_price": round(fill_price, 8),
                        "collateral": round(collateral, 4),
                    }
                ).eq("id", self._db_trade_id).execute()
                self.logger.warning(
                    "[%s] DB entry_price FALLBACK: signal=$%.4f on_fill=$%.4f (fetch_order failed) id=%s",
                    option_symbol,
                    signal_price,
                    fill_price,
                    self._db_trade_id,
                )

            paper_direction = None
            if signal and hasattr(signal, "metadata") and signal.metadata:
                paper_direction = signal.metadata.get("direction") or signal.metadata.get("breakout_direction")
            if not paper_direction:
                paper_direction = "UP" if option_side == "call" else "DOWN"
            paper_entry_spot = float(self._last_spot_price or spot or 0.0)
            await self._start_paper_futures_shadow(
                option_trade_id=self._db_trade_id,
                option_symbol=option_symbol,
                setup_type=setup_type,
                direction=paper_direction,
                entry_spot=paper_entry_spot,
            )
        except Exception:
            self.logger.exception("[%s] _write_entry_to_db FAILED", option_symbol)

    async def _resolve_fill_price(self, order: dict, symbol: str) -> float:
        """Get the actual execution price from the exchange."""
        order_id = order.get("id")

        if order_id and self.options_exchange:
            try:
                import asyncio

                await asyncio.sleep(1)
                fetched = await self.options_exchange.fetch_order(order_id, symbol)
                avg = fetched.get("average")
                if avg and float(avg) > 0:
                    return float(avg)
                if fetched.get("status") == "closed":
                    p = fetched.get("price")
                    if p and float(p) > 0:
                        return float(p)
            except Exception as e:
                self.logger.debug(
                    "[%s] fetch_order for fill price failed: %s", symbol, e
                )

        avg = order.get("average")
        if avg and float(avg) > 0:
            return float(avg)

        return 0

    async def _close_option_trade_in_db(
        self,
        exit_premium: float,
        exit_type: str,
        *,
        option_symbol: str | None = None,
        entry_premium: float = 0.0,
        highest_premium: float = 0.0,
        contracts: int = 0,
        order: dict | None = None,
    ) -> bool:
        """Close the option trade in DB with correct options P&L."""
        sym = option_symbol or self.option_symbol or self.pair

        if not self._db_trade_id:
            for _ in range(20):
                await asyncio.sleep(0.1)
                if self._db_trade_id:
                    break

        if order:
            resolved = await self._resolve_fill_price(order, sym)
            if resolved and resolved > 0:
                self.logger.info(
                    "[%s] DB exit_price updated: on_fill=$%.4f actual=$%.4f",
                    sym,
                    exit_premium,
                    resolved,
                )
                exit_premium = resolved
        ep = entry_premium or self.entry_premium
        hp = highest_premium or self.highest_premium
        ct = contracts or self._contracts

        if not self._db or not self._db.is_connected:
            return False

        try:
            from alpha.utils import iso_now

            if self._db_trade_id:
                resp = (
                    self.executor.db.client.table("trades")
                    .select("*")
                    .eq("id", self._db_trade_id)
                    .execute()
                )
                open_trade = resp.data[0] if resp.data else None
            else:
                open_trade = await self._db.get_open_trade(
                    pair=sym,
                    exchange="delta",
                    strategy="options_scalp",
                )
            if not open_trade:
                self.logger.warning(
                    "[%s] _close_option_trade_in_db: no open trade found (db_id=%s)",
                    sym,
                    self._db_trade_id,
                )
                return False

            db_entry = float(open_trade.get("entry_price", ep) or ep)
            db_contracts = int(
                open_trade.get("contracts") or open_trade.get("amount") or ct
            )

            multiplier = self.CONTRACT_MULTIPLIER.get(self._base_asset, 0.01)
            spot = self._last_spot_price or (
                exit_premium * (200 if self._base_asset == "BTC" else 100)
            )
            calculated_fee = round(db_contracts * multiplier * spot * 0.000118, 8)

            stored_entry_fee = float(open_trade.get("entry_fee") or 0)
            entry_fee = (
                stored_entry_fee if 0 < stored_entry_fee <= 0.10 else calculated_fee
            )
            exit_fee = calculated_fee

            self.logger.info(
                "[%s] FEE CHECK: entry stored=$%.6f calc=$%.6f using=$%.6f | exit calc=$%.6f",
                sym,
                stored_entry_fee,
                calculated_fee,
                entry_fee,
                exit_fee,
            )

            gross_pnl = self._calc_options_pnl(db_entry, exit_premium, db_contracts)
            pnl_pct = (
                (exit_premium - db_entry) / db_entry * 100 if db_entry > 0 else 0.0
            )
            net_pnl = gross_pnl - entry_fee - exit_fee

            peak_pnl_pct = (hp - ep) / ep * 100 if ep > 0 else 0

            exit_reason = canonical_option_exit_reason(exit_type)

            await self._db.update_trade(
                open_trade["id"],
                {
                    "status": "closed",
                    "exit_price": round(exit_premium, 8),
                    "closed_at": iso_now(),
                    "pnl": round(net_pnl, 8),
                    "net_pnl": round(net_pnl, 8),
                    "pnl_pct": round(pnl_pct, 4),
                    "gross_pnl": round(gross_pnl, 8),
                    "entry_fee": round(entry_fee, 8),
                    "exit_fee": round(exit_fee, 8),
                    "peak_pnl": round(peak_pnl_pct, 4),
                    "reason": exit_reason,
                    "exit_reason": exit_reason,
                    "position_state": None,
                },
            )

            await self._close_paper_futures_shadow(
                exit_spot=float(self._last_spot_price or spot or 0.0),
                exit_reason=exit_reason,
            )

            self.logger.info(
                "[%s] OPTIONS DB CLOSE: id=%s exit=$%.4f gross=$%.6f net=$%.6f (%.2f%%)",
                sym,
                open_trade["id"],
                exit_premium,
                gross_pnl,
                net_pnl,
                pnl_pct,
            )

            try:
                bot = getattr(self, "_alpha_bot", None)
                if bot and hasattr(bot, "record_session_trade"):
                    side_label = (
                        "CALL" if sym.endswith("-C") or sym.endswith("C") else "PUT"
                    )
                    bot.record_session_trade(
                        {
                            "pair": sym,
                            "base": self._base_asset,
                            "side_label": side_label,
                            "net_pnl": net_pnl,
                            "fees": entry_fee + exit_fee,
                            "pnl": net_pnl,
                        }
                    )
            except Exception:
                pass

            try:
                alerts = getattr(self.executor, "alerts", None)
                if alerts is not None:
                    pnl_emoji = "\u2705" if net_pnl >= 0 else "\u274c"
                    opened_at = open_trade.get("opened_at") or open_trade.get(
                        "created_at"
                    )
                    hold_time = "?"
                    if opened_at:
                        from datetime import datetime as _dt, timezone as _tz

                        try:
                            if isinstance(opened_at, str):
                                opened_at = _dt.fromisoformat(
                                    opened_at.replace("Z", "+00:00")
                                )
                            delta = _dt.now(_tz.utc) - opened_at
                            mins = int(delta.total_seconds() // 60)
                            hold_time = (
                                f"{mins}m"
                                if mins < 60
                                else f"{mins // 60}h{mins % 60}m"
                            )
                        except Exception:
                            pass
                    side_label = (
                        "CALL" if sym.endswith("-C") or sym.endswith("C") else "PUT"
                    )
                    msg = (
                        f"{pnl_emoji} {self._base_asset} option closed\n"
                        f"{exit_type} | {side_label} ${ep:.0f}\n"
                        f"${db_entry:.2f} \u2192 ${exit_premium:.2f} ({pnl_pct:+.1f}%)\n"
                        f"Gross: ${gross_pnl:+.4f} | Net: ${net_pnl:+.4f}\n"
                        f"Hold: {hold_time} | Fees: ${entry_fee + exit_fee:.4f}"
                    )
                    await alerts.send_text(msg)
            except Exception:
                self.logger.debug("[%s] Failed to send exit Telegram alert", sym)

            return True

        except Exception:
            self.logger.exception(
                "[%s] _close_option_trade_in_db failed",
                sym,
            )
            return False

    # ==================================================================
    # EXIT SIGNAL BUILDER
    # ==================================================================

    async def _do_option_exit_limit(
        self,
        limit_price: float,
        fallback_price: float,
        fallback_after_sec: float,
        reason: str,
    ) -> list[Signal]:
        """GPFC #71: try a limit fill at ``limit_price`` first; market fallback.

        Thin wrapper delegating to :meth:`_do_option_exit`. The actual
        limit-then-market mechanic lives in trade_executor.py (~L1078) for
        non-urgent Delta exits and uses a 3s wait. ``fallback_after_sec`` is
        accepted for caller-side documentation; the executor's value applies.
        """
        if self.entry_premium > 0:
            recomputed_pnl = (fallback_price - self.entry_premium) / self.entry_premium * 100
        else:
            recomputed_pnl = 0.0
        return await self._do_option_exit(
            current_premium=fallback_price,
            pnl_pct=recomputed_pnl,
            exit_type=reason,
            limit_price=limit_price,
        )

    def _remember_second_chance_reentry(
        self,
        *,
        exit_type: str,
        exit_premium: float,
        pnl_pct: float,
        peak_pnl_pct: float,
    ) -> None:
        """Create a short-lived watch for a better re-entry in the same option."""
        setup_type = str(self._position_setup_type or self._pending_entry_setup or "MOM_BURST")
        if setup_type not in self.REENTRY_ALLOWED_SETUPS:
            return
        if not self.option_symbol or self.entry_premium <= 0 or exit_premium <= 0:
            return
        if peak_pnl_pct < self.REENTRY_MIN_ORIGINAL_PEAK_PCT:
            return
        exit_key = exit_type.lower()
        if not (
            exit_key.startswith("stop_phase")
            or exit_key in {"dead", "micro_protect", "breakeven"}
        ):
            return
        if pnl_pct > 0 and exit_key not in {"micro_protect", "breakeven"}:
            return

        direction = "UP" if self.option_side == "call" else "DOWN"
        now = time.monotonic()
        self._reentry_watch = {
            "symbol": self.option_symbol,
            "option_type": self.option_side,
            "setup_type": setup_type,
            "direction": direction,
            "strike": self.strike_price,
            "expiry": self.expiry_dt.isoformat() if self.expiry_dt else None,
            "original_entry": self.entry_premium,
            "exit_premium": exit_premium,
            "lowest_ask": exit_premium,
            "peak_pnl_pct": peak_pnl_pct,
            "exit_type": exit_type,
            "created_at": now,
            "expires_at": now + self.REENTRY_WATCH_SEC,
            "attempts": 0,
        }
        self.logger.info(
            "[%s] SECOND_CHANCE_WATCH: %s %s entry=$%.4f exit=$%.4f "
            "peak=%+.1f%% watch=%ds discount_needed=%.1f%%",
            self.pair,
            setup_type,
            self.option_symbol,
            self.entry_premium,
            exit_premium,
            peak_pnl_pct,
            int(self.REENTRY_WATCH_SEC),
            self.REENTRY_MIN_DISCOUNT_PCT,
        )

    async def _do_option_exit(
        self,
        current_premium: float,
        pnl_pct: float,
        exit_type: str,
        limit_price: float | None = None,
    ) -> list[Signal]:
        """Build exit signal for option position.

        GPFC #71: when ``limit_price`` is provided, the executor's built-in
        limit-then-market mechanism (trade_executor.py ~L1078) will post a
        limit at that price and fall back to market after 3s if unfilled.
        For non-urgent Delta exits (TRAIL/PEAK/BREAKEVEN/DEAD) this lets us
        try to lock the tier floor before settling for the market bid.
        """
        if self._exit_in_progress:
            self.logger.info(
                "[%s] EXIT_ALREADY_IN_PROGRESS — suppressing duplicate %s",
                self.option_symbol or self.pair,
                exit_type,
            )
            return []
        self._exit_in_progress = True
        try:
            ticker = await self.options_exchange.fetch_ticker(self.option_symbol)
            # GPFC #47: for SELL placement we need a real executable price.
            # Bid is what we can actually sell at. Never use `last` (Delta
            # leaks spot) and never use mark (theoretical, not executable).
            live_bid = float(ticker.get("bid") or 0)
            if live_bid > 0:
                self.logger.info(
                    "[%s] LIVE_BID: $%.4f (cached=$%.4f, diff=%+.2f%%)",
                    self.option_symbol,
                    live_bid,
                    current_premium,
                    (live_bid - current_premium) / current_premium * 100
                    if current_premium > 0
                    else 0,
                )
                current_premium = live_bid
                if self.entry_premium > 0:
                    pnl_pct = (
                        (current_premium - self.entry_premium)
                        / self.entry_premium
                        * 100
                    )
        except Exception as e:
            self.logger.debug(
                "[%s] Live bid fetch failed, using cached: %s", self.option_symbol, e
            )

        pnl_usd = self._calc_options_pnl(
            self.entry_premium, current_premium, self._contracts
        )
        reason = (
            f"Option {exit_type} {self.option_side} | "
            f"${self.entry_premium:.4f} \u2192 ${current_premium:.4f} "
            f"({pnl_pct:+.1f}%) P&L=${pnl_usd:+.4f}"
        )
        self.logger.info("[%s] OPTIONS EXIT — %s", self.option_symbol, reason)

        pnl_tag = f"+${pnl_usd:.4f}" if pnl_usd >= 0 else f"-${abs(pnl_usd):.4f}"
        await self._log_activity(
            "options_exit",
            f"{self.pair} — OPTIONS EXIT: {exit_type} {self.option_side} | "
            f"${self.entry_premium:.4f} -> ${current_premium:.4f} ({pnl_pct:+.1f}%) {pnl_tag}",
            {
                "exit_type": exit_type,
                "option_side": self.option_side,
                "entry_premium": self.entry_premium,
                "exit_premium": current_premium,
                "pnl_pct": round(pnl_pct, 2),
                "pnl_usd": round(pnl_usd, 4),
                "strike": self.strike_price,
                "symbol": self.option_symbol,
            },
        )

        self._opt_ratchet_floor = 0.0

        if pnl_pct >= 0:
            self.hourly_wins += 1
        else:
            self.hourly_losses += 1
        self.hourly_pnl += pnl_usd

        await self._clear_dashboard_position(exit_type, pnl_pct, pnl_usd)

        peak_pnl_pct = (
            ((self.highest_premium - self.entry_premium) / self.entry_premium * 100)
            if self.entry_premium > 0
            else 0
        )
        self._remember_second_chance_reentry(
            exit_type=exit_type,
            exit_premium=current_premium,
            pnl_pct=pnl_pct,
            peak_pnl_pct=peak_pnl_pct,
        )

        # GPFC #71: if a limit_price is provided, the executor's limit-then-market
        # path (non-urgent Delta exits) will use this as the limit. Otherwise
        # market sells at current_premium as before.
        signal_price = limit_price if (limit_price is not None and limit_price > 0) else current_premium
        if limit_price is not None and limit_price > 0:
            self.logger.info(
                "[%s] EXIT_LIMIT_TARGET — %s requesting limit @ $%.4f "
                "(market_fallback @ $%.4f after 3s)",
                self.option_symbol, exit_type, signal_price, current_premium,
            )
        return [
            Signal(
                side="sell",
                price=signal_price,
                amount=float(self._contracts),
                order_type="market",
                reason=reason,
                strategy=self.name,
                pair=self.option_symbol or self.pair,
                leverage=self.OPTIONS_LEVERAGE,
                position_type="long",
                reduce_only=True,
                exchange_id="delta",
                metadata={
                    "peak_pnl": round(peak_pnl_pct, 4),
                    "exit_type": exit_type,
                    "db_already_closed": False,
                    "exit_retry_attempts": 5,
                    "exit_retry_delay_sec": 1.0,
                    "limit_price": signal_price if limit_price else None,
                    "market_fallback_price": current_premium if limit_price else None,
                },
            )
        ]

    async def _verify_option_position(self) -> list[Signal] | None:
        """Check exchange positions to detect if option is still open."""
        if not self.options_exchange or not self.option_symbol:
            return None

        # Don't verify in first 60s after entry — Delta may not show position immediately
        if self.entry_time and time.monotonic() - self.entry_time < 60:
            return None

        try:
            positions = await self.options_exchange.fetch_positions()
            self._position_verify_failures = 0
            for pos in positions:
                symbol = pos.get("symbol", "")
                contracts = float(pos.get("contracts", 0) or 0)
                if symbol == self.option_symbol and contracts != 0:
                    # Found — reset empty streak counter
                    self._position_verify_empty_count = 0
                    return None

            # GPFC #44: require MIN_VERIFY_EMPTY_CYCLES consecutive empty
            # responses before logging POSITION_GONE. If in doubt, do NOT
            # close — let the normal exit logic handle it.
            self._position_verify_empty_count += 1

            now_utc = datetime.now(timezone.utc)
            if self.expiry_dt:
                mins_to_expiry = (self.expiry_dt - now_utc).total_seconds() / 60
                if mins_to_expiry <= self._EXPIRY_CLOSE_MINUTES:
                    self.logger.warning(
                        "[%s] POSITION VERIFY: not found, near expiry (%.1f min) — "
                        "log only (verify does not close)",
                        self.option_symbol,
                        mins_to_expiry,
                    )
                    return []

            if self._position_verify_empty_count < self._MIN_VERIFY_EMPTY_CYCLES:
                self.logger.warning(
                    "[%s] POSITION VERIFY: not found (%d/%d consecutive) — "
                    "waiting for confirmation, not closing",
                    self.option_symbol,
                    self._position_verify_empty_count,
                    self._MIN_VERIFY_EMPTY_CYCLES,
                )
                return []

            self.logger.warning(
                "[%s] POSITION VERIFY: not found on exchange (%d consecutive cycles) — "
                "log only (verify does not close)",
                self.option_symbol,
                self._position_verify_empty_count,
            )
            return []

        except Exception as e:
            self._position_verify_failures += 1
            self.logger.warning(
                "[%s] Position verify fetch_positions failed (%d/%d): %s",
                self.option_symbol,
                self._position_verify_failures,
                self._MAX_VERIFY_FAILURES,
                e,
            )
            if self._position_verify_failures >= self._MAX_VERIFY_FAILURES:
                self.logger.error(
                    "[%s] POSITION VERIFY: %d consecutive failures — log only (verify does not close)",
                    self.option_symbol,
                    self._position_verify_failures,
                )
                return []
            return None

    async def _handle_position_gone(self, reason: str) -> list[Signal]:
        """Handle a position that no longer exists on exchange."""
        is_expiry = False
        if self.expiry_dt:
            time_past_expiry = (
                datetime.now(timezone.utc) - self.expiry_dt
            ).total_seconds()
            is_expiry = time_past_expiry >= 0

        # Compute exit premium FIRST so the label can use it for ITM/OTM split.
        exit_premium = self._last_known_premium
        if exit_premium <= 0:
            exit_premium = self.entry_premium * 0.5 if self.entry_premium > 0 else 0.0

        if is_expiry and reason == "EXPIRED_TICKER_FAIL":
            exit_premium = 0.0  # ticker failed at expiry → assume worthless

        # GPFC #76/#79: specific lowercase labels instead of catch-all GONE/EXPIRY.
        if reason == "TICKER_FAIL_REPEATED":
            exit_reason = "ticker_dropout"
        elif is_expiry:
            # ITM: settled with value. OTM: expired worthless.
            exit_reason = "expired_itm" if exit_premium > 0 else "expired_otm"
        else:
            # Position disappeared from exchange outside of expiry context.
            exit_reason = "reconcile_gone"
        exit_reason_detail = f"{exit_reason}_{reason}" if reason else exit_reason

        self.logger.info(
            "[%s] %s (%s) — exit_premium=$%.4f (last_known=$%.4f entry=$%.4f)",
            self.option_symbol,
            exit_reason,
            reason,
            exit_premium,
            self._last_known_premium,
            self.entry_premium,
        )

        pnl_pct = 0.0
        pnl_usd = 0.0
        if self.entry_premium > 0:
            pnl_pct = (exit_premium - self.entry_premium) / self.entry_premium * 100
            pnl_usd = self._calc_options_pnl(
                self.entry_premium, exit_premium, self._contracts
            )

        if self._db:
            try:
                from alpha.utils import iso_now

                open_trade = await self._db.get_open_trade(
                    pair=self.option_symbol or self.pair,
                    exchange="delta",
                    strategy="options_scalp",
                )
                if open_trade:
                    entry_price = float(
                        open_trade.get("entry_price", self.entry_premium)
                        or self.entry_premium
                    )
                    contracts = int(
                        open_trade.get("contracts")
                        or open_trade.get("amount")
                        or self._contracts
                    )
                    multiplier = self.CONTRACT_MULTIPLIER.get(self._base_asset, 0.01)
                    spot = self._last_spot_price or (
                        exit_premium * (200 if self._base_asset == "BTC" else 100)
                    )
                    calculated_fee = round(contracts * multiplier * spot * 0.000118, 8)

                    stored_entry_fee = float(open_trade.get("entry_fee") or 0)
                    entry_fee = (
                        stored_entry_fee
                        if 0 < stored_entry_fee <= 0.10
                        else calculated_fee
                    )
                    exit_fee = calculated_fee

                    gross_pnl = self._calc_options_pnl(
                        entry_price, exit_premium, contracts
                    )
                    net_pnl = gross_pnl - entry_fee - exit_fee
                    db_pnl_pct = (
                        (exit_premium - entry_price) / entry_price * 100
                        if entry_price > 0
                        else 0.0
                    )

                    peak_pnl_val = (
                        (
                            (self.highest_premium - self.entry_premium)
                            / self.entry_premium
                            * 100
                        )
                        if self.entry_premium > 0
                        else 0
                    )

                    await self._db.update_trade(
                        open_trade["id"],
                        {
                            "status": "closed",
                            "exit_price": exit_premium,
                            "closed_at": iso_now(),
                            "pnl": round(net_pnl, 8),
                            "net_pnl": round(net_pnl, 8),
                            "pnl_pct": round(db_pnl_pct, 4),
                            "gross_pnl": round(gross_pnl, 8),
                            "entry_fee": round(entry_fee, 8),
                            "exit_fee": round(exit_fee, 8),
                            "peak_pnl": round(peak_pnl_val, 4),
                            "reason": exit_reason_detail.lower(),
                            "exit_reason": exit_reason,
                            "position_state": None,
                        },
                    )
                    pnl_pct = db_pnl_pct
                    pnl_usd = net_pnl
                    self.logger.info(
                        "[%s] Trade %s closed as %s — exit=$%.4f P&L=$%.4f (%.2f%%)",
                        self.option_symbol,
                        open_trade["id"],
                        exit_reason,
                        exit_premium,
                        net_pnl,
                        db_pnl_pct,
                    )
                else:
                    self.logger.info(
                        "[%s] No open trade found in DB — already closed",
                        self.option_symbol,
                    )
            except Exception:
                self.logger.exception(
                    "[%s] Failed to close trade as %s", self.option_symbol, exit_reason
                )

        try:
            alerts = getattr(self.executor, "alerts", None)
            if alerts is not None:
                pair_short = self._base_asset
                pnl_tag = (
                    f"+${pnl_usd:.4f}" if pnl_usd >= 0 else f"-${abs(pnl_usd):.4f}"
                )
                if is_expiry:
                    msg = (
                        f"\u23f0 {pair_short} option expired\n"
                        f"{self.option_side} ${self.strike_price:.0f} | "
                        f"${self.entry_premium:.4f} \u2192 ${exit_premium:.4f} "
                        f"({pnl_pct:+.1f}%) {pnl_tag}"
                    )
                else:
                    msg = (
                        f"\u2139\ufe0f {pair_short} option position gone\n"
                        f"{self.option_side} ${self.strike_price:.0f} | "
                        f"${self.entry_premium:.4f} \u2192 ${exit_premium:.4f} "
                        f"({pnl_pct:+.1f}%) {pnl_tag}\n"
                        f"Closed in DB, no action needed."
                    )
                await alerts.send_text(msg)
        except Exception:
            self.logger.debug(
                "[%s] Failed to send %s Telegram alert", self.option_symbol, exit_reason
            )

        await self._log_activity(
            f"options_{exit_reason.lower()}",
            f"{self.pair} — OPTIONS {exit_reason}: {reason} | "
            f"{self.option_side} strike=${self.strike_price:.0f} | "
            f"exit=${exit_premium:.4f} P&L={pnl_pct:+.1f}% ${pnl_usd:+.4f}",
            {
                "reason": reason,
                "exit_reason": exit_reason,
                "option_side": self.option_side,
                "strike": self.strike_price,
                "symbol": self.option_symbol,
                "exit_premium": exit_premium,
                "pnl_pct": round(pnl_pct, 2),
                "pnl_usd": round(pnl_usd, 4),
            },
        )

        if pnl_pct >= 0:
            self.hourly_wins += 1
        else:
            self.hourly_losses += 1
        self.hourly_pnl += pnl_usd

        await self._clear_dashboard_position(exit_reason_detail, pnl_pct, pnl_usd)

        self._position_gone_cooldown_until = (
            time.monotonic() + self._POSITION_GONE_COOLDOWN_SEC
        )
        self.logger.info(
            "[%s] %s cooldown: no new options entries for %ds",
            self.pair,
            exit_reason,
            self._POSITION_GONE_COOLDOWN_SEC,
        )

        # Build exit signal with proper exit_type for position-gone scenarios
        peak_pnl_pct = (
            ((self.highest_premium - self.entry_premium) / self.entry_premium * 100)
            if self.entry_premium > 0
            else 0
        )

        self.in_position = False
        OptionsScalpStrategy._global_in_position = False
        OptionsScalpStrategy._global_position_asset = None
        self.option_side = None
        self.option_symbol = None
        self.entry_premium = 0.0
        self.highest_premium = 0.0
        self._last_known_premium = 0.0
        self._trailing_active = False
        self._peak_trail_pending_ticks = 0
        self._locked_trail_floor_pct = 0.0
        self._last_trail_floor_pct_written = -1.0
        self._position_opened_at = None
        self.strike_price = 0.0
        self.expiry_dt = None
        self._consecutive_ticker_failures = 0
        self._position_verify_failures = 0
        self._position_verify_empty_count = 0
        self._last_state_write = 0.0
        self._is_squeeze_entry = False
        self._squeeze_breakout_time = None
        self._position_setup_type = None

        # Return Signal with exit_type so executor knows why we exited
        return [
            Signal(
                side="sell",
                price=exit_premium,
                amount=float(self._contracts) if self._contracts else 0.0,
                order_type="market",
                reason=f"Option {exit_reason_detail} — position closed externally",
                strategy=self.name,
                pair=self.option_symbol or self.pair,
                leverage=self.OPTIONS_LEVERAGE,
                position_type="long",
                reduce_only=True,
                exchange_id="delta",
                metadata={
                    "peak_pnl": round(peak_pnl_pct, 4),
                    "exit_type": exit_reason_detail,
                    "db_already_closed": True,
                },
            )
        ]

    async def _clear_dashboard_position(
        self,
        exit_type: str = "",
        pnl_pct: float = 0.0,
        pnl_usd: float = 0.0,
    ) -> None:
        """Write a final options_state update that clears all position fields."""
        if not self._db:
            return

        signal_strength = 0
        signal_side: str | None = None
        signal_reason = ""
        spot_price = 0.0

        if self._scalp and hasattr(self._scalp, "last_signal_state"):
            ss = self._scalp.last_signal_state
            if ss:
                signal_strength = ss.get("strength", 0)
                signal_side = ss.get("side")
                signal_reason = ss.get("reason", "")
                spot_price = ss.get("current_price", 0)

        state = {
            "spot_price": spot_price or None,
            "expiry": self._selected_expiry.isoformat()
            if self._selected_expiry
            else None,
            "expiry_label": None,
            "atm_strike": None,
            "call_premium": None,
            "put_premium": None,
            "signal_strength": signal_strength,
            "signal_side": signal_side,
            "signal_reason": signal_reason,
            "position_side": None,
            "position_strike": None,
            "position_symbol": None,
            "entry_premium": None,
            "current_premium": None,
            "pnl_pct": None,
            "pnl_usd": None,
            "trailing_active": False,
            "highest_premium": None,
            "last_exit_type": exit_type,
            "last_exit_pnl_pct": round(pnl_pct, 2),
            "last_exit_pnl_usd": round(pnl_usd, 4),
            "signals_panel": {
                "bb_width_pct": round(self._bb_width_pct, 3),
                "bb_width_threshold": (
                    self.SQUEEZE_BB_WIDTH_BTC
                    if self._base_asset == "BTC"
                    else self.SQUEEZE_BB_WIDTH_ETH
                ),
                # GPFC #62: keep the new fields populated post-exit so the
                # dashboard doesn't show stale values when we flip back to
                # scanning.
                "kc_width_pct": round(self._last_kc_width_pct, 3),
                "bb_kc_width_ratio": (
                    round(self._bb_width_pct / self._last_kc_width_pct, 3)
                    if self._last_kc_width_pct > 0 and self._bb_width_pct > 0
                    else None
                ),
                "regime": self._cached_regime,
                "momentum_60s_pct": round(self._underlying_momentum_pct(), 3),
                "momentum_freshness_ratio": round(
                    self._underlying_acceleration_ratio(), 3
                ),
                "momentum_acceleration_ratio": round(
                    self._underlying_acceleration_ratio(), 3
                ),
                "momentum_burst_threshold_pct": self.MOMENTUM_BURST_THRESHOLD_PCT,
                "squeeze_status": "WAITING",
                "bb_position": round(self._bb_position, 2),
                "direction_bias": "NEUTRAL",
                "premium_current_ask": None,
                "premium_cheap_threshold": None,
                "last_action": "SCANNING",
                "squeeze_duration_candles": 0,
                # In-position telemetry — flat now.
                "premium_velocity_pct": None,
                "underlying_vs_position_pct": None,
                "trail_armed": False,
                "trail_first_activation_pct": self.OPT_TRAIL_TIERS[0][0],
            },
            # Top-level squeeze fields (read directly by dashboard)
            "bb_width_pct": round(self._bb_width_pct, 3),
            "bb_width_threshold": (
                self.SQUEEZE_BB_WIDTH_BTC
                if self._base_asset == "BTC"
                else self.SQUEEZE_BB_WIDTH_ETH
            ),
            "squeeze_active": False,
            "bb_position": round(self._bb_position, 2),
            "direction_bias": "NEUTRAL",
            "premium_current_ask": None,
            "premium_cheap_threshold": None,
            "premium_lowest_ask": None,
            "premium_highest_ask": None,
            "last_squeeze_action": "SCANNING",
            "last_action_at": None,
            # Reset breakout state (GPFC #21)
            "breakout_state": "NONE",
            "breakout_direction": None,
            "breakout_velocity_pct": None,
            "breakout_confirmation_secs_remaining": None,
            "breakout_detected_at": None,
            "breakout_premium_at_detection": None,
        }

        try:
            await self._db.upsert_options_state(self.pair, state)
            self.logger.info(
                "[%s] Dashboard options state cleared (exit=%s pnl=%+.1f%%)",
                self.pair,
                exit_type,
                pnl_pct,
            )
        except Exception as e:
            self.logger.warning(
                "[%s] Failed to clear dashboard options state: %s", self.pair, e
            )

    # ==================================================================
    # CALLBACKS
    # ==================================================================

    def on_fill(self, signal: Signal, order: dict) -> None:
        """Track option position state on fill."""
        pending_side = signal.metadata.get("pending_side")
        if pending_side:
            fill_price = order.get("average") or order.get("price") or 0
            fill_price = float(fill_price) if fill_price else 0
            if not fill_price:
                self.logger.error(
                    "[%s] NO FILL PRICE from exchange — skipping on_fill", signal.pair
                )
                return
            self._position_premium_history.clear()
            self._last_30s_premium = None
            self._exit_in_progress = False
            self.in_position = True
            self._reentry_watch = None
            self._position_setup_type = signal.metadata.get("setup_type") or self._pending_entry_setup
            OptionsScalpStrategy._global_in_position = True
            OptionsScalpStrategy._global_position_asset = self._base_asset
            self.option_side = pending_side
            self.option_symbol = signal.pair
            self.entry_premium = fill_price
            self.entry_time = time.monotonic()
            self._position_opened_at = datetime.now(timezone.utc).isoformat()
            self.highest_premium = fill_price
            self._last_known_premium = fill_price
            self._trailing_active = False
            self._peak_trail_pending_ticks = 0
            self._consecutive_ticker_failures = 0
            self._opt_ratchet_floor = 0.0
            # GPFC #52: snapshot spot + 60s momentum at fill.
            self._spot_at_entry = float(self._last_spot_price or 0)
            self._entry_underlying_move = abs(self._underlying_momentum_pct())
            self._peak_timestamp = self.entry_time
            self._prev_highest_premium = fill_price
            self.strike_price = signal.metadata.get("strike", 0)
            self._contracts = int(signal.metadata.get("contracts", 1) or 1)
            expiry_str = signal.metadata.get("expiry")
            if expiry_str:
                self.expiry_dt = datetime.fromisoformat(expiry_str)
            self.logger.info(
                "[%s] OPTION FILLED — %s x%d strike=$%.0f premium=$%.4f exp=%s",
                self.option_symbol,
                self.option_side,
                self._contracts,
                self.strike_price,
                fill_price,
                self.expiry_dt.strftime("%b %d %H:%M") if self.expiry_dt else "?",
            )

            try:
                alerts = getattr(self.executor, "alerts", None)
                if alerts is not None:
                    import asyncio

                    _mult = self.CONTRACT_MULTIPLIER.get(self._base_asset, 0.01)
                    collateral = fill_price * self._contracts * _mult
                    _spot = self._last_spot_price or signal.metadata.get(
                        "spot_price", 0
                    )
                    _fee = (
                        round(self._contracts * _mult * _spot * 0.000118, 6)
                        if _spot
                        else 0
                    )
                    msg = (
                        f"\U0001f4e5 {self._base_asset} option opened\n"
                        f"{self.option_side.upper()} ${self.strike_price:.0f} | "
                        f"x{self._contracts} @ ${fill_price:.2f}\n"
                        f"Stake: ${collateral:.2f} | Fee: ${_fee:.4f}"
                    )
                    asyncio.get_event_loop().create_task(alerts.send_text(msg))
            except Exception:
                pass

            # If _execute_breakout_entry already wrote the DB row on the
            # signal path (the normal BB_SQUEEZE / MOMENTUM_BURST flow), skip
            # the insert here. This both prevents duplicate rows and protects
            # peak_pnl tracking (_db_trade_id is already set, so
            # _update_position_state_in_db starts updating the real row
            # immediately on the next tick).
            if self._db_trade_id:
                self.logger.info(
                    "[%s] on_fill: DB row already written by signal path "
                    "(id=%s) — skipping duplicate insert",
                    self.option_symbol,
                    self._db_trade_id,
                )
            else:
                # GPFC #74: if the signal path already built metadata, use it.
                # If not (e.g. on_fill fired before _execute_breakout_entry ran),
                # attempt to build metadata now so the DB row gets confidence.
                if not self._pending_entry_signals:
                    # GPFC #74 FIX: on_fill is sync — cannot await. Use the ticker
                    # cached by the most recent async tick (pre-entry fetch or
                    # _check_option_exit). If cache is cold, skip metadata rather
                    # than crashing.
                    _of_ticker: dict[str, Any] | None = self._last_option_ticker
                    if _of_ticker is None:
                        self.logger.warning(
                            "[%s] on_fill_fallback: no cached ticker — writing trade without metadata",
                            self.pair,
                        )
                    else:
                        try:
                            self._pending_entry_signals = self._build_entry_metadata(
                                _of_ticker,
                                self.option_side,
                                fill_price,
                                entry_path="on_fill_fallback",
                            )
                        except Exception as _me:
                            self.logger.warning(
                                "[%s] on_fill: metadata build failed — writing DB without confidence: %s",
                                self.option_symbol, _me,
                            )

                import asyncio as _aio_entry

                _aio_entry.get_event_loop().create_task(
                    self._write_entry_to_db(
                        fill_price,
                        self._contracts,
                        order,
                        signal,
                        option_symbol=self.option_symbol,
                        option_side=self.option_side,
                        strike_price=self.strike_price,
                        base_asset=self._base_asset,
                    )
                )
        else:
            exit_fill = float(order.get("average") or order.get("price") or 0)
            if not exit_fill:
                self.logger.error(
                    "[%s] NO EXIT FILL PRICE from exchange — skipping", signal.pair
                )
                return
            exit_type = signal.metadata.get("exit_type", "UNKNOWN")
            self.logger.info(
                "[%s] OPTION EXIT FILLED — %s closed @ $%.4f",
                self.option_symbol or self.pair,
                self.option_side,
                exit_fill,
            )

            _sym = self.option_symbol or self.pair
            _entry_prem = self.entry_premium
            _highest_prem = self.highest_premium
            _contracts = self._contracts
            _order = dict(order)

            if exit_fill > 0:
                import asyncio

                asyncio.get_event_loop().create_task(
                    self._close_option_trade_in_db(
                        exit_fill,
                        exit_type,
                        option_symbol=_sym,
                        entry_premium=_entry_prem,
                        highest_premium=_highest_prem,
                        contracts=_contracts,
                        order=_order,
                    )
                )

            self.in_position = False
            OptionsScalpStrategy._global_in_position = False
            OptionsScalpStrategy._global_position_asset = None
            self.option_side = None
            self.option_symbol = None
            self.entry_premium = 0.0
            self.highest_premium = 0.0
            self._trailing_active = False
            self._peak_trail_pending_ticks = 0
            self._position_opened_at = None
            self.strike_price = 0.0
            self.expiry_dt = None
            self._contracts = 1
            self._db_trade_id = None
            self._last_state_write = 0.0
            self._is_squeeze_entry = False
            self._squeeze_breakout_time = None
            self._position_setup_type = None
            self._position_premium_history.clear()
            self._last_30s_premium = None
            self._exit_in_progress = False

    def on_rejected(self, signal: Signal) -> None:
        """Handle rejected option orders."""
        pending_side = signal.metadata.get("pending_side")
        if pending_side:
            self.logger.warning(
                "[%s] Option entry REJECTED — not tracking",
                signal.pair,
            )
        elif signal.reduce_only and self.in_position:
            self.logger.warning(
                "[%s] Option EXIT rejected - keeping position state for next exit/reconcile cycle",
                self.option_symbol or signal.pair,
            )
            self._exit_in_progress = False
            self._consecutive_ticker_failures = 0
            self._position_verify_failures = 0
            return

    # ==================================================================
    # STATS
    # ==================================================================

    def reset_hourly_stats(self) -> dict[str, Any]:
        """Return stats and reset counters."""
        stats = {
            "wins": self.hourly_wins,
            "losses": self.hourly_losses,
            "pnl": self.hourly_pnl,
            "in_position": self.in_position,
            "option_side": self.option_side,
            "option_symbol": self.option_symbol,
        }
        self.hourly_wins = 0
        self.hourly_losses = 0
        self.hourly_pnl = 0.0
        return stats

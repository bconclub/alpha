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

Exit (GPFC #21 — SQUEEZE_RELEASE removed, replaced by BREAKOUT_FAKEOUT):
  1. OPT_SL:           -30% premium (always active, even Phase 1)
  2. OPT_ENTRY_DROP:   -8% in first 60s — bad entry, cut fast
  3. Ratchet/Trail:    lock profit at tiers, trail at +8%, TP at +30%
  4. EXPIRY_GUARD:     < 30 min → always exit; < 2h + pnl < +10% → exit
  - Progressive SL for stale trades after squeeze hold time (GPFC #23):
      ETH: 5m → -10%, 8m → -5%, 12m → OPT_STALE check (starts at 25m post-entry)
      BTC: 8m → -15%, 12m → -10%, 18m → OPT_STALE check (starts at 35m post-entry)
      If squeeze still active (bb_width < threshold) → STALE_HOLD, don't exit

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


class OptionsScalpStrategy(BaseStrategy):
    """Buy CALLs/PUTs during BB squeeze — buy cheap premium, hold through breakout."""

    name = StrategyName.OPTIONS_SCALP
    check_interval_sec = 5  # 5-second ticks

    # ── Class-level shared state ──────────────────────────────────────
    _global_in_position: bool = (
        False  # ONE option at a time across ALL assets (BTC+ETH)
    )
    _global_position_asset: str | None = None  # which asset holds the lock

    # ── Delta Exchange contract multiplier (options) ─────────────
    CONTRACT_MULTIPLIER: dict[str, float] = {"ETH": 0.01, "BTC": 0.001}

    # ── Option chain refresh ──────────────────────────────────────
    CHAIN_REFRESH_INTERVAL = 30 * 60  # Refresh every 30 min
    MIN_EXPIRY_HOURS = 1  # Must be 1+ hour to expiry
    EXPIRY_SWITCH_HOURS = (
        3.0  # Switch to next-day expiry when < 3h remain on current day
    )
    CLOSE_BEFORE_EXPIRY_HOURS = 0.5  # Close 30 min before expiry

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
    SQUEEZE_FILL_POLL_SEC = 30  # Poll every 30s during fill wait
    SQUEEZE_CHEAP_PERCENTILE = 0.25  # Buy bottom 25% of 30-min premium range
    SQUEEZE_HISTORY_MIN = 30  # Track premium history for 30 min
    # GPFC #23: Extended stale windows for squeeze entries (squeezes need time to resolve)
    SQUEEZE_NO_STALE_MIN_ETH = (
        15  # No stale SL for first 15 min after squeeze fill (ETH)
    )
    SQUEEZE_NO_STALE_MIN_BTC = (
        35  # No stale SL for first 35 min after squeeze fill (BTC)
    )
    # Dynamic confirmation window thresholds (GPFC #21) — UPDATED
    # velocity >= 0.3% → 20s, 0.15-0.3% → 40s, < 0.15% → 60s
    BREAKOUT_CONFIRM_HIGH_VELOCITY = 0.3  # >= 0.3% → 20s confirmation
    BREAKOUT_CONFIRM_MED_VELOCITY = 0.15  # 0.15-0.3% → 40s confirmation
    BREAKOUT_CONFIRM_MIN_VELOCITY = 0.0  # < 0.15% → 60s confirmation (weak move)
    BREAKOUT_CONFIRM_SEC_HIGH = 20  # Fast for strong moves
    BREAKOUT_CONFIRM_SEC_MED = 40  # Medium wait for medium moves
    BREAKOUT_CONFIRM_SEC_MAX = 60  # Max wait for weak moves
    BREAKOUT_FAKEOUT_DROP_PCT = 5.0  # Premium drop > 5% from breakout = fakeout
    BREAKOUT_OVERPRICED_RISE_PCT = 15.0  # Premium rise > 15% = overpriced, abort

    # ── Dynamic option sizing ──────────────────────────────────────
    # NEW: Fixed 20-30% capital allocation per trade (GPFC #20)
    # allocation_pct = 0.20 + (confidence * 0.10)  # 20% at conf=0.0, 30% at conf=1.0
    CAPITAL_PER_TRADE_MIN_PCT = 0.20  # 20% minimum per trade (low confidence)
    CAPITAL_PER_TRADE_MAX_PCT = 0.30  # 30% maximum per trade (high confidence)
    OPT_SURVIVAL_BALANCE = 20.0  # below this, cap allocation at 30%
    OPT_SURVIVAL_MAX_ALLOC = 30.0

    # ── Exit thresholds ────────────────
    TP_PREMIUM_GAIN_PCT = 30.0  # Take profit at +30% premium gain
    SL_PREMIUM_LOSS_PCT = 30.0  # Stop loss at -30% premium drop
    # Tiered trailing: start wide, tighten as profit grows
    OPT_TRAIL_TIERS: list[tuple[float, float]] = [
        (10.0, 8.0),  # +10% peak → 8% trail distance
        (20.0, 6.0),  # +20% peak → 6% trail
        (30.0, 5.0),  # +30% peak → 5% trail
        (50.0, 4.0),  # +50% peak → 4% trail
    ]
    PULLBACK_EXIT_PCT = 40.0  # Exit if lost 40% of peak gain
    PULLBACK_ACTIVATE_PCT = 8.0  # Pullback only fires after +8% peak
    DECAY_THRESHOLD_PCT = 3.0  # Exit if was +10%+ and faded to +3%

    # ── Stale SL tightening — progressive exit for stuck trades ─────
    STALE_MOVE_THRESHOLD = 5.0  # < 5% from entry = stale (not going anywhere)
    # ETH stale thresholds
    STALE_SL_5M_ETH = -10.0  # 5 min: SL → -10%
    STALE_SL_8M_ETH = -5.0  # 8 min: SL → -5%
    STALE_EXIT_MIN_ETH = 12  # 12 min: force OPT_STALE (but starts at 15m for squeeze)
    # BTC stale thresholds
    STALE_SL_8M_BTC = -15.0  # 8 min: SL → -15%
    STALE_SL_12M_BTC = -10.0  # 12 min: SL → -10%
    STALE_EXIT_MIN_BTC = 18  # 18 min: force OPT_STALE (but starts at 20m for squeeze)
    PHASE1_HANDS_OFF_SEC = 30  # Only SL fires in first 30s after fill

    # ── Expiry guard ────────
    EXPIRY_GUARD_HOURS = 2.0  # if expiry < 2h AND pnl < +10% → exit
    EXPIRY_GUARD_MIN_MIN = 30  # if expiry < 30 min → always exit regardless of P&L

    # ── Ratchet floor table: (peak_pct, locked_floor_pct) ────────────
    OPT_RATCHET_FLOOR_TABLE = [
        (0.0, -10.0),  # 0% or no peak → floor at -10% (safety net)
        (3.0, -10.0),  # +3% peak → floor at -10%  ← BREATHING ROOM
        (5.0, -5.0),   # +5% peak → floor at -5%   ← BREATHING ROOM
        (8.0, 0.0),    # +8% peak → breakeven      ← WAS +2%, now 0%
        (15.0, 5.0),   # +15% peak → +5%
        (25.0, 10.0),  # +25% peak → +10%
        (40.0, 20.0),  # +40% peak → +20%
        (60.0, 35.0),  # +60% peak → +35%
    ]

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

        # Cooldowns
        self._position_gone_cooldown_until: float = 0.0
        self._POSITION_GONE_COOLDOWN_SEC = 60
        self._no_fill_cooldown_until: float = 0.0

        # DB trade ID
        self._db_trade_id: int | None = None

        # Regime skip logging throttle
        self._last_regime_log: float = 0.0
        self._current_regime: str | None = None

        # Position verification
        self._position_verify_tick: int = 0
        self._position_verify_failures: int = 0
        self._MAX_VERIFY_FAILURES = 10

        # Ratchet profit floor
        self._opt_ratchet_floor: float = -999.0  # Sentinel value indicating "not set"

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

        # Dashboard chain panel cached state
        self._cached_candle_momentum: dict | None = None
        self._cached_bot_state: str = "scanning"
        self._cached_target_strike: float | None = None

        # ── Dashboard signals panel state ─────────────────────────
        self._squeeze_status: str = "WAITING"  # ACTIVE / WAITING
        self._bb_width_pct: float = 0.0  # Current BB width %
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
        self._MOMENTUM_CHECK_WINDOW_SEC = 60.0  # Look back 60s for momentum
        self._MOMENTUM_THRESHOLD_PCT = 0.1  # Min 0.1% momentum to ride

        # ── Caching for squeeze detection ─────────────────────────
        # Cache OHLCV data to avoid refetching within same scan tick
        self._cached_ohlcv: list[list[float]] | None = None
        self._cached_ohlcv_time: float = 0.0
        self._OHLCV_CACHE_SEC = 25  # Cache valid for 25 seconds


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

    # ==================================================================
    # LIFECYCLE
    # ==================================================================

    async def on_start(self) -> None:
        """Load option markets on startup + restore position state from DB."""
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
        _no_stale = (
            self.SQUEEZE_NO_STALE_MIN_BTC
            if self._base_asset == "BTC"
            else self.SQUEEZE_NO_STALE_MIN_ETH
        )
        self.logger.info(
            "[%s] OPTIONS SCALP ACTIVE — BB_SQUEEZE strategy (GPFC #23) | "
            "BB_width<%.1f%% KC_squeeze fill_wait=%ds "
            "TP=%d%% SL=%d%% Trail=%d%%/%d%% Pullback=%d%% Decay=%d%% "
            "NoStale=%dm StaleCheck=%dm Phase1=%ds Alloc=%s%s",
            self.pair,
            _bb_w,
            self.SQUEEZE_FILL_WAIT_SEC,
            int(self.TP_PREMIUM_GAIN_PCT),
            int(self.SL_PREMIUM_LOSS_PCT),
            int(self.OPT_TRAIL_TIERS[0][0]),
            int(self.OPT_TRAIL_TIERS[0][1]),
            int(self.PULLBACK_EXIT_PCT),
            int(self.DECAY_THRESHOLD_PCT),
            _no_stale,
            self.STALE_EXIT_MIN_BTC
            if self._base_asset == "BTC"
            else self.STALE_EXIT_MIN_ETH,
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
                self.in_position = True
                OptionsScalpStrategy._global_in_position = True
                OptionsScalpStrategy._global_position_asset = self._base_asset
                self.option_symbol = trade_pair
                self.entry_premium = trade.get("entry_price", 0)
                self.entry_time = time.monotonic()
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

                # Restore ratchet floor based on recovered highest_premium
                if self.entry_premium > 0:
                    restored_peak_pct = (
                        (self.highest_premium - self.entry_premium)
                        / self.entry_premium
                        * 100
                    )
                    self._update_opt_ratchet_floor(restored_peak_pct)

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
                current_bid = (
                    ticker.get("bid") or ticker.get("last") or self.entry_premium
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
                        raw_call_ask = float(t.get("ask") or t.get("last") or 0)
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
                        raw_put_ask = float(t.get("ask") or t.get("last") or 0)
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
                    current_prem = ticker.get("last") or ticker.get("bid") or None
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

        # ── Signals panel state ──
        signals_panel = {
            "bb_width_pct": round(self._bb_width_pct, 3),
            "bb_width_threshold": (
                self.SQUEEZE_BB_WIDTH_BTC
                if self._base_asset == "BTC"
                else self.SQUEEZE_BB_WIDTH_ETH
            ),
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
            # Top-level squeeze fields (read directly by dashboard)
            "bb_width_pct": round(self._bb_width_pct, 3),
            "bb_width_threshold": (
                self.SQUEEZE_BB_WIDTH_BTC
                if self._base_asset == "BTC"
                else self.SQUEEZE_BB_WIDTH_ETH
            ),
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

        # Pre-compute bot state BEFORE dashboard write so timers are fresh
        self._precompute_bot_state()

        # Write dashboard state every 30 seconds
        await self._write_dashboard_state()

        # In position: manage exit
        if self.in_position:
            self._cached_bot_state = "in_position"

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
        if OptionsScalpStrategy._global_in_position and not self.in_position:
            if self._tick_count % 6 == 0:
                self.logger.info(
                    "[%s] OPTIONS GLOBAL_LOCK — %s has an open option",
                    self.pair,
                    OptionsScalpStrategy._global_position_asset or "another asset",
                )
            self._cached_bot_state = "blocked:other_asset_in_position"
            return []

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

        option_type = "call" if direction == "UP" else "put"

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

        # Select strike
        strikes_to_try = [atm_strike]
        if self._base_asset == "BTC":
            otm_candidates = self._get_otm_candidates(atm_strike, option_type)
            if otm_candidates:
                strikes_to_try = [otm_candidates[0], atm_strike]

        selected_strike: float | None = None
        selected_symbol: str | None = None
        current_ask: float = 0.0

        for strike in strikes_to_try:
            sym = self._build_option_symbol(strike, option_type, self._selected_expiry)
            if sym is None:
                continue
            try:
                ticker = await self.options_exchange.fetch_ticker(sym)
                ask = float(ticker.get("ask") or ticker.get("last") or 0)
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
                current_ask = ask
                break

        if selected_strike is None or selected_symbol is None:
            self.logger.info(
                "[%s] SQUEEZE_BREAKOUT dir=%s: no affordable strike — skip",
                self.pair,
                direction,
            )
            return

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
            current_ask = float(ticker.get("ask") or ticker.get("last") or 0)
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

        # GPFC #24: Window complete — check if premium is rising or stable (not falling)
        # Premium must be >= start premium (within 2% tolerance) to confirm
        CHANGE_TOLERANCE_PCT = 2.0  # Allow up to 2% drop (considered "stable")
        change_pct = (
            (current_ask - self._breakout_entry_ask) / self._breakout_entry_ask * 100
        )

        if change_pct < -CHANGE_TOLERANCE_PCT:
            # Premium fell during confirmation — fakeout
            self.logger.info(
                "[%s] BREAKOUT_FAKEOUT: premium falling during confirmation $%.4f → $%.4f (%.1f%%) — abort",
                self.pair,
                self._breakout_entry_ask,
                current_ask,
                change_pct,
            )
            await self._log_activity(
                "options_skip",
                f"{self.pair} — BREAKOUT_FAKEOUT: premium falling during confirmation "
                f"${self._breakout_entry_ask:.4f} → ${current_ask:.4f} ({change_pct:.1f}%) — abort",
                {
                    "direction": self._breakout_direction,
                    "ask": current_ask,
                    "entry_ask": self._breakout_entry_ask,
                    "change_pct": round(change_pct, 2),
                },
            )
            self._last_action = "BREAKOUT_FAKEOUT"
            self._last_action_at = time.time()
            self._breakout_state = "FAKEOUT"
            self._reset_breakout_state()
            return []

        # Premium rising or stable — CONFIRMED, enter now
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

        # Recalculate contracts at confirmed ask price
        opt_contracts = self._calculate_option_contracts(
            confirmed_ask, entry_confidence
        )
        if opt_contracts < 1:
            self.logger.info(
                "[%s] BREAKOUT_CONFIRMED: no affordable contracts at $%.4f — abort",
                self.pair,
                confirmed_ask,
            )
            self._reset_breakout_state()
            return []

        limit_price = confirmed_ask  # Enter at current market ask after confirmation

        # Get current price for logging/metadata
        current_price = self._last_spot_price
        atm_strike = self._cached_target_strike or selected_strike

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

        # Poll for fill up to 5 min, every 30s
        limit_filled = False
        fill_price = limit_price
        _filled_qty = 0.0
        polls = self.SQUEEZE_FILL_WAIT_SEC // self.SQUEEZE_FILL_POLL_SEC

        for _poll in range(polls):
            await asyncio.sleep(self.SQUEEZE_FILL_POLL_SEC)
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
        self._last_action = "SQUEEZE_FILL"
        self._last_action_at = time.time()

        self.logger.info(
            "[%s] BREAKOUT_FILL: dir=%s premium=$%.4f",
            self.pair,
            self._breakout_direction,
            premium,
        )

        # SET POSITION STATE
        self.in_position = True
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
        self._is_squeeze_entry = True
        self._squeeze_breakout_time = time.monotonic()
        if self._selected_expiry:
            self.expiry_dt = self._selected_expiry

        self.logger.info(
            "[%s] POSITION LOCKED — %s x%d @ $%.4f (breakout confirmed, no stale for %dm)",
            self.pair,
            option_type.upper(),
            opt_contracts,
            fill_price,
            self.SQUEEZE_NO_STALE_MIN_BTC
            if self._base_asset == "BTC"
            else self.SQUEEZE_NO_STALE_MIN_ETH,
        )

        self._entry_context = (
            f"BB_SQUEEZE_BREAKOUT dir={self._breakout_direction} BB_width={bb_width_pct:.3f}% "
            f"ask=${premium:.4f} conf={entry_confidence:.2f}"
        )

        expiry_str = self._selected_expiry.strftime("%b %d %H:%M")
        strike_label = "ATM" if selected_strike == atm_strike else "OTM"

        await self._log_activity(
            "options_entry",
            f"{self.pair} — OPTIONS: {option_type.upper()} {strike_label} ${selected_strike:.0f} | "
            f"premium=${premium:.4f} | expiry={expiry_str} | BREAKOUT dir={self._breakout_direction}",
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
                "setup_type": "BB_SQUEEZE_BREAKOUT",
                "contracts": opt_contracts,
                "bb_width_pct": round(bb_width_pct, 4),
                "confidence": round(entry_confidence, 3),
                "breakout_direction": self._breakout_direction,
            },
        )

        self._reset_breakout_state()

        return self._build_entry_signal(
            option_type=option_type,
            selected_symbol=selected_symbol,
            selected_strike=selected_strike,
            premium=premium,
            strength=0,
            signals_str=f"BB_SQUEEZE_BREAKOUT dir={self._breakout_direction} width={bb_width_pct:.3f}%",
            current_price=current_price,
            setup_type="BB_SQUEEZE_BREAKOUT",
            expiry_str=expiry_str,
            strike_label=strike_label,
            contracts=opt_contracts,
            confidence=entry_confidence,
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
                    "strike": selected_strike,
                    "strike_label": strike_label,
                    "expiry": self._selected_expiry.isoformat()
                    if self._selected_expiry
                    else "",
                    "underlying_price": current_price,
                    "underlying_pair": self.pair,
                    "tp_price": premium * (1 + self.TP_PREMIUM_GAIN_PCT / 100),
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
    # RATCHET FLOOR
    # ==================================================================

    def _update_opt_ratchet_floor(self, pnl_pct: float) -> None:
        """Ratchet profit floor — one-way lock based on premium peak."""
        for threshold, floor in self.OPT_RATCHET_FLOOR_TABLE:
            if pnl_pct >= threshold and floor > self._opt_ratchet_floor:
                self.logger.info(
                    "[%s] RATCHET FLOOR ↑ pnl +%.1f%% ≥ %+.0f%% → floor locked at +%.1f%%",
                    self.option_symbol,
                    pnl_pct,
                    threshold,
                    floor,
                )
                self._opt_ratchet_floor = floor

    # ==================================================================
    # GPFC #22 Part 2: Let Winners Ride — Momentum Check
    # ==================================================================

    def _update_momentum_history(self, current_price: float) -> None:
        """Track price history for momentum calculations."""
        now = time.monotonic()
        self._momentum_price_history.append((now, current_price))

    def _should_ride_momentum(self, current_pnl_pct: float) -> bool:
        """Check if we should skip exit and ride the momentum.

        Returns True if:
        - Current P&L is positive (we're winning)
        - Underlying price momentum in position direction > 0.1% over last 60s

        Hard override: Always exit if peak > +50% AND pullback > 60% of peak gain
        """
        if current_pnl_pct <= 0:
            return False  # Only ride momentum when profitable

        if len(self._momentum_price_history) < 2:
            return False  # Not enough data

        now = time.monotonic()
        cutoff = now - self._MOMENTUM_CHECK_WINDOW_SEC

        # Find price from ~60s ago
        old_price = None
        for t, price in reversed(self._momentum_price_history):
            if t <= cutoff:
                old_price = price
                break

        if old_price is None or old_price <= 0:
            return False

        # Get current price
        current_price = self._momentum_price_history[-1][1]

        # Calculate momentum %
        momentum_pct = (current_price - old_price) / old_price * 100

        # Check if momentum is in our favor
        # For CALL: positive momentum is good
        # For PUT: negative momentum is good
        if self.option_side == "call":
            momentum_favorable = momentum_pct >= self._MOMENTUM_THRESHOLD_PCT
        elif self.option_side == "put":
            momentum_favorable = momentum_pct <= -self._MOMENTUM_THRESHOLD_PCT
        else:
            return False

        if momentum_favorable:
            self.logger.debug(
                "[%s] RIDE_MOMENTUM check: momentum=%+.2f%% threshold=%.2f%% — RIDING",
                self.option_symbol,
                momentum_pct,
                self._MOMENTUM_THRESHOLD_PCT,
            )

        return momentum_favorable

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
            current_premium = ticker.get("last") or ticker.get("bid") or 0
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
                return await self._do_option_exit(0, -100.0, "EXPIRED_WORTHLESS")
            return []

        # GPFC #22 Part 2: Update momentum history with spot price
        try:
            if self.futures_exchange:
                spot_ticker = await self.futures_exchange.fetch_ticker(self.pair)
                spot_price = spot_ticker.get("last") or 0
                if spot_price > 0:
                    self._last_spot_price = spot_price
                    self._update_momentum_history(spot_price)
        except Exception:
            pass  # Non-critical, continue without momentum data

        # Track peak premium
        self.highest_premium = max(self.highest_premium, current_premium)

        # Update ratchet floor
        self._update_opt_ratchet_floor(
            (self.highest_premium - self.entry_premium) / self.entry_premium * 100
            if self.entry_premium > 0
            else 0
        )

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

        hold_seconds = time.monotonic() - self.entry_time
        in_phase1 = hold_seconds < self.PHASE1_HANDS_OFF_SEC

        # Heartbeat (every ~60s)
        if self._tick_count % 6 == 0:
            trail_tag = " [TRAILING]" if self._trailing_active else ""
            phase_tag = " [PHASE1]" if in_phase1 else ""
            squeeze_tag = " [SQUEEZE]" if self._is_squeeze_entry else ""
            self.logger.info(
                "[%s] %s | $%.4f → $%.4f (%+.1f%%) | peak=$%.4f (+%.1f%%) | %ds%s%s%s",
                self.option_symbol,
                self.option_side,
                self.entry_premium,
                current_premium,
                premium_change_pct,
                self.highest_premium,
                peak_pnl_pct,
                int(hold_seconds),
                trail_tag,
                phase_tag,
                squeeze_tag,
            )

        # ── 1. EXPIRY GUARD ───────────
        if self.expiry_dt:
            time_to_expiry = (
                self.expiry_dt - datetime.now(timezone.utc)
            ).total_seconds()
            mins_to_expiry = time_to_expiry / 60
            if mins_to_expiry <= self.EXPIRY_GUARD_MIN_MIN:
                self.logger.info(
                    "[%s] EXPIRY_GUARD: %s expires in %.0fm < %dm → EXIT regardless of P&L",
                    self.option_symbol,
                    self.option_symbol,
                    mins_to_expiry,
                    self.EXPIRY_GUARD_MIN_MIN,
                )
                return await self._do_option_exit(
                    current_premium, premium_change_pct, "EXPIRY_GUARD"
                )
            elif (
                mins_to_expiry <= self.EXPIRY_GUARD_HOURS * 60
                and premium_change_pct < 10.0
            ):
                self.logger.info(
                    "[%s] EXPIRY_GUARD: %s expires in %.0fm, pnl=%.1f%% < +10%% → EXIT",
                    self.option_symbol,
                    self.option_symbol,
                    mins_to_expiry,
                    premium_change_pct,
                )
                return await self._do_option_exit(
                    current_premium, premium_change_pct, "EXPIRY_GUARD"
                )

        # ── Ratchet floor update ─────
        self._update_opt_ratchet_floor(peak_pnl_pct)

        # ── 2. ENTRY DROP ──
        if hold_seconds <= 60 and premium_change_pct <= -8.0:
            self.logger.info(
                "[%s] OPT_ENTRY_DROP: entry=$%.4f current=$%.4f drop=%.1f%% after %.0fs",
                self.option_symbol,
                self.entry_premium,
                current_premium,
                premium_change_pct,
                hold_seconds,
            )
            return await self._do_option_exit(
                current_premium, premium_change_pct, "OPT_ENTRY_DROP"
            )

        # ── 3. RATCHET EXIT ─────────
        if (
            self._opt_ratchet_floor > -900.0  # Floor was actually set (not sentinel)
            and premium_change_pct < self._opt_ratchet_floor
        ):
            # GPFC #22 Part 2: Check momentum before firing RATCHET exit — let winners ride
            if self._should_ride_momentum(premium_change_pct):
                self.logger.info(
                    "[%s] RIDE_MOMENTUM: pnl=+%.1f%% ratchet_floor=%+.1f%% — skipping RATCHET, holding",
                    self.option_symbol,
                    premium_change_pct,
                    self._opt_ratchet_floor,
                )
            else:
                self.logger.info(
                    "[%s] OPT_RATCHET — pnl +%.1f%% fell below floor +%.1f%%",
                    self.option_symbol,
                    premium_change_pct,
                    self._opt_ratchet_floor,
                )
                return await self._do_option_exit(
                    current_premium, premium_change_pct, "OPT_RATCHET"
                )

        # ── 4. STOP LOSS ────────────
        if premium_change_pct <= -self.SL_PREMIUM_LOSS_PCT:
            self.logger.info(
                "[%s] OPTION SL — premium %+.1f%% ($%.4f → $%.4f)",
                self.option_symbol,
                premium_change_pct,
                self.entry_premium,
                current_premium,
            )
            return await self._do_option_exit(
                current_premium, premium_change_pct, "OPT_SL"
            )

        # ── Phase 1 hands-off ─────
        if in_phase1:
            return []

        # ── 5. PEAK TRAIL ───────────
        if peak_pnl_pct >= 8.0:
            trail_floor_pct = peak_pnl_pct * 0.65
            if premium_change_pct <= trail_floor_pct:
                multiplier = self.CONTRACT_MULTIPLIER.get(self._base_asset, 0.01)
                spot = self._last_spot_price or (
                    current_premium * (200 if self._base_asset == "BTC" else 100)
                )
                estimated_fees = 2 * (self._contracts * multiplier * spot * 0.000118)
                gross_pnl = self._calc_options_pnl(
                    self.entry_premium, current_premium, self._contracts
                )

                if peak_pnl_pct < 15.0 and gross_pnl < estimated_fees * 1.5:
                    self.logger.info(
                        "[%s] OPT_PEAK_TRAIL skipped — gross=$%.4f < fees*1.5=$%.4f (peak +%.1f%%)",
                        self.option_symbol,
                        gross_pnl,
                        estimated_fees * 1.5,
                        peak_pnl_pct,
                    )
                else:
                    self.logger.info(
                        "[%s] OPT_PEAK_TRAIL — peak +%.1f%%, floor +%.1f%%, now +%.1f%%",
                        self.option_symbol,
                        peak_pnl_pct,
                        trail_floor_pct,
                        premium_change_pct,
                    )
                    return await self._do_option_exit(
                        current_premium, premium_change_pct, "OPT_PEAK_TRAIL"
                    )

        # ── 6. TAKE PROFIT ──────────
        if premium_change_pct >= self.TP_PREMIUM_GAIN_PCT:
            self.logger.info(
                "[%s] OPTION TP — premium +%.1f%% ($%.4f → $%.4f)",
                self.option_symbol,
                premium_change_pct,
                self.entry_premium,
                current_premium,
            )
            return await self._do_option_exit(current_premium, premium_change_pct, "TP")

        # ── 7. TIERED TRAILING ──────
        trail_distance = 0.0
        for tier_pct, tier_dist in self.OPT_TRAIL_TIERS:
            if peak_pnl_pct >= tier_pct:
                trail_distance = tier_dist
        if trail_distance > 0 and not self._trailing_active:
            self._trailing_active = True
            self.logger.info(
                "[%s] OPTION TRAIL ON at +%.1f%% (distance=%.1f%%)",
                self.option_symbol,
                premium_change_pct,
                trail_distance,
            )

        # ── 8. TRAILING STOP ────────
        if self._trailing_active and trail_distance > 0:
            trail_floor = self.highest_premium * (1 - trail_distance / 100)
            if current_premium <= trail_floor:
                final_pct = (
                    (current_premium - self.entry_premium) / self.entry_premium * 100
                )
                self.logger.info(
                    "[%s] OPTION TRAIL HIT — peak=$%.4f floor=$%.4f now=$%.4f (dist=%.1f%%)",
                    self.option_symbol,
                    self.highest_premium,
                    trail_floor,
                    current_premium,
                    trail_distance,
                )
                return await self._do_option_exit(
                    current_premium, final_pct, "OPT_TRAIL"
                )

        # ── 9. PULLBACK ─────────────
        if peak_pnl_pct >= self.PULLBACK_ACTIVATE_PCT and premium_change_pct > 0:
            pct_of_peak_lost = (
                (peak_pnl_pct - premium_change_pct) / peak_pnl_pct
            ) * 100
            if pct_of_peak_lost >= self.PULLBACK_EXIT_PCT:
                # GPFC #22 Part 2: Check momentum before firing PULLBACK — let winners ride
                # Hard override: always exit if peak > +50% AND pullback > 60% of peak gain
                hard_override = peak_pnl_pct > 50.0 and pct_of_peak_lost > 60.0
                if not hard_override and self._should_ride_momentum(premium_change_pct):
                    self.logger.info(
                        "[%s] RIDE_MOMENTUM: pnl=+%.1f%% peak=+%.1f%% lost=%.0f%% — skipping PULLBACK, holding",
                        self.option_symbol,
                        premium_change_pct,
                        peak_pnl_pct,
                        pct_of_peak_lost,
                    )
                else:
                    if hard_override:
                        self.logger.info(
                            "[%s] OPTION PULLBACK (HARD OVERRIDE) — peak +%.1f%% now +%.1f%% (lost %.0f%% of gain)",
                            self.option_symbol,
                            peak_pnl_pct,
                            premium_change_pct,
                            pct_of_peak_lost,
                        )
                    else:
                        self.logger.info(
                            "[%s] OPTION PULLBACK — peak +%.1f%% now +%.1f%% (lost %.0f%% of gain)",
                            self.option_symbol,
                            peak_pnl_pct,
                            premium_change_pct,
                            pct_of_peak_lost,
                        )
                    return await self._do_option_exit(
                        current_premium, premium_change_pct, "PULLBACK"
                    )

        # ── 10. DECAY ───────────────
        if peak_pnl_pct >= 10.0 and premium_change_pct <= self.DECAY_THRESHOLD_PCT:
            self.logger.info(
                "[%s] OPTION DECAY — peak +%.1f%% faded to +%.1f%% (threshold +%.1f%%)",
                self.option_symbol,
                peak_pnl_pct,
                premium_change_pct,
                self.DECAY_THRESHOLD_PCT,
            )
            return await self._do_option_exit(
                current_premium, premium_change_pct, "DECAY"
            )

        # ── 11. PROGRESSIVE SL TIGHTENING (stale trade protection) ────
        # GPFC #23: Smarter stale exit for squeeze setups
        abs_move_pct = abs(premium_change_pct)

        # Determine no-stale threshold based on asset (extended for squeeze entries)
        no_stale_threshold = (
            self.SQUEEZE_NO_STALE_MIN_BTC * 60
            if self._is_squeeze_entry and self._base_asset == "BTC"
            else self.SQUEEZE_NO_STALE_MIN_ETH * 60
            if self._is_squeeze_entry
            else 0  # non-squeeze entries (shouldn't happen now)
        )

        is_stale = (
            abs_move_pct < self.STALE_MOVE_THRESHOLD
            and peak_pnl_pct < 10.0
            and premium_change_pct <= 0.0
            and hold_seconds > no_stale_threshold  # Only after no-stale period
        )

        if is_stale:
            hold_min = hold_seconds / 60
            _is_btc = self._base_asset == "BTC"

            # GPFC #23: Before firing OPT_STALE, check if squeeze is still active
            squeeze_still_active = False
            if self._is_squeeze_entry:
                squeeze_result = await self._detect_squeeze()
                if squeeze_result:
                    is_squeeze, bb_width_pct, *_ = squeeze_result
                    bb_width_threshold = (
                        self.SQUEEZE_BB_WIDTH_BTC
                        if self._base_asset == "BTC"
                        else self.SQUEEZE_BB_WIDTH_ETH
                    )
                    # Squeeze is "still active" if BB width is still tight (< threshold)
                    squeeze_still_active = bb_width_pct < bb_width_threshold
                    if squeeze_still_active:
                        self.logger.info(
                            "[%s] STALE_HOLD: squeeze still forming (bb_width=%.2f%% < %.1f%%), "
                            "keeping position — %.0fm held",
                            self.option_symbol,
                            bb_width_pct,
                            bb_width_threshold,
                            hold_min,
                        )

            # After 30 minutes, never let squeeze still_active block exits
            if hold_min >= 30:
                if squeeze_still_active:
                    self.logger.info(
                        "[%s] SQUEEZE_TIMEOUT: forcing squeeze_still_active=False after %.0fm",
                        self.option_symbol,
                        hold_min,
                    )
                squeeze_still_active = False

            if _is_btc:
                if hold_min >= self.STALE_EXIT_MIN_BTC:
                    if squeeze_still_active:
                        # Squeeze still active → don't exit
                        pass
                    else:
                        self.logger.info(
                            "[%s] OPT_STALE: %.0fm no movement (move=%.1f%%, peak=%.1f%%) → EXIT",
                            self.option_symbol,
                            hold_min,
                            premium_change_pct,
                            peak_pnl_pct,
                        )
                        return await self._do_option_exit(
                            current_premium, premium_change_pct, "OPT_STALE"
                        )
                elif hold_min >= 12.0 and premium_change_pct < self.STALE_SL_12M_BTC:
                    if not squeeze_still_active:
                        self.logger.info(
                            "[%s] SL_TIGHTEN: 12m stale, SL → %.0f%% (now %.1f%%)",
                            self.option_symbol,
                            self.STALE_SL_12M_BTC,
                            premium_change_pct,
                        )
                        return await self._do_option_exit(
                            current_premium, premium_change_pct, "OPT_STALE"
                        )
                elif hold_min >= 8.0 and premium_change_pct < self.STALE_SL_8M_BTC:
                    if not squeeze_still_active:
                        self.logger.info(
                            "[%s] SL_TIGHTEN: 8m stale, SL → %.0f%% (now %.1f%%)",
                            self.option_symbol,
                            self.STALE_SL_8M_BTC,
                            premium_change_pct,
                        )
                        return await self._do_option_exit(
                            current_premium, premium_change_pct, "OPT_STALE"
                        )
            else:
                if hold_min >= self.STALE_EXIT_MIN_ETH:
                    if squeeze_still_active:
                        # Squeeze still active → don't exit
                        pass
                    else:
                        self.logger.info(
                            "[%s] OPT_STALE: %.0fm no movement (move=%.1f%%, peak=%.1f%%) → EXIT",
                            self.option_symbol,
                            hold_min,
                            premium_change_pct,
                            peak_pnl_pct,
                        )
                        return await self._do_option_exit(
                            current_premium, premium_change_pct, "OPT_STALE"
                        )
                elif hold_min >= 8.0 and premium_change_pct < self.STALE_SL_8M_ETH:
                    if not squeeze_still_active:
                        self.logger.info(
                            "[%s] SL_TIGHTEN: 8m stale, SL → %.0f%% (now %.1f%%)",
                            self.option_symbol,
                            self.STALE_SL_8M_ETH,
                            premium_change_pct,
                        )
                        return await self._do_option_exit(
                            current_premium, premium_change_pct, "OPT_STALE"
                        )
                elif hold_min >= 5.0 and premium_change_pct < self.STALE_SL_5M_ETH:
                    if not squeeze_still_active:
                        self.logger.info(
                            "[%s] SL_TIGHTEN: 5m stale, SL → %.0f%% (now %.1f%%)",
                            self.option_symbol,
                            self.STALE_SL_5M_ETH,
                            premium_change_pct,
                        )
                        return await self._do_option_exit(
                            current_premium, premium_change_pct, "OPT_STALE"
                        )

        # ── 12. SIGNAL REVERSAL ─────
        if self._scalp and hasattr(self._scalp, "last_signal_state"):
            ss = self._scalp.last_signal_state
            if ss:
                new_side = ss.get("side")
                new_strength = ss.get("strength", 0)
                signal_age = time.monotonic() - ss.get("timestamp", 0)

                if (
                    signal_age < 30  # SIGNAL_STALENESS_SEC
                    and new_strength >= 4  # MIN_SIGNAL_STRENGTH
                    and new_side is not None
                ):
                    is_reversal = (
                        self.option_side == "call" and new_side == "short"
                    ) or (self.option_side == "put" and new_side == "long")
                    if is_reversal:
                        self.logger.info(
                            "[%s] SIGNAL REVERSAL — %s → opposite %s at %+.1f%%",
                            self.option_symbol,
                            self.option_side,
                            new_side,
                            premium_change_pct,
                        )
                        return await self._do_option_exit(
                            current_premium,
                            premium_change_pct,
                            "OPT_REVERSAL",
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
            mult = self.CONTRACT_MULTIPLIER.get(base_asset, 0.01)
            spot = self._last_spot_price or 0
            entry_fee = round(contracts * mult * spot * 0.000118, 8) if spot else 0

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
                "setup_type": "BB_SQUEEZE",
                "signals_fired": f"option_side={option_side} "
                + getattr(self, "_entry_context", ""),
                "opened_at": datetime.utcnow().isoformat() + "Z",
            }

            result = self.executor.db.client.table("trades").insert(row).execute()
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
                collateral = actual_fill * contracts / self.OPTIONS_LEVERAGE
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
                collateral = fill_price * contracts / self.OPTIONS_LEVERAGE
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

            from alpha.trade_executor import _extract_exit_reason

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
                    "exit_reason": _extract_exit_reason(exit_type),
                    "position_state": None,
                },
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

    async def _do_option_exit(
        self,
        current_premium: float,
        pnl_pct: float,
        exit_type: str,
    ) -> list[Signal]:
        """Build exit signal for option position."""
        try:
            ticker = await self.options_exchange.fetch_ticker(self.option_symbol)
            live_bid = ticker.get("bid") or ticker.get("last") or 0
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

        self._opt_ratchet_floor = -999.0

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

        return [
            Signal(
                side="sell",
                price=current_premium,
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
                    return None

            now_utc = datetime.now(timezone.utc)
            if self.expiry_dt:
                mins_to_expiry = (self.expiry_dt - now_utc).total_seconds() / 60
                if mins_to_expiry <= self._EXPIRY_CLOSE_MINUTES:
                    self.logger.warning(
                        "[%s] POSITION VERIFY: not found, near expiry (%.1f min) — EXPIRY",
                        self.option_symbol,
                        mins_to_expiry,
                    )
                    return await self._handle_position_gone("VERIFY_EXPIRY")

            self.logger.warning(
                "[%s] POSITION VERIFY: not found on exchange — POSITION_GONE",
                self.option_symbol,
            )
            return await self._handle_position_gone("VERIFY_GONE")

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
                    "[%s] POSITION VERIFY: %d consecutive failures — forcing POSITION_GONE",
                    self.option_symbol,
                    self._position_verify_failures,
                )
                return await self._handle_position_gone("VERIFY_API_FAIL")
            return None

    async def _handle_position_gone(self, reason: str) -> list[Signal]:
        """Handle a position that no longer exists on exchange."""
        is_expiry = False
        if self.expiry_dt:
            time_past_expiry = (
                datetime.now(timezone.utc) - self.expiry_dt
            ).total_seconds()
            is_expiry = time_past_expiry >= 0

        exit_reason = "EXPIRY" if is_expiry else "POSITION_GONE"
        exit_reason_detail = f"{exit_reason}_{reason}" if reason else exit_reason

        exit_premium = self._last_known_premium
        if exit_premium <= 0:
            exit_premium = self.entry_premium * 0.5 if self.entry_premium > 0 else 0.0

        if is_expiry and reason == "EXPIRED_TICKER_FAIL":
            exit_premium = 0.0

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
        self._position_opened_at = None
        self.strike_price = 0.0
        self.expiry_dt = None
        self._consecutive_ticker_failures = 0
        self._position_verify_failures = 0
        self._last_state_write = 0.0
        self._is_squeeze_entry = False
        self._squeeze_breakout_time = None

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
                "squeeze_status": "WAITING",
                "bb_position": round(self._bb_position, 2),
                "direction_bias": "NEUTRAL",
                "premium_current_ask": None,
                "premium_cheap_threshold": None,
                "last_action": "SCANNING",
                "squeeze_duration_candles": 0,
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
            self.in_position = True
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
            self._consecutive_ticker_failures = 0
            self._opt_ratchet_floor = -999.0
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
            self._db_trade_id = None

            try:
                alerts = getattr(self.executor, "alerts", None)
                if alerts is not None:
                    import asyncio

                    collateral = fill_price * self._contracts / self.OPTIONS_LEVERAGE
                    _mult = self.CONTRACT_MULTIPLIER.get(self._base_asset, 0.01)
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
                        f"Collateral: ${collateral:.2f} | Fee: ${_fee:.4f}"
                    )
                    asyncio.get_event_loop().create_task(alerts.send_text(msg))
            except Exception:
                pass

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
            self._position_opened_at = None
            self.strike_price = 0.0
            self.expiry_dt = None
            self._contracts = 1
            self._db_trade_id = None
            self._last_state_write = 0.0
            self._is_squeeze_entry = False
            self._squeeze_breakout_time = None

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
                "[%s] Option EXIT rejected — clearing in_position (position likely closed externally)",
                self.option_symbol or signal.pair,
            )
            self.in_position = False
            OptionsScalpStrategy._global_in_position = False
            OptionsScalpStrategy._global_position_asset = None
            self.option_side = None
            self.option_symbol = None
            self.entry_premium = 0.0
            self.highest_premium = 0.0
            self._trailing_active = False
            self._position_opened_at = None
            self.strike_price = 0.0
            self.expiry_dt = None
            self._last_state_write = 0.0
            self._is_squeeze_entry = False
            self._squeeze_breakout_time = None

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

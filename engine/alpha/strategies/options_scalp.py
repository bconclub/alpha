"""Alpha Options Scalp — Buy CALLs/PUTs on strong momentum signals.

═══════════════════════════════════════════════════════════════
 OPTION ENTRY SIGNAL — ADAPTIVE FLOW (reads the market, not thresholds)
═══════════════════════════════════════════════════════════════

 1. REGIME GATE        CHOPPY blocked, all others allowed
 2. ADAPTIVE GATE      3 of 5 candles directional + cumulative move >= 2.0x
                       recent avg candle range (adapts to market noise)
                       + Volume confirmation: entry candles >= 1.5x avg volume
                       + Acceleration: recent candles bigger than earlier ones
                       + Floor: minimum 0.10% cum regardless
 3. UNDERLYING MOVE    Price must move >= 0.10% in last ~60s
 4. EXPIRY             Nearest expiry (today preferred, min 1h to expiry)
 5. STRIKE SELECTION   Highest OI within ATM + 1-2 OTM (liquidity = premium moves)
 6. PREMIUM SWEET SPOT Prefer $3-25 ETH / $50-500 BTC. Too cheap = illiquid skip.
                       Expensive = only enter on monster signal (3x noise + 2.5x vol)
 7. PREMIUM CHECK      Sample premium twice 5s apart (5s total wait)
                       Falling → SKIP. Not falling → place limit NOW at second ask
 8. LIMIT ENTRY        Place limit at pre-spike ask, wait 10s for fill
                       Filled → on (market proved the move). Not filled → PREMIUM_NO_FILL, 30s cooldown
                       Partial fill → keep filled qty, cancel residual
 9. PULLBACK WAIT      Wait up to 15s for 3% premium dip before buying

 COOLDOWNS:
   - Trade cooldown: 2 min between trades
   - Dead market: 10 min after exit with 0% peak
   - Position gone: 60s after position disappears
   - No fill: 30s after PREMIUM_NO_FILL (order placed but market didn't fill in 10s)

 SIZING:
   - 3+/5 candles directional → 50% allocation
   - BB_SQUEEZE → 60% factor on top
   - Survival mode: balance < $5 → max 5 contracts
   - BTC + ETH both enabled (50x leverage = tiny collateral)

═══════════════════════════════════════════════════════════════

Exit (4 ways out — we paid the premium, let it play):
  1. OPT_SL:         -30% premium (always active, even Phase 1)
  2. OPT_ENTRY_DROP: -8% in first 60s — bad entry, get out fast (Phase 1)
  3. Ratchet/Trail:  lock profit at (10→3, 15→7, 25→15, 40→25)%, trail at +8%, TP at +30%
  4. EXPIRY_GUARD:   < 30 min → always exit; < 2h + pnl < +10% → exit
  - Progressive SL for stale trades (peak < +10%, premium ≤ 0%, move < 5%):
      5 min: SL tightens to -10% | 8 min: SL tightens to -5% | 12 min: force OPT_STALE
  - Phase 1 (first 30s): only SL + ENTRY_DROP fire

Risk: Max loss = premium paid. No liquidation. Safest momentum play.
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
    """Buy CALLs/PUTs on momentum signals from the scalp strategy.

    Reads the scalp strategy's `last_signal_state` dict every 5 seconds.
    Enters on 2-of-4+ signals. Low brokerage, capped loss = premium paid.
    """

    name = StrategyName.OPTIONS_SCALP
    check_interval_sec = 5  # 5-second ticks (was 10 — catch fresh signals faster)

    # ── Class-level shared state ──────────────────────────────────────
    _global_in_position: bool = False  # ONE option at a time across ALL assets (BTC+ETH)
    _global_position_asset: str | None = None  # which asset holds the lock

    # ── Delta Exchange contract multiplier (options) ─────────────
    CONTRACT_MULTIPLIER: dict[str, float] = {"ETH": 0.01, "BTC": 0.001}

    # ── Option chain refresh ──────────────────────────────────────
    CHAIN_REFRESH_INTERVAL = 30 * 60     # Refresh every 30 min
    MIN_EXPIRY_HOURS = 1                 # Must be 1+ hour to expiry — prefer today's expiry (10-100x more volume)
    EXPIRY_SWITCH_HOURS = 3.0            # Switch to next-day expiry when < 3h remain on current day
    CLOSE_BEFORE_EXPIRY_HOURS = 0.5      # Close 30 min before expiry

    # ── Strike selection ──────────────────────────────────────────
    BTC_STRIKE_ROUND = 200               # BTC: nearest $200
    ETH_STRIKE_ROUND = 20                # ETH: nearest $20
    MAX_OTM_STRIKES = 1                  # ATM or 1 OTM only — further OTM is dead money

    # ── Premium limits ────────────────────────────────────────────
    OPTIONS_LEVERAGE = 50                # Delta options are 50x leveraged
    MIN_PREMIUM_USD = 5.00               # Skip strikes < $5 — too little delta, premium doesn't respond

    # ── Entry ─────────────────────────────────────────────────────
    MIN_SIGNAL_STRENGTH = 4              # 4-of-4 required (was 2 — need full conviction for options)
    SIGNAL_STALENESS_SEC = 30            # Signal must be < 30s old (was 15 — too tight with 5s check cycle)
    # Candle-based early-direction gate (3/5 candles required, adaptive threshold)
    CANDLE_MOM_STREAK = 3                # 3 of 5 candles must agree in direction
    CANDLE_MOM_LOOKBACK = 5              # check last 5 completed 1m candles (was 3)
    # ── Adaptive threshold — compare move to recent noise ─────────
    ADAPTIVE_CUM_MULTIPLIER = 2.0        # entry requires cum >= 2.0x avg candle range (was 2.5 — volume confirms quality)
    ADAPTIVE_CUM_FLOOR = 0.08            # absolute minimum cum% regardless of noise level (was 0.10 — blocked quiet markets)
    ADAPTIVE_RANGE_WINDOW = 20           # rolling window of candle ranges for noise baseline
    # ── Volume confirmation — no volume no trade ──────────────────
    VOLUME_CONFIRM_WINDOW = 20           # rolling window for avg volume baseline
    VOLUME_CONFIRM_MULTIPLIER = 1.2      # entry candles must have >= 1.2x avg volume (was 1.5 — too tight for options)
    VOLUME_CONFIRM_CANDLES = 3           # average volume of last 3 candles for entry check
    MIN_UNDERLYING_MOVE_PCT = 0.10       # underlying must move >= 0.10% in last 60s
    MIN_UNDERLYING_MOVE_SECS = 60        # lookback window for underlying move check
    OPT_RSI_CALL_MAX = 40               # calls only when RSI < 40 (oversold conviction)
    OPT_RSI_PUT_MIN = 60                # puts only when RSI > 60 (overbought conviction)

    # ── GPFC: Setup whitelist — only proven setups ──────────────
    ALLOWED_SETUPS = {"MOMENTUM_BURST", "BB_SQUEEZE"}  # the only profitable patterns
    # ── Premium sweet spot — prefer cheap, allow expensive only on strong signal ──
    PREMIUM_SWEET_SPOT: dict[str, tuple[float, float]] = {
        "ETH": (3.0, 25.0),   # $3-$25 sweet spot for ETH (was $15 — most ATM are $20+)
        "BTC": (50.0, 500.0), # $50-$500 sweet spot for BTC (was $300)
    }
    PREMIUM_EXPENSIVE_CUM_MULT = 3.0    # expensive premium requires cum >= 3x avg_range (was 4x)
    PREMIUM_EXPENSIVE_VOL_MULT = 2.0    # expensive premium requires vol >= 2.0x avg (was 2.5)

    # ── Dynamic option sizing ──────────────────────────────────────
    # Same pair allocation as futures so capital is balanced.
    OPT_PAIR_ALLOC_PCT: dict[str, float] = {
        "ETH": 60.0,
        "BTC": 50.0,
    }
    OPT_STRONG_ALLOC_PCT: dict[str, float] = {   # full alloc for strong signals
        "ETH": 60.0,
        "BTC": 50.0,
    }
    OPT_NORMAL_ALLOC_PCT: dict[str, float] = {   # reduced alloc for normal signals
        "ETH": 45.0,
        "BTC": 35.0,
    }
    OPT_MAX_COLLATERAL_PCT = 70.0        # never use >70% of balance on 1 option
    OPT_SURVIVAL_BALANCE = 20.0          # below this, cap allocation at 30%
    OPT_SURVIVAL_MAX_ALLOC = 30.0

    # ── Pullback entry ───────────────────────────────────────────
    PULLBACK_WAIT_SEC = 15              # Wait up to 15s for premium dip (was 30 — move is over by then)
    PULLBACK_DIP_PCT = 3.0             # Min dip to trigger entry (was 5 — too rare)
    PULLBACK_SKIP_RISE_PCT = 15.0      # Skip if premium rose this much (was 5 — rising = move happening!)
    PULLBACK_POLL_SEC = 2              # Check every 2s during pullback wait

    # ── Exit thresholds (tuned for momentum scalps) ────────────────
    TP_PREMIUM_GAIN_PCT = 30.0           # Take profit at +30% premium gain
    SL_PREMIUM_LOSS_PCT = 30.0           # Stop loss at -30% premium drop (was 50 — thesis is wrong, get out)
    # Tiered trailing: start wide, tighten as profit grows
    OPT_TRAIL_TIERS: list[tuple[float, float]] = [
        (10.0, 8.0),   # +10% peak → 8% trail distance
        (20.0, 6.0),   # +20% peak → 6% trail
        (30.0, 5.0),   # +30% peak → 5% trail
        (50.0, 4.0),   # +50% peak → 4% trail
    ]
    PULLBACK_EXIT_PCT = 40.0             # Exit if lost 40% of peak gain (was 50 — too aggressive)
    PULLBACK_ACTIVATE_PCT = 8.0          # Pullback only fires after +8% peak (was 5 — let winners breathe)
    DECAY_THRESHOLD_PCT = 3.0            # Exit if was +10%+ and faded to +3%
    # ── Stale SL tightening — progressive exit for stuck trades ─────
    STALE_MOVE_THRESHOLD = 5.0           # < 5% from entry = stale (not going anywhere)
    # ETH stale thresholds (faster-moving premium)
    STALE_SL_5M_ETH = -10.0             # 5 min: SL → -10%
    STALE_SL_8M_ETH = -5.0              # 8 min: SL → -5%
    STALE_EXIT_MIN_ETH = 12             # 12 min: force OPT_STALE
    # BTC stale thresholds (slower-moving premium — more room)
    STALE_SL_8M_BTC = -15.0             # 8 min: SL → -15%
    STALE_SL_12M_BTC = -10.0            # 12 min: SL → -10%
    STALE_EXIT_MIN_BTC = 18             # 18 min: force OPT_STALE
    PHASE1_HANDS_OFF_SEC = 30            # Only SL fires in first 30s after fill

    # ── Expiry guard — exit before contract expires worthless ────────
    EXPIRY_GUARD_HOURS = 2.0             # if expiry < 2h AND pnl < +10% → exit
    EXPIRY_GUARD_MIN_MIN = 30            # if expiry < 30 min → always exit regardless of P&L

    # ── Ratchet floor table: (peak_pct, locked_floor_pct) ────────────
    # Wider floors — give winners room to breathe. Don't lock breakeven until +5%.
    OPT_RATCHET_FLOOR_TABLE = [
        (3.0, -2.0),     # +3% peak → floor -2% (room to breathe)
        (5.0, 0.0),      # +5% peak → breakeven lock
        (8.0, 2.0),      # +8% → lock +2%
        (15.0, 5.0),     # +15% → lock +5%
        (25.0, 10.0),    # +25% → lock +10%
        (40.0, 20.0),    # +40% → lock +20%
        (60.0, 35.0),    # +60% → lock +35%
    ]

    # ── Position limits ───────────────────────────────────────────
    MAX_OPTION_POSITIONS = 1             # 1 option at a time

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
        self.option_side: str | None = None       # "call" or "put"
        self.option_symbol: str | None = None      # ccxt unified symbol
        self.entry_premium: float = 0.0
        self.entry_time: float = 0.0
        self._contracts: int = 1                   # dynamic — set by _calculate_option_contracts
        self._candle_alloc_pct: float = 35.0       # dynamic — set by signal strength
        self._strong_signal: bool = False          # True when cum >= 3x threshold + vol >= 2x
        self.highest_premium: float = 0.0
        self._trailing_active: bool = False
        self.strike_price: float = 0.0
        self.expiry_dt: datetime | None = None

        # Stats
        self._tick_count: int = 0
        self.hourly_wins: int = 0
        self.hourly_losses: int = 0
        self.hourly_pnl: float = 0.0

        # Skip-logging throttle: only log each skip reason once per 5 min
        self._last_skip_reason: str = ""
        self._last_skip_time: float = 0.0
        self._SKIP_LOG_INTERVAL = 5 * 60  # 5 minutes

        # Dashboard state write interval
        self._STATE_WRITE_INTERVAL = 30  # Write to DB every 30 seconds
        self._last_state_write: float = 0.0

        # Ticker failure tracking — detect POSITION_GONE (expired/delisted)
        self._consecutive_ticker_failures: int = 0
        self._MAX_TICKER_FAILURES = 6   # 6 failures × 10s = 60s of no data → position gone
        self._EXPIRY_CLOSE_MINUTES = 5  # Within 5 min of expiry, treat ticker fail as expired

        # Last known premium — used as exit price when position disappears
        self._last_known_premium: float = 0.0
        # Last known spot price — used for accurate fee calculation
        self._last_spot_price: float = 0.0
        # Entry context string for signals_fired DB column
        self._entry_context: str = ""

        # Cooldown after POSITION_GONE — no new options entry for 60s
        self._position_gone_cooldown_until: float = 0.0
        self._POSITION_GONE_COOLDOWN_SEC = 60

        # Cooldown after PREMIUM_NO_FILL — no new entry for 30s
        self._no_fill_cooldown_until: float = 0.0

        # DB trade ID — set on entry write, used for close lookup
        self._db_trade_id: int | None = None

        # Regime skip logging throttle (log once per 60s to avoid spam)
        self._last_regime_log: float = 0.0
        self._current_regime: str | None = None

        # Position verification ticker (every 3rd tick = ~30s)
        self._position_verify_tick: int = 0
        self._position_verify_failures: int = 0
        self._MAX_VERIFY_FAILURES = 10  # 10 × 30s = ~5 min of failed verifies → force POSITION_GONE

        # Ratchet profit floor
        self._opt_ratchet_floor: float = 0.0

        # ── Adaptive threshold: rolling candle ranges + volumes ──
        self._candle_ranges: deque[float] = deque(maxlen=self.ADAPTIVE_RANGE_WINDOW)
        self._candle_volumes: deque[float] = deque(maxlen=self.VOLUME_CONFIRM_WINDOW)
        self._last_range_candle_ts: float = 0.0   # timestamp of last candle ingested

        # Dashboard chain panel cached state (set during check, read by _write_dashboard_state)
        self._cached_candle_momentum: dict | None = None
        self._cached_bot_state: str = "scanning"
        self._cached_target_strike: float | None = None

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

    async def _log_skip(self, reason: str, metadata: dict[str, Any] | None = None) -> None:
        """Log an options skip event (throttled to avoid spam)."""
        now = time.monotonic()
        if reason == self._last_skip_reason and (now - self._last_skip_time) < self._SKIP_LOG_INTERVAL:
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
                    1 for m in self.options_exchange.markets.values()
                    if m.get("type") == "option"
                )
                self.logger.info(
                    "[%s] Options exchange loaded — %d option markets",
                    self.pair, opt_count,
                )
            except Exception as e:
                self.logger.error("[%s] Failed to load options markets: %s", self.pair, e)

        await self._refresh_option_chain()

        # Restore position state from DB if engine restarted with open option trade
        await self._restore_position_from_db()

        _ss = self.PREMIUM_SWEET_SPOT.get(self._base_asset, (3.0, 15.0))
        self.logger.info(
            "[%s] OPTIONS SCALP ACTIVE — adaptive_gate(2.0x noise, vol 1.2x, 3/5 candles), "
            "premium=$%.0f-$%.0f sweet | "
            "TP=%d%% SL=%d%% Trail=%d%%/%d%% Pullback=%d%% Decay=%d%% "
            "Stale=%d/%d/%dm Phase1=%ds Alloc=%s%s",
            self.pair,
            _ss[0], _ss[1],
            int(self.TP_PREMIUM_GAIN_PCT), int(self.SL_PREMIUM_LOSS_PCT),
            int(self.OPT_TRAIL_TIERS[0][0]), int(self.OPT_TRAIL_TIERS[0][1]),
            int(self.PULLBACK_EXIT_PCT), int(self.DECAY_THRESHOLD_PCT),
            5, 8, self.STALE_EXIT_MIN_BTC if self._base_asset == "BTC" else self.STALE_EXIT_MIN_ETH, self.PHASE1_HANDS_OFF_SEC,
            f"{self.OPT_PAIR_ALLOC_PCT.get(self._base_asset, 20)}%",
            f" | RESTORED: {self.option_side} {self.option_symbol}" if self.in_position else "",
        )

    async def _restore_position_from_db(self) -> None:
        """Restore in-memory position state from DB after engine restart.

        Checks the trades table for an open options_scalp trade on this pair's
        underlying asset. If found, restores all position tracking fields so
        exit management continues seamlessly.
        """
        if not self._db or not self._db.is_connected:
            return

        try:
            # Options trades are stored with the option symbol as pair
            # (e.g. ETH/USD:USD-260222-1980-C), but we need to find by strategy
            open_trades = await self._db.get_open_trades(pair=None)
            for trade in open_trades:
                if trade.get("strategy") != "options_scalp":
                    continue
                # Match by base asset (BTC or ETH)
                trade_pair = trade.get("pair", "")
                trade_asset = trade_pair.split("/")[0] if "/" in trade_pair else ""
                if trade_asset != self._base_asset:
                    continue

                # Found our open option trade — restore state
                self.in_position = True
                OptionsScalpStrategy._global_in_position = True  # acquire global lock
                OptionsScalpStrategy._global_position_asset = self._base_asset
                self.option_symbol = trade_pair
                self.entry_premium = trade.get("entry_price", 0)
                self.entry_time = time.monotonic()  # can't restore exact time, use now
                self.highest_premium = max(
                    self.entry_premium,
                    trade.get("current_price") or self.entry_premium,
                )

                # Determine option side from position_type or pair suffix
                if trade_pair.endswith("-C"):
                    self.option_side = "call"
                elif trade_pair.endswith("-P"):
                    self.option_side = "put"
                else:
                    self.option_side = "call"  # fallback

                # Restore trailing state
                self._trailing_active = trade.get("position_state") == "trailing"
                self.strike_price = trade.get("stop_loss", 0) or 0  # strike stored elsewhere

                # Try to parse strike from symbol: ETH/USD:USD-260222-1980-C
                parts = trade_pair.split("-")
                if len(parts) >= 3:
                    try:
                        self.strike_price = float(parts[-2])
                    except ValueError:
                        pass

                # Try to restore expiry from symbol: -YYMMDD-
                if len(parts) >= 2:
                    try:
                        expiry_str = parts[-3] if len(parts) >= 4 else parts[1]
                        self.expiry_dt = datetime.strptime(expiry_str, "%y%m%d").replace(
                            hour=12, tzinfo=timezone.utc,
                        )
                    except (ValueError, IndexError):
                        pass

                # Restore contracts from amount column
                self._contracts = max(1, int(trade.get("amount", 1) or 1))

                self.logger.info(
                    "[%s] RESTORED from DB: %s x%d %s strike=$%.0f entry=$%.4f peak=$%.4f trail=%s",
                    self.pair, self.option_side, self._contracts, self.option_symbol,
                    self.strike_price, self.entry_premium, self.highest_premium,
                    self._trailing_active,
                )
                break  # Only one position per asset

        except Exception as e:
            self.logger.error("[%s] Failed to restore position from DB: %s", self.pair, e)

    async def _update_position_state_in_db(self, current_premium: float) -> None:
        """Write live position state to the trades table so dashboard shows real P&L.

        Similar to scalp.py's _update_position_state_in_db, writes:
        current_price (premium), position_state, current_pnl, peak_pnl
        every ~10s.
        """
        if not self._db or not self._db.is_connected:
            return
        if not self.in_position or not self.option_symbol:
            return

        try:
            # P&L %
            pnl_pct = 0.0
            if self.entry_premium > 0:
                pnl_pct = (current_premium - self.entry_premium) / self.entry_premium * 100

            # Peak P&L %
            peak_pnl = 0.0
            if self.entry_premium > 0:
                peak_pnl = (self.highest_premium - self.entry_premium) / self.entry_premium * 100

            state = "trailing" if self._trailing_active else "holding"

            # Find our open trade (options trade pair = option symbol)
            open_trade = await self._db.get_open_trade(
                pair=self.option_symbol, exchange="delta", strategy="options_scalp",
            )
            if open_trade:
                # Live dollar P&L using contract multiplier (no leverage division)
                live_pnl = self._calc_options_pnl(
                    self.entry_premium, current_premium, self._contracts,
                )

                await self._db.update_trade(open_trade["id"], {
                    "position_state": state,
                    "current_price": round(current_premium, 8),
                    "current_pnl": round(pnl_pct, 4),
                    "peak_pnl": round(peak_pnl, 4),
                    "pnl": round(live_pnl, 8),
                    "pnl_pct": round(pnl_pct, 4),
                })
        except Exception as e:
            self.logger.debug("[%s] position state DB update failed: %s", self.pair, e)

    # ==================================================================
    # OPTIONS P&L HELPER
    # ==================================================================

    def _calc_options_pnl(
        self, entry_premium: float, exit_premium: float, contracts: int,
    ) -> float:
        """Calculate gross P&L for an options trade using contract multiplier.

        Returns gross_pnl in USD. Never divides by leverage.
        """
        multiplier = self.CONTRACT_MULTIPLIER.get(self._base_asset, 0.01)
        return (exit_premium - entry_premium) * contracts * multiplier

    # ==================================================================
    # OPTION CHAIN MANAGEMENT
    # ==================================================================

    async def _refresh_option_chain(self) -> None:
        """Fetch available option contracts, filter for valid expiries.

        Refreshed every 30 minutes. Filters for:
        - Correct underlying asset (BTC or ETH)
        - Expiry at least MIN_EXPIRY_HOURS away
        - Both calls and puts
        """
        now = time.monotonic()
        if now - self._chain_last_refresh < self.CHAIN_REFRESH_INTERVAL and self._option_chain:
            return

        if not self.options_exchange:
            return

        try:
            # Reload markets to get fresh option listings
            if self._chain_last_refresh > 0:
                await self.options_exchange.load_markets(True)  # force reload

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

                chain.append({
                    "symbol": symbol,
                    "strike": float(market.get("strike", 0)),
                    "option_type": (market.get("optionType") or "").lower(),
                    "expiry": expiry_dt,
                })

            chain.sort(key=lambda x: (x["expiry"], x["strike"]))
            self._option_chain = chain
            self._chain_last_refresh = now

            if chain:
                self._selected_expiry = chain[0]["expiry"]
                hours_away = (self._selected_expiry - now_utc).total_seconds() / 3600

                # EXPIRY SWITCH: if nearest expiry < 3h away, use next-day expiry
                if hours_away < self.EXPIRY_SWITCH_HOURS:
                    next_expiries = sorted(set(
                        c["expiry"] for c in chain if c["expiry"] > self._selected_expiry
                    ))
                    if next_expiries:
                        old_exp = self._selected_expiry
                        self._selected_expiry = next_expiries[0]
                        new_hours = (self._selected_expiry - now_utc).total_seconds() / 3600
                        self.logger.info(
                            "[%s] EXPIRY_SWITCH: nearest %s only %.1fh away — "
                            "switching to %s (%.1fh away)",
                            self.pair,
                            old_exp.strftime("%b %d %H:%M UTC"), hours_away,
                            self._selected_expiry.strftime("%b %d %H:%M UTC"), new_hours,
                        )
                        hours_away = new_hours

                self._available_strikes = sorted(set(
                    c["strike"] for c in chain
                    if c["expiry"] == self._selected_expiry
                ))
                self.logger.info(
                    "[%s] Option chain refreshed: %d contracts, "
                    "selected expiry=%s (%.1fh away), %d strikes",
                    self.pair, len(chain),
                    self._selected_expiry.strftime("%b %d %H:%M UTC"),
                    hours_away, len(self._available_strikes),
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
        self, atm_strike: float, option_type: str, extra: int = 0,
    ) -> list[float]:
        """Get sorted OTM strikes away from ATM (up for calls, down for puts).

        Returns up to MAX_OTM_STRIKES candidates (+ extra for fallback walk).
        When extra=1, returns only the (MAX_OTM+1)th strike (the next one beyond normal range).
        """
        if option_type == "call":
            candidates = sorted(s for s in self._available_strikes if s > atm_strike)
        else:
            candidates = sorted(
                (s for s in self._available_strikes if s < atm_strike), reverse=True,
            )
        if extra > 0:
            # Return only the strikes beyond the normal MAX_OTM range
            start = self.MAX_OTM_STRIKES
            return candidates[start:start + extra]
        return candidates[:self.MAX_OTM_STRIKES]

    def _build_option_symbol(
        self, strike: float, option_type: str, expiry: datetime,
    ) -> str | None:
        """Find the ccxt unified symbol for the given option parameters.

        Searches the cached chain first, falls back to manual construction:
        BTC/USD:USD-YYMMDD-STRIKE-C/P
        """
        target_type = option_type.lower()
        for opt in self._option_chain:
            if (opt["strike"] == strike
                    and opt["option_type"] == target_type
                    and opt["expiry"] == expiry):
                return opt["symbol"]

        # Fallback: construct manually
        expiry_str = expiry.strftime("%y%m%d")
        strike_str = str(int(strike))
        cp = "C" if target_type == "call" else "P"
        symbol = f"{self._base_asset}/USD:USD-{expiry_str}-{strike_str}-{cp}"
        self.logger.warning(
            "[%s] Option not in chain, constructed: %s", self.pair, symbol,
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

        # Fallback: fetch spot price from futures exchange if scalp didn't provide one
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

            # ATM strike
            if self._available_strikes and spot_price > 0:
                atm_strike = min(self._available_strikes, key=lambda s: abs(s - spot_price))

                # Fetch ATM call + put premiums (best-effort, skip on error)
                try:
                    call_sym = self._build_option_symbol(
                        atm_strike, "call", self._selected_expiry,
                    )
                    if call_sym and self.options_exchange:
                        t = await self.options_exchange.fetch_ticker(call_sym)
                        call_premium = t.get("last") or t.get("ask") or None
                except Exception:
                    pass

                try:
                    put_sym = self._build_option_symbol(
                        atm_strike, "put", self._selected_expiry,
                    )
                    if put_sym and self.options_exchange:
                        t = await self.options_exchange.fetch_ticker(put_sym)
                        put_premium = t.get("last") or t.get("ask") or None
                except Exception:
                    pass

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
            # Call strikes: ATM and 4 above (ascending)
            call_strikes = sorted(s for s in self._available_strikes if s >= atm_strike)[:5]
            for strike in call_strikes:
                try:
                    sym = self._build_option_symbol(strike, "call", self._selected_expiry)
                    if sym:
                        t = await self.options_exchange.fetch_ticker(sym)
                        chain_calls.append({
                            "strike": strike,
                            "bid": t.get("bid") or 0,
                            "ask": t.get("ask") or 0,
                        })
                except Exception:
                    chain_calls.append({"strike": strike, "bid": 0, "ask": 0})

            # Put strikes: ATM and 4 below (descending)
            put_strikes = sorted(
                (s for s in self._available_strikes if s <= atm_strike), reverse=True,
            )[:5]
            for strike in put_strikes:
                try:
                    sym = self._build_option_symbol(strike, "put", self._selected_expiry)
                    if sym:
                        t = await self.options_exchange.fetch_ticker(sym)
                        chain_puts.append({
                            "strike": strike,
                            "bid": t.get("bid") or 0,
                            "ask": t.get("ask") or 0,
                        })
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

            # Fetch current premium for position
            try:
                if self.options_exchange:
                    ticker = await self.options_exchange.fetch_ticker(self.option_symbol)
                    current_prem = ticker.get("last") or ticker.get("bid") or None
                    if current_prem and entry_prem and entry_prem > 0:
                        pnl_pct = (current_prem - entry_prem) / entry_prem * 100
                        pnl_usd = (current_prem - entry_prem) * self._contracts
            except Exception:
                pass

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
            "chain_calls": chain_calls,
            "chain_puts": chain_puts,
            "candle_momentum": self._cached_candle_momentum,
            "bot_state": self._cached_bot_state,
            "target_strike": self._cached_target_strike,
            "balance": round(balance, 2) if balance is not None else None,
        }

        await self._db.upsert_options_state(self.pair, state)

    # ==================================================================
    # MAIN CHECK LOOP
    # ==================================================================

    async def check(self) -> list[Signal]:
        """Main tick: refresh chain, check for entry/exit."""
        self._tick_count += 1

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

        # Not in position: look for entry from scalp signals
        return await self._check_option_entry()

    def _precompute_bot_state(self) -> None:
        """Set _cached_bot_state for cooldown timers before dashboard write."""
        if self.in_position:
            self._cached_bot_state = "in_position"
            return

        # No-fill cooldown
        if time.monotonic() < self._no_fill_cooldown_until:
            remaining = self._no_fill_cooldown_until - time.monotonic()
            self._cached_bot_state = f"blocked:no_fill_cooldown:{int(remaining)}s"
            return

        # Position-gone cooldown
        if time.monotonic() < self._position_gone_cooldown_until:
            remaining = self._position_gone_cooldown_until - time.monotonic()
            self._cached_bot_state = f"blocked:position_gone_cooldown:{int(remaining)}s"
            return

        # Will be overwritten by _check_option_entry() with the real state
        # but this ensures dashboard write has at least "scanning"
        if self._cached_bot_state.startswith("blocked:position_gone_cooldown") or \
                self._cached_bot_state.startswith("blocked:no_fill_cooldown"):
            self._cached_bot_state = "scanning"

    # ==================================================================
    # ENTRY LOGIC
    # ==================================================================

    async def _check_option_entry(self) -> list[Signal]:
        """Check scalp's signal state for 2/4+ momentum, buy option."""
        self._cached_bot_state = "scanning"
        self._cached_target_strike = None

        # 0. GLOBAL POSITION LOCK — only 1 option across all assets (BTC+ETH)
        if OptionsScalpStrategy._global_in_position and not self.in_position:
            if self._tick_count % 6 == 0:
                self.logger.info(
                    "[%s] OPTIONS GLOBAL_LOCK — %s has an open option",
                    self.pair, OptionsScalpStrategy._global_position_asset or "another asset",
                )
            self._cached_bot_state = "blocked:other_asset_in_position"
            return []

        # 0a. POSITION_GONE cooldown — no new entries for 60s after position disappeared
        if time.monotonic() < self._no_fill_cooldown_until:
            remaining = self._no_fill_cooldown_until - time.monotonic()
            if self._tick_count % 6 == 0:
                self.logger.info(
                    "[%s] OPTIONS COOLDOWN after PREMIUM_NO_FILL — %.0fs remaining",
                    self.pair, remaining,
                )
            self._cached_bot_state = f"blocked:no_fill_cooldown:{int(remaining)}s"
            return []

        if time.monotonic() < self._position_gone_cooldown_until:
            remaining = self._position_gone_cooldown_until - time.monotonic()
            if self._tick_count % 6 == 0:
                self.logger.info(
                    "[%s] OPTIONS COOLDOWN after POSITION_GONE — %.0fs remaining",
                    self.pair, remaining,
                )
            self._cached_bot_state = f"blocked:position_gone_cooldown:{int(remaining)}s"
            return []

        # 0b. Smart cooldown — no hard time block, just require fresh momentum after losses

        # 0c. BTC balance skip REMOVED — at 50x leverage, BTC OTM collateral is tiny ($0.60-1.12)

        # 1. Market regime gate — only CHOPPY blocked
        # SIDEWAYS, TRENDING_UP, TRENDING_DOWN all allowed — candle momentum is the gate.
        self._current_regime = None
        if self._market_analyzer:
            analysis = self._market_analyzer.last_analysis_for(self.pair)
            if analysis:
                self._current_regime = analysis.condition.value
                now = time.monotonic()
                if now - self._last_regime_log >= 120:
                    self._last_regime_log = now
                    self.logger.info(
                        "[%s] OPTIONS regime: %s", self.pair, self._current_regime,
                    )
                if self._current_regime and "CHOPPY" in str(self._current_regime).upper():
                    if self._tick_count % 30 == 0:
                        self.logger.info(
                            "[%s] OPTIONS CHOPPY_BLOCK: regime=%s — skipping",
                            self.pair, self._current_regime,
                        )
                    self._cached_bot_state = "blocked:choppy_regime"
                    return []

        # 2. Early-direction gate — PRIMARY ENTRY GATE
        # Direction determined FROM candles (2/3 completed 1m candles).
        # Per-asset cumulative: BTC >= 0.15%, ETH >= 0.20%.
        candle_pass, candle_reason, side, candle_count, candle_cum_pct, candle_pass_sizes = await self._check_candle_momentum()
        # Compute adaptive threshold for dashboard display
        _avg_range = mean(self._candle_ranges) if len(self._candle_ranges) >= 10 else 0.10
        _adaptive_thresh = max(_avg_range * self.ADAPTIVE_CUM_MULTIPLIER, self.ADAPTIVE_CUM_FLOOR)
        _avg_vol = mean(self._candle_volumes) if len(self._candle_volumes) >= 5 else 0
        self._cached_candle_momentum = {
            "count": candle_count, "total": self.CANDLE_MOM_LOOKBACK,
            "cum_pct": round(candle_cum_pct, 4), "direction": side, "passed": candle_pass,
            "reason": candle_reason,
            "adaptive_threshold": round(_adaptive_thresh, 4),
            "avg_range": round(_avg_range, 4),
            "avg_volume": round(_avg_vol, 0),
        }
        if not candle_pass:
            if self._tick_count % 6 == 0:
                self.logger.info("[%s] %s", self.pair, candle_reason)
            return []


        # 2b. Acceleration check is now inside _check_candle_momentum (3-of-5 with growing check)

        self.logger.info(
            "[%s] EARLY_GATE: %d/3 candles %s, cum=%.2f%% → premium check",
            self.pair, candle_count, side, candle_cum_pct,
        )

        # 2b. Underlying move check — confirm price is actually moving, not just candle noise
        underlying_move_pct = 0.0
        try:
            ohlcv_1s = await self.futures_exchange.fetch_ohlcv(self.pair, "1m", limit=2)
            if ohlcv_1s and len(ohlcv_1s) >= 2:
                price_now = float(ohlcv_1s[-1][4])  # latest close
                self._last_spot_price = price_now    # cache for fee calculation
                price_ago = float(ohlcv_1s[-2][1])  # open of previous candle (~60s ago)
                if price_ago > 0:
                    underlying_move_pct = abs(price_now - price_ago) / price_ago * 100
                    if underlying_move_pct < self.MIN_UNDERLYING_MOVE_PCT:
                        if self._tick_count % 6 == 0:
                            self.logger.info(
                                "[%s] OPTIONS UNDERLYING_MOVE: %.3f%% < %.2f%% in ~60s — SKIP",
                                self.pair, underlying_move_pct, self.MIN_UNDERLYING_MOVE_PCT,
                            )
                        return []
        except Exception as e:
            self.logger.debug("[%s] Underlying move check failed: %s", self.pair, e)

        # 2c. Full allocation base — confidence multiplier scales contracts below
        self._candle_alloc_pct = self.OPT_STRONG_ALLOC_PCT.get(self._base_asset, 60.0)
        self._strong_signal = False

        # 3. Determine option type from candle direction
        option_type = "call" if side == "long" else "put"

        # 3a. Counter-trend always allowed — candle momentum already ensures direction is real.
        # If 2/3 candles are red in TRENDING_UP, that's a reversal signal worth playing.
        # Options max loss = premium paid, no leverage risk.

        # 3b. Soft read scalp context — RSI, range position (don't block if unavailable)
        signal_state = None
        if self._scalp and hasattr(self._scalp, "last_signal_state"):
            signal_state = self._scalp.last_signal_state
            if signal_state is not None:
                signal_age = time.monotonic() - signal_state.get("timestamp", 0)
                if signal_age > self.SIGNAL_STALENESS_SEC:
                    signal_state = None  # stale — ignore

        # 3c. RSI — informational only (candle momentum is the gate)
        # PUT with RSI=30 = strong downtrend. CALL with RSI=70 = strong uptrend.

        # 3d. Range Gate — zone-based filtering for options (soft warning, no block)
        _opt_cached = type(self._scalp)._cached_signals.get(self._base_asset, {}) if self._scalp else {}
        _opt_range_pos = _opt_cached.get("range_position")
        if _opt_range_pos is not None:
            _zone_warning = None
            if _opt_range_pos <= 0.20 and option_type == "put":
                _zone_warning = f"PUT in LOW_ZONE (pos={_opt_range_pos:.2f})"
            elif _opt_range_pos >= 0.80 and option_type == "call":
                _zone_warning = f"CALL in HIGH_ZONE (pos={_opt_range_pos:.2f})"
            if _zone_warning:
                self.logger.info("[%s] OPT_RANGE note: %s — entering anyway", self.pair, _zone_warning)

        # Extract scalp strength for metadata/logging (not gating)
        strength = 0
        if signal_state is not None:
            strength = signal_state.get("strength", 0)

        # Log entry context from scalp signals for analysis
        _rsi = signal_state.get("rsi", 0) if signal_state else 0
        _mom60 = signal_state.get("momentum_60s", 0) if signal_state else 0
        _bb = _opt_cached.get("bb_position", 0)
        _vol = _opt_cached.get("volume_ratio", 0)
        self._entry_context = f"RSI={_rsi:.0f} mom60={_mom60:.3f}% BB={_bb:.2f} vol={_vol:.2f}x cum={candle_cum_pct:.2f}%"
        self.logger.info(
            "[%s] ENTRY_CONTEXT: %s | candles=%d/%d",
            self.pair, self._entry_context, candle_count, self.CANDLE_MOM_LOOKBACK,
        )

        # 2d. Confidence score — skip low-conviction entries, scale contracts to conviction
        _candle_score = 1.0 if candle_count >= 5 else (0.7 if candle_count >= 4 else 0.5)
        _cum_ratio = candle_cum_pct / _adaptive_thresh if _adaptive_thresh > 0 else 1.0
        _cum_score = 1.0 if _cum_ratio >= 2.0 else (0.7 if _cum_ratio >= 1.5 else 0.4)
        _entry_vols_conf = list(self._candle_volumes)[-self.VOLUME_CONFIRM_CANDLES:]
        _entry_vol_conf = mean(_entry_vols_conf) if _entry_vols_conf else 0
        _avg_vol_conf = mean(self._candle_volumes) if len(self._candle_volumes) >= 5 else 0
        _vol_ratio_conf = _entry_vol_conf / _avg_vol_conf if _avg_vol_conf > 0 else 0
        _vol_score = 1.0 if _vol_ratio_conf >= 2.0 else (0.7 if _vol_ratio_conf >= 1.5 else 0.4)
        entry_confidence = (_candle_score + _cum_score + _vol_score) / 3.0
        if entry_confidence < 0.4:
            self.logger.info(
                "[%s] CONFIDENCE: candle=%.1f cum=%.1f vol=%.1f final=%.2f → SKIP (below 0.4)",
                self.pair, _candle_score, _cum_score, _vol_score, entry_confidence,
            )
            self._cached_bot_state = "blocked:low_confidence"
            return []

        self._cached_bot_state = "ready"
        self.logger.info(
            "[%s] OPTIONS CANDLE_READY: %s — checking chain/premium",
            self.pair, option_type.upper(),
        )

        # 4. Get current underlying price (from scalp state or ticker)
        current_price = 0
        if signal_state is not None:
            current_price = signal_state.get("current_price", 0)
        if current_price <= 0:
            # Fallback: fetch ticker directly
            try:
                ticker = await self.futures_exchange.fetch_ticker(self.pair)
                current_price = float(ticker.get("last", 0) or 0)
            except Exception:
                pass
        if current_price <= 0:
            self.logger.info("[%s] OPTIONS: no current_price available", self.pair)
            self._cached_bot_state = "blocked:no_price"
            return []

        # 6. Check expiry validity
        if self._selected_expiry is None:
            if self._tick_count % 30 == 0:
                self.logger.info("[%s] No valid expiry available", self.pair)
            await self._log_skip(
                f"{self.pair} — OPTIONS SKIP: no valid expiry available",
                {"option_type": option_type, "strength": strength},
            )
            self._cached_bot_state = "blocked:no_expiry"
            return []

        hours_to_expiry = (
            self._selected_expiry - datetime.now(timezone.utc)
        ).total_seconds() / 3600
        if hours_to_expiry < self.MIN_EXPIRY_HOURS:
            if self._tick_count % 30 == 0:
                self.logger.info(
                    "[%s] Nearest expiry only %.1fh away (need %dh+)",
                    self.pair, hours_to_expiry, self.MIN_EXPIRY_HOURS,
                )
            await self._log_skip(
                f"{self.pair} — OPTIONS SKIP: expiry only {hours_to_expiry:.1f}h away (need {self.MIN_EXPIRY_HOURS}h+)",
                {"option_type": option_type, "strength": strength, "hours_to_expiry": round(hours_to_expiry, 1)},
            )
            self._cached_bot_state = "blocked:expiry_close"
            return []

        # 7. Find ATM strike
        atm_strike = self._get_atm_strike(current_price)
        if atm_strike is None:
            if self._tick_count % 30 == 0:
                self.logger.info("[%s] No valid strikes found", self.pair)
            await self._log_skip(
                f"{self.pair} — OPTIONS SKIP: no valid strikes for {option_type.upper()}",
                {"option_type": option_type, "strength": strength, "price": current_price},
            )
            self._cached_bot_state = "blocked:no_strikes"
            return []

        # 8-9. Per-asset strike selection:
        #   ETH: ATM only — OTM ETH options have poor delta response
        #   BTC: 1 OTM first (cheaper), then ATM fallback
        if self._base_asset == "ETH":
            strikes_to_try = [atm_strike]
            self.logger.info(
                "[%s] STRIKE CANDIDATES: $%.0f (ETH ATM only)",
                self.pair, atm_strike,
            )
        else:
            otm_candidates = self._get_otm_candidates(atm_strike, option_type)
            strikes_to_try = otm_candidates[:1] + [atm_strike]
            self.logger.info(
                "[%s] STRIKE CANDIDATES: %s (BTC 1 OTM → ATM)",
                self.pair,
                ", ".join(f"${s:.0f}" for s in strikes_to_try),
            )
        selected_strike: float | None = None
        selected_symbol: str | None = None
        premium: float = 0.0
        opt_contracts: int = 0
        first_collateral: float | None = None  # track first-tried strike cost for logging

        # Calculate OTM offset for each strike relative to ATM
        def _otm_offset(s: float) -> int:
            if option_type == "call":
                return len([x for x in self._available_strikes if atm_strike < x <= s])
            return len([x for x in self._available_strikes if s <= x < atm_strike])

        for i, strike in enumerate(strikes_to_try):
            symbol = self._build_option_symbol(strike, option_type, self._selected_expiry)
            if symbol is None:
                continue

            try:
                ticker = await self.options_exchange.fetch_ticker(symbol)
                prem = ticker.get("last") or ticker.get("ask") or 0
            except Exception as e:
                self.logger.debug("[%s] Ticker fetch failed for %s: %s", self.pair, symbol, e)
                continue

            if prem <= 0:
                continue

            collateral = prem / self.OPTIONS_LEVERAGE

            # Track first-tried strike collateral for logging
            if i == 0:
                first_collateral = collateral

            # Check premium not too small (illiquid)
            if prem < self.MIN_PREMIUM_USD:
                self.logger.debug(
                    "[%s] Strike $%.0f premium $%.4f < min $%.2f — illiquid",
                    self.pair, strike, prem, self.MIN_PREMIUM_USD,
                )
                continue

            # Dynamic sizing: how many contracts can we afford?
            n = self._calculate_option_contracts(prem)
            if n >= 1:
                selected_strike = strike
                selected_symbol = symbol
                premium = prem
                opt_contracts = n
                self._cached_target_strike = strike
                otm_n = _otm_offset(strike)
                otm_label = f"{otm_n} OTM" if otm_n > 0 else "ATM"
                self.logger.info(
                    "[%s] OPT STRIKE: %s $%.0f (%s), premium=$%.4f, col=$%.4f, %d contracts",
                    self.pair, option_type.upper(), strike, otm_label, prem, collateral, n,
                )
                break

            self.logger.debug(
                "[%s] Strike $%.0f — can't afford 1 contract (premium=$%.4f, collateral=$%.4f)",
                self.pair, strike, prem, collateral,
            )

        if selected_strike is None or selected_symbol is None:
            if self._tick_count % 30 == 0:
                label = "ATM only" if self._base_asset == "ETH" else "1 OTM + ATM"
                self.logger.info(
                    "[%s] No affordable strike (%s) — skipping "
                    "(ATM=$%.0f collateral=$%.4f)",
                    self.pair, label, atm_strike,
                    first_collateral or 0,
                )
            await self._log_skip(
                f"{self.pair} — OPTIONS SKIP: no affordable strike "
                f"(ATM=${atm_strike:.0f} collateral=${first_collateral or 0:.4f})",
                {"option_type": option_type, "atm_strike": atm_strike,
                 "first_collateral": first_collateral,
                 "strength": strength},
            )
            self._cached_bot_state = "blocked:no_affordable_strike"
            return []

        # Confidence multiplier: scale base contract count by signal conviction
        _base_contracts = opt_contracts
        if entry_confidence >= 0.8:
            _conf_mult = 1.0
        elif entry_confidence >= 0.6:
            _conf_mult = 0.6
        else:
            _conf_mult = 0.3
        opt_contracts = max(1, int(_base_contracts * _conf_mult))
        self.logger.info(
            "[%s] CONFIDENCE: candle=%.1f cum=%.1f vol=%.1f final=%.2f → %dct (base was %dct)",
            self.pair, _candle_score, _cum_score, _vol_score, entry_confidence,
            opt_contracts, _base_contracts,
        )

        # 9a-post. PREMIUM SWEET SPOT — prefer cheap, allow expensive on strong signal
        sweet_low, sweet_high = self.PREMIUM_SWEET_SPOT.get(
            self._base_asset, (3.0, 15.0),
        )
        if premium < sweet_low:
            self.logger.info(
                "[%s] PREMIUM_TOO_CHEAP: $%.2f < $%.1f — likely illiquid, SKIP",
                self.pair, premium, sweet_low,
            )
            self._cached_bot_state = "blocked:premium_illiquid"
            return []

        if premium > sweet_high:
            # Expensive premium — only enter on STRONG signal
            _avg_range_now = mean(self._candle_ranges) if len(self._candle_ranges) >= 10 else 0.10
            _strong_cum = max(_avg_range_now * self.PREMIUM_EXPENSIVE_CUM_MULT, self.ADAPTIVE_CUM_FLOOR * 2)
            _avg_vol_now = mean(self._candle_volumes) if len(self._candle_volumes) >= 5 else 0
            # Use the most recent volumes from the rolling deque
            _recent_vols = list(self._candle_volumes)[-self.VOLUME_CONFIRM_CANDLES:]
            _entry_vol_now = mean(_recent_vols) if _recent_vols else 0

            if candle_cum_pct < _strong_cum:
                self.logger.info(
                    "[%s] EXPENSIVE_PREMIUM: $%.1f > $%.0f, need stronger signal "
                    "(cum=%.2f%% < %.2f%%) → SKIP",
                    self.pair, premium, sweet_high, candle_cum_pct, _strong_cum,
                )
                self._cached_bot_state = "blocked:premium_expensive_weak"
                return []
            if _avg_vol_now > 0 and _entry_vol_now < _avg_vol_now * self.PREMIUM_EXPENSIVE_VOL_MULT:
                self.logger.info(
                    "[%s] EXPENSIVE_PREMIUM: $%.1f > $%.0f, need stronger volume "
                    "(%.0f < %.1fx avg %.0f) → SKIP",
                    self.pair, premium, sweet_high, _entry_vol_now,
                    self.PREMIUM_EXPENSIVE_VOL_MULT, _avg_vol_now,
                )
                self._cached_bot_state = "blocked:premium_expensive_low_vol"
                return []
            self.logger.info(
                "[%s] EXPENSIVE_PREMIUM_OK: $%.1f > $%.0f but signal is STRONG "
                "(cum=%.2f%% >= %.2f%%, vol=%.0f >= %.1fx) → proceeding",
                self.pair, premium, sweet_high, candle_cum_pct, _strong_cum,
                _entry_vol_now, self.PREMIUM_EXPENSIVE_VOL_MULT,
            )

        # 9b. PREMIUM CHECK — sample twice 5s apart, place limit immediately if NOT falling.
        # Enters before the spike rather than chasing it. Market proves the move by filling us.
        first_ask = premium
        self.logger.info(
            "[%s] PREMIUM_CHECK: first_ask=$%.4f — waiting 5s for confirmation",
            self.pair, first_ask,
        )

        await asyncio.sleep(5)
        second_ask = 0.0
        try:
            _chk_ticker = await self.options_exchange.fetch_ticker(selected_symbol)
            second_ask = float(_chk_ticker.get("ask") or _chk_ticker.get("last") or 0)
        except Exception as e:
            self.logger.debug("[%s] PREMIUM_CHECK: second sample failed: %s", self.pair, e)

        if second_ask <= 0:
            self.logger.info("[%s] PREMIUM_CHECK: second ask unavailable — SKIP", self.pair)
            return []

        # Part D: if premium is falling, skip
        if second_ask < first_ask:
            self.logger.info(
                "[%s] PREMIUM_CHECK: first=$%.4f second=$%.4f → SKIP (PREMIUM_FALLING)",
                self.pair, first_ask, second_ask,
            )
            await self._log_skip(
                f"{self.pair} — PREMIUM_FALLING: ${first_ask:.4f} → ${second_ask:.4f}",
                {"first_ask": first_ask, "second_ask": second_ask},
            )
            return []

        # Premium not falling — place limit at FIRST ask (before spike)
        # If premium keeps rising through our price we fill at a discount.
        # If it peaked and reversed, nobody lifts our stale price → clean cancel.
        limit_price = first_ask
        self.logger.info(
            "[%s] PREMIUM_CHECK: first=$%.4f second=$%.4f → placing limit @ $%.4f (first_ask)",
            self.pair, first_ask, second_ask, limit_price,
        )

        # Place limit buy
        limit_order_id = None
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
                "[%s] PREMIUM_LIMIT: order %s placed — %d contracts @ $%.4f",
                self.pair, limit_order_id, opt_contracts, limit_price,
            )
        except Exception as e:
            self.logger.info("[%s] PREMIUM_LIMIT: order placement failed: %s — SKIP", self.pair, e)
            return []

        # Poll for fill over 10 seconds (10 × 1s)
        limit_filled = False
        fill_price = limit_price
        _filled_qty = 0.0
        for _poll in range(10):  # 10 × 1s = 10s
            await asyncio.sleep(1)
            try:
                updated = await self.options_exchange.fetch_order(limit_order_id, selected_symbol)
                status = updated.get("status", "")
                _filled_qty = float(updated.get("filled", 0) or 0)
                if status == "closed" or _filled_qty >= opt_contracts:
                    fill_price = float(updated.get("average", 0) or updated.get("price", 0) or limit_price)
                    limit_filled = True
                    self.logger.info(
                        "[%s] PREMIUM_LIMIT: FILLED @ $%.4f (%d contracts)",
                        self.pair, fill_price, opt_contracts,
                    )
                    break
                elif _filled_qty > 0:
                    self.logger.debug(
                        "[%s] PREMIUM_LIMIT: partial %.1f/%d — continuing poll",
                        self.pair, _filled_qty, opt_contracts,
                    )
            except Exception as e:
                self.logger.debug("[%s] PREMIUM_LIMIT: poll failed: %s", self.pair, e)

        if not limit_filled:
            if _filled_qty > 0:
                # Partial fill — keep it, cancel residual, adjust contracts
                try:
                    await self.options_exchange.cancel_order(limit_order_id, selected_symbol)
                except Exception:
                    pass
                opt_contracts = max(1, int(_filled_qty))
                fill_price = limit_price
                limit_filled = True
                self.logger.info(
                    "[%s] PREMIUM_LIMIT: PARTIAL FILL — %d contracts @ ~$%.4f — keeping",
                    self.pair, opt_contracts, fill_price,
                )
            else:
                # No fill — cancel, log, apply 30s cooldown
                cancel_ok = False
                try:
                    await self.options_exchange.cancel_order(limit_order_id, selected_symbol)
                    cancel_ok = True
                except Exception as _ce:
                    # Cancel failed — verify it didn't silently fill
                    try:
                        _fc = await self.options_exchange.fetch_order(limit_order_id, selected_symbol)
                        if _fc.get("status") == "closed" or float(_fc.get("filled", 0) or 0) >= opt_contracts:
                            fill_price = float(_fc.get("average", 0) or _fc.get("price", 0) or limit_price)
                            limit_filled = True
                            self.logger.info(
                                "[%s] PREMIUM_LIMIT: cancel failed but order FILLED @ $%.4f",
                                self.pair, fill_price,
                            )
                    except Exception:
                        pass
                    if not limit_filled:
                        self.logger.info("[%s] PREMIUM_LIMIT: cancel failed: %s — SKIP", self.pair, _ce)
                        return []

                if not limit_filled:
                    self.logger.info(
                        "[%s] PREMIUM_NO_FILL: ask=$%.4f pair=%s — order unfilled in 10s, cancelled",
                        self.pair, limit_price, self.pair,
                    )
                    await self._log_skip(
                        f"{self.pair} — PREMIUM_NO_FILL: ask=${limit_price:.4f} — order unfilled in 10s, cancelled",
                        {"ask": limit_price, "pair": self.pair},
                    )
                    self._no_fill_cooldown_until = time.monotonic() + 30
                    return []

        if not limit_filled:
            return []

        # Re-fetch order for Delta's actual fill price (average field)
        try:
            final = await self.options_exchange.fetch_order(limit_order_id, selected_symbol)
            actual_avg = float(final.get("average") or final.get("price") or limit_price)
            if actual_avg > 0:
                fill_price = actual_avg
        except Exception:
            pass  # keep fill_price from polling loop

        # Use fill price for entry — order already executed, signal is informational
        premium = fill_price
        self._limit_entry_filled = True  # flag for executor to skip order placement

        # SET POSITION STATE IMMEDIATELY — before async trade_executor flow.
        # If on_fill() never fires (WS miss, restart), this ensures we track the position.
        self.in_position = True
        OptionsScalpStrategy._global_in_position = True
        OptionsScalpStrategy._global_position_asset = self._base_asset
        self.entry_premium = fill_price
        self._contracts = opt_contracts
        self.option_symbol = selected_symbol
        self.option_side = option_type
        self.entry_time = time.monotonic()
        self.highest_premium = fill_price
        self._last_known_premium = fill_price
        self.strike_price = selected_strike
        if self._selected_expiry:
            self.expiry_dt = self._selected_expiry
        self.logger.info(
            "[%s] POSITION LOCKED — %s x%d @ $%.4f (before executor flow)",
            self.pair, option_type.upper(), opt_contracts, fill_price,
        )

        # 10. Classify setup_type from scalp signal reason (soft — default MOMENTUM_BURST)
        signals_str = ""
        if signal_state is not None:
            signals_str = signal_state.get("reason", "")
        setup_type = "MOMENTUM_BURST"  # candle momentum IS a momentum burst
        if self._scalp and signals_str:
            try:
                candidates = self._scalp._classify_setups(signals_str)
                if candidates:
                    setup_type = candidates[0]  # highest priority setup
            except Exception:
                pass

        # 10a. GPFC: Setup whitelist — only MOMENTUM_BURST and BB_SQUEEZE
        if setup_type not in self.ALLOWED_SETUPS:
            self.logger.info(
                "[%s] OPTIONS SETUP_BLOCK: %s not in whitelist %s — skipping",
                self.pair, setup_type, self.ALLOWED_SETUPS,
            )
            await self._log_skip(
                f"{self.pair} — OPTIONS SETUP_BLOCK: {setup_type} not in whitelist",
                {"option_type": option_type, "setup_type": setup_type, "strength": strength},
            )
            self._cached_bot_state = "blocked:setup_not_allowed"
            return []

        # 10b. SIDEWAYS regime — all setups allowed (candle momentum is the gate)
        # Only CHOPPY is blocked (at regime gate above)

        # 10c. (MOVED to step 9a-post — premium cap now checked BEFORE limit order)

        # 10d. Sizing already handled by dynamic candle alloc (35/50%)
        # BB_SQUEEZE gets 60% factor applied on top
        if setup_type == "BB_SQUEEZE" and opt_contracts > 1:
            adjusted = max(1, int(opt_contracts * 0.60))
            self.logger.info(
                "[%s] OPTIONS SIZING: BB_SQUEEZE → 60%% factor → %d→%d contracts",
                self.pair, opt_contracts, adjusted,
            )
            opt_contracts = adjusted

        # 11. Pullback entry — wait up to 30s for premium dip before buying
        expiry_str = self._selected_expiry.strftime('%b %d %H:%M')
        strike_label = "ATM" if selected_strike == atm_strike else "OTM"

        return await self._attempt_pullback_entry(
            option_type=option_type,
            selected_symbol=selected_symbol,
            selected_strike=selected_strike,
            atm_strike=atm_strike,
            signal_premium=premium,
            strength=strength,
            signals_str=signals_str,
            current_price=current_price,
            setup_type=setup_type,
            expiry_str=expiry_str,
            strike_label=strike_label,
            contracts=opt_contracts,
        )

    # ==================================================================
    # PULLBACK ENTRY
    # ==================================================================

    async def _attempt_pullback_entry(
        self,
        option_type: str,
        selected_symbol: str,
        selected_strike: float,
        atm_strike: float,
        signal_premium: float,
        strength: int,
        signals_str: str,
        current_price: float,
        setup_type: str,
        expiry_str: str,
        strike_label: str,
        contracts: int = 1,
    ) -> list[Signal]:
        """Wait up to PULLBACK_WAIT_SEC for premium to dip before entering.

        1. Poll option ticker every PULLBACK_POLL_SEC (2s)
        2. If premium dips 5-10% below signal → enter at market (dipped price)
        3. If premium rises 5%+ above signal → skip (move already priced in)
        4. After 30s no dip → enter at market only if within +5% of signal price
        """
        import asyncio

        self.logger.info(
            "[%s] PULLBACK WAIT: %s $%.0f premium=$%.4f — waiting up to %ds for dip",
            self.pair, option_type.upper(), selected_strike,
            signal_premium, self.PULLBACK_WAIT_SEC,
        )

        elapsed = 0.0
        entry_premium = signal_premium  # default: use signal-time price

        while elapsed < self.PULLBACK_WAIT_SEC:
            await asyncio.sleep(self.PULLBACK_POLL_SEC)
            elapsed += self.PULLBACK_POLL_SEC

            try:
                ticker = await self.options_exchange.fetch_ticker(selected_symbol)
                now_premium = ticker.get("last") or ticker.get("ask") or 0
            except Exception as e:
                self.logger.debug("[%s] Pullback ticker fail: %s", self.pair, e)
                continue

            if now_premium <= 0:
                continue

            change_pct = (now_premium - signal_premium) / signal_premium * 100

            # Premium rose too much — move already priced in, skip entry
            if change_pct >= self.PULLBACK_SKIP_RISE_PCT:
                self.logger.info(
                    "[%s] PULLBACK SKIP: premium rose +%.1f%% ($%.4f → $%.4f) — move priced in",
                    self.pair, change_pct, signal_premium, now_premium,
                )
                await self._log_skip(
                    f"{self.pair} — OPTIONS PULLBACK SKIP: premium rose +{change_pct:.1f}%",
                    {"signal_premium": signal_premium, "now_premium": now_premium},
                )
                return []

            # Premium dipped enough — enter now
            if change_pct <= -self.PULLBACK_DIP_PCT:
                entry_premium = now_premium
                self.logger.info(
                    "[%s] PULLBACK DIP: premium dipped %.1f%% ($%.4f → $%.4f) — entering",
                    self.pair, change_pct, signal_premium, now_premium,
                )
                break

            self.logger.debug(
                "[%s] PULLBACK polling: %.0fs premium=$%.4f (%+.1f%%)",
                self.pair, elapsed, now_premium, change_pct,
            )

        else:
            # 30s elapsed, no dip — check if still within +5% of signal price
            try:
                ticker = await self.options_exchange.fetch_ticker(selected_symbol)
                final_premium = ticker.get("last") or ticker.get("ask") or 0
            except Exception:
                final_premium = 0

            if final_premium <= 0:
                self.logger.info("[%s] PULLBACK TIMEOUT: no valid premium — skipping", self.pair)
                return []

            final_change = (final_premium - signal_premium) / signal_premium * 100
            if final_change > self.PULLBACK_SKIP_RISE_PCT:
                self.logger.info(
                    "[%s] PULLBACK TIMEOUT: premium +%.1f%% above signal — skipping",
                    self.pair, final_change,
                )
                return []

            entry_premium = final_premium
            self.logger.info(
                "[%s] PULLBACK TIMEOUT: no dip but within range (%+.1f%%) — entering at $%.4f",
                self.pair, final_change, entry_premium,
            )

        # Log to activity_log for dashboard
        await self._log_activity(
            "options_entry",
            f"{self.pair} — OPTIONS: {option_type.upper()} {strike_label} ${selected_strike:.0f} | "
            f"premium=${entry_premium:.4f} | expiry={expiry_str} | candle_entry {signals_str or 'candle_momentum'}",
            {"option_type": option_type, "strike": selected_strike, "premium": entry_premium,
             "strike_label": strike_label,
             "expiry": self._selected_expiry.isoformat() if self._selected_expiry else "",
             "strength": strength, "underlying_price": current_price,
             "symbol": selected_symbol, "setup_type": setup_type},
        )

        # Build and return entry signal
        return self._build_entry_signal(
            option_type=option_type,
            selected_symbol=selected_symbol,
            selected_strike=selected_strike,
            premium=entry_premium,
            strength=strength,
            signals_str=signals_str,
            current_price=current_price,
            setup_type=setup_type,
            expiry_str=expiry_str,
            strike_label=strike_label,
            contracts=contracts,
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
    ) -> list[Signal]:
        """Build the entry Signal for an option trade."""
        # Store contracts for exit sizing
        self._contracts = contracts
        # Capture and reset limit entry flag
        already_filled = getattr(self, "_limit_entry_filled", False)
        self._limit_entry_filled = False

        reason = (
            f"OPTIONS {option_type.upper()} | candle_entry "
            f"({signals_str or 'candle_momentum'}) | "
            f"{strike_label} Strike=${selected_strike:.0f} "
            f"Exp={expiry_str} "
            f"Premium=${premium:.4f} x{contracts}"
        )
        self.logger.info("[%s] OPTIONS ENTRY — %s (setup=%s)", self.pair, reason, setup_type)

        return [Signal(
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
                "expiry": self._selected_expiry.isoformat() if self._selected_expiry else "",
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
        )]

    # ==================================================================
    # DYNAMIC OPTION SIZING
    # ==================================================================

    def _calculate_option_contracts(self, premium: float) -> int:
        """Dynamic sizing: contracts based on balance, pair allocation, leverage.

        Formula:
          collateral_available = balance × alloc_pct × 40% safety cap
          collateral_per_contract = premium / leverage
          contracts = floor(collateral_available / collateral_per_contract)
          Minimum 1, returns 0 if can't afford 1.
        """
        import math

        exchange_capital = self.risk_manager.get_exchange_capital(self._exchange_id)
        if exchange_capital <= 0 or premium <= 0:
            return 0

        # Signal strength sizing: strong signal → full alloc, normal → reduced
        alloc_pct = self._candle_alloc_pct  # set by _check_option_entry

        # Survival mode: low balance → cap allocation
        if exchange_capital < self.OPT_SURVIVAL_BALANCE:
            alloc_pct = min(alloc_pct, self.OPT_SURVIVAL_MAX_ALLOC)

        # Collateral budget (capped at 70% of total balance)
        collateral_available = exchange_capital * (alloc_pct / 100)
        max_collateral = exchange_capital * (self.OPT_MAX_COLLATERAL_PCT / 100)
        collateral_available = min(collateral_available, max_collateral)

        # Collateral per contract at leverage
        collateral_per_contract = premium / self.OPTIONS_LEVERAGE
        if collateral_per_contract <= 0:
            return 0

        contracts = math.floor(collateral_available / collateral_per_contract)
        contracts = max(contracts, 0)

        # Survival mode: balance < $5 → cap at 5 contracts
        if exchange_capital < 5.0 and contracts > 5:
            self.logger.info(
                "[%s] SURVIVAL_MODE: bal=$%.2f < $5 — capping %d → 5 contracts",
                self.pair, exchange_capital, contracts,
            )
            contracts = 5

        # Hard cap per asset: ETH 40, BTC whatever fits collateral
        hard_cap = 40 if self._base_asset == "ETH" else 999
        if contracts > hard_cap:
            self.logger.info(
                "[%s] SIZE_CAP: %d → %d contracts (hard cap)",
                self.pair, contracts, hard_cap,
            )
            contracts = hard_cap

        # SAFETY: max SL loss = 25% of balance
        multiplier = self.CONTRACT_MULTIPLIER.get(self._base_asset, 0.01)
        max_sl_loss = contracts * premium * (self.SL_PREMIUM_LOSS_PCT / 100) * multiplier
        max_allowed_loss = exchange_capital * 0.25
        if max_sl_loss > max_allowed_loss and premium > 0:
            safe_contracts = math.floor(
                max_allowed_loss / (premium * (self.SL_PREMIUM_LOSS_PCT / 100) * multiplier)
            )
            self.logger.info(
                "[%s] SL_SAFETY: %d→%d contracts (SL loss $%.2f > 25%% of bal $%.2f)",
                self.pair, contracts, safe_contracts, max_sl_loss, exchange_capital,
            )
            contracts = max(safe_contracts, 1)

        self.logger.info(
            "[%s] OPT_SIZING: %d contracts @ $%.4f "
            "(collateral=$%.2f, alloc=%.0f%%, bal=$%.2f, per_ct=$%.4f, strong=%s)",
            self.pair, contracts, premium,
            collateral_available, alloc_pct, exchange_capital,
            collateral_per_contract, self._strong_signal,
        )
        return contracts

    # ==================================================================
    # CANDLE-BASED MOMENTUM GATE
    # ==================================================================

    async def _check_candle_momentum(self) -> tuple[bool, str, str | None, int, float, list[float]]:
        """Early-direction gate for options entry — PRIMARY GATE.

        Reads the market like a trader watching the tape:
        1. Direction: ≥3 of last 5 candles in same direction
        2. Adaptive threshold: cum move >= 2.0x recent avg candle range (adapts to noise)
        3. Volume confirmation: entry candles must have 1.5x avg volume
        4. Acceleration: recent candles bigger than earlier ones (move is growing)

        Returns:
            (passed, reason_string, side, directional_count, cum_pct, candle_sizes)
        """
        exchange = self.futures_exchange
        if not exchange:
            return False, "no_exchange", None, 0, 0.0, []

        try:
            # Fetch extra candles for the rolling range/volume baseline
            fetch_limit = max(self.ADAPTIVE_RANGE_WINDOW, self.VOLUME_CONFIRM_WINDOW) + self.CANDLE_MOM_LOOKBACK + 2
            ohlcv = await exchange.fetch_ohlcv(self.pair, "1m", limit=fetch_limit)
        except Exception as e:
            self.logger.debug("[%s] CANDLE_MOM: fetch_ohlcv failed: %s", self.pair, e)
            return False, f"fetch_failed ({e})", None, 0, 0.0, []

        if not ohlcv or len(ohlcv) < self.CANDLE_MOM_LOOKBACK:
            return False, f"insufficient candles ({len(ohlcv) if ohlcv else 0})", None, 0, 0.0, []

        # ── Update rolling baseline from ALL fetched candles ──
        # Only ingest candles we haven't seen yet (by timestamp)
        for candle in ohlcv:
            ts = float(candle[0])
            if ts <= self._last_range_candle_ts:
                continue
            self._last_range_candle_ts = ts
            o, c, vol = float(candle[1]), float(candle[4]), float(candle[5])
            if o > 0:
                self._candle_ranges.append(abs(c - o) / o * 100)
            if vol > 0:
                self._candle_volumes.append(vol)

        # ── Take last 5 completed candles for direction/momentum ──
        completed = ohlcv[-self.CANDLE_MOM_LOOKBACK:]

        current_price = float(completed[-1][4])
        if current_price <= 0:
            return False, "bad price", None, 0, 0.0, []

        # ── ADAPTIVE THRESHOLD: compare move to recent noise ──
        avg_range = mean(self._candle_ranges) if len(self._candle_ranges) >= 10 else 0.10
        cum_threshold = max(avg_range * self.ADAPTIVE_CUM_MULTIPLIER, self.ADAPTIVE_CUM_FLOOR)

        # ── Classify candles ──
        doji_threshold = current_price * 0.0001  # 0.01% of price
        green_count = 0
        red_count = 0
        cumulative_move = 0.0
        candle_sizes: list[float] = []
        candle_volumes: list[float] = []

        for candle in completed:
            o, c, vol = float(candle[1]), float(candle[4]), float(candle[5])
            move = c - o
            cumulative_move += move
            candle_sizes.append(abs(move) / o * 100 if o > 0 else 0.0)
            candle_volumes.append(vol)

            if abs(move) < doji_threshold:
                continue
            if move > 0:
                green_count += 1
            else:
                red_count += 1

        n = self.CANDLE_MOM_LOOKBACK  # 5

        # ── DIRECTION: 3 of 5 candles must agree ──
        if green_count >= self.CANDLE_MOM_STREAK:
            side = "long"
            directional_count = green_count
        elif red_count >= self.CANDLE_MOM_STREAK:
            side = "short"
            directional_count = red_count
        else:
            return (
                False,
                f"{green_count}/{n} green, {red_count}/{n} red — no clear direction → SKIP",
                None, 0, 0.0, candle_sizes,
            )

        # Last candle color (informational only — no longer required to match direction)
        last_o, last_c = float(completed[-1][1]), float(completed[-1][4])
        last_move = last_c - last_o

        # ── Cumulative move (direction-aware) ──
        cum_pct = (cumulative_move / current_price) * 100
        if side == "short":
            cum_pct = -cum_pct

        # ── VOLUME CONFIRMATION: entry candles must spike ──
        avg_vol = mean(self._candle_volumes) if len(self._candle_volumes) >= 5 else 0
        entry_vol_candles = candle_volumes[-self.VOLUME_CONFIRM_CANDLES:]
        entry_vol = mean(entry_vol_candles) if entry_vol_candles else 0
        vol_ratio = entry_vol / avg_vol if avg_vol > 0 else 0
        vol_ok = avg_vol <= 0 or entry_vol >= avg_vol * self.VOLUME_CONFIRM_MULTIPLIER

        # ── ACCELERATION: are recent candles bigger? ──
        accel_ok = True
        if len(candle_sizes) >= 4:
            recent_avg = mean(candle_sizes[-2:])
            earlier_avg = mean(candle_sizes[:2])
            if earlier_avg > 0 and recent_avg < earlier_avg * 0.3:
                accel_ok = False  # move is fading, not building

        # ── Build result ──
        color = "green" if side == "long" else "red"
        last_color = "green" if last_move > doji_threshold else ("red" if last_move < -doji_threshold else "doji")

        passed = (
            cum_pct >= cum_threshold
            and vol_ok
            and accel_ok
        )

        if passed:
            reason = (
                f"ADAPTIVE_GATE: {directional_count}/{n} {color}, "
                f"cum={cum_pct:+.2f}% vs {self.ADAPTIVE_CUM_MULTIPLIER}x avg_range={cum_threshold:.2f}%, "
                f"vol={vol_ratio:.1f}x, last={last_color} → PASS"
            )
        else:
            parts = [f"{directional_count}/{n} {color}"]
            if cum_pct < cum_threshold:
                parts.append(f"cum={cum_pct:+.2f}% < adaptive {cum_threshold:.2f}%")
            if not vol_ok:
                parts.append(f"LOW_VOLUME: {entry_vol:.0f} < {self.VOLUME_CONFIRM_MULTIPLIER}x avg {avg_vol:.0f}")
            if not accel_ok:
                parts.append("FADING_MOVE: recent candles shrinking")
            reason = "ADAPTIVE_GATE: " + ", ".join(parts) + " → SKIP"

        return passed, reason, side if passed else None, directional_count, cum_pct, candle_sizes

    # ==================================================================
    # RATCHET FLOOR
    # ==================================================================

    def _update_opt_ratchet_floor(self, pnl_pct: float) -> None:
        """Ratchet profit floor — one-way lock based on premium peak."""
        for threshold, floor in self.OPT_RATCHET_FLOOR_TABLE:
            if pnl_pct >= threshold and floor > self._opt_ratchet_floor:
                self.logger.info(
                    "[%s] RATCHET FLOOR ↑ pnl +%.1f%% ≥ %+.0f%% → floor locked at +%.1f%%",
                    self.option_symbol, pnl_pct, threshold, floor,
                )
                self._opt_ratchet_floor = floor

    # ==================================================================
    # EXIT LOGIC
    # ==================================================================

    async def _check_option_exit(self) -> list[Signal]:
        """Check exit conditions for open option position.

        Phase 1 (first 30s after fill): SL + ENTRY_DROP fire.
        After Phase 1:
        1. Expiry: Close 2 hours before expiry
        2a. Ratchet floor: lock profit floor as premium rises
        2b. SL: -50% premium drop (always active)
        2b2. Entry Drop: -8% in first 60s → bad entry, cut fast
        2b3. Fast Dead Momentum: <1% move at 60s, <2% at 90s (skip if peak >+5%)
        3. Momentum Fade: losing + momentum dying → exit
        3b. Dead Momentum: flat + momentum dead 60s + held 3min → backstop
        4. Dead Momentum (severe): losing >5% + momentum dead + held 5min
        5. TP: +30% premium gain
        6-7. Trailing: tiered activation
        8. Pullback: exit if lost 40% of peak gain (when peak was 8%+)
        9. Decay: exit if was +10%+ and faded to +3%
        10. Timeout: close after 10 minutes (only if decaying)
        11. Signal reversal: opposite momentum
        """
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
            self._consecutive_ticker_failures = 0  # reset on success
            if current_premium > 0:
                self._last_known_premium = current_premium  # track for POSITION_GONE exit
        except Exception as e:
            self._consecutive_ticker_failures += 1
            now_utc = datetime.now(timezone.utc)

            # Near/past expiry + ticker fail → treat as expired (position gone)
            if self.expiry_dt:
                mins_to_expiry = (self.expiry_dt - now_utc).total_seconds() / 60
                if mins_to_expiry <= self._EXPIRY_CLOSE_MINUTES:
                    self.logger.warning(
                        "[%s] Ticker failed near expiry (%.1f min) — marking POSITION_GONE",
                        self.option_symbol, mins_to_expiry,
                    )
                    return await self._handle_position_gone("EXPIRED_TICKER_FAIL")

            # Too many consecutive failures → position likely delisted/gone
            if self._consecutive_ticker_failures >= self._MAX_TICKER_FAILURES:
                self.logger.warning(
                    "[%s] %d consecutive ticker failures — marking POSITION_GONE",
                    self.option_symbol, self._consecutive_ticker_failures,
                )
                return await self._handle_position_gone("TICKER_FAIL_REPEATED")

            self.logger.warning(
                "[%s] Failed to fetch option ticker (%d/%d): %s",
                self.option_symbol, self._consecutive_ticker_failures,
                self._MAX_TICKER_FAILURES, e,
            )
            return []

        if current_premium <= 0:
            # May have expired worthless
            if self.expiry_dt and datetime.now(timezone.utc) >= self.expiry_dt:
                return await self._do_option_exit(0, -100.0, "EXPIRED_WORTHLESS")
            return []

        # Track peak premium
        self.highest_premium = max(self.highest_premium, current_premium)

        # Update ratchet floor immediately on every premium fetch
        # (don't wait for exit check — short spikes could be missed)
        self._update_opt_ratchet_floor(
            (self.highest_premium - self.entry_premium) / self.entry_premium * 100
            if self.entry_premium > 0 else 0
        )

        # Write position state to trades table every tick (~10s)
        # so dashboard shows live P&L for options positions
        await self._update_position_state_in_db(current_premium)

        # P&L
        premium_change_pct = (
            (current_premium - self.entry_premium) / self.entry_premium * 100
        ) if self.entry_premium > 0 else 0

        peak_pnl_pct = (
            (self.highest_premium - self.entry_premium) / self.entry_premium * 100
        ) if self.entry_premium > 0 else 0

        hold_seconds = time.monotonic() - self.entry_time
        in_phase1 = hold_seconds < self.PHASE1_HANDS_OFF_SEC

        # Heartbeat (every ~60s)
        if self._tick_count % 6 == 0:
            trail_tag = " [TRAILING]" if self._trailing_active else ""
            phase_tag = " [PHASE1]" if in_phase1 else ""
            self.logger.info(
                "[%s] %s | $%.4f → $%.4f (%+.1f%%) | peak=$%.4f (+%.1f%%) | %ds%s%s",
                self.option_symbol, self.option_side,
                self.entry_premium, current_premium, premium_change_pct,
                self.highest_premium, peak_pnl_pct,
                int(hold_seconds), trail_tag, phase_tag,
            )

        # ── 1. EXPIRY GUARD: protect against holding to $0 ───────────
        if self.expiry_dt:
            time_to_expiry = (self.expiry_dt - datetime.now(timezone.utc)).total_seconds()
            mins_to_expiry = time_to_expiry / 60
            if mins_to_expiry <= self.EXPIRY_GUARD_MIN_MIN:
                # < 30 min — always exit, theta will eat us
                self.logger.info(
                    "[%s] EXPIRY_GUARD: %s expires in %.0fm < %dm → EXIT regardless of P&L",
                    self.option_symbol, self.option_symbol, mins_to_expiry, self.EXPIRY_GUARD_MIN_MIN,
                )
                return await self._do_option_exit(current_premium, premium_change_pct, "EXPIRY_GUARD")
            elif mins_to_expiry <= self.EXPIRY_GUARD_HOURS * 60 and premium_change_pct < 10.0:
                # < 2h AND not sufficiently profitable — exit before decay accelerates
                self.logger.info(
                    "[%s] EXPIRY_GUARD: %s expires in %.0fm, pnl=%.1f%% < +10%% → EXIT",
                    self.option_symbol, self.option_symbol, mins_to_expiry, premium_change_pct,
                )
                return await self._do_option_exit(current_premium, premium_change_pct, "EXPIRY_GUARD")

        # ── Ratchet floor update (always, before any exit checks) ─────
        # Use PEAK pnl, not current — so the floor locks even if price has already dropped
        self._update_opt_ratchet_floor(peak_pnl_pct)

        # ── 2b2. ENTRY DROP: premium drops 8%+ within first 60s → bad entry ──
        # Runs first in Phase 1 so it catches bad entries before SL/ratchet.
        if hold_seconds <= 60 and premium_change_pct <= -8.0:
            self.logger.info(
                "[%s] OPT_ENTRY_DROP: entry=$%.4f current=$%.4f drop=%.1f%% after %.0fs",
                self.option_symbol, self.entry_premium, current_premium,
                premium_change_pct, hold_seconds,
            )
            return await self._do_option_exit(current_premium, premium_change_pct, "OPT_ENTRY_DROP")

        # ── 2a. RATCHET EXIT: premium fell below locked floor ─────────
        if self._opt_ratchet_floor != 0.0 and premium_change_pct < self._opt_ratchet_floor:
            self.logger.info(
                "[%s] OPT_RATCHET — pnl +%.1f%% fell below floor +%.1f%%",
                self.option_symbol, premium_change_pct, self._opt_ratchet_floor,
            )
            return await self._do_option_exit(current_premium, premium_change_pct, "OPT_RATCHET")

        # ── 2b. STOP LOSS: -50% premium drop (always active, even Phase 1)
        if premium_change_pct <= -self.SL_PREMIUM_LOSS_PCT:
            self.logger.info(
                "[%s] OPTION SL — premium %+.1f%% ($%.4f → $%.4f)",
                self.option_symbol, premium_change_pct,
                self.entry_premium, current_premium,
            )
            return await self._do_option_exit(current_premium, premium_change_pct, "OPT_SL")

        # ── Phase 1 hands-off: only SL + ENTRY_DROP fire in first 30s ─────
        if in_phase1:
            return []

        # ── 2c. PEAK TRAIL: once peak exceeds +8%, trail 35% behind ──
        # Gate: only trail-exit if gross P&L exceeds estimated fees × 1.5,
        # otherwise we lock in fee-losing "wins". Exception: peak >+15% always exits.
        if peak_pnl_pct >= 8.0:
            trail_floor_pct = peak_pnl_pct * 0.65
            if premium_change_pct <= trail_floor_pct:
                multiplier = self.CONTRACT_MULTIPLIER.get(self._base_asset, 0.01)
                spot = self._last_spot_price or (current_premium * (200 if self._base_asset == "BTC" else 100))
                estimated_fees = 2 * (self._contracts * multiplier * spot * 0.000118)
                gross_pnl = self._calc_options_pnl(self.entry_premium, current_premium, self._contracts)

                if peak_pnl_pct < 15.0 and gross_pnl < estimated_fees * 1.5:
                    self.logger.info(
                        "[%s] OPT_PEAK_TRAIL skipped — gross=$%.4f < fees*1.5=$%.4f (peak +%.1f%%)",
                        self.option_symbol, gross_pnl, estimated_fees * 1.5, peak_pnl_pct,
                    )
                else:
                    self.logger.info(
                        "[%s] OPT_PEAK_TRAIL — peak +%.1f%%, floor +%.1f%%, now +%.1f%%",
                        self.option_symbol, peak_pnl_pct, trail_floor_pct, premium_change_pct,
                    )
                    return await self._do_option_exit(current_premium, premium_change_pct, "OPT_PEAK_TRAIL")

        # ── 3. TAKE PROFIT: +30% premium gain ────────────────────────
        if premium_change_pct >= self.TP_PREMIUM_GAIN_PCT:
            self.logger.info(
                "[%s] OPTION TP — premium +%.1f%% ($%.4f → $%.4f)",
                self.option_symbol, premium_change_pct,
                self.entry_premium, current_premium,
            )
            return await self._do_option_exit(current_premium, premium_change_pct, "TP")

        # ── 6. TIERED TRAILING: activate at +10%, tighten as profit grows ──
        # Find the active trail tier based on peak premium pct
        trail_distance = 0.0
        for tier_pct, tier_dist in self.OPT_TRAIL_TIERS:
            if peak_pnl_pct >= tier_pct:
                trail_distance = tier_dist
        if trail_distance > 0 and not self._trailing_active:
            self._trailing_active = True
            self.logger.info(
                "[%s] OPTION TRAIL ON at +%.1f%% (distance=%.1f%%)",
                self.option_symbol, premium_change_pct, trail_distance,
            )

        # ── 7. TRAILING STOP: distance% below peak premium ──────────
        if self._trailing_active and trail_distance > 0:
            trail_floor = self.highest_premium * (1 - trail_distance / 100)
            if current_premium <= trail_floor:
                final_pct = (current_premium - self.entry_premium) / self.entry_premium * 100
                self.logger.info(
                    "[%s] OPTION TRAIL HIT — peak=$%.4f floor=$%.4f now=$%.4f (dist=%.1f%%)",
                    self.option_symbol, self.highest_premium, trail_floor, current_premium, trail_distance,
                )
                return await self._do_option_exit(current_premium, final_pct, "OPT_TRAIL")

        # ── 6. PULLBACK: exit if lost 40% of peak gain (peak was 8%+)
        if peak_pnl_pct >= self.PULLBACK_ACTIVATE_PCT and premium_change_pct > 0:
            pct_of_peak_lost = ((peak_pnl_pct - premium_change_pct) / peak_pnl_pct) * 100
            if pct_of_peak_lost >= self.PULLBACK_EXIT_PCT:
                self.logger.info(
                    "[%s] OPTION PULLBACK — peak +%.1f%% now +%.1f%% (lost %.0f%% of gain)",
                    self.option_symbol, peak_pnl_pct, premium_change_pct, pct_of_peak_lost,
                )
                return await self._do_option_exit(current_premium, premium_change_pct, "PULLBACK")

        # ── 7. DECAY: was +10%+ and faded to +3% ─────────────────────
        if peak_pnl_pct >= 10.0 and premium_change_pct <= self.DECAY_THRESHOLD_PCT:
            self.logger.info(
                "[%s] OPTION DECAY — peak +%.1f%% faded to +%.1f%% (threshold +%.1f%%)",
                self.option_symbol, peak_pnl_pct, premium_change_pct, self.DECAY_THRESHOLD_PCT,
            )
            return await self._do_option_exit(current_premium, premium_change_pct, "DECAY")

        # ── 8. PROGRESSIVE SL TIGHTENING: stale trade protection ────
        # Gate: only fires when premium hasn't moved (< 5% from entry in either direction)
        # AND peak was never meaningful (< +10%) AND currently not winning.
        # If it moved and came back, trail/ratchet should have caught it — don't interfere.
        abs_move_pct = abs(premium_change_pct)
        is_stale = (
            abs_move_pct < self.STALE_MOVE_THRESHOLD
            and peak_pnl_pct < 10.0
            and premium_change_pct <= 0.0
        )
        if is_stale:
            hold_min = hold_seconds / 60
            _is_btc = self._base_asset == "BTC"
            if _is_btc:
                if hold_min >= self.STALE_EXIT_MIN_BTC:
                    self.logger.info(
                        "[%s] OPT_STALE: %.0fm no movement (move=%.1f%%, peak=%.1f%%) → EXIT",
                        self.option_symbol, hold_min, premium_change_pct, peak_pnl_pct,
                    )
                    return await self._do_option_exit(current_premium, premium_change_pct, "OPT_STALE")
                elif hold_min >= 12.0 and premium_change_pct < self.STALE_SL_12M_BTC:
                    self.logger.info(
                        "[%s] SL_TIGHTEN: 12m stale, SL → %.0f%% (now %.1f%%)",
                        self.option_symbol, self.STALE_SL_12M_BTC, premium_change_pct,
                    )
                    return await self._do_option_exit(current_premium, premium_change_pct, "OPT_STALE_SL")
                elif hold_min >= 8.0 and premium_change_pct < self.STALE_SL_8M_BTC:
                    self.logger.info(
                        "[%s] SL_TIGHTEN: 8m stale, SL → %.0f%% (now %.1f%%)",
                        self.option_symbol, self.STALE_SL_8M_BTC, premium_change_pct,
                    )
                    return await self._do_option_exit(current_premium, premium_change_pct, "OPT_STALE_SL")
            else:
                if hold_min >= self.STALE_EXIT_MIN_ETH:
                    self.logger.info(
                        "[%s] OPT_STALE: %.0fm no movement (move=%.1f%%, peak=%.1f%%) → EXIT",
                        self.option_symbol, hold_min, premium_change_pct, peak_pnl_pct,
                    )
                    return await self._do_option_exit(current_premium, premium_change_pct, "OPT_STALE")
                elif hold_min >= 8.0 and premium_change_pct < self.STALE_SL_8M_ETH:
                    self.logger.info(
                        "[%s] SL_TIGHTEN: 8m stale, SL → %.0f%% (now %.1f%%)",
                        self.option_symbol, self.STALE_SL_8M_ETH, premium_change_pct,
                    )
                    return await self._do_option_exit(current_premium, premium_change_pct, "OPT_STALE_SL")
                elif hold_min >= 5.0 and premium_change_pct < self.STALE_SL_5M_ETH:
                    self.logger.info(
                        "[%s] SL_TIGHTEN: 5m stale, SL → %.0f%% (now %.1f%%)",
                        self.option_symbol, self.STALE_SL_5M_ETH, premium_change_pct,
                    )
                    return await self._do_option_exit(current_premium, premium_change_pct, "OPT_STALE_SL")

        # ── 9. SIGNAL REVERSAL ────────────────────────────────────────
        if self._scalp and hasattr(self._scalp, "last_signal_state"):
            ss = self._scalp.last_signal_state
            if ss:
                new_side = ss.get("side")
                new_strength = ss.get("strength", 0)
                signal_age = time.monotonic() - ss.get("timestamp", 0)

                if (signal_age < self.SIGNAL_STALENESS_SEC
                        and new_strength >= self.MIN_SIGNAL_STRENGTH
                        and new_side is not None):
                    is_reversal = (
                        (self.option_side == "call" and new_side == "short")
                        or (self.option_side == "put" and new_side == "long")
                    )
                    if is_reversal:
                        self.logger.info(
                            "[%s] SIGNAL REVERSAL — %s → opposite %s at %+.1f%%",
                            self.option_symbol, self.option_side,
                            new_side, premium_change_pct,
                        )
                        return await self._do_option_exit(
                            current_premium, premium_change_pct, "OPT_REVERSAL",
                        )

        return []

    # ==================================================================
    # OPTIONS DB WRITE (entry + close, bypasses trade_executor P&L)
    # ==================================================================

    async def _write_entry_to_db(self, fill_price: float, contracts: int,
                                  order: dict, signal, option_symbol: str,
                                  option_side: str, strike_price: float,
                                  base_asset: str):
        """Insert a new options trade row into the DB, then update with actual fill price.

        Step 1: Insert with entry_price=0 (placeholder).
        Step 2: Fetch actual execution price from exchange via fetch_order.
        Step 3: UPDATE the row with the real fill price.
        """
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
                "setup_type": "MOMENTUM_BURST",
                "signals_fired": f"option_side={option_side} " + getattr(self, '_entry_signals_fired', ''),
                "opened_at": datetime.utcnow().isoformat() + "Z",
            }

            result = self.executor.db.client.table("trades").insert(row).execute()
            if result.data:
                self._db_trade_id = result.data[0].get("id")
            else:
                self.logger.error("[%s] OPTIONS DB ENTRY returned no data", option_symbol)
                return

            # ── Step 2: Resolve actual execution price from exchange ──
            signal_price = getattr(signal, "price", 0) or 0
            actual_fill = await self._resolve_fill_price(order, option_symbol)

            if actual_fill and actual_fill > 0:
                collateral = actual_fill * contracts / self.OPTIONS_LEVERAGE
                self.executor.db.client.table("trades").update({
                    "entry_price": round(actual_fill, 8),
                    "collateral": round(collateral, 4),
                }).eq("id", self._db_trade_id).execute()

                # Also update in-memory entry_premium so exit P&L uses correct price
                self.entry_premium = actual_fill
                self.highest_premium = max(self.highest_premium, actual_fill)

                self.logger.info(
                    "[%s] DB entry_price updated: signal=$%.4f fill=$%.4f id=%s x%d fee=$%.6f",
                    option_symbol, signal_price, actual_fill,
                    self._db_trade_id, contracts, entry_fee,
                )
            else:
                # Fallback: use fill_price from on_fill (order.average/price)
                collateral = fill_price * contracts / self.OPTIONS_LEVERAGE
                self.executor.db.client.table("trades").update({
                    "entry_price": round(fill_price, 8),
                    "collateral": round(collateral, 4),
                }).eq("id", self._db_trade_id).execute()
                self.logger.warning(
                    "[%s] DB entry_price FALLBACK: signal=$%.4f on_fill=$%.4f (fetch_order failed) id=%s",
                    option_symbol, signal_price, fill_price, self._db_trade_id,
                )
        except Exception:
            self.logger.exception("[%s] _write_entry_to_db FAILED", option_symbol)

    async def _resolve_fill_price(self, order: dict, symbol: str) -> float:
        """Get the actual execution price from the exchange.

        Tries order['average'] first, then fetches the order from exchange
        to get the definitive fill price. Returns 0 on failure.
        """
        order_id = order.get("id")

        # Try fetch_order for the definitive fill price
        if order_id and self.options_exchange:
            try:
                import asyncio
                await asyncio.sleep(1)  # brief delay for exchange settlement
                fetched = await self.options_exchange.fetch_order(order_id, symbol)
                avg = fetched.get("average")
                if avg and float(avg) > 0:
                    return float(avg)
                # Some exchanges put fill price in 'price' after order is closed
                if fetched.get("status") == "closed":
                    p = fetched.get("price")
                    if p and float(p) > 0:
                        return float(p)
            except Exception as e:
                self.logger.debug("[%s] fetch_order for fill price failed: %s", symbol, e)

        # Fall back to order dict from create_order response
        avg = order.get("average")
        if avg and float(avg) > 0:
            return float(avg)

        return 0

    async def _close_option_trade_in_db(
        self, exit_premium: float, exit_type: str,
        *, option_symbol: str | None = None,
        entry_premium: float = 0.0, highest_premium: float = 0.0,
        contracts: int = 0, order: dict | None = None,
    ) -> bool:
        """Close the option trade in DB with correct options P&L.

        Called from on_fill() after exchange confirms the exit.
        Volatile state (option_symbol, entry_premium, etc.) is passed
        explicitly since on_fill clears self.* after scheduling this task.
        Falls back to self.* when called from _handle_position_gone.
        """
        sym = option_symbol or self.option_symbol or self.pair

        # Resolve actual exit fill price from exchange (not limit order price)
        if order:
            resolved = await self._resolve_fill_price(order, sym)
            if resolved and resolved > 0:
                self.logger.info(
                    "[%s] DB exit_price updated: on_fill=$%.4f actual=$%.4f",
                    sym, exit_premium, resolved,
                )
                exit_premium = resolved
        ep = entry_premium or self.entry_premium
        hp = highest_premium or self.highest_premium
        ct = contracts or self._contracts

        if not self._db or not self._db.is_connected:
            return False

        try:
            from alpha.utils import iso_now

            # Use _db_trade_id if available (set by _write_entry_to_db)
            if self._db_trade_id:
                resp = self.executor.db.client.table("trades").select("*").eq(
                    "id", self._db_trade_id
                ).execute()
                open_trade = resp.data[0] if resp.data else None
            else:
                open_trade = await self._db.get_open_trade(
                    pair=sym, exchange="delta", strategy="options_scalp",
                )
            if not open_trade:
                self.logger.warning(
                    "[%s] _close_option_trade_in_db: no open trade found (db_id=%s)",
                    sym, self._db_trade_id,
                )
                return False

            db_entry = float(open_trade.get("entry_price", ep) or ep)
            db_contracts = int(open_trade.get("contracts") or open_trade.get("amount") or ct)

            # Delta fee = qty × contract_multiplier × spot_price × 0.000118
            multiplier = self.CONTRACT_MULTIPLIER.get(self._base_asset, 0.01)
            spot = self._last_spot_price or (exit_premium * (200 if self._base_asset == "BTC" else 100))
            calculated_fee = round(db_contracts * multiplier * spot * 0.000118, 8)

            # Entry fee: use DB value if reasonable, else recalculate
            stored_entry_fee = float(open_trade.get("entry_fee") or 0)
            entry_fee = stored_entry_fee if 0 < stored_entry_fee <= 0.10 else calculated_fee

            # Exit fee: always calculate from spot (most accurate at exit time)
            exit_fee = calculated_fee

            self.logger.info(
                "[%s] FEE CHECK: entry stored=$%.6f calc=$%.6f using=$%.6f | exit calc=$%.6f",
                sym, stored_entry_fee, calculated_fee, entry_fee, exit_fee,
            )

            gross_pnl = self._calc_options_pnl(db_entry, exit_premium, db_contracts)
            pnl_pct = (exit_premium - db_entry) / db_entry * 100 if db_entry > 0 else 0.0
            net_pnl = gross_pnl - entry_fee - exit_fee

            peak_pnl_pct = (hp - ep) / ep * 100 if ep > 0 else 0

            from alpha.trade_executor import _extract_exit_reason
            await self._db.update_trade(open_trade["id"], {
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
            })

            self.logger.info(
                "[%s] OPTIONS DB CLOSE: id=%s exit=$%.4f gross=$%.6f net=$%.6f (%.2f%%)",
                sym, open_trade["id"], exit_premium,
                gross_pnl, net_pnl, pnl_pct,
            )

            # Record for session tracking
            try:
                bot = getattr(self, "_alpha_bot", None)
                if bot and hasattr(bot, "record_session_trade"):
                    side_label = "CALL" if sym.endswith("-C") or sym.endswith("C") else "PUT"
                    bot.record_session_trade({
                        "pair": sym, "base": self._base_asset,
                        "side_label": side_label,
                        "net_pnl": net_pnl,
                        "fees": entry_fee + exit_fee,
                        "pnl": net_pnl,
                    })
            except Exception:
                pass  # non-critical

            # Telegram exit notification
            try:
                alerts = getattr(self.executor, "alerts", None)
                if alerts is not None:
                    pnl_emoji = "\u2705" if net_pnl >= 0 else "\u274c"
                    # Calculate hold time from DB opened_at
                    opened_at = open_trade.get("opened_at") or open_trade.get("created_at")
                    hold_time = "?"
                    if opened_at:
                        from datetime import datetime as _dt, timezone as _tz
                        try:
                            if isinstance(opened_at, str):
                                opened_at = _dt.fromisoformat(opened_at.replace("Z", "+00:00"))
                            delta = _dt.now(_tz.utc) - opened_at
                            mins = int(delta.total_seconds() // 60)
                            hold_time = f"{mins}m" if mins < 60 else f"{mins // 60}h{mins % 60}m"
                        except Exception:
                            pass
                    option_side = open_trade.get("side", "buy")
                    # Derive call/put from symbol (ends with -C or -P)
                    side_label = "CALL" if sym.endswith("-C") or sym.endswith("C") else "PUT"
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
                "[%s] _close_option_trade_in_db failed", sym,
            )
            return False

    # ==================================================================
    # EXIT SIGNAL BUILDER
    # ==================================================================

    async def _do_option_exit(
        self, current_premium: float, pnl_pct: float, exit_type: str,
    ) -> list[Signal]:
        """Build exit signal for option position."""
        # Fetch fresh live bid before exit — use for P&L and Signal price
        try:
            ticker = await self.options_exchange.fetch_ticker(self.option_symbol)
            live_bid = ticker.get("bid") or ticker.get("last") or 0
            if live_bid > 0:
                self.logger.info(
                    "[%s] LIVE_BID: $%.4f (cached=$%.4f, diff=%+.2f%%)",
                    self.option_symbol, live_bid, current_premium,
                    (live_bid - current_premium) / current_premium * 100 if current_premium > 0 else 0,
                )
                current_premium = live_bid
                if self.entry_premium > 0:
                    pnl_pct = (current_premium - self.entry_premium) / self.entry_premium * 100
        except Exception as e:
            self.logger.debug("[%s] Live bid fetch failed, using cached: %s", self.option_symbol, e)

        pnl_usd = self._calc_options_pnl(self.entry_premium, current_premium, self._contracts)
        reason = (
            f"Option {exit_type} {self.option_side} | "
            f"${self.entry_premium:.4f} → ${current_premium:.4f} "
            f"({pnl_pct:+.1f}%) P&L=${pnl_usd:+.4f}"
        )
        self.logger.info("[%s] OPTIONS EXIT — %s", self.option_symbol, reason)

        # Log to activity_log for dashboard
        pnl_tag = f"+${pnl_usd:.4f}" if pnl_usd >= 0 else f"-${abs(pnl_usd):.4f}"
        await self._log_activity(
            "options_exit",
            f"{self.pair} — OPTIONS EXIT: {exit_type} {self.option_side} | "
            f"${self.entry_premium:.4f} -> ${current_premium:.4f} ({pnl_pct:+.1f}%) {pnl_tag}",
            {"exit_type": exit_type, "option_side": self.option_side,
             "entry_premium": self.entry_premium, "exit_premium": current_premium,
             "pnl_pct": round(pnl_pct, 2), "pnl_usd": round(pnl_usd, 4),
             "strike": self.strike_price, "symbol": self.option_symbol},
        )

        # Reset ratchet state
        self._opt_ratchet_floor = 0.0

        # Stats tracking
        if pnl_pct >= 0:
            self.hourly_wins += 1
        else:
            self.hourly_losses += 1
        self.hourly_pnl += pnl_usd

        # Immediately clear dashboard position state so UI doesn't show stale "OPEN"
        await self._clear_dashboard_position(exit_type, pnl_pct, pnl_usd)

        # Peak P&L for DB — executor writes it to peak_pnl column
        peak_pnl_pct = (
            (self.highest_premium - self.entry_premium) / self.entry_premium * 100
        ) if self.entry_premium > 0 else 0

        # DB close happens in on_fill() AFTER exchange fills with actual price
        return [Signal(
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
        )]

    async def _verify_option_position(self) -> list[Signal] | None:
        """Check exchange positions to detect if option is still open.

        Called every 3rd tick (~30s). Returns _handle_position_gone result
        if position no longer exists, or None to continue normal exit checks.
        """
        if not self.options_exchange or not self.option_symbol:
            return None

        try:
            positions = await self.options_exchange.fetch_positions()
            self._position_verify_failures = 0  # reset on success
            for pos in positions:
                symbol = pos.get("symbol", "")
                contracts = float(pos.get("contracts", 0) or 0)
                if symbol == self.option_symbol and contracts != 0:
                    return None  # Position still exists — all good

            # Position not found on exchange
            now_utc = datetime.now(timezone.utc)
            if self.expiry_dt:
                mins_to_expiry = (self.expiry_dt - now_utc).total_seconds() / 60
                if mins_to_expiry <= self._EXPIRY_CLOSE_MINUTES:
                    self.logger.warning(
                        "[%s] POSITION VERIFY: not found, near expiry (%.1f min) — EXPIRY",
                        self.option_symbol, mins_to_expiry,
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
                self.option_symbol, self._position_verify_failures,
                self._MAX_VERIFY_FAILURES, e,
            )
            # After repeated failures, force-close — API is down or position is gone
            if self._position_verify_failures >= self._MAX_VERIFY_FAILURES:
                self.logger.error(
                    "[%s] POSITION VERIFY: %d consecutive failures — forcing POSITION_GONE",
                    self.option_symbol, self._position_verify_failures,
                )
                return await self._handle_position_gone("VERIFY_API_FAIL")
            return None

    async def _handle_position_gone(self, reason: str) -> list[Signal]:
        """Handle a position that no longer exists on exchange.

        Determines if the contract expired or vanished unexpectedly.
        Uses last known premium as exit price, marks trade closed in DB,
        sends Telegram alert, applies 60s cooldown. No retry.
        """
        # Determine if this is an expiry or unexpected disappearance
        is_expiry = False
        if self.expiry_dt:
            time_past_expiry = (datetime.now(timezone.utc) - self.expiry_dt).total_seconds()
            is_expiry = time_past_expiry >= 0  # at or past expiry time

        exit_reason = "EXPIRY" if is_expiry else "POSITION_GONE"
        exit_reason_detail = f"{exit_reason}_{reason}" if reason else exit_reason

        # Use last known premium as exit price (tracked every tick)
        exit_premium = self._last_known_premium
        if exit_premium <= 0:
            exit_premium = self.entry_premium * 0.5 if self.entry_premium > 0 else 0.0

        # For expired contracts that went to zero, use 0
        if is_expiry and reason == "EXPIRED_TICKER_FAIL":
            exit_premium = 0.0

        self.logger.info(
            "[%s] %s (%s) — exit_premium=$%.4f (last_known=$%.4f entry=$%.4f)",
            self.option_symbol, exit_reason, reason,
            exit_premium, self._last_known_premium, self.entry_premium,
        )

        # Calculate P&L using contract multiplier (never use trade_executor's calc_pnl)
        pnl_pct = 0.0
        pnl_usd = 0.0
        if self.entry_premium > 0:
            pnl_pct = (exit_premium - self.entry_premium) / self.entry_premium * 100
            pnl_usd = self._calc_options_pnl(self.entry_premium, exit_premium, self._contracts)

        # Mark trade closed in DB directly (no exchange order needed)
        if self._db:
            try:
                from alpha.utils import iso_now
                open_trade = await self._db.get_open_trade(
                    pair=self.option_symbol or self.pair,
                    exchange="delta",
                    strategy="options_scalp",
                )
                if open_trade:
                    entry_price = float(open_trade.get("entry_price", self.entry_premium) or self.entry_premium)
                    contracts = int(open_trade.get("contracts") or open_trade.get("amount") or self._contracts)
                    # Delta fee = qty × contract_multiplier × spot_price × 0.000118
                    multiplier = self.CONTRACT_MULTIPLIER.get(self._base_asset, 0.01)
                    spot = self._last_spot_price or (exit_premium * (200 if self._base_asset == "BTC" else 100))
                    calculated_fee = round(contracts * multiplier * spot * 0.000118, 8)

                    stored_entry_fee = float(open_trade.get("entry_fee") or 0)
                    entry_fee = stored_entry_fee if 0 < stored_entry_fee <= 0.10 else calculated_fee
                    exit_fee = calculated_fee  # position gone = no exchange fee, use calculated

                    gross_pnl = self._calc_options_pnl(entry_price, exit_premium, contracts)
                    net_pnl = gross_pnl - entry_fee - exit_fee
                    db_pnl_pct = (exit_premium - entry_price) / entry_price * 100 if entry_price > 0 else 0.0

                    # Peak P&L from tracked highest premium
                    peak_pnl_val = (
                        (self.highest_premium - self.entry_premium) / self.entry_premium * 100
                    ) if self.entry_premium > 0 else 0

                    await self._db.update_trade(open_trade["id"], {
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
                    })
                    pnl_pct = db_pnl_pct
                    pnl_usd = net_pnl
                    self.logger.info(
                        "[%s] Trade %s closed as %s — exit=$%.4f P&L=$%.4f (%.2f%%)",
                        self.option_symbol, open_trade["id"], exit_reason,
                        exit_premium, net_pnl, db_pnl_pct,
                    )
                else:
                    self.logger.info(
                        "[%s] No open trade found in DB — already closed", self.option_symbol,
                    )
            except Exception:
                self.logger.exception("[%s] Failed to close trade as %s", self.option_symbol, exit_reason)

        # Send Telegram alert
        try:
            alerts = getattr(self.executor, "alerts", None)
            if alerts is not None:
                pair_short = self._base_asset
                pnl_tag = f"+${pnl_usd:.4f}" if pnl_usd >= 0 else f"-${abs(pnl_usd):.4f}"
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
            self.logger.debug("[%s] Failed to send %s Telegram alert", self.option_symbol, exit_reason)

        # Log to activity feed
        await self._log_activity(
            f"options_{exit_reason.lower()}",
            f"{self.pair} — OPTIONS {exit_reason}: {reason} | "
            f"{self.option_side} strike=${self.strike_price:.0f} | "
            f"exit=${exit_premium:.4f} P&L={pnl_pct:+.1f}% ${pnl_usd:+.4f}",
            {"reason": reason, "exit_reason": exit_reason,
             "option_side": self.option_side,
             "strike": self.strike_price, "symbol": self.option_symbol,
             "exit_premium": exit_premium,
             "pnl_pct": round(pnl_pct, 2), "pnl_usd": round(pnl_usd, 4)},
        )

        # Stats tracking
        if pnl_pct >= 0:
            self.hourly_wins += 1
        else:
            self.hourly_losses += 1
        self.hourly_pnl += pnl_usd

        # Clear dashboard + position state
        await self._clear_dashboard_position(exit_reason_detail, pnl_pct, pnl_usd)

        # Apply 60s cooldown before next options entry
        self._position_gone_cooldown_until = time.monotonic() + self._POSITION_GONE_COOLDOWN_SEC
        self.logger.info(
            "[%s] %s cooldown: no new options entries for %ds",
            self.pair, exit_reason, self._POSITION_GONE_COOLDOWN_SEC,
        )

        # Clear all position state — no retry, we're done
        self.in_position = False
        OptionsScalpStrategy._global_in_position = False  # release global lock
        OptionsScalpStrategy._global_position_asset = None
        self.option_side = None
        self.option_symbol = None
        self.entry_premium = 0.0
        self.highest_premium = 0.0
        self._last_known_premium = 0.0
        self._trailing_active = False
        self.strike_price = 0.0
        self.expiry_dt = None
        self._consecutive_ticker_failures = 0
        self._position_verify_failures = 0
        self._last_state_write = 0.0

        return []  # No signal needed — handled directly in DB

    async def _clear_dashboard_position(
        self, exit_type: str = "", pnl_pct: float = 0.0, pnl_usd: float = 0.0,
    ) -> None:
        """Write a final options_state update that clears all position fields.

        Called on exit so the dashboard immediately shows 'No Position'
        instead of stale 'CALL OPEN'.
        """
        if not self._db:
            return

        # Build state with position fields explicitly nulled
        # Keep market data (spot, expiry, premiums) intact for display
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
            "expiry": self._selected_expiry.isoformat() if self._selected_expiry else None,
            "expiry_label": None,
            "atm_strike": None,
            "call_premium": None,
            "put_premium": None,
            "signal_strength": signal_strength,
            "signal_side": signal_side,
            "signal_reason": signal_reason,
            # Position fields: ALL cleared
            "position_side": None,
            "position_strike": None,
            "position_symbol": None,
            "entry_premium": None,
            "current_premium": None,
            "pnl_pct": None,
            "pnl_usd": None,
            "trailing_active": False,
            "highest_premium": None,
            # Exit info for dashboard (last exit summary)
            "last_exit_type": exit_type,
            "last_exit_pnl_pct": round(pnl_pct, 2),
            "last_exit_pnl_usd": round(pnl_usd, 4),
        }

        try:
            await self._db.upsert_options_state(self.pair, state)
            self.logger.info(
                "[%s] Dashboard options state cleared (exit=%s pnl=%+.1f%%)",
                self.pair, exit_type, pnl_pct,
            )
        except Exception as e:
            self.logger.warning("[%s] Failed to clear dashboard options state: %s", self.pair, e)

    # ==================================================================
    # CALLBACKS
    # ==================================================================

    def on_fill(self, signal: Signal, order: dict) -> None:
        """Track option position state on fill."""
        pending_side = signal.metadata.get("pending_side")
        if pending_side:
            # Entry fill — prefer order['average'] (actual execution price).
            # order['price'] may be the limit order price, NOT the fill price.
            # _write_entry_to_db will fetch_order for the definitive price.
            fill_price = order.get("average") or order.get("price") or 0
            fill_price = float(fill_price) if fill_price else 0
            if not fill_price:
                self.logger.error("[%s] NO FILL PRICE from exchange — skipping on_fill", signal.pair)
                return
            self.in_position = True
            OptionsScalpStrategy._global_in_position = True  # global lock
            OptionsScalpStrategy._global_position_asset = self._base_asset
            self.option_side = pending_side
            self.option_symbol = signal.pair
            self.entry_premium = fill_price
            self.entry_time = time.monotonic()
            self.highest_premium = fill_price
            self._last_known_premium = fill_price
            self._trailing_active = False
            self._consecutive_ticker_failures = 0
            # Reset ratchet state on entry
            self._opt_ratchet_floor = 0.0
            self.strike_price = signal.metadata.get("strike", 0)
            self._contracts = int(signal.metadata.get("contracts", 1) or 1)
            expiry_str = signal.metadata.get("expiry")
            if expiry_str:
                self.expiry_dt = datetime.fromisoformat(expiry_str)
            self.logger.info(
                "[%s] OPTION FILLED — %s x%d strike=$%.0f premium=$%.4f exp=%s",
                self.option_symbol, self.option_side, self._contracts,
                self.strike_price, fill_price,
                self.expiry_dt.strftime("%b %d %H:%M") if self.expiry_dt else "?",
            )
            self._db_trade_id = None  # reset; will be set by _write_entry_to_db

            # Telegram entry notification
            try:
                alerts = getattr(self.executor, "alerts", None)
                if alerts is not None:
                    import asyncio
                    collateral = fill_price * self._contracts / self.OPTIONS_LEVERAGE
                    _mult = self.CONTRACT_MULTIPLIER.get(self._base_asset, 0.01)
                    _spot = self._last_spot_price or signal.metadata.get("spot_price", 0)
                    _fee = round(self._contracts * _mult * _spot * 0.000118, 6) if _spot else 0
                    msg = (
                        f"\U0001f4e5 {self._base_asset} option opened\n"
                        f"{self.option_side.upper()} ${self.strike_price:.0f} | "
                        f"x{self._contracts} @ ${fill_price:.2f}\n"
                        f"Collateral: ${collateral:.2f} | Fee: ${_fee:.4f}"
                    )
                    asyncio.get_event_loop().create_task(alerts.send_text(msg))
            except Exception:
                pass

            # Write entry to DB
            import asyncio as _aio_entry
            _aio_entry.get_event_loop().create_task(
                self._write_entry_to_db(
                    fill_price, self._contracts, order, signal,
                    option_symbol=self.option_symbol,
                    option_side=self.option_side,
                    strike_price=self.strike_price,
                    base_asset=self._base_asset,
                )
            )
        else:
            # Exit fill — close trade in DB with actual fill price from exchange.
            # Prefer order['average'] (execution price). order['price'] may be
            # the limit order price, NOT the fill price.
            exit_fill = float(order.get("average") or order.get("price") or 0)
            if not exit_fill:
                self.logger.error("[%s] NO EXIT FILL PRICE from exchange — skipping", signal.pair)
                return
            exit_type = signal.metadata.get("exit_type", "UNKNOWN")
            self.logger.info(
                "[%s] OPTION EXIT FILLED — %s closed @ $%.4f",
                self.option_symbol or self.pair, self.option_side, exit_fill,
            )

            # Overwrite DB with correct options P&L using actual fill price.
            # Snapshot volatile state — create_task runs after we clear self.*
            _sym = self.option_symbol or self.pair
            _entry_prem = self.entry_premium
            _highest_prem = self.highest_premium
            _contracts = self._contracts
            _side = self.option_side
            _strike = self.strike_price
            _base = self._base_asset
            _order = dict(order)  # snapshot for async task

            if exit_fill > 0:
                import asyncio
                asyncio.get_event_loop().create_task(
                    self._close_option_trade_in_db(
                        exit_fill, exit_type,
                        option_symbol=_sym,
                        entry_premium=_entry_prem,
                        highest_premium=_highest_prem,
                        contracts=_contracts,
                        order=_order,
                    )
                )

            # Single Telegram notification sent from _close_option_trade_in_db
            # (has correct exchange-fill data, fees, hold time). No duplicate here.

            self.in_position = False
            OptionsScalpStrategy._global_in_position = False  # release global lock
            OptionsScalpStrategy._global_position_asset = None
            self.option_side = None
            self.option_symbol = None
            self.entry_premium = 0.0
            self.highest_premium = 0.0
            self._trailing_active = False
            self.strike_price = 0.0
            self.expiry_dt = None
            self._contracts = 1
            self._db_trade_id = None
            # Force next check() to immediately write cleared state to dashboard
            self._last_state_write = 0.0

    def on_rejected(self, signal: Signal) -> None:
        """Handle rejected option orders.

        For entry: just log (no state to clear).
        For exit: clear in_position so we don't keep generating exit signals
        for a position the exchange no longer has. The trade was already
        marked closed in DB by _mark_position_gone.
        """
        pending_side = signal.metadata.get("pending_side")
        if pending_side:
            self.logger.warning(
                "[%s] Option entry REJECTED — not tracking", signal.pair,
            )
        elif signal.reduce_only and self.in_position:
            # Exit was rejected (position likely already gone on exchange)
            self.logger.warning(
                "[%s] Option EXIT rejected — clearing in_position (position likely closed externally)",
                self.option_symbol or signal.pair,
            )
            self.in_position = False
            OptionsScalpStrategy._global_in_position = False  # release global lock
            OptionsScalpStrategy._global_position_asset = None
            self.option_side = None
            self.option_symbol = None
            self.entry_premium = 0.0
            self.highest_premium = 0.0
            self._trailing_active = False
            self.strike_price = 0.0
            self.expiry_dt = None
            self._last_state_write = 0.0  # Force dashboard state clear on next tick

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

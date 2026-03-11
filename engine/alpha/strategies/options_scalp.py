"""Alpha Options Scalp — Buy CALLs/PUTs on strong momentum signals.

═══════════════════════════════════════════════════════════════
 OPTION ENTRY SIGNAL — CURRENT FLOW (all gates must pass)
═══════════════════════════════════════════════════════════════

 1. REGIME GATE        CHOPPY blocked, all others allowed
 2. EARLY DIRECTION    2 of 3 candles directional + cumulative move threshold
                       BTC >= 0.15% | ETH >= 0.20% | last candle must match
 3. UNDERLYING MOVE    Price must move >= 0.10% in last ~60s
 4. EXPIRY             Nearest expiry (today preferred, min 1h to expiry)
 5. STRIKE SELECTION   Highest OI within ATM + 1-2 OTM (liquidity = premium moves)
 6. PREMIUM FLOOR      Min $5 premium (kills dead low-delta strikes)
 7. PREMIUM CAP        Max $40 premium (avoid low-gamma expensive options)
 8. PREMIUM CONFIRM    Dynamic wait (3s fast / 10s standard), must rise or hold ±0.5%
 9. LIMIT ENTRY        Place limit buy at ORIGINAL price, wait 15s for fill
                       If not filled → cancel and skip (no overpaying)
10. PULLBACK WAIT      Wait up to 15s for 3% premium dip before buying

 COOLDOWNS:
   - Trade cooldown: 2 min between trades
   - Dead market: 10 min after exit with 0% peak
   - Position gone: 60s after position disappears

 SIZING:
   - 3/3 candles → 50% allocation | 2/3 → 35%
   - BB_SQUEEZE → 60% factor on top
   - Survival mode: balance < $5 → max 5 contracts
   - BTC + ETH both enabled (50x leverage = tiny collateral)

═══════════════════════════════════════════════════════════════

Exit (DO NOT TOUCH):
  - Ratchet floor: lock profit at (10→3, 15→7, 25→15, 40→25, 100→70)%
  - SL: 50% premium loss (always active, even in Phase 1)
  - Momentum Fade: profitable + momentum < 0.02% for 60s → exit
  - Dead Momentum: losing + momentum dead 45s + held 3min → exit
  - TP: 30% premium gain
  - Trailing: activates at +15%, trails 5% behind peak
  - Timeout: 10 minutes (only if premium decaying)
  - Decay: exit if was +10%+ and faded to +3%
  - Phase 1 (first 30s): only SL fires

Risk: Max loss = premium paid. No liquidation. Safest momentum play.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
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
    # Candle-based early-direction gate (3/3 candles required)
    CANDLE_MOM_STREAK = 3                # ALL 3 candles must agree (was 2 — 2/3 had 27% WR, 3/3 had 40%)
    CANDLE_MOM_LOOKBACK = 3              # number of completed 1m candles to check
    # Per-asset cumulative thresholds (raised — 0.10% entries were noise)
    CANDLE_MOM_CUM_PCT_BTC = 0.20        # BTC: was 0.15 — winners had 0.20%+
    CANDLE_MOM_CUM_PCT_ETH = 0.15        # ETH: was 0.10 — 0.10% entries were noise
    MIN_UNDERLYING_MOVE_PCT = 0.10       # underlying must move >= 0.10% in last 60s
    MIN_UNDERLYING_MOVE_SECS = 60        # lookback window for underlying move check
    OPT_RSI_CALL_MAX = 40               # calls only when RSI < 40 (oversold conviction)
    OPT_RSI_PUT_MIN = 60                # puts only when RSI > 60 (overbought conviction)
    OPT_TRADE_COOLDOWN_SEC = 300        # 5 min between trades (was 120 — max 12/hr = ~15-20/day)
    OPT_DEAD_COOLDOWN_SEC = 600         # 10 min cooldown after dead momentum exit (0% peak = dead market)
    COOLDOWN_OVERRIDE_CUM_PCT = 0.30    # bypass 5min cooldown only on very strong moves (was 0.20)
    DEAD_COOLDOWN_OVERRIDE_CUM_PCT = 0.25  # bypass dead-market cooldown if cum move >= 0.25%
    # OPT_LOSS_STREAK_LIMIT removed — candle momentum gates entry quality

    # ── GPFC: Setup whitelist — only proven setups ──────────────
    ALLOWED_SETUPS = {"MOMENTUM_BURST", "BB_SQUEEZE"}  # the only profitable patterns
    # ── GPFC: Premium cap — avoid expensive low-gamma options ───
    MAX_PREMIUM_USD: dict[str, float] = {"ETH": 40.0, "BTC": 800.0}

    # ── Dynamic option sizing ──────────────────────────────────────
    # Same pair allocation as futures so capital is balanced.
    OPT_PAIR_ALLOC_PCT: dict[str, float] = {
        "ETH": 30.0,
        "BTC": 20.0,
    }
    OPT_MAX_COLLATERAL_PCT = 40.0        # never use >40% of balance on 1 option
    OPT_SURVIVAL_BALANCE = 20.0          # below this, cap allocation at 30%
    OPT_SURVIVAL_MAX_ALLOC = 30.0

    # ── Pullback entry ───────────────────────────────────────────
    PULLBACK_WAIT_SEC = 15              # Wait up to 15s for premium dip (was 30 — move is over by then)
    PULLBACK_DIP_PCT = 3.0             # Min dip to trigger entry (was 5 — too rare)
    PULLBACK_SKIP_RISE_PCT = 15.0      # Skip if premium rose this much (was 5 — rising = move happening!)
    PULLBACK_POLL_SEC = 2              # Check every 2s during pullback wait

    # ── Exit thresholds (tuned for momentum scalps) ────────────────
    TP_PREMIUM_GAIN_PCT = 30.0           # Take profit at +30% premium gain
    SL_PREMIUM_LOSS_PCT = 50.0           # Stop loss at -50% premium drop (was 30 — $20 option SLs at $10, clean/predictable)
    TRAILING_ACTIVATE_PCT = 15.0         # Trail activates at +15% gain (was 10 — too early)
    TRAILING_DISTANCE_PCT = 5.0          # Trail 5% below peak premium
    PULLBACK_EXIT_PCT = 40.0             # Exit if lost 40% of peak gain (was 50 — too aggressive)
    PULLBACK_ACTIVATE_PCT = 8.0          # Pullback only fires after +8% peak (was 5 — let winners breathe)
    DECAY_THRESHOLD_PCT = 3.0            # Exit if was +10%+ and faded to +3%
    TIMEOUT_MINUTES = 10                 # Options timeout (was 5 — give gamma time to work)
    TIMEOUT_DECAY_PCT = 15.0             # Only timeout if premium decayed > 15% from entry
    PHASE1_HANDS_OFF_SEC = 30            # Only SL fires in first 30s after fill

    # ── Momentum fade — premium profitable but momentum dying ────────
    OPT_MOM_FADE_THRESHOLD = 0.02        # momentum < 0.02% = dying
    OPT_MOM_FADE_CONFIRM_SEC = 60        # hold 60s below threshold to confirm (was 15 — options premium lags spot)
    OPT_MOM_FADE_MIN_HOLD = 60           # min 60s in position before fade can fire
    OPT_MOM_FADE_TREND_HOLD = 90         # trend-aligned: need 90s hold
    OPT_MOM_FADE_TREND_CONFIRM = 20      # trend-aligned: need 20s confirm

    # ── Dead momentum — momentum dead + losing + held too long ───────
    OPT_DEAD_MOM_CONFIRM_SEC = 30        # 30s of dead momentum (was 45)
    OPT_DEAD_MOM_MIN_HOLD = 120          # min 2min hold before dead fires (was 180)

    # ── Ratchet floor table: (peak_pct, locked_floor_pct) ────────────
    # GPFC: Lower entry floors — protect small peaks that reverse
    OPT_RATCHET_FLOOR_TABLE = [
        (1.0, -1.0),     # +1% peak → floor -1% (limit bleed on small movers)
        (2.0, 0.0),      # +2% peak → breakeven lock
        (3.0, 1.0),      # +3% peak → lock +1%
        (5.0, 2.0),      # small winner lock — +5% peak → floor at +2%
        (10.0, 3.0),     # first major floor at 10% peak
        (15.0, 7.0),     # mid-tier
        (25.0, 15.0),    # big runner
        (40.0, 25.0),    # lock 25% at 40% peak
        (100.0, 70.0),   # 70% locked at 100% peak
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
        self._candle_alloc_pct: float = 35.0       # dynamic — set by candle quality (35/50%)
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
        # Cooldown after dead market (OPT_DEAD_MOMENTUM with 0% peak)
        self._dead_market_cooldown_until: float = 0.0

        # Trade cooldown — 5 min between options trades
        self._last_option_trade_time: float = 0.0

        # Regime skip logging throttle (log once per 60s to avoid spam)
        self._last_regime_log: float = 0.0
        self._current_regime: str | None = None

        # Position verification ticker (every 3rd tick = ~30s)
        self._position_verify_tick: int = 0

        # Momentum fade / dead momentum timers
        self._opt_mom_fade_since: float | None = None
        self._opt_mom_dying_since: float | None = None
        # Ratchet profit floor
        self._opt_ratchet_floor: float = 0.0

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

        self.logger.info(
            "[%s] OPTIONS SCALP ACTIVE — min_strength=%d, "
            "TP=%d%% SL=%d%% Trail=%d%%/%d%% Pullback=%d%% Decay=%d%% "
            "Timeout=%dm Phase1=%ds Alloc=%s%s",
            self.pair, self.MIN_SIGNAL_STRENGTH,
            int(self.TP_PREMIUM_GAIN_PCT), int(self.SL_PREMIUM_LOSS_PCT),
            int(self.TRAILING_ACTIVATE_PCT), int(self.TRAILING_DISTANCE_PCT),
            int(self.PULLBACK_EXIT_PCT), int(self.DECAY_THRESHOLD_PCT),
            self.TIMEOUT_MINUTES, self.PHASE1_HANDS_OFF_SEC,
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

        # Position-gone cooldown
        if time.monotonic() < self._position_gone_cooldown_until:
            remaining = self._position_gone_cooldown_until - time.monotonic()
            self._cached_bot_state = f"blocked:position_gone_cooldown:{int(remaining)}s"
            return

        # Trade cooldown
        if self._last_option_trade_time > 0:
            elapsed = time.monotonic() - self._last_option_trade_time
            if elapsed < self.OPT_TRADE_COOLDOWN_SEC:
                remaining = self.OPT_TRADE_COOLDOWN_SEC - elapsed
                self._cached_bot_state = f"blocked:trade_cooldown:{int(remaining)}s"
                return

        # Dead market cooldown
        if time.monotonic() < self._dead_market_cooldown_until:
            remaining = self._dead_market_cooldown_until - time.monotonic()
            self._cached_bot_state = f"blocked:dead_market_cooldown:{int(remaining)}s"
            return

        # Will be overwritten by _check_option_entry() with the real state
        # but this ensures dashboard write has at least "scanning"
        if self._cached_bot_state.startswith("blocked:trade_cooldown") or \
           self._cached_bot_state.startswith("blocked:position_gone_cooldown"):
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
                    "[%s] OPTIONS GLOBAL_LOCK — another asset has an open option",
                    self.pair,
                )
            self._cached_bot_state = "blocked:other_asset_in_position"
            return []

        # 0a. POSITION_GONE cooldown — no new entries for 60s after position disappeared
        if time.monotonic() < self._position_gone_cooldown_until:
            remaining = self._position_gone_cooldown_until - time.monotonic()
            if self._tick_count % 6 == 0:
                self.logger.info(
                    "[%s] OPTIONS COOLDOWN after POSITION_GONE — %.0fs remaining",
                    self.pair, remaining,
                )
            self._cached_bot_state = f"blocked:position_gone_cooldown:{int(remaining)}s"
            return []

        # 0b. Trade cooldown — 2 min between options trades
        now = time.monotonic()
        if self._last_option_trade_time > 0:
            elapsed = now - self._last_option_trade_time
            if elapsed < self.OPT_TRADE_COOLDOWN_SEC:
                remaining = self.OPT_TRADE_COOLDOWN_SEC - elapsed
                # Momentum override: strong fresh momentum bypasses cooldown
                _, _, _, _ov_count, _ov_cum = await self._check_candle_momentum()
                if _ov_count >= 2 and _ov_cum >= self.COOLDOWN_OVERRIDE_CUM_PCT:
                    self.logger.info(
                        "[%s] COOLDOWN_OVERRIDE: trade cooldown bypassed — "
                        "%d/5 candles, cum=%.2f%% >= %.2f%% (%.0fs remaining)",
                        self.pair, _ov_count, _ov_cum,
                        self.COOLDOWN_OVERRIDE_CUM_PCT, remaining,
                    )
                else:
                    if self._tick_count % 6 == 0:
                        self.logger.info(
                            "[%s] OPTIONS TRADE_COOLDOWN — %.0fs remaining (2min between trades)",
                            self.pair, remaining,
                        )
                    self._cached_bot_state = f"blocked:trade_cooldown:{int(remaining)}s"
                    return []

        # 0b2. Dead market cooldown — 10 min after OPT_DEAD_MOMENTUM exit with 0% peak
        if time.monotonic() < self._dead_market_cooldown_until:
            remaining = self._dead_market_cooldown_until - time.monotonic()
            # Momentum override: stronger threshold for dead-market cooldown
            _, _, _, _ov_count, _ov_cum = await self._check_candle_momentum()
            if _ov_count >= 2 and _ov_cum >= self.DEAD_COOLDOWN_OVERRIDE_CUM_PCT:
                self.logger.info(
                    "[%s] COOLDOWN_OVERRIDE: dead-market cooldown bypassed — "
                    "%d/5 candles, cum=%.2f%% >= %.2f%% (%.0fs remaining)",
                    self.pair, _ov_count, _ov_cum,
                    self.DEAD_COOLDOWN_OVERRIDE_CUM_PCT, remaining,
                )
                # Clear the dead-market cooldown so it doesn't re-block next tick
                self._dead_market_cooldown_until = 0.0
            else:
                if self._tick_count % 6 == 0:
                    self.logger.info(
                        "[%s] DEAD_MARKET_COOLDOWN — %.0fs remaining (10min after 0%% peak exit)",
                        self.pair, remaining,
                    )
                self._cached_bot_state = f"blocked:dead_market_cooldown:{int(remaining)}s"
                return []

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
        candle_pass, candle_reason, side, candle_count, candle_cum_pct = await self._check_candle_momentum()
        self._cached_candle_momentum = {
            "count": candle_count, "total": self.CANDLE_MOM_LOOKBACK,
            "cum_pct": round(candle_cum_pct, 4), "direction": side, "passed": candle_pass,
            "reason": candle_reason,
        }
        if not candle_pass:
            if self._tick_count % 6 == 0:
                self.logger.info("[%s] %s", self.pair, candle_reason)
            return []

        # 3/3 candles required — max conviction allocation
        self._candle_alloc_pct = 50.0

        self.logger.info(
            "[%s] EARLY_GATE: %d/3 candles %s, cum=%.2f%% → premium check | alloc=%.0f%%",
            self.pair, candle_count, side, candle_cum_pct, self._candle_alloc_pct,
        )

        # 2b. Underlying move check — confirm price is actually moving, not just candle noise
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
            "[%s] ENTRY_CONTEXT: %s | candles=%d/3",
            self.pair, self._entry_context, candle_count,
        )

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

        # 9a-post. PREMIUM CAP — check BEFORE placing any order
        max_prem = self.MAX_PREMIUM_USD.get(self._base_asset, 40.0)
        if premium > max_prem:
            self.logger.info(
                "[%s] OPTIONS PREMIUM_HIGH: $%.2f > $%.0f cap — skipping",
                self.pair, premium, max_prem,
            )
            await self._log_skip(
                f"{self.pair} — OPTIONS PREMIUM_HIGH: ${premium:.2f} > ${max_prem:.0f}",
                {"option_type": option_type, "premium": premium, "setup_type": setup_type},
            )
            self._cached_bot_state = "blocked:premium_high"
            return []

        # 9b. PREMIUM CONFIRMATION + LIMIT ENTRY at original price.
        # Dynamic wait: strong moves get fast confirm, weaker ones standard.
        # Premium must rise (or hold flat ±0.5%) during the window.
        first_ask = premium
        fast_confirm = True  # 3/3 candles required → always fast confirm (3s)
        confirm_wait = 3 if fast_confirm else 10
        confirm_mode = "fast" if fast_confirm else "standard"
        self.logger.info(
            "[%s] PREMIUM_CONFIRM: %s mode (%ds) — %d/3 candles, cum=%.2f%%",
            self.pair, confirm_mode, confirm_wait, candle_count, candle_cum_pct,
        )
        await asyncio.sleep(confirm_wait)
        try:
            ticker2 = await self.options_exchange.fetch_ticker(selected_symbol)
            second_ask = ticker2.get("ask") or ticker2.get("last") or 0
        except Exception as e:
            self.logger.debug("[%s] Premium confirm fetch failed: %s", self.pair, e)
            second_ask = 0

        # Premium must rise or hold flat (within -0.5%) — skip if dropped more
        pct_chg = ((second_ask - first_ask) / first_ask * 100) if first_ask > 0 else 0
        if second_ask <= 0 or pct_chg < -0.5:
            self.logger.info(
                "[%s] PREMIUM_CONFIRM: $%.4f → $%.4f (%+.2f%%) — premium dead, SKIP",
                self.pair, first_ask, second_ask, pct_chg,
            )
            return []

        # Dynamic limit price: chase the move if premium rose significantly
        if pct_chg >= 5.0:
            limit_price = second_ask
            self.logger.info(
                "[%s] PREMIUM_LIMIT: chasing at confirmed $%.4f (+%.2f%% vs original) — strong move",
                self.pair, second_ask, pct_chg,
            )
        else:
            limit_price = first_ask
            self.logger.info(
                "[%s] PREMIUM_LIMIT: placing limit at $%.4f (confirmed $%.4f, %+.2f%%) — waiting 15s",
                self.pair, first_ask, second_ask, pct_chg,
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

        # Poll for fill over 15 seconds
        limit_filled = False
        fill_price = limit_price
        for _poll in range(5):  # 5 × 3s = 15s
            await asyncio.sleep(3)
            try:
                updated = await self.options_exchange.fetch_order(limit_order_id, selected_symbol)
                status = updated.get("status", "")
                filled_qty = float(updated.get("filled", 0) or 0)
                if status == "closed" or filled_qty >= opt_contracts:
                    fill_price = float(updated.get("average", 0) or updated.get("price", 0) or limit_price)
                    limit_filled = True
                    self.logger.info(
                        "[%s] PREMIUM_LIMIT: FILLED @ $%.4f (%d contracts)",
                        self.pair, fill_price, opt_contracts,
                    )
                    break
            except Exception as e:
                self.logger.debug("[%s] PREMIUM_LIMIT: poll failed: %s", self.pair, e)

        if not limit_filled:
            # Cancel unfilled order — move happened without us
            try:
                await self.options_exchange.cancel_order(limit_order_id, selected_symbol)
                self.logger.info(
                    "[%s] PREMIUM_LIMIT: NOT filled in 15s — cancelled, SKIP (move happened without us)",
                    self.pair,
                )
            except Exception as e:
                # Cancel failed — check if it actually filled
                try:
                    final_check = await self.options_exchange.fetch_order(limit_order_id, selected_symbol)
                    if final_check.get("status") == "closed" or float(final_check.get("filled", 0) or 0) >= opt_contracts:
                        fill_price = float(final_check.get("average", 0) or final_check.get("price", 0) or limit_price)
                        limit_filled = True
                        self.logger.info(
                            "[%s] PREMIUM_LIMIT: cancel failed but order FILLED @ $%.4f",
                            self.pair, fill_price,
                        )
                except Exception:
                    pass
                if not limit_filled:
                    self.logger.info("[%s] PREMIUM_LIMIT: cancel failed: %s — SKIP", self.pair, e)
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

        alloc_pct = self._candle_alloc_pct  # dynamic: 35/50% based on candle quality

        # Survival mode: low balance → cap allocation
        if exchange_capital < self.OPT_SURVIVAL_BALANCE:
            alloc_pct = min(alloc_pct, self.OPT_SURVIVAL_MAX_ALLOC)

        # Collateral budget (capped at 40% of total balance)
        collateral_available = exchange_capital * (alloc_pct / 100)
        max_collateral = exchange_capital * (self.OPT_MAX_COLLATERAL_PCT / 100)
        collateral_available = min(collateral_available, max_collateral)

        # Collateral per contract at leverage
        collateral_per_contract = premium / self.OPTIONS_LEVERAGE
        if collateral_per_contract <= 0:
            return 0

        contracts = math.floor(collateral_available / collateral_per_contract)
        contracts = max(contracts, 0)

        # Survival mode: balance < $5 → cap at 5 contracts (collateral is tiny at 50x leverage)
        if exchange_capital < 5.0 and contracts > 5:
            self.logger.info(
                "[%s] SURVIVAL_MODE: bal=$%.2f < $5 — capping %d → 5 contracts",
                self.pair, exchange_capital, contracts,
            )
            contracts = 5

        # Hard cap: never exceed 15 contracts per trade
        if contracts > 15:
            self.logger.info(
                "[%s] SIZE_CAP: %d → 15 contracts (hard cap)",
                self.pair, contracts,
            )
            contracts = 15

        self.logger.info(
            "[%s] OPT_SIZING: %d contracts @ $%.4f "
            "(collateral=$%.2f, alloc=%.0f%%, bal=$%.2f, per_ct=$%.4f)",
            self.pair, contracts, premium,
            collateral_available, alloc_pct, exchange_capital,
            collateral_per_contract,
        )
        return contracts

    # ==================================================================
    # CANDLE-BASED MOMENTUM GATE
    # ==================================================================

    async def _check_candle_momentum(self) -> tuple[bool, str, str | None, int, float]:
        """Early-direction gate for options entry — PRIMARY GATE.

        Determines direction AND momentum from last 3 completed 1m candles.
        Direction comes FROM candles (not from scalp signal).

        All three conditions must pass:
        1. Direction gate: ≥2 of 3 candles in same direction (green=long, red=short)
        2. Cumulative move: sum of (close-open) ≥ threshold (BTC 0.15%, ETH 0.20%)
        3. Last candle: must match direction (no reversal at end)

        Returns:
            (passed, reason_string, side, directional_count, cum_pct)
        """
        exchange = self.futures_exchange
        if not exchange:
            return False, "no_exchange", None, 0, 0.0

        try:
            ohlcv = await exchange.fetch_ohlcv(self.pair, "1m", limit=self.CANDLE_MOM_LOOKBACK + 2)
        except Exception as e:
            self.logger.debug("[%s] CANDLE_MOM: fetch_ohlcv failed: %s", self.pair, e)
            return False, f"fetch_failed ({e})", None, 0, 0.0

        if not ohlcv or len(ohlcv) < self.CANDLE_MOM_LOOKBACK:
            return False, f"insufficient candles ({len(ohlcv) if ohlcv else 0})", None, 0, 0.0

        # Take last 3 completed candles
        completed = ohlcv[-self.CANDLE_MOM_LOOKBACK:]

        current_price = float(completed[-1][4])  # close of last completed candle
        if current_price <= 0:
            return False, "bad price", None, 0, 0.0

        # Per-asset cumulative threshold
        cum_threshold = (
            self.CANDLE_MOM_CUM_PCT_ETH if self._base_asset == "ETH"
            else self.CANDLE_MOM_CUM_PCT_BTC
        )

        # Classify each candle: bullish (green), bearish (red), or doji (neutral)
        doji_threshold = current_price * 0.0001  # 0.01% of price
        green_count = 0
        red_count = 0
        cumulative_move = 0.0

        for candle in completed:
            o, c = float(candle[1]), float(candle[4])
            move = c - o
            cumulative_move += move

            if abs(move) < doji_threshold:
                continue  # doji — neutral, skip

            if move > 0:
                green_count += 1
            else:
                red_count += 1

        # Determine direction from candle majority (2/3 minimum)
        if green_count >= self.CANDLE_MOM_STREAK:
            side = "long"
            directional_count = green_count
        elif red_count >= self.CANDLE_MOM_STREAK:
            side = "short"
            directional_count = red_count
        else:
            n = self.CANDLE_MOM_LOOKBACK
            return False, f"{green_count}/{n} green, {red_count}/{n} red — no clear direction → SKIP", None, 0, 0.0

        # Last completed candle must match direction (no reversal)
        last_o, last_c = float(completed[-1][1]), float(completed[-1][4])
        last_move = last_c - last_o
        last_is_directional = (
            (side == "long" and last_move > doji_threshold)
            or (side == "short" and last_move < -doji_threshold)
        )

        # Cumulative move check (direction-aware)
        cum_pct = (cumulative_move / current_price) * 100
        if side == "short":
            cum_pct = -cum_pct  # for shorts, negative move is positive for our direction

        # Build result
        color = "green" if side == "long" else "red"
        last_color = "green" if last_move > doji_threshold else ("red" if last_move < -doji_threshold else "doji")
        n = self.CANDLE_MOM_LOOKBACK

        passed = (
            cum_pct >= cum_threshold
            and last_is_directional
        )

        if passed:
            reason = (
                f"EARLY_GATE: {directional_count}/{n} {color}, "
                f"cum={cum_pct:+.2f}% (≥{cum_threshold}%), last={last_color} → ENTER"
            )
        else:
            parts = [f"{directional_count}/{n} {color}"]
            if cum_pct < cum_threshold:
                parts.append(f"cum={cum_pct:+.2f}% < {cum_threshold}%")
            if not last_is_directional:
                direction_label = "CALL" if side == "long" else "PUT"
                parts.append(f"last candle {last_color} but need {color} for {direction_label}")
            reason = "EARLY_GATE: " + ", ".join(parts) + " → SKIP"

        return passed, reason, side if passed else None, directional_count, cum_pct

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

        Phase 1 (first 30s after fill): only SL fires.
        After Phase 1:
        1. Expiry: Close 2 hours before expiry
        2. Ratchet floor: lock profit floor as premium rises
        3. SL: -50% premium drop (always active)
        4. Momentum Fade: profitable + momentum dying → exit
        5. Dead Momentum: losing + momentum dead 45s + held 3min → exit
        6. TP: +30% premium gain
        7. Trailing: activates at +15%, trails 5% behind peak
        8. Pullback: exit if lost 40% of peak gain (when peak was 8%+)
        9. Decay: exit if was +10%+ and faded to +3%
        10. Timeout: close after 5 minutes
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

        # ── 1. EXPIRY EXIT: close 2 hours before expiry ──────────────
        if self.expiry_dt:
            time_to_expiry = (self.expiry_dt - datetime.now(timezone.utc)).total_seconds()
            close_threshold = self.CLOSE_BEFORE_EXPIRY_HOURS * 3600
            if time_to_expiry <= close_threshold:
                self.logger.info(
                    "[%s] EXPIRY in %.1fh — closing option",
                    self.option_symbol, time_to_expiry / 3600,
                )
                return await self._do_option_exit(current_premium, premium_change_pct, "EXPIRY_CLOSE")

        # ── Ratchet floor update (always, before any exit checks) ─────
        # Use PEAK pnl, not current — so the floor locks even if price has already dropped
        self._update_opt_ratchet_floor(peak_pnl_pct)

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

        # ── Phase 1 hands-off: only SL fires in first 30s ────────────
        if in_phase1:
            return []

        # ── 3. MOMENTUM FADE: profitable + momentum dying ─────────────
        momentum_60s = 0.0
        if self._scalp and hasattr(self._scalp, "last_signal_state"):
            ss = self._scalp.last_signal_state
            if ss:
                momentum_60s = abs(ss.get("momentum_60s", 0) or 0)

        if hold_seconds >= self.OPT_MOM_FADE_MIN_HOLD and premium_change_pct > 0:
            if momentum_60s < self.OPT_MOM_FADE_THRESHOLD:
                now_m = time.monotonic()
                if self._opt_mom_fade_since is None:
                    self._opt_mom_fade_since = now_m
                # Trend-aligned positions get longer leash
                trend = self._scalp._get_15m_trend() if self._scalp else "neutral"
                trend_aligned = (
                    (self.option_side == "call" and trend == "bullish")
                    or (self.option_side == "put" and trend == "bearish")
                )
                if trend_aligned:
                    confirm_sec = self.OPT_MOM_FADE_TREND_CONFIRM
                    min_hold = self.OPT_MOM_FADE_TREND_HOLD
                else:
                    confirm_sec = self.OPT_MOM_FADE_CONFIRM_SEC
                    min_hold = self.OPT_MOM_FADE_MIN_HOLD

                elapsed = now_m - self._opt_mom_fade_since
                if elapsed >= confirm_sec and hold_seconds >= min_hold:
                    self.logger.info(
                        "[%s] OPT_MOMENTUM_FADE — profitable +%.1f%% but mom=%.4f%% dead %.0fs (aligned=%s)",
                        self.option_symbol, premium_change_pct, momentum_60s,
                        elapsed, trend_aligned,
                    )
                    return await self._do_option_exit(current_premium, premium_change_pct, "OPT_MOMENTUM_FADE")
            else:
                self._opt_mom_fade_since = None

        # ── 4. DEAD MOMENTUM: losing + momentum dead + held too long ──
        # If peak was never green (highest_premium <= entry_premium), cut faster (90s hold)
        # If peak > 0%, keep full 120s — it moved once, might move again
        peak_was_green = self.highest_premium > self.entry_premium if self.entry_premium > 0 else False
        dead_min_hold = self.OPT_DEAD_MOM_MIN_HOLD if peak_was_green else 90
        if hold_seconds >= dead_min_hold and premium_change_pct < 0:
            if momentum_60s < self.OPT_MOM_FADE_THRESHOLD:
                now_m = time.monotonic()
                if self._opt_mom_dying_since is None:
                    self._opt_mom_dying_since = now_m
                dead_elapsed = now_m - self._opt_mom_dying_since
                if dead_elapsed >= self.OPT_DEAD_MOM_CONFIRM_SEC:
                    self.logger.info(
                        "[%s] OPT_DEAD_MOMENTUM — losing %.1f%% + mom dead %.0fs + held %ds (peak_green=%s)",
                        self.option_symbol, premium_change_pct, dead_elapsed, int(hold_seconds), peak_was_green,
                    )
                    return await self._do_option_exit(current_premium, premium_change_pct, "OPT_DEAD_MOMENTUM")
            else:
                self._opt_mom_dying_since = None

        # ── 5. TAKE PROFIT: +30% premium gain ────────────────────────
        if premium_change_pct >= self.TP_PREMIUM_GAIN_PCT:
            self.logger.info(
                "[%s] OPTION TP — premium +%.1f%% ($%.4f → $%.4f)",
                self.option_symbol, premium_change_pct,
                self.entry_premium, current_premium,
            )
            return await self._do_option_exit(current_premium, premium_change_pct, "TP")

        # ── 6. TRAILING activation at +15% ───────────────────────────
        if premium_change_pct >= self.TRAILING_ACTIVATE_PCT and not self._trailing_active:
            self._trailing_active = True
            self.logger.info(
                "[%s] OPTION TRAIL ON at +%.1f%%", self.option_symbol, premium_change_pct,
            )

        # ── 7. TRAILING STOP: 5% below peak premium ─────────────────
        if self._trailing_active:
            trail_floor = self.highest_premium * (1 - self.TRAILING_DISTANCE_PCT / 100)
            if current_premium <= trail_floor:
                final_pct = (current_premium - self.entry_premium) / self.entry_premium * 100
                self.logger.info(
                    "[%s] OPTION TRAIL HIT — peak=$%.4f floor=$%.4f now=$%.4f",
                    self.option_symbol, self.highest_premium, trail_floor, current_premium,
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

        # ── 8. TIMEOUT: close after 10 minutes (GPFC: only if decaying) ──
        if hold_seconds >= self.TIMEOUT_MINUTES * 60:
            # GPFC: Don't timeout a flat/rising trade — only if premium decayed
            if premium_change_pct <= -self.TIMEOUT_DECAY_PCT or premium_change_pct < 0:
                self.logger.info(
                    "[%s] OPTION TIMEOUT — held %dm (limit %dm) at %+.1f%%",
                    self.option_symbol, int(hold_seconds / 60),
                    self.TIMEOUT_MINUTES, premium_change_pct,
                )
                return await self._do_option_exit(current_premium, premium_change_pct, "OPT_TIMEOUT")
            else:
                # Profitable or flat — let it ride, log once
                if self._tick_count % 6 == 0:
                    self.logger.info(
                        "[%s] OPTION TIMEOUT SKIP — held %dm but at %+.1f%% (no decay)",
                        self.option_symbol, int(hold_seconds / 60), premium_change_pct,
                    )

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
    # OPTIONS DB CLOSE (bypasses trade_executor P&L)
    # ==================================================================

    async def _close_option_trade_in_db(
        self, exit_premium: float, exit_type: str,
        *, option_symbol: str | None = None,
        entry_premium: float = 0.0, highest_premium: float = 0.0,
        contracts: int = 0,
    ) -> bool:
        """Close the option trade in DB with correct options P&L.

        Called from on_fill() after exchange confirms the exit.
        Volatile state (option_symbol, entry_premium, etc.) is passed
        explicitly since on_fill clears self.* after scheduling this task.
        Falls back to self.* when called from _handle_position_gone.
        """
        sym = option_symbol or self.option_symbol or self.pair
        ep = entry_premium or self.entry_premium
        hp = highest_premium or self.highest_premium
        ct = contracts or self._contracts

        if not self._db or not self._db.is_connected:
            return False

        try:
            from alpha.utils import iso_now

            open_trade = await self._db.get_open_trade(
                pair=sym, exchange="delta", strategy="options_scalp",
            )
            if not open_trade:
                self.logger.warning(
                    "[%s] _close_option_trade_in_db: no open trade found", sym,
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

        # Reset momentum / ratchet state
        self._opt_mom_fade_since = None
        self._opt_mom_dying_since = None
        self._opt_ratchet_floor = 0.0

        # Stats tracking
        if pnl_pct >= 0:
            self.hourly_wins += 1
        else:
            self.hourly_losses += 1
        self.hourly_pnl += pnl_usd

        # Trade cooldown — extended to 10 min for dead momentum exits where peak was 0%
        self._last_option_trade_time = time.monotonic()
        if exit_type == "OPT_DEAD_MOMENTUM" and self.highest_premium <= self.entry_premium:
            # Peak never went green → dead market, use 10 min cooldown
            self._dead_market_cooldown_until = time.monotonic() + self.OPT_DEAD_COOLDOWN_SEC
            self.logger.info(
                "[%s] DEAD MARKET — peak was 0%%, setting 10-min cooldown",
                self.option_symbol,
            )

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
            # fetch_positions failed — don't flag as gone, just log
            self.logger.debug(
                "[%s] Position verify fetch_positions failed: %s", self.option_symbol, e,
            )
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

        # Trade cooldown — set 5 min timer
        self._last_option_trade_time = time.monotonic()

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
        self.option_side = None
        self.option_symbol = None
        self.entry_premium = 0.0
        self.highest_premium = 0.0
        self._last_known_premium = 0.0
        self._trailing_active = False
        self.strike_price = 0.0
        self.expiry_dt = None
        self._consecutive_ticker_failures = 0
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
            # Entry fill — ONLY use exchange fill price. Never fallback to signal.price (limit price).
            fill_price = order.get("average") or order.get("price") or self.entry_premium
            if not fill_price:
                self.logger.error("[%s] NO FILL PRICE from exchange — skipping on_fill", signal.pair)
                return
            self.in_position = True
            OptionsScalpStrategy._global_in_position = True  # global lock
            self.option_side = pending_side
            self.option_symbol = signal.pair
            self.entry_premium = fill_price
            self.entry_time = time.monotonic()
            self.highest_premium = fill_price
            self._last_known_premium = fill_price
            self._trailing_active = False
            self._consecutive_ticker_failures = 0
            # Reset momentum / ratchet state on entry
            self._opt_mom_fade_since = None
            self._opt_mom_dying_since = None
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
        else:
            # Exit fill — close trade in DB with actual fill price from exchange
            exit_fill = float(order.get("average") or order.get("price") or signal.price or 0)
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

            if exit_fill > 0:
                import asyncio
                asyncio.get_event_loop().create_task(
                    self._close_option_trade_in_db(
                        exit_fill, exit_type,
                        option_symbol=_sym,
                        entry_premium=_entry_prem,
                        highest_premium=_highest_prem,
                        contracts=_contracts,
                    )
                )

            # Telegram exit notification — sent here because
            # _close_option_trade_in_db may not find the open trade
            # (trade_executor already closed it before on_fill runs)
            try:
                alerts = getattr(self.executor, "alerts", None)
                if alerts is not None and exit_fill > 0 and _entry_prem > 0:
                    import asyncio as _aio
                    _mult = 0.001 if "BTC" in _sym else 0.01
                    _gross = (exit_fill - _entry_prem) * _contracts * _mult
                    _pnl_pct = (exit_fill - _entry_prem) / _entry_prem * 100
                    _emoji = "\u2705" if _gross >= 0 else "\u274c"
                    _side_label = "CALL" if _sym.endswith("-C") or _sym.endswith("C") else "PUT"
                    msg = (
                        f"{_emoji} {_base} option closed\n"
                        f"{exit_type} | {_side_label} ${_strike:.0f}\n"
                        f"${_entry_prem:.2f} \u2192 ${exit_fill:.2f} ({_pnl_pct:+.1f}%)\n"
                        f"Gross: ${_gross:+.4f} | x{_contracts}"
                    )
                    _aio.get_event_loop().create_task(alerts.send_text(msg))
            except Exception:
                pass

            self.in_position = False
            OptionsScalpStrategy._global_in_position = False  # release global lock
            self.option_side = None
            self.option_symbol = None
            self.entry_premium = 0.0
            self.highest_premium = 0.0
            self._trailing_active = False
            self.strike_price = 0.0
            self.expiry_dt = None
            self._contracts = 1
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

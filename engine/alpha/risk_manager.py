"""Risk manager — position sizing, exposure limits, win-rate circuit breakers.

Multi-pair + multi-exchange aware: tracks positions per pair, enforces total
exposure cap (accounting for leverage), and monitors liquidation risk on
futures positions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from alpha.config import config
from alpha.strategies.base import Signal
from alpha.utils import setup_logger, utcnow

logger = setup_logger("risk_manager")


@dataclass
class Position:
    pair: str
    side: str
    entry_price: float
    amount: float
    strategy: str
    opened_at: str
    exchange: str = "binance"
    leverage: int = 1
    position_type: str = "spot"  # "spot", "long", or "short"


class RiskManager:
    """
    Enforces risk rules before any trade is executed.

    Rules:
    - Max position per trade: check COLLATERAL (margin) for futures, order value for spot
    - Max 2 concurrent positions across ALL pairs/exchanges
    - Max 1 position per pair at a time
    - Total exposure capped at 60% of capital (collateral-based for futures)
    - Daily loss limit: stop bot at threshold
    - Per-trade stop-loss: 2%
    - Win-rate circuit breaker: if < 40% over last 20 trades -> pause
    """

    def __init__(self, capital: float | None = None) -> None:
        self.capital = capital or config.trading.starting_capital
        self.max_position_pct = config.trading.max_position_pct
        self.max_total_exposure_pct = config.trading.max_total_exposure_pct
        self.max_concurrent = config.trading.max_concurrent_positions
        self.daily_loss_limit_pct = config.trading.max_loss_daily_pct
        self.per_trade_sl_pct = config.trading.per_trade_stop_loss_pct

        # Per-exchange capital: strategies size off their own exchange balance
        self.binance_capital: float = 0.0
        self.delta_capital: float = 0.0

        self.open_positions: list[Position] = []
        self.daily_pnl: float = 0.0
        self.daily_pnl_by_pair: dict[str, float] = {}
        self.trade_results: list[bool] = []  # True=win, False=loss (last N)
        self.is_paused = False
        self._pause_reason: str = ""

    def update_exchange_balances(self, binance: float | None, delta: float | None) -> None:
        """Update per-exchange capital from live balance fetches."""
        if binance is not None:
            self.binance_capital = binance
        if delta is not None:
            self.delta_capital = delta
        self.capital = self.binance_capital + self.delta_capital
        logger.info(
            "Balances updated: Binance=$%.2f, Delta=$%.2f, Total=$%.2f",
            self.binance_capital, self.delta_capital, self.capital,
        )

    def get_exchange_capital(self, exchange_id: str) -> float:
        """Return capital for a specific exchange."""
        if exchange_id == "delta":
            return self.delta_capital
        return self.binance_capital

    # -- Properties ------------------------------------------------------------

    @property
    def win_rate(self) -> float:
        if not self.trade_results:
            return 100.0  # no trades yet -- allow trading
        recent = self.trade_results[-20:]
        return (sum(recent) / len(recent)) * 100

    @property
    def daily_loss_pct(self) -> float:
        if self.capital == 0:
            return 0.0
        return abs(min(self.daily_pnl, 0)) / self.capital * 100

    @property
    def total_exposure(self) -> float:
        """Sum of capital at risk across all positions.

        Spot: order value (price * amount).
        Futures: collateral/margin (price * amount), NOT notional.
        The actual capital locked is the margin, not the leveraged value.
        """
        total = 0.0
        for p in self.open_positions:
            order_value = p.entry_price * p.amount
            if p.position_type in ("long", "short") and p.leverage > 1:
                # Futures: collateral = order_value (margin posted)
                total += order_value
            else:
                # Spot: full order value
                total += order_value
        return total

    @property
    def total_exposure_pct(self) -> float:
        if self.capital == 0:
            return 0.0
        return (self.total_exposure / self.capital) * 100

    @property
    def spot_exposure(self) -> float:
        """Spot positions only."""
        return sum(
            p.entry_price * p.amount
            for p in self.open_positions if p.position_type == "spot"
        )

    @property
    def futures_exposure(self) -> float:
        """Futures collateral (margin) only — NOT notional."""
        return sum(
            p.entry_price * p.amount
            for p in self.open_positions if p.position_type in ("long", "short")
        )

    @property
    def futures_notional(self) -> float:
        """Futures notional value (for display/logging only)."""
        return sum(
            p.entry_price * p.amount * p.leverage
            for p in self.open_positions if p.position_type in ("long", "short")
        )

    def pairs_with_positions(self) -> set[str]:
        """Return the set of pairs that currently have an open position."""
        return {p.pair for p in self.open_positions}

    def has_position(self, pair: str) -> bool:
        """Check if there's already an open position for this pair."""
        return pair in self.pairs_with_positions()

    # -- Signal approval -------------------------------------------------------

    def approve_signal(self, signal: Signal) -> bool:
        """Return True if the signal passes all risk checks."""
        if self.is_paused:
            logger.warning("Bot is paused: %s -- rejecting %s %s", self._pause_reason, signal.side, signal.pair)
            return False

        # Determine if this signal opens a new position
        # Spot: only "buy" opens. Futures: any non-reduce_only signal opens.
        is_opening = (
            (signal.position_type == "spot" and signal.side == "buy")
            or (signal.position_type in ("long", "short") and not signal.reduce_only)
        )

        # 1. Daily loss limit
        if self.daily_loss_pct >= self.daily_loss_limit_pct:
            self._pause("daily loss limit reached (%.1f%%)" % self.daily_loss_pct)
            return False

        # 2. Win-rate circuit breaker
        if len(self.trade_results) >= 20 and self.win_rate < 40:
            self._pause("win rate too low (%.1f%% over last 20 trades)" % self.win_rate)
            return False

        # 3. Max concurrent positions (across ALL pairs/exchanges)
        if is_opening and len(self.open_positions) >= self.max_concurrent:
            logger.info(
                "Max concurrent positions (%d) reached -- rejecting %s %s",
                self.max_concurrent, signal.pair, signal.position_type,
            )
            return False

        # 4. Max 1 position per pair
        if is_opening and self.has_position(signal.pair):
            logger.info("Already have open position on %s -- rejecting", signal.pair)
            return False

        # 5. Position size limit
        #    Futures: check COLLATERAL (margin), not notional value.
        #    Spot: check order value directly.
        #    Use per-exchange capital so Binance trades size from Binance balance
        #    and Delta trades size from Delta balance.
        trade_value = signal.price * signal.amount
        is_futures = signal.position_type in ("long", "short") and signal.leverage > 1
        exchange_capital = self.get_exchange_capital(signal.exchange_id)
        if exchange_capital <= 0:
            exchange_capital = self.capital  # fallback to total if not set
        max_value = exchange_capital * (self.max_position_pct / 100)

        if is_futures:
            # Collateral = trade_value (the margin posted). Notional = trade_value * leverage.
            collateral = trade_value
            if collateral > max_value * 1.05:  # 5% tolerance
                logger.info(
                    "Futures collateral $%.2f exceeds max $%.2f (%.0f%% of $%.2f %s capital) -- rejecting %s",
                    collateral, max_value, self.max_position_pct, exchange_capital,
                    signal.exchange_id, signal.pair,
                )
                return False
        else:
            # Spot: order value checked directly
            if trade_value > max_value * 1.05:
                logger.info(
                    "Order value $%.2f exceeds max $%.2f (%.0f%% of $%.2f %s capital) -- rejecting %s",
                    trade_value, max_value, self.max_position_pct, exchange_capital,
                    signal.exchange_id, signal.pair,
                )
                return False

        # 6. Total exposure cap (collateral-based for futures, value-based for spot)
        if is_opening:
            # For futures, add collateral; for spot, add order value
            added_exposure = trade_value  # both cases: collateral = order value
            new_exposure = self.total_exposure + added_exposure
            new_exposure_pct = (new_exposure / self.capital) * 100 if self.capital else 0
            if new_exposure_pct > self.max_total_exposure_pct:
                logger.info(
                    "Total exposure would be %.1f%% (cap %.1f%%) -- rejecting %s",
                    new_exposure_pct, self.max_total_exposure_pct, signal.pair,
                )
                return False

        notional_str = f" notional=${trade_value * signal.leverage:.2f}" if is_futures else ""
        logger.info(
            "Signal approved: %s %s %s %.6f @ $%.2f (collateral=$%.2f, %dx%s) | "
            "%s_capital=$%.2f | positions=%d, exposure=%.1f%%, daily_pnl=$%.2f",
            signal.position_type, signal.side, signal.pair, signal.amount, signal.price,
            trade_value, signal.leverage, notional_str, signal.exchange_id, exchange_capital,
            len(self.open_positions), self.total_exposure_pct, self.daily_pnl,
        )
        return True

    # -- Position tracking -----------------------------------------------------

    def record_open(self, signal: Signal) -> None:
        """Track a newly opened position."""
        self.open_positions.append(Position(
            pair=signal.pair,
            side=signal.side,
            entry_price=signal.price,
            amount=signal.amount,
            strategy=signal.strategy.value,
            opened_at=utcnow().isoformat(),
            exchange=signal.exchange_id,
            leverage=signal.leverage,
            position_type=signal.position_type,
        ))

    def record_close(self, pair: str, pnl: float) -> None:
        """Record a closed trade's P&L."""
        self.daily_pnl += pnl
        self.daily_pnl_by_pair[pair] = self.daily_pnl_by_pair.get(pair, 0.0) + pnl
        self.trade_results.append(pnl >= 0)
        # Remove first matching position for this pair
        new_positions: list[Position] = []
        removed = False
        for p in self.open_positions:
            if p.pair == pair and not removed:
                removed = True
                continue
            new_positions.append(p)
        self.open_positions = new_positions
        self.capital += pnl
        logger.info(
            "Trade closed [%s]: PnL=$%.4f | daily=$%.4f | capital=$%.2f | win_rate=%.1f%%",
            pair, pnl, self.daily_pnl, self.capital, self.win_rate,
        )

    # -- Liquidation monitoring ------------------------------------------------

    def check_liquidation_risk(self, pair: str, current_price: float) -> float | None:
        """Return distance-to-liquidation as a percentage, or None if no futures position.

        For long:  liq_price = entry * (1 - 1/leverage)
        For short: liq_price = entry * (1 + 1/leverage)
        """
        for pos in self.open_positions:
            if pos.pair != pair or pos.leverage <= 1:
                continue
            if pos.position_type == "long":
                liq_price = pos.entry_price * (1 - 1 / pos.leverage)
                distance_pct = ((current_price - liq_price) / current_price) * 100
            elif pos.position_type == "short":
                liq_price = pos.entry_price * (1 + 1 / pos.leverage)
                distance_pct = ((liq_price - current_price) / current_price) * 100
            else:
                continue
            return distance_pct
        return None

    # -- Daily reset -----------------------------------------------------------

    def reset_daily(self) -> None:
        """Called at midnight to reset daily counters."""
        logger.info("Daily reset -- previous daily PnL: $%.4f", self.daily_pnl)
        self.daily_pnl = 0.0
        self.daily_pnl_by_pair.clear()
        if self.is_paused and "daily loss" in self._pause_reason:
            self.is_paused = False
            self._pause_reason = ""
            logger.info("Bot unpaused after daily reset")

    # -- Pause control ---------------------------------------------------------

    def unpause(self) -> None:
        """Manually unpause the bot."""
        self.is_paused = False
        self._pause_reason = ""
        logger.info("Bot manually unpaused")

    def _pause(self, reason: str) -> None:
        self.is_paused = True
        self._pause_reason = reason
        logger.warning("BOT PAUSED: %s", reason)

    # -- Status ----------------------------------------------------------------

    def get_status(self) -> dict:
        return {
            "capital": self.capital,
            "daily_pnl": self.daily_pnl,
            "daily_loss_pct": self.daily_loss_pct,
            "open_positions": len(self.open_positions),
            "total_exposure_pct": self.total_exposure_pct,
            "spot_exposure": self.spot_exposure,
            "futures_exposure": self.futures_exposure,       # collateral/margin
            "futures_notional": self.futures_notional,       # leveraged value
            "win_rate": self.win_rate,
            "is_paused": self.is_paused,
            "pause_reason": self._pause_reason,
            "pairs_with_positions": list(self.pairs_with_positions()),
        }

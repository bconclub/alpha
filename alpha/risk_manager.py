"""Risk manager — position sizing, exposure limits, win-rate circuit breakers.

Multi-pair aware: tracks positions per pair, enforces total exposure cap,
and prioritises signals by strength when capital is limited.
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


class RiskManager:
    """
    Enforces risk rules before any trade is executed.

    Rules:
    - Max 30% of capital per single trade
    - Max 2 concurrent positions across ALL pairs
    - Max 1 position per pair at a time
    - Total exposure capped at 60% of capital
    - Daily loss limit: stop bot at threshold
    - Per-trade stop-loss: 2%
    - Win-rate circuit breaker: if < 40% over last 20 trades → pause
    """

    def __init__(self, capital: float | None = None) -> None:
        self.capital = capital or config.trading.starting_capital
        self.max_position_pct = config.trading.max_position_pct
        self.max_total_exposure_pct = config.trading.max_total_exposure_pct
        self.max_concurrent = config.trading.max_concurrent_positions
        self.daily_loss_limit_pct = config.trading.max_loss_daily_pct
        self.per_trade_sl_pct = config.trading.per_trade_stop_loss_pct

        self.open_positions: list[Position] = []
        self.daily_pnl: float = 0.0
        self.daily_pnl_by_pair: dict[str, float] = {}
        self.trade_results: list[bool] = []  # True=win, False=loss (last N)
        self.is_paused = False
        self._pause_reason: str = ""

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def win_rate(self) -> float:
        if not self.trade_results:
            return 100.0  # no trades yet — allow trading
        recent = self.trade_results[-20:]
        return (sum(recent) / len(recent)) * 100

    @property
    def daily_loss_pct(self) -> float:
        if self.capital == 0:
            return 0.0
        return abs(min(self.daily_pnl, 0)) / self.capital * 100

    @property
    def total_exposure(self) -> float:
        """Sum of all open position values in USD."""
        return sum(p.entry_price * p.amount for p in self.open_positions)

    @property
    def total_exposure_pct(self) -> float:
        if self.capital == 0:
            return 0.0
        return (self.total_exposure / self.capital) * 100

    def pairs_with_positions(self) -> set[str]:
        """Return the set of pairs that currently have an open position."""
        return {p.pair for p in self.open_positions}

    def has_position(self, pair: str) -> bool:
        """Check if there's already an open position for this pair."""
        return pair in self.pairs_with_positions()

    # ── Signal approval ──────────────────────────────────────────────────────

    def approve_signal(self, signal: Signal) -> bool:
        """Return True if the signal passes all risk checks."""
        if self.is_paused:
            logger.warning("Bot is paused: %s — rejecting %s %s", self._pause_reason, signal.side, signal.pair)
            return False

        # 1. Daily loss limit
        if self.daily_loss_pct >= self.daily_loss_limit_pct:
            self._pause("daily loss limit reached (%.1f%%)" % self.daily_loss_pct)
            return False

        # 2. Win-rate circuit breaker
        if len(self.trade_results) >= 20 and self.win_rate < 40:
            self._pause("win rate too low (%.1f%% over last 20 trades)" % self.win_rate)
            return False

        # 3. Max concurrent positions (across ALL pairs)
        if signal.side == "buy" and len(self.open_positions) >= self.max_concurrent:
            logger.info(
                "Max concurrent positions (%d) reached — rejecting %s buy",
                self.max_concurrent, signal.pair,
            )
            return False

        # 4. Max 1 position per pair
        if signal.side == "buy" and self.has_position(signal.pair):
            logger.info("Already have open position on %s — rejecting buy", signal.pair)
            return False

        # 5. Position size limit (per trade)
        trade_value = signal.price * signal.amount
        max_value = self.capital * (self.max_position_pct / 100)
        if trade_value > max_value * 1.05:  # 5% tolerance
            logger.info(
                "Trade value $%.2f exceeds max $%.2f (%.0f%% of capital) — rejecting %s",
                trade_value, max_value, self.max_position_pct, signal.pair,
            )
            return False

        # 6. Total exposure cap (across all pairs)
        if signal.side == "buy":
            new_exposure_pct = ((self.total_exposure + trade_value) / self.capital) * 100
            if new_exposure_pct > self.max_total_exposure_pct:
                logger.info(
                    "Total exposure would be %.1f%% (cap %.1f%%) — rejecting %s buy",
                    new_exposure_pct, self.max_total_exposure_pct, signal.pair,
                )
                return False

        logger.info(
            "Signal approved: %s %s %.6f @ %.2f ($%.2f) | positions=%d, exposure=%.1f%%, daily_pnl=$%.2f",
            signal.side, signal.pair, signal.amount, signal.price,
            trade_value, len(self.open_positions), self.total_exposure_pct, self.daily_pnl,
        )
        return True

    # ── Position tracking ────────────────────────────────────────────────────

    def record_open(self, signal: Signal) -> None:
        """Track a newly opened position."""
        self.open_positions.append(Position(
            pair=signal.pair,
            side=signal.side,
            entry_price=signal.price,
            amount=signal.amount,
            strategy=signal.strategy.value,
            opened_at=utcnow().isoformat(),
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

    # ── Daily reset ──────────────────────────────────────────────────────────

    def reset_daily(self) -> None:
        """Called at midnight to reset daily counters."""
        logger.info("Daily reset — previous daily PnL: $%.4f", self.daily_pnl)
        self.daily_pnl = 0.0
        self.daily_pnl_by_pair.clear()
        if self.is_paused and "daily loss" in self._pause_reason:
            self.is_paused = False
            self._pause_reason = ""
            logger.info("Bot unpaused after daily reset")

    # ── Pause control ────────────────────────────────────────────────────────

    def unpause(self) -> None:
        """Manually unpause the bot."""
        self.is_paused = False
        self._pause_reason = ""
        logger.info("Bot manually unpaused")

    def _pause(self, reason: str) -> None:
        self.is_paused = True
        self._pause_reason = reason
        logger.warning("BOT PAUSED: %s", reason)

    # ── Status ───────────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        return {
            "capital": self.capital,
            "daily_pnl": self.daily_pnl,
            "daily_loss_pct": self.daily_loss_pct,
            "open_positions": len(self.open_positions),
            "total_exposure_pct": self.total_exposure_pct,
            "win_rate": self.win_rate,
            "is_paused": self.is_paused,
            "pause_reason": self._pause_reason,
            "pairs_with_positions": list(self.pairs_with_positions()),
        }

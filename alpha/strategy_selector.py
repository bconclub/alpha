"""Strategy selector — picks the best strategy per pair based on market conditions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from alpha.market_analyzer import MarketAnalysis
from alpha.strategies.base import MarketCondition, StrategyName
from alpha.utils import iso_now, setup_logger

if TYPE_CHECKING:
    from alpha.db import Database

logger = setup_logger("strategy_selector")


class StrategySelector:
    """Maps market conditions to the optimal strategy, tracked per pair."""

    def __init__(self, db: Any | None = None, arb_enabled: bool = True) -> None:
        self.db: Database | None = db
        self.arb_enabled = arb_enabled
        # Per-pair strategy tracking
        self._current: dict[str, StrategyName | None] = {}

    def current_strategy(self, pair: str | None = None) -> StrategyName | None:
        """Return the currently selected strategy for a pair."""
        if pair is None:
            # Backward-compat: return first entry
            return next(iter(self._current.values()), None)
        return self._current.get(pair)

    async def select(
        self,
        analysis: MarketAnalysis,
        arb_opportunity: bool = False,
    ) -> StrategyName | None:
        """Choose a strategy for the pair in the analysis.

        Returns None if the pair should pause (e.g. extreme volatility).
        """
        pair = analysis.pair
        previous = self._current.get(pair)

        # Priority 1: arbitrage if detected
        if self.arb_enabled and arb_opportunity:
            selected = StrategyName.ARBITRAGE
            reason = f"[{pair}] Arbitrage opportunity detected (cross-exchange spread > threshold)"

        # Priority 2: market-condition mapping
        elif analysis.condition == MarketCondition.SIDEWAYS:
            selected = StrategyName.GRID
            reason = f"[{pair}] Sideways market — {analysis.reason}"

        elif analysis.condition == MarketCondition.TRENDING:
            selected = StrategyName.MOMENTUM
            reason = f"[{pair}] Trending market — {analysis.reason}"

        elif analysis.condition == MarketCondition.VOLATILE:
            # High volatility: pause or use tight grid
            if analysis.atr and analysis.volume_ratio > 2.0:
                # Extreme — pause this pair
                logger.warning("[%s] Extreme volatility detected — pausing", pair)
                self._current[pair] = None
                await self._log_selection(analysis, None, f"[{pair}] Extreme volatility — pausing")
                return None
            else:
                # Moderate volatility — tight grid
                selected = StrategyName.GRID
                reason = f"[{pair}] Moderate volatility — using tight grid — {analysis.reason}"
        else:
            selected = StrategyName.GRID
            reason = f"[{pair}] Fallback to grid"

        switched = previous != selected
        self._current[pair] = selected

        if switched:
            logger.info(
                "[%s] Strategy switched: %s → %s | %s",
                pair,
                previous.value if previous else "none",
                selected.value,
                reason,
            )
        else:
            logger.debug("[%s] Strategy unchanged: %s", pair, selected.value)

        await self._log_selection(analysis, selected, reason)
        return selected

    async def _log_selection(
        self,
        analysis: MarketAnalysis,
        strategy: StrategyName | None,
        reason: str,
    ) -> None:
        if self.db is None:
            return
        try:
            await self.db.log_strategy_selection({
                "timestamp": iso_now(),
                "pair": analysis.pair,
                "market_condition": analysis.condition.value,
                "adx": analysis.adx,
                "atr": analysis.atr,
                "bb_width": analysis.bb_width,
                "rsi": analysis.rsi,
                "volume_ratio": analysis.volume_ratio,
                "strategy_selected": strategy.value if strategy else "paused",
                "reason": reason,
            })
        except Exception:
            logger.exception("Failed to log strategy selection to DB")

"""Alpha — main entry point. Multi-pair concurrent orchestrator."""

from __future__ import annotations

import asyncio
import signal
import sys
from typing import Any

import aiohttp
import ccxt.async_support as ccxt
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from alpha.alerts import AlertManager
from alpha.config import config
from alpha.db import Database
from alpha.market_analyzer import MarketAnalyzer
from alpha.risk_manager import RiskManager
from alpha.strategies.arbitrage import ArbitrageStrategy
from alpha.strategies.base import BaseStrategy, StrategyName
from alpha.strategies.grid import GridStrategy
from alpha.strategies.momentum import MomentumStrategy
from alpha.strategy_selector import StrategySelector
from alpha.trade_executor import TradeExecutor
from alpha.utils import setup_logger

logger = setup_logger("main")


class AlphaBot:
    """Top-level bot orchestrator — runs multiple pairs concurrently."""

    def __init__(self) -> None:
        # Core components (initialized in start())
        self.binance: ccxt.Exchange | None = None
        self.kucoin: ccxt.Exchange | None = None
        self.db = Database()
        self.alerts = AlertManager()
        self.risk_manager = RiskManager()
        self.executor: TradeExecutor | None = None
        self.analyzer: MarketAnalyzer | None = None
        self.selector: StrategySelector | None = None

        # Multi-pair
        self.pairs: list[str] = config.trading.pairs

        # Per-pair strategy instances:  pair → {StrategyName → instance}
        self._strategies: dict[str, dict[StrategyName, BaseStrategy]] = {}
        # Per-pair active strategy:  pair → running strategy or None
        self._active_strategies: dict[str, BaseStrategy | None] = {}

        # Scheduler
        self._scheduler = AsyncIOScheduler()

        # Shutdown flag
        self._running = False

    async def start(self) -> None:
        """Initialize all components and start the main loop."""
        logger.info("=" * 60)
        logger.info("  ALPHA BOT — Starting up (multi-pair)")
        logger.info("  Pairs: %s", ", ".join(self.pairs))
        logger.info("  Capital: $%.2f", config.trading.starting_capital)
        logger.info("=" * 60)

        # Connect external services
        await self._init_exchanges()
        await self.db.connect()
        await self.alerts.connect()

        # Restore state from DB if available
        await self._restore_state()

        # Build components
        self.executor = TradeExecutor(self.binance, db=self.db, alerts=self.alerts)  # type: ignore[arg-type]
        self.analyzer = MarketAnalyzer(self.binance, pair=self.pairs[0])  # type: ignore[arg-type]
        self.selector = StrategySelector(db=self.db, arb_enabled=self.kucoin is not None)

        # Load Binance minimum order sizes for all pairs
        await self.executor.load_market_limits(self.pairs)

        # Register strategies per pair
        for pair in self.pairs:
            self._strategies[pair] = {
                StrategyName.GRID: GridStrategy(pair, self.executor, self.risk_manager),
                StrategyName.MOMENTUM: MomentumStrategy(pair, self.executor, self.risk_manager),
                StrategyName.ARBITRAGE: ArbitrageStrategy(
                    pair, self.executor, self.risk_manager, self.kucoin,
                ),
            }
            self._active_strategies[pair] = None

        # Schedule periodic tasks
        self._scheduler.add_job(
            self._analysis_cycle, "interval",
            seconds=config.trading.analysis_interval_sec,
        )
        self._scheduler.add_job(self._daily_reset, "cron", hour=0, minute=0)
        self._scheduler.add_job(self._save_status, "interval", minutes=5)
        self._scheduler.add_job(self._poll_commands, "interval", seconds=10)
        self._scheduler.start()

        # Notify
        await self.alerts.send_bot_started(self.pairs, config.trading.starting_capital)

        # Register shutdown signals
        self._running = True
        if sys.platform != "win32":
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown("Signal received")))

        # Run initial analysis immediately
        await self._analysis_cycle()

        # Keep running
        logger.info("Bot running — %d pairs — press Ctrl+C to stop", len(self.pairs))
        try:
            while self._running:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, asyncio.CancelledError):
            await self.shutdown("KeyboardInterrupt")

    async def shutdown(self, reason: str = "Shutdown requested") -> None:
        """Graceful shutdown — stop all strategies, save state, close connections."""
        if not self._running:
            return
        self._running = False
        logger.info("Shutting down: %s", reason)

        # Stop all active strategies concurrently
        stop_tasks = []
        for pair, strategy in self._active_strategies.items():
            if strategy:
                stop_tasks.append(strategy.stop())
        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)
        self._active_strategies = {p: None for p in self.pairs}

        # Save final state
        await self._save_status()

        # Stop scheduler
        self._scheduler.shutdown(wait=False)

        # Notify
        await self.alerts.send_bot_stopped(reason)

        # Close exchange connections
        if self.binance:
            await self.binance.close()
        if self.kucoin:
            await self.kucoin.close()

        logger.info("Shutdown complete")

    # -- Core cycle ------------------------------------------------------------

    async def _analysis_cycle(self) -> None:
        """Analyze all pairs concurrently, then switch strategies by signal strength priority."""
        if not self._running:
            return

        try:
            # 1. Analyze all pairs in parallel
            analysis_tasks = [
                self.analyzer.analyze(pair)  # type: ignore[union-attr]
                for pair in self.pairs
            ]
            results = await asyncio.gather(*analysis_tasks, return_exceptions=True)

            # 2. Collect successful analyses
            analyses = []
            for pair, result in zip(self.pairs, results):
                if isinstance(result, Exception):
                    logger.error("Analysis failed for %s: %s", pair, result)
                else:
                    analyses.append(result)

            # 3. Sort by signal_strength descending — best opportunities first
            analyses.sort(key=lambda a: a.signal_strength, reverse=True)

            logger.info(
                "Analysis complete — strength ranking: %s",
                ", ".join(f"{a.pair}={a.signal_strength:.0f}" for a in analyses),
            )

            # 4. Select strategy per pair and switch
            for analysis in analyses:
                pair = analysis.pair

                # Check for arb opportunity on this pair
                arb_opportunity = False
                if self.kucoin:
                    arb_opportunity = await self._check_arb_opportunity(pair)

                selected = await self.selector.select(analysis, arb_opportunity)  # type: ignore[union-attr]
                await self._switch_strategy(pair, selected)

        except Exception:
            logger.exception("Error in analysis cycle")

    async def _switch_strategy(self, pair: str, name: StrategyName | None) -> None:
        """Stop current strategy for a pair and start the new one."""
        current = self._active_strategies.get(pair)
        current_name = current.name if current else None

        if current_name == name:
            return  # no change

        # Stop current
        if current:
            await current.stop()
            self._active_strategies[pair] = None

        if name is None:
            logger.info("[%s] No strategy active (paused)", pair)
            return

        # Start new
        pair_strategies = self._strategies.get(pair, {})
        strategy = pair_strategies.get(name)
        if strategy is None:
            logger.error("[%s] Strategy %s not registered", pair, name)
            return

        self._active_strategies[pair] = strategy
        await strategy.start()

        # Alert
        last = self.analyzer.last_analysis_for(pair) if self.analyzer else None  # type: ignore[union-attr]
        await self.alerts.send_strategy_switch(
            pair=pair,
            old=current_name.value if current_name else None,
            new=name.value,
            reason=last.reason if last else "initial",
        )

    async def _check_arb_opportunity(self, pair: str) -> bool:
        """Quick check if there's a cross-exchange spread for a pair."""
        if not self.kucoin:
            return False
        try:
            binance_ticker = await self.binance.fetch_ticker(pair)  # type: ignore[union-attr]
            kucoin_ticker = await self.kucoin.fetch_ticker(pair)
            bp = binance_ticker["last"]
            kp = kucoin_ticker["last"]
            spread_pct = abs((bp - kp) / bp) * 100
            return spread_pct > config.trading.arb_min_spread_pct
        except Exception:
            return False

    # -- Scheduled jobs --------------------------------------------------------

    async def _daily_reset(self) -> None:
        """Midnight reset: send daily summary, reset daily P&L."""
        logger.info("Daily reset triggered")

        # Build active strategies map for summary
        active_map: dict[str, str | None] = {}
        for pair in self.pairs:
            strat = self._active_strategies.get(pair)
            active_map[pair] = strat.name.value if strat else None

        await self.alerts.send_daily_summary(
            total_pnl=self.risk_manager.daily_pnl,
            win_rate=self.risk_manager.win_rate,
            trades_count=len(self.risk_manager.trade_results),
            capital=self.risk_manager.capital,
            active_strategies=active_map,
            pnl_by_pair=dict(self.risk_manager.daily_pnl_by_pair),
        )
        self.risk_manager.reset_daily()

    async def _save_status(self) -> None:
        """Persist bot state to Supabase for crash recovery + dashboard display."""
        rm = self.risk_manager

        # Build per-pair info
        active_map: dict[str, str | None] = {}
        for pair in self.pairs:
            strat = self._active_strategies.get(pair)
            active_map[pair] = strat.name.value if strat else None

        # Use primary pair's analysis for condition
        last = self.analyzer.last_analysis if self.analyzer else None

        status = {
            "total_pnl": rm.capital - config.trading.starting_capital,
            "daily_pnl": rm.daily_pnl,
            "daily_loss_pct": rm.daily_loss_pct,
            "win_rate": rm.win_rate,
            "total_trades": len(rm.trade_results),
            "open_positions": len(rm.open_positions),
            "active_strategy": active_map.get(self.pairs[0]) if self.pairs else None,
            "market_condition": last.condition.value if last else None,
            "capital": rm.capital,
            "pair": ", ".join(self.pairs),
            "is_running": self._running,
            "is_paused": rm.is_paused,
            "pause_reason": rm._pause_reason or None,
        }
        await self.db.save_bot_status(status)

    async def _poll_commands(self) -> None:
        """Check Supabase for pending dashboard commands and execute them."""
        try:
            commands = await self.db.poll_pending_commands()
            for cmd in commands:
                await self._handle_command(cmd)
        except Exception:
            logger.exception("Error polling commands")

    async def _handle_command(self, cmd: dict) -> None:
        """Process a single dashboard command."""
        cmd_id: int = cmd["id"]
        command: str = cmd["command"]
        params: dict = cmd.get("params") or {}
        result_msg = "ok"

        logger.info("Processing command %d: %s %s", cmd_id, command, params)

        try:
            if command == "pause":
                self.risk_manager.is_paused = True
                self.risk_manager._pause_reason = params.get("reason", "Paused via dashboard")
                # Stop all active strategies
                stop_tasks = []
                for pair, strategy in self._active_strategies.items():
                    if strategy:
                        stop_tasks.append(strategy.stop())
                        self._active_strategies[pair] = None
                if stop_tasks:
                    await asyncio.gather(*stop_tasks, return_exceptions=True)
                await self.alerts.send_risk_alert("Bot paused via dashboard")
                result_msg = "Bot paused"

            elif command == "resume":
                self.risk_manager.unpause()
                await self._analysis_cycle()  # re-evaluate and start strategies
                await self.alerts.send_risk_alert("Bot resumed via dashboard")
                result_msg = "Bot resumed"

            elif command == "force_strategy":
                strategy_name = params.get("strategy")
                target_pair = params.get("pair", self.pairs[0])  # default to primary pair
                if strategy_name:
                    try:
                        target = StrategyName(strategy_name)
                        self.risk_manager.unpause()
                        await self._switch_strategy(target_pair, target)
                        result_msg = f"Forced {strategy_name} on {target_pair}"
                    except ValueError:
                        result_msg = f"Unknown strategy: {strategy_name}"
                else:
                    result_msg = "Missing 'strategy' param"

            elif command == "update_config":
                if "max_position_pct" in params:
                    self.risk_manager.max_position_pct = float(params["max_position_pct"])
                    result_msg = f"max_position_pct -> {params['max_position_pct']}"
                elif "daily_loss_limit_pct" in params:
                    self.risk_manager.daily_loss_limit_pct = float(params["daily_loss_limit_pct"])
                    result_msg = f"daily_loss_limit_pct -> {params['daily_loss_limit_pct']}"
                else:
                    result_msg = f"Config updated: {params}"
            else:
                result_msg = f"Unknown command: {command}"

        except Exception as e:
            result_msg = f"Error: {e}"
            logger.exception("Failed to handle command %d", cmd_id)

        await self.db.mark_command_executed(cmd_id, result_msg)

    async def _restore_state(self) -> None:
        """Restore capital and state from last saved status."""
        last = await self.db.get_last_bot_status()
        if last:
            self.risk_manager.capital = last.get("capital", config.trading.starting_capital)
            logger.info("Restored state from DB — capital: $%.2f", self.risk_manager.capital)
        else:
            logger.info("No previous state found — starting fresh")

    # -- Exchange init ---------------------------------------------------------

    async def _init_exchanges(self) -> None:
        """Create ccxt exchange instances.

        Uses the threaded DNS resolver to avoid aiodns failures on Windows.
        """
        # Force threaded resolver so aiohttp doesn't depend on aiodns/c-ares
        resolver = aiohttp.resolver.ThreadedResolver()
        connector = aiohttp.TCPConnector(resolver=resolver, ssl=True)
        session = aiohttp.ClientSession(connector=connector)

        # Binance (required)
        self.binance = ccxt.binance({
            "apiKey": config.binance.api_key,
            "secret": config.binance.secret,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
            "session": session,
        })
        if not config.binance.api_key:
            logger.warning("Binance API key not set — running in sandbox/read-only mode")
            self.binance.set_sandbox_mode(True)

        # KuCoin (optional, for arbitrage)
        if config.kucoin.api_key:
            kucoin_session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(resolver=aiohttp.resolver.ThreadedResolver(), ssl=True)
            )
            self.kucoin = ccxt.kucoin({
                "apiKey": config.kucoin.api_key,
                "secret": config.kucoin.secret,
                "password": config.kucoin.passphrase,
                "enableRateLimit": True,
                "session": kucoin_session,
            })
            logger.info("KuCoin exchange initialized (arbitrage enabled)")
        else:
            logger.info("KuCoin credentials not set — arbitrage disabled")


def main() -> None:
    """Entry point."""
    bot = AlphaBot()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        logger.info("Interrupted")


if __name__ == "__main__":
    main()

"""Alpha — main entry point. Multi-pair, multi-exchange concurrent orchestrator.

Supports Bybit (futures), Binance (spot), and Delta Exchange India (options) in parallel.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import os
import signal
import sys
import time
from typing import Any

import aiohttp
import ccxt.async_support as ccxt
import sdnotify
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from alpha.alerts import AlertManager
from alpha.config import config
from alpha.db import Database
from alpha.market_analyzer import MarketAnalyzer
from alpha.price_feed import PriceFeed
from alpha.risk_manager import RiskManager
from alpha.paper_futures import PaperFuturesStrategy, build_paper_futures_strategies
from alpha.paper_options import BasePaperOptions, build_paper_options_strategies
from alpha.strategies.base import Signal, StrategyName
from alpha.strategies.options_scalp import OptionsScalpStrategy
from alpha.strategies.scalp import ScalpStrategy
from alpha.trade_executor import TradeExecutor, DELTA_CONTRACT_SIZE, calc_pnl, is_option_symbol
from alpha.utils import iso_now, setup_logger

logger = setup_logger("main")


class AlphaBot:
    """Top-level bot orchestrator — runs multiple pairs and exchanges concurrently."""

    def __init__(self) -> None:
        # Core components (initialized in start())
        self.delta: ccxt.Exchange | None = None
        self.delta_options: ccxt.Exchange | None = None  # Delta options exchange
        self.db = Database()
        self.alerts = AlertManager()
        self.risk_manager = RiskManager()
        self.executor: TradeExecutor | None = None
        self.delta_analyzer: MarketAnalyzer | None = None

        # Delta futures pairs (used for market analysis → options signals)
        self.delta_pairs: list[str] = config.delta.pairs
        self.paper_futures_pairs: list[str] = []

        # Scalp strategies: pair -> ScalpStrategy (provides signals to options)
        self._scalp_strategies: dict[str, ScalpStrategy] = {}
        # Options overlay strategies: pair -> OptionsScalpStrategy
        self._options_strategies: dict[str, OptionsScalpStrategy] = {}
        # Independent paper futures strategies: pair -> paper-only strategy lanes
        self._paper_futures_strategies: dict[str, list[PaperFuturesStrategy]] = {}
        # Independent paper OPTIONS strategies: pair -> buy-only option lanes
        self._paper_options_strategies: dict[str, list[BasePaperOptions]] = {}
        # Paper lab universe — BTC + ETH only.
        self.paper_pairs: list[str] = []

        # PAPER-ONLY MODE: when on, NO live orders are ever placed (live options
        # + live scalp entries disabled). Only the paper lab runs. Durable across
        # restarts so a crash-restart can never silently resume live trading.
        # Default ON until the paper lab proves a real edge. Flip with PAPER_ONLY=0.
        self.paper_only: bool = os.getenv("PAPER_ONLY", "1").strip().lower() not in ("0", "false", "no", "off")

        # ─── GPFC #43: orphan-adopt cooldowns ───
        # Reconciler tries to adopt any live Delta options position the bot
        # isn't actively managing. When adoption must be deferred (strategy
        # already busy with another symbol, or no strategy registered for
        # that asset), we fire a single telegram alert per symbol rather
        # than spamming every 60 s. Keys are cleared once the orphan is
        # either adopted or disappears from Delta.
        self._orphan_defer_alerted: set[str] = set()

        # ─── GPFC #48: per-symbol empty-cycle counter ───
        # Only close an option row as RECONCILE_ORPHAN_CLOSED after Delta has
        # returned *no* position for that symbol across 2 consecutive
        # reconcile cycles — one empty read is often a transient positions-API
        # glitch. Keys: option symbol. Value: consecutive empty cycles.
        self._option_symbol_empty_cycles: dict[str, int] = {}

        # Strategy enable/disable flags (toggled from dashboard)
        self._options_enabled: bool = True

        # Exchange enable/disable flags
        self._delta_enabled: bool = True

        # WebSocket price feed for real-time exit checks
        self._price_feed: PriceFeed | None = None

        # Scheduler
        self._scheduler = AsyncIOScheduler()

        # systemd watchdog notifier
        self._sd_notifier = sdnotify.SystemdNotifier()

        # Shutdown flag
        self._running = False
        self._start_time: float = 0.0  # monotonic time for uptime calc

        # Suppress strategy-change alerts on the very first analysis cycle
        self._has_run_first_cycle: bool = False

        # Latest analysis data — cached for hourly market update
        self._latest_analyses: list[dict[str, Any]] = []

        # Hourly tracking
        self._hourly_pnl: float = 0.0
        self._hourly_wins: int = 0
        self._hourly_losses: int = 0
        # Track last analysis cycle time for diagnostics
        self._last_cycle_time: float = time.monotonic()

        # ── Session-based reporting (IST) ──────────────────────────────
        # Session boundaries in IST hours: (start_hour, start_min, end_hour, end_min, name)
        self._sessions: list[tuple[int, int, int, int, str]] = [
            (8, 0, 12, 0, "Morning"),       # 08:00-12:00 IST
            (12, 0, 17, 30, "Afternoon"),    # 12:00-17:30 IST
            (17, 30, 22, 0, "Evening"),      # 17:30-22:00 IST
            (22, 0, 8, 0, "Night"),          # 22:00-08:00 IST (crosses midnight)
        ]
        self._session_trades: list[dict[str, Any]] = []
        self._current_session_name: str | None = None

        # Orphan grace: first-seen time for untracked positions (key: "exchange:pair")
        self._position_first_seen: dict[str, float] = {}
        self.ORPHAN_GRACE_S = 120  # seconds before orphan close fires

        # Orphan close retry tracking (key: "exchange:pair")
        self._orphan_fail_count: dict[str, int] = {}
        self._orphan_gave_up: set[str] = set()  # positions we've given up on
        self.ORPHAN_MAX_RETRIES = 3  # stop trying after N failures

    @property
    def all_pairs(self) -> list[str]:
        """All tracked pairs (Delta only)."""
        return self.delta_pairs if self.delta else []

    def _get_scalp(self, pair: str, exchange: str | None = None) -> ScalpStrategy | None:
        """Look up a scalp strategy by bare pair name (Delta only)."""
        if exchange:
            return self._scalp_strategies.get(f"{exchange}:{pair}")
        return self._scalp_strategies.get(f"delta:{pair}")

    def _paper_btc_eth_pairs(self) -> list[str]:
        """Paper lab universe: BTC + ETH underlying perps only."""
        candidates = list(dict.fromkeys(
            (config.delta.options_pairs or []) + (self.delta_pairs or [])
        ))
        wanted = [p for p in candidates if p.split("/")[0] in ("BTC", "ETH")]
        if not wanted:
            wanted = ["BTC/USD:USD", "ETH/USD:USD"]
        # de-dupe by base asset, keep BTC first then ETH
        seen: set[str] = set()
        ordered: list[str] = []
        for base in ("BTC", "ETH"):
            for p in wanted:
                if p.split("/")[0] == base and base not in seen:
                    ordered.append(p)
                    seen.add(base)
        return ordered

    async def _build_paper_pulse(self, params: dict[str, Any]) -> str:
        """Build the clean, fixed-format paper-lab Telegram pulse from the DB.

        Structure is deterministic (always identical shape); only the short
        'learned' / 'next' lines come from the routine via params.
        """
        loop = asyncio.get_running_loop()
        # V3 era cutover: both labs re-seeded to exactly $1,000 at this moment.
        # The pulse reports the CURRENT era only; V2 history stays in the DB
        # and engine/PAPER_RESULTS.md.
        era_start = "2026-06-09T21:21:00Z"
        era_seed = 1000.0

        def fetch(table: str, cols: str, time_col: str) -> list[dict[str, Any]]:
            try:
                return (
                    self.db.client.table(table).select(cols)
                    .gte(time_col, era_start).limit(2000).execute().data or []
                )
            except Exception:
                return []

        opt = await loop.run_in_executor(None, lambda: fetch("paper_options_trades", "setup_type,status,pnl_usd", "opened_at"))
        fut = await loop.run_in_executor(None, lambda: fetch("paper_futures_trades", "setup_type,status,pnl_usd", "opened_at"))
        dep = await loop.run_in_executor(None, lambda: fetch("paper_deposits", "lab,amount,kind", "created_at"))

        def funded(lab: str) -> float:
            return era_seed + sum(float(d.get("amount") or 0) for d in dep if d.get("lab") == lab)

        def burns(lab: str) -> int:
            return sum(1 for d in dep if d.get("lab") == lab and d.get("kind") == "refill")

        def net(rows: list[dict[str, Any]]) -> float:
            return sum(float(r.get("pnl_usd") or 0) for r in rows if r.get("status") == "closed")

        net_opt, net_fut = net(opt), net(fut)
        bal_opt = funded("options") + net_opt
        bal_fut = funded("futures") + net_fut

        lane: dict[str, float] = {}
        for r in opt + fut:
            if r.get("status") == "closed":
                k = r.get("setup_type") or "?"
                lane[k] = lane.get(k, 0.0) + float(r.get("pnl_usd") or 0)
        best = max(lane.items(), key=lambda x: x[1], default=(None, 0.0))
        worst = min(lane.items(), key=lambda x: x[1], default=(None, 0.0))
        working = f"{best[0]} +${best[1]:,.0f}" if best[0] and best[1] > 0 else "nothing yet"
        losing = f"{worst[0]} −${abs(worst[1]):,.0f}" if worst[0] and worst[1] < 0 else "—"

        # The message is sent with HTML parse mode — free text MUST be escaped
        # or strings like "lev <=10x" kill the send (Telegram: unsupported tag).
        from html import escape

        working = escape(working)
        losing = escape(losing)
        learned = escape((str(params.get("learned") or "").strip()) or "gathering data")
        nxt = escape((str(params.get("next") or "").strip()) or "keep the labs running")

        def line(label: str, bal: float, n: float) -> str:
            dot = "🟢" if n >= 0 else "🔴"
            sign = "+" if n >= 0 else "−"
            return f"{dot} {label}  ${bal:,.0f}  ({sign}${abs(n):,.0f})"

        return (
            "🤖 <b>Alpha Paper Lab</b>\n\n"
            "<b>P/L</b>\n"
            f"{line('Options', bal_opt, net_opt)}\n"
            f"{line('Futures', bal_fut, net_fut)}\n\n"
            f"🟢 <b>Working</b> — {working}\n\n"
            f"🔴 <b>Losing</b> — {losing}\n\n"
            f"🧠 <b>Learned</b>\n{learned}\n\n"
            f"🔧 <b>Next</b>\n{nxt}\n\n"
            f"✅ Live OFF · Burns {burns('options')}× / {burns('futures')}×"
        )

    async def _select_top_delta_futures_pairs(self, limit: int = 5) -> list[str]:
        """Pick the most liquid active Delta USD perpetuals for paper futures.

        This is paper-only. Live options continue using config.delta.options_pairs.
        """
        fallback = list(dict.fromkeys(self.delta_pairs or config.delta.options_pairs))
        if not self.delta:
            return fallback[:limit]
        try:
            await self.delta.load_markets()
            markets = [
                m for m in self.delta.markets.values()
                if m.get("active")
                and m.get("swap")
                and m.get("linear")
                and m.get("quote") == "USD"
                and m.get("symbol")
            ]
            symbols = [str(m["symbol"]) for m in markets]
            tickers = await self.delta.fetch_tickers(symbols)
            ranked: list[tuple[float, str]] = []
            for symbol in symbols:
                ticker = tickers.get(symbol) or {}
                quote_volume = float(ticker.get("quoteVolume") or 0.0)
                if quote_volume <= 0:
                    continue
                ranked.append((quote_volume, symbol))
            ranked.sort(reverse=True)
            selected = [symbol for _, symbol in ranked[:limit]]
            if not selected:
                raise RuntimeError("no Delta futures tickers had quote volume")
            logger.info(
                "Paper futures top-volume Delta pairs: %s",
                ", ".join(f"{symbol}=${volume:,.0f}" for volume, symbol in ranked[:limit]),
            )
            return selected
        except Exception as exc:
            logger.warning(
                "Could not select top Delta futures by volume (%s); falling back to %s",
                exc,
                ", ".join(fallback[:limit]) or "none",
            )
            return fallback[:limit]

    async def start(self) -> None:
        """Initialize all components and start the main loop."""
        from pathlib import Path
        from alpha.utils import get_version
        version = get_version()

        # Load soul document
        soul_path = Path(__file__).resolve().parent.parent / "SOUL.md"
        if soul_path.exists():
            soul_lines = soul_path.read_text().strip().splitlines()
            for line in soul_lines[:3]:
                if line.strip():
                    logger.info("  %s", line.strip().lstrip("#").strip())

        logger.info("=" * 60)
        logger.info("  ALPHA v%s — Delta Options Agent", version)
        logger.info("  DELTA (options): %s",
                     ", ".join(config.delta.options_pairs) if config.delta.options_enabled else "disabled")
        logger.info("  DELTA (futures/signals): %s, %dx leverage",
                     ", ".join(self.delta_pairs), config.delta.leverage)
        logger.info("  Soul: Momentum is everything. Speed wins. Never idle.")
        logger.info("=" * 60)

        # Connect external services
        await self._init_exchanges()
        await self.db.connect()
        await self._auto_changelog(version)
        await self.alerts.connect()

        # Immediate startup ping — proves Telegram is working before anything else runs
        try:
            logger.info(
                "[STARTUP] Telegram state: bot=%s chat_id=%s connected=%s",
                bool(self.alerts._bot), bool(self.alerts._chat_id), self.alerts.is_connected,
            )
            if self.alerts.is_connected:
                await self.alerts._send(f"\U0001f7e2 <b>ALPHA v{version}</b> starting...")
                logger.info("[STARTUP] Early Telegram ping sent OK")
            else:
                logger.error("[STARTUP] Telegram NOT connected — no startup message will be sent")
        except Exception:
            logger.exception("[STARTUP] Early Telegram ping failed")

        # Restore state from DB if available
        await self._restore_state()

        # Hook into risk_manager.record_close to track hourly stats
        _original_record_close = self.risk_manager.record_close

        def _tracked_record_close(pair: str, pnl: float) -> None:
            _original_record_close(pair, pnl)
            self._hourly_pnl += pnl
            if pnl >= 0:
                self._hourly_wins += 1
            else:
                self._hourly_losses += 1

        self.risk_manager.record_close = _tracked_record_close  # type: ignore[assignment]

        # Build components — Delta only (futures for signals + options for trading)
        self.executor = TradeExecutor(
            None,  # type: ignore[arg-type]  # no Binance
            db=self.db,
            alerts=self.alerts,
            delta_exchange=self.delta,
            risk_manager=self.risk_manager,
            options_exchange=self.delta_options,
        )

        if self.delta:
            self.delta_analyzer = MarketAnalyzer(
                self.delta, pair=self.delta_pairs[0] if self.delta_pairs else None,
            )

        # Load market limits for Delta only
        await self.executor.load_market_limits(
            [],  # no Binance spot pairs
            delta_pairs=self.delta_pairs if self.delta else None,
        )

        if self.delta:
            # Paper lab is BTC + ETH only (futures + options).
            self.paper_pairs = self._paper_btc_eth_pairs()
            self.paper_futures_pairs = self.paper_pairs

        # Register Delta scalp strategies (provide market signals to options)
        if self.delta:
            for pair in self.delta_pairs:
                self._scalp_strategies[f"delta:{pair}"] = ScalpStrategy(
                    pair, self.executor, self.risk_manager,
                    exchange=self.delta,
                    is_futures=True,
                    market_analyzer=self.delta_analyzer,
                    exchange_id="delta",
                )

        # Options overlay — buy CALLs/PUTs on 3/4+ scalp signals
        # Options use Delta exchange, signals come from Delta scalp strategies
        # PAPER-ONLY: skip building live options entirely (proven net-negative bleeder).
        # V3: legacy live strategies additionally require LIVE_MODE=legacy — the
        # only supported live path is the LiveMirror (LIVE_MODE=mirror).
        self._live_mode = os.getenv("LIVE_MODE", "off").strip().lower()
        if (
            self.delta and self.delta_options and self._options_enabled
            and not self.paper_only and self._live_mode == "legacy"
        ):
            for pair in config.delta.options_pairs:
                # Map options pair to Delta scalp strategy (delta-prefixed keys)
                base = pair.split("/")[0]
                scalp = self._scalp_strategies.get(f"delta:{pair}")
                if scalp is None:
                    # Try matching by base asset within delta-prefixed keys
                    scalp = next(
                        (s for p, s in self._scalp_strategies.items() if p.startswith(f"delta:{base}/")),
                        None,
                    )
                if scalp is None:
                    logger.warning("Options pair %s — no matching Delta scalp strategy", pair)
                    continue
                opts = OptionsScalpStrategy(
                    pair, self.executor, self.risk_manager,
                    options_exchange=self.delta_options,
                    futures_exchange=self.delta,
                    scalp_strategy=scalp,
                    market_analyzer=self.delta_analyzer,
                    db=self.db,
                )
                opts._alpha_bot = self  # back-ref for session tracking
                self._options_strategies[pair] = opts

        # Void any paper trades left 'open' by a previous (now-dead) process —
        # we lost their in-memory state on restart, so they're ghost rows.
        if self.delta:
            await self.db.cancel_orphan_paper_trades()

        # Independent paper futures experiments. These never place exchange
        # orders; they only write paper rows for comparing futures-style logic.
        if self.delta:
            for pair in self.paper_futures_pairs:
                self._paper_futures_strategies[pair] = build_paper_futures_strategies(
                    pair,
                    self.delta,
                    self.db,
                    self._scalp_strategies.get(f"delta:{pair}"),
                )

        # Independent paper OPTIONS lab (buy-only, BTC/ETH). Reads the real
        # Delta option chain + premiums; never places orders.
        if self.delta and self.delta_options:
            for pair in self.paper_pairs:
                self._paper_options_strategies[pair] = build_paper_options_strategies(
                    pair,
                    self.delta_options,
                    self.delta,
                    self.db,
                )

        # PAPER-ONLY: hard-block every live entry path via the risk manager so a
        # restart can never resume real trading. Paper lanes ignore this flag.
        # The legacy scalp/options live paths also stay blocked unless
        # LIVE_MODE=legacy is set explicitly (the V3 live path is LiveMirror,
        # which manages its own rails and ignores the risk-manager pause).
        if self.paper_only:
            self.risk_manager.is_paused = True
            self.risk_manager._pause_reason = "PAPER-ONLY mode (no live trading)"
            logger.warning("⚠️ PAPER-ONLY MODE — live trading disabled; only paper lab runs")
        elif self._live_mode != "legacy":
            self.risk_manager.is_paused = True
            self.risk_manager._pause_reason = f"LIVE_MODE={self._live_mode or 'off'} (legacy live paths blocked)"
            logger.warning("⚠️ Legacy live paths blocked (LIVE_MODE=%s) — only LiveMirror may trade", self._live_mode)

        # LiveMirror — the V3 live path: mirrors the single best paper signal
        # with tiny size and hard rails. Requires PAPER_ONLY=0 AND LIVE_MODE=mirror.
        self.live_mirror = None
        if self.delta and self._live_mode == "mirror" and not self.paper_only:
            from alpha.live_mirror import LiveMirror

            self.live_mirror = LiveMirror(
                self.delta,
                self.db,
                self.alerts,
                balance_fn=lambda: self._fetch_portfolio_usd(self.delta),
            )
        elif self._live_mode == "mirror":
            logger.info("LiveMirror armed but INACTIVE (PAPER_ONLY is on)")

        # Inject restored position state into strategy instances
        await self._restore_strategy_state()

        # ── Close orphaned positions from removed strategies ─────────────
        # If any open trades exist from non-scalp strategies (e.g. futures_momentum),
        # close them immediately at market to free up margin.
        await self._close_orphaned_positions()

        # ── ORPHAN PROTECTION: close any exchange positions not in bot memory ──
        await self._reconcile_exchange_positions()

        # Start Delta scalp strategies (signal generation for options)
        started = 0
        for pair, scalp in self._scalp_strategies.items():
            if not self._delta_enabled:
                logger.info("Skipping %s — delta exchange disabled", pair)
                continue
            await scalp.start()
            started += 1
        logger.info("Delta scalp (signal gen) started on %d/%d pairs", started, len(self._scalp_strategies))

        # Load pair/setup configs from DB → apply to scalp strategies
        await self._load_pair_setup_configs()

        # Start options strategies (gated by delta enabled flag)
        for pair, opts in self._options_strategies.items():
            if not self._delta_enabled:
                logger.info("Skipping options %s — delta exchange disabled", pair)
                continue
            await opts.start()
        if self._options_strategies:
            logger.info("Options overlay started on %d pairs", len(self._options_strategies))

        paper_started = 0
        paper_total = sum(len(strategies) for strategies in self._paper_futures_strategies.values())
        for pair, paper_strategies in self._paper_futures_strategies.items():
            if not self._delta_enabled:
                logger.info("Skipping paper futures %s — delta exchange disabled", pair)
                continue
            for paper in paper_strategies:
                await paper.start()
                paper_started += 1
        if self._paper_futures_strategies:
            logger.info(
                "Paper futures experiments started on %d/%d strategy lanes (%s)",
                paper_started,
                paper_total,
                ", ".join(self.paper_futures_pairs),
            )

        if self.live_mirror:
            await self.live_mirror.start()

        # Start paper OPTIONS lanes (buy-only, BTC/ETH)
        opt_started = 0
        opt_total = sum(len(s) for s in self._paper_options_strategies.values())
        for pair, opt_lanes in self._paper_options_strategies.items():
            if not self._delta_enabled:
                logger.info("Skipping paper options %s — delta exchange disabled", pair)
                continue
            for lane in opt_lanes:
                await lane.start()
                opt_started += 1
        if self._paper_options_strategies:
            logger.info(
                "Paper OPTIONS lab started on %d/%d lanes (%s)",
                opt_started,
                opt_total,
                ", ".join(self.paper_pairs),
            )

        # ── GPFC #48: merge duplicate open rows for the same symbol ──
        await self._merge_duplicate_open_options()

        # ── ORPHAN_STARTUP: close stale DB trades with no exchange position ──
        await self._close_orphan_options_on_startup()

        # Start WebSocket price feed — Delta only (for exit checks + premium monitoring)
        try:
            self._price_feed = PriceFeed(
                strategies=self._scalp_strategies,
                option_strategies=self._options_strategies,
                delta_pairs=self.delta_pairs if self.delta else [],
                delta_testnet=config.delta.testnet,
            )
            await self._price_feed.start()
        except Exception:
            logger.exception("PriceFeed failed to start — REST polling continues as fallback")
            self._price_feed = None

        # Schedule periodic tasks
        self._scheduler.add_job(
            self._analysis_cycle, "interval",
            seconds=config.trading.analysis_interval_sec,
        )
        self._scheduler.add_job(self._daily_reset, "cron", hour=18, minute=30)  # midnight IST = 18:30 UTC
        # 3x daily updates: 8 AM, 12 PM, 8 PM IST (2:30, 6:30, 14:30 UTC)
        self._scheduler.add_job(self._hourly_report, "cron", hour="2,6,14", minute=30)
        # Session summaries at IST boundaries (converted to UTC):
        # 12:00 IST = 06:30 UTC (end Morning), 17:30 IST = 12:00 UTC (end Afternoon),
        # 22:00 IST = 16:30 UTC (end Evening), 08:00 IST = 02:30 UTC (end Night)
        self._scheduler.add_job(
            lambda: asyncio.ensure_future(self._session_summary("Morning", "08:00-12:00")),
            "cron", hour=6, minute=30,
        )
        self._scheduler.add_job(
            lambda: asyncio.ensure_future(self._session_summary("Afternoon", "12:00-17:30")),
            "cron", hour=12, minute=0,
        )
        self._scheduler.add_job(
            lambda: asyncio.ensure_future(self._session_summary("Evening", "17:30-22:00")),
            "cron", hour=16, minute=30,
        )
        self._scheduler.add_job(
            lambda: asyncio.ensure_future(self._session_summary("Night", "22:00-08:00")),
            "cron", hour=2, minute=30,
        )
        self._scheduler.add_job(self._save_status, "interval", minutes=2)
        self._scheduler.add_job(self._reconcile_exchange_positions, "interval", seconds=60)
        self._scheduler.add_job(self._telegram_health_check, "interval", minutes=5)
        self._scheduler.add_job(self._poll_commands, "interval", seconds=5)
        # GPFC #77: reconciler disabled in the live loop — was creating phantom ghost rows.
        # Still invokable manually via CLI ("reconcile" / "smart_reconcile" commands).
        # self._scheduler.add_job(self._run_reconciliation, "interval", minutes=60)
        self._scheduler.add_job(self._watchdog_ping, "interval", seconds=60)
        self._scheduler.start()

        # Signal systemd that we are ready and alive
        self._sd_notifier.notify("READY=1")
        self._sd_notifier.notify("WATCHDOG=1")

        # Fetch Delta balance for trade sizing
        delta_bal: float | None = None
        try:
            delta_bal = await self._fetch_portfolio_usd(self.delta) if self.delta else None
            self.risk_manager.update_exchange_balances(delta=delta_bal)
        except Exception:
            logger.exception("[STARTUP] Failed to fetch Delta balance — continuing with defaults")

        total_capital = self.risk_manager.capital

        # ── Log per-pair affordability for Delta ────────────────────
        try:
            if self.delta and delta_bal is not None:
                from alpha.trade_executor import DELTA_CONTRACT_SIZE

                active_pairs: list[str] = []
                skipped_pairs: list[str] = []
                leverage = config.delta.leverage or 1
                for pair in self.delta_pairs:
                    contract_size = DELTA_CONTRACT_SIZE.get(pair, 0)
                    if contract_size <= 0:
                        logger.warning("[STARTUP] %s — unknown contract size, may not trade", pair)
                        skipped_pairs.append(pair)
                        continue
                    try:
                        ticker = await self.delta.fetch_ticker(pair)
                        price = float(ticker.get("last", 0) or 0)
                    except Exception:
                        price = 0
                    if price > 0:
                        collateral = (contract_size * price) / leverage
                        affordable = delta_bal >= collateral
                        status = "ACTIVE" if affordable else "SKIPPED"
                        logger.info(
                            "[STARTUP] %s %s — 1 contract=$%.2f collateral (%dx), bal=$%.2f",
                            pair, status, collateral, leverage, delta_bal,
                        )
                        if affordable:
                            active_pairs.append(pair)
                        else:
                            skipped_pairs.append(pair)
                    else:
                        logger.warning("[STARTUP] %s — could not fetch price", pair)
                        active_pairs.append(pair)
                logger.info(
                    "[STARTUP] Delta Active: %s | Skipped: %s",
                    ", ".join(active_pairs) or "none",
                    ", ".join(skipped_pairs) or "none",
                )
        except Exception:
            logger.exception("[STARTUP] Affordability check failed — continuing")

        # ── Build startup message as flat string ─────────────────────────
        try:
            from alpha.utils import get_version as _gv, ist_now as _ist

            _v = _gv()
            _now = _ist().strftime("%Y-%m-%d %H:%M IST")

            # Exchange
            _ex_lines = []
            if self.delta and delta_bal is not None and delta_bal > 0:
                _ex_lines.append(f"  \u2705 Delta ${delta_bal:,.2f}")
            elif self.delta:
                _ex_lines.append(f"  \u26a0\ufe0f Delta ${delta_bal or 0:,.2f}")
            else:
                _ex_lines.append(f"  \u274c Delta — no API key")

            # Strategies
            _st_lines = []
            n_opts = len(self._options_strategies)
            if self._options_enabled and self._delta_enabled and n_opts > 0:
                _st_lines.append(f"  \u2705 Options — {n_opts} pairs")
            else:
                _st_lines.append(f"  \u274c Options — disabled")

            # Market regime (from first scalp strategy)
            _regime = "unknown"
            for s in self._scalp_strategies.values():
                _regime = getattr(s, "_market_regime", "unknown")
                break

            # All pairs
            _all_bases = sorted({p.split("/")[0] for p in self.all_pairs})
            _pairs_str = " | ".join(_all_bases) if _all_bases else "none"

            msg = (
                f"\U0001f7e2 <b>ALPHA v{_v} — LIVE</b>\n"
                f"\n"
                f"<b>Balance:</b> <code>${total_capital:,.2f}</code>\n"
                f"<b>Pairs:</b> <code>{_pairs_str}</code>\n"
                f"\n"
                f"<b>Exchanges</b>\n"
                + "\n".join(_ex_lines) + "\n"
                f"\n"
                f"<b>Strategies</b>\n"
                + "\n".join(_st_lines) + "\n"
                f"\n"
                f"<b>Market:</b> <code>{_regime}</code>\n"
                f"<b>Time:</b> <code>{_now}</code>"
            )

            logger.info("[STARTUP] Sending status report to Telegram")
            await self.alerts.send_bot_started(msg)
            logger.info("[STARTUP] Status report sent OK")
        except Exception:
            logger.exception("[STARTUP] Failed to build/send startup message")

        # Register shutdown signals
        self._running = True
        self._start_time = time.monotonic()
        if sys.platform != "win32":
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown("Signal received")))

        # Run initial analysis immediately
        await self._analysis_cycle()
        asyncio.ensure_future(self._options_position_loop())

        # Keep running
        logger.info(
            "Bot running — Delta options (%d pairs) — Ctrl+C to stop",
            len(self._options_strategies),
        )
        try:
            while self._running:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, asyncio.CancelledError):
            await self.shutdown("KeyboardInterrupt")

    async def shutdown(self, reason: str = "Shutdown requested") -> None:
        """Graceful shutdown -- stop all strategies, save state, close connections."""
        if not self._running:
            return
        self._running = False
        self._sd_notifier.notify("STOPPING=1")
        logger.info("Shutting down: %s", reason)

        # Stop WebSocket price feed first (prevents new exit triggers)
        if self._price_feed:
            await self._price_feed.stop()

        # Stop all active strategies concurrently (scalp + options overlays + paper futures)
        stop_tasks = []
        for pair, scalp in self._scalp_strategies.items():
            if scalp.is_active:
                stop_tasks.append(scalp.stop())
        for pair, opts in self._options_strategies.items():
            if opts.is_active:
                stop_tasks.append(opts.stop())
        for pair, paper_strategies in self._paper_futures_strategies.items():
            for paper in paper_strategies:
                if paper.is_active:
                    stop_tasks.append(paper.stop())
        for pair, opt_lanes in self._paper_options_strategies.items():
            for lane in opt_lanes:
                if lane.is_active:
                    stop_tasks.append(lane.stop())
        if getattr(self, "live_mirror", None) and self.live_mirror.is_active:
            # NOTE: does not close the live position — it's real and persists
            # on the exchange; the mirror re-attaches to it on next boot.
            stop_tasks.append(self.live_mirror.stop())
        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)

        # Save final state
        await self._save_status()

        # Stop scheduler
        self._scheduler.shutdown(wait=False)

        # Notify (before closing Telegram session)
        await self.alerts.send_bot_stopped(reason)

        # Close Telegram bot session (prevents "Unclosed client session" warnings)
        await self.alerts.disconnect()

        # Close exchange connections
        if self.delta:
            await self.delta.close()
        if self.delta_options:
            await self.delta_options.close()

        logger.info("Shutdown complete")

    # -- Core cycle ------------------------------------------------------------

    async def _options_position_loop(self) -> None:
        """Fast 10s exit check loop for open options positions — independent of 5min analysis cycle."""
        while self._running:
            await asyncio.sleep(10)
            for opts in self._options_strategies.values():
                if opts.in_position:
                    try:
                        signals = await opts._check_option_exit()
                        for signal in signals:
                            if self.risk_manager.approve_signal(signal):
                                order = await self.executor.execute(signal)
                                if order is not None:
                                    opts.on_fill(signal, order)
                                else:
                                    opts.on_rejected(signal)
                            else:
                                logger.info(
                                    "Risk manager rejected fast options exit: %s",
                                    signal.reason,
                                )
                                opts.on_rejected(signal)
                    except Exception:
                        logger.exception(
                            "Fast options exit loop failed for %s",
                            getattr(opts, "option_symbol", None) or opts.pair,
                        )

    async def _analysis_cycle(self) -> None:
        """Analyze all pairs (both exchanges) concurrently, switch strategies by signal strength."""
        if not self._running:
            return
        self._last_cycle_time = time.monotonic()

        # Refresh pair/setup configs from DB (hot-reload every analysis cycle)
        try:
            await self._load_pair_setup_configs()
        except Exception:
            logger.exception("Failed to refresh pair/setup configs")

        try:
            # 1. Analyze Delta pairs (provides signals for options)
            analysis_pairs: list[str] = []
            analysis_tasks = []

            if self.delta and self.delta_analyzer:
                for pair in self.delta_pairs:
                    analysis_pairs.append(pair)
                    analysis_tasks.append(self.delta_analyzer.analyze(pair))

            results = await asyncio.gather(*analysis_tasks, return_exceptions=True)

            # 2. Collect successful analyses
            analyses = []
            for pair, result in zip(analysis_pairs, results):
                if isinstance(result, Exception):
                    logger.error("Analysis failed for %s: %s", pair, result)
                else:
                    analyses.append(result)

            # 3. Sort by signal_strength descending -- best opportunities first
            analyses.sort(key=lambda a: a.signal_strength, reverse=True)

            logger.info(
                "Analysis complete -- strength ranking: %s",
                ", ".join(f"{a.pair}={a.signal_strength:.0f}" for a in analyses),
            )

            # 4. Log analysis per pair — ALL pairs use SCALP only (no strategy switching)
            all_analysis_dicts: list[dict[str, Any]] = []

            for analysis in analyses:
                pair = analysis.pair

                # Log to strategy_log DB table (dashboard reads this) — always "scalp"
                try:
                    exchange = "delta"
                    if analysis.rsi >= 50:
                        entry_distance_pct = analysis.rsi - 55.0
                    else:
                        entry_distance_pct = 45.0 - analysis.rsi

                    # Grab live signal state from the scalp strategy (1m data)
                    scalp = self._get_scalp(pair)
                    sig = scalp.last_signal_state if scalp else None
                    sig_count = sig.get("strength", 0) if sig else 0
                    sig_side = sig.get("side") if sig else None  # "long", "short", or None
                    bull_count = sig.get("bull_count", 0) if sig else 0
                    bear_count = sig.get("bear_count", 0) if sig else 0

                    # Per-direction core-4 booleans (dashboard shows both bull + bear dots)
                    bull_mom = sig.get("bull_mom", False) if sig else False
                    bull_vol = sig.get("bull_vol", False) if sig else False
                    bull_rsi = sig.get("bull_rsi", False) if sig else False
                    bull_bb = sig.get("bull_bb", False) if sig else False
                    bear_mom = sig.get("bear_mom", False) if sig else False
                    bear_vol = sig.get("bear_vol", False) if sig else False
                    bear_rsi = sig.get("bear_rsi", False) if sig else False
                    bear_bb = sig.get("bear_bb", False) if sig else False

                    # Legacy: active-side signals for backward compat
                    if sig_side == "long":
                        sig_mom, sig_vol, sig_rsi, sig_bb = bull_mom, bull_vol, bull_rsi, bull_bb
                    elif sig_side == "short":
                        sig_mom, sig_vol, sig_rsi, sig_bb = bear_mom, bear_vol, bear_rsi, bear_bb
                    else:
                        if bull_count >= bear_count:
                            sig_mom, sig_vol, sig_rsi, sig_bb = bull_mom, bull_vol, bull_rsi, bull_bb
                        else:
                            sig_mom, sig_vol, sig_rsi, sig_bb = bear_mom, bear_vol, bear_rsi, bear_bb

                    await self.db.log_strategy_selection({
                        "timestamp": iso_now(),
                        "pair": pair,
                        "exchange": exchange,
                        "market_condition": analysis.condition.value,
                        "adx": analysis.adx,
                        "atr": analysis.atr,
                        "bb_width": analysis.bb_width,
                        "bb_upper": analysis.bb_upper,
                        "bb_lower": analysis.bb_lower,
                        "rsi": analysis.rsi,
                        "volume_ratio": analysis.volume_ratio,
                        "signal_strength": analysis.signal_strength,
                        "macd_value": analysis.macd_value,
                        "macd_signal": analysis.macd_signal,
                        "macd_histogram": analysis.macd_histogram,
                        "current_price": analysis.current_price,
                        "price_change_15m": analysis.price_change_pct,
                        "price_change_1h": analysis.price_change_1h,
                        "price_change_24h": analysis.price_change_24h,
                        "entry_distance_pct": entry_distance_pct,
                        "plus_di": analysis.plus_di,
                        "minus_di": analysis.minus_di,
                        "direction": analysis.direction,
                        "strategy_selected": "scalp",
                        "reason": f"[{pair}] Scalp-only mode — all pairs use scalp strategy",
                        # Signal state from 1m scalp strategy (dashboard reads these)
                        "signal_count": sig_count,
                        "signal_side": sig_side,
                        "signal_mom": sig_mom,
                        "signal_vol": sig_vol,
                        "signal_rsi": sig_rsi,
                        "signal_bb": sig_bb,
                        "bull_count": bull_count,
                        "bear_count": bear_count,
                        # Per-direction indicator booleans (dashboard dual dots)
                        "bull_mom": bull_mom,
                        "bull_vol": bull_vol,
                        "bull_rsi": bull_rsi,
                        "bull_bb": bull_bb,
                        "bear_mom": bear_mom,
                        "bear_vol": bear_vol,
                        "bear_rsi": bear_rsi,
                        "bear_bb": bear_bb,
                        "skip_reason": sig.get("skip_reason", "") if sig else "",
                    })
                except Exception:
                    logger.debug("Failed to log strategy selection for %s", pair)

                # Collect analysis data for market update (ALL pairs)
                all_analysis_dicts.append({
                    "pair": pair,
                    "condition": analysis.condition.value,
                    "adx": analysis.adx,
                    "rsi": analysis.rsi,
                    "direction": analysis.direction,
                    "exchange": exchange,
                })

            rm = self.risk_manager

            # 4b. Cache latest analysis data for the hourly market update
            self._latest_analyses = all_analysis_dicts

            # Mark first cycle complete (suppress strategy change spam on startup)
            self._has_run_first_cycle = True

            # 5. Check liquidation risk for futures positions
            await self._check_liquidation_risks()

            # 6. Daily loss monitoring — log only, no pausing
            # (Z philosophy: trade every opportunity, never auto-pause)

        except Exception:
            logger.exception("Error in analysis cycle")

    async def _check_arb_opportunity(self, pair: str) -> bool:
        """DISABLED — arbitrage removed (Delta options only mode)."""
        return False

    async def _check_liquidation_risks(self) -> None:
        """Monitor futures positions for liquidation proximity.

        Leverage-aware thresholds: at 50x liq is ~2% away, at 20x it's ~5%.
        Warning tiers are scaled as fractions of the total liq distance:
          >60% of liq distance: no warning (normal operation)
          40-60%: INFO log only, no Telegram
          20-40%: Telegram WARNING (once per pair, yellow)
          <20%: Telegram CRITICAL (every 5 min, red)

        Skip warning entirely if:
          - The scalp strategy doesn't think we're in a position (ghost entry)
          - SL distance > current distance (SL should fire first)
        """
        if not self.delta:
            return

        # Initialize warning state if needed
        if not hasattr(self, "_liq_warned"):
            self._liq_warned: dict[str, float] = {}  # pair -> last telegram time

        sl_distance_pct = config.trading.per_trade_stop_loss_pct  # actual configured SL

        for pair in self.delta_pairs:
            try:
                # ── Ghost position guard ──
                # Only check liquidation if the scalp strategy ALSO thinks we're in
                # a position. Prevents spam from stale entries in risk_manager.
                scalp = self._get_scalp(pair, exchange="delta")
                if scalp and not scalp.in_position:
                    self._liq_warned.pop(pair, None)
                    continue

                ticker = await self.delta.fetch_ticker(pair)
                current_price = ticker["last"]
                distance = self.risk_manager.check_liquidation_risk(pair, current_price)
                if distance is None:
                    # No futures position — clear warning state
                    self._liq_warned.pop(pair, None)
                    continue

                # Find position info
                pos = None
                for p in self.risk_manager.open_positions:
                    if p.pair == pair and p.leverage > 1:
                        pos = p
                        break
                if pos is None:
                    continue

                # Calculate liq price + leverage-aware thresholds
                leverage = pos.leverage or 20
                if pos.position_type == "long":
                    liq_price = pos.entry_price * (1 - 1 / leverage)
                else:
                    liq_price = pos.entry_price * (1 + 1 / leverage)

                liq_total_pct = 100.0 / leverage   # total distance: 2% at 50x, 5% at 20x
                safe_threshold = liq_total_pct * 0.60     # >60%: safe
                info_threshold = liq_total_pct * 0.40     # 40-60%: INFO
                warn_threshold = liq_total_pct * 0.20     # 20-40%: WARNING
                # <20%: CRITICAL

                # >60% of liq distance: normal operation, no warning
                if distance > safe_threshold:
                    self._liq_warned.pop(pair, None)
                    continue

                # Skip if SL would trigger before liquidation
                if distance > sl_distance_pct:
                    continue

                now = time.monotonic()

                # 40-60% of liq distance: INFO log only
                if distance >= info_threshold:
                    logger.info(
                        "[%s] Liquidation distance: %.2f%% (%s %dx, liq_total=%.1f%%) — SL should trigger first",
                        pair, distance, pos.position_type, leverage, liq_total_pct,
                    )
                    continue

                # 20-40% of liq distance: Telegram WARNING (once per pair)
                if distance >= warn_threshold:
                    if pair not in self._liq_warned:
                        self._liq_warned[pair] = now
                        await self.alerts.send_liquidation_warning(
                            pair, distance, pos.position_type, leverage,
                            current_price=current_price, liq_price=liq_price,
                        )
                        logger.warning(
                            "[%s] LIQUIDATION WARNING: %.2f%% from liquidation (%s %dx)",
                            pair, distance, pos.position_type, leverage,
                        )
                    continue

                # <20% of liq distance: CRITICAL — alert every 5 minutes
                last_alert = self._liq_warned.get(pair, 0)
                if now - last_alert >= 300:
                    self._liq_warned[pair] = now
                    await self.alerts.send_liquidation_warning(
                        pair, distance, pos.position_type, leverage,
                        current_price=current_price, liq_price=liq_price,
                    )
                    logger.critical(
                        "[%s] CRITICAL LIQUIDATION: %.2f%% from liquidation (%s %dx) — price=$%.2f liq=$%.2f",
                        pair, distance, pos.position_type, leverage,
                        current_price, liq_price,
                    )

            except Exception:
                logger.debug("Could not check liquidation risk for %s", pair)

    # -- Scheduled jobs --------------------------------------------------------

    async def _daily_reset(self) -> None:
        """Midnight reset: send daily summary, reset daily P&L.

        Trade stats are queried from the DATABASE, not in-memory counters.
        This survives bot restarts and is the single source of truth.
        """
        logger.info("Daily reset triggered")
        rm = self.risk_manager

        # Query the PREVIOUS day's trade stats — this runs at midnight IST,
        # so "today" has 0 trades; we want the day that just ended.
        if self.db is not None:
            today_stats = await self.db.get_today_trade_stats(previous_day=True)
            total = today_stats["total_trades"]
            wins = today_stats["wins"]
            losses = today_stats["losses"]
            daily_pnl = today_stats["daily_pnl"]
            win_rate = today_stats["win_rate"]
            pnl_map = today_stats["pnl_by_pair"]
            best_trade = today_stats["best_trade"]
            worst_trade = today_stats["worst_trade"]
        else:
            # Fallback to in-memory (should never happen)
            total = len(rm.trade_results)
            wins = sum(1 for w in rm.trade_results if w)
            losses = total - wins
            daily_pnl = rm.daily_pnl
            win_rate = rm.win_rate
            pnl_map = dict(rm.daily_pnl_by_pair)
            best_trade = None
            worst_trade = None
            if pnl_map:
                best_pair = max(pnl_map, key=pnl_map.get)  # type: ignore[arg-type]
                worst_pair = min(pnl_map, key=pnl_map.get)  # type: ignore[arg-type]
                best_trade = {"pair": best_pair, "pnl": pnl_map[best_pair]}
                worst_trade = {"pair": worst_pair, "pnl": pnl_map[worst_pair]}

        # Fetch Delta balance
        delta_bal = await self._fetch_portfolio_usd(self.delta) if self.delta else None
        total_capital = delta_bal or 0

        total_fees = today_stats.get("total_fees", 0.0) if self.db else 0.0

        await self.alerts.send_daily_summary(
            total_trades=total,
            wins=wins,
            losses=losses,
            win_rate=win_rate,
            daily_pnl=daily_pnl,
            capital=total_capital,
            pnl_by_pair=pnl_map,
            best_trade=best_trade,
            worst_trade=worst_trade,
            delta_balance=delta_bal,
            total_fees=total_fees,
        )
        rm.reset_daily()
        # Also reset hourly counters at midnight
        self._hourly_pnl = 0.0
        self._hourly_wins = 0
        self._hourly_losses = 0
        # Reset scalp daily stats
        for scalp in self._scalp_strategies.values():
            scalp.reset_daily_stats()

    async def _hourly_report(self) -> None:
        """Send hourly market update + summary to Telegram, then reset hourly counters.

        Positions are cross-checked against actual exchange balances, not just
        internal state. The balance shown is the REAL portfolio value including
        held assets (USDT + value of BTC/ETH/SOL etc.).
        """
        try:
            rm = self.risk_manager

            # Build active strategies map (scalp + options overlays)
            active_map: dict[str, str | None] = {}
            for pair in self.all_pairs:
                scalp = self._get_scalp(pair)
                opts = self._options_strategies.get(pair)
                if scalp and scalp.in_position:
                    side = scalp.position_side or "long"
                    active_map[pair] = f"scalp_{side}"
                elif opts and getattr(opts, "in_position", False):
                    active_map[pair] = "options_scalp"
                elif scalp:
                    active_map[pair] = "scalp"
                else:
                    active_map[pair] = None

            # Fetch live exchange balance — Delta only
            delta_bal = await self._fetch_portfolio_usd(self.delta) if self.delta else None

            # Capital = Delta balance
            total_capital = delta_bal or 0

            # Cross-check positions against exchange: verify we actually hold coins
            verified_positions = await self._verify_positions_against_exchange()

            # Compute unrealized P&L for open positions from scalp strategies
            unrealized_pnl = 0.0
            for _key, scalp in self._scalp_strategies.items():
                if scalp.in_position and scalp.entry_price > 0:
                    # Get latest price from analysis cache
                    analysis = self._latest_analyses.get(scalp.pair) if self._latest_analyses else None
                    if analysis and analysis.current_price and analysis.current_price > 0:
                        if scalp.position_side == "short":
                            pnl_pct = (scalp.entry_price - analysis.current_price) / scalp.entry_price * 100
                        else:
                            pnl_pct = (analysis.current_price - scalp.entry_price) / scalp.entry_price * 100
                        # Estimate position value from risk manager
                        for pos in rm.open_positions:
                            if pos.pair == scalp.pair:
                                notional = pos.entry_price * pos.amount
                                unrealized_pnl += notional * (pnl_pct / 100)
                                break

            # Build exchange balances dict — Delta only
            exchange_balances: dict[str, float] = {}
            if delta_bal is not None:
                exchange_balances["delta"] = delta_bal

            # Build options status per base asset
            options_status: dict[str, str] = {}
            for pair, opts in self._options_strategies.items():
                base = pair.split("/")[0] if "/" in pair else pair[:3]
                if opts.in_position and opts.option_side:
                    side_icon = "\U0001f7e2" if opts.option_side == "call" else "\U0001f534"
                    strike_tag = f"${opts.strike_price:,.0f}" if opts.strike_price else ""
                    ct_tag = f"x{opts._contracts}" if opts._contracts > 1 else ""
                    options_status[base] = (
                        f"{side_icon} {opts.option_side.upper()} {strike_tag} "
                        f"{ct_tag} \u2192 Holding"
                    )
                else:
                    options_status[base] = "\u23f8 Scanning"

            # Send hourly market update (all pairs grouped by exchange)
            if self._latest_analyses:
                await self.alerts.send_market_update(
                    analyses=self._latest_analyses,
                    active_strategies=active_map,
                    capital=total_capital,
                    open_position_count=len(verified_positions),
                    exchange_balances=exchange_balances,
                    options_status=options_status if self._options_strategies else None,
                )

            await self.alerts.send_hourly_summary(
                open_positions=verified_positions,
                hourly_wins=self._hourly_wins,
                hourly_losses=self._hourly_losses,
                hourly_pnl=self._hourly_pnl,
                daily_pnl=rm.daily_pnl,
                capital=total_capital,
                active_strategies=active_map,
                win_rate_24h=rm.win_rate,
                exchange_balances=exchange_balances,
                unrealized_pnl=unrealized_pnl,
            )

            # Reset hourly counters
            self._hourly_pnl = 0.0
            self._hourly_wins = 0
            self._hourly_losses = 0
        except Exception:
            logger.exception("Error sending hourly report")

    async def _verify_positions_against_exchange(self) -> list[dict[str, Any]]:
        """Cross-check risk manager positions against actual exchange balances.

        Returns a list of verified positions (those confirmed to still exist
        on the exchange). Delta only — trust internal state for futures/options.
        """
        rm = self.risk_manager
        verified: list[dict[str, Any]] = []

        for pos in rm.open_positions:
            # Delta: trust internal state (futures/options positions don't show as spot balances)
                verified.append({
                    "pair": pos.pair,
                    "position_type": pos.position_type,
                    "exchange": pos.exchange,
                })

        return verified

    def record_session_trade(self, trade_info: dict[str, Any]) -> None:
        """Called on each options trade close to track session stats."""
        self._session_trades.append(trade_info)

    async def _session_summary(self, session_name: str, session_window: str) -> None:
        """Send session summary and reset session trades."""
        try:
            trades = self._session_trades
            if not trades:
                logger.info("[SESSION] %s ended — no trades", session_name)
                self._session_trades = []
                return

            total = len(trades)
            wins = sum(1 for t in trades if t.get("net_pnl", 0) > 0)
            losses = total - wins
            session_pnl = sum(t.get("net_pnl", 0) for t in trades)
            total_fees = sum(t.get("fees", 0) for t in trades)

            best_trade = max(trades, key=lambda t: t.get("net_pnl", 0)) if trades else None
            worst_trade = min(trades, key=lambda t: t.get("net_pnl", 0)) if trades else None

            await self.alerts.send_session_summary(
                session_name=session_name,
                session_window=session_window,
                total_trades=total,
                wins=wins,
                losses=losses,
                session_pnl=session_pnl,
                total_fees=total_fees,
                best_trade=best_trade,
                worst_trade=worst_trade,
            )

            logger.info(
                "[SESSION] %s: %d trades, W/L=%d/%d, P&L=$%.4f",
                session_name, total, wins, losses, session_pnl,
            )

            # Reset for next session
            self._session_trades = []

        except Exception:
            logger.exception("[SESSION] Failed to send session summary for %s", session_name)

    async def _save_status(self) -> None:
        """Persist bot state to Supabase for crash recovery + dashboard display."""
        try:
            await self._save_status_inner()
        except Exception:
            logger.exception("[STATUS] _save_status failed — dashboard may show stale data")

    async def _save_status_inner(self) -> None:
        rm = self.risk_manager

        # Build per-pair info (scalp + options overlays)
        active_map: dict[str, str | None] = {}
        active_count = 0
        for pair in self.all_pairs:
            scalp = self._get_scalp(pair)
            opts = self._options_strategies.get(pair)
            if scalp and scalp.in_position:
                side = scalp.position_side or "long"
                active_map[pair] = f"scalp_{side}"
                active_count += 1
            elif opts and getattr(opts, "in_position", False):
                active_map[pair] = "options_scalp"
                active_count += 1
            elif scalp:
                active_map[pair] = "scalp"
                active_count += 1
            else:
                active_map[pair] = None

        # Use Delta analyzer for condition
        last = self.delta_analyzer.last_analysis if self.delta_analyzer else None

        # Fetch Delta balance
        delta_bal: float | None = None
        try:
            delta_bal = await self._fetch_portfolio_usd(self.delta) if self.delta else None
        except Exception:
            logger.exception("[STATUS] Balance fetch failed — saving status with partial data")
        rm.update_exchange_balances(delta=delta_bal)

        # Fetch raw INR balance for dashboard display
        delta_balance_inr = None
        if self.delta:
            try:
                bal = await self.delta.fetch_balance()
                inr_val = bal.get("total", {}).get("INR") or bal.get("free", {}).get("INR")
                if inr_val is not None and float(inr_val) > 0:
                    delta_balance_inr = round(float(inr_val), 2)
            except Exception:
                pass

        # Determine bot state. In the V3 era rm.is_paused only describes the
        # LEGACY live gate — the real states the dashboard needs are:
        #   live_mirror  → paper lab running AND LiveMirror trading real money
        #   paper        → paper lab running, live off
        #   running/paused/error → legacy semantics
        if getattr(self, "live_mirror", None) and self.live_mirror.is_active:
            bot_state = "live_mirror"
        elif not self._running:
            bot_state = "error"
        elif self.paper_only or getattr(self, "_live_mode", "off") != "legacy":
            bot_state = "paper"
        elif rm.is_paused:
            bot_state = "paused"
        else:
            bot_state = "running"

        # Query ACTUAL P&L from trades table (source of truth)
        # Never trust in-memory calculations for dashboard display
        try:
            trade_stats = await self.db.get_trade_stats()
        except Exception:
            logger.warning("[STATUS] get_trade_stats failed — using defaults")
            trade_stats = {"total_pnl": 0, "win_rate": 0, "total_trades": 0}

        logger.info("DB_WRITE options_scalp_enabled=%s (type=%s)", self._options_enabled, type(self._options_enabled).__name__)
        status = {
            "total_pnl": trade_stats["total_pnl"],
            "daily_pnl": rm.daily_pnl,
            "daily_loss_pct": rm.daily_loss_pct,
            "win_rate": trade_stats["win_rate"],
            "total_trades": trade_stats["total_trades"],
            "open_positions": len(rm.open_positions),
            "active_strategy": active_map.get(self.delta_pairs[0]) if self.delta_pairs else None,
            "market_condition": last.condition.value if last else None,
            "capital": rm.capital,
            "pair": ", ".join(self.all_pairs),
            "is_running": self._running,
            "is_paused": rm.is_paused,
            "pause_reason": rm._pause_reason or None,
            # Exchange data — Delta only
            "delta_balance": delta_bal,
            "delta_balance_inr": delta_balance_inr,
            "delta_connected": self.delta is not None and delta_bal is not None,
            "bot_state": bot_state,
            "shorting_enabled": config.delta.enable_shorting,
            "leverage": config.delta.leverage,
            "active_strategy_count": active_count,
            "uptime_seconds": int(time.monotonic() - self._start_time) if self._start_time else 0,
            # Strategy toggles
            "options_scalp_enabled": True,
            "delta_enabled": self._delta_enabled,
            # INR exchange rate for dashboard display
            "inr_usd_rate": await self._get_inr_usd_rate(),
            # Daily P&L breakdown
            "daily_pnl_scalp": rm.daily_pnl_scalp,
            "daily_pnl_options": rm.daily_pnl_options,
        }

        # ── Aggregate market regime from all scalp strategies ──────────
        # Priority: CHOPPY > TRENDING_DOWN > TRENDING_UP > SIDEWAYS
        regime_priority = {"CHOPPY": 4, "TRENDING_DOWN": 3, "TRENDING_UP": 2, "SIDEWAYS": 1}
        worst_regime = "SIDEWAYS"
        worst_score = 0
        for s in self._scalp_strategies.values():
            r = getattr(s, "_market_regime", "SIDEWAYS")
            p = regime_priority.get(r, 1)
            if p > worst_score:
                worst_score = p
                worst_regime = r

        # Metrics: merge across pairs sharing the winning regime (max chop/ATR stress; strongest |net|)
        best_chop = 0.0
        best_atr_ratio = 1.0
        best_net_change = 0.0
        regime_since_ts = None
        oldest_since_mono: float | None = None
        for s in self._scalp_strategies.values():
            r = getattr(s, "_market_regime", "SIDEWAYS")
            if r != worst_regime:
                continue
            best_chop = max(best_chop, float(getattr(s, "_chop_score", 0.0)))
            best_atr_ratio = max(best_atr_ratio, float(getattr(s, "_atr_ratio", 1.0)))
            nc = float(getattr(s, "_net_change_30m", 0.0))
            if abs(nc) > abs(best_net_change):
                best_net_change = nc
            since_mono = float(getattr(s, "_regime_since", 0.0))
            if since_mono > 0:
                if oldest_since_mono is None or since_mono < oldest_since_mono:
                    oldest_since_mono = since_mono

        if oldest_since_mono is not None and self._start_time:
            elapsed = time.monotonic() - oldest_since_mono
            regime_since_ts = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(seconds=elapsed)).isoformat()

        status["market_regime"] = worst_regime
        status["chop_score"] = round(best_chop, 3)
        status["atr_ratio"] = round(best_atr_ratio, 2)
        status["net_change_30m"] = round(best_net_change, 3)
        if regime_since_ts:
            status["regime_since"] = regime_since_ts

        # ── Diagnostics blob — "Why No Trades?" data for dashboard ──
        try:
            now_m = time.monotonic()
            diag: dict[str, Any] = {
                "last_scan_ago_s": int(now_m - self._last_cycle_time),
                "paused": {"is_paused": rm.is_paused, "reason": rm._pause_reason or None},
                "positions": {
                    "open": len(rm.open_positions),
                    "max": rm.max_concurrent,
                    "slots_free": rm.max_concurrent - len(rm.open_positions),
                    "pairs": [p.pair for p in rm.open_positions],
                },
                "balance": {
                    "delta": round(delta_bal, 2) if delta_bal else None,
                    "delta_min_trade": bool(delta_bal and delta_bal >= 5),
                },
                "pairs": {},
            }
            for key, scalp in self._scalp_strategies.items():
                bare_pair = scalp.pair  # bare pair name without exchange prefix
                sl_cd = max(0, int((ScalpStrategy._pair_last_sl_time.get(bare_pair, 0) + 120) - now_m))
                rev_cd = max(0, int((ScalpStrategy._pair_last_reversal_time.get(bare_pair, 0) + 120) - now_m))
                streak_cd = max(0, int(ScalpStrategy._pair_streak_pause_until.get(bare_pair, 0) - now_m))
                phantom_cd = max(0, int(getattr(scalp, "_phantom_cooldown_until", 0) - now_m))
                sig = getattr(scalp, "last_signal_state", None) or {}
                diag["pairs"][key] = {
                    "skip_reason": getattr(scalp, "_skip_reason", "") or "NONE",
                    "in_position": scalp.in_position,
                    "position_side": scalp.position_side,
                    "cooldowns": {
                        "sl": sl_cd, "reversal": rev_cd,
                        "streak": streak_cd, "phantom": phantom_cd,
                    },
                    "signals": {
                        "bull_count": sig.get("bull_count", 0),
                        "bear_count": sig.get("bear_count", 0),
                        "rsi": round(sig["rsi"], 1) if sig.get("rsi") is not None else None,
                        "momentum": round(sig["momentum_60s"], 3) if sig.get("momentum_60s") is not None else None,
                        "trend_15m": sig.get("trend_15m"),
                    },
                }
            status["diagnostics"] = diag
        except Exception:
            logger.debug("Failed to build diagnostics blob")

        await self.db.save_bot_status(status)

    async def _run_reconciliation(self) -> None:
        """Hourly reconciliation against Delta Exchange fills."""
        if not self.delta_options or not self.db.is_connected:
            return
        try:
            from alpha.reconcile import DeltaReconciler
            reconciler = DeltaReconciler(self.delta_options, self.db.client, logger)
            result = await reconciler.run(since_hours=2)
            logger.info(
                "RECONCILE: matched=%d updated=%d inserted=%d diff=$%.4f",
                result["matched"], result["updated"], result["inserted"], result["diff"],
            )
            if result["updated"] > 0 or result["inserted"] > 0:
                try:
                    await self.alerts.send_text(
                        f"\U0001f504 Reconciled: {result['updated']} updated, "
                        f"{result['inserted']} ghosts inserted, diff=${result['diff']:.4f}"
                    )
                except Exception:
                    pass
        except Exception:
            logger.exception("Reconcile failed")

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
                if getattr(self, "live_mirror", None):
                    self.live_mirror.user_paused = True   # no NEW live entries; open position still managed
                # Stop all active strategies (scalp + options overlays + paper futures)
                stop_tasks = []
                for pair, scalp in self._scalp_strategies.items():
                    if scalp.is_active:
                        stop_tasks.append(scalp.stop())
                for pair, opts in self._options_strategies.items():
                    if opts.is_active:
                        stop_tasks.append(opts.stop())
                for pair, paper_strategies in self._paper_futures_strategies.items():
                    for paper in paper_strategies:
                        if paper.is_active:
                            stop_tasks.append(paper.stop())
                for pair, opt_lanes in self._paper_options_strategies.items():
                    for lane in opt_lanes:
                        if lane.is_active:
                            stop_tasks.append(lane.stop())
                if stop_tasks:
                    await asyncio.gather(*stop_tasks, return_exceptions=True)
                await self.alerts.send_command_confirmation("pause")
                result_msg = "Bot paused"

            elif command == "resume":
                force = bool(params.get("force", False))
                # Restart paper lab lanes regardless of mode.
                for pair, paper_strategies in self._paper_futures_strategies.items():
                    for paper in paper_strategies:
                        if not paper.is_active and self._delta_enabled:
                            await paper.start()
                for pair, opt_lanes in self._paper_options_strategies.items():
                    for lane in opt_lanes:
                        if not lane.is_active and self._delta_enabled:
                            await lane.start()
                if self.paper_only:
                    # PAPER-ONLY: never bring live trading back. Keep is_paused on.
                    self.risk_manager.is_paused = True
                    self.risk_manager._pause_reason = "PAPER-ONLY mode (no live trading)"
                    await self.alerts.send_command_confirmation("resume")
                    result_msg = "Paper lab resumed (PAPER-ONLY: live stays off)"
                elif getattr(self, "_live_mode", "off") != "legacy":
                    # MIRROR mode: resume = let the LiveMirror take entries again.
                    # Legacy scalp/options stay blocked; risk manager stays paused.
                    self.risk_manager.is_paused = True
                    self.risk_manager._pause_reason = f"LIVE_MODE={self._live_mode or 'off'} (legacy live paths blocked)"
                    if getattr(self, "live_mirror", None):
                        self.live_mirror.user_paused = False
                    await self.alerts.send_command_confirmation("resume")
                    result_msg = "Paper lab + LiveMirror resumed (legacy live stays off)"
                else:
                    self.risk_manager.unpause(force=force)
                    await self._analysis_cycle()  # re-evaluate and start strategies
                    # Restart scalp + options overlays (live)
                    for pair, scalp in self._scalp_strategies.items():
                        if not scalp.is_active:
                            await scalp.start()
                    for pair, opts in self._options_strategies.items():
                        if not opts.is_active:
                            await opts.start()
                    label = "force_resume" if force else "resume"
                    await self.alerts.send_command_confirmation(label)
                    result_msg = "Bot force-resumed (win-rate bypass active)" if force else "Bot resumed"

            elif command == "notify":
                # Generic Telegram passthrough — the hourly paper-lab co-work routine
                # uses this to push its check-in summary to the user's chat.
                text = (params.get("text") or "").strip()
                if text:
                    try:
                        await self.alerts._send(text, allow_in_quiet=True)
                    except Exception:
                        # HTML parse failure (e.g. a literal "<=") — resend escaped
                        from html import escape

                        await self.alerts._send(escape(text), allow_in_quiet=True)
                    result_msg = f"Notify sent ({len(text)} chars)"
                else:
                    result_msg = "Notify skipped — empty text"

            elif command == "paper_pulse":
                # Deterministic, always-clean paper-lab Telegram pulse. The engine
                # formats it from the DB; the routine only supplies short
                # 'learned' / 'next' lines via params. Guarantees consistent shape.
                try:
                    text = await self._build_paper_pulse(params)
                    await self.alerts._send(text, allow_in_quiet=True)
                    result_msg = "Paper pulse sent"
                except Exception as exc:
                    result_msg = f"Paper pulse failed: {exc}"

            elif command == "force_strategy":
                # Only scalp and options_scalp are active — force_strategy is a no-op
                result_msg = "Only scalp and options_scalp strategies are active"
                await self.alerts.send_command_confirmation("force_strategy", result_msg)

            elif command == "toggle_strategy":
                strategy = params.get("strategy", "")
                enabled = params.get("enabled", True)
                if strategy == "scalp":
                    self._scalp_enabled = enabled
                    tasks = []
                    if enabled:
                        for pair, scalp in self._scalp_strategies.items():
                            if not scalp.is_active:
                                tasks.append(scalp.start())
                    else:
                        for pair, scalp in self._scalp_strategies.items():
                            if scalp.is_active:
                                tasks.append(scalp.stop())
                    if tasks:
                        await asyncio.gather(*tasks, return_exceptions=True)
                    result_msg = f"Scalp {'enabled' if enabled else 'disabled'}"
                elif strategy == "options_scalp":
                    logger.info("OPTIONS_DEBUG: dashboard toggle setting _options_enabled=%s (was %s)", enabled, self._options_enabled)
                    self._options_enabled = enabled
                    tasks = []
                    if enabled:
                        for pair, opts in self._options_strategies.items():
                            if not opts.is_active:
                                tasks.append(opts.start())
                    else:
                        for pair, opts in self._options_strategies.items():
                            if opts.is_active:
                                tasks.append(opts.stop())
                    if tasks:
                        await asyncio.gather(*tasks, return_exceptions=True)
                    result_msg = f"Options scalp {'enabled' if enabled else 'disabled'}"
                else:
                    result_msg = f"Unknown strategy: {strategy}"
                await self.alerts.send_command_confirmation("toggle_strategy", result_msg)

            elif command == "toggle_exchange":
                exchange = params.get("exchange", "")
                enabled = params.get("enabled", True)
                tasks = []
                if exchange == "delta":
                    self._delta_enabled = enabled
                else:
                    result_msg = f"Unknown exchange: {exchange}"
                    await self.db.mark_command_executed(cmd_id, result_msg)
                    return

                for pair, scalp in self._scalp_strategies.items():
                    ex_id = getattr(scalp, "_exchange_id", "delta")
                    if ex_id == exchange:
                        if enabled and not scalp.is_active:
                            tasks.append(scalp.start())
                        elif not enabled and scalp.is_active:
                            tasks.append(scalp.stop())
                # Also handle options strategies for delta
                if exchange == "delta":
                    for pair, opts in self._options_strategies.items():
                        if enabled and not opts.is_active and self._options_enabled:
                            tasks.append(opts.start())
                        elif not enabled and opts.is_active:
                            tasks.append(opts.stop())
                    for pair, paper_strategies in self._paper_futures_strategies.items():
                        for paper in paper_strategies:
                            if enabled and not paper.is_active:
                                tasks.append(paper.start())
                            elif not enabled and paper.is_active:
                                tasks.append(paper.stop())
                    for pair, opt_lanes in self._paper_options_strategies.items():
                        for lane in opt_lanes:
                            if enabled and not lane.is_active:
                                tasks.append(lane.start())
                            elif not enabled and lane.is_active:
                                tasks.append(lane.stop())
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                result_msg = f"{exchange.title()} {'enabled' if enabled else 'disabled'} ({len(tasks)} strategies)"
                await self.alerts.send_command_confirmation("toggle_exchange", result_msg)

            elif command == "update_config":
                if "max_position_pct" in params:
                    self.risk_manager.max_position_pct = float(params["max_position_pct"])
                    result_msg = f"max_position_pct -> {params['max_position_pct']}"
                elif "setup_type" in params:
                    # Setup toggle from dashboard Strategies page
                    st = params["setup_type"]
                    en = params.get("enabled", True)
                    for _pair, scalp in self._scalp_strategies.items():
                        scalp._setup_config[st] = en
                    result_msg = f"setup {st} -> {'enabled' if en else 'disabled'}"
                else:
                    result_msg = f"Config updated: {params}"
                await self.alerts.send_command_confirmation("update_config", result_msg)

            elif command == "update_pair_config":
                result_msg = self._apply_pair_config(params)
                await self.alerts.send_command_confirmation(
                    "update_pair_config", result_msg,
                )

            elif command == "close_trade":
                result_msg = await self._handle_close_trade(params)
                await self.alerts.send_command_confirmation("close_trade", result_msg)

            elif command == "reconcile":
                from alpha.reconcile import DeltaReconciler
                reconciler = DeltaReconciler(self.delta_options, self.db.client, logger)
                result = await reconciler.run(since_hours=int(params.get("hours", 24)))
                result_msg = (
                    f"Reconciled: {result['updated']} updated, "
                    f"{result['inserted']} inserted, diff=${result['diff']:.4f}"
                )

            elif command == "smart_reconcile":
                from alpha.smart_reconcile import SmartDeltaReconciler
                from datetime import datetime, timezone, timedelta
                reconciler = SmartDeltaReconciler(self.delta_options, self.db.client, logger)
                dry_run = bool(params.get("dry_run", True))
                date_from_str = params.get("date_from")
                date_to_str = params.get("date_to")
                if date_from_str and date_to_str:
                    date_from = datetime.fromisoformat(date_from_str.replace("Z", "+00:00"))
                    date_to = datetime.fromisoformat(date_to_str.replace("Z", "+00:00"))
                else:
                    # Default to last 24h
                    now = datetime.now(timezone.utc)
                    date_from = now - timedelta(hours=24)
                    date_to = now
                result = await reconciler.run(date_from=date_from, date_to=date_to, dry_run=dry_run)
                result_msg = (
                    f"Smart reconcile (dry_run={dry_run}): processed={result['processed']} "
                    f"updated={result['updated']} skipped={result['skipped']} "
                    f"dupes={result.get('duplicates_marked', 0)} ghosts={result.get('ghosts_inserted', 0)} "
                    f"errors={result['errors']}"
                )

            else:
                result_msg = f"Unknown command: {command}"

        except Exception as e:
            result_msg = f"Error: {e}"
            logger.exception("Failed to handle command %d", cmd_id)

        await self.db.mark_command_executed(cmd_id, result_msg)

    def _apply_pair_config(self, params: dict) -> str:
        """Hot-update scalp strategy config for a specific pair (Brain command).

        Supported params: pair, sl, tp, trail_activate, bias, enabled,
        timeout_minutes, phase1.
        """
        pair_str = params.get("pair", "")
        if not pair_str:
            return "Error: missing 'pair' param"

        # Find the matching scalp strategy instance
        scalp: ScalpStrategy | None = None
        for _key, s in self._scalp_strategies.items():
            if s.pair == pair_str or pair_str.startswith(s.pair.split("/")[0]):
                scalp = s
                pair_str = s.pair  # normalise to full bare pair
                break

        if scalp is None:
            return f"Error: no scalp strategy for {pair_str}"

        short = pair_str.split("/")[0]
        changes: list[str] = []

        if "sl" in params:
            val = float(params["sl"])
            scalp.PAIR_SL_FLOOR[short] = val
            changes.append(f"SL={val}%")

        if "tp" in params:
            val = float(params["tp"])
            scalp.PAIR_TP_FLOOR[short] = val
            changes.append(f"TP={val}%")

        if "trail_activate" in params:
            val = float(params["trail_activate"])
            scalp.TRAILING_ACTIVATE_PCT = val
            changes.append(f"trail={val}%")

        if "phase1" in params:
            val = int(params["phase1"])
            scalp.PHASE1_SECONDS = val
            changes.append(f"phase1={val}s")

        if "timeout_minutes" in params:
            val = int(params["timeout_minutes"])
            scalp.MAX_HOLD_SECONDS = val * 60
            changes.append(f"timeout={val}m")

        if "enabled" in params:
            enabled = params["enabled"]
            if enabled is False or str(enabled).lower() in ("false", "0"):
                scalp._pair_enabled = False
                if scalp.is_active:
                    # Schedule stop on next tick — can't await in sync method
                    asyncio.ensure_future(scalp.stop())
                changes.append("DISABLED")
            else:
                scalp._pair_enabled = True
                if not scalp.is_active:
                    asyncio.ensure_future(scalp.start())
                changes.append("ENABLED")

        if "allocation_pct" in params:
            val = float(params["allocation_pct"])
            scalp._allocation_pct = max(0.0, min(70.0, val))
            changes.append(f"alloc={val}%")

        if "bias" in params:
            bias = str(params["bias"]).lower()
            # Store bias on the strategy instance for signal filtering
            scalp._brain_bias = bias  # type: ignore[attr-defined]
            changes.append(f"bias={bias}")

        summary = ", ".join(changes) if changes else "no changes"
        result_msg = f"SENTINEL UPDATE: {pair_str} — {summary}"
        logger.info(result_msg)
        return result_msg

    async def _load_pair_setup_configs(self) -> None:
        """Load pair_config + setup_config from DB and apply to all scalp strategies."""
        try:
            pair_configs = await self.db.get_pair_configs()
            setup_configs = await self.db.get_setup_configs()
        except Exception:
            logger.debug("Could not load pair/setup configs from DB (tables may not exist yet)")
            return

        # Apply pair configs to matching scalp strategies
        for _key, scalp in self._scalp_strategies.items():
            bare = scalp.pair
            base = bare.split("/")[0] if "/" in bare else bare.replace("USD", "").replace(":USD", "")
            pc = pair_configs.get(base, {})
            if pc:
                scalp._pair_enabled = pc.get("enabled", True)
                scalp._allocation_pct = float(pc.get("allocation_pct", scalp._allocation_pct))

            # Apply setup configs to all strategies (shared across all pairs)
            scalp._setup_config = setup_configs

        if pair_configs or setup_configs:
            logger.info(
                "Loaded configs: %d pair(s), %d setup(s)",
                len(pair_configs), len(setup_configs),
            )

    async def _handle_close_trade(self, params: dict) -> str:
        """Force-close an open trade via dashboard command.

        Supports both scalp (futures) and options_scalp positions.
        If position is no longer on exchange (ghost), closes DB record directly.
        """
        pair_str = params.get("pair", "")
        trade_id = params.get("trade_id")
        if not pair_str:
            return "Error: missing 'pair' param"

        # ── Options trades: handle separately ──
        if is_option_symbol(pair_str) or (trade_id and await self._is_options_trade(trade_id)):
            return await self._close_options_trade(pair_str, trade_id)

        # Find the matching scalp strategy
        scalp: ScalpStrategy | None = None
        for _key, s in self._scalp_strategies.items():
            if s.pair == pair_str or pair_str.startswith(s.pair.split("/")[0]):
                scalp = s
                break

        if not scalp:
            # No strategy found — try to close as ghost position in DB
            if trade_id:
                return await self._close_ghost_trade(trade_id, pair_str)
            return f"Error: no strategy found for pair {pair_str}"

        if not scalp.in_position:
            # Strategy exists but not in position — close ghost DB record
            if trade_id:
                return await self._close_ghost_trade(trade_id, pair_str)
            return f"No open position for {pair_str}"

        # Build exit signal at current price
        side = scalp.position_side or "long"
        price = scalp.entry_price  # will be overridden by market order
        exit_signal = scalp._exit_signal(price, side, f"MANUAL_CLOSE (dashboard cmd, trade_id={trade_id})")

        # Execute immediately via market order
        try:
            result = await self.executor.execute(exit_signal)
            if result:
                logger.info("MANUAL CLOSE executed: %s %s", pair_str, side)
                return f"Closed {pair_str} {side} via market order"
            else:
                return f"Error: execute() returned None for {pair_str}"
        except Exception as e:
            logger.exception("Failed to manual close %s", pair_str)
            return f"Error closing {pair_str}: {e}"

    async def _is_options_trade(self, trade_id: int) -> bool:
        """Check if a trade ID belongs to an options_scalp trade."""
        try:
            trades = await self.db.get_all_open_trades()
            for t in trades:
                if t.get("id") == trade_id:
                    return t.get("strategy") == "options_scalp" or is_option_symbol(t.get("pair", ""))
        except Exception:
            pass
        return False

    async def _close_options_trade(self, pair_str: str, trade_id: int | None) -> str:
        """Close an options trade — try market exit via executor, then DB-only if ghost."""
        # Check if options strategy has an active position on exchange
        for strat in self._options_strategies.values():
            if strat.in_position and (strat.option_symbol == pair_str or strat.pair == pair_str):
                # Build a market exit signal and execute
                try:
                    from alpha.strategies.base import Signal, StrategyName
                    exit_side = "sell"  # options are always long, close by selling
                    exit_signal = Signal(
                        side=exit_side,
                        price=strat.entry_premium or 0,
                        amount=strat.CONTRACTS_PER_TRADE,
                        order_type="market",
                        reason=f"MANUAL_CLOSE (dashboard cmd, trade_id={trade_id})",
                        strategy=StrategyName.OPTIONS_SCALP,
                        pair=strat.option_symbol or pair_str,
                        leverage=strat.OPTIONS_LEVERAGE,
                        position_type="long",
                        reduce_only=True,
                        exchange_id="delta",
                    )
                    result = await self.executor.execute(exit_signal)
                    if result:
                        strat.in_position = False
                        strat.option_symbol = None
                        return f"Closed options position {pair_str} via market order"
                    else:
                        return f"Execute returned None for options {pair_str} — trying ghost close"
                except Exception as e:
                    logger.exception("Failed to close options %s via executor", pair_str)

        # No active strategy position — close as ghost trade in DB
        if trade_id:
            return await self._close_ghost_trade(trade_id, pair_str)
        return f"No active options position found for {pair_str}"

    async def _close_ghost_trade(self, trade_id: int, pair_str: str) -> str:
        """Close a ghost trade (in DB but not on exchange) with best available price."""
        try:
            open_trade = None
            trades = await self.db.get_all_open_trades()
            for t in trades:
                if t.get("id") == trade_id:
                    open_trade = t
                    break

            if not open_trade:
                return f"Trade {trade_id} not found or already closed"

            entry_price = float(open_trade.get("entry_price", 0) or 0)
            position_type = open_trade.get("position_type", "long")
            leverage = int(open_trade.get("leverage", 1) or 1)
            amount = float(open_trade.get("amount", 0) or 0)
            exchange_id = open_trade.get("exchange", "delta")

            # Try to get exit price from exchange trade history
            exit_price = entry_price  # fallback
            try:
                exchange = self.delta_options if is_option_symbol(pair_str) else self.delta
                if exchange:
                    recent = await exchange.fetch_my_trades(pair_str, limit=20)
                    close_side = "sell" if position_type in ("long", "spot") else "buy"
                    fills = [t for t in (recent or []) if t.get("side") == close_side]
                    if fills:
                        exit_price = float(fills[-1].get("price", 0) or 0) or entry_price
                    elif not fills:
                        ticker = await exchange.fetch_ticker(pair_str)
                        exit_price = float(ticker.get("last", 0) or 0) or entry_price
            except Exception as e:
                logger.warning("Ghost trade %s: could not fetch exit price: %s", pair_str, e)

            # Determine fee rate by exchange
            _fee = {"kraken": config.kraken.taker_fee,
                    "bybit": config.bybit.taker_fee,
                    "delta": config.delta.taker_fee_with_gst,
                    "binance": 0.001}.get(exchange_id, 0.0)
            result = calc_pnl(
                entry_price, exit_price, amount,
                position_type, leverage,
                exchange_id, pair_str,
                entry_fee_rate=_fee, exit_fee_rate=_fee,
            )

            await self.db.update_trade(trade_id, {
                "status": "closed",
                "exit_price": exit_price,
                "closed_at": iso_now(),
                "pnl": round(result.net_pnl, 8),
                "pnl_pct": round(result.pnl_pct, 4),
                "gross_pnl": round(result.gross_pnl, 8),
                "entry_fee": round(result.entry_fee, 8),
                "exit_fee": round(result.exit_fee, 8),
                "reason": "ghost_manual_close",
                "exit_reason": "MANUAL",
                "position_state": None,
            })

            logger.info(
                "GHOST TRADE CLOSED: %s (trade_id=%s) exit=$%.4f pnl=$%.4f (%.2f%%)",
                pair_str, trade_id, exit_price, result.net_pnl, result.pnl_pct,
            )
            return f"Ghost trade closed: {pair_str} exit=${exit_price:.4f} P&L={result.pnl_pct:+.2f}%"

        except Exception as e:
            logger.exception("Failed to close ghost trade %s", pair_str)
            return f"Error closing ghost trade {pair_str}: {e}"

    async def _close_binance_dust_trades(self) -> None:
        """Mark Binance trades below $6 as closed dust (too small to sell).

        DISABLED — Delta only mode, no Binance trades.
        """
        return
        try:
            if not self.binance:
                return
            bal = await self.binance.fetch_balance()
            free_map = bal.get("free", {})

            open_trades = await self.db.get_all_open_trades()
            binance_trades = [t for t in open_trades if t.get("exchange") == "binance"]
            dust_count = 0
            for trade in binance_trades:
                pair = trade.get("pair", "")
                base = pair.split("/")[0] if "/" in pair else pair
                held = float(free_map.get(base, 0) or 0)
                entry_price = float(trade.get("entry_price", 0) or 0)
                held_value = held * entry_price if entry_price > 0 else 0
                if held_value < 5.0 and held_value > 0:
                    trade_id = trade.get("id")
                    order_id = trade.get("order_id", "")
                    if trade_id:
                        # Calculate P&L from entry — dust is a small loss
                        try:
                            ticker = await self.binance.fetch_ticker(pair)  # type: ignore[union-attr]
                            current_price = float(ticker.get("last", 0) or 0)
                        except Exception:
                            current_price = entry_price  # fallback: 0 P&L
                        _r = calc_pnl(
                            entry_price, current_price, held,
                            trade.get("position_type", "spot"),
                            trade.get("leverage", 1) or 1,
                            "binance", pair,
                            entry_fee_rate=0.001, exit_fee_rate=0.001,
                        )
                        pnl, pnl_pct = _r.net_pnl, _r.pnl_pct
                        if order_id:
                            await self.db.close_trade(
                                order_id, current_price, pnl, pnl_pct,
                                reason="dust_unsellable",
                                exit_reason="DUST",
                                gross_pnl=_r.gross_pnl,
                                entry_fee=_r.entry_fee,
                                exit_fee=_r.exit_fee,
                            )
                        else:
                            await self.db.update_trade(trade_id, {
                                "status": "closed",
                                "closed_at": iso_now(),
                                "exit_price": current_price,
                                "pnl": pnl,
                                "pnl_pct": pnl_pct,
                                "reason": "dust_unsellable",
                                "exit_reason": "DUST",
                            })
                        dust_count += 1
                        logger.info(
                            "Dust trade %s: exit=$%.2f pnl=$%.4f (%.2f%%)",
                            pair, current_price, pnl, pnl_pct,
                        )
            if dust_count:
                logger.info("Closed %d Binance dust trades (< $5)", dust_count)
        except Exception:
            logger.exception("Failed to check Binance dust trades")

    async def _auto_changelog(self, version: str) -> None:
        """Auto-detect version changes and parameter diffs, log to changelog."""
        if not self.db.is_connected:
            return

        import subprocess
        from pathlib import Path as _Path

        now = iso_now()
        repo_root = str(_Path(__file__).resolve().parent.parent.parent)

        # 1. Get git info
        git_hash: str | None = None
        git_message: str | None = None
        try:
            git_hash = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=repo_root, text=True, timeout=5,
            ).strip()
        except Exception:
            pass
        try:
            git_message = subprocess.check_output(
                ["git", "log", "-1", "--format=%s"],
                cwd=repo_root, text=True, timeout=5,
            ).strip()
        except Exception:
            pass

        # 2. Version change → deploy entry
        last_entry = await self.db.get_latest_changelog()
        last_version = last_entry.get("version") if last_entry else None

        if last_version != version:
            title = f"Deploy v{version}"
            if git_message:
                title = f"Deploy v{version}: {git_message}"
            await self.db.log_changelog({
                "change_type": "gpfc",
                "title": title[:200],
                "description": (
                    f"Auto-detected version change from "
                    f"{last_version or 'unknown'} to {version}"
                ),
                "version": version,
                "status": "deployed",
                "deployed_at": now,
                "git_commit_hash": git_hash,
                "tags": ["auto"],
            })
            logger.info("Auto-changelog: version %s -> %s", last_version, version)

        # 3. Parameter change detection
        current_snapshot = ScalpStrategy.get_constants_snapshot()

        last_param = await self.db.get_latest_changelog(change_type="param_change")
        previous_snapshot = (
            last_param.get("parameters_after") if last_param else None
        )

        if previous_snapshot and previous_snapshot != current_snapshot:
            # Build diff description
            changed: list[str] = []
            all_keys = set(list(current_snapshot.keys()) + list(previous_snapshot.keys()))
            for key in sorted(all_keys):
                old_val = previous_snapshot.get(key)
                new_val = current_snapshot.get(key)
                if old_val != new_val:
                    changed.append(f"{key}: {old_val} -> {new_val}")

            await self.db.log_changelog({
                "change_type": "param_change",
                "title": f"Parameter change ({len(changed)} params)",
                "description": "; ".join(changed)[:500],
                "version": version,
                "parameters_before": previous_snapshot,
                "parameters_after": current_snapshot,
                "status": "deployed",
                "deployed_at": now,
                "git_commit_hash": git_hash,
                "tags": ["auto", "params"],
            })
            logger.info("Auto-changelog: %d parameter(s) changed", len(changed))
        elif not previous_snapshot:
            # Seed baseline snapshot
            await self.db.log_changelog({
                "change_type": "param_change",
                "title": f"Initial parameter snapshot v{version}",
                "description": "Baseline snapshot — no previous entry to compare",
                "version": version,
                "parameters_before": None,
                "parameters_after": current_snapshot,
                "status": "deployed",
                "deployed_at": now,
                "git_commit_hash": git_hash,
                "tags": ["auto", "params", "baseline"],
            })
            logger.info("Auto-changelog: seeded initial parameter snapshot")

    async def _restore_state(self) -> None:
        """Restore capital, state, and open positions from last saved status.

        Open positions from DB are verified against actual exchange balances.
        Stale positions (no longer on exchange) are marked closed.
        """
        last = await self.db.get_last_bot_status()
        if last:
            # Restore Delta balance if available
            delta_bal = last.get("delta_balance")
            if delta_bal is not None:
                self.risk_manager.update_exchange_balances(
                    delta=float(delta_bal) if delta_bal else None,
                )
                logger.info(
                    "Restored state from DB -- Delta=$%.2f",
                    self.risk_manager.delta_capital,
                )
            else:
                # Fallback to single capital field
                self.risk_manager.capital = last.get("capital", config.trading.starting_capital)
                logger.info("Restored state from DB -- capital: $%.2f (legacy)", self.risk_manager.capital)

            # options_scalp always starts enabled; dashboard toggle still works at runtime
            logger.info("options_scalp_enabled=True (hardcoded, dashboard toggle still works at runtime)")

            # Restore exchange toggle state
            for ex_name in ("bybit", "delta", "kraken"):
                db_val = last.get(f"{ex_name}_enabled")
                if db_val is not None:
                    setattr(self, f"_{ex_name}_enabled", bool(db_val))
            logger.info(
                "Restored exchange toggles: bybit=%s delta=%s kraken=%s",
                self._bybit_enabled, self._delta_enabled, self._kraken_enabled,
            )
        else:
            logger.info("No previous state found -- starting fresh")

        # Restore open positions from DB and verify against exchange balances
        await self._restore_open_positions()

    async def _restore_open_positions(self) -> None:
        """Load open trades from DB and verify they still exist on exchange.

        For each open trade:
        - Spot (Binance): check if we still hold the base asset (> $1 worth)
        - Futures (Bybit): check via fetch_positions() for real coin holdings
        - Futures (Delta): check via fetch_positions() for real contract holdings
        If position no longer exists, mark trade as closed in DB.
        If it does exist, register it with the risk manager.

        NOTE: Restored trades are saved in self._restored_trades for later
        injection into strategy instances (see _restore_strategy_state).
        """
        self._restored_trades: list[dict[str, Any]] = []

        open_trades = await self.db.get_all_open_trades()
        if not open_trades:
            logger.info("No open trades to restore from DB")
            return

        logger.info("Found %d open trades in DB — verifying against exchange...", len(open_trades))

        # Fetch Delta positions via fetch_positions() — actual open contracts
        delta_positions: dict[str, dict[str, Any]] = {}
        try:
            if self.delta:
                positions = await self.delta.fetch_positions()
                for pos in positions:
                    contracts = float(pos.get("contracts", 0) or 0)
                    if contracts != 0:
                        symbol = pos.get("symbol", "")
                        side = "long" if contracts > 0 else "short"
                        entry_px = float(pos.get("entryPrice", 0) or 0)
                        delta_positions[symbol] = {
                            "side": side,
                            "contracts": abs(contracts),
                            "entry_price": entry_px,
                            "info": pos,
                        }
                        logger.info(
                            "Found open Delta position: %s %s %.0f contracts @ $%.2f",
                            symbol, side, abs(contracts), entry_px,
                        )
                if not delta_positions:
                    logger.info("No open Delta positions on exchange")
        except Exception as e:
            logger.error("Failed to fetch Delta positions on startup: %s", e)

        # Fetch options positions from delta_options exchange (separate from futures)
        options_positions: dict[str, dict[str, Any]] = {}
        try:
            if self.delta_options:
                opt_positions = await self.delta_options.fetch_positions()
                for pos in opt_positions:
                    contracts = float(pos.get("contracts", 0) or 0)
                    if contracts != 0:
                        symbol = pos.get("symbol", "")
                        entry_px = float(pos.get("entryPrice", 0) or 0)
                        options_positions[symbol] = {
                            "side": "long" if contracts > 0 else "short",
                            "contracts": abs(contracts),
                            "entry_price": entry_px,
                        }
                        logger.info(
                            "Found open options position: %s %.0f contracts @ $%.4f",
                            symbol, abs(contracts), entry_px,
                        )
                if not options_positions:
                    logger.info("No open options positions on exchange")
        except Exception as e:
            logger.warning("Could not fetch options positions on startup: %s", e)

        restored = 0
        closed = 0

        for trade in open_trades:
            pair = trade.get("pair", "")
            exchange_id = trade.get("exchange", "binance")
            entry_price = float(trade.get("entry_price", 0) or 0)
            amount = float(trade.get("amount", 0) or 0)
            strategy = trade.get("strategy", "")
            position_type = trade.get("position_type", "spot")
            leverage = int(trade.get("leverage", 1) or 1)
            trade_id = trade.get("id")

            # Get the base asset (e.g., "ETH" from "ETH/USDT" or "ETHUSD")
            base = pair.split("/")[0] if "/" in pair else pair.replace("USD", "").replace("USDT", "")

            # Check if position still exists on exchange — Delta only
            position_exists = False

            if exchange_id != "delta":
                # Non-Delta trades: skip (no longer supported)
                logger.info("Skipping non-Delta trade %s on %s", pair, exchange_id)
                continue

            if exchange_id == "delta":
                # Options trades: check options_positions (separate exchange)
                if is_option_symbol(pair):
                    opt_pos = options_positions.get(pair)
                    if opt_pos:
                        position_exists = True
                        logger.info(
                            "Options position %s verified on exchange: %.0f contracts",
                            pair, opt_pos["contracts"],
                        )
                    else:
                        logger.info(
                            "Options position %s NOT found on exchange — closed/expired",
                            pair,
                        )
                        position_exists = False
                else:
                    # Futures: verify against actual Delta positions from fetch_positions()
                    delta_pos = delta_positions.get(pair)
                    if delta_pos:
                        position_exists = True
                        # Use EXCHANGE for size/side (truth), DB for entry_price (truth)
                        # Exchange entryPrice can be average/current — DB has our real entry
                        db_entry_price = float(trade.get("entry_price", 0) or 0)
                        exchange_entry_price = delta_pos["entry_price"]
                        amount = delta_pos["contracts"]
                        position_type = delta_pos["side"]
                        # Keep DB entry_price — only fall back to exchange if DB is 0
                        if db_entry_price > 0:
                            entry_price = db_entry_price
                        elif exchange_entry_price > 0:
                            entry_price = exchange_entry_price
                        logger.info(
                            "Delta position %s verified: %s %.0f contracts | "
                            "entry=$%.2f (DB) vs $%.2f (exchange) — using DB",
                            pair, position_type, amount, db_entry_price, exchange_entry_price,
                        )
                    else:
                        # Position not found on Delta — it was closed externally
                        logger.info(
                            "Delta position %s NOT found on exchange — was closed externally",
                            pair,
                        )
                        position_exists = False

            if position_exists:
                # Register with risk manager using a synthetic Signal
                from alpha.strategies.base import Signal, StrategyName
                try:
                    strat_name = StrategyName(strategy)
                except ValueError:
                    strat_name = StrategyName.SCALP  # fallback

                side = "buy" if position_type in ("spot", "long") else "sell"
                synthetic_signal = Signal(
                    side=side,
                    price=entry_price,
                    amount=amount,
                    order_type="market",
                    reason="restored from DB",
                    strategy=strat_name,
                    pair=pair,
                    leverage=leverage,
                    position_type=position_type,
                    exchange_id=exchange_id,
                )
                self.risk_manager.record_open(synthetic_signal)
                self._restored_trades.append({
                    "pair": pair,
                    "exchange_id": exchange_id,
                    "entry_price": entry_price,
                    "amount": amount,
                    "position_type": position_type,
                    "leverage": leverage,
                    "strategy": strategy,
                    "opened_at": trade.get("opened_at"),
                    "peak_pnl": trade.get("peak_pnl"),
                })
                restored += 1
                logger.info(
                    "RESTORED %s %s %.0f @ $%.2f (DB) on %s [%s]",
                    pair, position_type, amount, entry_price, exchange_id, strategy,
                )
            else:
                # Position no longer on exchange — find actual exit price
                exit_price = 0.0
                pnl = 0.0
                pnl_pct = 0.0

                # Try to get real exit price from recent trade history
                try:
                    exchange = self.delta  # Delta only mode
                    if exchange:
                        # fetch_my_trades returns recent fills for this pair
                        recent_trades = await exchange.fetch_my_trades(pair, limit=20)
                        if recent_trades:
                            # Find the most recent closing trade (opposite side)
                            close_side = "sell" if position_type in ("long", "spot") else "buy"
                            closing_fills = [
                                t for t in recent_trades
                                if t.get("side") == close_side
                            ]
                            if closing_fills:
                                last_fill = closing_fills[-1]  # most recent
                                exit_price = float(last_fill.get("price", 0) or 0)
                                logger.info(
                                    "Found exit fill for %s: $%.2f (from trade history)",
                                    pair, exit_price,
                                )
                        # Fallback: use current ticker price
                        if exit_price <= 0:
                            ticker = await exchange.fetch_ticker(pair)
                            exit_price = float(ticker.get("last", 0) or 0)
                            logger.info(
                                "No exit fill found for %s, using current price: $%.2f",
                                pair, exit_price,
                            )
                except Exception as e:
                    logger.warning(
                        "Could not fetch exit price for %s: %s — using entry as fallback",
                        pair, e,
                    )
                    exit_price = entry_price  # worst case: 0 P&L

                # Calculate P&L (leveraged, contract-aware)
                _fee = {"kraken": config.kraken.taker_fee,
                        "bybit": config.bybit.taker_fee,
                        "delta": config.delta.taker_fee_with_gst,
                        "binance": 0.001}.get(exchange_id, 0.0)
                result = calc_pnl(
                    entry_price, exit_price, amount,
                    position_type, leverage,
                    exchange_id, pair,
                    entry_fee_rate=_fee, exit_fee_rate=_fee,
                )
                pnl, pnl_pct = result.net_pnl, result.pnl_pct

                # Close in DB with real data
                order_id = trade.get("order_id", "")
                if order_id:
                    await self.db.close_trade(
                        order_id, exit_price, pnl, pnl_pct,
                        reason="position_not_found_on_restart",
                        exit_reason="GONE",
                        gross_pnl=result.gross_pnl,
                        entry_fee=result.entry_fee,
                        exit_fee=result.exit_fee,
                    )
                elif trade_id:
                    await self.db.update_trade(trade_id, {
                        "status": "closed",
                        "closed_at": iso_now(),
                        "exit_price": exit_price,
                        "pnl": pnl,
                        "pnl_pct": pnl_pct,
                        "gross_pnl": round(result.gross_pnl, 8),
                        "entry_fee": round(result.entry_fee, 8),
                        "exit_fee": round(result.exit_fee, 8),
                        "reason": "position_not_found_on_restart",
                        "exit_reason": "GONE",
                    })

                closed += 1
                logger.info(
                    "Position %s no longer on %s — closed (exit=$%.2f, pnl=$%.4f, %.2f%%, trade_id=%s)",
                    pair, exchange_id, exit_price, pnl, pnl_pct, trade_id,
                )

        # Also check for Delta positions NOT in DB (opened manually or DB out of sync)
        if delta_positions:
            db_delta_pairs = {
                t.get("pair") for t in open_trades if t.get("exchange") == "delta"
            }
            for symbol, dpos in delta_positions.items():
                if symbol not in db_delta_pairs:
                    logger.warning(
                        "Delta position %s %s %.0f contracts exists on exchange "
                        "but NOT in DB — creating DB record",
                        symbol, dpos["side"], dpos["contracts"],
                    )
                    # Create a DB trade record so the bot can manage exit
                    await self.db.log_trade({
                        "pair": symbol,
                        "exchange": "delta",
                        "strategy": "scalp",
                        "side": "buy" if dpos["side"] == "long" else "sell",
                        "entry_price": dpos["entry_price"],
                        "amount": dpos["contracts"],
                        "position_type": dpos["side"],
                        "leverage": config.delta.leverage,
                        "status": "open",
                        "opened_at": iso_now(),
                        "reason": "discovered_on_restart",
                        "setup_type": "SQUEEZE",
                    })
                    self._restored_trades.append({
                        "pair": symbol,
                        "exchange_id": "delta",
                        "entry_price": dpos["entry_price"],
                        "amount": dpos["contracts"],
                        "position_type": dpos["side"],
                        "leverage": config.delta.leverage,
                        "strategy": "scalp",
                        "opened_at": None,  # just discovered, treat as fresh
                        "peak_pnl": None,
                    })
                    # Also register with risk manager
                    from alpha.strategies.base import Signal, StrategyName
                    synthetic_signal = Signal(
                        side="buy" if dpos["side"] == "long" else "sell",
                        price=dpos["entry_price"],
                        amount=dpos["contracts"],
                        order_type="market",
                        reason="discovered on exchange",
                        strategy=StrategyName.SCALP,
                        pair=symbol,
                        leverage=config.delta.leverage,
                        position_type=dpos["side"],
                        exchange_id="delta",
                    )
                    self.risk_manager.record_open(synthetic_signal)
                    restored += 1

        logger.info(
            "Position restore complete: %d restored, %d marked closed (of %d DB open)",
            restored, closed, len(open_trades),
        )

    async def _restore_strategy_state(self) -> None:
        """Inject restored positions into strategy instances.

        Called AFTER strategies are created but BEFORE they start ticking.
        This tells scalp strategies about positions that were open before
        the restart, so they manage exits instead of opening duplicates.

        CRITICAL: entry_time is computed from the real opened_at timestamp
        (not time.monotonic()), so timeout/breakeven exits work correctly
        across bot restarts. Without this, timers reset to 0 on every deploy
        and positions can get stuck indefinitely.

        ALSO: fetches current price on restore to:
        - Update highest/lowest_since_entry for accurate trailing
        - Activate trailing if already past threshold
        - Log real PnL so we know the position's state immediately
        """
        if not hasattr(self, "_restored_trades") or not self._restored_trades:
            return

        injected = 0
        for trade in self._restored_trades:
            pair = trade["pair"]
            exchange_id = trade["exchange_id"]
            entry_price = trade["entry_price"]
            amount = trade["amount"]
            position_type = trade["position_type"]  # "long", "short", or "spot"
            strategy_name = trade.get("strategy", "")

            # Only inject scalp positions (our active strategy)
            scalp = self._get_scalp(pair, exchange=exchange_id)
            if scalp and strategy_name in ("scalp", ""):
                scalp.in_position = True
                scalp.position_side = position_type if position_type in ("long", "short") else "long"
                scalp.entry_price = entry_price
                scalp.entry_amount = amount

                # ── CRITICAL: use real opened_at time, not monotonic now ──
                # This ensures timeout (5min) and breakeven (60s) count from
                # ORIGINAL entry, not from restart. Without this, positions
                # survive forever across deploys because timers keep resetting.
                opened_at_str = trade.get("opened_at")
                if opened_at_str:
                    try:
                        from datetime import datetime, timezone
                        if isinstance(opened_at_str, str):
                            # Parse ISO timestamp: "2026-02-16T04:58:07.123Z"
                            opened_at_str = opened_at_str.replace("Z", "+00:00")
                            opened_dt = datetime.fromisoformat(opened_at_str)
                        else:
                            opened_dt = opened_at_str  # already datetime
                        # Convert to monotonic: how many seconds ago was it opened?
                        seconds_ago = (datetime.now(timezone.utc) - opened_dt).total_seconds()
                        seconds_ago = max(0, seconds_ago)  # don't go negative
                        scalp.entry_time = time.monotonic() - seconds_ago
                        logger.info(
                            "Restored %s entry_time: opened %ds ago (timeout/breakeven preserved)",
                            pair, int(seconds_ago),
                        )
                    except Exception as e:
                        logger.warning(
                            "Could not parse opened_at '%s' for %s: %s — using now",
                            opened_at_str, pair, e,
                        )
                        scalp.entry_time = time.monotonic()
                else:
                    scalp.entry_time = time.monotonic()

                scalp.highest_since_entry = entry_price
                scalp.lowest_since_entry = entry_price

                # Restore peak P&L if available (for decay exit)
                peak_pnl = trade.get("peak_pnl")
                if peak_pnl is not None and peak_pnl > 0:
                    scalp._peak_unrealized_pnl = float(peak_pnl)
                    logger.info("Restored %s peak_pnl: %.2f%%", pair, float(peak_pnl))

                # ── IMMEDIATE EXIT CHECK ON RESTORE ──────────────────
                # Fetch current price and check if we should exit right away.
                # This catches: SL breached while bot was down, TP reached,
                # trailing threshold already passed.
                try:
                    current_price = await self._get_current_price(pair, exchange_id)
                    if current_price and current_price > 0:
                        current_pnl = scalp._calc_pnl_pct(current_price)

                        # Update peak tracking with current price
                        if scalp.position_side == "long":
                            scalp.highest_since_entry = max(entry_price, current_price)
                        else:
                            scalp.lowest_since_entry = min(entry_price, current_price)
                        scalp._peak_unrealized_pnl = max(scalp._peak_unrealized_pnl, current_pnl)

                        # Activate trailing if already profitable enough
                        if current_pnl >= scalp.TRAILING_ACTIVATE_PCT:
                            scalp._trailing_active = True
                            scalp._update_trail_stop()
                            logger.info(
                                "[%s] RESTORE: already at +%.2f%% — trailing activated",
                                pair, current_pnl,
                            )

                        # If past SL, trigger immediate exit via WS check
                        sl_pct = scalp._sl_pct
                        if current_pnl <= -sl_pct:
                            logger.warning(
                                "[%s] RESTORE: already past SL (%.2f%% < -%.2f%%) — will exit on next tick",
                                pair, current_pnl, sl_pct,
                            )

                        logger.info(
                            "Restored %s %s %.0f @ $%.2f (DB) — current $%.2f — PnL %+.2f%%",
                            pair, scalp.position_side, amount, entry_price,
                            current_price, current_pnl,
                        )
                    else:
                        logger.info(
                            "Injected restored position into ScalpStrategy: "
                            "%s %s %.0f @ $%.2f on %s",
                            pair, scalp.position_side, amount, entry_price, exchange_id,
                        )
                except Exception:
                    logger.info(
                        "Injected restored position into ScalpStrategy: "
                        "%s %s %.0f @ $%.2f on %s (price fetch failed)",
                        pair, scalp.position_side, amount, entry_price, exchange_id,
                    )

                injected += 1
                continue

            # Non-scalp positions will be closed by _close_orphaned_positions()
            logger.warning(
                "Skipping restore for non-scalp position %s (%s strategy) — will be closed as orphan",
                pair, strategy_name,
            )

        logger.info(
            "Strategy state restoration complete — %d positions injected",
            injected,
        )

    # ==================================================================
    # PRICE HELPERS
    # ==================================================================

    async def _get_current_price(self, pair: str, exchange_id: str) -> float | None:
        """Fetch current price for a pair from the appropriate exchange.

        Returns None on any failure (caller should handle gracefully).
        """
        try:
            exchange = self.delta  # Delta only mode
            if exchange:
                ticker = await exchange.fetch_ticker(pair)
                return float(ticker.get("last", 0) or 0) or None
        except Exception:
            logger.debug("Could not fetch current price for %s/%s", pair, exchange_id)
        return None

    # ==================================================================
    # TELEGRAM HEALTH CHECK — verify connection every 5 minutes
    # ==================================================================

    def _watchdog_ping(self) -> None:
        """Send systemd watchdog keepalive every 60s + heartbeat log for cron watchdog."""
        self._sd_notifier.notify("WATCHDOG=1")
        logger.info("heartbeat")

    async def _telegram_health_check(self) -> None:
        """Ping Telegram API every 5 minutes. Reconnect if dead."""
        try:
            ok = await self.alerts.health_check()
            if not ok:
                logger.warning("Telegram health check failed — alerts may be down")
        except Exception:
            logger.exception("Telegram health check error")

    # ==================================================================
    # ORPHAN PROTECTION — reconcile exchange positions every 60s
    # ==================================================================

    async def _reconcile_exchange_positions(self) -> None:
        """Fetch ALL exchange positions and reconcile with bot memory.

        CASE 1: Exchange has position, bot doesn't track it → CLOSE immediately
        CASE 2: Bot thinks it has position, exchange doesn't → Mark closed in DB
        CASE 3: open_positions has entry but strategy says no position → GHOST SWEEP

        This is the #1 safety net. Runs on startup AND every 60 seconds.
        """
        try:
            await self._reconcile_delta_positions()
        except Exception:
            logger.exception("Orphan reconciliation failed (Delta)")

        # ── GHOST SWEEP ──────────────────────────────────────────────
        # Catch stale entries in open_positions where the strategy has
        # already cleared in_position (e.g., close order placed but
        # _close_trade_in_db() failed/threw, so record_close() was
        # never called). Without this, stale entries persist forever
        # because the per-pair reconciliation skips pairs where
        # scalp.in_position == False.
        try:
            ghost_pairs: list[str] = []
            for pos in self.risk_manager.open_positions:
                scalp = self._get_scalp(pos.pair, exchange=pos.exchange)
                if scalp is not None and scalp.in_position:
                    continue  # scalp strategy owns this position
                # Check options strategies too
                base_pair = pos.pair.split("-")[0] if "-" in pos.pair else pos.pair
                opts = self._options_strategies.get(pos.pair)
                if opts is None:
                    opts = self._options_strategies.get(base_pair)
                if opts is None:
                    opts = next(
                        (
                            strategy
                            for pair_key, strategy in self._options_strategies.items()
                            if pair_key.startswith(f"{base_pair}/")
                            or strategy._base_asset == base_pair
                        ),
                        None,
                    )
                if opts is not None and opts.in_position:
                    continue  # options strategy owns this position
                ghost_pairs.append(pos.pair)
            for pair in ghost_pairs:
                logger.warning(
                    "GHOST SWEEP: removing stale open_positions entry for %s "
                    "(strategy.in_position=False but risk_manager still tracking)",
                    pair,
                )
                self.risk_manager.record_close(pair, 0.0)
        except Exception:
            logger.exception("Ghost sweep failed")

        # ── DB ORPHAN SWEEP (options only — log, never close) ──────────
        try:
            all_open = await self.db.get_all_open_trades()
            await self._orphan_sweep_options(all_open)
        except Exception:
            logger.exception("DB orphan sweep failed")

        # ── MISSING OPTIONS SYNC ────────────────────────────────────────
        # Catch live exchange positions that have no DB record (race on entry)
        try:
            await self._sync_missing_options_to_db()
        except Exception:
            logger.exception("Missing options sync failed")

        # ── GPFC #45: OPTIONS SELF-HEAL ─────────────────────────────────
        # Close ghost / expired rows, force-refresh corrupt current_price
        # from a fresh ticker so dashboards stop showing hallucinated values.
        try:
            await self._reconcile_option_open_rows()
        except Exception:
            logger.exception("Options self-heal reconcile failed")

    async def _orphan_sweep_futures(self, all_open: list[dict]) -> None:
        """DISABLED — futures sweep removed (Delta options only mode)."""
        return  # noqa: no futures orphan sweep
        for trade in all_open:
            pair = trade.get("pair", "")
            exchange = trade.get("exchange", "")
            trade_id = trade.get("id")
            strategy_name = trade.get("strategy", "")
            if not pair or not trade_id:
                continue

            # Skip options trades — handled by _orphan_sweep_options
            if strategy_name == "options_scalp" or is_option_symbol(pair):
                continue

            # Check if any strategy is actively managing this position
            fs_key = f"{exchange}:{pair}"
            scalp = self._get_scalp(pair, exchange=exchange)
            if scalp and scalp.in_position:
                self._position_first_seen.pop(fs_key, None)
                continue

            # No strategy owns this — check grace period before closing
            if fs_key not in self._position_first_seen:
                self._position_first_seen[fs_key] = time.monotonic()
            age = time.monotonic() - self._position_first_seen[fs_key]
            if age < self.ORPHAN_GRACE_S:
                logger.info(
                    "ORPHAN_GRACE: skipping DB trade id=%s %s/%s (age %.0fs < %ds)",
                    trade_id, pair, exchange, age, self.ORPHAN_GRACE_S,
                )
                continue
            self._position_first_seen.pop(fs_key, None)

            logger.warning(
                "DB ORPHAN SWEEP (futures): closing trade id=%s %s/%s "
                "(no strategy tracking, no exchange position)",
                trade_id, pair, exchange,
            )
            entry_price = float(trade.get("entry_price", 0) or 0)
            position_type = trade.get("position_type", "spot")
            leverage = trade.get("leverage", 1) or 1
            amount = float(trade.get("amount", 0) or 0)
            pnl = 0.0

            # Try to get current price for P&L calculation
            exit_price = entry_price
            try:
                ex = self.delta  # Delta only mode
                if ex:
                    ticker = await ex.fetch_ticker(pair)
                    exit_price = float(ticker.get("last", 0) or 0) or entry_price
            except Exception:
                pass  # use entry_price as fallback (0 P&L)

            _fee = {"kraken": config.kraken.taker_fee,
                    "bybit": config.bybit.taker_fee,
                    "delta": config.delta.taker_fee_with_gst,
                    "binance": 0.001}.get(exchange, 0.0)
            result = calc_pnl(
                entry_price, exit_price, amount,
                position_type, leverage,
                exchange, pair,
                entry_fee_rate=_fee, exit_fee_rate=_fee,
            )
            await self.db.update_trade(trade_id, {
                "status": "closed",
                "exit_price": exit_price,
                "closed_at": iso_now(),
                "pnl": round(result.net_pnl, 8),
                "pnl_pct": round(result.pnl_pct, 4),
                "gross_pnl": round(result.gross_pnl, 8),
                "entry_fee": round(result.entry_fee, 8),
                "exit_fee": round(result.exit_fee, 8),
                "exit_reason": "ORPHAN",
                "position_state": None,
            })
            logger.info(
                "DB ORPHAN closed (futures): id=%s %s exit=$%.4f pnl=$%.4f (%.2f%%)",
                trade_id, pair, exit_price, result.net_pnl, result.pnl_pct,
            )

    async def _orphan_sweep_options(self, all_open: list[dict]) -> None:
        """Log orphan options trades but do NOT auto-close them.

        Options positions are managed by options_scalp.py's
        _restore_position_from_db() on restart. Never close them here.
        """
        for trade in all_open:
            pair = trade.get("pair", "")
            exchange = trade.get("exchange", "")
            trade_id = trade.get("id")
            strategy_name = trade.get("strategy", "")
            if not pair or not trade_id:
                continue

            # Only handle options trades
            if strategy_name != "options_scalp" and not is_option_symbol(pair):
                continue

            # Check if the options strategy is actively managing it
            base_asset = pair.split("-")[0] if "-" in pair else pair
            opts = self._options_strategies.get(base_asset)
            if opts and opts.in_position:
                fs_key = f"{exchange}:{pair}"
                self._position_first_seen.pop(fs_key, None)
                continue

            # Not actively managed — LOG only, do NOT close.
            # options_scalp._restore_position_from_db() will pick it up on restart.
            logger.info(
                "DB ORPHAN SWEEP (options): SKIP id=%s %s/%s — "
                "options positions are restored on restart, not auto-closed",
                trade_id, pair, exchange,
            )

    async def _reconcile_option_open_rows(self) -> None:
        """GPFC #45: self-heal open option rows against Delta truth.

        For every DB row where status='open' AND strategy='options_scalp':
          - Ghost (no Delta position)               -> RECONCILE_ORPHAN_CLOSED
          - Expired (hours_to_expiry < 0)           -> RECONCILE_EXPIRED
          - Corrupt current_price (>99% off real)   -> force-refresh from ticker

        Runs on every 60 s reconcile cycle. Makes the DB self-correcting so
        the dashboard never carries hallucinated / stale premium values.
        """
        if not self.delta_options or not self.db.is_connected:
            return

        try:
            all_open = await self.db.get_all_open_trades()
        except Exception:
            logger.exception("SELF_HEAL: failed to fetch open trades")
            return

        option_rows = [
            t for t in all_open
            if t.get("strategy") == "options_scalp"
            and t.get("exchange") == "delta"
            and is_option_symbol(t.get("pair", ""))
        ]
        if not option_rows:
            return

        # Fetch Delta truth once per cycle.
        try:
            positions = await self.delta_options.fetch_positions()
        except Exception:
            logger.debug("SELF_HEAL: fetch_positions failed; skipping this cycle")
            return

        live_contracts: dict[str, float] = {}
        for pos in positions:
            contracts = float(pos.get("contracts", 0) or 0)
            if abs(contracts) < 1e-8:
                continue
            sym = pos.get("symbol", "")
            if sym:
                live_contracts[sym] = contracts

        # GPFC #48: increment/clear per-symbol empty-cycle counters BEFORE
        # looping the DB rows, so every row for the same symbol sees the same
        # counter this pass. Counter resets the moment Delta reports a position.
        symbols_this_pass = {t.get("pair", "") for t in option_rows if t.get("pair")}
        for sym in symbols_this_pass:
            if sym in live_contracts:
                self._option_symbol_empty_cycles.pop(sym, None)
            else:
                self._option_symbol_empty_cycles[sym] = (
                    self._option_symbol_empty_cycles.get(sym, 0) + 1
                )
        # Drop counters for symbols no longer in any open DB row.
        for stale_sym in list(self._option_symbol_empty_cycles.keys()):
            if stale_sym not in symbols_this_pass:
                self._option_symbol_empty_cycles.pop(stale_sym, None)

        now_utc = _dt.datetime.now(_dt.timezone.utc)

        for trade in option_rows:
            trade_id = trade.get("id")
            pair = trade.get("pair", "")
            if not trade_id or not pair:
                continue

            # ── 1. EXPIRED check (close regardless of positions-API state) ──
            expiry_str = ""
            md = trade.get("metadata") or {}
            if isinstance(md, dict):
                expiry_str = str(md.get("expiry") or "")
            if not expiry_str:
                # fall back to parsing symbol YYMMDD segment if present
                expiry_str = ""
            expired = False
            if expiry_str:
                try:
                    expiry_dt = _dt.datetime.fromisoformat(
                        expiry_str.replace("Z", "+00:00"),
                    )
                    if expiry_dt.tzinfo is None:
                        expiry_dt = expiry_dt.replace(tzinfo=_dt.timezone.utc)
                    expired = now_utc >= expiry_dt
                except Exception:
                    expired = False
            if expired:
                entry_price = float(trade.get("entry_price", 0) or 0)
                contracts = int(
                    trade.get("contracts") or trade.get("amount") or 0,
                )
                try:
                    await self.db.update_trade(trade_id, {
                        "status": "closed",
                        "closed_at": iso_now(),
                        "exit_price": 0.0 if entry_price > 0 else 0.0,
                        "pnl": -entry_price * contracts * 0.01,
                        "pnl_pct": -100.0,
                        "exit_reason": "EXPIRY",
                        "reason": "expired_on_reconcile",
                        "position_state": None,
                    })
                    logger.warning(
                        "SELF_HEAL: id=%s %s expired — closed as RECONCILE_EXPIRED",
                        trade_id, pair,
                    )
                except Exception:
                    logger.exception("SELF_HEAL: failed to close expired id=%s", trade_id)
                continue

            # ── 2. GHOST check (no matching Delta position) ─────────────
            if pair not in live_contracts:
                # Grace: don't close trades opened < 5 min ago (fill race)
                opened_str = trade.get("opened_at", "")
                if opened_str:
                    try:
                        if isinstance(opened_str, str):
                            op = opened_str.replace("Z", "+00:00")
                            opened_dt = _dt.datetime.fromisoformat(op)
                        else:
                            opened_dt = opened_str
                        age = (now_utc - opened_dt).total_seconds()
                        if age < 300:
                            continue
                    except Exception:
                        pass

                # GPFC #48: require 2 consecutive empty cycles before closing.
                # One empty positions-API read is often a transient glitch;
                # real orphans stay empty across successive reconciles.
                empty_cycles = self._option_symbol_empty_cycles.get(pair, 0)
                if empty_cycles < 2:
                    logger.warning(
                        "SELF_HEAL: id=%s %s not in Delta positions "
                        "(cycle %d/2) — waiting for confirmation, NOT closing",
                        trade_id, pair, empty_cycles,
                    )
                    continue

                # Try to fetch a current bid so we close with real price.
                # GPFC #47: never use `last` — Delta leaks spot there.
                exit_price = 0.0
                try:
                    ticker = await self.delta_options.fetch_ticker(pair)
                    exit_price = float(
                        ticker.get("bid")
                        or ticker.get("ask")
                        or 0,
                    )
                except Exception:
                    exit_price = 0.0

                entry_price = float(trade.get("entry_price", 0) or 0)
                contracts = int(trade.get("contracts") or trade.get("amount") or 0)
                try:
                    pnl = 0.0
                    pnl_pct = 0.0
                    if entry_price > 0 and contracts > 0 and exit_price > 0:
                        # ETH = 0.01, BTC = 0.001
                        mult = 0.001 if "BTC" in pair else 0.01
                        pnl = (exit_price - entry_price) * contracts * mult
                        pnl_pct = (exit_price - entry_price) / entry_price * 100
                    await self.db.update_trade(trade_id, {
                        "status": "closed",
                        "closed_at": iso_now(),
                        "exit_price": exit_price,
                        "pnl": round(pnl, 8),
                        "pnl_pct": round(pnl_pct, 4),
                        "exit_reason": "ORPHAN",
                        "reason": "no_delta_position_on_reconcile",
                        "position_state": None,
                    })
                    logger.warning(
                        "SELF_HEAL: id=%s %s has no Delta position — "
                        "RECONCILE_ORPHAN_CLOSED at $%.4f (pnl=$%.4f)",
                        trade_id, pair, exit_price, pnl,
                    )
                except Exception:
                    logger.exception(
                        "SELF_HEAL: failed to close ghost id=%s", trade_id,
                    )
                continue

            # ── 3. Corrupt current_price check ──────────────────────────
            # GPFC #47: prefer info.mark_price; never trust `last` on Delta.
            stored_cp = float(trade.get("current_price", 0) or 0)
            if stored_cp <= 0:
                continue
            try:
                ticker = await self.delta_options.fetch_ticker(pair)
                info = ticker.get("info") or {}
                real_premium = 0.0
                mark = info.get("mark_price") if isinstance(info, dict) else None
                if mark is not None:
                    try:
                        real_premium = float(mark)
                    except (TypeError, ValueError):
                        real_premium = 0.0
                if real_premium <= 0:
                    bid = float(ticker.get("bid") or 0)
                    ask = float(ticker.get("ask") or 0)
                    if bid > 0 and ask > 0:
                        real_premium = (bid + ask) / 2.0
                    elif bid > 0:
                        real_premium = bid
                    elif ask > 0:
                        real_premium = ask
            except Exception:
                continue
            if real_premium <= 0:
                continue
            deviation = abs(stored_cp - real_premium) / real_premium
            if deviation > 0.99:
                entry_price = float(trade.get("entry_price", 0) or 0)
                fresh_pnl_pct = (
                    (real_premium - entry_price) / entry_price * 100
                    if entry_price > 0 else 0.0
                )
                fresh_peak = max(
                    float(trade.get("peak_pnl") or 0),
                    fresh_pnl_pct,
                )
                # Don't let a previously-corrupted peak stay sky-high.
                if abs(float(trade.get("peak_pnl") or 0)) > 500:
                    fresh_peak = fresh_pnl_pct
                try:
                    await self.db.update_trade(trade_id, {
                        "current_price": round(real_premium, 8),
                        "current_pnl": round(fresh_pnl_pct, 4),
                        "peak_pnl": round(fresh_peak, 4),
                    })
                    logger.warning(
                        "SELF_HEAL: id=%s %s corrupt current_price "
                        "$%.4f → $%.4f (real), pnl=%.1f%% peak=%.1f%%",
                        trade_id, pair, stored_cp, real_premium,
                        fresh_pnl_pct, fresh_peak,
                    )
                except Exception:
                    logger.exception(
                        "SELF_HEAL: failed to refresh corrupt id=%s", trade_id,
                    )

    async def _merge_duplicate_open_options(self) -> None:
        """GPFC #48: collapse duplicate open option rows for the same symbol.

        When the signal path and on_fill callback both insert for the same
        fill (pre-GPFC #48 races), we end up with 2+ open rows per symbol.
        At startup, keep the row with the most populated state (highest
        ``current_price`` / ``peak_pnl`` / non-zero ``entry_price``) and
        **hard-delete** the rest so they don't pollute trade counts, win
        rate, or dashboard history.
        """
        if not self.db.is_connected:
            return
        try:
            all_open = await self.db.get_all_open_trades()
        except Exception:
            logger.exception("MERGE_DUPES: failed to fetch open trades")
            return

        opts_open = [
            t for t in all_open
            if t.get("strategy") == "options_scalp"
            and t.get("exchange") == "delta"
        ]
        if len(opts_open) < 2:
            return

        by_pair: dict[str, list[dict]] = {}
        for t in opts_open:
            pair = t.get("pair") or ""
            if not pair:
                continue
            by_pair.setdefault(pair, []).append(t)

        def _richness(row: dict) -> tuple[float, float, float, float, int]:
            # Rank by data completeness, newer row wins on ties.
            entry_p = float(row.get("entry_price") or 0)
            cur_p = float(row.get("current_price") or 0)
            peak = float(row.get("peak_pnl") or 0)
            fee = float(row.get("entry_fee") or 0)
            rid = int(row.get("id") or 0)
            return (
                1.0 if entry_p > 0 else 0.0,
                1.0 if cur_p > 0 else 0.0,
                abs(peak),
                fee,
                rid,
            )

        for pair, rows in by_pair.items():
            if len(rows) < 2:
                continue
            rows_sorted = sorted(rows, key=_richness, reverse=True)
            keeper = rows_sorted[0]
            drops = rows_sorted[1:]
            logger.warning(
                "MERGE_DUPES: %s has %d open rows — keeping id=%s, "
                "hard-deleting %d duplicate row(s)",
                pair, len(rows), keeper.get("id"), len(drops),
            )
            for drop in drops:
                drop_id = drop.get("id")
                if not drop_id:
                    continue
                try:
                    ok = await self.db.delete_trade(drop_id)
                    if not ok:
                        logger.warning(
                            "MERGE_DUPES: delete_trade returned False for id=%s",
                            drop_id,
                        )
                except Exception:
                    logger.exception(
                        "MERGE_DUPES: failed to delete duplicate id=%s", drop_id,
                    )

    async def _close_orphan_options_on_startup(self) -> None:
        """Close stale options trades in DB that have no matching exchange position.

        Runs AFTER opts.start() (which restores DB state into strategy memory).
        If a trade has been open >10 min and Delta has no matching position,
        close it as ORPHAN_STARTUP and clear the strategy's in_position flag.
        """
        if not self.delta_options or not self.db.is_connected:
            return

        # Fetch all open options_scalp trades from DB
        try:
            all_open = await self.db.get_open_trades()
        except Exception as e:
            logger.error("ORPHAN_STARTUP: failed to fetch open trades: %s", e)
            return

        option_trades = [
            t for t in all_open
            if t.get("strategy") == "options_scalp"
            and t.get("exchange") == "delta"
        ]
        if not option_trades:
            return

        # Fetch live options positions from Delta
        exchange_positions: dict[str, dict[str, Any]] = {}
        try:
            positions = await self.delta_options.fetch_positions()
            for pos in positions:
                contracts = float(pos.get("contracts", 0) or 0)
                if contracts != 0:
                    symbol = pos.get("symbol", "")
                    exchange_positions[symbol] = {
                        "side": "long" if contracts > 0 else "short",
                        "contracts": abs(contracts),
                    }
        except Exception as e:
            logger.error("ORPHAN_STARTUP: failed to fetch Delta options positions: %s", e)
            return

        now = _dt.datetime.now(_dt.timezone.utc)
        closed = 0

        for trade in option_trades:
            trade_id = trade.get("id")
            pair = trade.get("pair", "")
            if not trade_id:
                continue

            # Check if position exists on exchange
            if pair in exchange_positions:
                continue  # real position — leave it alone

            # Check age
            opened_str = trade.get("opened_at", "")
            if not opened_str:
                continue
            try:
                if isinstance(opened_str, str):
                    opened_str = opened_str.replace("Z", "+00:00")
                    opened_dt = _dt.datetime.fromisoformat(opened_str)
                else:
                    opened_dt = opened_str
                age = now - opened_dt
            except (ValueError, TypeError):
                logger.warning("ORPHAN_STARTUP: can't parse opened_at for trade %s", trade_id)
                continue

            if age < _dt.timedelta(minutes=10):
                logger.info(
                    "ORPHAN_STARTUP: trade %s %s age %s < 10min — skipping",
                    trade_id, pair, age,
                )
                continue

            # No exchange position and >30 min old → close as orphan
            entry_price = float(trade.get("entry_price", 0) or 0)
            contracts = int(trade.get("contracts") or trade.get("amount") or 0)

            await self.db.update_trade(trade_id, {
                "status": "closed",
                "closed_at": iso_now(),
                "exit_price": entry_price,
                "pnl": 0.0,
                "pnl_pct": 0.0,
                "exit_reason": "ORPHAN",
                "reason": f"stale orphan closed on startup (age {age})",
            })

            # Clear strategy in_position so it can trade again
            base_asset = pair.split("/")[0] if "/" in pair else ""
            opts = self._options_strategies.get(
                next((k for k in self._options_strategies if k.split("/")[0] == base_asset), ""),
            )
            if opts and opts.in_position and opts.option_symbol == pair:
                opts.in_position = False
                OptionsScalpStrategy._global_in_position = False  # release global lock
                OptionsScalpStrategy._global_position_asset = None
                opts.option_symbol = None
                opts._db_trade_id = None
                opts._contracts = 0

            closed += 1
            logger.warning(
                "ORPHAN_STARTUP: closed stale trade #%s %s (age %s, entry=$%.4f, %d contracts)",
                trade_id, pair, age, entry_price, contracts,
            )

            try:
                await self.alerts.send_orphan_alert(
                    pair=pair,
                    side="buy",
                    contracts=float(contracts),
                    action="CLOSED as ORPHAN_STARTUP",
                    detail=f"Age: {age} — entry: ${entry_price:.4f} — no exchange position",
                )
            except Exception:
                pass

        if closed:
            logger.info("ORPHAN_STARTUP: closed %d stale options trade(s)", closed)

        # After closing orphans, discover any live positions missing from DB
        await self._sync_missing_options_to_db()

    async def _sync_missing_options_to_db(self) -> None:
        """Find live Delta options positions with no DB record and sync them.

        This catches trades where the entry DB write was lost due to race
        conditions or restarts. Creates the DB record and injects state into
        the strategy so the bot manages the exit normally.
        """
        if not self.delta_options or not self.db.is_connected:
            return

        # Fetch live options positions
        try:
            positions = await self.delta_options.fetch_positions()
        except Exception as e:
            logger.debug("Missing options sync: fetch_positions failed: %s", e)
            return

        live_positions: dict[str, dict[str, Any]] = {}
        for pos in positions:
            contracts = float(pos.get("contracts", 0) or 0)
            if contracts == 0:
                continue
            symbol = pos.get("symbol", "")
            if not symbol:
                continue
            live_positions[symbol] = {
                "contracts": abs(contracts),
                "entry_price": float(pos.get("entryPrice", 0) or pos.get("mark_price", 0) or 0),
                "mark_price": float(pos.get("mark_price", 0) or 0),
            }

        # GPFC #43: clear defer-alert flags for orphans that no longer exist on
        # Delta, so if the same symbol ever reappears it gets a fresh alert.
        _live_syms = set(live_positions.keys())
        stale_defer = self._orphan_defer_alerted - _live_syms
        if stale_defer:
            self._orphan_defer_alerted -= stale_defer

        if not live_positions:
            return

        # Fetch DB open options trades
        try:
            all_open = await self.db.get_all_open_trades()
        except Exception as e:
            logger.debug("Missing options sync: get_all_open_trades failed: %s", e)
            return

        db_option_pairs = {
            t.get("pair") for t in all_open
            if t.get("strategy") == "options_scalp" and t.get("exchange") == "delta"
        }

        for symbol, pos in live_positions.items():
            # Parse symbol: e.g. ETH/USD:USD-260331-2100-C
            base_asset = symbol.split("/")[0] if "/" in symbol else ""
            option_side = "call" if symbol.endswith("-C") else ("put" if symbol.endswith("-P") else "call")

            # Find matching strategy up-front — we need it for ownership checks
            # and for the adoption path below.
            opts = None
            for _pk, _strategy in self._options_strategies.items():
                if _strategy._base_asset == base_asset:
                    opts = _strategy
                    break

            # CASE A: strategy is actively tracking THIS symbol → leave alone.
            if opts is not None and opts.in_position and opts.option_symbol == symbol:
                # Orphan resolved — clear any stale defer-alert flag.
                self._orphan_defer_alerted.discard(symbol)
                continue

            # ═════════════════════════════════════════════════════════════
            # GPFC #43: ADOPT-FIRST RECONCILER
            #
            # Prior behaviour (GPFC #41/42) flattened any live Delta options
            # position the bot wasn't actively managing. User feedback:
            # "Orphan should be taken back into position and the bot should
            # be able to manage it." So we now:
            #
            #   • Re-hydrate strategy state from Delta (entry avg, mark,
            #     contracts, strike, expiry) + any existing DB row, so the
            #     normal exit engine (hard-SL, breakeven, peak-trail) takes
            #     over from the next tick.
            #   • Defer adoption (alert once + wait) when the strategy is
            #     already tracking a *different* symbol — the strategy is
            #     single-position by design, so the next sweep after the
            #     current trade closes will pick the orphan up.
            #
            # Peak-trail granularity for adopted positions is degraded
            # (historical highest_premium is gone) but hard-SL, breakeven,
            # and fresh-peak tracking from adoption time all still fire,
            # so the position is no longer bleeding unmanaged.
            # ═════════════════════════════════════════════════════════════

            # CASE B1: no strategy registered for this base asset (e.g. you
            # manually opened a BTC option while the bot runs ETH-only).
            # We can't manage it — alert once, leave on exchange.
            if opts is None:
                if symbol not in self._orphan_defer_alerted:
                    self._orphan_defer_alerted.add(symbol)
                    logger.warning(
                        "ORPHAN_UNMANAGED: %s x%.0f on Delta but no %s "
                        "strategy registered — leaving on exchange, "
                        "please close manually if unintended",
                        symbol, pos["contracts"], base_asset,
                    )
                    try:
                        await self.alerts.send_orphan_alert(
                            pair=symbol,
                            side=option_side,
                            contracts=pos["contracts"],
                            action="UNMANAGED (no strategy)",
                            detail=(
                                f"No {base_asset} strategy registered. "
                                f"Position will sit idle on Delta until you "
                                f"close it manually."
                            ),
                        )
                    except Exception:
                        pass
                continue

            # CASE B2: strategy is busy managing a DIFFERENT symbol.
            # Single-position strategy can't juggle two — defer adoption
            # until current trade closes. Next sweep (≤60 s) handles it.
            if opts.in_position and opts.option_symbol and opts.option_symbol != symbol:
                if symbol not in self._orphan_defer_alerted:
                    self._orphan_defer_alerted.add(symbol)
                    logger.warning(
                        "ORPHAN_DEFER: %s x%.0f — strategy busy with %s, "
                        "will adopt when current trade closes",
                        symbol, pos["contracts"], opts.option_symbol,
                    )
                    try:
                        await self.alerts.send_orphan_alert(
                            pair=symbol,
                            side=option_side,
                            contracts=pos["contracts"],
                            action="DEFERRED (strategy busy)",
                            detail=(
                                f"Strategy is managing {opts.option_symbol}. "
                                f"This orphan will be adopted after the "
                                f"current trade closes (≤60 s)."
                            ),
                        )
                    except Exception:
                        pass
                continue

            # CASE C: strategy is idle → adopt. Reuse existing DB row if one
            # exists (preserves opened_at, original entry_fee, setup_type),
            # otherwise create a new one. In both paths we inject live state
            # into the strategy so exit management resumes immediately.
            has_stale_db_row = symbol in db_option_pairs
            logger.warning(
                "ORPHAN_ADOPT: %s x%.0f @ $%.4f — %s, injecting into strategy",
                symbol, pos["contracts"], pos["entry_price"],
                "reusing existing DB row" if has_stale_db_row else "creating new DB row",
            )

            # Parse strike
            strike_price = 0.0
            parts = symbol.split("-")
            if len(parts) >= 3:
                try:
                    strike_price = float(parts[-2])
                except ValueError:
                    pass

            # Parse expiry
            expiry_dt = None
            if len(parts) >= 3:
                try:
                    expiry_str = parts[-3]
                    expiry_dt = _dt.datetime.strptime(expiry_str, "%y%m%d").replace(
                        hour=12, tzinfo=_dt.timezone.utc,
                    )
                except (ValueError, IndexError):
                    pass

            # opts is already resolved at the top of the loop; no re-lookup.

            # Adopt DB row: reuse existing if present (preserves opened_at,
            # original entry_fee, setup_type), otherwise create a new one.
            adopted_db_id: int | None = None
            if has_stale_db_row:
                try:
                    _rows = (
                        self.db.client.table("trades")
                        .select("id,entry_price,opened_at")
                        .eq("pair", symbol)
                        .eq("strategy", "options_scalp")
                        .eq("exchange", "delta")
                        .eq("status", "open")
                        .order("opened_at", desc=True)
                        .execute()
                    )
                    _data = _rows.data or []
                    if _data:
                        adopted_db_id = int(_data[0]["id"])
                    # If multiple open rows exist for the same symbol (legacy
                    # dup artifact), keep the newest and null-close the rest
                    # so the dashboard position count is correct.
                    for _extra in _data[1:]:
                        try:
                            await self.db.update_trade(int(_extra["id"]), {
                                "status": "cancelled",
                                "exit_reason": "DUPLICATE_ADOPTED",
                                "reason": "adopt_dedup_on_reconcile",
                                "closed_at": iso_now(),
                                "position_state": None,
                            })
                        except Exception:
                            pass
                except Exception as e:
                    logger.error(
                        "ORPHAN_ADOPT: failed to look up existing DB row for "
                        "%s: %s — will create a new one", symbol, e,
                    )

            if adopted_db_id is None:
                try:
                    cutoff = (
                        _dt.datetime.now(_dt.timezone.utc)
                        - _dt.timedelta(minutes=20)
                    ).isoformat()
                    _recent_rows = (
                        self.db.client.table("trades")
                        .select("id,entry_price,contracts,amount,opened_at,metadata")
                        .eq("pair", symbol)
                        .eq("strategy", "options_scalp")
                        .eq("exchange", "delta")
                        .eq("status", "closed")
                        .eq("exit_reason", "RECONCILE_GONE")
                        .gte("opened_at", cutoff)
                        .order("opened_at", desc=True)
                        .limit(10)
                        .execute()
                    )
                    for _row in _recent_rows.data or []:
                        row_entry = float(_row.get("entry_price") or 0)
                        row_contracts = float(
                            _row.get("contracts") or _row.get("amount") or 0
                        )
                        entry_close = (
                            row_entry <= 0
                            or pos["entry_price"] <= 0
                            or abs(row_entry - pos["entry_price"])
                            <= max(0.05, pos["entry_price"] * 0.03)
                        )
                        contracts_close = (
                            row_contracts <= 0
                            or abs(row_contracts - pos["contracts"]) <= 1
                        )
                        if not (entry_close and contracts_close):
                            continue

                        existing_metadata = _row.get("metadata") or {}
                        if not isinstance(existing_metadata, dict):
                            existing_metadata = {}
                        existing_metadata.update({
                            "reopened_from_reconcile_gone": True,
                            "reopened_at": iso_now(),
                            "reopen_mark_price": pos.get("mark_price") or 0,
                            "reopen_entry_price": pos["entry_price"],
                            "reopen_contracts": pos["contracts"],
                        })

                        await self.db.update_trade(int(_row["id"]), {
                            "status": "open",
                            "exit_price": None,
                            "closed_at": None,
                            "pnl": None,
                            "net_pnl": None,
                            "pnl_pct": None,
                            "gross_pnl": None,
                            "exit_fee": None,
                            "reason": "reopened_after_false_reconcile_gone",
                            "exit_reason": None,
                            "position_state": "open",
                            "metadata": existing_metadata,
                        })
                        adopted_db_id = int(_row["id"])
                        has_stale_db_row = True
                        logger.warning(
                            "ORPHAN_ADOPT: reopened recent RECONCILE_GONE row %s "
                            "for %s x%.0f @ $%.4f instead of creating duplicate",
                            adopted_db_id, symbol, pos["contracts"], pos["entry_price"],
                        )
                        break
                except Exception as e:
                    logger.error(
                        "ORPHAN_ADOPT: failed to look up recent RECONCILE_GONE row "
                        "for %s: %s - will create a new one", symbol, e,
                    )

            if adopted_db_id is None:
                try:
                    _new_row = await self.db.log_trade({
                        "pair": symbol,
                        "exchange": "delta",
                        "strategy": "options_scalp",
                        "side": "buy",
                        "entry_price": pos["entry_price"],
                        "contracts": pos["contracts"],
                        "leverage": 50,
                        "position_type": "long",
                        "status": "open",
                        "opened_at": iso_now(),
                        "reason": "discovered_by_reconcile",
                        "setup_type": "SQUEEZE",
                    })
                    if isinstance(_new_row, dict) and _new_row.get("id"):
                        adopted_db_id = int(_new_row["id"])
                except Exception as e:
                    logger.error(
                        "ORPHAN_ADOPT: failed to insert DB record for %s: %s",
                        symbol, e,
                    )
                    continue

            # Inject live state into the strategy so exits resume on the
            # next tick. Historical peak is lost on pure-orphan adoptions;
            # hard-SL / breakeven / fresh peak-trail all still work.
            opts.in_position = True
            OptionsScalpStrategy._global_in_position = True
            OptionsScalpStrategy._global_position_asset = base_asset
            opts.option_symbol = symbol
            opts.option_side = option_side
            opts.entry_premium = pos["entry_price"]
            opts.entry_time = time.monotonic()
            opts.highest_premium = max(
                pos["entry_price"], pos.get("mark_price") or pos["entry_price"]
            )
            if opts.entry_premium > 0:
                current_peak_pct = (
                    (opts.highest_premium - opts.entry_premium)
                    / opts.entry_premium
                    * 100
                )
                opts._opt_ratchet_floor = opts._compute_dynamic_floor(
                    current_peak_pct, 0.0
                )
            opts._last_known_premium = pos["mark_price"] or pos["entry_price"]
            opts._contracts = int(pos["contracts"])
            opts.strike_price = strike_price
            opts.expiry_dt = expiry_dt
            opts._trailing_active = False
            opts._consecutive_ticker_failures = 0
            opts._position_verify_failures = 0
            if adopted_db_id is not None:
                try:
                    opts._db_trade_id = adopted_db_id
                except Exception:
                    pass
            logger.info(
                "ORPHAN_ADOPT: %s %s x%d strike=$%.0f entry=$%.4f mark=$%.4f "
                "peak=$%.4f db_id=%s — strategy now managing",
                symbol, option_side, opts._contracts, strike_price,
                opts.entry_premium, pos.get("mark_price") or 0,
                opts.highest_premium, adopted_db_id,
            )

            # Register with risk manager so position counts stay accurate.
            from alpha.strategies.base import Signal, StrategyName
            synthetic_signal = Signal(
                side="buy",
                price=pos["entry_price"],
                amount=pos["contracts"],
                order_type="market",
                reason="discovered_by_reconcile",
                strategy=StrategyName.OPTIONS_SCALP,
                pair=symbol,
                leverage=50,
                position_type="long",
                exchange_id="delta",
            )
            self.risk_manager.record_open(synthetic_signal)

            # Adoption succeeded — clear any prior defer-alert flag.
            self._orphan_defer_alerted.discard(symbol)

            try:
                await self.alerts.send_orphan_alert(
                    pair=symbol,
                    side=option_side,
                    contracts=pos["contracts"],
                    action="ADOPTED (strategy now managing)",
                    detail=(
                        f"Entry: ${pos['entry_price']:.4f}  mark: "
                        f"${pos.get('mark_price') or 0:.4f}. Hard-SL, "
                        f"breakeven, and peak-trail active from this tick."
                    ),
                )
            except Exception:
                pass

    async def _reconcile_bybit_positions(self) -> None:
        """DISABLED — Bybit not used (Delta options only mode)."""
        return  # noqa: Bybit disabled
        if not self.bybit:
            return

        # ── Step 1: Fetch ALL open positions from Bybit ──────────────
        try:
            positions = await self.bybit.fetch_positions()
        except Exception:
            logger.debug("Failed to fetch Bybit positions for reconciliation")
            return

        # Build map: symbol → {side, amount, entry_price}
        # Skip dust positions (near-zero residuals after close)
        exchange_positions: dict[str, dict[str, Any]] = {}
        for pos in positions:
            contracts = float(pos.get("contracts", 0) or 0)
            if abs(contracts) < 1e-8:
                continue
            symbol = pos.get("symbol", "")
            side = "long" if contracts > 0 else "short"
            entry_px = float(pos.get("entryPrice", 0) or 0)
            notional = abs(contracts) * entry_px if entry_px > 0 else 0
            if entry_px <= 0 or notional < 1.0:
                logger.debug("Skipping dust position %s: %.8f coins worth $%.4f", symbol, abs(contracts), notional)
                self._position_first_seen.pop(f"bybit:{symbol}", None)
                self._orphan_fail_count.pop(f"bybit:{symbol}", None)
                self._orphan_gave_up.discard(f"bybit:{symbol}")
                continue
            exchange_positions[symbol] = {
                "side": side,
                "amount": abs(contracts),
                "entry_price": entry_px,
            }

        # ── Step 2: Check ALL exchange positions against bot state ────
        all_checked_pairs = set(self.bybit_pairs) | set(exchange_positions.keys())

        for pair in all_checked_pairs:
            epos = exchange_positions.get(pair)
            scalp = self._get_scalp(pair, exchange="bybit")

            # Clean up orphan tracking for pairs no longer on exchange
            if not epos:
                fs_key = f"bybit:{pair}"
                self._position_first_seen.pop(fs_key, None)
                self._orphan_fail_count.pop(fs_key, None)
                self._orphan_gave_up.discard(fs_key)

            # ── EXIT-PENDING GUARD: strategy is mid-exit, position will close shortly ──
            if epos and scalp and getattr(scalp, '_pending_exit_restore', None):
                self._position_first_seen.pop(f"bybit:{pair}", None)
                self._orphan_fail_count.pop(f"bybit:{pair}", None)
                self._orphan_gave_up.discard(f"bybit:{pair}")
                logger.debug("EXIT_PENDING: %s has pending exit restore — skipping orphan check", pair)
                continue

            if epos and scalp and scalp.in_position:
                self._position_first_seen.pop(f"bybit:{pair}", None)
                self._orphan_fail_count.pop(f"bybit:{pair}", None)
                self._orphan_gave_up.discard(f"bybit:{pair}")

                # ── SAFETY: ensure DB also has this trade ──────────────
                try:
                    if self.db.is_connected:
                        db_trade = await self.db.get_open_trade(pair=pair, exchange="bybit")
                        if not db_trade:
                            side = epos["side"]
                            amount = epos["amount"]
                            entry_px = epos["entry_price"]
                            s_entry = getattr(scalp, "entry_price", 0) or 0
                            fill_price = s_entry if s_entry > 0 else entry_px
                            lev = getattr(scalp, "_leverage", config.bybit.leverage) or 20
                            notional = fill_price * amount
                            cost = notional / lev if lev > 1 else notional
                            position_type = scalp.position_side or side

                            trade_id = await self.db.log_trade({
                                "pair": pair,
                                "side": "buy" if position_type == "long" else "sell",
                                "entry_price": fill_price,
                                "amount": amount,
                                "contracts": amount,
                                "cost": cost,
                                "collateral": round(notional / lev, 8) if lev > 1 else round(notional, 8),
                                "strategy": "scalp",
                                "order_type": "market",
                                "exchange": "bybit",
                                "status": "open",
                                "reason": "BACKFILL (DB insert missed)",
                                "leverage": lev,
                                "position_type": position_type,
                                "setup_type": "backfill",
                            })
                            logger.warning(
                                "DB BACKFILL: inserted missing trade for %s %s (id=%s)",
                                pair, position_type, trade_id,
                            )
                except Exception:
                    logger.debug("DB backfill check failed for %s (bybit)", pair)

                continue  # ALL GOOD

            if epos and (not scalp or not scalp.in_position):
                side = epos["side"]
                amount = epos["amount"]
                entry_px = epos["entry_price"]

                # ── CASE 3: Try to RESTORE from DB before closing ────
                restored = False
                if scalp and self.db.is_connected:
                    open_trade = await self.db.get_open_trade(
                        pair=pair, exchange="bybit",
                    )
                    if open_trade and open_trade.get("status") == "open":
                        db_entry_price = float(open_trade.get("entry_price", 0) or 0)
                        restore_price = db_entry_price if db_entry_price > 0 else entry_px

                        # ── SIDE MISMATCH FIX: exchange is truth ──
                        db_side = open_trade.get("position_type", "")
                        if db_side and db_side != side:
                            logger.warning(
                                "SIDE MISMATCH: %s — DB says %s, exchange says %s. "
                                "Updating DB to match exchange.",
                                pair, db_side.upper(), side.upper(),
                            )
                            trade_id_db = open_trade.get("id")
                            if trade_id_db:
                                try:
                                    new_order_side = "buy" if side == "long" else "sell"
                                    await self.db.update_trade(trade_id_db, {
                                        "position_type": side,
                                        "side": new_order_side,
                                    })
                                except Exception as e:
                                    logger.warning("Failed to fix side mismatch in DB for %s: %s", pair, e)

                        scalp.in_position = True
                        scalp.position_side = side
                        scalp.entry_price = restore_price
                        scalp.entry_amount = amount
                        scalp.highest_since_entry = restore_price
                        scalp.lowest_since_entry = restore_price

                        opened_at_str = open_trade.get("opened_at")
                        if opened_at_str:
                            try:
                                from datetime import datetime, timezone
                                if isinstance(opened_at_str, str):
                                    opened_at_str = opened_at_str.replace("Z", "+00:00")
                                    opened_dt = datetime.fromisoformat(opened_at_str)
                                else:
                                    opened_dt = opened_at_str
                                seconds_ago = max(0, (datetime.now(timezone.utc) - opened_dt).total_seconds())
                                scalp.entry_time = time.monotonic() - seconds_ago
                            except Exception:
                                scalp.entry_time = time.monotonic()
                        else:
                            scalp.entry_time = time.monotonic()

                        # Set phantom cooldown — protect restored position from phantom detection
                        scalp._phantom_cooldown_until = time.monotonic() + 120

                        current_price = await self._get_current_price(pair, "bybit")
                        if current_price and current_price > 0:
                            current_pnl = scalp._calc_pnl_pct(current_price)
                            if side == "long":
                                scalp.highest_since_entry = max(restore_price, current_price)
                            else:
                                scalp.lowest_since_entry = min(restore_price, current_price)
                            scalp._peak_unrealized_pnl = max(0, current_pnl)
                            if current_pnl >= scalp.TRAILING_ACTIVATE_PCT:
                                scalp._trailing_active = True
                                scalp._update_trail_stop()
                                logger.info(
                                    "RESTORE: %s already at +%.2f%% — trailing activated",
                                    pair, current_pnl,
                                )
                        else:
                            current_price = entry_px
                            current_pnl = 0.0

                        logger.warning(
                            "RESTORED: %s %s %.6f coins @ $%.2f (DB) — "
                            "current $%.2f — PnL %+.2f%%",
                            pair, side, amount, restore_price,
                            current_price, current_pnl,
                        )
                        try:
                            await self.alerts.send_orphan_alert(
                                pair=pair, side=side, contracts=amount,
                                action="RESTORED INTO BOT",
                                detail=f"Entry: ${restore_price:.2f} (DB) — current ${current_price:.2f} — PnL {current_pnl:+.2f}%",
                            )
                        except Exception:
                            pass
                        restored = True

                if not restored:
                    fs_key = f"bybit:{pair}"

                    # ── Already gave up on this position? Silent skip ──
                    if fs_key in self._orphan_gave_up:
                        continue

                    # ── Grace period: don't close newly-detected positions ──
                    if fs_key not in self._position_first_seen:
                        self._position_first_seen[fs_key] = time.monotonic()
                    age = time.monotonic() - self._position_first_seen[fs_key]
                    if age < self.ORPHAN_GRACE_S:
                        logger.info(
                            "ORPHAN_GRACE: skipping %s (age %.0fs < %ds)",
                            pair, age, self.ORPHAN_GRACE_S,
                        )
                        continue

                    # ── CASE 1: True ORPHAN — close it ─────────────────
                    fail_count = self._orphan_fail_count.get(fs_key, 0)
                    logger.warning(
                        "ORPHAN DETECTED: %s %s %.6f coins @ $%.2f — "
                        "NOT in bot memory! CLOSING (attempt %d/%d)",
                        pair, side, amount, entry_px,
                        fail_count + 1, self.ORPHAN_MAX_RETRIES,
                    )
                    try:
                        await self.alerts.send_orphan_alert(
                            pair=pair, side=side, contracts=amount,
                            action="CLOSING AT MARKET",
                            detail=f"Entry: ${entry_px:.2f} — not in bot memory or DB (attempt {fail_count + 1}/{self.ORPHAN_MAX_RETRIES})",
                        )
                    except Exception:
                        pass

                    try:
                        close_side = "sell" if side == "long" else "buy"
                        await self.bybit.create_order(
                            pair, "market", close_side, amount,
                            params={"reduceOnly": True},
                        )
                        logger.info(
                            "ORPHAN CLOSED: %s %s %.6f coins at market",
                            pair, side, amount,
                        )

                        self._position_first_seen.pop(fs_key, None)
                        self._orphan_fail_count.pop(fs_key, None)
                        self._orphan_gave_up.discard(fs_key)

                        if self.db.is_connected:
                            open_trade = await self.db.get_open_trade(
                                pair=pair, exchange="bybit",
                            )
                            if open_trade:
                                try:
                                    ticker = await self.bybit.fetch_ticker(pair)
                                    exit_price = float(ticker.get("last", 0) or 0) or entry_px
                                except Exception:
                                    exit_price = entry_px
                                trade_lev = open_trade.get("leverage", config.bybit.leverage) or 1
                                _r = calc_pnl(
                                    entry_px, exit_price, amount,
                                    side, trade_lev,
                                    "bybit", pair,
                                    entry_fee_rate=config.bybit.taker_fee,
                                    exit_fee_rate=config.bybit.taker_fee,
                                )
                                pnl, pnl_pct = _r.net_pnl, _r.pnl_pct
                                order_id = open_trade.get("order_id", "")
                                if order_id:
                                    await self.db.close_trade(
                                        order_id, exit_price, pnl, pnl_pct,
                                        reason="orphan_closed",
                                        exit_reason="ORPHAN",
                                        gross_pnl=_r.gross_pnl,
                                        entry_fee=_r.entry_fee,
                                        exit_fee=_r.exit_fee,
                                    )
                                    logger.info("Orphan DB trade %s closed: P&L=%.2f%%", pair, pnl_pct)

                    except Exception:
                        fail_count += 1
                        self._orphan_fail_count[fs_key] = fail_count

                        if fail_count >= self.ORPHAN_MAX_RETRIES:
                            self._orphan_gave_up.add(fs_key)
                            self._position_first_seen.pop(fs_key, None)
                            logger.error(
                                "ORPHAN GAVE UP: %s failed %d times — silencing alerts. CLOSE MANUALLY!",
                                pair, fail_count,
                            )
                            try:
                                await self.alerts.send_orphan_alert(
                                    pair=pair, side=side, contracts=amount,
                                    action=f"GIVING UP after {fail_count} failures",
                                    detail=f"Auto-close failed {fail_count}x. Close {pair} manually on Bybit! No more alerts for this position.",
                                )
                            except Exception:
                                pass
                        else:
                            logger.exception(
                                "Failed to close orphan %s (attempt %d/%d) — will retry",
                                pair, fail_count, self.ORPHAN_MAX_RETRIES,
                            )
                            try:
                                await self.alerts.send_orphan_alert(
                                    pair=pair, side=side, contracts=amount,
                                    action=f"CLOSE FAILED (attempt {fail_count}/{self.ORPHAN_MAX_RETRIES})",
                                    detail=f"Auto-close failed. Will retry {self.ORPHAN_MAX_RETRIES - fail_count} more time(s).",
                                )
                            except Exception:
                                pass

        # ── Step 3: Check for PHANTOM positions (bot has, exchange doesn't) ──
        now = time.monotonic()
        for _key, scalp in self._scalp_strategies.items():
            if not scalp.in_position or not scalp.is_futures:
                continue
            if getattr(scalp, "_exchange_id", "delta") != "bybit":
                continue  # skip non-Bybit strategies
            # Phantom cooldown: skip detection during cooldown (prevents RESTORE→PHANTOM cycle)
            if now < getattr(scalp, '_phantom_cooldown_until', 0):
                logger.debug("PHANTOM COOLDOWN: %s — %.0fs remaining", scalp.pair,
                             getattr(scalp, '_phantom_cooldown_until', 0) - now)
                continue
            epos = exchange_positions.get(scalp.pair)
            if not epos:
                if scalp.entry_time > 0:
                    hold_seconds = now - scalp.entry_time
                    if hold_seconds < 300:
                        logger.debug(
                            "PHANTOM SKIP: %s — opened %.0fs ago (< 5min)", scalp.pair, hold_seconds,
                        )
                        continue
                if scalp._last_position_exit > 0:
                    since_exit = now - scalp._last_position_exit
                    if since_exit < 30:
                        logger.debug(
                            "PHANTOM SKIP: %s — trade closed %.0fs ago (< 30s)", scalp.pair, since_exit,
                        )
                        continue

                logger.warning(
                    "PHANTOM DETECTED: %s — bot thinks %s @ $%.2f "
                    "but Bybit has NO position! Clearing.",
                    scalp.pair, scalp.position_side, scalp.entry_price,
                )
                # Cancel any stale open orders for this pair (unfilled limit entries)
                try:
                    await self.bybit.cancel_all_orders(scalp.pair)
                    logger.info("PHANTOM: cancelled all open orders for %s on Bybit", scalp.pair)
                except Exception as e:
                    logger.debug("Cancel orders for %s on Bybit: %s", scalp.pair, e)

                try:
                    await self.alerts.send_orphan_alert(
                        pair=scalp.pair,
                        side=scalp.position_side or "unknown",
                        contracts=scalp.entry_amount,
                        action="PHANTOM CLEARED",
                        detail=f"Bot thought {scalp.position_side} @ ${scalp.entry_price:.2f} but Bybit has nothing",
                    )
                except Exception:
                    pass

                scalp.in_position = False
                scalp.position_side = None
                scalp.entry_price = 0.0
                scalp.entry_amount = 0.0
                scalp._last_position_exit = now
                scalp._phantom_cooldown_until = now + 60
                ScalpStrategy._live_pnl.pop(scalp.pair, None)

                phantom_pnl_for_rm = 0.0
                if self.db.is_connected:
                    open_trade = await self.db.get_open_trade(
                        pair=scalp.pair, exchange="bybit", strategy="scalp",
                    )
                    if open_trade:
                        order_id = open_trade.get("order_id", "")
                        entry_px = float(open_trade.get("entry_price", 0) or 0)
                        trade_lev = open_trade.get("leverage", config.bybit.leverage) or 1
                        pos_type = open_trade.get("position_type", "long")
                        phantom_amount = open_trade.get("amount", 0)
                        phantom_exit = entry_px
                        phantom_reason = "phantom_cleared"

                        try:
                            recent_trades = await self.bybit.fetch_my_trades(scalp.pair, limit=20)
                            if recent_trades:
                                close_side = "sell" if pos_type == "long" else "buy"
                                closing_fills = [
                                    t for t in recent_trades if t.get("side") == close_side
                                ]
                                if closing_fills:
                                    last_fill = closing_fills[-1]
                                    fill_price = float(last_fill.get("price", 0) or 0)
                                    if fill_price > 0:
                                        phantom_exit = fill_price
                                        phantom_reason = "CLOSED_BY_EXCHANGE"
                        except Exception as e:
                            logger.debug("Could not fetch trade history for %s: %s", scalp.pair, e)

                        if phantom_exit == entry_px:
                            try:
                                ticker = await self.bybit.fetch_ticker(scalp.pair)
                                phantom_exit = float(ticker.get("last", 0) or 0) or entry_px
                            except Exception:
                                pass

                        # ── SAFETY: never close with $0 exit ──
                        if phantom_exit <= 0:
                            logger.error("Bybit phantom %s: exit=$0, skipping close", scalp.pair)
                            continue

                        _r = calc_pnl(
                            entry_px, phantom_exit, phantom_amount,
                            pos_type, trade_lev, "bybit", scalp.pair,
                            entry_fee_rate=config.bybit.taker_fee,
                            exit_fee_rate=config.bybit.taker_fee,
                        )
                        phantom_pnl, phantom_pnl_pct = _r.net_pnl, _r.pnl_pct
                        phantom_pnl_for_rm = phantom_pnl
                        _bybit_exit_map = {
                            "CLOSED_BY_EXCHANGE": "CLOSED_BY_EXCHANGE",
                        }
                        phantom_exit_reason = _bybit_exit_map.get(phantom_reason, "PHANTOM")
                        if order_id:
                            await self.db.close_trade(
                                order_id, phantom_exit, phantom_pnl, phantom_pnl_pct,
                                reason="phantom_cleared",
                                exit_reason=phantom_exit_reason,
                                gross_pnl=_r.gross_pnl,
                                entry_fee=_r.entry_fee,
                                exit_fee=_r.exit_fee,
                            )
                        logger.info(
                            "Phantom trade %s closed: exit=$%.2f pnl=$%.4f (%.2f%%)",
                            scalp.pair, phantom_exit, phantom_pnl, phantom_pnl_pct,
                        )

                self.risk_manager.record_close(scalp.pair, phantom_pnl_for_rm)

    async def _reconcile_kraken_positions(self) -> None:
        """DISABLED — Kraken not used (Delta options only mode)."""
        return  # noqa: Kraken disabled
        """Reconcile Kraken positions with bot memory.

        Same pattern as Bybit reconciliation:
        - Kraken amounts are in coins (no contract conversion)

        CASE 1 (ORPHAN): Exchange has position, bot doesn't → CLOSE immediately
        CASE 2 (PHANTOM): Bot thinks position exists, exchange doesn't → clear state
        CASE 3 (RESTORE): Exchange has position, DB has trade → restore strategy
        """
        if not self.kraken:
            return

        # ── Step 1: Fetch ALL open positions from Kraken ──────────────
        try:
            positions = await self.kraken.fetch_positions()
        except Exception:
            logger.debug("Failed to fetch Kraken positions for reconciliation")
            return

        # Build map: symbol → {side, amount, entry_price}
        # Skip dust/ghost positions (near-zero residuals after close)
        exchange_positions: dict[str, dict[str, Any]] = {}
        for pos in positions:
            contracts = float(pos.get("contracts", 0) or 0)
            if abs(contracts) < 1e-8:
                continue
            symbol = pos.get("symbol", "")
            side = "long" if contracts > 0 else "short"
            entry_px = float(pos.get("entryPrice", 0) or 0)
            notional = abs(contracts) * entry_px if entry_px > 0 else 0
            min_order = self.KRAKEN_MIN_ORDER.get(symbol, 0.01)
            # Skip dust/ghost: no entry price, notional < $1, or below exchange minimum order
            if entry_px <= 0 or notional < 1.0 or abs(contracts) < min_order:
                logger.debug(
                    "Skipping dust/ghost position %s: %.8f coins @ $%.2f worth $%.4f",
                    symbol, abs(contracts), entry_px, notional,
                )
                # Clear any orphan tracking for this dust position
                self._position_first_seen.pop(f"kraken:{symbol}", None)
                self._orphan_fail_count.pop(f"kraken:{symbol}", None)
                self._orphan_gave_up.discard(f"kraken:{symbol}")
                continue
            exchange_positions[symbol] = {
                "side": side,
                "amount": abs(contracts),
                "entry_price": entry_px,
            }

        # ── Step 2: Check ALL exchange positions against bot state ────
        all_checked_pairs = set(self.kraken_pairs) | set(exchange_positions.keys())

        for pair in all_checked_pairs:
            epos = exchange_positions.get(pair)
            scalp = self._get_scalp(pair, exchange="kraken")

            # Clean up orphan tracking for pairs no longer on exchange
            if not epos:
                fs_key = f"kraken:{pair}"
                self._position_first_seen.pop(fs_key, None)
                self._orphan_fail_count.pop(fs_key, None)
                self._orphan_gave_up.discard(fs_key)

            # ── EXIT-PENDING GUARD: strategy is mid-exit, position will close shortly ──
            # _pending_exit_restore means _record_scalp_result already cleared in_position
            # but the exit order is still in-flight. Don't flag as orphan.
            if epos and scalp and getattr(scalp, '_pending_exit_restore', None):
                self._position_first_seen.pop(f"kraken:{pair}", None)
                self._orphan_fail_count.pop(f"kraken:{pair}", None)
                self._orphan_gave_up.discard(f"kraken:{pair}")
                logger.debug(
                    "EXIT_PENDING: %s has pending exit restore — skipping orphan check",
                    pair,
                )
                continue

            if epos and scalp and scalp.in_position:
                self._position_first_seen.pop(f"kraken:{pair}", None)
                self._orphan_fail_count.pop(f"kraken:{pair}", None)
                self._orphan_gave_up.discard(f"kraken:{pair}")

                # ── SAFETY: ensure DB also has this trade ──────────────
                try:
                    if self.db.is_connected:
                        db_trade = await self.db.get_open_trade(pair=pair, exchange="kraken")
                        if not db_trade:
                            side = epos["side"]
                            amount = epos["amount"]
                            entry_px = epos["entry_price"]
                            s_entry = getattr(scalp, "entry_price", 0) or 0
                            fill_price = s_entry if s_entry > 0 else entry_px
                            lev = getattr(scalp, "_leverage", config.kraken.leverage) or 20
                            notional = fill_price * amount
                            cost = notional / lev if lev > 1 else notional
                            position_type = scalp.position_side or side

                            trade_id = await self.db.log_trade({
                                "pair": pair,
                                "side": "buy" if position_type == "long" else "sell",
                                "entry_price": fill_price,
                                "amount": amount,
                                "contracts": amount,
                                "cost": cost,
                                "collateral": round(notional / lev, 8) if lev > 1 else round(notional, 8),
                                "strategy": "scalp",
                                "order_type": "market",
                                "exchange": "kraken",
                                "status": "open",
                                "reason": "BACKFILL (DB insert missed)",
                                "leverage": lev,
                                "position_type": position_type,
                                "setup_type": "backfill",
                            })
                            logger.warning(
                                "DB BACKFILL: inserted missing trade for %s %s (id=%s)",
                                pair, position_type, trade_id,
                            )
                except Exception:
                    logger.debug("DB backfill check failed for %s (kraken)", pair)

                continue  # ALL GOOD

            if epos and (not scalp or not scalp.in_position):
                side = epos["side"]
                amount = epos["amount"]
                entry_px = epos["entry_price"]

                # ── CASE 3: Try to RESTORE from DB before closing ────
                restored = False
                if scalp and self.db.is_connected:
                    open_trade = await self.db.get_open_trade(
                        pair=pair, exchange="kraken",
                    )
                    if open_trade and open_trade.get("status") == "open":
                        db_entry_price = float(open_trade.get("entry_price", 0) or 0)
                        restore_price = db_entry_price if db_entry_price > 0 else entry_px

                        # ── SIDE MISMATCH FIX: exchange is truth ──
                        # If DB says LONG but exchange has SHORT (or vice versa),
                        # update DB to match exchange — exchange is the source of truth.
                        db_side = open_trade.get("position_type", "")
                        if db_side and db_side != side:
                            logger.warning(
                                "SIDE MISMATCH: %s — DB says %s, exchange says %s. "
                                "Updating DB to match exchange.",
                                pair, db_side.upper(), side.upper(),
                            )
                            trade_id = open_trade.get("id")
                            if trade_id:
                                try:
                                    new_order_side = "buy" if side == "long" else "sell"
                                    await self.db.update_trade(trade_id, {
                                        "position_type": side,
                                        "side": new_order_side,
                                    })
                                except Exception as e:
                                    logger.warning("Failed to fix side mismatch in DB for %s: %s", pair, e)

                        scalp.in_position = True
                        scalp.position_side = side
                        scalp.entry_price = restore_price
                        scalp.entry_amount = amount
                        scalp.highest_since_entry = restore_price
                        scalp.lowest_since_entry = restore_price

                        opened_at_str = open_trade.get("opened_at")
                        if opened_at_str:
                            try:
                                from datetime import datetime, timezone
                                if isinstance(opened_at_str, str):
                                    opened_at_str = opened_at_str.replace("Z", "+00:00")
                                    opened_dt = datetime.fromisoformat(opened_at_str)
                                else:
                                    opened_dt = opened_at_str
                                seconds_ago = max(0, (datetime.now(timezone.utc) - opened_dt).total_seconds())
                                scalp.entry_time = time.monotonic() - seconds_ago
                            except Exception:
                                scalp.entry_time = time.monotonic()
                        else:
                            scalp.entry_time = time.monotonic()

                        # Set phantom cooldown — protect restored position from phantom detection
                        scalp._phantom_cooldown_until = time.monotonic() + 120

                        current_price = await self._get_current_price(pair, "kraken")
                        if current_price and current_price > 0:
                            current_pnl = scalp._calc_pnl_pct(current_price)
                            if side == "long":
                                scalp.highest_since_entry = max(restore_price, current_price)
                            else:
                                scalp.lowest_since_entry = min(restore_price, current_price)
                            scalp._peak_unrealized_pnl = max(0, current_pnl)
                            if current_pnl >= scalp.TRAILING_ACTIVATE_PCT:
                                scalp._trailing_active = True
                                scalp._update_trail_stop()
                                logger.info(
                                    "RESTORE: %s already at +%.2f%% — trailing activated",
                                    pair, current_pnl,
                                )
                        else:
                            current_price = entry_px
                            current_pnl = 0.0

                        logger.warning(
                            "RESTORED: %s %s %.6f coins @ $%.2f (DB) — "
                            "current $%.2f — PnL %+.2f%%",
                            pair, side, amount, restore_price,
                            current_price, current_pnl,
                        )
                        try:
                            await self.alerts.send_orphan_alert(
                                pair=pair, side=side, contracts=amount,
                                action="RESTORED INTO BOT",
                                detail=f"Entry: ${restore_price:.2f} (DB) — current ${current_price:.2f} — PnL {current_pnl:+.2f}%",
                            )
                        except Exception:
                            pass
                        restored = True

                if not restored:
                    fs_key = f"kraken:{pair}"

                    # ── Already gave up on this position? Silent skip ──
                    if fs_key in self._orphan_gave_up:
                        continue

                    # ── Grace period: don't close newly-detected positions ──
                    if fs_key not in self._position_first_seen:
                        self._position_first_seen[fs_key] = time.monotonic()
                    age = time.monotonic() - self._position_first_seen[fs_key]
                    if age < self.ORPHAN_GRACE_S:
                        logger.info(
                            "ORPHAN_GRACE: skipping %s (age %.0fs < %ds)",
                            pair, age, self.ORPHAN_GRACE_S,
                        )
                        continue

                    # ── CASE 1: True ORPHAN — close it ─────────────────
                    fail_count = self._orphan_fail_count.get(fs_key, 0)
                    logger.warning(
                        "ORPHAN DETECTED: %s %s %.6f coins @ $%.2f — "
                        "NOT in bot memory! CLOSING (attempt %d/%d)",
                        pair, side, amount, entry_px,
                        fail_count + 1, self.ORPHAN_MAX_RETRIES,
                    )
                    try:
                        await self.alerts.send_orphan_alert(
                            pair=pair, side=side, contracts=amount,
                            action="CLOSING AT MARKET",
                            detail=f"Entry: ${entry_px:.2f} — not in bot memory or DB (attempt {fail_count + 1}/{self.ORPHAN_MAX_RETRIES})",
                        )
                    except Exception:
                        pass

                    try:
                        close_side = "sell" if side == "long" else "buy"
                        # Kraken: try with reduceOnly first, fall back to plain market
                        try:
                            await self.kraken.create_order(
                                pair, "market", close_side, amount,
                                params={"reduceOnly": True},
                            )
                        except Exception as e1:
                            logger.warning(
                                "Kraken reduceOnly close failed for %s: %s — retrying plain market",
                                pair, e1,
                            )
                            await self.kraken.create_order(
                                pair, "market", close_side, amount,
                            )
                        logger.info(
                            "ORPHAN CLOSED: %s %s %.6f coins at market",
                            pair, side, amount,
                        )

                        # ── Success: clean up all tracking ────────────
                        self._position_first_seen.pop(fs_key, None)
                        self._orphan_fail_count.pop(fs_key, None)
                        self._orphan_gave_up.discard(fs_key)

                        if self.db.is_connected:
                            open_trade = await self.db.get_open_trade(
                                pair=pair, exchange="kraken",
                            )
                            if open_trade:
                                try:
                                    ticker = await self.kraken.fetch_ticker(pair)
                                    exit_price = float(ticker.get("last", 0) or 0) or entry_px
                                except Exception:
                                    exit_price = entry_px
                                trade_lev = open_trade.get("leverage", config.kraken.leverage) or 1
                                _r = calc_pnl(
                                    entry_px, exit_price, amount,
                                    side, trade_lev,
                                    "kraken", pair,
                                    entry_fee_rate=config.kraken.taker_fee,
                                    exit_fee_rate=config.kraken.taker_fee,
                                )
                                pnl, pnl_pct = _r.net_pnl, _r.pnl_pct
                                order_id = open_trade.get("order_id", "")
                                if order_id:
                                    await self.db.close_trade(
                                        order_id, exit_price, pnl, pnl_pct,
                                        reason="orphan_closed",
                                        exit_reason="ORPHAN",
                                        gross_pnl=_r.gross_pnl,
                                        entry_fee=_r.entry_fee,
                                        exit_fee=_r.exit_fee,
                                    )
                                    logger.info("Orphan DB trade %s closed: P&L=%.2f%%", pair, pnl_pct)

                    except Exception as close_err:
                        # ── Failed: increment retry counter ───────────
                        fail_count += 1
                        self._orphan_fail_count[fs_key] = fail_count
                        logger.error(
                            "ORPHAN CLOSE ERROR %s (attempt %d/%d): %s",
                            pair, fail_count, self.ORPHAN_MAX_RETRIES, close_err,
                        )

                        if fail_count >= self.ORPHAN_MAX_RETRIES:
                            # Give up — no more retries, no more alerts
                            self._orphan_gave_up.add(fs_key)
                            self._position_first_seen.pop(fs_key, None)
                            logger.error(
                                "ORPHAN GAVE UP: %s failed %d times — "
                                "silencing alerts. CLOSE MANUALLY!",
                                pair, fail_count,
                            )
                            try:
                                await self.alerts.send_orphan_alert(
                                    pair=pair, side=side, contracts=amount,
                                    action=f"GIVING UP after {fail_count} failures",
                                    detail=f"Auto-close failed {fail_count}x. Close {pair} manually on Kraken! No more alerts for this position.",
                                )
                            except Exception:
                                pass
                        else:
                            logger.exception(
                                "Failed to close orphan %s (attempt %d/%d) — will retry",
                                pair, fail_count, self.ORPHAN_MAX_RETRIES,
                            )
                            try:
                                await self.alerts.send_orphan_alert(
                                    pair=pair, side=side, contracts=amount,
                                    action=f"CLOSE FAILED (attempt {fail_count}/{self.ORPHAN_MAX_RETRIES})",
                                    detail=f"Auto-close failed. Will retry {self.ORPHAN_MAX_RETRIES - fail_count} more time(s).",
                                )
                            except Exception:
                                pass

        # ── Step 3: Check for PHANTOM positions (bot has, exchange doesn't) ──
        now = time.monotonic()
        for _key, scalp in self._scalp_strategies.items():
            if not scalp.in_position or not scalp.is_futures:
                continue
            if getattr(scalp, "_exchange_id", "delta") != "kraken":
                continue  # skip non-Kraken strategies
            # Phantom cooldown: skip detection during cooldown (prevents RESTORE→PHANTOM cycle)
            if now < getattr(scalp, '_phantom_cooldown_until', 0):
                logger.debug("PHANTOM COOLDOWN: %s — %.0fs remaining", scalp.pair,
                             getattr(scalp, '_phantom_cooldown_until', 0) - now)
                continue
            epos = exchange_positions.get(scalp.pair)
            if not epos:
                if scalp.entry_time > 0:
                    hold_seconds = now - scalp.entry_time
                    if hold_seconds < 300:
                        logger.debug(
                            "PHANTOM SKIP: %s — opened %.0fs ago (< 5min)", scalp.pair, hold_seconds,
                        )
                        continue
                if scalp._last_position_exit > 0:
                    since_exit = now - scalp._last_position_exit
                    if since_exit < 30:
                        logger.debug(
                            "PHANTOM SKIP: %s — trade closed %.0fs ago (< 30s)", scalp.pair, since_exit,
                        )
                        continue

                logger.warning(
                    "PHANTOM DETECTED: %s — bot thinks %s @ $%.2f "
                    "but Kraken has NO position! Clearing.",
                    scalp.pair, scalp.position_side, scalp.entry_price,
                )
                # Cancel any stale open orders for this pair (unfilled limit entries)
                try:
                    await self.kraken.cancel_all_orders(scalp.pair)
                    logger.info("PHANTOM: cancelled all open orders for %s on Kraken", scalp.pair)
                except Exception as e:
                    logger.debug("Cancel orders for %s on Kraken: %s", scalp.pair, e)

                try:
                    await self.alerts.send_orphan_alert(
                        pair=scalp.pair,
                        side=scalp.position_side or "unknown",
                        contracts=scalp.entry_amount,
                        action="PHANTOM CLEARED",
                        detail=f"Bot thought {scalp.position_side} @ ${scalp.entry_price:.2f} but Kraken has nothing",
                    )
                except Exception:
                    pass

                scalp.in_position = False
                scalp.position_side = None
                scalp.entry_price = 0.0
                scalp.entry_amount = 0.0
                scalp._last_position_exit = now
                scalp._phantom_cooldown_until = now + 60
                ScalpStrategy._live_pnl.pop(scalp.pair, None)

                phantom_pnl_for_rm = 0.0
                if self.db.is_connected:
                    open_trade = await self.db.get_open_trade(
                        pair=scalp.pair, exchange="kraken", strategy="scalp",
                    )
                    if open_trade:
                        order_id = open_trade.get("order_id", "")
                        entry_px = float(open_trade.get("entry_price", 0) or 0)
                        trade_lev = open_trade.get("leverage", config.kraken.leverage) or 1
                        pos_type = open_trade.get("position_type", "long")
                        phantom_amount = open_trade.get("amount", 0)
                        phantom_exit = entry_px
                        try:
                            recent_trades = await self.kraken.fetch_my_trades(scalp.pair, limit=20)
                            if recent_trades:
                                close_side = "sell" if pos_type == "long" else "buy"
                                closing_fills = [
                                    t for t in recent_trades if t.get("side") == close_side
                                ]
                                if closing_fills:
                                    last_fill = closing_fills[-1]
                                    fill_price = float(last_fill.get("price", 0) or 0)
                                    if fill_price > 0:
                                        phantom_exit = fill_price
                        except Exception as e:
                            logger.debug("Could not fetch trade history for %s: %s", scalp.pair, e)

                        if phantom_exit == entry_px:
                            try:
                                ticker = await self.kraken.fetch_ticker(scalp.pair)
                                phantom_exit = float(ticker.get("last", 0) or 0) or entry_px
                            except Exception:
                                pass

                        # ── SAFETY: never close with $0 exit ──
                        if phantom_exit <= 0:
                            logger.error("Kraken phantom %s: exit=$0, skipping close", scalp.pair)
                            continue

                        _r = calc_pnl(
                            entry_px, phantom_exit, phantom_amount,
                            pos_type, trade_lev, "kraken", scalp.pair,
                            entry_fee_rate=config.kraken.taker_fee,
                            exit_fee_rate=config.kraken.taker_fee,
                        )
                        phantom_pnl, phantom_pnl_pct = _r.net_pnl, _r.pnl_pct
                        phantom_pnl_for_rm = phantom_pnl
                        if order_id:
                            await self.db.close_trade(
                                order_id, phantom_exit, phantom_pnl, phantom_pnl_pct,
                                reason="phantom_cleared",
                                exit_reason="PHANTOM",
                                gross_pnl=_r.gross_pnl,
                                entry_fee=_r.entry_fee,
                                exit_fee=_r.exit_fee,
                            )
                        logger.info(
                            "Phantom trade %s closed: exit=$%.2f pnl=$%.4f (%.2f%%)",
                            scalp.pair, phantom_exit, phantom_pnl, phantom_pnl_pct,
                        )

                self.risk_manager.record_close(scalp.pair, phantom_pnl_for_rm)

    async def _reconcile_delta_positions(self) -> None:
        """Reconcile Delta Exchange positions with bot memory.

        Runs on startup AND every 60 seconds. Three cases:

        CASE 1 (ORPHAN): Exchange has position, bot doesn't → CLOSE immediately
        CASE 2 (PHANTOM): Bot thinks position exists, exchange doesn't → clear state
        CASE 3 (RESTORE): Exchange has position, bot doesn't but DB does → restore strategy

        This is independent of price updates, strategy state, or anything else.
        Pure exchange truth vs bot memory comparison.
        """
        if not self.delta:
            return

        # ── Step 1: Fetch ALL open positions from Delta exchange ────────
        try:
            positions = await self.delta.fetch_positions()
        except Exception:
            logger.debug("Failed to fetch Delta positions for reconciliation")
            return

        # Build map: symbol → {side, contracts, entry_price}
        # Skip dust positions (near-zero residuals after close)
        exchange_positions: dict[str, dict[str, Any]] = {}
        for pos in positions:
            contracts = float(pos.get("contracts", 0) or 0)
            if abs(contracts) < 1e-8:
                continue
            symbol = pos.get("symbol", "")
            side = "long" if contracts > 0 else "short"
            entry_px = float(pos.get("entryPrice", 0) or 0)
            # Delta uses contract sizes, compute notional for dust check
            contract_size = DELTA_CONTRACT_SIZE.get(symbol, 1.0)
            # Also try ccxt symbol for contract size lookup
            native = symbol.replace("/", "").replace(":USD", "")
            for ccxt_p, cs in DELTA_CONTRACT_SIZE.items():
                if ccxt_p.replace("/", "").replace(":USD", "") == native:
                    contract_size = cs
                    break
            notional = abs(contracts) * contract_size * entry_px if entry_px > 0 else 0
            if entry_px <= 0 or notional < 1.0:
                logger.debug("Skipping dust position %s: %.0f ct worth $%.4f", symbol, abs(contracts), notional)
                self._position_first_seen.pop(f"delta:{symbol}", None)
                self._orphan_fail_count.pop(f"delta:{symbol}", None)
                self._orphan_gave_up.discard(f"delta:{symbol}")
                continue
            exchange_positions[symbol] = {
                "side": side,
                "contracts": abs(contracts),
                "entry_price": entry_px,
                "leverage": float(pos.get("leverage", 0) or 0),
            }

        # ── Step 1b: Normalize exchange symbols to ccxt unified format ──
        # Delta fetch_positions() may return native format (ETHUSD) or ccxt (ETH/USD:USD).
        # Build a lookup: native symbol → ccxt symbol for strategy matching.
        _native_to_ccxt: dict[str, str] = {}
        for ccxt_pair in self.delta_pairs:
            # BTC/USD:USD → BTCUSD
            native = ccxt_pair.replace("/", "").replace(":USD", "")
            _native_to_ccxt[native] = ccxt_pair
            _native_to_ccxt[ccxt_pair] = ccxt_pair  # identity

        def _resolve_pair(sym: str) -> str:
            """Resolve exchange symbol to ccxt pair format."""
            return _native_to_ccxt.get(sym, sym)

        # ── Step 2: Check ALL exchange positions against bot state ──────
        # Normalize all exchange position keys to ccxt format
        normalized_positions: dict[str, dict[str, Any]] = {}
        for sym, data in exchange_positions.items():
            resolved = _resolve_pair(sym)
            normalized_positions[resolved] = data

        all_checked_pairs = set(self.delta_pairs) | set(normalized_positions.keys())

        for pair in all_checked_pairs:
            # Skip options positions — managed by OptionsScalpStrategy
            if is_option_symbol(pair):
                logger.debug("Skipping options position in orphan check: %s", pair)
                continue

            epos = normalized_positions.get(pair)
            scalp = self._get_scalp(pair, exchange="delta")

            # Clean up orphan tracking for pairs no longer on exchange
            if not epos:
                fs_key = f"delta:{pair}"
                self._position_first_seen.pop(fs_key, None)
                self._orphan_fail_count.pop(fs_key, None)
                self._orphan_gave_up.discard(fs_key)

            # ── EXIT-PENDING GUARD: strategy is mid-exit, position will close shortly ──
            if epos and scalp and getattr(scalp, '_pending_exit_restore', None):
                self._position_first_seen.pop(f"delta:{pair}", None)
                self._orphan_fail_count.pop(f"delta:{pair}", None)
                self._orphan_gave_up.discard(f"delta:{pair}")
                logger.debug("EXIT_PENDING: %s has pending exit restore — skipping orphan check", pair)
                continue

            if epos and scalp and scalp.in_position:
                # ALL GOOD — exchange has it, bot is managing it
                self._position_first_seen.pop(f"delta:{pair}", None)
                self._orphan_fail_count.pop(f"delta:{pair}", None)
                self._orphan_gave_up.discard(f"delta:{pair}")

                # ── SAFETY: ensure DB also has this trade ──────────────
                # If _open_trade_in_db() failed silently, the dashboard
                # can't see the position. Detect and backfill here.
                try:
                    if self.db.is_connected:
                        db_trade = await self.db.get_open_trade(pair=pair, exchange="delta")
                        if not db_trade:
                            side = epos["side"]
                            contracts = epos["contracts"]
                            entry_px = epos["entry_price"]
                            # Use strategy entry_price if available (more accurate)
                            s_entry = getattr(scalp, "entry_price", 0) or 0
                            fill_price = s_entry if s_entry > 0 else entry_px
                            lev = getattr(scalp, "_leverage", config.delta.leverage) or 20
                            contract_size = DELTA_CONTRACT_SIZE.get(pair, 1.0)
                            coin_qty = contracts * contract_size
                            notional = fill_price * coin_qty
                            cost = notional / lev if lev > 1 else notional
                            collateral = round(notional / lev, 8) if lev > 1 else round(notional, 8)
                            position_type = scalp.position_side or side

                            trade_data = {
                                "pair": pair,
                                "side": "buy" if position_type == "long" else "sell",
                                "entry_price": fill_price,
                                "amount": contracts,
                                "contracts": contracts,
                                "cost": cost,
                                "collateral": collateral,
                                "strategy": "scalp",
                                "order_type": "market",
                                "exchange": "delta",
                                "status": "open",
                                "reason": "BACKFILL (DB insert missed)",
                                "leverage": lev,
                                "position_type": position_type,
                                "setup_type": "backfill",
                            }
                            trade_id = await self.db.log_trade(trade_data)
                            logger.warning(
                                "DB BACKFILL: inserted missing trade for %s %s %.0f ct "
                                "@ $%.4f (id=%s) — dashboard can now see it",
                                pair, position_type, contracts, fill_price, trade_id,
                            )
                            try:
                                await self.alerts.send_orphan_alert(
                                    pair=pair, side=position_type,
                                    contracts=contracts,
                                    action="DB BACKFILL",
                                    detail=f"Trade was on exchange + bot but missing from DB. Inserted id={trade_id}",
                                )
                            except Exception:
                                pass
                except Exception:
                    logger.debug("DB backfill check failed for %s", pair)

                continue

            if epos and (not scalp or not scalp.in_position):
                # Exchange has position, bot doesn't track it
                side = epos["side"]
                contracts = epos["contracts"]
                entry_px = epos["entry_price"]

                # ── CASE 3: Try to RESTORE from DB before closing ──────
                # If DB has an open trade for this pair, restore the strategy
                # instead of closing. This handles restarts where strategy
                # state wasn't properly injected.
                restored = False
                if scalp and self.db.is_connected:
                    open_trade = await self.db.get_open_trade(
                        pair=pair, exchange="delta",
                    )
                    if open_trade and open_trade.get("status") == "open" and open_trade.get("strategy") == "live_mirror":
                        # The LiveMirror owns this position. NEVER inject it into
                        # the legacy scalp strategy — on 06-11 that restore handed
                        # the mirror's long to scalp, whose protective SL then
                        # sold it out from under the mirror 3 minutes later.
                        self._position_first_seen.pop(f"delta:{pair}", None)
                        restored = True
                        logger.info("LiveMirror owns %s position — reconciler hands off", pair)
                    elif open_trade and open_trade.get("status") == "open":
                        # DB knows about this position — restore into strategy
                        # Use DB entry_price (truth), exchange for size/side only
                        db_entry_price = float(open_trade.get("entry_price", 0) or 0)
                        restore_price = db_entry_price if db_entry_price > 0 else entry_px

                        # ── SIDE MISMATCH FIX: exchange is truth ──
                        db_side = open_trade.get("position_type", "")
                        if db_side and db_side != side:
                            logger.warning(
                                "SIDE MISMATCH: %s — DB says %s, exchange says %s. "
                                "Updating DB to match exchange.",
                                pair, db_side.upper(), side.upper(),
                            )
                            trade_id_db = open_trade.get("id")
                            if trade_id_db:
                                try:
                                    new_order_side = "buy" if side == "long" else "sell"
                                    await self.db.update_trade(trade_id_db, {
                                        "position_type": side,
                                        "side": new_order_side,
                                    })
                                except Exception as e:
                                    logger.warning("Failed to fix side mismatch in DB for %s: %s", pair, e)

                        scalp.in_position = True
                        scalp.position_side = side
                        scalp.entry_price = restore_price
                        scalp.entry_amount = contracts
                        scalp.highest_since_entry = restore_price
                        scalp.lowest_since_entry = restore_price

                        # Restore entry_time from DB opened_at
                        opened_at_str = open_trade.get("opened_at")
                        if opened_at_str:
                            try:
                                from datetime import datetime, timezone
                                if isinstance(opened_at_str, str):
                                    opened_at_str = opened_at_str.replace("Z", "+00:00")
                                    opened_dt = datetime.fromisoformat(opened_at_str)
                                else:
                                    opened_dt = opened_at_str
                                seconds_ago = max(0, (datetime.now(timezone.utc) - opened_dt).total_seconds())
                                scalp.entry_time = time.monotonic() - seconds_ago
                            except Exception:
                                scalp.entry_time = time.monotonic()
                        else:
                            scalp.entry_time = time.monotonic()

                        # Set phantom cooldown — protect restored position from phantom detection
                        scalp._phantom_cooldown_until = time.monotonic() + 120

                        # Fetch actual current market price for immediate checks
                        current_price = await self._get_current_price(pair, "delta")
                        if current_price and current_price > 0:
                            current_pnl = scalp._calc_pnl_pct(current_price)
                            # Update highest/lowest with current market price
                            if side == "long":
                                scalp.highest_since_entry = max(restore_price, current_price)
                            else:
                                scalp.lowest_since_entry = min(restore_price, current_price)
                            scalp._peak_unrealized_pnl = max(0, current_pnl)

                            # Activate trailing if already profitable enough
                            if current_pnl >= scalp.TRAILING_ACTIVATE_PCT:
                                scalp._trailing_active = True
                                scalp._update_trail_stop()
                                logger.info(
                                    "RESTORE: %s already at +%.2f%% — trailing activated",
                                    pair, current_pnl,
                                )
                        else:
                            current_price = entry_px  # fallback
                            current_pnl = 0.0

                        logger.warning(
                            "RESTORED: %s %s %.0f contracts @ $%.2f (DB) — "
                            "current $%.2f — PnL %+.2f%%",
                            pair, side, contracts, restore_price,
                            current_price, current_pnl,
                        )
                        try:
                            await self.alerts.send_orphan_alert(
                                pair=pair, side=side, contracts=contracts,
                                action="RESTORED INTO BOT",
                                detail=f"Entry: ${restore_price:.2f} (DB) — current ${current_price:.2f} — PnL {current_pnl:+.2f}%",
                            )
                        except Exception:
                            pass
                        restored = True

                if not restored:
                    # ── SAFETY: check DB one more time for ANY open trade ────
                    # Prevents orphan-closing positions that were JUST opened
                    # (race between strategy open and reconciliation cycle)
                    any_open = None
                    if self.db.is_connected:
                        any_open = await self.db.get_open_trade(pair=pair, exchange="delta")
                    if any_open and any_open.get("status") == "open":
                        logger.info(
                            "ORPHAN SKIP: %s has open DB trade (id=%s) — NOT closing",
                            pair, any_open.get("order_id", "?"),
                        )
                        # Try to restore into strategy if scalp exists — but NEVER
                        # hand a LiveMirror position to the legacy scalp strategy.
                        if scalp and any_open.get("strategy") != "live_mirror":
                            db_price = float(any_open.get("entry_price", 0) or 0) or entry_px
                            scalp.in_position = True
                            scalp.position_side = side
                            scalp.entry_price = db_price
                            scalp.entry_amount = contracts
                            scalp.entry_time = time.monotonic()
                            logger.warning(
                                "ORPHAN→RESTORE: %s %s %.0f ct @ $%.2f — forced restore from DB",
                                pair, side, contracts, db_price,
                            )
                        continue

                    fs_key = f"delta:{pair}"

                    # ── Already gave up on this position? Silent skip ──
                    if fs_key in self._orphan_gave_up:
                        continue

                    # ── Grace period: don't close newly-detected positions ──
                    if fs_key not in self._position_first_seen:
                        self._position_first_seen[fs_key] = time.monotonic()
                    age = time.monotonic() - self._position_first_seen[fs_key]
                    if age < self.ORPHAN_GRACE_S:
                        logger.info(
                            "ORPHAN_GRACE: skipping %s (age %.0fs < %ds)",
                            pair, age, self.ORPHAN_GRACE_S,
                        )
                        continue

                    # ── CASE 1: Untracked position → ADOPT it (manual trade) ──
                    # The user punches trades directly on Delta and leaves them
                    # for the bot. NEVER auto-close. Adoption goes to the
                    # LiveMirror's V3 exit engine (ATR stop → breakeven lock →
                    # profit ratchet → tightening trail, 24h max, NO impatience
                    # exits) — NOT to legacy scalp, whose ±0.3% SL / 30-min cap
                    # is exactly the churn the user rejected. If the mirror is
                    # busy or inactive, the position is LEFT ALONE with one
                    # loud alert.
                    fail_count = self._orphan_fail_count.get(fs_key, 0)
                    lev = int(epos.get("leverage") or 0) or int(config.delta.leverage or 20)
                    mirror = getattr(self, "live_mirror", None)
                    try:
                        adopted = False
                        if mirror and mirror.is_active:
                            adopted = await mirror.adopt_manual(pair, side, contracts, entry_px, lev)
                        if not adopted:
                            note = (
                                "LiveMirror is busy with another position"
                                if mirror and mirror.is_active
                                else "LiveMirror inactive (PAPER_ONLY / LIVE_MODE off)"
                            )
                            logger.warning(
                                "MANUAL_ADOPT SKIPPED: %s %s %.0f ct @ $%.2f — %s. "
                                "Position LEFT OPEN on Delta — bot will NOT touch it.",
                                pair, side, contracts, entry_px, note,
                            )
                            if fs_key not in self._orphan_gave_up:
                                self._orphan_gave_up.add(fs_key)  # alert once, then stay silent
                                try:
                                    await self.alerts.send_orphan_alert(
                                        pair=pair, side=side, contracts=contracts,
                                        action="LEFT OPEN — unmanaged",
                                        detail=(
                                            f"Manual trade @ ${entry_px:.2f} {lev}x NOT adopted ({note}). "
                                            f"The bot will not close or manage it — handle it on Delta."
                                        ),
                                    )
                                except Exception:
                                    pass
                            continue

                        logger.info(
                            "MANUAL_ADOPT OK: %s %s %.0f ct @ $%.2f %dx — LiveMirror managing (V3 exits)",
                            pair, side, contracts, entry_px, lev,
                        )

                        # ── Success: clean up all tracking ────────────
                        self._position_first_seen.pop(fs_key, None)
                        self._orphan_fail_count.pop(fs_key, None)
                        self._orphan_gave_up.discard(fs_key)

                    except Exception:
                        fail_count += 1
                        self._orphan_fail_count[fs_key] = fail_count

                        if fail_count >= self.ORPHAN_MAX_RETRIES:
                            self._orphan_gave_up.add(fs_key)
                            self._position_first_seen.pop(fs_key, None)
                            logger.error(
                                "MANUAL_ADOPT GAVE UP: %s failed %d times — position stays "
                                "open on Delta, MANAGE MANUALLY!",
                                pair, fail_count,
                            )
                            try:
                                await self.alerts.send_orphan_alert(
                                    pair=pair, side=side, contracts=contracts,
                                    action=f"ADOPT FAILED {fail_count}x — unmanaged",
                                    detail=f"Could not adopt manual trade. Position stays open but bot is NOT managing it. Manage {pair} manually on Delta!",
                                )
                            except Exception:
                                pass
                        else:
                            logger.exception(
                                "Failed to adopt manual trade %s (attempt %d/%d) — will retry",
                                pair, fail_count, self.ORPHAN_MAX_RETRIES,
                            )

        # ── Step 3: Check for PHANTOM positions (bot has, exchange doesn't) ──
        now = time.monotonic()
        for _key, scalp in self._scalp_strategies.items():
            if not scalp.in_position or not scalp.is_futures:
                continue
            if getattr(scalp, "_exchange_id", "delta") != "delta":
                continue  # skip non-Delta strategies
            # Phantom cooldown: skip detection during cooldown (prevents RESTORE→PHANTOM cycle)
            if now < getattr(scalp, '_phantom_cooldown_until', 0):
                logger.debug("PHANTOM COOLDOWN: %s — %.0fs remaining", scalp.pair,
                             getattr(scalp, '_phantom_cooldown_until', 0) - now)
                continue
            epos = normalized_positions.get(scalp.pair)
            if not epos:
                # ── TIME GUARDS: don't phantom-clear legitimate trades ──
                # Guard 1: position opened < 5 min ago — give it time to settle
                if scalp.entry_time > 0:
                    hold_seconds = now - scalp.entry_time
                    if hold_seconds < 300:
                        logger.debug(
                            "PHANTOM SKIP: %s — opened %.0fs ago (< 5min), not clearing",
                            scalp.pair, hold_seconds,
                        )
                        continue

                # Guard 2: strategy just closed a trade < 30s ago — normal exit, not phantom
                if scalp._last_position_exit > 0:
                    since_exit = now - scalp._last_position_exit
                    if since_exit < 30:
                        logger.debug(
                            "PHANTOM SKIP: %s — trade closed %.0fs ago (< 30s), not phantom",
                            scalp.pair, since_exit,
                        )
                        continue

                logger.warning(
                    "PHANTOM DETECTED: %s — bot thinks %s @ $%.2f "
                    "but exchange has NO position! Clearing.",
                    scalp.pair, scalp.position_side, scalp.entry_price,
                )
                # Cancel any stale open orders for this pair (unfilled limit entries)
                try:
                    await self.delta.cancel_all_orders(scalp.pair)
                    logger.info("PHANTOM: cancelled all open orders for %s on Delta", scalp.pair)
                except Exception as e:
                    logger.debug("Cancel orders for %s on Delta: %s", scalp.pair, e)

                try:
                    await self.alerts.send_orphan_alert(
                        pair=scalp.pair,
                        side=scalp.position_side or "unknown",
                        contracts=scalp.entry_amount,
                        action="PHANTOM CLEARED",
                        detail=f"Bot thought {scalp.position_side} @ ${scalp.entry_price:.2f} but exchange has nothing",
                    )
                except Exception:
                    pass

                # Clear bot state
                scalp.in_position = False
                scalp.position_side = None
                scalp.entry_price = 0.0
                scalp.entry_amount = 0.0
                scalp._last_position_exit = now
                # Set phantom cooldown — no new entries on this pair for 60s
                scalp._phantom_cooldown_until = now + 60
                ScalpStrategy._live_pnl.pop(scalp.pair, None)

                phantom_pnl_for_rm = 0.0  # track actual P&L for risk manager

                # Mark closed in DB — use trade history to find real exit price & reason
                if self.db.is_connected:
                    open_trade = await self.db.get_open_trade(
                        pair=scalp.pair, exchange="delta", strategy="scalp",
                    )
                    if open_trade:
                        order_id = open_trade.get("order_id", "")
                        entry_px = float(open_trade.get("entry_price", 0) or 0)
                        trade_lev = open_trade.get("leverage", config.delta.leverage) or 1
                        pos_type = open_trade.get("position_type", "long")
                        phantom_amount = open_trade.get("amount", 0)
                        phantom_exit = entry_px
                        phantom_reason = "phantom_cleared"

                        # Try to find actual exit from Delta trade history
                        try:
                            recent_trades = await self.delta.fetch_my_trades(scalp.pair, limit=20)
                            if recent_trades:
                                close_side = "sell" if pos_type == "long" else "buy"
                                closing_fills = [
                                    t for t in recent_trades
                                    if t.get("side") == close_side
                                ]
                                if closing_fills:
                                    last_fill = closing_fills[-1]
                                    fill_price = float(last_fill.get("price", 0) or 0)
                                    if fill_price > 0:
                                        phantom_exit = fill_price
                                        # Determine exit reason from fill context
                                        fill_info = last_fill.get("info", {})
                                        fill_type = str(fill_info.get("meta_data", {}).get("order_type", "")).lower() if isinstance(fill_info, dict) else ""
                                        if "stop" in fill_type or "sl" in fill_type:
                                            phantom_reason = "SL_EXCHANGE"
                                        elif "take_profit" in fill_type or "tp" in fill_type:
                                            phantom_reason = "TP_EXCHANGE"
                                        else:
                                            phantom_reason = "CLOSED_BY_EXCHANGE"
                                        logger.info(
                                            "Phantom %s: found exit fill $%.2f (reason=%s)",
                                            scalp.pair, fill_price, phantom_reason,
                                        )
                        except Exception as e:
                            logger.debug("Could not fetch trade history for %s: %s", scalp.pair, e)

                        if phantom_exit == entry_px:
                            try:
                                ticker = await self.delta.fetch_ticker(scalp.pair)
                                phantom_exit = float(ticker.get("last", 0) or 0) or entry_px
                            except Exception:
                                pass

                        # ── SAFETY: never close with $0 exit ──
                        if phantom_exit <= 0:
                            logger.error("Delta phantom %s: exit=$0, skipping close", scalp.pair)
                            continue

                        _r = calc_pnl(
                            entry_px, phantom_exit, phantom_amount,
                            pos_type, trade_lev, "delta", scalp.pair,
                            entry_fee_rate=config.delta.taker_fee_with_gst,
                            exit_fee_rate=config.delta.taker_fee_with_gst,
                        )
                        phantom_pnl, phantom_pnl_pct = _r.net_pnl, _r.pnl_pct
                        phantom_pnl_for_rm = phantom_pnl
                        trade_id = open_trade.get("id")
                        _phantom_exit_map = {"SL_EXCHANGE": "SL_EXCHANGE",
                                             "TP_EXCHANGE": "TP_EXCHANGE", "CLOSED_BY_EXCHANGE": "CLOSED_BY_EXCHANGE"}
                        phantom_exit_reason = _phantom_exit_map.get(phantom_reason, "PHANTOM")
                        if order_id:
                            await self.db.close_trade(
                                order_id, phantom_exit, phantom_pnl, phantom_pnl_pct,
                                reason=phantom_reason,
                                exit_reason=phantom_exit_reason,
                                gross_pnl=_r.gross_pnl,
                                entry_fee=_r.entry_fee,
                                exit_fee=_r.exit_fee,
                            )
                        elif trade_id:
                            await self.db.update_trade(trade_id, {
                                "status": "closed",
                                "exit_price": phantom_exit,
                                "closed_at": iso_now(),
                                "pnl": round(phantom_pnl, 8),
                                "pnl_pct": round(phantom_pnl_pct, 4),
                                "reason": phantom_reason,
                                "exit_reason": phantom_exit_reason,
                            })
                        logger.info(
                            "Phantom trade %s closed: exit=$%.2f pnl=$%.4f (%.2f%%) reason=%s",
                            scalp.pair, phantom_exit, phantom_pnl, phantom_pnl_pct, phantom_reason,
                        )

                # Remove from risk manager — use real P&L for accurate daily tracking
                self.risk_manager.record_close(scalp.pair, phantom_pnl_for_rm)

    async def _reconcile_binance_positions(self) -> None:
        """DISABLED — Binance not used (Delta options only mode)."""
        return  # noqa: Binance disabled
        if not self.binance:
            return

        try:
            balance = await self.binance.fetch_balance()
            free_balances = balance.get("free", {})
        except Exception:
            return

        for _key, scalp in self._scalp_strategies.items():
            if scalp.is_futures:
                continue  # skip Delta pairs
            if not scalp.in_position:
                continue  # bot doesn't think it has a position, skip

            # Check if we actually hold this asset
            base = scalp.pair.split("/")[0] if "/" in scalp.pair else scalp.pair
            held = float(free_balances.get(base, 0) or 0)
            held_value = held * scalp.entry_price if scalp.entry_price > 0 else 0

            if held_value < 3.0:
                # ── TIME GUARDS ──
                bnow = time.monotonic()
                if scalp.entry_time > 0 and (bnow - scalp.entry_time) < 300:
                    continue  # opened < 5 min ago
                if scalp._last_position_exit > 0 and (bnow - scalp._last_position_exit) < 30:
                    continue  # just closed < 30s ago

                # PHANTOM — bot thinks position exists but nothing on exchange
                logger.warning(
                    "PHANTOM (Binance): %s — bot thinks long @ $%.2f but only $%.2f held. Clearing.",
                    scalp.pair, scalp.entry_price, held_value,
                )
                try:
                    await self.alerts.send_orphan_alert(
                        pair=scalp.pair, side="long", contracts=scalp.entry_amount,
                        action="PHANTOM CLEARED (insufficient balance)",
                        detail=f"Only ${held_value:.2f} held — position was closed externally",
                    )
                except Exception:
                    pass

                scalp.in_position = False
                scalp.position_side = None
                scalp.entry_price = 0.0
                scalp.entry_amount = 0.0
                scalp._last_position_exit = bnow
                scalp._phantom_cooldown_until = bnow + 60

                phantom_pnl_for_rm_bn = 0.0  # track actual P&L for risk manager

                if self.db.is_connected:
                    open_trade = await self.db.get_open_trade(
                        pair=scalp.pair, exchange="binance", strategy="scalp",
                    )
                    if open_trade:
                        order_id = open_trade.get("order_id", "")
                        entry_px = float(open_trade.get("entry_price", 0) or 0)
                        phantom_amount = open_trade.get("amount", 0)
                        phantom_exit = entry_px
                        phantom_reason = "phantom_cleared"

                        # Try to find actual exit from Binance trade history
                        try:
                            recent_trades = await self.binance.fetch_my_trades(scalp.pair, limit=20)
                            if recent_trades:
                                closing_fills = [
                                    t for t in recent_trades if t.get("side") == "sell"
                                ]
                                if closing_fills:
                                    last_fill = closing_fills[-1]
                                    fill_price = float(last_fill.get("price", 0) or 0)
                                    if fill_price > 0:
                                        phantom_exit = fill_price
                                        phantom_reason = "CLOSED_BY_EXCHANGE"
                                        logger.info(
                                            "Phantom Binance %s: found sell fill $%.2f",
                                            scalp.pair, fill_price,
                                        )
                        except Exception as e:
                            logger.debug("Could not fetch Binance trade history for %s: %s", scalp.pair, e)

                        # Fallback: current ticker if no fill found
                        if phantom_exit == entry_px:
                            try:
                                ticker = await self.binance.fetch_ticker(scalp.pair)
                                phantom_exit = float(ticker.get("last", 0) or 0) or entry_px
                            except Exception:
                                pass

                        # ── SAFETY: never close with $0 exit ──
                        if phantom_exit <= 0:
                            logger.error("Binance phantom %s: exit=$0, skipping close", scalp.pair)
                            continue

                        _r = calc_pnl(
                            entry_px, phantom_exit, phantom_amount,
                            "spot", 1, "binance", scalp.pair,
                            entry_fee_rate=0.001, exit_fee_rate=0.001,
                        )
                        phantom_pnl, phantom_pnl_pct = _r.net_pnl, _r.pnl_pct
                        phantom_pnl_for_rm_bn = phantom_pnl
                        trade_id = open_trade.get("id")
                        _phantom_exit_map_bn = {"phantom_cleared": "PHANTOM", "SL_EXCHANGE": "SL_EXCHANGE",
                                                "TP_EXCHANGE": "TP_EXCHANGE", "CLOSED_BY_EXCHANGE": "CLOSED_BY_EXCHANGE"}
                        phantom_exit_reason = _phantom_exit_map_bn.get(phantom_reason, "PHANTOM")
                        if order_id:
                            await self.db.close_trade(
                                order_id, phantom_exit, phantom_pnl, phantom_pnl_pct,
                                reason=phantom_reason,
                                exit_reason=phantom_exit_reason,
                                gross_pnl=_r.gross_pnl,
                                entry_fee=_r.entry_fee,
                                exit_fee=_r.exit_fee,
                            )
                        elif trade_id:
                            await self.db.update_trade(trade_id, {
                                "status": "closed",
                                "exit_price": phantom_exit,
                                "closed_at": iso_now(),
                                "pnl": round(phantom_pnl, 8),
                                "pnl_pct": round(phantom_pnl_pct, 4),
                                "reason": phantom_reason,
                                "exit_reason": phantom_exit_reason,
                            })
                        logger.info(
                            "Phantom Binance %s closed: exit=$%.2f pnl=$%.4f reason=%s",
                            scalp.pair, phantom_exit, phantom_pnl, phantom_reason,
                        )
                # Remove from risk manager — use real P&L for accurate daily tracking
                self.risk_manager.record_close(scalp.pair, phantom_pnl_for_rm_bn)

    async def _close_orphaned_positions(self) -> None:
        """Close any open positions from non-scalp strategies (e.g. futures_momentum).

        Called on startup to free up margin tied by strategies that have been removed.
        Sends a market sell/buy to close the position, then marks the DB trade as closed.
        """
        if not self.db.is_connected:
            return

        open_trades = await self.db.get_all_open_trades()
        if not open_trades:
            return

        # Only close non-scalp, non-options_scalp positions
        allowed_strategies = {"scalp", "options_scalp", ""}
        orphans = [
            t for t in open_trades
            if t.get("strategy", "") not in allowed_strategies
        ]

        if not orphans:
            return

        logger.warning(
            "Found %d orphaned position(s) from removed strategies — closing at market",
            len(orphans),
        )

        for trade in orphans:
            pair = trade["pair"]
            exchange_id = trade.get("exchange", "delta")
            position_type = trade.get("position_type", "long")
            amount = trade.get("amount", 0)
            entry_price = trade.get("entry_price", 0)
            order_id = trade.get("order_id", "")
            strategy_name = trade.get("strategy", "unknown")

            logger.info(
                "Closing orphaned %s position: %s %s %.6f @ $%.2f (strategy=%s)",
                strategy_name, pair, position_type, amount, entry_price, strategy_name,
            )

            pnl = 0.0
            pnl_pct = 0.0
            trade_lev = trade.get("leverage", 1) or 1

            try:
                # Determine close side
                close_side = "sell" if position_type == "long" else "buy"

                # Get current price for P&L calc
                exchange = self.delta  # Delta only mode
                if exchange:
                    ticker = await exchange.fetch_ticker(pair)
                    current_price = float(ticker.get("last", 0) or 0)
                else:
                    current_price = entry_price

                # For Delta: convert to contracts
                if exchange_id == "delta":
                    contract_size = DELTA_CONTRACT_SIZE.get(pair, 0.01)
                    contracts = max(1, int(amount / contract_size))

                    await exchange.create_order(  # type: ignore[union-attr]
                        pair, "market", close_side, contracts,
                        params={"reduceOnly": True},
                    )
                    logger.info(
                        "Closed orphaned position: %s %s %d contracts at market",
                        pair, close_side, contracts,
                    )
                else:
                    # Binance spot — sell the amount
                    if exchange:
                        await exchange.create_order(  # type: ignore[union-attr]
                            pair, "market", close_side, amount,
                        )

                # Calculate P&L (leveraged, contract-aware)
                _fee = {"kraken": config.kraken.taker_fee,
                        "bybit": config.bybit.taker_fee,
                        "delta": config.delta.taker_fee_with_gst,
                        "binance": 0.001}.get(exchange_id, 0.0)
                _r = calc_pnl(
                    entry_price, current_price, amount,
                    position_type, trade_lev,
                    exchange_id, pair,
                    entry_fee_rate=_fee, exit_fee_rate=_fee,
                )
                pnl, pnl_pct = _r.net_pnl, _r.pnl_pct

                # Close in DB
                if order_id:
                    await self.db.close_trade(
                        order_id, current_price, pnl, pnl_pct,
                        reason="orphan_strategy_removed",
                        exit_reason="ORPHAN",
                        gross_pnl=_r.gross_pnl,
                        entry_fee=_r.entry_fee,
                        exit_fee=_r.exit_fee,
                    )

                # Remove from risk manager — prevents ghost entries
                self.risk_manager.record_close(pair, pnl)

                # Send alert
                await self.alerts.send_text(
                    f"🧹 Closed orphaned {strategy_name} position\n"
                    f"{pair} {position_type.upper()} @ ${entry_price:.2f}\n"
                    f"Exit: ${current_price:.2f} | P&L: ${pnl:+.4f} ({pnl_pct:+.2f}%)\n"
                    f"Reason: Strategy removed — freeing margin"
                )

            except Exception:
                logger.exception("Failed to close orphaned position %s", pair)
                # Try to at least mark it in DB — use current price if possible
                fallback_pnl = 0.0
                try:
                    if order_id:
                        # Try to get current price for accurate P&L
                        fallback_exit = entry_price
                        try:
                            exchange = self.delta  # Delta only mode
                            if exchange:
                                ticker = await exchange.fetch_ticker(pair)
                                fallback_exit = float(ticker.get("last", 0) or 0) or entry_price
                        except Exception:
                            pass  # keep fallback_exit = entry_price, pnl = 0
                        _fee = {"kraken": config.kraken.taker_fee,
                                "bybit": config.bybit.taker_fee,
                                "delta": config.delta.taker_fee_with_gst,
                                "binance": 0.001}.get(exchange_id, 0.0)
                        _r = calc_pnl(
                            entry_price, fallback_exit, amount,
                            position_type, trade_lev,
                            exchange_id, pair,
                            entry_fee_rate=_fee, exit_fee_rate=_fee,
                        )
                        fallback_pnl, fallback_pnl_pct = _r.net_pnl, _r.pnl_pct
                        await self.db.close_trade(
                            order_id, fallback_exit, fallback_pnl, fallback_pnl_pct,
                            reason="orphan_strategy_removed",
                            exit_reason="ORPHAN",
                            gross_pnl=_r.gross_pnl,
                            entry_fee=_r.entry_fee,
                            exit_fee=_r.exit_fee,
                        )
                        logger.info(
                            "Orphan fallback close %s: exit=$%.2f pnl=$%.4f (%.2f%%)",
                            pair, fallback_exit, fallback_pnl, fallback_pnl_pct,
                        )
                    # Remove from risk manager even in fallback path
                    self.risk_manager.record_close(pair, fallback_pnl)
                except Exception:
                    pass

    # -- Exchange init ---------------------------------------------------------

    async def _init_exchanges(self) -> None:
        """Create ccxt exchange instances — Delta only.

        Uses the threaded DNS resolver to avoid aiodns failures on Windows.
        """
        # Delta Exchange India (futures + options)
        if config.delta.api_key:
            # Validate credentials are plain strings
            delta_key = str(config.delta.api_key).strip()
            delta_secret = str(config.delta.secret).strip()
            logger.info(
                "Delta credentials: key_len=%d, secret_len=%d, key_type=%s, secret_type=%s",
                len(delta_key), len(delta_secret),
                type(config.delta.api_key).__name__, type(config.delta.secret).__name__,
            )

            delta_session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(
                    resolver=aiohttp.resolver.ThreadedResolver(), ssl=True,
                )
            )
            self.delta = ccxt.delta({
                "apiKey": delta_key,
                "secret": delta_secret,
                "enableRateLimit": True,
                "options": {"defaultType": "future"},
                "session": delta_session,
            })
            # Override to India endpoint — urls['api'] must be a dict with public/private keys
            self.delta.urls["api"] = {
                "public": config.delta.base_url,
                "private": config.delta.base_url,
            }
            # ── LEVERAGE SAFETY CHECK ─────────────────────────────────────
            if config.delta.leverage > 20:
                logger.warning(
                    "!!! LEVERAGE IS %dx — max supported is 20x !!! "
                    "Set DELTA_LEVERAGE=20 in .env",
                    config.delta.leverage,
                )
            logger.info(
                "Delta Exchange India initialized (futures enabled, testnet=%s, leverage=%dx, url=%s)",
                config.delta.testnet, config.delta.leverage, config.delta.base_url,
            )

            # Delta Options — separate ccxt instance for option markets
            if config.delta.options_enabled:
                delta_options_session = aiohttp.ClientSession(
                    connector=aiohttp.TCPConnector(
                        resolver=aiohttp.resolver.ThreadedResolver(), ssl=True,
                    )
                )
                self.delta_options = ccxt.delta({
                    "apiKey": delta_key,
                    "secret": delta_secret,
                    "enableRateLimit": True,
                    "options": {"defaultType": "option"},
                    "session": delta_options_session,
                })
                self.delta_options.urls["api"] = {
                    "public": config.delta.base_url,
                    "private": config.delta.base_url,
                }
                logger.info("Delta Exchange India options initialized (pairs: %s)",
                            ", ".join(config.delta.options_pairs))
            else:
                logger.info("Delta options disabled (set DELTA_OPTIONS_ENABLED=true to enable)")
        else:
            self.delta_pairs = []  # no Delta pairs if no credentials
            logger.info("Delta credentials not set -- futures disabled")

        # Bybit/Kraken/Binance — DISABLED (Delta options only mode)
        logger.info("Running in Delta-only mode — Bybit/Kraken/Binance disabled")

    async def _fetch_portfolio_usd(
        self, exchange: ccxt.Exchange | None,
    ) -> float | None:
        """Fetch total portfolio value in USD including held assets.

        For Binance: USDT free + value of held crypto assets.
        For Delta: wallet balance + unrealized P&L from open positions.
        """
        if not exchange:
            return None
        ex_id = getattr(exchange, "id", "?")
        try:
            balance = await exchange.fetch_balance()
            total_map = balance.get("total", {})
            free_map = balance.get("free", {})

            # Log raw balance data for debugging
            holdings = {k: float(v) for k, v in total_map.items()
                        if v is not None and float(v) > 0}
            free_holdings = {k: float(v) for k, v in free_map.items()
                            if v is not None and float(v) > 0}
            logger.info("Holdings on %s: total=%s free=%s", ex_id, holdings, free_holdings)

            # Also log the info dict if available (contains exchange-specific fields)
            info = balance.get("info")
            if info and isinstance(info, dict):
                # Log key fields for Delta (wallet_balance, equity, margin_balance, etc.)
                for key in ("wallet_balance", "equity", "available_balance",
                            "margin_balance", "unrealized_pnl", "balance", "result"):
                    if key in info:
                        logger.info("  %s.info.%s = %s", ex_id, key, info[key])
                # Delta may nest under 'result' key
                result = info.get("result") if isinstance(info.get("result"), dict) else None
                if result:
                    for key in ("balance", "available_balance", "portfolio_margin",
                                "commission", "unrealized_pnl"):
                        if key in result:
                            logger.info("  %s.info.result.%s = %s", ex_id, key, result[key])

            # ── Stablecoins at face value ──────────────────────────────────
            stablecoin_total = 0.0
            for key in ("USDT", "USD", "USDC"):
                val = total_map.get(key)
                if val is not None and float(val) > 0:
                    stablecoin_total += float(val)

            # ── Value held crypto assets using live ticker prices ──────────
            asset_total = 0.0
            asset_details: list[str] = []
            tracked_bases = set()
            for pair in (config.trading.pairs or []):
                base = pair.split("/")[0] if "/" in pair else pair
                tracked_bases.add(base)

            for asset, qty in holdings.items():
                if asset in ("USDT", "USD", "USDC", "INR"):
                    continue
                if asset not in tracked_bases:
                    continue
                qty_f = float(qty)
                if qty_f <= 0:
                    continue
                try:
                    ticker = await exchange.fetch_ticker(f"{asset}/USDT")
                    price = ticker.get("last", 0) or 0
                    if price and price > 0:
                        value = qty_f * price
                        if value > 0.50:
                            asset_total += value
                            asset_details.append(f"{asset}={qty_f:.6f}@${price:.2f}=${value:.2f}")
                except Exception:
                    pass

            # ── Delta Exchange India: INR → USD conversion ─────────────────
            inr_total = 0.0
            inr_raw = 0.0
            inr_val = total_map.get("INR") or free_map.get("INR")
            if inr_val is not None and float(inr_val) > 0:
                inr_raw = float(inr_val)
                # Try to get live INR/USD rate from Binance
                inr_rate = await self._get_inr_usd_rate()
                inr_total = inr_raw / inr_rate

            # ── Delta: add unrealized P&L from open futures positions ──────
            unrealized_pnl_usd = 0.0
            if ex_id == "delta" and exchange:
                try:
                    positions = await exchange.fetch_positions()
                    for pos in positions:
                        contracts = float(pos.get("contracts", 0) or 0)
                        if contracts == 0:
                            continue
                        # ccxt normalizes unrealizedPnl
                        upnl = float(pos.get("unrealizedPnl", 0) or 0)
                        if upnl != 0:
                            unrealized_pnl_usd += upnl
                    if unrealized_pnl_usd != 0:
                        logger.info("  Delta unrealized P&L: $%.4f", unrealized_pnl_usd)
                except Exception as e:
                    logger.debug("Could not fetch Delta positions for P&L: %s", e)

            portfolio_total = stablecoin_total + asset_total + inr_total + unrealized_pnl_usd

            if inr_raw > 0:
                logger.info(
                    "Portfolio %s: USDT=$%.2f + assets=$%.2f%s + INR=₹%.2f ($%.2f) + uPnL=$%.4f = $%.2f",
                    ex_id, stablecoin_total, asset_total,
                    f" ({', '.join(asset_details)})" if asset_details else "",
                    inr_raw, inr_total, unrealized_pnl_usd, portfolio_total,
                )
            else:
                logger.info(
                    "Portfolio %s: USDT=$%.2f + assets=$%.2f%s + uPnL=$%.4f = $%.2f",
                    ex_id, stablecoin_total, asset_total,
                    f" ({', '.join(asset_details)})" if asset_details else "",
                    unrealized_pnl_usd, portfolio_total,
                )

            return portfolio_total if portfolio_total > 0 else 0.0

        except Exception as e:
            logger.warning("Could not fetch balance from %s: %s (type: %s)", ex_id, e, type(e).__name__)
            return None

    async def _get_inr_usd_rate(self) -> float:
        """Get current INR/USD exchange rate. Uses cached value, refreshed every hour."""
        now = time.monotonic()
        if hasattr(self, "_inr_rate") and hasattr(self, "_inr_rate_time"):
            if now - self._inr_rate_time < 3600:  # cache for 1 hour
                return self._inr_rate

        rate = 86.5  # fallback default
        try:
            env_rate = config.delta.__dict__.get("inr_usd_rate")
            if env_rate and float(env_rate) > 0:
                rate = float(env_rate)
        except Exception:
            pass

        self._inr_rate = rate
        self._inr_rate_time = now
        logger.debug("INR/USD rate: %.2f", rate)
        return rate


def _acquire_lockfile() -> Any:
    """Prevent duplicate bot processes via PID lockfile (Linux/macOS only)."""
    if sys.platform == "win32":
        return None
    import fcntl
    lock_path = "/tmp/alpha_bot.lock"
    lock_file = open(lock_path, "w")  # noqa: SIM115
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_file.write(str(os.getpid()))
        lock_file.flush()
        return lock_file  # keep reference so GC doesn't close it
    except BlockingIOError:
        print(f"FATAL: Alpha already running (lockfile {lock_path}). Exiting.")
        sys.exit(1)


def main() -> None:
    """Entry point."""
    _lock = _acquire_lockfile()  # noqa: F841 — must keep reference
    bot = AlphaBot()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        logger.info("Interrupted")


if __name__ == "__main__":
    main()

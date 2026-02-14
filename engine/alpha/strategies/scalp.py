"""Pattern-based scalping strategy — always hunting for entries.

Runs as an independent parallel task alongside whatever primary strategy
is active. Checks every 10 seconds on 1m candles. Philosophy: always be
in the market. If balance is available, find a pattern and enter.

Entry Patterns (ANY one pattern triggers entry):
  1. RSI Extreme:     RSI < 30 long, RSI > 70 short (instant)
  2. BB Squeeze Break: BB width < 1% + price breaks band → enter breakout direction
  3. Volume Spike:    Volume > 2x average → enter candle direction
  4. RSI Divergence:  Price lower low + RSI higher low → long (vice versa short)
  5. Quick Reversal:  After SL, if price reverses within 30s → enter opposite
  6. Candle Pattern:  3 consecutive directional candles (>0.1% each) → fade
  7. Mean Reversion:  Price > 1.5% from 20-EMA → enter toward EMA
  8. BB Touch + Confirm: Price at BB + (RSI or volume or candle pattern) → enter

Exit:
  - TP: 1.5% price (= 7.5% capital at 5x)
  - SL: 0.75% (= 3.75% capital at 5x)
  - Trailing: activate 0.80%, trail 0.40%
  - Timeout: 45 min
  - Flatline: close if < 0.1% move for 30 min
  - Risk/reward: 2:1 — need 34% win rate to profit
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import ccxt.async_support as ccxt
import numpy as np
import pandas as pd
import ta

from alpha.config import config
from alpha.strategies.base import BaseStrategy, Signal, StrategyName
from alpha.utils import setup_logger

if TYPE_CHECKING:
    from alpha.risk_manager import RiskManager
    from alpha.trade_executor import TradeExecutor

logger = setup_logger("scalp")


class ScalpStrategy(BaseStrategy):
    """
    Pattern-based scalp — always hunting for entries.

    Any ONE pattern triggers an entry. 8 patterns scanned every 10s.
    Tighter RSI thresholds for standard patterns; extreme RSI bypasses all.

    Exit: TP=1.5%, SL=0.75%, Trail=0.80/0.40, Timeout=45min, Flatline=30min.
    Risk/reward 2:1 — only need 34% win rate to profit.
    """

    name = StrategyName.SCALP
    check_interval_sec = 10  # 10 second ticks — always hunting

    # ── Exit thresholds (2:1 R/R) ─────────────────────────────────────────
    TAKE_PROFIT_PCT = 1.5         # 1.5% price move
    STOP_LOSS_PCT = 0.75          # 0.75% price move (2:1 R/R)
    TRAILING_ACTIVATE_PCT = 0.80  # start trailing after 0.80%
    TRAILING_DISTANCE_PCT = 0.40  # trail at 0.40% from high/low
    MAX_HOLD_SECONDS = 45 * 60    # 45 minutes
    FLATLINE_SECONDS = 30 * 60    # close if flat for 30 min
    FLATLINE_MIN_MOVE_PCT = 0.1   # "flat" means < 0.1% total move

    # ── Pattern thresholds ────────────────────────────────────────────────
    RSI_EXTREME_LONG = 30         # instant long entry
    RSI_EXTREME_SHORT = 70        # instant short entry
    BB_SQUEEZE_WIDTH_PCT = 1.0    # BB width < 1% = squeeze
    VOL_SPIKE_RATIO = 2.0         # volume > 2x average
    CANDLE_MIN_PCT = 0.1          # min candle size for candle pattern
    MEAN_REVERSION_PCT = 1.5      # price > 1.5% from EMA → mean revert
    BB_TOUCH_CONFIRM_RSI_L = 40   # RSI < 40 confirms lower BB touch
    BB_TOUCH_CONFIRM_RSI_S = 60   # RSI > 60 confirms upper BB touch

    # ── Position sizing ───────────────────────────────────────────────────
    CAPITAL_PCT_SPOT = 50.0       # 50% for spot (Binance $5 min)
    CAPITAL_PCT_FUTURES = 30.0    # 30% for futures (leverage)
    MAX_POSITIONS_PER_EXCHANGE = 2  # 2 concurrent per exchange
    MAX_SPREAD_PCT = 0.15         # skip if spread > 0.15%

    # ── Rate limiting / risk ──────────────────────────────────────────────
    MAX_TRADES_PER_HOUR = 30
    CONSECUTIVE_LOSS_PAUSE = 5    # pause after 5 consecutive losses
    PAUSE_DURATION_SEC = 15 * 60  # 15 minutes pause
    DAILY_LOSS_LIMIT_PCT = 5.0

    def __init__(
        self,
        pair: str,
        executor: TradeExecutor,
        risk_manager: RiskManager,
        exchange: Any = None,
        is_futures: bool = False,
    ) -> None:
        super().__init__(pair, executor, risk_manager)
        self.trade_exchange: ccxt.Exchange | None = exchange
        self.is_futures = is_futures
        self.leverage: int = min(config.delta.leverage, 10) if is_futures else 1
        self.capital_pct: float = self.CAPITAL_PCT_FUTURES if is_futures else self.CAPITAL_PCT_SPOT
        self._exchange_id: str = "delta" if is_futures else "binance"

        # Position state
        self.in_position = False
        self.position_side: str | None = None  # "long" or "short"
        self.entry_price: float = 0.0
        self.entry_amount: float = 0.0
        self.entry_time: float = 0.0
        self.highest_since_entry: float = 0.0
        self.lowest_since_entry: float = float("inf")
        self._positions_on_pair: int = 0

        # Rate limiting
        self._hourly_trades: list[float] = []
        self._consecutive_losses: int = 0
        self._paused_until: float = 0.0
        self._daily_scalp_loss: float = 0.0

        # Quick reversal state
        self._last_sl_side: str | None = None
        self._last_sl_time: float = 0.0

        # Stats for hourly summary
        self.hourly_wins: int = 0
        self.hourly_losses: int = 0
        self.hourly_pnl: float = 0.0

        # Tick tracking
        self._tick_count: int = 0
        self._last_heartbeat: float = 0.0

    async def on_start(self) -> None:
        self.in_position = False
        self.position_side = None
        self.entry_price = 0.0
        self.entry_amount = 0.0
        self._positions_on_pair = 0
        self._tick_count = 0
        self._last_heartbeat = time.monotonic()
        tag = f"{self.leverage}x futures" if self.is_futures else "spot"
        self.logger.info(
            "[%s] Scalp ACTIVE (%s, %.0f%% capital) — PATTERN-BASED, tick=%ds, "
            "8 patterns, TP=%.2f%% SL=%.2f%% Trail=%.2f/%.2f%% Timeout=%dm",
            self.pair, tag, self.capital_pct, self.check_interval_sec,
            self.TAKE_PROFIT_PCT, self.STOP_LOSS_PCT,
            self.TRAILING_ACTIVATE_PCT, self.TRAILING_DISTANCE_PCT,
            self.MAX_HOLD_SECONDS // 60,
        )

    async def on_stop(self) -> None:
        self.logger.info(
            "[%s] Scalp stopped — %dW/%dL, P&L=$%.4f",
            self.pair, self.hourly_wins, self.hourly_losses, self.hourly_pnl,
        )

    # ======================================================================
    # MAIN CHECK LOOP
    # ======================================================================

    async def check(self) -> list[Signal]:
        """One scalping tick — fetch 1m candles, scan patterns, manage exits."""
        signals: list[Signal] = []
        self._tick_count += 1
        exchange = self.trade_exchange or self.executor.exchange

        # ── Pause check ──────────────────────────────────────────────────
        now = time.monotonic()
        if now < self._paused_until:
            remaining = int(self._paused_until - now)
            if self._tick_count % 30 == 0:
                self.logger.info(
                    "[%s] Scalp PAUSED (%d losses) — resuming in %dm",
                    self.pair, self._consecutive_losses, remaining // 60,
                )
            return signals

        # ── Daily scalp loss limit ───────────────────────────────────────
        if self._daily_scalp_loss <= -(self.risk_manager.get_exchange_capital(self._exchange_id) * self.DAILY_LOSS_LIMIT_PCT / 100):
            if self._tick_count % 30 == 0:
                self.logger.info(
                    "[%s] Scalp STOPPED — daily loss limit hit ($%.4f)",
                    self.pair, self._daily_scalp_loss,
                )
            return signals

        # ── Rate limit check ─────────────────────────────────────────────
        cutoff = time.time() - 3600
        self._hourly_trades = [t for t in self._hourly_trades if t > cutoff]
        if len(self._hourly_trades) >= self.MAX_TRADES_PER_HOUR:
            if self._tick_count % 30 == 0:
                self.logger.info(
                    "[%s] Scalp rate limited — %d trades/hr (max %d)",
                    self.pair, len(self._hourly_trades), self.MAX_TRADES_PER_HOUR,
                )
            return signals

        # ── Fetch 1m candles ─────────────────────────────────────────────
        ohlcv = await exchange.fetch_ohlcv(self.pair, "1m", limit=50)
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        close = df["close"]
        volume = df["volume"]
        current_price = float(close.iloc[-1])

        # ── Compute indicators ───────────────────────────────────────────
        rsi_series = ta.momentum.RSIIndicator(close, window=14).rsi()
        bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
        bb_upper = float(bb.bollinger_hband().iloc[-1])
        bb_lower = float(bb.bollinger_lband().iloc[-1])
        bb_mid = float(bb.bollinger_mavg().iloc[-1])

        rsi_now = float(rsi_series.iloc[-1])

        # Volume ratio
        avg_vol = float(volume.iloc[-11:-1].mean()) if len(volume) >= 11 else float(volume.mean())
        current_vol = float(volume.iloc[-1])
        vol_ratio = current_vol / avg_vol if avg_vol > 0 else 0

        # BB width as percentage of mid
        bb_range = bb_upper - bb_lower
        bb_width_pct = (bb_range / bb_mid * 100) if bb_mid > 0 else 999

        # Price proximity to bands
        lower_dist_pct = ((current_price - bb_lower) / bb_lower * 100) if bb_lower > 0 else 999
        upper_dist_pct = ((bb_upper - current_price) / bb_upper * 100) if bb_upper > 0 else 999

        # EMA 20 for mean reversion
        ema_20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
        ema_dist_pct = ((current_price - ema_20) / ema_20 * 100) if ema_20 > 0 else 0

        # Candle changes for pattern detection
        closes = close.values
        candle_changes: list[float] = []
        for i in range(-3, 0):
            if len(closes) >= abs(i) + 1:
                prev = float(closes[i - 1])
                cur = float(closes[i])
                candle_changes.append(((cur - prev) / prev * 100) if prev > 0 else 0)
            else:
                candle_changes.append(0)

        last_candle_pct = candle_changes[-1] if candle_changes else 0

        # RSI previous values for divergence
        rsi_vals = rsi_series.dropna().values
        prev_close = float(close.iloc[-2]) if len(close) >= 2 else current_price

        # ── Heartbeat every 5 minutes ────────────────────────────────────
        if now - self._last_heartbeat >= 300:
            self._last_heartbeat = now
            tag = f"{self.leverage}x" if self.is_futures else "spot"
            if self.in_position:
                hold_sec = time.monotonic() - self.entry_time
                pnl_now = ((current_price - self.entry_price) / self.entry_price * 100
                           if self.position_side == "long"
                           else (self.entry_price - current_price) / self.entry_price * 100)
                self.logger.info(
                    "[%s] Scalp heartbeat (%s) — %s @ $%.2f for %ds, PnL=%+.2f%%, RSI=%.1f",
                    self.pair, tag, self.position_side, self.entry_price,
                    int(hold_sec), pnl_now, rsi_now,
                )
            else:
                self.logger.info(
                    "[%s] Scalp heartbeat (%s) — HUNTING | RSI=%.1f, BBW=%.2f%%, Vol=%.1fx, "
                    "EMA_dist=%+.2f%% | trades/hr=%d, W/L=%d/%d",
                    self.pair, tag, rsi_now, bb_width_pct, vol_ratio, ema_dist_pct,
                    len(self._hourly_trades), self.hourly_wins, self.hourly_losses,
                )

        # ── In position: check exit ──────────────────────────────────────
        if self.in_position:
            signals = self._check_exits(current_price, rsi_now)
            return signals

        # ── No position: HUNT for patterns ───────────────────────────────
        self.logger.info(
            "[%s] Scalp #%d HUNTING | $%.2f | RSI=%.1f | BBW=%.1f%% | "
            "Vol=%.1fx | EMA_dist=%+.2f%% | candle=%+.2f%%",
            self.pair, self._tick_count, current_price,
            rsi_now, bb_width_pct, vol_ratio, ema_dist_pct, last_candle_pct,
        )

        # Check position limits
        if self.risk_manager.has_position(self.pair):
            return signals

        scalp_positions = sum(
            1 for p in self.risk_manager.open_positions
            if p.strategy == "scalp" and getattr(p, "exchange_id", None) == self._exchange_id
        )
        if scalp_positions >= self.MAX_POSITIONS_PER_EXCHANGE:
            return signals

        # Spread check
        try:
            ticker = await exchange.fetch_ticker(self.pair)
            bid = ticker.get("bid", 0) or 0
            ask = ticker.get("ask", 0) or 0
            if bid > 0 and ask > 0:
                spread_pct = ((ask - bid) / bid) * 100
                if spread_pct > self.MAX_SPREAD_PCT:
                    return signals
        except Exception:
            pass

        # Check available balance
        available = self.risk_manager.get_available_capital(self._exchange_id)
        min_balance = 5.50 if self._exchange_id == "binance" else 1.00
        if available < min_balance:
            if self._tick_count % 30 == 0:
                self.logger.info(
                    "[%s] Insufficient %s balance: $%.2f < $%.2f — waiting",
                    self.pair, self._exchange_id, available, min_balance,
                )
            return signals

        # Size the position
        amount = self._calculate_position_size(current_price, available)
        if amount is None:
            return signals

        # ── Scan all 8 patterns (first match wins) ────────────────────────
        entry = self._scan_patterns(
            current_price, rsi_now, rsi_vals, bb_upper, bb_lower,
            bb_width_pct, vol_ratio, last_candle_pct, candle_changes,
            ema_dist_pct, closes, lower_dist_pct, upper_dist_pct,
        )

        if entry is not None:
            side, pattern_name, reason = entry
            signals.append(self._build_entry_signal(side, current_price, amount, reason))

        return signals

    # ======================================================================
    # PATTERN SCANNER — any ONE pattern triggers entry
    # ======================================================================

    def _scan_patterns(
        self,
        price: float,
        rsi_now: float,
        rsi_vals: np.ndarray,
        bb_upper: float,
        bb_lower: float,
        bb_width_pct: float,
        vol_ratio: float,
        last_candle_pct: float,
        candle_changes: list[float],
        ema_dist_pct: float,
        closes: np.ndarray,
        lower_dist_pct: float,
        upper_dist_pct: float,
    ) -> tuple[str, str, str] | None:
        """Scan 8 entry patterns. Returns (side, pattern_name, reason) or None."""

        can_short = self.is_futures and config.delta.enable_shorting

        # ── P1: Quick Reversal (highest priority — time-sensitive) ────────
        if self._last_sl_side and (time.monotonic() - self._last_sl_time) < 30:
            if self._last_sl_side == "long" and can_short and rsi_now > 50:
                self._last_sl_side = None
                return ("short", "quick_reversal",
                        f"PATTERN: quick_reversal (reversed long SL, RSI={rsi_now:.1f})")
            elif self._last_sl_side == "short" and rsi_now < 50:
                self._last_sl_side = None
                return ("long", "quick_reversal",
                        f"PATTERN: quick_reversal (reversed short SL, RSI={rsi_now:.1f})")
            self._last_sl_side = None

        # ── P2: RSI Extreme (instant entry) ──────────────────────────────
        if rsi_now < self.RSI_EXTREME_LONG:
            return ("long", "rsi_extreme",
                    f"PATTERN: rsi_extreme (RSI={rsi_now:.1f})")
        if rsi_now > self.RSI_EXTREME_SHORT and can_short:
            return ("short", "rsi_extreme",
                    f"PATTERN: rsi_extreme (RSI={rsi_now:.1f})")

        # ── P3: Volume Spike (enter candle direction) ────────────────────
        if vol_ratio >= self.VOL_SPIKE_RATIO and abs(last_candle_pct) >= self.CANDLE_MIN_PCT:
            if last_candle_pct > 0:
                return ("long", "volume_spike",
                        f"PATTERN: volume_spike (Vol={vol_ratio:.1f}x, candle=+{last_candle_pct:.2f}%)")
            elif can_short:
                return ("short", "volume_spike",
                        f"PATTERN: volume_spike (Vol={vol_ratio:.1f}x, candle={last_candle_pct:.2f}%)")

        # ── P4: BB Squeeze Breakout ──────────────────────────────────────
        if bb_width_pct < self.BB_SQUEEZE_WIDTH_PCT:
            if price > bb_upper:
                return ("long", "bb_squeeze_break",
                        f"PATTERN: bb_squeeze_break (BBW={bb_width_pct:.2f}%, break=upper)")
            elif price < bb_lower and can_short:
                return ("short", "bb_squeeze_break",
                        f"PATTERN: bb_squeeze_break (BBW={bb_width_pct:.2f}%, break=lower)")

        # ── P5: Mean Reversion (price far from EMA → revert) ─────────────
        if abs(ema_dist_pct) >= self.MEAN_REVERSION_PCT:
            if ema_dist_pct < 0:
                # Price below EMA → long (revert up)
                return ("long", "mean_reversion",
                        f"PATTERN: mean_reversion (price {ema_dist_pct:+.2f}% from EMA)")
            elif can_short:
                # Price above EMA → short (revert down)
                return ("short", "mean_reversion",
                        f"PATTERN: mean_reversion (price {ema_dist_pct:+.2f}% from EMA)")

        # ── P6: Candle Pattern (3 consecutive → fade) ────────────────────
        if len(candle_changes) >= 3:
            all_red = all(c < -self.CANDLE_MIN_PCT for c in candle_changes)
            all_green = all(c > self.CANDLE_MIN_PCT for c in candle_changes)
            if all_red:
                return ("long", "candle_pattern",
                        f"PATTERN: candle_pattern (3 red candles: {', '.join(f'{c:.2f}%' for c in candle_changes)})")
            elif all_green and can_short:
                return ("short", "candle_pattern",
                        f"PATTERN: candle_pattern (3 green candles: {', '.join(f'{c:.2f}%' for c in candle_changes)})")

        # ── P7: RSI Divergence ───────────────────────────────────────────
        if len(closes) >= 10 and len(rsi_vals) >= 10:
            # Look at last 5 and previous 5 for divergence
            recent_price_low = float(np.min(closes[-5:]))
            prev_price_low = float(np.min(closes[-10:-5]))
            recent_rsi_low = float(np.min(rsi_vals[-5:]))
            prev_rsi_low = float(np.min(rsi_vals[-10:-5]))

            recent_price_high = float(np.max(closes[-5:]))
            prev_price_high = float(np.max(closes[-10:-5]))
            recent_rsi_high = float(np.max(rsi_vals[-5:]))
            prev_rsi_high = float(np.max(rsi_vals[-10:-5]))

            # Bullish divergence: price lower low + RSI higher low
            if (recent_price_low < prev_price_low and recent_rsi_low > prev_rsi_low
                    and rsi_now < 45):
                return ("long", "rsi_divergence",
                        f"PATTERN: rsi_divergence (price LL ${recent_price_low:.2f}<${prev_price_low:.2f}, "
                        f"RSI HL {recent_rsi_low:.1f}>{prev_rsi_low:.1f})")
            # Bearish divergence: price higher high + RSI lower high
            if (can_short and recent_price_high > prev_price_high
                    and recent_rsi_high < prev_rsi_high and rsi_now > 55):
                return ("short", "rsi_divergence",
                        f"PATTERN: rsi_divergence (price HH ${recent_price_high:.2f}>${prev_price_high:.2f}, "
                        f"RSI LH {recent_rsi_high:.1f}<{prev_rsi_high:.1f})")

        # ── P8: BB Touch + Confirmation ──────────────────────────────────
        if lower_dist_pct <= 0.3:  # within 0.3% of lower BB
            confirmations = []
            if rsi_now < self.BB_TOUCH_CONFIRM_RSI_L:
                confirmations.append(f"RSI={rsi_now:.1f}")
            if vol_ratio >= 1.2:
                confirmations.append(f"Vol={vol_ratio:.1f}x")
            if last_candle_pct < -self.CANDLE_MIN_PCT:
                confirmations.append(f"candle={last_candle_pct:.2f}%")
            if confirmations:
                return ("long", "bb_touch_confirm",
                        f"PATTERN: bb_touch_confirm (lower BB, {' + '.join(confirmations)})")

        if upper_dist_pct <= 0.3 and can_short:
            confirmations = []
            if rsi_now > self.BB_TOUCH_CONFIRM_RSI_S:
                confirmations.append(f"RSI={rsi_now:.1f}")
            if vol_ratio >= 1.2:
                confirmations.append(f"Vol={vol_ratio:.1f}x")
            if last_candle_pct > self.CANDLE_MIN_PCT:
                confirmations.append(f"candle=+{last_candle_pct:.2f}%")
            if confirmations:
                return ("short", "bb_touch_confirm",
                        f"PATTERN: bb_touch_confirm (upper BB, {' + '.join(confirmations)})")

        return None

    # ======================================================================
    # EXIT LOGIC
    # ======================================================================

    def _check_exits(self, current_price: float, rsi_now: float) -> list[Signal]:
        """Check all exit conditions for the current position."""
        signals: list[Signal] = []
        hold_seconds = time.monotonic() - self.entry_time

        if self.position_side == "long":
            pnl_pct = ((current_price - self.entry_price) / self.entry_price) * 100
            self.highest_since_entry = max(self.highest_since_entry, current_price)

            if pnl_pct >= self.TRAILING_ACTIVATE_PCT:
                trail_stop = self.highest_since_entry * (1 - self.TRAILING_DISTANCE_PCT / 100)
            else:
                trail_stop = self.entry_price * (1 - self.STOP_LOSS_PCT / 100)

            tp_price = self.entry_price * (1 + self.TAKE_PROFIT_PCT / 100)

            self.logger.info(
                "[%s] Scalp #%d — LONG | $%.2f | PnL=%+.3f%% | %ds | SL=$%.2f | TP=$%.2f",
                self.pair, self._tick_count, current_price, pnl_pct,
                int(hold_seconds), trail_stop, tp_price,
            )

            if current_price >= tp_price:
                cap_pct = pnl_pct * self.leverage
                signals.append(self._exit_signal(current_price, "long",
                    f"Scalp TP +{pnl_pct:.2f}% price (+{cap_pct:.1f}% capital at {self.leverage}x)"))
                self._record_scalp_result(pnl_pct, "tp")
            elif current_price <= trail_stop:
                cap_pct = pnl_pct * self.leverage
                exit_type = "trail" if pnl_pct >= 0 else "sl"
                signals.append(self._exit_signal(current_price, "long",
                    f"Scalp {exit_type.upper()} {pnl_pct:+.2f}% price ({cap_pct:+.1f}% capital at {self.leverage}x)"))
                self._record_scalp_result(pnl_pct, exit_type)
                self._last_sl_side = "long"
                self._last_sl_time = time.monotonic()
            elif hold_seconds >= self.MAX_HOLD_SECONDS:
                cap_pct = pnl_pct * self.leverage
                signals.append(self._exit_signal(current_price, "long",
                    f"Scalp TIMEOUT {pnl_pct:+.2f}% price ({cap_pct:+.1f}% capital) after {int(hold_seconds)}s"))
                self._record_scalp_result(pnl_pct, "timeout")
            elif hold_seconds >= self.FLATLINE_SECONDS and abs(pnl_pct) < self.FLATLINE_MIN_MOVE_PCT:
                cap_pct = pnl_pct * self.leverage
                signals.append(self._exit_signal(current_price, "long",
                    f"Scalp FLATLINE {pnl_pct:+.2f}% (< {self.FLATLINE_MIN_MOVE_PCT}% in {int(hold_seconds)}s)"))
                self._record_scalp_result(pnl_pct, "flatline")

        elif self.position_side == "short":
            pnl_pct = ((self.entry_price - current_price) / self.entry_price) * 100
            self.lowest_since_entry = min(self.lowest_since_entry, current_price)

            if pnl_pct >= self.TRAILING_ACTIVATE_PCT:
                trail_stop = self.lowest_since_entry * (1 + self.TRAILING_DISTANCE_PCT / 100)
            else:
                trail_stop = self.entry_price * (1 + self.STOP_LOSS_PCT / 100)

            tp_price = self.entry_price * (1 - self.TAKE_PROFIT_PCT / 100)

            self.logger.info(
                "[%s] Scalp #%d — SHORT | $%.2f | PnL=%+.3f%% | %ds | SL=$%.2f | TP=$%.2f",
                self.pair, self._tick_count, current_price, pnl_pct,
                int(hold_seconds), trail_stop, tp_price,
            )

            if current_price <= tp_price:
                cap_pct = pnl_pct * self.leverage
                signals.append(self._exit_signal(current_price, "short",
                    f"Scalp TP +{pnl_pct:.2f}% price (+{cap_pct:.1f}% capital at {self.leverage}x)"))
                self._record_scalp_result(pnl_pct, "tp")
            elif current_price >= trail_stop:
                cap_pct = pnl_pct * self.leverage
                exit_type = "trail" if pnl_pct >= 0 else "sl"
                signals.append(self._exit_signal(current_price, "short",
                    f"Scalp {exit_type.upper()} {pnl_pct:+.2f}% price ({cap_pct:+.1f}% capital at {self.leverage}x)"))
                self._record_scalp_result(pnl_pct, exit_type)
                self._last_sl_side = "short"
                self._last_sl_time = time.monotonic()
            elif hold_seconds >= self.MAX_HOLD_SECONDS:
                cap_pct = pnl_pct * self.leverage
                signals.append(self._exit_signal(current_price, "short",
                    f"Scalp TIMEOUT {pnl_pct:+.2f}% price ({cap_pct:+.1f}% capital) after {int(hold_seconds)}s"))
                self._record_scalp_result(pnl_pct, "timeout")
            elif hold_seconds >= self.FLATLINE_SECONDS and abs(pnl_pct) < self.FLATLINE_MIN_MOVE_PCT:
                cap_pct = pnl_pct * self.leverage
                signals.append(self._exit_signal(current_price, "short",
                    f"Scalp FLATLINE {pnl_pct:+.2f}% (< {self.FLATLINE_MIN_MOVE_PCT}% in {int(hold_seconds)}s)"))
                self._record_scalp_result(pnl_pct, "flatline")

        return signals

    # ======================================================================
    # POSITION SIZING
    # ======================================================================

    def _calculate_position_size(self, current_price: float, available: float) -> float | None:
        """Calculate position amount in coin terms. Returns None if can't size."""
        exchange_capital = self.risk_manager.get_exchange_capital(self._exchange_id)
        capital = exchange_capital * (self.capital_pct / 100)
        capital = min(capital, available)

        if self.is_futures:
            from alpha.trade_executor import DELTA_CONTRACT_SIZE
            contract_size = DELTA_CONTRACT_SIZE.get(self.pair, 0)
            if contract_size <= 0:
                self.logger.warning("[%s] Unknown Delta contract size — skipping", self.pair)
                return None

            one_contract_collateral = (contract_size * current_price) / self.leverage
            if one_contract_collateral > available:
                if self._tick_count % 30 == 0:
                    self.logger.info(
                        "[%s] 1 contract needs $%.2f collateral > $%.2f available — skipping",
                        self.pair, one_contract_collateral, available,
                    )
                return None

            contracts = int(capital * self.leverage / (contract_size * current_price))
            contracts = max(contracts, 1)
            total_collateral = contracts * one_contract_collateral
            if total_collateral > available:
                contracts = max(1, int(available / one_contract_collateral))
                total_collateral = contracts * one_contract_collateral

            amount = contracts * contract_size

            self.logger.debug(
                "[%s] Sizing (futures): capital=$%.2f, avail=$%.2f "
                "→ %d contracts (%.6f coin, collateral=$%.2f, %dx)",
                self.pair, capital, available, contracts,
                amount, total_collateral, self.leverage,
            )
        else:
            amount = capital / current_price
            self.logger.debug(
                "[%s] Sizing (spot): capital=$%.2f, avail=$%.2f → amount=%.8f",
                self.pair, capital, available, amount,
            )

        return amount

    # ======================================================================
    # SIGNAL BUILDERS
    # ======================================================================

    def _build_entry_signal(self, side: str, price: float, amount: float, reason: str) -> Signal:
        """Build an entry signal for a detected pattern."""
        self.logger.info("[%s] %s → %s entry", self.pair, reason, side.upper())

        if side == "long":
            sl = price * (1 - self.STOP_LOSS_PCT / 100)
            tp = price * (1 + self.TAKE_PROFIT_PCT / 100)
            return Signal(
                side="buy",
                price=price,
                amount=amount,
                order_type="market",
                reason=reason,
                strategy=self.name,
                pair=self.pair,
                stop_loss=sl,
                take_profit=tp,
                leverage=self.leverage if self.is_futures else 1,
                position_type="long" if self.is_futures else "spot",
                exchange_id="delta" if self.is_futures else "binance",
                metadata={"pending_side": "long", "pending_amount": amount},
            )
        else:  # short
            sl = price * (1 + self.STOP_LOSS_PCT / 100)
            tp = price * (1 - self.TAKE_PROFIT_PCT / 100)
            return Signal(
                side="sell",
                price=price,
                amount=amount,
                order_type="market",
                reason=reason,
                strategy=self.name,
                pair=self.pair,
                stop_loss=sl,
                take_profit=tp,
                leverage=self.leverage,
                position_type="short",
                exchange_id="delta",
                metadata={"pending_side": "short", "pending_amount": amount},
            )

    def _exit_signal(self, price: float, side: str, reason: str) -> Signal:
        """Build an exit signal for the current position."""
        amount = self.entry_amount
        if amount <= 0:
            exchange_capital = self.risk_manager.get_exchange_capital(self._exchange_id)
            capital = exchange_capital * (self.capital_pct / 100)
            amount = capital / price
            if self.is_futures:
                amount *= self.leverage

        exit_side = "sell" if side == "long" else "buy"
        return Signal(
            side=exit_side,
            price=price,
            amount=amount,
            order_type="market",
            reason=reason,
            strategy=self.name,
            pair=self.pair,
            leverage=self.leverage if self.is_futures else 1,
            position_type=side if self.is_futures else "spot",
            reduce_only=self.is_futures,
            exchange_id="delta" if self.is_futures else "binance",
        )

    # ======================================================================
    # ORDER FILL / REJECTION CALLBACKS
    # ======================================================================

    def on_fill(self, signal: Signal, order: dict) -> None:
        """Called by _run_loop when an order fills — NOW safe to track position."""
        pending_side = signal.metadata.get("pending_side")
        pending_amount = signal.metadata.get("pending_amount", 0.0)
        if pending_side:
            fill_price = order.get("average") or order.get("price") or signal.price
            filled_amount = order.get("filled") or pending_amount or signal.amount
            self._open_position(pending_side, fill_price, filled_amount)
            self.logger.info(
                "[%s] Order FILLED — tracking %s position @ $%.2f, amount=%.8f",
                self.pair, pending_side, fill_price, filled_amount,
            )

    def on_rejected(self, signal: Signal) -> None:
        """Called by _run_loop when an order fails — do NOT track position."""
        pending_side = signal.metadata.get("pending_side")
        if pending_side:
            self.logger.warning(
                "[%s] Order FAILED — NOT tracking %s position (phantom prevention)",
                self.pair, pending_side,
            )

    # ======================================================================
    # POSITION MANAGEMENT
    # ======================================================================

    def _open_position(self, side: str, price: float, amount: float = 0.0) -> None:
        self.in_position = True
        self.position_side = side
        self.entry_price = price
        self.entry_amount = amount
        self.entry_time = time.monotonic()
        self.highest_since_entry = price
        self.lowest_since_entry = price
        self._positions_on_pair += 1
        self._hourly_trades.append(time.time())

    def _record_scalp_result(self, pnl_pct: float, exit_type: str) -> None:
        # Gross P&L = price change * notional (entry_amount is coin qty)
        notional = self.entry_price * self.entry_amount
        gross_pnl = notional * (pnl_pct / 100)

        # Estimate trading fees (entry + exit): ~0.05% per side on Delta, ~0.1% on Binance
        fee_rate = 0.001 if self._exchange_id == "delta" else 0.002  # round-trip
        est_fees = notional * fee_rate
        net_pnl = gross_pnl - est_fees

        # Capital P&L % (leveraged)
        capital_pnl_pct = pnl_pct * self.leverage

        self.hourly_pnl += net_pnl
        self._daily_scalp_loss += net_pnl if net_pnl < 0 else 0

        if pnl_pct >= 0:
            self.hourly_wins += 1
            self._consecutive_losses = 0
        else:
            self.hourly_losses += 1
            self._consecutive_losses += 1

        # Duration in human-readable format
        hold_sec = int(time.monotonic() - self.entry_time)
        if hold_sec >= 60:
            duration = f"{hold_sec // 60}m{hold_sec % 60:02d}s"
        else:
            duration = f"{hold_sec}s"

        self.logger.info(
            "[%s] SCALP CLOSED — %s hit %+.2f%% price (%+.2f%% capital at %dx) | "
            "Gross=$%.4f, Net=$%.4f (fees~$%.4f) | Duration: %s | "
            "W/L=%d/%d, streak=%d, daily=$%.4f",
            self.pair, exit_type.upper(), pnl_pct, capital_pnl_pct, self.leverage,
            gross_pnl, net_pnl, est_fees, duration,
            self.hourly_wins, self.hourly_losses,
            self._consecutive_losses, self._daily_scalp_loss,
        )

        if self._consecutive_losses >= self.CONSECUTIVE_LOSS_PAUSE:
            self._paused_until = time.monotonic() + self.PAUSE_DURATION_SEC
            self.logger.warning(
                "[%s] Scalp PAUSING %dmin — %d consecutive losses",
                self.pair, self.PAUSE_DURATION_SEC // 60, self._consecutive_losses,
            )

        self.in_position = False
        self.position_side = None
        self.entry_price = 0.0
        self.entry_amount = 0.0
        self._positions_on_pair = max(0, self._positions_on_pair - 1)

    # ======================================================================
    # STATS
    # ======================================================================

    def reset_hourly_stats(self) -> dict[str, Any]:
        stats = {
            "pair": self.pair,
            "wins": self.hourly_wins,
            "losses": self.hourly_losses,
            "pnl": self.hourly_pnl,
            "trades": self.hourly_wins + self.hourly_losses,
        }
        self.hourly_wins = 0
        self.hourly_losses = 0
        self.hourly_pnl = 0.0
        return stats

    def reset_daily_stats(self) -> None:
        self._daily_scalp_loss = 0.0
        self._consecutive_losses = 0
        self._paused_until = 0.0

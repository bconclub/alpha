# Changelog

All notable changes to the Alpha trading bot engine.

Format: `MAJOR.MINOR.PATCH`
- **Major**: Architecture changes (1.x = monorepo era)
- **Minor**: New features (strategies, exchanges)
- **Patch**: Bug fixes, parameter tweaks

---

## v2.0.0 — 2026-02-15 — Delta Scalping Agent

**FULL REFOCUS: Delta-only, aggressive momentum scalping.**

### Architecture
- **Delta-only mode**: Disabled ALL Binance trading (kept as fallback exchange reference)
- **SOUL.md**: Bot identity document read on startup, guides behavior
- **Grid strategy removed**: No longer used
- **Binance dust cleanup**: All Binance open trades auto-closed on startup

### Scalp Strategy Rewrite
- **3-second ticks** (was 5s) — faster reaction to momentum
- **1.0% TP / 0.50% SL** (2:1 R/R at 20x leverage)
- **Trailing stop**: activate at 0.60%, trail at 0.30%
- **Profit lock**: SL moves to breakeven after +0.50% — winners never become losers
- **15-minute timeout** (was 45 min) — don't hold forever
- **NEVER IDLE**: If no signal for 5 min, force entry on EMA slope direction
- **60-second momentum detection**: 0.10% price move in 60s triggers entry
- **ONE signal is enough**: RSI extreme, volume spike, BB breakout, acceleration, or 60s momentum
- **Immediate re-entry**: After profitable exit, hunt for next trade instantly

### Leverage & Position Sizing
- **20x leverage** (was 5x) on Delta futures
- **3 contracts per trade** ($3.12 collateral at 20x)
- **Max 3 concurrent positions** ($9.36 total collateral)

### Critical P&L Fix
- **Fixed**: P&L calculation for Delta futures — now correctly multiplies by `contract_size`
  - 1 ETH contract = 0.01 ETH, not 1 ETH
  - Formula: `pnl = (exit - entry) × contract_size × contracts`
  - Fixed in 4 places: `_close_trade_in_db`, `_open_trade_in_db`, `_notify_trade`, `_record_scalp_result`
- **Fixed**: Retroactive SQL migration to correct all existing trades in DB
- **Fixed**: Binance dust trades zeroed out (pnl=0, never properly closed)

### Daily Expiry Awareness
- **New**: Delta India daily contracts expire at 5:30 PM IST
- **New**: No new entries within 30 min of expiry (5:00 PM IST)
- **New**: Force close all positions 5 min before expiry (5:25 PM IST)

### Position Restore
- **Improved**: Uses Delta `fetch_positions()` for real contract verification on restart
- **New**: Discovers positions on exchange not in DB (creates records)
- **New**: Injects restored position state into strategy instances

### Other
- **New**: EXIT FAILED alert suppression — only alerts once per pair (no spam)
- **Updated**: Startup banner shows version, leverage, and soul reference
- **Removed**: numpy dependency (no longer needed)

## v1.1.0 — 2026-02-15
- **New**: Pattern-based scalp entry system (8 patterns, any-one-triggers)
- **New**: Version tracking system (VERSION file, CHANGELOG, auto-bump)
- **New**: Phantom position prevention (`on_fill`/`on_rejected` hooks in base strategy)
- **New**: Flatline exit — close if < 0.1% move for 30 minutes
- **Updated**: TP/SL widened for profitability (1.5% TP / 0.75% SL, 2:1 R/R)
- **Updated**: Trailing stop (activate 0.80%, trail 0.40%)
- **Updated**: Timeout extended to 45 minutes
- **Updated**: RSI entry thresholds tightened (LONG < 40, SHORT > 60)
- **Updated**: Delta contract conversion moved before validation
- First real Delta futures trades! 3 round-trips, net +$0.024

## v1.0.8 — 2026-02-14
- **Fix**: Phantom position prevention (`on_fill`/`on_rejected` hooks)
- **Fix**: Delta contract conversion (0.01 ETH / 0.01 = 1 contract, not 0.01)
- **Fix**: Floating-point safety in contract conversion (`round()` not `int()`)

## v1.0.7 — 2026-02-14
- **Fix**: Trade lifecycle (open → close in same DB row, not double INSERT)
- **Fix**: Stop trading when balance < minimum (per-exchange tracking)
- **Fix**: Max 2 positions per exchange
- **Fix**: Exit uses actual balance (fee-adjusted, truncated to LOT_SIZE step)
- **New**: Restore open positions from DB on startup (verify against exchange)
- **New**: Real portfolio balance in hourly report (USDT + held assets)

## v1.0.6 — 2026-02-14
- **Fix**: Supabase `trades_strategy_check` constraint (added 'scalp' value)
- First real Binance trades executed! (ETH, BTC, SOL)

## v1.0.5 — 2026-02-14
- **Fix**: Binance minimum notional ($5) — bumped spot capital to 50%
- **Fix**: Live balance tracking (not STARTING_CAPITAL)
- **New**: Per-exchange capital sizing (binance_capital, delta_capital)

## v1.0.4 — 2026-02-14
- **Fix**: Scalp entry loosened to 2-of-3 conditions (was all 3)

## v1.0.3 — 2026-02-14
- **Fix**: Risk manager leverage calculation (check collateral not notional)
- **Fix**: Delta order placement parameters (integer contracts, leverage params)

## v1.0.2 — 2026-02-14
- **New**: Scalp strategy with 10s ticks
- Params: 0.25% TP, 0.15% SL, 30% capital

## v1.0.1 — 2026-02-14
- **Fix**: Strategy execution loops (async tick loop)
- All strategies now tick and log continuously

## v1.0.0 — 2026-02-14
- Initial monorepo deployment (engine + dashboard)
- Strategies: Momentum, Futures Momentum, Grid, Arbitrage
- Exchanges: Binance (spot), Delta Exchange India (futures)
- Dashboard v2 command center on Vercel
- IST timezone support (daily reset at midnight IST)
- Telegram alerts (trade, market, risk, daily/hourly reports)

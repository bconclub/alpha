-- ============================================================================
-- OPTIONS SCALP MIGRATION — Run in Supabase SQL Editor
-- Adds 'options_scalp' to the strategy check constraints on trades and strategy_log
-- ============================================================================

-- 1. trades.strategy — drop and recreate to include 'options_scalp'
alter table public.trades drop constraint if exists trades_strategy_check;
alter table public.trades add constraint trades_strategy_check
    check (strategy in ('grid', 'momentum', 'arbitrage', 'futures_momentum', 'scalp', 'options_scalp'));

-- 2. strategy_log.strategy_selected — drop and recreate to include 'options_scalp'
alter table public.strategy_log drop constraint if exists strategy_log_strategy_selected_check;
alter table public.strategy_log add constraint strategy_log_strategy_selected_check
    check (strategy_selected in ('grid', 'momentum', 'arbitrage', 'futures_momentum', 'scalp', 'options_scalp', 'paused'));

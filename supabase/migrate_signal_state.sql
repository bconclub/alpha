-- ============================================================================
-- Migration: Add per-tick signal state to strategy_log
-- The bot writes which signals (MOM, VOL, RSI, BB) are active per pair,
-- so the dashboard displays the SAME state the bot sees — no independent calc.
-- Run in Supabase SQL Editor.
-- ============================================================================

-- ── Add signal state columns ────────────────────────────────────────────────

alter table public.strategy_log
    add column if not exists signal_count  smallint,       -- 0-4: how many of 4 signals are active
    add column if not exists signal_side   text,           -- "long", "short", or null (scanning)
    add column if not exists signal_mom    boolean,        -- momentum signal active
    add column if not exists signal_vol    boolean,        -- volume spike signal active
    add column if not exists signal_rsi    boolean,        -- RSI extreme signal active
    add column if not exists signal_bb     boolean;        -- BB mean-reversion signal active

-- ── Recreate v_strategy_latest with new columns ─────────────────────────────

drop view if exists public.v_strategy_latest;

create view public.v_strategy_latest as
select distinct on (pair)
    id, timestamp, pair, exchange,
    market_condition, strategy_selected, reason,
    adx, rsi, atr, bb_width, bb_upper, bb_lower,
    volume_ratio, signal_strength,
    macd_value, macd_signal, macd_histogram,
    current_price, entry_distance_pct, price_change_15m,
    price_change_1h, price_change_24h,
    plus_di, minus_di, direction,
    signal_count, signal_side,
    signal_mom, signal_vol, signal_rsi, signal_bb
from   public.strategy_log
order  by pair, timestamp desc;

-- ── Also update latest_strategy_log if it exists ────────────────────────────
-- (Some dashboards use this view instead)

drop view if exists public.latest_strategy_log;

create view public.latest_strategy_log as
select distinct on (pair, exchange)
    *
from   public.strategy_log
order  by pair, exchange, created_at desc;

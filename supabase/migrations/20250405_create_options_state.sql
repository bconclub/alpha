-- ═══════════════════════════════════════════════════════════════════════════════
-- Migration: Create options_state table with all dashboard fields
-- Generated from: engine/alpha/strategies/options_scalp.py state dict
-- Date: 2025-04-05
-- ═══════════════════════════════════════════════════════════════════════════════

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Drop existing table (use with caution in production!)
DROP TABLE IF EXISTS options_state CASCADE;

-- Create options_state table
CREATE TABLE options_state (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pair TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Core market data
    spot_price NUMERIC,
    expiry TIMESTAMPTZ,
    expiry_label TEXT,
    atm_strike NUMERIC,
    call_premium NUMERIC,
    put_premium NUMERIC,
    
    -- Signal data
    signal_strength INTEGER,
    signal_side TEXT,
    signal_reason TEXT,
    
    -- Position data (null when no position)
    position_side TEXT,
    position_strike NUMERIC,
    position_symbol TEXT,
    entry_premium NUMERIC,
    current_premium NUMERIC,
    pnl_pct NUMERIC,
    pnl_usd NUMERIC,
    trailing_active BOOLEAN DEFAULT FALSE,
    highest_premium NUMERIC,
    position_opened_at TIMESTAMPTZ,
    
    -- Chain data (JSON arrays)
    chain_calls JSONB,
    chain_puts JSONB,
    
    -- Bot state
    bot_state TEXT,
    target_strike NUMERIC,
    balance NUMERIC,
    
    -- Squeeze info (JSON object)
    squeeze_info JSONB,
    
    -- Signals panel (JSON object with nested fields)
    signals_panel JSONB,
    exit_config JSONB,
    entry_config JSONB,
    peak_trail_pending_ticks INTEGER DEFAULT 0,
    spot_momentum_20s_pct NUMERIC,
    
    -- Top-level BB Squeeze fields (read directly by dashboard)
    bb_width_pct NUMERIC,
    bb_width_threshold NUMERIC,
    squeeze_active BOOLEAN DEFAULT FALSE,
    bb_position NUMERIC,
    direction_bias TEXT,
    premium_current_ask NUMERIC,
    premium_cheap_threshold NUMERIC,
    premium_lowest_ask NUMERIC,
    premium_highest_ask NUMERIC,
    last_squeeze_action TEXT,
    last_action_at TIMESTAMPTZ,
    
    -- Breakout confirmation state (GPFC #20)
    breakout_state TEXT,
    breakout_direction TEXT,
    breakout_confirmation_secs_remaining INTEGER,
    breakout_detected_at TIMESTAMPTZ,
    breakout_premium_at_detection NUMERIC,
    breakout_velocity_pct NUMERIC,
    momentum_60s_pct NUMERIC,
    breakeven_stop_armed BOOLEAN DEFAULT FALSE
);

-- Create indexes
CREATE INDEX idx_options_state_pair ON options_state(pair);
CREATE INDEX idx_options_state_updated ON options_state(updated_at DESC);

-- Enable Row Level Security
ALTER TABLE options_state ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if any
DROP POLICY IF EXISTS "Allow public read" ON options_state;
DROP POLICY IF EXISTS "Allow service write" ON options_state;

-- Create policy for public read access
CREATE POLICY "Allow public read" ON options_state
    FOR SELECT USING (true);

-- Create policy for service role write access
CREATE POLICY "Allow service write" ON options_state
    FOR ALL 
    TO authenticated, anon, service_role
    USING (true) 
    WITH CHECK (true);

-- Create function to auto-update updated_at
CREATE OR REPLACE FUNCTION update_options_state_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for auto-updating updated_at
CREATE TRIGGER options_state_updated_at
    BEFORE UPDATE ON options_state
    FOR EACH ROW
    EXECUTE FUNCTION update_options_state_updated_at();

-- Add table comment
COMMENT ON TABLE options_state IS 'Real-time options strategy state for dashboard display (GPFC #20)';

-- Verify columns
-- SELECT column_name, data_type 
-- FROM information_schema.columns 
-- WHERE table_name = 'options_state' 
-- ORDER BY ordinal_position;

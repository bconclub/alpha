-- ═══════════════════════════════════════════════════════════════════════════════
-- GPFC #20: Complete options_state schema with all dashboard fields
-- ═══════════════════════════════════════════════════════════════════════════════

-- Drop existing table if rebuilding (use with caution in production!)
-- DROP TABLE IF EXISTS options_state;

-- Create options_state table with complete schema
CREATE TABLE IF NOT EXISTS options_state (
    -- Primary key & identification
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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
    position_side TEXT,           -- 'call' | 'put' | null
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
    
    -- Top-level BB Squeeze fields (for direct dashboard access)
    bb_width_pct NUMERIC,
    bb_width_threshold NUMERIC,
    squeeze_active BOOLEAN DEFAULT FALSE,
    bb_position NUMERIC,
    direction_bias TEXT,          -- 'CALL' | 'PUT' | 'NEUTRAL'
    premium_current_ask NUMERIC,
    premium_cheap_threshold NUMERIC,
    premium_lowest_ask NUMERIC,
    premium_highest_ask NUMERIC,
    last_squeeze_action TEXT,
    last_action_at TIMESTAMPTZ,
    
    -- Breakout confirmation state (GPFC #20)
    breakout_state TEXT,          -- 'NONE' | 'DETECTED' | 'CONFIRMED' | 'FAKEOUT'
    breakout_direction TEXT,      -- 'UP' | 'DOWN'
    breakout_confirmation_secs_remaining INTEGER,
    breakout_detected_at TIMESTAMPTZ,
    breakout_premium_at_detection NUMERIC,
    breakout_velocity_pct NUMERIC,
    momentum_60s_pct NUMERIC,
    breakeven_stop_armed BOOLEAN DEFAULT FALSE,
    
    -- Last exit summary
    last_exit_type TEXT,
    last_exit_pnl_pct NUMERIC,
    last_exit_pnl_usd NUMERIC
);

-- Create index for efficient lookups
CREATE INDEX IF NOT EXISTS idx_options_state_pair ON options_state(pair);
CREATE INDEX IF NOT EXISTS idx_options_state_updated ON options_state(updated_at DESC);

-- Enable Row Level Security
ALTER TABLE options_state ENABLE ROW LEVEL SECURITY;

-- Create policy for public read access (adjust as needed)
DROP POLICY IF EXISTS "Allow public read access" ON options_state;
CREATE POLICY "Allow public read access" ON options_state
    FOR SELECT USING (true);

-- Create policy for insert/update from service role
DROP POLICY IF EXISTS "Allow service role insert/update" ON options_state;
CREATE POLICY "Allow service role insert/update" ON options_state
    FOR ALL USING (true) WITH CHECK (true);

-- Create function to auto-update updated_at
CREATE OR REPLACE FUNCTION update_options_state_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for auto-updating updated_at
DROP TRIGGER IF EXISTS options_state_updated_at ON options_state;
CREATE TRIGGER options_state_updated_at
    BEFORE UPDATE ON options_state
    FOR EACH ROW
    EXECUTE FUNCTION update_options_state_updated_at();

-- ═══════════════════════════════════════════════════════════════════════════════
-- COMMENTS: Field documentation
-- ═══════════════════════════════════════════════════════════════════════════════

COMMENT ON TABLE options_state IS 'Real-time options strategy state for dashboard display (GPFC #20)';

COMMENT ON COLUMN options_state.pair IS 'Trading pair (e.g., BTC/USD)';
COMMENT ON COLUMN options_state.spot_price IS 'Current spot price of underlying';
COMMENT ON COLUMN options_state.expiry IS 'Selected option expiry datetime';
COMMENT ON COLUMN options_state.position_side IS 'Active position: call, put, or null';
COMMENT ON COLUMN options_state.pnl_pct IS 'Current P&L percentage';
COMMENT ON COLUMN options_state.squeeze_active IS 'Whether BB squeeze is currently detected';
COMMENT ON COLUMN options_state.bb_width_pct IS 'Current Bollinger Band width percentage';
COMMENT ON COLUMN options_state.direction_bias IS 'Directional bias: CALL (long), PUT (short), or NEUTRAL';
COMMENT ON COLUMN options_state.breakout_state IS 'GPFC #20: Breakout confirmation state machine';
COMMENT ON COLUMN options_state.breakout_direction IS 'GPFC #20: UP (call) or DOWN (put)';
COMMENT ON COLUMN options_state.breakout_confirmation_secs_remaining IS 'GPFC #20: Countdown for confirmation window';
COMMENT ON COLUMN options_state.signals_panel IS 'Nested JSON with all squeeze panel data';

-- ═══════════════════════════════════════════════════════════════════════════════
-- VERIFICATION: List all columns
-- ═══════════════════════════════════════════════════════════════════════════════

-- Run this to verify all columns exist:
-- SELECT column_name, data_type 
-- FROM information_schema.columns 
-- WHERE table_name = 'options_state' 
-- ORDER BY ordinal_position;

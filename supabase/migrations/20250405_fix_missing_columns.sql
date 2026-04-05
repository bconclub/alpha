-- ═══════════════════════════════════════════════════════════════════════════════
-- Fix: Add missing columns to options_state table
-- Run this if the original migration failed partially
-- ═══════════════════════════════════════════════════════════════════════════════

-- Add missing columns (safe to run multiple times - will skip if exists)
DO $$
BEGIN
    -- Top-level squeeze fields
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'direction_bias') THEN
        ALTER TABLE options_state ADD COLUMN direction_bias TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'bb_width_pct') THEN
        ALTER TABLE options_state ADD COLUMN bb_width_pct NUMERIC;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'bb_width_threshold') THEN
        ALTER TABLE options_state ADD COLUMN bb_width_threshold NUMERIC;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'squeeze_active') THEN
        ALTER TABLE options_state ADD COLUMN squeeze_active BOOLEAN DEFAULT FALSE;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'bb_position') THEN
        ALTER TABLE options_state ADD COLUMN bb_position NUMERIC;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'premium_current_ask') THEN
        ALTER TABLE options_state ADD COLUMN premium_current_ask NUMERIC;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'premium_cheap_threshold') THEN
        ALTER TABLE options_state ADD COLUMN premium_cheap_threshold NUMERIC;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'premium_lowest_ask') THEN
        ALTER TABLE options_state ADD COLUMN premium_lowest_ask NUMERIC;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'premium_highest_ask') THEN
        ALTER TABLE options_state ADD COLUMN premium_highest_ask NUMERIC;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'last_squeeze_action') THEN
        ALTER TABLE options_state ADD COLUMN last_squeeze_action TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'last_action_at') THEN
        ALTER TABLE options_state ADD COLUMN last_action_at TIMESTAMPTZ;
    END IF;
    
    -- Breakout confirmation fields
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'breakout_state') THEN
        ALTER TABLE options_state ADD COLUMN breakout_state TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'breakout_direction') THEN
        ALTER TABLE options_state ADD COLUMN breakout_direction TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'breakout_confirmation_secs_remaining') THEN
        ALTER TABLE options_state ADD COLUMN breakout_confirmation_secs_remaining INTEGER;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'breakout_detected_at') THEN
        ALTER TABLE options_state ADD COLUMN breakout_detected_at TIMESTAMPTZ;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'breakout_premium_at_detection') THEN
        ALTER TABLE options_state ADD COLUMN breakout_premium_at_detection NUMERIC;
    END IF;
    
    -- JSONB fields
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'squeeze_info') THEN
        ALTER TABLE options_state ADD COLUMN squeeze_info JSONB;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'signals_panel') THEN
        ALTER TABLE options_state ADD COLUMN signals_panel JSONB;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'chain_calls') THEN
        ALTER TABLE options_state ADD COLUMN chain_calls JSONB;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'chain_puts') THEN
        ALTER TABLE options_state ADD COLUMN chain_puts JSONB;
    END IF;
    
    -- Position fields
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'position_side') THEN
        ALTER TABLE options_state ADD COLUMN position_side TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'position_strike') THEN
        ALTER TABLE options_state ADD COLUMN position_strike NUMERIC;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'position_symbol') THEN
        ALTER TABLE options_state ADD COLUMN position_symbol TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'entry_premium') THEN
        ALTER TABLE options_state ADD COLUMN entry_premium NUMERIC;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'current_premium') THEN
        ALTER TABLE options_state ADD COLUMN current_premium NUMERIC;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'pnl_pct') THEN
        ALTER TABLE options_state ADD COLUMN pnl_pct NUMERIC;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'pnl_usd') THEN
        ALTER TABLE options_state ADD COLUMN pnl_usd NUMERIC;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'trailing_active') THEN
        ALTER TABLE options_state ADD COLUMN trailing_active BOOLEAN DEFAULT FALSE;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'highest_premium') THEN
        ALTER TABLE options_state ADD COLUMN highest_premium NUMERIC;
    END IF;
    
    -- Bot state fields
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'bot_state') THEN
        ALTER TABLE options_state ADD COLUMN bot_state TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'target_strike') THEN
        ALTER TABLE options_state ADD COLUMN target_strike NUMERIC;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'balance') THEN
        ALTER TABLE options_state ADD COLUMN balance NUMERIC;
    END IF;
    
    -- Market data fields
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'spot_price') THEN
        ALTER TABLE options_state ADD COLUMN spot_price NUMERIC;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'expiry') THEN
        ALTER TABLE options_state ADD COLUMN expiry TIMESTAMPTZ;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'expiry_label') THEN
        ALTER TABLE options_state ADD COLUMN expiry_label TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'atm_strike') THEN
        ALTER TABLE options_state ADD COLUMN atm_strike NUMERIC;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'call_premium') THEN
        ALTER TABLE options_state ADD COLUMN call_premium NUMERIC;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'put_premium') THEN
        ALTER TABLE options_state ADD COLUMN put_premium NUMERIC;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'signal_strength') THEN
        ALTER TABLE options_state ADD COLUMN signal_strength INTEGER;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'signal_side') THEN
        ALTER TABLE options_state ADD COLUMN signal_side TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'options_state' AND column_name = 'signal_reason') THEN
        ALTER TABLE options_state ADD COLUMN signal_reason TEXT;
    END IF;
    
END $$;

-- Verify all columns exist
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'options_state' 
ORDER BY ordinal_position;

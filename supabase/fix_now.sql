-- GPFC #22 Part 1 — Fix DB crash: Add missing columns to options_state
-- Run this on Supabase immediately

ALTER TABLE options_state 
ADD COLUMN IF NOT EXISTS breakout_velocity_pct float,
ADD COLUMN IF NOT EXISTS breakout_confirmation_secs_remaining int,
ADD COLUMN IF NOT EXISTS breakout_direction text,
ADD COLUMN IF NOT EXISTS breakout_state text DEFAULT 'NONE';

-- Add comment for documentation
COMMENT ON COLUMN options_state.breakout_velocity_pct IS 'Breakout velocity: % price move in last 3 candles (GPFC #21)';
COMMENT ON COLUMN options_state.breakout_confirmation_secs_remaining IS 'Seconds remaining in confirmation window (GPFC #21)';
COMMENT ON COLUMN options_state.breakout_direction IS 'Breakout direction: UP or DOWN (GPFC #21)';
COMMENT ON COLUMN options_state.breakout_state IS 'Breakout state: NONE, DETECTED, CONFIRMED, FAKEOUT (GPFC #21)';

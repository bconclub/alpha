-- Add 'reconcile' and 'toggle_exchange' to bot_commands CHECK constraint.
-- Run once against the live Supabase DB.

-- Drop the old constraint
ALTER TABLE public.bot_commands DROP CONSTRAINT IF EXISTS bot_commands_command_check;

-- Re-create with expanded allowed values
ALTER TABLE public.bot_commands ADD CONSTRAINT bot_commands_command_check
  CHECK (command IN (
    'pause', 'resume', 'force_strategy', 'update_config',
    'update_pair_config', 'close_trade', 'toggle_strategy',
    'toggle_exchange', 'reconcile'
  ));

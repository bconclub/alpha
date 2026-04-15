-- Add metadata JSONB column to trades table for reconciliation tracking
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'trades' AND column_name = 'metadata'
    ) THEN
        ALTER TABLE public.trades ADD COLUMN metadata JSONB DEFAULT NULL;
    END IF;
END $$;

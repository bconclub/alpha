-- ═══════════════════════════════════════════════════════════════════
-- Fix Delta Exchange P&L calculations (retroactive)
--
-- Problem: P&L was calculated using raw contract count as if it were
-- coin amount. 1 contract ETH/USD = 0.01 ETH, not 1 ETH.
--
-- Correct formula:
--   LONG:  gross_pnl = (exit_price - entry_price) × 0.01 × contracts
--   SHORT: gross_pnl = (entry_price - exit_price) × 0.01 × contracts
--   entry_fee = entry_price × 0.01 × contracts × 0.0005
--   exit_fee  = exit_price  × 0.01 × contracts × 0.0005
--   net_pnl   = gross_pnl - entry_fee - exit_fee
--
-- Fee rate: 0.05% taker per side (0.0005 as decimal)
--
-- Also recalculates pnl_pct as return on collateral:
--   collateral = entry_price × 0.01 × contracts / leverage
--   pnl_pct = net_pnl / collateral × 100
-- ═══════════════════════════════════════════════════════════════════

-- Fix LONG trades (ETH) — contract_size = 0.01, fee = 0.05% per side
UPDATE trades
SET
    pnl = (exit_price - entry_price) * 0.01 * amount
          - (entry_price * 0.01 * amount * 0.0005)
          - (exit_price * 0.01 * amount * 0.0005),
    pnl_pct = CASE
        WHEN leverage > 0 AND entry_price > 0
        THEN (
            (exit_price - entry_price) * 0.01 * amount
            - (entry_price * 0.01 * amount * 0.0005)
            - (exit_price * 0.01 * amount * 0.0005)
        ) / (entry_price * 0.01 * amount / leverage) * 100
        ELSE 0
    END
WHERE exchange = 'delta'
  AND position_type = 'long'
  AND status = 'closed'
  AND exit_price IS NOT NULL
  AND (pair LIKE 'ETH%' OR pair LIKE '%ETH%');

-- Fix SHORT trades (ETH)
UPDATE trades
SET
    pnl = (entry_price - exit_price) * 0.01 * amount
          - (entry_price * 0.01 * amount * 0.0005)
          - (exit_price * 0.01 * amount * 0.0005),
    pnl_pct = CASE
        WHEN leverage > 0 AND entry_price > 0
        THEN (
            (entry_price - exit_price) * 0.01 * amount
            - (entry_price * 0.01 * amount * 0.0005)
            - (exit_price * 0.01 * amount * 0.0005)
        ) / (entry_price * 0.01 * amount / leverage) * 100
        ELSE 0
    END
WHERE exchange = 'delta'
  AND position_type = 'short'
  AND status = 'closed'
  AND exit_price IS NOT NULL
  AND (pair LIKE 'ETH%' OR pair LIKE '%ETH%');

-- Fix LONG trades (BTC) — contract_size = 0.001
UPDATE trades
SET
    pnl = (exit_price - entry_price) * 0.001 * amount
          - (entry_price * 0.001 * amount * 0.0005)
          - (exit_price * 0.001 * amount * 0.0005),
    pnl_pct = CASE
        WHEN leverage > 0 AND entry_price > 0
        THEN (
            (exit_price - entry_price) * 0.001 * amount
            - (entry_price * 0.001 * amount * 0.0005)
            - (exit_price * 0.001 * amount * 0.0005)
        ) / (entry_price * 0.001 * amount / leverage) * 100
        ELSE 0
    END
WHERE exchange = 'delta'
  AND position_type = 'long'
  AND status = 'closed'
  AND exit_price IS NOT NULL
  AND (pair LIKE 'BTC%' OR pair LIKE '%BTC%');

-- Fix SHORT trades (BTC)
UPDATE trades
SET
    pnl = (entry_price - exit_price) * 0.001 * amount
          - (entry_price * 0.001 * amount * 0.0005)
          - (exit_price * 0.001 * amount * 0.0005),
    pnl_pct = CASE
        WHEN leverage > 0 AND entry_price > 0
        THEN (
            (entry_price - exit_price) * 0.001 * amount
            - (entry_price * 0.001 * amount * 0.0005)
            - (exit_price * 0.001 * amount * 0.0005)
        ) / (entry_price * 0.001 * amount / leverage) * 100
        ELSE 0
    END
WHERE exchange = 'delta'
  AND position_type = 'short'
  AND status = 'closed'
  AND exit_price IS NOT NULL
  AND (pair LIKE 'BTC%' OR pair LIKE '%BTC%');

-- Also fix the cost column (should be collateral, not raw notional)
UPDATE trades
SET cost = entry_price * 0.01 * amount / GREATEST(leverage, 1)
WHERE exchange = 'delta'
  AND (pair LIKE 'ETH%' OR pair LIKE '%ETH%')
  AND entry_price IS NOT NULL;

UPDATE trades
SET cost = entry_price * 0.001 * amount / GREATEST(leverage, 1)
WHERE exchange = 'delta'
  AND (pair LIKE 'BTC%' OR pair LIKE '%BTC%')
  AND entry_price IS NOT NULL;

-- ═══════════════════════════════════════════════════════════════════
-- Zero out Binance dust trades — they were never properly closed
-- ═══════════════════════════════════════════════════════════════════
UPDATE trades
SET pnl = 0, pnl_pct = 0
WHERE exchange = 'binance'
  AND status = 'closed';

-- Also mark any remaining Binance open trades as closed (dust)
UPDATE trades
SET status = 'closed', reason = 'dust_zeroed_v2'
WHERE exchange = 'binance'
  AND status = 'open';

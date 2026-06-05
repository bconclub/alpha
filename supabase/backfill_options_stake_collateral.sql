-- Backfill options collateral to the actual long-option stake/max-loss basis.
--
-- Old value used:
--   entry_price * contracts / leverage
--
-- Correct display/risk basis for bought Delta BTC/ETH options:
--   entry_price * contracts * option_contract_multiplier
--
-- Multipliers match engine/alpha/strategies/options_scalp.py:
--   ETH option contract = 0.01 ETH
--   BTC option contract = 0.001 BTC

UPDATE public.trades
SET collateral = ROUND(
  entry_price
  * COALESCE(NULLIF(contracts, 0), NULLIF(amount, 0), 0)
  * CASE
      WHEN pair LIKE 'BTC%' THEN 0.001
      WHEN pair LIKE 'ETH%' THEN 0.01
      ELSE 0
    END,
  8
)
WHERE strategy = 'options_scalp'
  AND pair ~ '-[0-9]{6}-[0-9]+-[CP]$'
  AND entry_price > 0
  AND COALESCE(NULLIF(contracts, 0), NULLIF(amount, 0), 0) > 0
  AND (pair LIKE 'BTC%' OR pair LIKE 'ETH%');


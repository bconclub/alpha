# Portfolio research changes, September 8, 2026

## Outcome

No tested variant establishes a profitable replacement. The changes provide a
reproducible, capital-constrained research tool. They do not alter live execution.

Two independent historical windows, each starting flat with $14.14:

| Scenario | June 15-August 22 equity change | August 23-September 7 equity change |
|---|---:|---:|
| Current rule approximation | -$9.94 | -$6.71 |
| Disable +25% take-profit | -$7.05 | -$6.27 |
| Exclude BTC | -$9.64 | -$7.16 |
| 1% estimated stop risk, 2% total risk | +$0.43 | -$0.32 |

Recent window closed-trade net for risk sizing was -$0.2711; one position remained
open. Including marked exposure and estimated exit fees gives -$0.3195 equity
change. Do not confuse these metrics. Its sampled drawdown was $0.5347 versus
$7.5342 for the current-rule approximation. Smaller sizing reduces exposure and
rejects many trades; it does not establish improved signal quality.

The windows are historical diagnostic cohorts, NOT untouched out-of-sample tests.
Each starts fresh with the same balance and has no carried positions. They are
not a reproduction of historical account performance or a continuous compound
return. Current rules are applied retrospectively even when older live versions
used different rules.

## Changes

- Chronological shared cash/margin allocation, deterministic pair order, one
  position per pair and three concurrent positions maximum.
- Integer contracts and metadata-driven contract units; a one-contract minimum
  can no longer create an unaffordable simulated position.
- Optional estimated account-risk sizing. Risk includes assumed fees/slippage,
  but gaps can exceed the estimate. Existing risk reservations are conservative
  entry-risk estimates, not dynamically reduced by a favorable trail.
- ATR includes the just-closed signal candle, using the live indicator helper.
- +25% target, -26% margin cap, ATR trail and 72h hold limit.
- Adverse gap fills and configurable slippage; deterministic stop-before-target
  handling when both occur in a single OHLC candle.
- Daily cost/loss accounting, balance kill/recovery gate and funding-event input.
  Daily accounting intentionally uses costs when incurred, unlike live's current
  closed-trade counter. It is a proposed research control, not exact live parity.
- Closed profit, open positions, cash and marked equity are separate. Drawdown is
  calculated chronologically from bar-close equity including estimated exit fees.
- Strict missing/duplicate/misaligned candle rejection.
- Public-only dataset downloader and fixed scenario comparison command.
- Legacy backtest prints a prominent warning about unsupported live conclusions.

## Data and assumptions

Public Delta India data, 25,920 five-minute candles per pair including warmup.
BTC=0.001, ETH=0.01, SOL=1, XRP=1, DOGE=100 underlying units per contract, from
current product metadata. Historical contract validity still needs confirmation.

Source dataset SHA256:
`c7f7018ddbcd0c303a7556828d0410b4de08be7460d4f602918a8d532be1237b`

Fee assumption: 0.059% per side; adverse slippage: 5 basis points per fill.
Funding is NOT verified in this dataset and excluded from these numbers. The
replay can consume funding events, but an absent series is not evidence of zero
funding. Funding could erase the small earlier-period gain.

Remaining limitations: five-minute extrema differ from 12-second live samples;
ATR refresh timing differs from live's 15-minute cache; no liquidation, outages,
partial fills, manual adoption, intrabar equity drawdown, or restarts modeled.
Historical execution reconciliation is still required. A passing unit test suite
does not establish live-fill parity.

## Reproduce

From repository root, using a Python 3.10+ interpreter:

```sh
python -m unittest discover -s engine/scripts -p test_portfolio_replay.py -v
python engine/scripts/fetch_replay_data.py --start 2026-06-15 --end 2026-09-08 --output audit-market-2026-09-08.json
python engine/scripts/compare_replays.py audit-market-2026-09-08.json --output-dir research-results-2026-09-08
```

Downloaded data and full trade/equity outputs remain local. Summary figures above
are provided for review; commands recreate outputs without credentials. Public
history can be revised, so retain the original dataset/hash when reproducing.

## Next decision gate

Reconcile historical fills/fees/funding, verify replay against representative live
trades, and run a frozen paper configuration on future data. Do not optimize more
parameters against these same windows and call the winner out-of-sample. Only
after those checks can a strategy change be judged. This branch intentionally
contains no live trader changes and must not be presented as a profit-producing
upgrade.

# Changelog

## 2026-05-15 · GPFC #74 FIX: remove await from sync on_fill_fallback, use cached ticker

- `options_scalp.py`: Added `self._last_option_ticker` attribute in `__init__` (initialized to `None`)
- `options_scalp.py` (`_execute_breakout_entry`): Cache `_pre_ticker` into `self._last_option_ticker` immediately after the pre-entry fetch
- `options_scalp.py` (`_check_option_exit`): Cache `ticker` into `self._last_option_ticker` after each clean (non-absurd) tick
- `options_scalp.py` (`on_fill`): Replaced the `await self.options_exchange.fetch_ticker()` call inside the sync `on_fill_fallback` path with `self._last_option_ticker`; if cache is cold, logs a warning and skips metadata without crashing
- User-facing: bot no longer crashes on import with "await outside async function"; on_fill_fallback writes DB row without confidence when ticker cache is cold rather than raising `SyntaxError`
- Fixes deploy blocker introduced in GPFC #74 (commit 90dfd69)

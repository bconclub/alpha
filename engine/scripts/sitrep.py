"""One-shot situation report for the V5.2 trend rider.

Prints a compact digest: balance, open positions (entry/mark/PnL/stop
distance), and per pair how far the current 2h close sits from the
20-bar Donchian box edges — i.e. exactly how close the bot is to its
next entry trigger. Read-only; safe to run any time.

    python3 scripts/sitrep.py
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import ccxt.async_support as ccxt

PAIRS = ["BTC/USD:USD", "ETH/USD:USD", "SOL/USD:USD", "XRP/USD:USD", "DOGE/USD:USD"]
CHANNEL_LEN = 20
TIMEFRAME = "2h"


def _load_env() -> None:
    env = Path(__file__).resolve().parent.parent / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


async def main() -> None:
    _load_env()
    ex = ccxt.delta({
        "apiKey": os.environ.get("DELTA_API_KEY", ""),
        "secret": os.environ.get("DELTA_SECRET", ""),
        "enableRateLimit": True,
        "options": {"defaultType": "future"},
    })
    # account keys live on the India deployment, same as the engine
    base = "https://api.india.delta.exchange"
    ex.urls["api"] = {"public": base, "private": base}
    try:
        await ex.load_markets()

        bal_free = bal_total = 0.0
        positions = []
        try:
            b = await ex.fetch_balance()
            usd = b.get("USD") or b.get("USDT") or {}
            bal_free = float(usd.get("free") or 0)
            bal_total = float(usd.get("total") or 0)
            positions = [p for p in await ex.fetch_positions() if float(p.get("contracts") or 0) != 0]
        except Exception as e:  # keys missing/expired — market section still works
            print(f"ACCOUNT: unavailable ({type(e).__name__})")

        if bal_total:
            print(f"ACCOUNT: ${bal_total:.2f} total, ${bal_free:.2f} free")
        for p in positions:
            contracts = float(p.get("contracts") or 0)
            side = p.get("side") or ("long" if contracts > 0 else "short")
            entry = float(p.get("entryPrice") or 0)
            mark = float(p.get("markPrice") or 0)
            sym_full = p.get("symbol") or "?"
            sym = sym_full.split("/")[0]
            if not mark:  # delta position payload lacks mark — use ticker
                try:
                    mark = float((await ex.fetch_ticker(sym_full)).get("last") or 0)
                except Exception:
                    mark = 0.0
            csize = float((ex.market(sym_full).get("contractSize") if sym_full in ex.markets else 0) or 0)
            chg = (mark - entry) / entry * 100 if (entry and mark) else 0
            if side == "short":
                chg = -chg
            upnl = (mark - entry) * abs(contracts) * csize * (1 if side != "short" else -1) if mark else 0.0
            print(f"POSITION: {sym} {side.upper()} entry={entry:g} mark={mark:g} "
                  f"px_move={chg:+.2f}% uPnL=${upnl:+.3f}")
        if not positions:
            print("POSITION: none open")

        print(f"MARKET ({TIMEFRAME} Donchian-{CHANNEL_LEN} — entry fires on a close beyond the box):")
        for pair in PAIRS:
            try:
                rows = await ex.fetch_ohlcv(pair, TIMEFRAME, limit=CHANNEL_LEN + 10)
            except Exception:
                # bot symbols are USD-settled; public data also lives on USDT symbols
                alt = pair.split("/")[0] + "/USDT:USDT"
                try:
                    rows = await ex.fetch_ohlcv(alt, TIMEFRAME, limit=CHANNEL_LEN + 10)
                except Exception:
                    rows = []
            if len(rows) < CHANNEL_LEN + 2:
                print(f"  {pair.split('/')[0]:5} candles unavailable")
                continue
            closed = rows[:-1]
            hist = closed[-(CHANNEL_LEN + 1):-1]
            upper = max(float(r[2]) for r in hist)
            lower = min(float(r[3]) for r in hist)
            last = float(rows[-1][4])
            to_up = (upper - last) / last * 100
            to_dn = (last - lower) / last * 100
            state = "INSIDE BOX"
            if last > upper:
                state = "ABOVE BOX (long zone)"
            elif last < lower:
                state = "BELOW BOX (short zone)"
            print(f"  {pair.split('/')[0]:5} {last:>12g}  box {lower:g}..{upper:g}  "
                  f"long_trig +{max(to_up, 0):.2f}%  short_trig -{max(to_dn, 0):.2f}%  [{state}]")
    finally:
        await ex.close()


if __name__ == "__main__":
    asyncio.run(main())

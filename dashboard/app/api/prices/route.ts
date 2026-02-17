import { NextResponse } from 'next/server';

/**
 * GET /api/prices
 *
 * Fetches live mark prices from Delta Exchange (India) public API.
 * No authentication required.
 *
 * Returns: { prices: { "BTC/USD:USD": 67950.5, "ETH/USD:USD": 2450.3, ... },
 *            source: "delta", timestamp: 1234567890 }
 */

// Delta India production ticker endpoint
const DELTA_TICKERS_URL = 'https://api.india.delta.exchange/v2/tickers';

// Map Delta symbol → ccxt-style pair (as stored in our DB)
const DELTA_SYMBOL_MAP: Record<string, string> = {
  BTCUSD: 'BTC/USD:USD',
  ETHUSD: 'ETH/USD:USD',
  SOLUSD: 'SOL/USD:USD',
  XRPUSD: 'XRP/USD:USD',
};

// Which Delta symbols to extract
const DELTA_SYMBOLS = new Set(Object.keys(DELTA_SYMBOL_MAP));

interface DeltaTicker {
  symbol: string;
  mark_price: string | null;
  close: string | null;
  spot_price: string | null;
}

export const dynamic = 'force-dynamic'; // never cache
export const revalidate = 0;

export async function GET() {
  const prices: Record<string, number> = {};

  try {
    const deltaPrices = await fetchDeltaPrices();
    Object.assign(prices, deltaPrices);
  } catch (err) {
    console.warn('[API /prices] Delta fetch failed:', err);
  }

  return NextResponse.json({
    prices,
    source: 'delta',
    timestamp: Date.now(),
  });
}

async function fetchDeltaPrices(): Promise<Record<string, number>> {
  const res = await fetch(DELTA_TICKERS_URL, {
    signal: AbortSignal.timeout(5000),
    headers: { Accept: 'application/json' },
  });

  if (!res.ok) {
    throw new Error(`Delta API ${res.status}: ${res.statusText}`);
  }

  const data = await res.json();
  const tickers: DeltaTicker[] = data?.result ?? [];
  const prices: Record<string, number> = {};

  for (const ticker of tickers) {
    if (!DELTA_SYMBOLS.has(ticker.symbol)) continue;

    const pair = DELTA_SYMBOL_MAP[ticker.symbol];
    // Prefer mark_price (fairest), fall back to close, then spot_price
    const priceStr = ticker.mark_price ?? ticker.close ?? ticker.spot_price;
    if (priceStr) {
      const price = parseFloat(priceStr);
      if (price > 0) {
        prices[pair] = price;
      }
    }
  }

  return prices;
}

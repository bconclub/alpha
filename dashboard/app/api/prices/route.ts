import { NextResponse } from 'next/server';

/**
 * GET /api/prices
 *
 * Fetches live prices from multiple exchanges (Kraken, Delta).
 * No authentication required — uses public ticker endpoints.
 *
 * Priority: Kraken (primary futures exchange) → Delta (options + fallback)
 *
 * Returns: { prices: { "BTC/USD:USD": 67950.5, "ETH/USD:USD": 2450.3, ... },
 *            sources: ["kraken","delta"], timestamp: 1234567890 }
 */

// ── Kraken ──────────────────────────────────────────────────────────────────
// Public REST: https://docs.kraken.com/api/docs/rest-api/get-ticker-information
const KRAKEN_TICKER_URL = 'https://api.kraken.com/0/public/Ticker';

// Map Kraken pair codes → ccxt-style pair (as stored in our DB)
const KRAKEN_PAIR_MAP: Record<string, string> = {
  XXBTZUSD: 'BTC/USD:USD',
  XETHZUSD: 'ETH/USD:USD',
  SOLUSD:   'SOL/USD:USD',
  XXRPZUSD: 'XRP/USD:USD',
};

// Kraken query string (comma-separated pair IDs)
const KRAKEN_PAIRS_QUERY = Object.keys(KRAKEN_PAIR_MAP).join(',');

// ── Delta ───────────────────────────────────────────────────────────────────
const DELTA_TICKERS_URL = 'https://api.india.delta.exchange/v2/tickers';

const DELTA_SYMBOL_MAP: Record<string, string> = {
  BTCUSD: 'BTC/USD:USD',
  ETHUSD: 'ETH/USD:USD',
  SOLUSD: 'SOL/USD:USD',
  XRPUSD: 'XRP/USD:USD',
};

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
  const sources: string[] = [];

  // Fetch from both exchanges in parallel
  const [krakenResult, deltaResult] = await Promise.allSettled([
    fetchKrakenPrices(),
    fetchDeltaPrices(),
  ]);

  // Delta first (lower priority — will be overwritten by Kraken)
  if (deltaResult.status === 'fulfilled') {
    Object.assign(prices, deltaResult.value);
    sources.push('delta');
  } else {
    console.warn('[API /prices] Delta fetch failed:', deltaResult.reason);
  }

  // Kraken second (higher priority — overwrites Delta for same pairs)
  if (krakenResult.status === 'fulfilled') {
    Object.assign(prices, krakenResult.value);
    sources.push('kraken');
  } else {
    console.warn('[API /prices] Kraken fetch failed:', krakenResult.reason);
  }

  return NextResponse.json({
    prices,
    sources,
    timestamp: Date.now(),
  });
}

// ── Kraken fetcher ──────────────────────────────────────────────────────────
async function fetchKrakenPrices(): Promise<Record<string, number>> {
  const res = await fetch(`${KRAKEN_TICKER_URL}?pair=${KRAKEN_PAIRS_QUERY}`, {
    signal: AbortSignal.timeout(5000),
    headers: { Accept: 'application/json' },
  });

  if (!res.ok) {
    throw new Error(`Kraken API ${res.status}: ${res.statusText}`);
  }

  const data = await res.json();
  if (data.error && data.error.length > 0) {
    throw new Error(`Kraken API error: ${data.error.join(', ')}`);
  }

  const result: Record<string, any> = data.result ?? {};
  const prices: Record<string, number> = {};

  for (const [krakenPair, ticker] of Object.entries(result)) {
    const pair = KRAKEN_PAIR_MAP[krakenPair];
    if (!pair) continue;

    // Kraken ticker format: c = last trade [price, lot-volume]
    // a = ask [price, whole, lot], b = bid [price, whole, lot]
    const t = ticker as any;
    // Use last trade price (most recent actual fill)
    const priceStr = t.c?.[0] ?? t.a?.[0] ?? t.b?.[0];
    if (priceStr) {
      const price = parseFloat(priceStr);
      if (price > 0) {
        prices[pair] = price;
      }
    }
  }

  return prices;
}

// ── Delta fetcher ───────────────────────────────────────────────────────────
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

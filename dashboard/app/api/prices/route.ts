import { NextResponse } from 'next/server';

/**
 * GET /api/prices
 *
 * Fetches live mark prices from Delta Exchange (India) public API
 * and spot prices from Binance. No authentication required.
 *
 * Returns: { prices: { "BTC/USD:USD": 67950.5, "ETH/USD:USD": 2450.3, ... },
 *            source: "delta+binance", timestamp: 1234567890 }
 */

// Delta India production ticker endpoint
const DELTA_TICKERS_URL = 'https://api.india.delta.exchange/v2/tickers';

// Binance spot price endpoint
const BINANCE_PRICE_URL = 'https://api.binance.com/api/v3/ticker/price';

// Map Delta symbol → ccxt-style pair (as stored in our DB)
const DELTA_SYMBOL_MAP: Record<string, string> = {
  BTCUSD: 'BTC/USD:USD',
  ETHUSD: 'ETH/USD:USD',
  SOLUSD: 'SOL/USD:USD',
  XRPUSD: 'XRP/USD:USD',
};

// Map Binance symbol → ccxt-style pair
const BINANCE_SYMBOL_MAP: Record<string, string> = {
  BTCUSDT: 'BTC/USDT',
  ETHUSDT: 'ETH/USDT',
  SOLUSDT: 'SOL/USDT',
  XRPUSDT: 'XRP/USDT',
};

// Which Delta symbols to extract
const DELTA_SYMBOLS = new Set(Object.keys(DELTA_SYMBOL_MAP));

// Which Binance symbols to fetch
const BINANCE_SYMBOLS = Object.keys(BINANCE_SYMBOL_MAP);

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

  // Fetch Delta + Binance in parallel
  const [deltaResult, binanceResult] = await Promise.allSettled([
    fetchDeltaPrices(),
    fetchBinancePrices(),
  ]);

  if (deltaResult.status === 'fulfilled') {
    Object.assign(prices, deltaResult.value);
  } else {
    console.warn('[API /prices] Delta fetch failed:', deltaResult.reason);
  }

  if (binanceResult.status === 'fulfilled') {
    Object.assign(prices, binanceResult.value);
  } else {
    console.warn('[API /prices] Binance fetch failed:', binanceResult.reason);
  }

  return NextResponse.json({
    prices,
    source: 'delta+binance',
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

async function fetchBinancePrices(): Promise<Record<string, number>> {
  const symbolsParam = JSON.stringify(BINANCE_SYMBOLS);
  const url = `${BINANCE_PRICE_URL}?symbols=${encodeURIComponent(symbolsParam)}`;

  const res = await fetch(url, {
    signal: AbortSignal.timeout(5000),
    headers: { Accept: 'application/json' },
  });

  if (!res.ok) {
    throw new Error(`Binance API ${res.status}: ${res.statusText}`);
  }

  const data: Array<{ symbol: string; price: string }> = await res.json();
  const prices: Record<string, number> = {};

  for (const item of data) {
    const pair = BINANCE_SYMBOL_MAP[item.symbol];
    if (pair) {
      const price = parseFloat(item.price);
      if (price > 0) {
        prices[pair] = price;
      }
    }
  }

  return prices;
}

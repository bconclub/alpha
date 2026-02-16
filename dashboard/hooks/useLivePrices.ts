'use client';

import { useEffect, useRef, useState, useCallback } from 'react';

/** Live prices from exchange APIs, polled every POLL_INTERVAL_MS. */
export interface LivePriceData {
  /** Map of pair → latest price, e.g. { "BTC/USD:USD": 67950.5 } */
  prices: Record<string, number>;
  /** Unix timestamp (ms) of last successful fetch */
  lastUpdated: number;
  /** Whether we're currently fetching */
  loading: boolean;
  /** Last error message (clears on next success) */
  error: string | null;
}

const POLL_INTERVAL_MS = 3_000; // 3 seconds

/**
 * Hook that polls /api/prices every 3 seconds for live exchange prices.
 *
 * Only polls when there are open positions (saves API calls when idle).
 */
export function useLivePrices(hasOpenPositions: boolean): LivePriceData {
  const [data, setData] = useState<LivePriceData>({
    prices: {},
    lastUpdated: 0,
    loading: false,
    error: null,
  });

  // Use ref to avoid stale closures in interval
  const hasPositionsRef = useRef(hasOpenPositions);
  hasPositionsRef.current = hasOpenPositions;

  const fetchPrices = useCallback(async () => {
    if (!hasPositionsRef.current) return;

    try {
      const res = await fetch('/api/prices', {
        signal: AbortSignal.timeout(4000),
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const json = await res.json();

      setData({
        prices: json.prices ?? {},
        lastUpdated: json.timestamp ?? Date.now(),
        loading: false,
        error: null,
      });
    } catch (err) {
      setData((prev) => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : 'Fetch failed',
      }));
    }
  }, []);

  useEffect(() => {
    // Fetch immediately on mount (or when positions appear)
    if (hasOpenPositions) {
      setData((prev) => ({ ...prev, loading: true }));
      fetchPrices();
    }

    const interval = setInterval(fetchPrices, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [hasOpenPositions, fetchPrices]);

  return data;
}

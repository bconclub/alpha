'use client';

import { useMemo, useState, useCallback } from 'react';
import Link from 'next/link';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import { useLivePrices } from '@/hooks/useLivePrices';
import { getSupabase } from '@/lib/supabase';
import { formatNumber, formatCurrency, formatPrice, cn } from '@/lib/utils';

// Delta contract sizes (must match engine)
const DELTA_CONTRACT_SIZE: Record<string, number> = {
  'BTC/USD:USD': 0.001,
  'ETH/USD:USD': 0.01,
  'SOL/USD:USD': 1.0,
  'XRP/USD:USD': 1.0,
};

const TRAIL_ACTIVATION_PCT = 0.30; // must match engine TRAILING_ACTIVATE_PCT
const DEFAULT_SL_PCT = 0.25;      // must match engine STOP_LOSS_PCT fallback

function extractBaseAsset(pair: string): string {
  if (pair.includes('/')) return pair.split('/')[0];
  return pair.replace(/USD.*$/, '');
}

/** Format a price with 4 decimals for cheap assets (XRP), 2 for the rest */
function fmtPrice(value: number): string {
  const decimals = Math.abs(value) < 10 ? 4 : 2;
  return formatNumber(value, decimals);
}

/** Format a dollar P&L with 4 decimals when the absolute value is small */
function fmtPnl(value: number): string {
  const decimals = Math.abs(value) < 10 ? 4 : 2;
  return `$${formatNumber(Math.abs(value), decimals)}`;
}

interface PositionDisplay {
  id: string;
  pair: string;
  pairShort: string;
  positionType: 'long' | 'short';
  entryPrice: number;
  currentPrice: number | null;
  contracts: number;
  leverage: number;
  pricePnlPct: number | null;    // raw price move %
  capitalPnlPct: number | null;  // leveraged capital return %
  pnlUsd: number | null;         // dollar P&L (gross, no fees)
  collateral: number | null;     // actual capital at risk
  duration: string;
  trailActive: boolean;
  trailStopPrice: number | null;
  peakPnlPct: number | null;     // highest price P&L % reached
  slPrice: number | null;
  tpPrice: number | null;
  exchange: string;
}

// ---------------------------------------------------------------------------
// Position State Badge
// ---------------------------------------------------------------------------

type PositionState = 'near_sl' | 'at_risk' | 'holding_loss' | 'holding_gain' | 'trailing';

function getPositionState(pos: PositionDisplay): PositionState {
  const pnl = pos.pricePnlPct ?? 0;
  const peak = pos.peakPnlPct ?? 0;

  // TRAILING: only if trail genuinely active AND peak confirms it
  if (pos.trailActive && peak >= TRAIL_ACTIVATION_PCT) {
    return 'trailing';
  }

  // Compute SL distance to check "near SL"
  if (pos.slPrice != null && pos.currentPrice != null && pos.entryPrice > 0) {
    const slDist = Math.abs(pos.entryPrice - pos.slPrice);
    const currentDist = pos.positionType === 'long'
      ? pos.currentPrice - pos.slPrice
      : pos.slPrice - pos.currentPrice;
    // Near SL: within 30% of the SL distance from entry
    if (currentDist <= slDist * 0.30 && currentDist >= 0) {
      return 'near_sl';
    }
  }

  if (pnl < -0.15) return 'at_risk';
  if (pnl < 0) return 'holding_loss';
  return 'holding_gain';
}

function StateBadge({ state, trailStopPrice, entryPrice }: {
  state: PositionState;
  trailStopPrice: number | null;
  entryPrice: number;
}) {
  switch (state) {
    case 'near_sl':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-[#ff1744]/15 text-[#ff1744]">
          <span className="w-1.5 h-1.5 rounded-full bg-[#ff1744] animate-pulse" />
          NEAR SL
        </span>
      );
    case 'at_risk':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-[#ff1744]/10 text-[#ff1744]">
          AT RISK
        </span>
      );
    case 'holding_loss':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-400/10 text-amber-400">
          HOLDING
        </span>
      );
    case 'holding_gain':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-[#00c853]/10 text-[#00c853]">
          HOLDING
        </span>
      );
    case 'trailing':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-[#00c853]/10 text-[#00c853]">
          <span className="w-1.5 h-1.5 rounded-full bg-[#00c853] animate-pulse" />
          TRAILING
          {trailStopPrice != null && (
            <span className="text-zinc-400 font-normal ml-0.5">
              @${fmtPrice(trailStopPrice)}
            </span>
          )}
        </span>
      );
  }
}

// ---------------------------------------------------------------------------
// Position Range Bar (SL ← Entry → Peak/TP)
// ---------------------------------------------------------------------------

function PositionRangeBar({ pos }: { pos: PositionDisplay }) {
  const pnl = pos.pricePnlPct ?? 0;
  const entry = pos.entryPrice;
  const current = pos.currentPrice;
  const peak = pos.peakPnlPct ?? 0;

  if (current == null || entry <= 0) return null;

  // Compute SL price (from DB or estimate)
  const slPrice = pos.slPrice ?? (
    pos.positionType === 'long'
      ? entry * (1 - DEFAULT_SL_PCT / 100)
      : entry * (1 + DEFAULT_SL_PCT / 100)
  );

  // Range: SL distance below entry, peak/trail above entry
  const slDistPct = DEFAULT_SL_PCT; // distance from entry to SL in %
  const peakPct = Math.max(peak, Math.abs(pnl), 0.05); // at least 0.05 to avoid zero range

  // Total range: SL side + profit side
  const totalRange = slDistPct + Math.max(peakPct, TRAIL_ACTIVATION_PCT);

  // Entry position as % of total bar width (SL is at 0%, entry is partway)
  const entryPos = (slDistPct / totalRange) * 100;

  // Current price position on the bar
  const currentPos = ((slDistPct + pnl) / totalRange) * 100;
  const clampedCurrentPos = Math.max(0, Math.min(100, currentPos));

  // Trail activation line position
  const trailLinePos = ((slDistPct + TRAIL_ACTIVATION_PCT) / totalRange) * 100;

  // Trail stop position (if active)
  let trailStopPos: number | null = null;
  if (pos.trailActive && pos.trailStopPrice != null && entry > 0) {
    const trailStopPnl = pos.positionType === 'long'
      ? ((pos.trailStopPrice - entry) / entry) * 100
      : ((entry - pos.trailStopPrice) / entry) * 100;
    trailStopPos = Math.max(0, Math.min(100, ((slDistPct + trailStopPnl) / totalRange) * 100));
  }

  // Fill bar: from entry to current
  const fillLeft = Math.min(entryPos, clampedCurrentPos);
  const fillWidth = Math.abs(clampedCurrentPos - entryPos);
  const isProfit = pnl >= 0;

  return (
    <div className="w-full">
      {/* Bar with markers */}
      <div className="relative h-2.5 bg-zinc-800 rounded-full overflow-hidden">
        {/* SL zone background (left side, subtle red) */}
        <div
          className="absolute top-0 bottom-0 bg-[#ff1744]/8 rounded-l-full"
          style={{ left: 0, width: `${entryPos}%` }}
        />

        {/* Fill bar: current P&L relative to entry */}
        <div
          className={cn(
            'absolute top-0 bottom-0 transition-all duration-500 rounded-full',
            isProfit ? 'bg-[#00c853]' : 'bg-[#ff1744]',
          )}
          style={{ left: `${fillLeft}%`, width: `${fillWidth}%` }}
        />

        {/* Entry line */}
        <div
          className="absolute top-0 bottom-0 w-px bg-zinc-500"
          style={{ left: `${entryPos}%` }}
        />

        {/* Trail activation line (dashed) */}
        <div
          className="absolute top-0 bottom-0 w-px bg-[#00c853]/30"
          style={{ left: `${Math.min(trailLinePos, 100)}%` }}
        />

        {/* Trail stop line (if active) */}
        {trailStopPos != null && (
          <div
            className="absolute top-0 bottom-0 w-px bg-[#ffd600]"
            style={{ left: `${trailStopPos}%` }}
          />
        )}

        {/* Current price marker dot */}
        <div
          className={cn(
            'absolute top-1/2 -translate-y-1/2 w-2 h-2 rounded-full border border-zinc-900 z-10 transition-all duration-500',
            isProfit ? 'bg-[#00c853]' : 'bg-[#ff1744]',
          )}
          style={{ left: `${clampedCurrentPos}%`, marginLeft: '-4px' }}
        />
      </div>

      {/* Labels below bar */}
      <div className="relative h-3 mt-0.5">
        <span className="absolute text-[8px] font-mono text-[#ff1744]/70" style={{ left: 0 }}>
          SL ${fmtPrice(slPrice)}
        </span>
        <span
          className="absolute text-[8px] font-mono text-zinc-500 -translate-x-1/2"
          style={{ left: `${entryPos}%` }}
        >
          Entry
        </span>
        {pos.trailActive && pos.trailStopPrice != null ? (
          <span className="absolute right-0 text-[8px] font-mono text-[#ffd600]/70">
            Trail ${fmtPrice(pos.trailStopPrice)}
          </span>
        ) : (
          <span className="absolute right-0 text-[8px] font-mono text-zinc-600">
            {peak > 0 ? `Peak +${peak.toFixed(2)}%` : `+${TRAIL_ACTIVATION_PCT}%`}
          </span>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function LivePositions() {
  const { openPositions, strategyLog } = useSupabase();
  const livePrices = useLivePrices(openPositions.length > 0);

  // Track which positions are being closed
  const [closingIds, setClosingIds] = useState<Set<string>>(new Set());

  const handleClose = useCallback(async (posId: string, pair: string) => {
    const sb = getSupabase();
    if (!sb) return;

    setClosingIds((prev) => new Set(prev).add(posId));
    try {
      const { error } = await sb.from('bot_commands').insert({
        command: 'close_trade',
        params: { trade_id: Number(posId), pair },
      });
      if (error) {
        console.error('[Alpha] close_trade command failed:', error.message);
        setClosingIds((prev) => {
          const next = new Set(prev);
          next.delete(posId);
          return next;
        });
      }
      // Don't clear closingIds on success — wait for realtime to remove position
    } catch (e) {
      console.error('[Alpha] close_trade insert error:', e);
      setClosingIds((prev) => {
        const next = new Set(prev);
        next.delete(posId);
        return next;
      });
    }
  }, []);

  // Clear closing state when position disappears from openPositions
  const openIds = useMemo(() => new Set(openPositions.map((p) => p.id)), [openPositions]);
  useMemo(() => {
    setClosingIds((prev) => {
      const next = new Set<string>();
      Array.from(prev).forEach((id) => {
        if (openIds.has(id)) next.add(id);
      });
      return next.size !== prev.size ? next : prev;
    });
  }, [openIds]);

  // Build fallback prices from latest strategy_log entries (every ~5min)
  const fallbackPrices = useMemo(() => {
    const prices = new Map<string, number>();
    for (const log of strategyLog) {
      if (log.current_price && log.pair) {
        const asset = extractBaseAsset(log.pair);
        if (!prices.has(asset)) {
          prices.set(asset, log.current_price);
        }
      }
    }
    return prices;
  }, [strategyLog]);

  // Build display data for each open position
  const positions: PositionDisplay[] = useMemo(() => {
    if (!openPositions || openPositions.length === 0) return [];

    return openPositions.map((pos) => {
      const asset = extractBaseAsset(pos.pair);
      // Priority: live API price (3s) → bot DB price (~10s) → strategy_log (~5min)
      const currentPrice =
        livePrices.prices[pos.pair]       // exact pair match from API (e.g. "BTC/USD:USD")
        ?? pos.current_price              // bot writes to DB every ~10s
        ?? fallbackPrices.get(asset)      // strategy_log price (every ~5min)
        ?? null;
      const leverage = pos.leverage > 1 ? pos.leverage : 1;

      // Calculate P&L
      let pricePnlPct: number | null = null;
      let capitalPnlPct: number | null = null;
      let pnlUsd: number | null = null;
      let collateral: number | null = null;

      if (currentPrice != null && pos.entry_price > 0) {
        // Price move %
        if (pos.position_type === 'short') {
          pricePnlPct = ((pos.entry_price - currentPrice) / pos.entry_price) * 100;
        } else {
          pricePnlPct = ((currentPrice - pos.entry_price) / pos.entry_price) * 100;
        }
        // Capital return % = price move × leverage
        capitalPnlPct = pricePnlPct * leverage;

        // Dollar P&L (gross — fees deducted on close)
        let coinAmount = pos.amount;
        if (pos.exchange === 'delta') {
          const contractSize = DELTA_CONTRACT_SIZE[pos.pair] ?? 1.0;
          coinAmount = pos.amount * contractSize;
        }
        if (pos.position_type === 'short') {
          pnlUsd = (pos.entry_price - currentPrice) * coinAmount;
        } else {
          pnlUsd = (currentPrice - pos.entry_price) * coinAmount;
        }

        // Collateral = notional / leverage
        const notional = pos.entry_price * coinAmount;
        collateral = leverage > 1 ? notional / leverage : notional;
      }

      // Use ACTUAL position state from bot (written to DB every ~10s)
      // Only trust trailing state if peak P&L confirms it (≥0.30%)
      const peakPnlPct = pos.peak_pnl ?? (pricePnlPct != null && pricePnlPct > 0 ? pricePnlPct : 0);
      const trailActive = (
        pos.position_state === 'trailing'
        && peakPnlPct >= TRAIL_ACTIVATION_PCT
      );

      // Use ACTUAL trail stop price from bot, or estimate if not available
      let trailStopPrice: number | null = pos.trail_stop_price ?? null;
      if (trailStopPrice == null && trailActive && currentPrice != null && pricePnlPct != null) {
        // Fallback estimation when bot hasn't written state yet
        let trailDist = 0.30;
        const tiers: [number, number][] = [[0.50, 0.30], [1.00, 0.50], [2.00, 0.70], [3.00, 1.00]];
        for (const [minProfit, dist] of tiers) {
          if (pricePnlPct >= minProfit) trailDist = dist;
        }
        if (pos.position_type === 'short') {
          trailStopPrice = currentPrice * (1 + trailDist / 100);
        } else {
          trailStopPrice = currentPrice * (1 - trailDist / 100);
        }
      }

      return {
        id: pos.id,
        pair: pos.pair,
        pairShort: asset,
        positionType: pos.position_type as 'long' | 'short',
        entryPrice: pos.entry_price,
        currentPrice,
        contracts: pos.amount,
        leverage,
        pricePnlPct,
        capitalPnlPct,
        pnlUsd,
        collateral,
        duration: durationSince(pos.opened_at),
        trailActive,
        trailStopPrice,
        peakPnlPct,
        slPrice: pos.stop_loss ?? null,
        tpPrice: pos.take_profit ?? null,
        exchange: pos.exchange,
      };
    });
  }, [openPositions, livePrices.prices, fallbackPrices]);

  if (positions.length === 0) return null;

  return (
    <div className="bg-[#0d1117] border border-zinc-800 rounded-xl p-3 md:p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-zinc-400 uppercase tracking-wider">
          Live Positions
        </h3>
        <span className="text-[10px] text-zinc-500 font-mono flex items-center gap-1.5">
          {positions.length} active
          {livePrices.lastUpdated > 0 && (
            <span className="inline-flex items-center gap-1 text-[9px]">
              <span className="w-1.5 h-1.5 rounded-full bg-[#00c853] animate-pulse" />
              LIVE
            </span>
          )}
        </span>
      </div>

      <div className="space-y-2">
        {positions.map((pos) => {
          const isProfit = (pos.pricePnlPct ?? 0) >= 0;
          const pnlColor = isProfit ? 'text-[#00c853]' : 'text-[#ff1744]';
          const posState = getPositionState(pos);
          const borderColor = posState === 'trailing' ? 'border-[#00c853]/30'
            : posState === 'near_sl' || posState === 'at_risk' ? 'border-[#ff1744]/20'
            : isProfit ? 'border-[#00c853]/20'
            : 'border-zinc-800/50';
          const isClosing = closingIds.has(pos.id);

          return (
            <div
              key={pos.id}
              className={cn(
                'w-full bg-zinc-900/50 border rounded-lg px-3 py-2.5 md:px-4 md:py-3',
                'transition-colors',
                borderColor,
                isClosing && 'opacity-60',
              )}
            >
              {/* Row 1: Pair + Side + Status + Close + Duration */}
              <div className="flex items-center justify-between gap-2 mb-1.5">
                <div className="flex items-center gap-2 min-w-0">
                  <span
                    className={cn(
                      'w-1.5 h-5 rounded-sm shrink-0',
                      pos.positionType === 'short' ? 'bg-[#ff1744]' : 'bg-[#00c853]',
                    )}
                  />
                  <Link href="/trades" className="text-sm font-bold text-white hover:underline">
                    {pos.pairShort}
                  </Link>
                  <span className={cn(
                    'text-[10px] font-semibold px-1.5 py-0.5 rounded',
                    pos.positionType === 'short'
                      ? 'bg-[#ff1744]/10 text-[#ff1744]'
                      : 'bg-[#00c853]/10 text-[#00c853]',
                  )}>
                    {pos.positionType.toUpperCase()} {pos.leverage}x
                  </span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <StateBadge
                    state={posState}
                    trailStopPrice={pos.trailStopPrice}
                    entryPrice={pos.entryPrice}
                  />
                  <button
                    onClick={() => handleClose(pos.id, pos.pair)}
                    disabled={isClosing}
                    className={cn(
                      'px-2 py-0.5 rounded text-[10px] font-semibold transition-colors',
                      isClosing
                        ? 'bg-zinc-700/50 text-zinc-500 cursor-not-allowed'
                        : 'bg-[#ff1744]/10 text-[#ff1744] hover:bg-[#ff1744]/20 active:bg-[#ff1744]/30',
                    )}
                  >
                    {isClosing ? 'Closing...' : 'Close'}
                  </button>
                  <span className="text-[9px] text-zinc-600 font-mono">{pos.duration}</span>
                </div>
              </div>

              {/* Row 2: Labeled P&L grid */}
              {pos.pricePnlPct != null ? (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-1 text-xs font-mono">
                  <div>
                    <div className="text-[9px] text-zinc-500 uppercase">P&L</div>
                    <div className={cn('font-bold', pnlColor)}>
                      {pos.pnlUsd != null ? `${pos.pnlUsd >= 0 ? '+' : '-'}${fmtPnl(pos.pnlUsd)}` : '\u2014'}
                    </div>
                  </div>
                  <div>
                    <div className="text-[9px] text-zinc-500 uppercase">Return</div>
                    <div className={cn('font-bold', pnlColor)}>
                      {pos.capitalPnlPct != null ? `${pos.capitalPnlPct >= 0 ? '+' : ''}${pos.capitalPnlPct.toFixed(1)}%` : '\u2014'}
                    </div>
                  </div>
                  <div>
                    <div className="text-[9px] text-zinc-500 uppercase">Entry &rarr; Now</div>
                    <div className="text-zinc-300">
                      ${fmtPrice(pos.entryPrice)} &rarr; ${pos.currentPrice != null ? fmtPrice(pos.currentPrice) : '...'}
                    </div>
                  </div>
                  <div>
                    <div className="text-[9px] text-zinc-500 uppercase">Price Move</div>
                    <div className={cn(pnlColor)}>
                      {pos.pricePnlPct >= 0 ? '+' : ''}{pos.pricePnlPct.toFixed(pos.entryPrice < 10 ? 4 : 3)}%
                    </div>
                  </div>
                </div>
              ) : (
                <span className="text-xs text-zinc-500">Calculating...</span>
              )}

              {/* Row 3: Position range bar + position size */}
              <div className="flex items-center gap-3 mt-1.5">
                {pos.pricePnlPct != null && (
                  <div className="flex-1 max-w-[240px] md:max-w-[320px]">
                    <PositionRangeBar pos={pos} />
                  </div>
                )}
                <span className="text-[10px] font-mono text-zinc-500 whitespace-nowrap shrink-0">
                  {pos.contracts}{pos.exchange === 'delta' ? ' ct' : ''}
                  {pos.collateral != null && ` \u00b7 $${pos.collateral < 10 ? pos.collateral.toFixed(4) : pos.collateral.toFixed(2)}`}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function durationSince(timestamp: string): string {
  const ms = Date.now() - new Date(timestamp).getTime();
  const mins = Math.floor(ms / 60000);
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  const remMins = mins % 60;
  return `${hours}h${remMins}m`;
}

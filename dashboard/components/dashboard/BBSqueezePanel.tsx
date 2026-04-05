'use client';

import React, { useMemo } from 'react';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import { formatNumber, cn } from '@/lib/utils';

// ── Types ───────────────────────────────────────────────────────────────

interface SqueezeAsset {
  asset: string;
  price: number | null;
  bbWidth: number | null;
  squeezeState: 'no_squeeze' | 'forming' | 'active' | 'firing';
  isActive: boolean;
  lastTimestamp: string | null;
}

// ── Helpers ─────────────────────────────────────────────────────────────

function extractBaseAsset(pair: string): string {
  if (pair.includes('/')) return pair.split('/')[0];
  return pair.replace(/USD.*$/, '');
}

function determineSqueezeState(width: number | null): SqueezeAsset['squeezeState'] {
  if (width == null) return 'no_squeeze';
  if (width < 2) return 'firing';
  if (width < 5) return 'active';
  if (width < 10) return 'forming';
  return 'no_squeeze';
}

function getStateConfig(state: SqueezeAsset['squeezeState']) {
  switch (state) {
    case 'firing':
      return {
        label: 'FIRE',
        badgeColor: 'bg-green-500/20 text-green-400',
        dotColor: 'bg-green-500',
        barColor: 'bg-green-500',
        statusText: 'ACTIVE',
      };
    case 'active':
      return {
        label: 'SQUEEZE',
        badgeColor: 'bg-yellow-500/20 text-yellow-400',
        dotColor: 'bg-yellow-500',
        barColor: 'bg-yellow-500',
        statusText: 'ACTIVE',
      };
    case 'forming':
      return {
        label: 'FORMING',
        badgeColor: 'bg-blue-500/20 text-blue-400',
        dotColor: 'bg-blue-500',
        barColor: 'bg-blue-500',
        statusText: 'ACTIVE',
      };
    default:
      return {
        label: 'NO SQUEEZE',
        badgeColor: 'bg-red-500/20 text-red-500',
        dotColor: 'bg-red-500',
        barColor: 'bg-red-500',
        statusText: 'DEAD',
      };
  }
}

// ── Sub-components ──────────────────────────────────────────────────────

function SqueezeCard({ asset }: { asset: SqueezeAsset }) {
  const state = getStateConfig(asset.squeezeState);
  const deltaBalance = 10.52; // Mock balance - would come from actual data
  
  // Calculate BB width percentage for visualization (max around 20%)
  const bbWidthPercent = asset.bbWidth != null 
    ? Math.min(100, Math.max(0, (asset.bbWidth / 20) * 100))
    : 0;

  return (
    <div className="bg-[#0f0f14] rounded-lg p-4 border border-white/5">
      {/* Header: Asset + Price + Status */}
      <div className="flex justify-between items-center mb-3">
        <div className="flex items-center gap-2">
          <span className="font-bold text-lg text-white">{asset.asset}</span>
          <span className="text-sm text-gray-400 font-mono">
            {asset.price != null ? `$${formatNumber(asset.price)}` : '—'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className={cn('w-2 h-2 rounded-full', state.dotColor)} />
          <span className={cn('text-xs font-bold', state.badgeColor.split(' ')[1])}>
            {state.statusText}
          </span>
          <span className="text-xs text-gray-500">Balance</span>
          <span className="text-xs font-mono text-gray-400">${deltaBalance.toFixed(2)}</span>
          <span className="text-xs bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded">Delta</span>
        </div>
      </div>

      {/* BB Squeeze Status */}
      <div className="flex justify-between items-center mb-2">
        <span className="text-xs text-gray-400">BB SQUEEZE</span>
        <span className={cn('text-xs font-bold', state.badgeColor.split(' ')[1])}>
          {state.label}
        </span>
      </div>

      {/* BB Width Bar */}
      <div className="space-y-2">
        <div className="flex justify-between text-xs">
          <span className="text-gray-500">BB Width</span>
          <span className="text-gray-400 font-mono">
            {asset.bbWidth != null ? `${asset.bbWidth.toFixed(2)}%` : '--%'} / --%
          </span>
        </div>
        <div className="h-1 bg-gray-800 rounded-full overflow-hidden">
          <div 
            className={cn('h-full transition-all duration-500', state.barColor)}
            style={{ width: `${bbWidthPercent}%` }}
          />
        </div>
      </div>

      {/* Premium Range Section */}
      <div className="mt-3 pt-3 border-t border-white/5">
        <div className="flex justify-between text-xs mb-1">
          <span className="text-gray-500">Premium Range (30MIN)</span>
          <span className="text-yellow-500">WAITING...</span>
        </div>
        <div className="h-8 bg-gray-900 rounded flex items-center justify-center">
          <span className="text-xs text-gray-600">No active squeeze</span>
        </div>
      </div>
    </div>
  );
}

// ── Main component ──────────────────────────────────────────────────────

export function BBSqueezePanel() {
  const { strategyLog } = useSupabase();

  const squeezeAssets = useMemo(() => {
    // ONLY BTC and ETH - no other coins
    const TRACKED_ASSETS = new Set(['BTC', 'ETH']);
    
    // Get latest data for each asset
    const latestByAsset = new Map<string, SqueezeAsset>();
    
    for (const log of strategyLog) {
      if (!log.pair) continue;
      const asset = extractBaseAsset(log.pair);
      if (!TRACKED_ASSETS.has(asset)) continue;
      
      const existing = latestByAsset.get(asset);
      if (!existing || new Date(log.timestamp) > new Date(existing.lastTimestamp || 0)) {
        // Calculate BB width from upper/lower bands
        const bbWidth = (log.bb_upper != null && log.bb_lower != null && log.current_price)
          ? ((log.bb_upper - log.bb_lower) / log.current_price) * 100
          : null;
          
        latestByAsset.set(asset, {
          asset,
          price: log.current_price ?? null,
          bbWidth,
          squeezeState: determineSqueezeState(bbWidth),
          isActive: bbWidth != null && bbWidth < 10,
          lastTimestamp: log.timestamp,
        });
      }
    }
    
    // Ensure both BTC and ETH are present in order
    const result: SqueezeAsset[] = [];
    for (const asset of ['BTC', 'ETH'] as const) {
      const data = latestByAsset.get(asset);
      if (data) {
        result.push(data);
      } else {
        // Placeholder for missing data
        result.push({
          asset,
          price: null,
          bbWidth: null,
          squeezeState: 'no_squeeze',
          isActive: false,
          lastTimestamp: null,
        });
      }
    }
    
    return result;
  }, [strategyLog]);

  return (
    <div className="bg-[#141419] border border-white/5 rounded-xl p-6">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-8 h-8 bg-green-500/20 rounded-lg flex items-center justify-center text-green-500 font-bold text-sm">
          α
        </div>
        <div>
          <h2 className="font-bold text-white">BB SQUEEZE</h2>
          <p className="text-xs text-gray-500">Buy Cheap Premium | Hold Breakout</p>
        </div>
        <div className="ml-auto text-xs text-gray-600">v{process.env.ALPHA_VERSION ?? '0.12.2'}</div>
      </div>

      <div className="space-y-4">
        {squeezeAssets.map((asset) => (
          <SqueezeCard key={asset.asset} asset={asset} />
        ))}
      </div>
    </div>
  );
}

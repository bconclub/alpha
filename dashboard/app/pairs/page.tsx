'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import { getSupabase } from '@/lib/supabase';
import { Badge } from '@/components/ui/Badge';
import type { Trade, PairConfig } from '@/lib/types';
import {
  formatPnL,
  formatPercentage,
  formatCurrency,
  formatShortDate,
  cn,
  getPnLColor,
} from '@/lib/utils';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PAIRS = ['BTC', 'ETH', 'XRP', 'SOL'] as const;
type PairName = (typeof PAIRS)[number];

// Map base asset → ccxt-style pair as stored in trades table
const PAIR_MAP: Record<PairName, string> = {
  BTC: 'BTC/USD:USD',
  ETH: 'ETH/USD:USD',
  XRP: 'XRP/USD:USD',
  SOL: 'SOL/USD:USD',
};

// Pair icon colors
const PAIR_COLORS: Record<PairName, string> = {
  BTC: '#f7931a',
  ETH: '#627eea',
  XRP: '#23292f',
  SOL: '#9945ff',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function extractBaseAsset(pair: string): string {
  if (pair.includes('/')) return pair.split('/')[0];
  return pair.replace(/USD.*$/, '');
}

function getTradesForPair(trades: Trade[], pairName: PairName): Trade[] {
  const ccxtPair = PAIR_MAP[pairName];
  return trades.filter((t) => t.pair === ccxtPair || extractBaseAsset(t.pair) === pairName);
}

function getExitReasonShort(reason: string | undefined): string {
  if (!reason) return '?';
  // Simplify exit reason for badge display
  const r = reason.toUpperCase();
  if (r.includes('TRAIL')) return 'TRL';
  if (r.includes('SPOT_PULLBACK')) return 'SPB';
  if (r.includes('SPOT_DECAY')) return 'SPD';
  if (r.includes('SPOT_BREAKEVEN')) return 'SBE';
  if (r.includes('STOP') || r.includes('SL')) return 'SL';
  if (r.includes('TP') || r.includes('TAKE_PROFIT')) return 'TP';
  if (r.includes('FLAT')) return 'FLT';
  if (r.includes('MANUAL')) return 'MAN';
  if (r.includes('TIMEOUT')) return 'TMO';
  return reason.slice(0, 3).toUpperCase();
}

function getExitColor(reason: string | undefined): string {
  if (!reason) return 'bg-zinc-600';
  const r = reason.toUpperCase();
  if (r.includes('TRAIL')) return 'bg-emerald-600';
  if (r.includes('TP') || r.includes('TAKE_PROFIT')) return 'bg-emerald-600';
  if (r.includes('SPOT_PULLBACK') || r.includes('SPOT_DECAY') || r.includes('SPOT_BREAKEVEN')) return 'bg-amber-600';
  if (r.includes('STOP') || r.includes('SL')) return 'bg-red-600';
  if (r.includes('FLAT')) return 'bg-zinc-500';
  return 'bg-zinc-600';
}

interface PairStats {
  totalTrades: number;
  closedTrades: number;
  wins: number;
  losses: number;
  winRate: number;
  netPnl: number;
  avgWin: number;
  avgLoss: number;
  last5: Trade[];
  openTrade: Trade | null;
  totalFees: number;
}

function computePairStats(trades: Trade[], pairName: PairName): PairStats {
  const pairTrades = getTradesForPair(trades, pairName);
  const closed = pairTrades.filter((t) => t.status === 'closed');
  const wins = closed.filter((t) => t.pnl > 0);
  const losses = closed.filter((t) => t.pnl <= 0);
  const netPnl = closed.reduce((sum, t) => sum + t.pnl, 0);
  const avgWin = wins.length > 0 ? wins.reduce((s, t) => s + t.pnl, 0) / wins.length : 0;
  const avgLoss = losses.length > 0 ? Math.abs(losses.reduce((s, t) => s + t.pnl, 0) / losses.length) : 0;
  const totalFees = closed.reduce((sum, t) => sum + (t.entry_fee ?? 0) + (t.exit_fee ?? 0), 0);

  // Sort closed trades by timestamp descending for last 5
  const sortedClosed = [...closed].sort(
    (a, b) => new Date(b.closed_at ?? b.timestamp).getTime() - new Date(a.closed_at ?? a.timestamp).getTime(),
  );

  // Find any open trade
  const openTrade = pairTrades.find((t) => t.status === 'open') ?? null;

  return {
    totalTrades: pairTrades.length,
    closedTrades: closed.length,
    wins: wins.length,
    losses: losses.length,
    winRate: closed.length > 0 ? (wins.length / closed.length) * 100 : 0,
    netPnl,
    avgWin,
    avgLoss,
    last5: sortedClosed.slice(0, 5),
    openTrade,
    totalFees,
  };
}

function getPairStatus(stats: PairStats, config: PairConfig | undefined): string {
  if (!config?.enabled) return 'Disabled';
  if (stats.openTrade) return 'In Trade';
  return 'Scanning';
}

function getStatusColor(status: string): string {
  switch (status) {
    case 'Disabled': return 'text-zinc-500';
    case 'In Trade': return 'text-amber-400';
    case 'Scanning': return 'text-emerald-400';
    case 'Cooldown': return 'text-blue-400';
    default: return 'text-zinc-400';
  }
}

function getStatusDot(status: string): string {
  switch (status) {
    case 'Disabled': return 'bg-zinc-500';
    case 'In Trade': return 'bg-amber-400';
    case 'Scanning': return 'bg-emerald-400 animate-pulse';
    case 'Cooldown': return 'bg-blue-400';
    default: return 'bg-zinc-500';
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function PairsPage() {
  const { trades, botStatus, pairConfigs, strategyLog } = useSupabase();

  // Compute stats per pair
  const pairStats = useMemo(() => {
    const result: Record<PairName, PairStats> = {} as any;
    for (const pair of PAIRS) {
      result[pair] = computePairStats(trades, pair);
    }
    return result;
  }, [trades]);

  // Get config for each pair
  const configMap = useMemo(() => {
    const map: Record<string, PairConfig> = {};
    for (const pc of pairConfigs) {
      map[pc.pair] = pc;
    }
    return map;
  }, [pairConfigs]);

  // Delta balance
  const deltaBalance = botStatus?.delta_balance ?? 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-4">
        <h1 className="text-xl md:text-2xl font-bold tracking-tight text-white">
          Pair Control
        </h1>
        <div className="flex items-center gap-2 text-xs text-zinc-500">
          <span>Delta Balance:</span>
          <span className="font-mono text-zinc-300">{formatCurrency(deltaBalance)}</span>
        </div>
      </div>

      {/* Allocation summary bar */}
      <AllocationBar configs={pairConfigs} balance={deltaBalance} />

      {/* Pair Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6">
        {PAIRS.map((pairName) => {
          const stats = pairStats[pairName];
          const config = configMap[pairName];
          const status = getPairStatus(stats, config);

          return (
            <PairCard
              key={pairName}
              pairName={pairName}
              stats={stats}
              config={config}
              status={status}
              balance={deltaBalance}
            />
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Allocation Summary Bar
// ---------------------------------------------------------------------------

function AllocationBar({ configs, balance }: { configs: PairConfig[]; balance: number }) {
  const totalAllocation = configs
    .filter((c) => c.enabled)
    .reduce((sum, c) => sum + c.allocation_pct, 0);
  const unallocated = Math.max(0, 100 - totalAllocation);

  return (
    <div className="bg-[#0d1117] border border-zinc-800 rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-zinc-500 uppercase tracking-wider">Allocation</span>
        <span className={cn(
          'text-xs font-mono font-medium',
          totalAllocation > 100 ? 'text-red-400' : 'text-zinc-300',
        )}>
          {totalAllocation}% allocated
          {totalAllocation > 100 && ' (over-allocated!)'}
        </span>
      </div>
      <div className="flex h-3 rounded-full overflow-hidden bg-zinc-800 gap-px">
        {configs
          .filter((c) => c.enabled && c.allocation_pct > 0)
          .map((c) => (
            <div
              key={c.pair}
              className="h-full transition-all duration-300"
              style={{
                width: `${c.allocation_pct}%`,
                backgroundColor: PAIR_COLORS[c.pair as PairName] ?? '#6b7280',
                opacity: 0.8,
              }}
              title={`${c.pair}: ${c.allocation_pct}%`}
            />
          ))}
        {unallocated > 0 && (
          <div
            className="h-full bg-zinc-700/50"
            style={{ width: `${unallocated}%` }}
            title={`Unallocated: ${unallocated}%`}
          />
        )}
      </div>
      <div className="flex items-center gap-4 mt-2">
        {configs
          .filter((c) => c.enabled && c.allocation_pct > 0)
          .map((c) => (
            <div key={c.pair} className="flex items-center gap-1.5 text-[10px] text-zinc-400">
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ backgroundColor: PAIR_COLORS[c.pair as PairName] ?? '#6b7280' }}
              />
              <span>{c.pair} {c.allocation_pct}%</span>
            </div>
          ))}
        {unallocated > 0 && (
          <div className="flex items-center gap-1.5 text-[10px] text-zinc-500">
            <span className="inline-block h-2 w-2 rounded-full bg-zinc-700" />
            <span>Free {unallocated}%</span>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pair Card
// ---------------------------------------------------------------------------

function PairCard({
  pairName,
  stats,
  config,
  status,
  balance,
}: {
  pairName: PairName;
  stats: PairStats;
  config: PairConfig | undefined;
  status: string;
  balance: number;
}) {
  const enabled = config?.enabled ?? true;
  const allocationPct = config?.allocation_pct ?? 0;
  const [localAllocation, setLocalAllocation] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);

  // Clear local override once DB value catches up to committed value
  useEffect(() => {
    if (localAllocation !== null && allocationPct === localAllocation) {
      setLocalAllocation(null);
    }
  }, [allocationPct, localAllocation]);

  // Allocation slider value (local override while dragging, else DB value)
  const sliderValue = localAllocation ?? allocationPct;
  const positionSize = balance * (sliderValue / 100);

  // Toggle enable/disable
  const handleToggle = useCallback(async () => {
    const client = getSupabase();
    if (!client) return;

    const newEnabled = !enabled;
    const newAllocation = newEnabled ? (allocationPct || 20) : 0;

    await client.from('pair_config').upsert({
      pair: pairName,
      enabled: newEnabled,
      allocation_pct: newAllocation,
      updated_at: new Date().toISOString(),
    });

    // Also send bot_command so engine picks it up immediately
    await client.from('bot_commands').insert({
      command: 'update_pair_config',
      params: { pair: pairName, enabled: newEnabled, allocation_pct: newAllocation },
      executed: false,
    });
  }, [enabled, allocationPct, pairName]);

  // Save allocation after slider change
  const handleAllocationCommit = useCallback(async (value: number) => {
    const client = getSupabase();
    if (!client) return;

    setSaving(true);
    await client.from('pair_config').upsert({
      pair: pairName,
      enabled: true,
      allocation_pct: value,
      updated_at: new Date().toISOString(),
    });

    await client.from('bot_commands').insert({
      command: 'update_pair_config',
      params: { pair: pairName, enabled: true, allocation_pct: value },
      executed: false,
    });

    setSaving(false);
  }, [pairName]);

  return (
    <div
      className={cn(
        'bg-[#0d1117] border rounded-xl p-4 md:p-5 transition-all',
        enabled ? 'border-zinc-700' : 'border-zinc-800 opacity-60',
      )}
      style={{ borderLeftColor: PAIR_COLORS[pairName], borderLeftWidth: 4 }}
    >
      {/* Header: Name + Status + Toggle */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold text-white"
            style={{ backgroundColor: PAIR_COLORS[pairName] + '30', border: `2px solid ${PAIR_COLORS[pairName]}` }}
          >
            {pairName}
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white">{pairName}/USD</h3>
            <div className="flex items-center gap-1.5">
              <span className={cn('inline-block h-2 w-2 rounded-full', getStatusDot(status))} />
              <span className={cn('text-xs font-medium', getStatusColor(status))}>{status}</span>
            </div>
          </div>
        </div>

        {/* Toggle */}
        <button
          onClick={handleToggle}
          className={cn(
            'relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200',
            enabled ? 'bg-emerald-500' : 'bg-zinc-700',
          )}
        >
          <span
            className={cn(
              'inline-block h-4 w-4 rounded-full bg-white transition-transform duration-200',
              enabled ? 'translate-x-6' : 'translate-x-1',
            )}
          />
        </button>
      </div>

      {/* Allocation Slider */}
      {enabled && (
        <div className="mb-4">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] text-zinc-500 uppercase tracking-wider">Allocation</span>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-zinc-300">{sliderValue}%</span>
              <span className="text-[10px] text-zinc-500">
                ({formatCurrency(positionSize)})
              </span>
              {saving && <span className="text-[10px] text-amber-400">Saving...</span>}
            </div>
          </div>
          <input
            type="range"
            min={0}
            max={70}
            step={5}
            value={sliderValue}
            onChange={(e) => setLocalAllocation(Number(e.target.value))}
            onMouseUp={() => handleAllocationCommit(sliderValue)}
            onTouchEnd={() => handleAllocationCommit(sliderValue)}
            className="w-full h-1.5 bg-zinc-700 rounded-full appearance-none cursor-pointer
                       [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
                       [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:shadow
                       [&::-webkit-slider-thumb]:cursor-pointer"
            style={{
              background: `linear-gradient(to right, ${PAIR_COLORS[pairName]} 0%, ${PAIR_COLORS[pairName]} ${(sliderValue / 70) * 100}%, #3f3f46 ${(sliderValue / 70) * 100}%)`,
            }}
          />
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div>
          <div className="text-[10px] text-zinc-500 uppercase">Trades</div>
          <div className="text-sm font-mono text-zinc-200">{stats.closedTrades}</div>
        </div>
        <div>
          <div className="text-[10px] text-zinc-500 uppercase">Win Rate</div>
          <div className={cn('text-sm font-mono', stats.winRate >= 50 ? 'text-emerald-400' : stats.closedTrades > 0 ? 'text-red-400' : 'text-zinc-400')}>
            {stats.closedTrades > 0 ? `${stats.winRate.toFixed(1)}%` : '---'}
          </div>
        </div>
        <div>
          <div className="text-[10px] text-zinc-500 uppercase">Net P&L</div>
          <div className={cn('text-sm font-mono font-bold', getPnLColor(stats.netPnl))}>
            {stats.closedTrades > 0 ? formatPnL(stats.netPnl) : '---'}
          </div>
        </div>
        <div>
          <div className="text-[10px] text-zinc-500 uppercase">Avg Win</div>
          <div className="text-sm font-mono text-emerald-400">
            {stats.avgWin > 0 ? formatPnL(stats.avgWin) : '---'}
          </div>
        </div>
        <div>
          <div className="text-[10px] text-zinc-500 uppercase">Avg Loss</div>
          <div className="text-sm font-mono text-red-400">
            {stats.avgLoss > 0 ? `-${formatCurrency(stats.avgLoss)}` : '---'}
          </div>
        </div>
        <div>
          <div className="text-[10px] text-zinc-500 uppercase">Fees</div>
          <div className="text-sm font-mono text-zinc-400">
            {stats.totalFees > 0 ? `-${formatCurrency(stats.totalFees)}` : '---'}
          </div>
        </div>
      </div>

      {/* W/L record */}
      <div className="flex items-center gap-2 mb-4">
        <span className="text-[10px] text-zinc-500 uppercase">Record:</span>
        <span className="text-xs font-mono text-emerald-400">{stats.wins}W</span>
        <span className="text-zinc-600">/</span>
        <span className="text-xs font-mono text-red-400">{stats.losses}L</span>
      </div>

      {/* Last 5 Trades */}
      <div>
        <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-2">Last 5 Trades</div>
        {stats.last5.length === 0 ? (
          <div className="text-xs text-zinc-600">No closed trades yet</div>
        ) : (
          <div className="flex items-center gap-1.5">
            {stats.last5.map((trade) => {
              const isWin = trade.pnl > 0;
              return (
                <div
                  key={trade.id}
                  className={cn(
                    'flex items-center gap-1 rounded-md px-2 py-1 text-[10px] font-mono font-medium',
                    isWin ? 'bg-emerald-400/10 text-emerald-400' : 'bg-red-400/10 text-red-400',
                  )}
                  title={`${formatPnL(trade.pnl)} | ${trade.exit_reason ?? '?'} | ${formatShortDate(trade.closed_at ?? trade.timestamp)}`}
                >
                  <span>{isWin ? 'W' : 'L'}</span>
                  <span className={cn('rounded px-1 py-px text-[8px] text-white', getExitColor(trade.exit_reason))}>
                    {getExitReasonShort(trade.exit_reason)}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Open Position Info */}
      {stats.openTrade && (
        <div className="mt-3 pt-3 border-t border-zinc-800">
          <div className="flex items-center justify-between">
            <div className="text-[10px] text-amber-400 uppercase tracking-wider">Open Position</div>
            <span className="text-[10px] text-zinc-500">
              {formatShortDate(stats.openTrade.timestamp)}
            </span>
          </div>
          <div className="flex items-center gap-4 mt-1 text-xs">
            <span className="text-zinc-400">
              Entry: <span className="text-zinc-200 font-mono">{formatCurrency(stats.openTrade.price)}</span>
            </span>
            {stats.openTrade.current_pnl != null && (
              <span className={cn('font-mono font-medium', getPnLColor(stats.openTrade.current_pnl))}>
                {formatPercentage(stats.openTrade.current_pnl)}
              </span>
            )}
            {stats.openTrade.position_state && (
              <Badge variant={stats.openTrade.position_state === 'trailing' ? 'success' : 'default'}>
                {stats.openTrade.position_state}
              </Badge>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

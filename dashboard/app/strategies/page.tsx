'use client';

import { useState, useMemo, useCallback } from 'react';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import { getSupabase } from '@/lib/supabase';
import { PnLChart } from '@/components/charts/PnLChart';
import { Badge } from '@/components/ui/Badge';
import {
  formatPnL,
  formatPercentage,
  formatCurrency,
  formatTimeAgo,
  formatDate,
  getStrategyColor,
  getStrategyLabel,
  getStrategyBadgeVariant,
  getExchangeLabel,
  getExchangeColor,
  cn,
  getPnLColor,
} from '@/lib/utils';
import type { Strategy, Trade, SetupConfig, SignalState } from '@/lib/types';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STRATEGIES: Strategy[] = ['scalp', 'options_scalp'];

// All setup types from the engine
const SETUP_TYPES = [
  'RSI_OVERRIDE',
  'BB_SQUEEZE',
  'LIQ_SWEEP',
  'FVG_FILL',
  'VOL_DIVERGENCE',
  'VWAP_RECLAIM',
  'TREND_CONT',
  'MOMENTUM_BURST',
  'MEAN_REVERT',
  'MULTI_SIGNAL',
  'MIXED',
] as const;

// Signal groups for the monitor
const CORE_SIGNALS = ['MOM_60S', 'VOL', 'RSI', 'BB'] as const;
const BONUS_SIGNALS = ['MOM_5M', 'TCONT', 'VWAP', 'BBSQZ', 'LIQSWEEP', 'FVG', 'VOLDIV'] as const;
const ALL_SIGNALS = [...CORE_SIGNALS, ...BONUS_SIGNALS] as const;

const ACTIVE_PAIRS = ['BTC', 'ETH', 'XRP', 'SOL'] as const;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function computeStats(trades: Trade[], strategy: Strategy) {
  const normalizedStrategy = strategy.toLowerCase();
  const filtered = trades.filter((t) => t.strategy.toLowerCase() === normalizedStrategy);
  const wins = filtered.filter((t) => t.pnl > 0).length;
  const losses = filtered.filter((t) => t.pnl < 0).length;
  const totalPnL = filtered.reduce((sum, t) => sum + t.pnl, 0);
  const avgPnL = filtered.length > 0 ? totalPnL / filtered.length : 0;

  // Spot vs futures breakdown
  const spotTrades = filtered.filter((t) => t.position_type === 'spot');
  const futuresTrades = filtered.filter((t) => t.position_type !== 'spot');
  const spotPnL = spotTrades.reduce((sum, t) => sum + t.pnl, 0);
  const futuresPnL = futuresTrades.reduce((sum, t) => sum + t.pnl, 0);

  const sorted = [...filtered].sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
  );
  const lastActive = sorted.length > 0 ? sorted[0].timestamp : null;

  return {
    totalTrades: filtered.length,
    wins,
    losses,
    winRate: filtered.length > 0 ? (wins / filtered.length) * 100 : 0,
    totalPnL,
    avgPnL,
    spotTrades: spotTrades.length,
    futuresTrades: futuresTrades.length,
    spotPnL,
    futuresPnL,
    lastActive,
  };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

function computeSetupStats(trades: Trade[], setupType: string) {
  const filtered = trades.filter(
    (t) => t.status === 'closed' && t.setup_type?.toUpperCase() === setupType.toUpperCase(),
  );
  const wins = filtered.filter((t) => t.pnl > 0).length;
  const losses = filtered.filter((t) => t.pnl <= 0).length;
  const totalPnL = filtered.reduce((sum, t) => sum + t.pnl, 0);
  const avgPnL = filtered.length > 0 ? totalPnL / filtered.length : 0;
  const winRate = filtered.length > 0 ? (wins / filtered.length) * 100 : 0;

  return { totalTrades: filtered.length, wins, losses, totalPnL, avgPnL, winRate };
}

export default function StrategiesPage() {
  const { trades, strategyLog, strategyPerformance, setupConfigs, signalStates } = useSupabase();
  const [activeTab, setActiveTab] = useState<Strategy>('scalp');

  const statsMap = useMemo(() => {
    const map = {} as Record<Strategy, ReturnType<typeof computeStats>>;
    for (const s of STRATEGIES) {
      map[s] = computeStats(trades, s);
    }
    return map;
  }, [trades]);

  const filteredTrades = useMemo(
    () => trades.filter((t) => t.strategy === activeTab),
    [trades, activeTab],
  );

  const recentLogs = useMemo(() => strategyLog.slice(0, 20), [strategyLog]);

  // Setup stats (computed from trades with setup_type)
  const setupStats = useMemo(() => {
    const map: Record<string, ReturnType<typeof computeSetupStats>> = {};
    for (const st of SETUP_TYPES) {
      map[st] = computeSetupStats(trades, st);
    }
    return map;
  }, [trades]);

  // Sort setups by P&L (worst to best)
  const sortedSetups = useMemo(() => {
    return [...SETUP_TYPES].sort(
      (a, b) => setupStats[a].totalPnL - setupStats[b].totalPnL,
    );
  }, [setupStats]);

  // Setup config map
  const setupConfigMap = useMemo(() => {
    const map: Record<string, SetupConfig> = {};
    for (const sc of setupConfigs) {
      map[sc.setup_type] = sc;
    }
    return map;
  }, [setupConfigs]);

  // Signal state map: { pair: { signal_id: SignalState } }
  const signalMap = useMemo(() => {
    const map: Record<string, Record<string, SignalState>> = {};
    for (const s of signalStates) {
      if (!map[s.pair]) map[s.pair] = {};
      map[s.pair][s.signal_id] = s;
    }
    return map;
  }, [signalStates]);

  // Toggle setup enable/disable
  const handleSetupToggle = useCallback(async (setupType: string) => {
    const client = getSupabase();
    if (!client) return;

    const current = setupConfigMap[setupType];
    const newEnabled = !(current?.enabled ?? true);

    await client.from('setup_config').upsert({
      setup_type: setupType,
      enabled: newEnabled,
      updated_at: new Date().toISOString(),
    });

    await client.from('bot_commands').insert({
      command: 'update_config',
      params: { setup_type: setupType, enabled: newEnabled },
      executed: false,
    });
  }, [setupConfigMap]);

  return (
    <div className="space-y-6">
      <h1 className="text-xl md:text-2xl font-bold tracking-tight text-white">
        Strategy Performance
      </h1>

      {/* ------------------------------------------------------------------- */}
      {/* Strategy cards                                                       */}
      {/* ------------------------------------------------------------------- */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 md:gap-6">
        {STRATEGIES.map((strategy) => {
          const stats = statsMap[strategy];
          const color = getStrategyColor(strategy);

          return (
            <div
              key={strategy}
              className="bg-card border border-zinc-800 rounded-xl p-4 md:p-6"
              style={{ borderLeftColor: color, borderLeftWidth: 4 }}
            >
              <h3 className="text-lg font-semibold text-white mb-4">
                {getStrategyLabel(strategy)}
              </h3>

              <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                <div>
                  <dt className="text-zinc-500">Total Trades</dt>
                  <dd className="font-medium text-zinc-200">{stats.totalTrades}</dd>
                </div>
                <div>
                  <dt className="text-zinc-500">Win Rate</dt>
                  <dd className="font-medium text-zinc-200">{formatPercentage(stats.winRate)}</dd>
                </div>
                <div>
                  <dt className="text-zinc-500">Wins</dt>
                  <dd className="font-medium text-emerald-400">{stats.wins}</dd>
                </div>
                <div>
                  <dt className="text-zinc-500">Losses</dt>
                  <dd className="font-medium text-red-400">{stats.losses}</dd>
                </div>
                <div>
                  <dt className="text-zinc-500">Total P&L</dt>
                  <dd className={cn('font-medium font-mono', stats.totalPnL >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                    {formatPnL(stats.totalPnL)}
                  </dd>
                </div>
                <div>
                  <dt className="text-zinc-500">Avg P&L</dt>
                  <dd className={cn('font-medium font-mono', stats.avgPnL >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                    {formatCurrency(stats.avgPnL)}
                  </dd>
                </div>
                {/* Spot vs Futures breakdown */}
                <div>
                  <dt className="text-zinc-500">Spot P&L</dt>
                  <dd className={cn('font-medium font-mono text-xs', stats.spotPnL >= 0 ? 'text-blue-400' : 'text-red-400')}>
                    {formatPnL(stats.spotPnL)}
                    <span className="text-zinc-600 ml-1">({stats.spotTrades})</span>
                  </dd>
                </div>
                <div>
                  <dt className="text-zinc-500">Futures P&L</dt>
                  <dd className={cn('font-medium font-mono text-xs', stats.futuresPnL >= 0 ? 'text-orange-400' : 'text-red-400')}>
                    {formatPnL(stats.futuresPnL)}
                    <span className="text-zinc-600 ml-1">({stats.futuresTrades})</span>
                  </dd>
                </div>
              </dl>

              {stats.lastActive && (
                <p className="mt-4 text-xs text-zinc-500">
                  Last active {formatTimeAgo(stats.lastActive)}
                </p>
              )}
            </div>
          );
        })}
      </div>

      {/* ------------------------------------------------------------------- */}
      {/* Strategy Performance by Exchange (from Supabase view)                */}
      {/* ------------------------------------------------------------------- */}
      {strategyPerformance.length > 0 && (
        <div className="bg-card border border-zinc-800 rounded-xl p-4 md:p-6">
          <h3 className="text-sm font-medium text-zinc-400 uppercase tracking-wider mb-4">
            Strategy Performance by Exchange
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-zinc-500 border-b border-zinc-800">
                  <th className="pb-2 pr-3 font-medium">Strategy</th>
                  <th className="pb-2 pr-3 font-medium hidden sm:table-cell">Exchange</th>
                  <th className="pb-2 pr-3 font-medium text-right">Trades</th>
                  <th className="pb-2 pr-3 font-medium text-right hidden sm:table-cell">Win Rate</th>
                  <th className="pb-2 pr-3 font-medium text-right">P&L</th>
                  <th className="pb-2 pr-3 font-medium text-right hidden md:table-cell">Best</th>
                  <th className="pb-2 font-medium text-right hidden md:table-cell">Worst</th>
                </tr>
              </thead>
              <tbody>
                {strategyPerformance.map((sp, idx) => (
                  <tr
                    key={`${sp.strategy}-${sp.exchange}`}
                    className={cn(
                      'border-b border-zinc-800/50 last:border-0',
                      idx % 2 === 0 ? 'bg-transparent' : 'bg-zinc-900/30',
                    )}
                  >
                    <td className="py-2.5 pr-3">
                      <Badge variant={getStrategyBadgeVariant(sp.strategy)}>
                        {getStrategyLabel(sp.strategy)}
                      </Badge>
                    </td>
                    <td className="py-2.5 pr-3 hidden sm:table-cell">
                      <span className="inline-flex items-center gap-1.5">
                        <span
                          className="w-2 h-2 rounded-full inline-block"
                          style={{ backgroundColor: getExchangeColor(sp.exchange) }}
                        />
                        <span className="text-zinc-300">{getExchangeLabel(sp.exchange)}</span>
                      </span>
                    </td>
                    <td className="py-2.5 pr-3 text-right font-mono text-zinc-300">{sp.total_trades}</td>
                    <td className="py-2.5 pr-3 text-right font-mono text-zinc-300 hidden sm:table-cell">{formatPercentage(sp.win_rate_pct)}</td>
                    <td className={cn('py-2.5 pr-3 text-right font-mono', sp.total_pnl >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                      {formatPnL(sp.total_pnl)}
                    </td>
                    <td className="py-2.5 pr-3 text-right font-mono text-emerald-400 hidden md:table-cell">{formatPnL(sp.best_trade)}</td>
                    <td className="py-2.5 text-right font-mono text-red-400 hidden md:table-cell">{formatPnL(sp.worst_trade)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------- */}
      {/* Tabbed P&L chart per strategy                                        */}
      {/* ------------------------------------------------------------------- */}
      <div>
        <div className="flex gap-1 mb-4 overflow-x-auto">
          {STRATEGIES.map((strategy) => (
            <button
              key={strategy}
              onClick={() => setActiveTab(strategy)}
              className={cn(
                'px-4 py-2 text-sm font-medium rounded-lg transition-colors whitespace-nowrap',
                activeTab === strategy
                  ? 'bg-zinc-700 text-white'
                  : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800',
              )}
            >
              {getStrategyLabel(strategy)}
            </button>
          ))}
        </div>
        <PnLChart trades={filteredTrades} strategy={activeTab} />
      </div>

      {/* ------------------------------------------------------------------- */}
      {/* Strategy Switch Log (timeline)                                       */}
      {/* ------------------------------------------------------------------- */}
      <div className="bg-card border border-zinc-800 rounded-xl p-6">
        <h3 className="text-sm font-medium text-zinc-400 uppercase tracking-wider mb-6">
          Strategy Switch Log
        </h3>

        {recentLogs.length === 0 ? (
          <p className="text-sm text-zinc-500">No strategy switch events yet</p>
        ) : (
          <div className="relative">
            <div className="absolute left-[7px] top-2 bottom-2 w-px bg-zinc-700" />

            <ul className="space-y-6">
              {recentLogs.map((entry) => (
                <li key={entry.id} className="relative flex gap-4 pl-6">
                  <span className="absolute left-0 top-1.5 h-3.5 w-3.5 rounded-full border-2 border-zinc-700 bg-zinc-900" />

                  <div className="min-w-0 flex-1">
                    <p className="text-xs text-zinc-500 mb-1">
                      {formatDate(entry.timestamp)}
                    </p>
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      <Badge variant="default">{entry.market_condition}</Badge>
                      <Badge variant={getStrategyBadgeVariant(entry.strategy_selected)}>
                        {getStrategyLabel(entry.strategy_selected)}
                      </Badge>
                    </div>
                    <p className="text-sm text-zinc-300">{entry.reason}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* ------------------------------------------------------------------- */}
      {/* Setup Control                                                        */}
      {/* ------------------------------------------------------------------- */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-4">Setup Control</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {sortedSetups.map((setupType) => {
            const stats = setupStats[setupType];
            const config = setupConfigMap[setupType];
            const enabled = config?.enabled ?? true;
            const wr = stats.winRate;

            // HOT/COLD badge
            let badge: { label: string; variant: 'success' | 'danger' | 'warning' } | null = null;
            if (stats.totalTrades >= 3 && wr >= 60) badge = { label: 'HOT', variant: 'success' };
            else if (stats.totalTrades >= 3 && wr < 30) badge = { label: 'COLD', variant: 'danger' };

            // BG tint based on profitability
            const bgTint = stats.totalTrades > 0
              ? stats.totalPnL >= 0
                ? 'bg-emerald-400/[0.03]'
                : 'bg-red-400/[0.03]'
              : '';

            return (
              <div
                key={setupType}
                className={cn(
                  'border rounded-xl p-3 transition-all',
                  enabled ? 'border-zinc-700' : 'border-zinc-800 opacity-50',
                  bgTint,
                )}
              >
                {/* Header: name + badge + toggle */}
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-xs font-semibold text-white truncate">
                      {setupType.replace(/_/g, ' ')}
                    </span>
                    {badge && (
                      <Badge variant={badge.variant} className="text-[8px] px-1.5 py-0">
                        {badge.label}
                      </Badge>
                    )}
                  </div>
                  <button
                    onClick={() => handleSetupToggle(setupType)}
                    className={cn(
                      'relative inline-flex h-5 w-9 items-center rounded-full transition-colors duration-200 shrink-0',
                      enabled ? 'bg-emerald-500' : 'bg-zinc-700',
                    )}
                  >
                    <span
                      className={cn(
                        'inline-block h-3 w-3 rounded-full bg-white transition-transform duration-200',
                        enabled ? 'translate-x-5' : 'translate-x-1',
                      )}
                    />
                  </button>
                </div>

                {/* Stats */}
                <div className="grid grid-cols-3 gap-2 text-[10px]">
                  <div>
                    <span className="text-zinc-500">Trades</span>
                    <div className="text-zinc-200 font-mono">{stats.totalTrades}</div>
                  </div>
                  <div>
                    <span className="text-zinc-500">WR</span>
                    <div className={cn(
                      'font-mono',
                      stats.totalTrades > 0 ? (wr >= 50 ? 'text-emerald-400' : 'text-red-400') : 'text-zinc-500',
                    )}>
                      {stats.totalTrades > 0 ? `${wr.toFixed(0)}%` : '---'}
                    </div>
                  </div>
                  <div>
                    <span className="text-zinc-500">P&L</span>
                    <div className={cn('font-mono', getPnLColor(stats.totalPnL))}>
                      {stats.totalTrades > 0 ? formatPnL(stats.totalPnL) : '---'}
                    </div>
                  </div>
                </div>

                {/* Avg P&L */}
                {stats.totalTrades > 0 && (
                  <div className="mt-1.5 text-[10px]">
                    <span className="text-zinc-500">Avg: </span>
                    <span className={cn('font-mono', getPnLColor(stats.avgPnL))}>
                      {formatCurrency(stats.avgPnL)}
                    </span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* ------------------------------------------------------------------- */}
      {/* Signal Monitor                                                       */}
      {/* ------------------------------------------------------------------- */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-4">Signal Monitor</h2>
        {signalStates.length === 0 ? (
          <div className="bg-[#0d1117] border border-zinc-800 rounded-xl p-8 text-center text-sm text-zinc-500">
            No signal data yet — engine will publish signals when scanning
          </div>
        ) : (
          <div className="bg-[#0d1117] border border-zinc-800 rounded-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-zinc-900/50">
                    <th className="px-3 py-2.5 text-left text-[10px] font-medium uppercase tracking-wider text-zinc-500 sticky left-0 bg-zinc-900/50 z-10">
                      Signal
                    </th>
                    {ACTIVE_PAIRS.map((pair) => (
                      <th
                        key={pair}
                        className="px-3 py-2.5 text-center text-[10px] font-medium uppercase tracking-wider text-zinc-500"
                      >
                        {pair}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {/* Core signals header */}
                  <tr>
                    <td
                      colSpan={ACTIVE_PAIRS.length + 1}
                      className="px-3 py-1.5 text-[9px] font-semibold text-zinc-500 uppercase tracking-widest bg-zinc-900/30"
                    >
                      Core (4/4 gate)
                    </td>
                  </tr>
                  {CORE_SIGNALS.map((signalId) => (
                    <SignalRow key={signalId} signalId={signalId} pairs={ACTIVE_PAIRS} signalMap={signalMap} />
                  ))}
                  {/* Bonus signals header */}
                  <tr>
                    <td
                      colSpan={ACTIVE_PAIRS.length + 1}
                      className="px-3 py-1.5 text-[9px] font-semibold text-zinc-500 uppercase tracking-widest bg-zinc-900/30"
                    >
                      Bonus (7 confirmation)
                    </td>
                  </tr>
                  {BONUS_SIGNALS.map((signalId) => (
                    <SignalRow key={signalId} signalId={signalId} pairs={ACTIVE_PAIRS} signalMap={signalMap} />
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Signal Row Component
// ---------------------------------------------------------------------------

function SignalRow({
  signalId,
  pairs,
  signalMap,
}: {
  signalId: string;
  pairs: readonly string[];
  signalMap: Record<string, Record<string, SignalState>>;
}) {
  return (
    <tr className="border-b border-zinc-800/30">
      <td className="px-3 py-2 text-xs font-mono text-zinc-300 sticky left-0 bg-[#0d1117] z-10">
        {signalId}
      </td>
      {pairs.map((pair) => {
        const signal = signalMap[pair]?.[signalId];
        if (!signal) {
          return (
            <td key={pair} className="px-3 py-2 text-center text-zinc-600">
              —
            </td>
          );
        }

        const dirArrow =
          signal.direction === 'bull' ? '↑' :
          signal.direction === 'bear' ? '↓' : '—';
        const dirColor =
          signal.direction === 'bull' ? 'text-emerald-400' :
          signal.direction === 'bear' ? 'text-red-400' : 'text-zinc-500';

        return (
          <td key={pair} className="px-3 py-2 text-center">
            <div className="flex items-center justify-center gap-1.5">
              {/* Firing dot */}
              <span
                className={cn(
                  'inline-block h-2 w-2 rounded-full',
                  signal.firing ? 'bg-emerald-400 shadow-[0_0_4px_rgba(52,211,153,0.5)]' : 'bg-zinc-700',
                )}
              />
              {/* Value */}
              <span className="font-mono text-zinc-300 text-[10px]">
                {signal.value != null ? signal.value.toFixed(2) : '—'}
              </span>
              {/* Direction arrow */}
              <span className={cn('text-[10px]', dirColor)}>{dirArrow}</span>
            </div>
          </td>
        );
      })}
    </tr>
  );
}

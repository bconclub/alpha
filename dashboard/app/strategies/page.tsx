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
  getStrategyColor,
  getStrategyLabel,
  getStrategyBadgeVariant,
  getExchangeLabel,
  getExchangeColor,
  cn,
  getPnLColor,
} from '@/lib/utils';
import type { Strategy, Trade, SetupConfig, SignalState, PairConfig } from '@/lib/types';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STRATEGIES: Strategy[] = ['scalp', 'options_scalp'];

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

const ALL_PAIR_BASES = ['BTC', 'ETH', 'XRP', 'SOL'] as const;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function extractBaseAsset(pair: string): string {
  if (pair.includes('/')) return pair.split('/')[0];
  return pair.replace(/USD.*$/, '');
}

function computeStats(trades: Trade[], strategy: Strategy) {
  const normalizedStrategy = strategy.toLowerCase();
  const filtered = trades.filter((t) => t.strategy.toLowerCase() === normalizedStrategy);
  const wins = filtered.filter((t) => t.pnl > 0).length;
  const losses = filtered.filter((t) => t.pnl < 0).length;
  const totalPnL = filtered.reduce((sum, t) => sum + t.pnl, 0);
  const avgPnL = filtered.length > 0 ? totalPnL / filtered.length : 0;

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

function computeSetupStats(trades: Trade[], setupType: string) {
  const filtered = trades.filter(
    (t) => t.status === 'closed' && t.setup_type?.toUpperCase() === setupType.toUpperCase(),
  );
  const wins = filtered.filter((t) => t.pnl > 0).length;
  const losses = filtered.filter((t) => t.pnl <= 0).length;
  const totalPnL = filtered.reduce((sum, t) => sum + t.pnl, 0);
  const avgWin = wins > 0 ? filtered.filter(t => t.pnl > 0).reduce((s, t) => s + t.pnl, 0) / wins : 0;
  const avgLoss = losses > 0 ? filtered.filter(t => t.pnl <= 0).reduce((s, t) => s + t.pnl, 0) / losses : 0;
  const winRate = filtered.length > 0 ? (wins / filtered.length) * 100 : 0;

  // Last 5 trades (W/L)
  const sorted = [...filtered].sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
  );
  const last5 = sorted.slice(0, 5).map((t) => t.pnl > 0);

  return { totalTrades: filtered.length, wins, losses, totalPnL, avgWin, avgLoss, winRate, last5 };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function StrategiesPage() {
  const { trades, strategyLog, strategyPerformance, setupConfigs, signalStates, pairConfigs } = useSupabase();
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

  // Setup stats
  const setupStats = useMemo(() => {
    const map: Record<string, ReturnType<typeof computeSetupStats>> = {};
    for (const st of SETUP_TYPES) {
      map[st] = computeSetupStats(trades, st);
    }
    return map;
  }, [trades]);

  // Sort setups by P&L ascending (worst first)
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

  // Signal state map: { pairBase: { signal_id: SignalState } }
  const signalMap = useMemo(() => {
    const map: Record<string, Record<string, SignalState>> = {};
    for (const s of signalStates) {
      if (!map[s.pair]) map[s.pair] = {};
      map[s.pair][s.signal_id] = s;
    }
    return map;
  }, [signalStates]);

  // Determine which pairs are active (have signal data + not disabled)
  const disabledBases = useMemo(() => {
    const disabled = new Set<string>();
    for (const pc of pairConfigs) {
      if (!pc.enabled) {
        disabled.add(extractBaseAsset(pc.pair));
      }
    }
    return disabled;
  }, [pairConfigs]);

  const activePairs = useMemo(() => {
    return ALL_PAIR_BASES.filter(
      (base) => !disabledBases.has(base) && signalMap[base] != null,
    );
  }, [disabledBases, signalMap]);

  // Filter signal rows: only show signals that have data for at least one active pair
  const visibleCoreSignals = useMemo(() => {
    return CORE_SIGNALS.filter((sigId) =>
      activePairs.some((p) => {
        const s = signalMap[p]?.[sigId];
        return s != null;
      }),
    );
  }, [activePairs, signalMap]);

  const visibleBonusSignals = useMemo(() => {
    return BONUS_SIGNALS.filter((sigId) =>
      activePairs.some((p) => {
        const s = signalMap[p]?.[sigId];
        return s != null;
      }),
    );
  }, [activePairs, signalMap]);

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
      {/* Setup Control                                                        */}
      {/* ------------------------------------------------------------------- */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-4">Setup Control</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {sortedSetups.map((setupType) => {
            const stats = setupStats[setupType];
            const config = setupConfigMap[setupType];
            const enabled = config?.enabled ?? true;
            const wr = stats.winRate;

            // Background tint based on WR
            const bgTint = stats.totalTrades === 0
              ? ''
              : wr > 50
                ? 'bg-emerald-500/[0.06]'
                : wr < 30
                  ? 'bg-red-500/[0.06]'
                  : '';

            return (
              <div
                key={setupType}
                className={cn(
                  'border rounded-xl p-4 transition-all',
                  enabled ? 'border-zinc-700' : 'border-zinc-800 opacity-40',
                  bgTint,
                )}
              >
                {/* Header: name + toggle */}
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-sm font-semibold text-white truncate">
                      {setupType.replace(/_/g, ' ')}
                    </span>
                    {stats.totalTrades >= 3 && wr >= 60 && (
                      <Badge variant="success" className="text-[8px] px-1.5 py-0">HOT</Badge>
                    )}
                    {stats.totalTrades >= 3 && wr < 30 && (
                      <Badge variant="danger" className="text-[8px] px-1.5 py-0">COLD</Badge>
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

                {stats.totalTrades === 0 ? (
                  <p className="text-xs text-zinc-600">No trades</p>
                ) : (
                  <>
                    {/* Stats row */}
                    <div className="grid grid-cols-3 gap-3 text-xs mb-3">
                      <div>
                        <span className="text-zinc-500 block text-[10px]">Trades</span>
                        <div className="text-zinc-200 font-mono font-medium">{stats.totalTrades}</div>
                      </div>
                      <div>
                        <span className="text-zinc-500 block text-[10px]">Win Rate</span>
                        <div className={cn(
                          'font-mono font-medium',
                          wr >= 50 ? 'text-emerald-400' : 'text-red-400',
                        )}>
                          {wr.toFixed(0)}%
                        </div>
                      </div>
                      <div>
                        <span className="text-zinc-500 block text-[10px]">Net P&L</span>
                        <div className={cn('font-mono font-medium', getPnLColor(stats.totalPnL))}>
                          {formatPnL(stats.totalPnL)}
                        </div>
                      </div>
                    </div>

                    {/* Last 5 trades dots */}
                    {stats.last5.length > 0 && (
                      <div className="flex items-center gap-1 mb-2">
                        <span className="text-[10px] text-zinc-500 mr-1">Last {stats.last5.length}:</span>
                        {stats.last5.map((isWin, i) => (
                          <span
                            key={i}
                            className={cn(
                              'inline-block h-2.5 w-2.5 rounded-full',
                              isWin
                                ? 'bg-emerald-400 shadow-[0_0_3px_rgba(52,211,153,0.4)]'
                                : 'bg-red-400 shadow-[0_0_3px_rgba(248,113,113,0.4)]',
                            )}
                            title={isWin ? 'Win' : 'Loss'}
                          />
                        ))}
                      </div>
                    )}

                    {/* Avg win / avg loss */}
                    <div className="flex gap-3 text-[10px] font-mono">
                      <span className="text-emerald-400">
                        Avg W: {formatCurrency(stats.avgWin)}
                      </span>
                      <span className="text-red-400">
                        Avg L: {formatCurrency(stats.avgLoss)}
                      </span>
                    </div>
                  </>
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
        ) : activePairs.length === 0 ? (
          <div className="bg-[#0d1117] border border-zinc-800 rounded-xl p-8 text-center text-sm text-zinc-500">
            No active pairs with signal data
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
                    {activePairs.map((pair) => (
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
                  {/* Core signals */}
                  {visibleCoreSignals.length > 0 && (
                    <>
                      <tr>
                        <td
                          colSpan={activePairs.length + 1}
                          className="px-3 py-1.5 text-[9px] font-semibold text-zinc-500 uppercase tracking-widest bg-zinc-900/30"
                        >
                          Core 4
                        </td>
                      </tr>
                      {visibleCoreSignals.map((signalId) => (
                        <SignalRow key={signalId} signalId={signalId} pairs={activePairs} signalMap={signalMap} />
                      ))}
                    </>
                  )}
                  {/* Bonus signals */}
                  {visibleBonusSignals.length > 0 && (
                    <>
                      <tr>
                        <td
                          colSpan={activePairs.length + 1}
                          className="px-3 py-1.5 text-[9px] font-semibold text-zinc-500 uppercase tracking-widest bg-zinc-900/30"
                        >
                          Bonus
                        </td>
                      </tr>
                      {visibleBonusSignals.map((signalId) => (
                        <SignalRow key={signalId} signalId={signalId} pairs={activePairs} signalMap={signalMap} />
                      ))}
                    </>
                  )}
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
  pairs: readonly string[] | string[];
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
            <td key={pair} className="px-3 py-2 text-center text-zinc-700">
              —
            </td>
          );
        }

        const dirArrow =
          signal.direction === 'bull' ? '\u2191' :
          signal.direction === 'bear' ? '\u2193' : '';
        const firing = signal.firing;

        return (
          <td key={pair} className="px-3 py-2 text-center">
            <div className="flex items-center justify-center gap-1.5">
              {/* Firing dot */}
              <span
                className={cn(
                  'inline-block h-2 w-2 rounded-full',
                  firing ? 'bg-emerald-400 shadow-[0_0_4px_rgba(52,211,153,0.5)]' : 'bg-zinc-700',
                )}
              />
              {/* Value */}
              <span className={cn(
                'font-mono text-[10px]',
                firing ? 'text-emerald-300' : 'text-zinc-600',
              )}>
                {signal.value != null ? signal.value.toFixed(2) : '—'}
              </span>
              {/* Direction arrow */}
              {dirArrow && (
                <span className={cn(
                  'text-[10px]',
                  signal.direction === 'bull' ? 'text-emerald-400' :
                  signal.direction === 'bear' ? 'text-red-400' : 'text-zinc-500',
                )}>
                  {dirArrow}
                </span>
              )}
            </div>
          </td>
        );
      })}
    </tr>
  );
}

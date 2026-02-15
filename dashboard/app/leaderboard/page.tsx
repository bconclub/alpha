'use client';

import { useState, useMemo } from 'react';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import { ExchangeToggle } from '@/components/dashboard/ExchangeToggle';
import type { Trade } from '@/lib/types';
import {
  formatPnL,
  formatPercentage,
  formatCurrency,
  formatShortDate,
  cn,
  getPnLColor,
  getStrategyLabel,
  getStrategyBadgeVariant,
  getExchangeLabel,
  getExchangeColor,
  getPositionTypeLabel,
  getPositionTypeColor,
  formatLeverage,
} from '@/lib/utils';
import { Badge } from '@/components/ui/Badge';

// ---------------------------------------------------------------------------
// Types & Constants
// ---------------------------------------------------------------------------

type SortKey = 'pnl' | 'pnl_pct' | 'duration' | 'date';
type SortDir = 'asc' | 'desc';

const TRADES_PER_PAGE = 25;

// Delta contract sizes (match engine)
const DELTA_CONTRACT_SIZE: Record<string, number> = {
  'BTC/USD:USD': 0.001,
  'ETH/USD:USD': 0.01,
  'SOL/USD:USD': 1.0,
  'XRP/USD:USD': 1.0,
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function extractBaseAsset(pair: string): string {
  if (pair.includes('/')) return pair.split('/')[0];
  return pair.replace(/USD.*$/, '');
}

function getDurationMs(trade: Trade): number | null {
  if (!trade.timestamp) return null;
  const open = new Date(trade.timestamp).getTime();
  if (trade.closed_at) {
    return new Date(trade.closed_at).getTime() - open;
  }
  return null;
}

function formatDuration(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  if (totalSec < 60) return `${totalSec}s`;
  const mins = Math.floor(totalSec / 60);
  const secs = totalSec % 60;
  if (mins < 60) return `${mins}m ${secs}s`;
  const hours = Math.floor(mins / 60);
  const remMins = mins % 60;
  if (hours < 24) return `${hours}h ${remMins}m`;
  const days = Math.floor(hours / 24);
  return `${days}d ${hours % 24}h`;
}

function computeNotional(trade: Trade): number {
  let coinAmount = trade.amount;
  if (trade.exchange === 'delta') {
    const contractSize = DELTA_CONTRACT_SIZE[trade.pair] ?? 1.0;
    coinAmount = trade.amount * contractSize;
  }
  return trade.price * coinAmount;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function LeaderboardPage() {
  const { filteredTrades } = useSupabase();

  const [sortKey, setSortKey] = useState<SortKey>('pnl');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [page, setPage] = useState(1);

  // Only closed trades with P&L data
  const closedTrades = useMemo(
    () => filteredTrades.filter((t) => t.status === 'closed' && t.pnl !== 0),
    [filteredTrades],
  );

  // Sorted trades
  const sorted = useMemo(() => {
    const arr = [...closedTrades];
    arr.sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case 'pnl':
          cmp = a.pnl - b.pnl;
          break;
        case 'pnl_pct':
          cmp = (a.pnl_pct ?? 0) - (b.pnl_pct ?? 0);
          break;
        case 'duration': {
          const da = getDurationMs(a) ?? Infinity;
          const db = getDurationMs(b) ?? Infinity;
          cmp = da - db;
          break;
        }
        case 'date':
          cmp = new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime();
          break;
      }
      return sortDir === 'desc' ? -cmp : cmp;
    });
    return arr;
  }, [closedTrades, sortKey, sortDir]);

  // Stats
  const stats = useMemo(() => {
    if (closedTrades.length === 0) {
      return {
        bestTrade: null as Trade | null,
        worstTrade: null as Trade | null,
        avgDuration: 0,
        avgWin: 0,
        avgLoss: 0,
        winRate: 0,
        profitFactor: 0,
        totalPnl: 0,
        totalTrades: 0,
        wins: 0,
        losses: 0,
      };
    }

    let bestTrade = closedTrades[0];
    let worstTrade = closedTrades[0];
    let totalDuration = 0;
    let durationCount = 0;
    let totalWinPnl = 0;
    let totalLossPnl = 0;
    let wins = 0;
    let losses = 0;
    let totalPnl = 0;

    for (const t of closedTrades) {
      if (t.pnl > bestTrade.pnl) bestTrade = t;
      if (t.pnl < worstTrade.pnl) worstTrade = t;

      totalPnl += t.pnl;

      if (t.pnl > 0) {
        wins++;
        totalWinPnl += t.pnl;
      } else {
        losses++;
        totalLossPnl += Math.abs(t.pnl);
      }

      const dur = getDurationMs(t);
      if (dur != null) {
        totalDuration += dur;
        durationCount++;
      }
    }

    return {
      bestTrade,
      worstTrade,
      avgDuration: durationCount > 0 ? totalDuration / durationCount : 0,
      avgWin: wins > 0 ? totalWinPnl / wins : 0,
      avgLoss: losses > 0 ? totalLossPnl / losses : 0,
      winRate: closedTrades.length > 0 ? (wins / closedTrades.length) * 100 : 0,
      profitFactor: totalLossPnl > 0 ? totalWinPnl / totalLossPnl : totalWinPnl > 0 ? Infinity : 0,
      totalPnl,
      totalTrades: closedTrades.length,
      wins,
      losses,
    };
  }, [closedTrades]);

  // Pagination
  const totalPages = Math.max(1, Math.ceil(sorted.length / TRADES_PER_PAGE));
  const safePage = Math.min(page, totalPages);
  const startIdx = (safePage - 1) * TRADES_PER_PAGE;
  const endIdx = Math.min(startIdx + TRADES_PER_PAGE, sorted.length);
  const visible = sorted.slice(startIdx, endIdx);

  // Sort handler
  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'));
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
    setPage(1);
  }

  const sortBtn = (key: SortKey, label: string) => (
    <button
      onClick={() => handleSort(key)}
      className={cn(
        'inline-flex items-center gap-1 cursor-pointer select-none',
        'text-xs font-medium uppercase tracking-wider transition-colors',
        sortKey === key ? 'text-white' : 'text-zinc-400 hover:text-zinc-200',
      )}
    >
      {label}
      {sortKey === key && (
        <span className="text-[10px]">{sortDir === 'desc' ? '\u25BC' : '\u25B2'}</span>
      )}
    </button>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-4">
        <h1 className="text-xl md:text-2xl font-bold tracking-tight text-white">
          Top Trades
        </h1>
        <ExchangeToggle />
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {/* Best Trade */}
        <div className="bg-[#0d1117] border border-zinc-800 rounded-xl p-3">
          <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Best Trade</div>
          <div className={cn('text-lg font-bold font-mono', getPnLColor(stats.bestTrade?.pnl ?? 0))}>
            {stats.bestTrade ? formatPnL(stats.bestTrade.pnl) : '---'}
          </div>
          {stats.bestTrade && (
            <div className="text-[10px] text-zinc-500 mt-0.5">
              {extractBaseAsset(stats.bestTrade.pair)} · {formatShortDate(stats.bestTrade.timestamp)}
            </div>
          )}
        </div>

        {/* Win Rate */}
        <div className="bg-[#0d1117] border border-zinc-800 rounded-xl p-3">
          <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Win Rate</div>
          <div className={cn('text-lg font-bold font-mono', stats.winRate >= 50 ? 'text-[#00c853]' : 'text-[#ff1744]')}>
            {stats.winRate.toFixed(1)}%
          </div>
          <div className="text-[10px] text-zinc-500 mt-0.5">
            {stats.wins}W / {stats.losses}L
          </div>
        </div>

        {/* Total P&L */}
        <div className="bg-[#0d1117] border border-zinc-800 rounded-xl p-3">
          <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Total P&L</div>
          <div className={cn('text-lg font-bold font-mono', getPnLColor(stats.totalPnl))}>
            {formatPnL(stats.totalPnl)}
          </div>
          <div className="text-[10px] text-zinc-500 mt-0.5">
            {stats.totalTrades} trades
          </div>
        </div>

        {/* Avg Win */}
        <div className="bg-[#0d1117] border border-zinc-800 rounded-xl p-3">
          <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Avg Win</div>
          <div className="text-lg font-bold font-mono text-[#00c853]">
            {stats.avgWin > 0 ? formatPnL(stats.avgWin) : '---'}
          </div>
        </div>

        {/* Avg Loss */}
        <div className="bg-[#0d1117] border border-zinc-800 rounded-xl p-3">
          <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Avg Loss</div>
          <div className="text-lg font-bold font-mono text-[#ff1744]">
            {stats.avgLoss > 0 ? `-${formatPnL(stats.avgLoss).replace(/[+-]/, '')}` : '---'}
          </div>
        </div>

        {/* Profit Factor */}
        <div className="bg-[#0d1117] border border-zinc-800 rounded-xl p-3">
          <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Profit Factor</div>
          <div className={cn('text-lg font-bold font-mono', stats.profitFactor >= 1 ? 'text-[#00c853]' : 'text-[#ff1744]')}>
            {stats.profitFactor === Infinity ? '\u221E' : stats.profitFactor.toFixed(2)}
          </div>
          <div className="text-[10px] text-zinc-500 mt-0.5">
            Avg dur: {stats.avgDuration > 0 ? formatDuration(stats.avgDuration) : '---'}
          </div>
        </div>
      </div>

      {/* Sort Controls (mobile) */}
      <div className="flex items-center gap-3 md:hidden overflow-x-auto">
        <span className="text-[10px] text-zinc-500 uppercase shrink-0">Sort:</span>
        {sortBtn('pnl', 'P&L $')}
        {sortBtn('pnl_pct', 'P&L %')}
        {sortBtn('duration', 'Duration')}
        {sortBtn('date', 'Date')}
      </div>

      {/* Mobile Card View */}
      <div className="md:hidden">
        {visible.length === 0 ? (
          <div className="rounded-xl border border-zinc-800 bg-[#0d1117] px-4 py-16 text-center text-sm text-zinc-500">
            No closed trades yet
          </div>
        ) : (
          <div className="space-y-2">
            {visible.map((trade, idx) => {
              const rank = startIdx + idx + 1;
              const dur = getDurationMs(trade);
              const isWin = trade.pnl > 0;

              return (
                <div
                  key={trade.id}
                  className={cn(
                    'border rounded-lg p-3',
                    isWin
                      ? 'bg-[#00c853]/5 border-[#00c853]/20'
                      : 'bg-[#ff1744]/5 border-[#ff1744]/20',
                  )}
                >
                  {/* Top row: Rank + Pair + P&L */}
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono text-zinc-500 w-6">#{rank}</span>
                      <span className="text-sm font-semibold text-white">
                        {extractBaseAsset(trade.pair)}
                      </span>
                      <span className={cn('text-[10px] font-medium', getPositionTypeColor(trade.position_type))}>
                        {getPositionTypeLabel(trade.position_type)}
                      </span>
                      <span
                        className="inline-block h-2 w-2 rounded-full"
                        style={{ backgroundColor: getExchangeColor(trade.exchange) }}
                      />
                    </div>
                    <div className="text-right">
                      <span className={cn('text-sm font-mono font-bold', getPnLColor(trade.pnl))}>
                        {formatPnL(trade.pnl)}
                      </span>
                    </div>
                  </div>
                  {/* Details row */}
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-zinc-400">
                    <span className="font-mono">
                      ${formatCurrency(trade.price).replace('$', '')} &rarr; {trade.exit_price != null ? `$${formatCurrency(trade.exit_price).replace('$', '')}` : '---'}
                    </span>
                    {trade.pnl_pct != null && (
                      <span className={cn('font-mono', getPnLColor(trade.pnl_pct))}>
                        {formatPercentage(trade.pnl_pct)}
                      </span>
                    )}
                    {dur != null && (
                      <span className="font-mono">{formatDuration(dur)}</span>
                    )}
                    <span>{formatShortDate(trade.timestamp)}</span>
                    <Badge variant={getStrategyBadgeVariant(trade.strategy)}>
                      {getStrategyLabel(trade.strategy)}
                    </Badge>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Desktop Table */}
      <div className="hidden md:block bg-[#0d1117] overflow-hidden rounded-xl border border-zinc-800">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-zinc-900/50">
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-zinc-400 w-12">
                  #
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-zinc-400">
                  Pair
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-zinc-400">
                  Side
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-zinc-400">
                  Entry &rarr; Exit
                </th>
                <th className="px-4 py-3 text-right">
                  {sortBtn('pnl', 'P&L $')}
                </th>
                <th className="px-4 py-3 text-right">
                  {sortBtn('pnl_pct', 'P&L %')}
                </th>
                <th className="px-4 py-3 text-right">
                  {sortBtn('duration', 'Duration')}
                </th>
                <th className="px-4 py-3 text-right">
                  {sortBtn('date', 'Date')}
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-zinc-400">
                  Strategy
                </th>
              </tr>
            </thead>
            <tbody>
              {visible.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-16 text-center text-sm text-zinc-500">
                    No closed trades yet
                  </td>
                </tr>
              ) : (
                visible.map((trade, idx) => {
                  const rank = startIdx + idx + 1;
                  const dur = getDurationMs(trade);
                  const isWin = trade.pnl > 0;

                  return (
                    <tr
                      key={trade.id}
                      className={cn(
                        'border-b border-zinc-800/50 transition-colors',
                        isWin
                          ? 'hover:bg-[#00c853]/5'
                          : 'hover:bg-[#ff1744]/5',
                      )}
                    >
                      {/* Rank */}
                      <td className="px-4 py-3 font-mono text-zinc-500 text-xs">
                        {rank}
                      </td>

                      {/* Pair */}
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1.5">
                          <span
                            className="inline-block h-2 w-2 rounded-full shrink-0"
                            style={{ backgroundColor: getExchangeColor(trade.exchange) }}
                          />
                          <span className="font-medium text-white">
                            {extractBaseAsset(trade.pair)}
                          </span>
                          {trade.leverage > 1 && (
                            <span className="text-[10px] text-amber-400 font-mono">
                              {formatLeverage(trade.leverage)}
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Side */}
                      <td className="px-4 py-3">
                        <span className={cn('text-xs font-medium', getPositionTypeColor(trade.position_type))}>
                          {getPositionTypeLabel(trade.position_type)}
                        </span>
                      </td>

                      {/* Entry → Exit */}
                      <td className="px-4 py-3 text-right font-mono text-xs text-zinc-300">
                        {formatCurrency(trade.price)} &rarr;{' '}
                        {trade.exit_price != null ? formatCurrency(trade.exit_price) : '---'}
                      </td>

                      {/* P&L $ */}
                      <td className={cn('px-4 py-3 text-right font-mono font-bold', getPnLColor(trade.pnl))}>
                        {formatPnL(trade.pnl)}
                      </td>

                      {/* P&L % */}
                      <td className={cn('px-4 py-3 text-right font-mono text-xs', getPnLColor(trade.pnl_pct ?? 0))}>
                        {trade.pnl_pct != null ? formatPercentage(trade.pnl_pct) : '---'}
                      </td>

                      {/* Duration */}
                      <td className="px-4 py-3 text-right font-mono text-xs text-zinc-400">
                        {dur != null ? formatDuration(dur) : '---'}
                      </td>

                      {/* Date */}
                      <td className="px-4 py-3 text-right text-xs text-zinc-400">
                        {formatShortDate(trade.timestamp)}
                      </td>

                      {/* Strategy */}
                      <td className="px-4 py-3">
                        <Badge variant={getStrategyBadgeVariant(trade.strategy)}>
                          {getStrategyLabel(trade.strategy)}
                        </Badge>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {sorted.length > TRADES_PER_PAGE && (
          <div className="flex items-center justify-between border-t border-zinc-800 px-4 py-3">
            <span className="text-xs text-zinc-400">
              Showing {startIdx + 1}&ndash;{endIdx} of {sorted.length} trades
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={safePage <= 1}
                className="rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs font-medium text-zinc-300 transition-colors hover:bg-zinc-700 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
              >
                Previous
              </button>
              <span className="min-w-[4rem] text-center text-xs text-zinc-400">
                {safePage} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={safePage >= totalPages}
                className="rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs font-medium text-zinc-300 transition-colors hover:bg-zinc-700 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Mobile pagination */}
      {sorted.length > TRADES_PER_PAGE && (
        <div className="md:hidden flex items-center justify-between">
          <span className="text-xs text-zinc-400">
            {startIdx + 1}&ndash;{endIdx} of {sorted.length}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={safePage <= 1}
              className="rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-xs font-medium text-zinc-300 disabled:opacity-40"
            >
              Prev
            </button>
            <span className="text-xs text-zinc-400">{safePage}/{totalPages}</span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={safePage >= totalPages}
              className="rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-xs font-medium text-zinc-300 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

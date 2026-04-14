'use client';

import { useMemo, useState, useEffect } from 'react';
import Link from 'next/link';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import { cn, formatPnL, formatCurrency } from '@/lib/utils';
import { PnLCalendar, buildDailyStats } from '@/components/dashboard/PnLCalendar';

// ── Types ───────────────────────────────────────────────────────────────

type TimeRange = '24h' | '7d' | '14d' | '30d';

// ── Components ──────────────────────────────────────────────────────────

function PnLChart({ trades, range }: { trades: any[]; range: TimeRange }) {
  const chartData = useMemo(() => {
    const now = Date.now();
    const istOffsetMs = 5.5 * 60 * 60 * 1000;
    
    let cutoffMs: number;
    let bucketSize: number;

    if (range === '24h') {
      const istNow = new Date(now + istOffsetMs);
      const todayIST = istNow.toISOString().slice(0, 10);
      cutoffMs = new Date(todayIST + 'T00:00:00+05:30').getTime();
      bucketSize = 60 * 60 * 1000; // 1 hour buckets
    } else {
      const days = range === '7d' ? 7 : range === '14d' ? 14 : 30;
      cutoffMs = now - days * 24 * 60 * 60 * 1000;
      bucketSize = 24 * 60 * 60 * 1000; // 1 day buckets
    }

    // Group trades into buckets
    const buckets = new Map<number, number>();

    for (const t of trades) {
      if (t.status !== 'closed') continue;
      const tradeTime = new Date(t.timestamp).getTime();
      if (tradeTime < cutoffMs) continue;

      // Align day buckets to IST midnight instead of UTC midnight
      const bucketTime =
        bucketSize === 24 * 60 * 60 * 1000
          ? Math.floor((tradeTime + istOffsetMs) / bucketSize) * bucketSize - istOffsetMs
          : Math.floor(tradeTime / bucketSize) * bucketSize;
      const existing = buckets.get(bucketTime) || 0;
      buckets.set(bucketTime, existing + (t.pnl || 0));
    }

    // Sort buckets and calculate cumulative
    const sorted = Array.from(buckets.entries()).sort((a, b) => a[0] - b[0]);
    if (sorted.length === 0) return [];

    let cumulative = 0;
    return sorted.map(([time, pnl]) => {
      cumulative += pnl;
      return { time, pnl, cumulative };
    });
  }, [trades, range]);

  if (chartData.length === 0) {
    return (
      <div className="h-48 bg-[#141419] rounded-xl flex items-center justify-center">
        <span className="text-sm text-gray-600">No trades in selected period</span>
      </div>
    );
  }

  const min = Math.min(...chartData.map(d => d.cumulative), 0);
  const max = Math.max(...chartData.map(d => d.cumulative), 0);
  const valueRange = max - min || 1;

  const width = 100;
  const height = 48;
  const padding = 4;

  const points = chartData.map((d, i) => {
    const x = padding + (i / (chartData.length - 1 || 1)) * (width - padding * 2);
    const y = padding + (1 - (d.cumulative - min) / valueRange) * (height - padding * 2);
    return `${x},${y}`;
  });

  const areaPoints = `${padding},${height} ${points.join(' ')} ${width - padding},${height}`;
  const isProfit = chartData[chartData.length - 1]?.cumulative >= 0;
  const color = isProfit ? '#22c55e' : '#ef4444';

  return (
    <div className="h-48 bg-[#141419] border border-white/5 rounded-xl p-4">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full" preserveAspectRatio="none">
        <defs>
          <linearGradient id="pnlGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.3} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <polygon points={areaPoints} fill="url(#pnlGradient)" />
        <polyline
          points={points.join(' ')}
          fill="none"
          stroke={color}
          strokeWidth="0.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
}

function StatCard({ label, value, subtext, color }: { label: string; value: string; subtext?: string; color?: string }) {
  return (
    <div className="bg-[#141419] border border-white/5 rounded-xl p-4">
      <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">{label}</div>
      <div className={cn('text-xl font-mono font-bold', color || 'text-white')}>{value}</div>
      {subtext && <div className="text-xs text-gray-600 mt-1">{subtext}</div>}
    </div>
  );
}

// ── Main Page ───────────────────────────────────────────────────────────

export default function PnLPage() {
  const { trades, filteredTrades } = useSupabase();
  const [range, setRange] = useState<TimeRange>('7d');
  const istOffsetMs = 5.5 * 60 * 60 * 1000;
  const istDateStr = new Date(Date.now() + istOffsetMs).toISOString().slice(0, 10);
  const [year, setYear] = useState(Number(istDateStr.slice(0, 4)));
  const [month, setMonth] = useState(Number(istDateStr.slice(5, 7)) - 1);

  // Calculate stats for selected range
  const stats = useMemo(() => {
    const now = Date.now();
    const istOffsetMs = 5.5 * 60 * 60 * 1000;
    
    let cutoffMs: number;
    if (range === '24h') {
      const istNow = new Date(now + istOffsetMs);
      const todayIST = istNow.toISOString().slice(0, 10);
      cutoffMs = new Date(todayIST + 'T00:00:00+05:30').getTime();
    } else {
      const days = range === '7d' ? 7 : range === '14d' ? 14 : 30;
      cutoffMs = now - days * 24 * 60 * 60 * 1000;
    }

    let netPnl = 0;
    let grossPnl = 0;
    let totalFees = 0;
    let wins = 0;
    let losses = 0;
    let bestTrade = -Infinity;
    let worstTrade = Infinity;
    let winAmounts = 0;
    let lossAmounts = 0;

    for (const t of trades) {
      if (t.status !== 'closed') continue;
      const tradeTime = new Date(t.timestamp).getTime();
      if (tradeTime < cutoffMs) continue;

      const pnl = t.pnl || 0;
      const fees = (t.entry_fee || 0) + (t.exit_fee || 0);
      const gross = t.gross_pnl != null ? t.gross_pnl : pnl + fees;

      netPnl += pnl;
      grossPnl += gross;
      totalFees += fees;

      if (pnl > 0) {
        wins++;
        winAmounts += gross;
      } else if (pnl < 0) {
        losses++;
        lossAmounts += Math.abs(gross);
      }

      bestTrade = Math.max(bestTrade, gross);
      worstTrade = Math.min(worstTrade, gross);
    }

    const total = wins + losses;
    const winRate = total > 0 ? (wins / total) * 100 : 0;
    const profitFactor = lossAmounts > 0 ? winAmounts / lossAmounts : winAmounts > 0 ? Infinity : 0;
    const expectancy = total > 0 ? grossPnl / total : 0;
    const avgWinner = wins > 0 ? winAmounts / wins : 0;
    const avgLoser = losses > 0 ? lossAmounts / losses : 0;

    return {
      netPnl,
      grossPnl,
      totalFees,
      wins,
      losses,
      winRate,
      bestTrade: bestTrade > -Infinity ? bestTrade : 0,
      worstTrade: worstTrade < Infinity ? worstTrade : 0,
      profitFactor,
      expectancy,
      avgWinner,
      avgLoser,
      total,
    };
  }, [trades, range]);

  // Calendar data
  const dailyStats = useMemo(() => buildDailyStats(filteredTrades), [filteredTrades]);
  const monthLabel = new Date(year, month).toLocaleString('en-US', { month: 'long', year: 'numeric' });

  const { winDays, lossDays } = useMemo(() => {
    let w = 0, l = 0;
    for (const s of Array.from(dailyStats.values())) {
      if (s.pnl > 0) w++;
      else if (s.pnl < 0) l++;
    }
    return { winDays: w, lossDays: l };
  }, [dailyStats]);

  const prevMonth = () => {
    if (month === 0) { setYear(y => y - 1); setMonth(11); }
    else setMonth(m => m - 1);
  };
  const nextMonth = () => {
    if (month === 11) { setYear(y => y + 1); setMonth(0); }
    else setMonth(m => m + 1);
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white p-4 md:p-6 pb-24 md:pb-6">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <Link 
          href="/" 
          className="flex items-center justify-center w-10 h-10 rounded-xl bg-[#141419] border border-white/5 text-gray-400 hover:text-white transition-colors"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
        </Link>
        <div>
          <h1 className="text-xl font-bold">P&L Analysis</h1>
          <p className="text-xs text-gray-500">Performance metrics and trade history</p>
        </div>
      </div>

      {/* Timeframe Toggle */}
      <div className="flex gap-2 mb-6">
        {(['24h', '7d', '14d', '30d'] as TimeRange[]).map((r) => (
          <button
            key={r}
            onClick={() => setRange(r)}
            className={cn(
              'px-4 py-2 rounded-xl text-sm font-medium transition-colors',
              range === r 
                ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' 
                : 'bg-[#141419] text-gray-400 border border-white/5 hover:text-white'
            )}
          >
            {r.toUpperCase()}
          </button>
        ))}
      </div>

      {/* Two-column layout for desktop: Chart/Stats left, Calendar right */}
      <div className="lg:grid lg:grid-cols-2 lg:gap-6">
        {/* Left Column: P&L Chart + Performance Metrics */}
        <div className="space-y-6">
          {/* P&L Chart */}
          <div>
            <PnLChart trades={trades} range={range} />
          </div>

          {/* Summary Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard 
              label="Net P&L" 
              value={formatPnL(stats.netPnl)}
              subtext={`${stats.total} trades`}
              color={stats.netPnl >= 0 ? 'text-green-400' : 'text-red-400'}
            />
            <StatCard 
              label="Gross P&L" 
              value={formatPnL(stats.grossPnl)}
              subtext={`${((stats.grossPnl / (Math.abs(stats.grossPnl) + 0.001)) * 100).toFixed(0)}% win ratio`}
              color={stats.grossPnl >= 0 ? 'text-green-400' : 'text-red-400'}
            />
            <StatCard 
              label="Total Fees" 
              value={`$${stats.totalFees.toFixed(2)}`}
              subtext={stats.total > 0 ? `$${(stats.totalFees / stats.total).toFixed(4)}/trade` : undefined}
              color="text-gray-400"
            />
            <StatCard 
              label="Win Rate" 
              value={`${stats.winRate.toFixed(1)}%`}
              subtext={`${stats.wins}W / ${stats.losses}L`}
              color="text-blue-400"
            />
          </div>

          {/* Performance Metrics */}
          <div className="bg-[#141419] border border-white/5 rounded-xl p-4">
            <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-4">Performance Metrics</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-xs text-gray-500 mb-1">Best Trade</div>
                <div className="text-sm font-mono text-green-400">+{formatPnL(stats.bestTrade)}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-1">Worst Trade</div>
                <div className="text-sm font-mono text-red-400">{formatPnL(stats.worstTrade)}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-1">Avg Winner</div>
                <div className="text-sm font-mono text-green-400">+{formatPnL(stats.avgWinner)}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-1">Avg Loser</div>
                <div className="text-sm font-mono text-red-400">-{formatPnL(stats.avgLoser)}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-1">Profit Factor</div>
                <div className={cn(
                  'text-sm font-mono',
                  stats.profitFactor >= 1 ? 'text-green-400' : 'text-red-400'
                )}>
                  {stats.profitFactor.toFixed(2)}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-1">Expectancy</div>
                <div className={cn(
                  'text-sm font-mono',
                  stats.expectancy >= 0 ? 'text-green-400' : 'text-red-400'
                )}>
                  {formatPnL(stats.expectancy)}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-1">Win Amount</div>
                <div className="text-sm font-mono text-green-400">+{formatPnL(stats.avgWinner * stats.wins)}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-1">Loss Amount</div>
                <div className="text-sm font-mono text-red-400">-{formatPnL(stats.avgLoser * stats.losses)}</div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Daily P&L Calendar */}
        <div className="mt-6 lg:mt-0">
          <div className="bg-[#141419] border border-white/5 rounded-xl p-4 h-full">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider">Daily P&L Calendar</h3>
                <div className="text-xs text-gray-600 mt-1">
                  <span className="text-red-400">{lossDays} loss days</span>
                  <span className="mx-2">/</span>
                  <span className="text-green-400">{winDays} profit days</span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={prevMonth} className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/5 transition-colors">
                  <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                </button>
                <span className="text-sm font-medium text-white min-w-[100px] text-center">{monthLabel}</span>
                <button onClick={nextMonth} className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/5 transition-colors">
                  <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
                  </svg>
                </button>
              </div>
            </div>

            <PnLCalendar dailyStats={dailyStats} year={year} month={month} />

            {/* Legend */}
            <div className="flex items-center justify-center gap-2 mt-4 text-[10px] text-gray-500">
              <span>Loss</span>
              <div className="flex gap-0.5">
                <div className="w-3 h-3 rounded bg-red-500" />
                <div className="w-3 h-3 rounded bg-red-500/70" />
                <div className="w-3 h-3 rounded bg-red-500/40" />
                <div className="w-3 h-3 rounded bg-gray-800" />
                <div className="w-3 h-3 rounded bg-green-500/40" />
                <div className="w-3 h-3 rounded bg-green-500/70" />
                <div className="w-3 h-3 rounded bg-green-500" />
              </div>
              <span>Profit</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

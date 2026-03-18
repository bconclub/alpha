'use client';

import { useMemo, useState } from 'react';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import { cn, formatPnL } from '@/lib/utils';
import type { Trade } from '@/lib/types';

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

function getDaysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate();
}

function getFirstDayOfWeek(year: number, month: number) {
  return new Date(year, month, 1).getDay();
}

/** Group closed trades by date (IST) and sum P&L */
function buildDailyPnL(trades: Trade[]): Map<string, { pnl: number; trades: number; wins: number }> {
  const map = new Map<string, { pnl: number; trades: number; wins: number }>();
  for (const t of trades) {
    if (t.status !== 'closed') continue;
    const dateKey = t.closed_at
      ? new Date(t.closed_at).toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' })
      : new Date(t.timestamp).toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' });
    const entry = map.get(dateKey) ?? { pnl: 0, trades: 0, wins: 0 };
    entry.pnl += t.pnl;
    entry.trades += 1;
    if (t.pnl > 0) entry.wins += 1;
    map.set(dateKey, entry);
  }
  return map;
}

function getPnLColor(pnl: number): string {
  if (pnl === 0) return 'bg-zinc-800/50';
  if (pnl > 0) {
    // Bigger profit = darker/richer green, small profit = light/faded green
    if (pnl >= 1.0) return 'bg-emerald-500';
    if (pnl >= 0.5) return 'bg-emerald-500/80';
    if (pnl >= 0.2) return 'bg-emerald-600/70';
    if (pnl >= 0.05) return 'bg-emerald-700/60';
    return 'bg-emerald-800/40';
  }
  // Bigger loss = darker/deeper red, small loss = light/faded red
  if (pnl <= -1.0) return 'bg-red-500';
  if (pnl <= -0.5) return 'bg-red-500/80';
  if (pnl <= -0.2) return 'bg-red-600/70';
  if (pnl <= -0.05) return 'bg-red-700/60';
  return 'bg-red-800/40';
}

function getPnLTextColor(pnl: number): string {
  if (pnl > 0) return 'text-emerald-400';
  if (pnl < 0) return 'text-red-400';
  return 'text-zinc-500';
}

export default function PnLPage() {
  const { filteredTrades } = useSupabase();

  // Default to current month (IST)
  const now = new Date(new Date().toLocaleString('en-US', { timeZone: 'Asia/Kolkata' }));
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth());

  const dailyPnL = useMemo(() => buildDailyPnL(filteredTrades), [filteredTrades]);

  const daysInMonth = getDaysInMonth(year, month);
  const firstDay = getFirstDayOfWeek(year, month);
  const monthLabel = new Date(year, month).toLocaleString('en-US', { month: 'long', year: 'numeric' });

  // Build calendar grid
  const cells: (null | { day: number; dateKey: string })[] = [];
  for (let i = 0; i < firstDay; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) {
    const dateKey = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
    cells.push({ day: d, dateKey });
  }

  // Monthly totals
  const monthStats = useMemo(() => {
    let totalPnl = 0;
    let totalTrades = 0;
    let totalWins = 0;
    let greenDays = 0;
    let redDays = 0;

    for (let d = 1; d <= daysInMonth; d++) {
      const dateKey = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
      const entry = dailyPnL.get(dateKey);
      if (entry) {
        totalPnl += entry.pnl;
        totalTrades += entry.trades;
        totalWins += entry.wins;
        if (entry.pnl > 0) greenDays++;
        else if (entry.pnl < 0) redDays++;
      }
    }
    return { totalPnl, totalTrades, totalWins, greenDays, redDays };
  }, [dailyPnL, year, month, daysInMonth]);

  const prevMonth = () => {
    if (month === 0) { setYear(y => y - 1); setMonth(11); }
    else setMonth(m => m - 1);
  };
  const nextMonth = () => {
    if (month === 11) { setYear(y => y + 1); setMonth(0); }
    else setMonth(m => m + 1);
  };

  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const selectedEntry = selectedDay ? dailyPnL.get(selectedDay) : null;

  return (
    <div className="space-y-4">
      <h1 className="text-xl md:text-2xl font-bold tracking-tight text-white">P&L Calendar</h1>

      {/* Month navigation */}
      <div className="flex items-center justify-between">
        <button onClick={prevMonth} className="p-2 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors">
          <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clipRule="evenodd" /></svg>
        </button>
        <span className="text-sm font-semibold text-white tracking-wide">{monthLabel}</span>
        <button onClick={nextMonth} className="p-2 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors">
          <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" /></svg>
        </button>
      </div>

      {/* Monthly summary */}
      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-2">
          <div className="text-[10px] uppercase tracking-wider text-zinc-500">Net P&L</div>
          <div className={cn('text-sm font-mono font-semibold', getPnLTextColor(monthStats.totalPnl))}>
            {formatPnL(monthStats.totalPnl)}
          </div>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-2">
          <div className="text-[10px] uppercase tracking-wider text-zinc-500">Trades</div>
          <div className="text-sm font-mono font-semibold text-white">
            {monthStats.totalTrades}
          </div>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-2">
          <div className="text-[10px] uppercase tracking-wider text-zinc-500">Days</div>
          <div className="text-sm font-mono font-semibold">
            <span className="text-emerald-400">{monthStats.greenDays}</span>
            <span className="text-zinc-600 mx-1">/</span>
            <span className="text-red-400">{monthStats.redDays}</span>
          </div>
        </div>
      </div>

      {/* Calendar grid */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-3">
        {/* Day headers */}
        <div className="grid grid-cols-7 gap-1 mb-1">
          {DAYS.map(d => (
            <div key={d} className="text-center text-[10px] font-medium text-zinc-500 py-1">{d}</div>
          ))}
        </div>

        {/* Day cells */}
        <div className="grid grid-cols-7 gap-1">
          {cells.map((cell, i) => {
            if (!cell) return <div key={`empty-${i}`} />;
            const entry = dailyPnL.get(cell.dateKey);
            const pnl = entry?.pnl ?? 0;
            const hasTrades = !!entry;
            const isSelected = selectedDay === cell.dateKey;
            const isToday = cell.dateKey === now.toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' });

            return (
              <button
                key={cell.dateKey}
                onClick={() => setSelectedDay(isSelected ? null : cell.dateKey)}
                className={cn(
                  'relative aspect-square rounded-md flex flex-col items-center justify-center transition-all',
                  hasTrades ? getPnLColor(pnl) : 'bg-zinc-800/30',
                  isSelected && 'ring-2 ring-blue-400',
                  isToday && !isSelected && 'ring-1 ring-zinc-500',
                )}
              >
                <span className={cn(
                  'text-[11px] font-medium',
                  hasTrades ? 'text-white' : 'text-zinc-600',
                )}>
                  {cell.day}
                </span>
                {hasTrades && (
                  <span className="text-[8px] font-mono text-white/80">
                    {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Selected day detail */}
      {selectedDay && selectedEntry && (
        <div className="rounded-lg border border-zinc-700 bg-zinc-900/60 p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-zinc-400">
              {new Date(selectedDay + 'T00:00:00').toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' })}
            </span>
            <button onClick={() => setSelectedDay(null)} className="text-zinc-500 hover:text-zinc-300">
              <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12" /></svg>
            </button>
          </div>
          <div className="grid grid-cols-3 gap-3 text-center">
            <div>
              <div className="text-[10px] text-zinc-500">Net P&L</div>
              <div className={cn('text-sm font-mono font-semibold', getPnLTextColor(selectedEntry.pnl))}>
                {formatPnL(selectedEntry.pnl)}
              </div>
            </div>
            <div>
              <div className="text-[10px] text-zinc-500">Trades</div>
              <div className="text-sm font-mono font-semibold text-white">{selectedEntry.trades}</div>
            </div>
            <div>
              <div className="text-[10px] text-zinc-500">Win Rate</div>
              <div className="text-sm font-mono font-semibold text-white">
                {selectedEntry.trades > 0 ? Math.round((selectedEntry.wins / selectedEntry.trades) * 100) : 0}%
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="flex items-center justify-center gap-1 text-[10px] text-zinc-500">
        <span>Loss</span>
        <div className="flex gap-0.5">
          <div className="w-3 h-3 rounded-sm bg-red-500" />
          <div className="w-3 h-3 rounded-sm bg-red-500/80" />
          <div className="w-3 h-3 rounded-sm bg-red-600/70" />
          <div className="w-3 h-3 rounded-sm bg-red-700/60" />
          <div className="w-3 h-3 rounded-sm bg-zinc-800/50" />
          <div className="w-3 h-3 rounded-sm bg-emerald-700/60" />
          <div className="w-3 h-3 rounded-sm bg-emerald-600/70" />
          <div className="w-3 h-3 rounded-sm bg-emerald-500/80" />
          <div className="w-3 h-3 rounded-sm bg-emerald-500" />
        </div>
        <span>Profit</span>
      </div>
    </div>
  );
}

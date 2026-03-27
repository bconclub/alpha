'use client';

import { useMemo } from 'react';
import { cn } from '@/lib/utils';
import type { Trade } from '@/lib/types';

// ── Types ──

export interface DayStats {
  pnl: number;
  fees: number;
  trades: number;
}

// ── Data builder: group closed trades by IST day ──

export function buildDailyStats(trades: Trade[]): Map<string, DayStats> {
  const map = new Map<string, DayStats>();
  for (const t of trades) {
    if (t.status !== 'closed') continue;
    const dateKey = t.closed_at
      ? new Date(t.closed_at).toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' })
      : new Date(t.timestamp).toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' });
    const entry = map.get(dateKey) ?? { pnl: 0, fees: 0, trades: 0 };
    entry.pnl += t.pnl;
    entry.fees += (t.entry_fee ?? 0) + (t.exit_fee ?? 0);
    entry.trades += 1;
    map.set(dateKey, entry);
  }
  return map;
}

// ── Calendar helpers ──

function getDaysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate();
}

function getFirstDayOfWeek(year: number, month: number) {
  return new Date(year, month, 1).getDay(); // 0=Sun
}

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

// ── Color: green/red intensity based on P&L magnitude ──

function getCellColor(pnl: number, maxAbs: number): string {
  if (maxAbs === 0) return 'bg-zinc-800/40';
  const ratio = Math.min(Math.abs(pnl) / maxAbs, 1);
  if (pnl > 0) {
    if (ratio > 0.7) return 'bg-emerald-500';
    if (ratio > 0.4) return 'bg-emerald-500/70';
    if (ratio > 0.15) return 'bg-emerald-600/50';
    return 'bg-emerald-700/30';
  }
  if (ratio > 0.7) return 'bg-red-500';
  if (ratio > 0.4) return 'bg-red-500/70';
  if (ratio > 0.15) return 'bg-red-600/50';
  return 'bg-red-700/30';
}

// ── Component ──

interface PnLCalendarProps {
  dailyStats: Map<string, DayStats>;
  year: number;
  month: number;
}

export function PnLCalendar({ dailyStats, year, month }: PnLCalendarProps) {
  const daysInMonth = getDaysInMonth(year, month);
  const firstDay = getFirstDayOfWeek(year, month);

  const todayKey = new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' });

  // Max absolute P&L this month for color scaling
  const maxAbs = useMemo(() => {
    let max = 0;
    for (let d = 1; d <= daysInMonth; d++) {
      const key = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
      const s = dailyStats.get(key);
      if (s) max = Math.max(max, Math.abs(s.pnl));
    }
    return max;
  }, [dailyStats, year, month, daysInMonth]);

  // Build cells: null for padding, or { day, dateKey }
  const cells: (null | { day: number; dateKey: string })[] = [];
  for (let i = 0; i < firstDay; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) {
    cells.push({
      day: d,
      dateKey: `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`,
    });
  }

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-2">
      {/* Day headers */}
      <div className="grid grid-cols-7 gap-1 mb-1">
        {DAYS.map(d => (
          <div key={d} className="text-center text-[9px] font-medium text-zinc-500">{d}</div>
        ))}
      </div>

      {/* Day cells */}
      <div className="grid grid-cols-7 gap-1">
        {cells.map((cell, i) => {
          if (!cell) return <div key={`e-${i}`} className="aspect-[1/1.15]" />;

          const stats = dailyStats.get(cell.dateKey);
          const hasTrades = !!stats;
          const pnl = stats?.pnl ?? 0;
          const isToday = cell.dateKey === todayKey;

          return (
            <div
              key={cell.dateKey}
              className={cn(
                'relative aspect-[1/1.15] rounded-md flex flex-col items-center justify-center px-0.5 min-w-0 overflow-hidden',
                hasTrades ? getCellColor(pnl, maxAbs) : 'bg-zinc-800/20',
                isToday && 'ring-1 ring-zinc-400',
              )}
            >
              {/* Day number */}
              <span className={cn(
                'text-[10px] font-medium leading-none',
                hasTrades ? 'text-white/90' : 'text-zinc-600',
              )}>
                {cell.day}
              </span>

              {hasTrades && stats && (
                <>
                  {/* Net P&L */}
                  <span className={cn(
                    'text-[9px] font-mono font-bold leading-tight mt-0.5',
                    pnl >= 0 ? 'text-white' : 'text-white',
                  )}>
                    {pnl >= 0 ? '+' : ''}{pnl < 10 && pnl > -10 ? pnl.toFixed(2) : pnl.toFixed(1)}
                  </span>
                  {/* Fees */}
                  <span className="text-[7px] font-mono leading-tight text-white/50 truncate w-full text-center">
                    fees: ${stats.fees < 10 ? stats.fees.toFixed(2) : stats.fees.toFixed(1)}
                  </span>
                  {/* Trade count */}
                  <span className="text-[7px] font-mono leading-tight text-white/50">
                    {stats.trades} trade{stats.trades !== 1 ? 's' : ''}
                  </span>
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

'use client';

import { useMemo } from 'react';
import Link from 'next/link';
import { ArrowRight } from 'lucide-react';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import { ExitChip } from '@/components/ui/ExitChip';
import { cn, formatCurrency, formatTimeAgo } from '@/lib/utils';

const LIMIT = 6;

export function RecentTrades() {
  const { trades } = useSupabase();

  const rows = useMemo(
    () =>
      trades
        .filter((t) => t.status === 'closed')
        .sort(
          (a, b) =>
            new Date(b.closed_at || b.timestamp).getTime() -
            new Date(a.closed_at || a.timestamp).getTime(),
        )
        .slice(0, LIMIT),
    [trades],
  );

  return (
    <section className="rounded-xl border border-white/[0.08] bg-[#101114] p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-base font-semibold text-white">Recent trades</h2>
        <Link href="/trades" className="flex items-center gap-1 text-xs font-medium text-zinc-400 hover:text-white">
          All trades <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </div>

      {rows.length === 0 ? (
        <p className="py-6 text-center text-sm text-zinc-600">No closed trades yet.</p>
      ) : (
        <ul className="divide-y divide-white/[0.05]">
          {rows.map((t) => {
            const long = t.position_type === 'long';
            const win = t.pnl > 0;
            return (
              <li key={t.id} className="flex items-center gap-3 py-2.5">
                <span className={cn(
                  'w-4 shrink-0 text-center text-xs',
                  long ? 'text-emerald-400' : 'text-red-400',
                )}>
                  {long ? '▲' : '▼'}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="flex items-center gap-2 text-sm font-semibold text-white">
                    {t.pair.split('/')[0]}
                    <span className="text-[11px] font-medium uppercase text-zinc-500">{long ? 'long' : 'short'}</span>
                    {t.exit_reason && <ExitChip exit={t.exit_reason} />}
                  </p>
                  <p className="truncate text-xs text-zinc-500">{formatTimeAgo(t.closed_at || t.timestamp)}</p>
                </div>
                <div className="text-right">
                  <p className={cn('font-mono text-sm font-semibold tabular-nums', win ? 'text-emerald-400' : t.pnl < 0 ? 'text-red-400' : 'text-zinc-300')}>
                    {t.pnl >= 0 ? '+' : ''}{formatCurrency(t.pnl)}
                  </p>
                  {t.pnl_pct != null && (
                    <p className="font-mono text-[11px] tabular-nums text-zinc-500">
                      {t.pnl_pct >= 0 ? '+' : ''}{t.pnl_pct.toFixed(1)}%
                    </p>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

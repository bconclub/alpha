'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { getSupabase } from '@/lib/supabase';
import type { PaperFuturesTrade } from '@/lib/types';

function money(value?: number | null): string {
  const n = Number(value ?? 0);
  const sign = n > 0 ? '+' : n < 0 ? '-' : '';
  return `${sign}$${Math.abs(n).toFixed(4)}`;
}

function pct(value?: number | null): string {
  const n = Number(value ?? 0);
  const sign = n > 0 ? '+' : '';
  return `${sign}${n.toFixed(2)}%`;
}

function shortPair(pair: string): string {
  return pair.replace('/USD:USD', '').replace('/USDT', '');
}

function holdTime(row: PaperFuturesTrade): string {
  const start = new Date(row.opened_at).getTime();
  const end = row.closed_at ? new Date(row.closed_at).getTime() : Date.now();
  if (!Number.isFinite(start) || !Number.isFinite(end)) return '-';
  const seconds = Math.max(0, Math.round((end - start) / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const rem = seconds % 60;
  return `${minutes}m ${rem}s`;
}

export default function PaperFuturesPage() {
  const [rows, setRows] = useState<PaperFuturesTrade[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchRows = useCallback(async () => {
    setLoading(true);
    setError(null);
    const supabase = getSupabase();
    if (!supabase) {
      setRows([]);
      setError('Supabase client is not configured.');
      setLoading(false);
      return;
    }
    const { data, error: queryError } = await supabase
      .from('paper_futures_trades')
      .select('*')
      .order('opened_at', { ascending: false })
      .limit(200);
    if (queryError) {
      setRows([]);
      setError(queryError.message);
    } else {
      setRows((data ?? []) as PaperFuturesTrade[]);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchRows();
  }, [fetchRows]);

  const stats = useMemo(() => {
    const closed = rows.filter((r) => r.status === 'closed');
    const wins = closed.filter((r) => Number(r.pnl_usd) > 0).length;
    const net = closed.reduce((sum, r) => sum + Number(r.pnl_usd ?? 0), 0);
    const peakAvg = closed.length
      ? closed.reduce((sum, r) => sum + Number(r.peak_pnl_pct ?? 0), 0) / closed.length
      : 0;
    return {
      total: rows.length,
      open: rows.filter((r) => r.status === 'open').length,
      closed: closed.length,
      winRate: closed.length ? (wins / closed.length) * 100 : 0,
      net,
      peakAvg,
    };
  }, [rows]);

  return (
    <div className="min-h-screen bg-[#0a0a0f] p-4 md:p-6">
      <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-xl font-bold text-zinc-100">Paper Futures</h1>
          <p className="mt-1 text-sm text-zinc-500">
            Multi-strategy paper lab: Donchian, EMA pullback, momentum impulse, signal mix, and option twins.
          </p>
        </div>
        <button
          onClick={fetchRows}
          className="inline-flex items-center gap-2 rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 hover:bg-zinc-800"
        >
          <RefreshCw size={15} />
          Refresh
        </button>
      </div>

      <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-6">
        {[
          ['Total', stats.total.toString()],
          ['Open', stats.open.toString()],
          ['Closed', stats.closed.toString()],
          ['Win Rate', `${stats.winRate.toFixed(0)}%`],
          ['Net', money(stats.net)],
          ['Avg Peak', pct(stats.peakAvg)],
        ].map(([label, value]) => (
          <div key={label} className="rounded-md border border-zinc-800 bg-zinc-950 p-3">
            <div className="text-[10px] uppercase tracking-wider text-zinc-500">{label}</div>
            <div className="mt-1 font-mono text-lg text-zinc-100">{value}</div>
          </div>
        ))}
      </div>

      <div className="overflow-hidden rounded-lg border border-zinc-800 bg-zinc-950">
        {error ? (
          <div className="p-5 text-sm text-red-300">{error}</div>
        ) : loading ? (
          <div className="p-5 text-sm text-zinc-400">Loading paper trades...</div>
        ) : rows.length === 0 ? (
          <div className="p-5 text-sm text-zinc-400">No paper futures rows yet.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1040px] text-left text-sm">
              <thead className="border-b border-zinc-800 bg-zinc-900/70 text-[10px] uppercase tracking-wider text-zinc-500">
                <tr>
                  <th className="px-4 py-3">Time</th>
                  <th className="px-4 py-3">Pair</th>
                  <th className="px-4 py-3">Dir</th>
                  <th className="px-4 py-3">Setup</th>
                  <th className="px-4 py-3 text-right">Entry</th>
                  <th className="px-4 py-3 text-right">Exit/Mark</th>
                  <th className="px-4 py-3 text-right">Margin</th>
                  <th className="px-4 py-3 text-right">Notional</th>
                  <th className="px-4 py-3 text-right">P&L</th>
                  <th className="px-4 py-3 text-right">Peak</th>
                  <th className="px-4 py-3">Hold</th>
                  <th className="px-4 py-3">Source</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const positive = Number(row.pnl_usd) > 0;
                  const mark = row.exit_price ?? row.current_price;
                  return (
                    <tr key={row.id} className="border-b border-zinc-900 text-zinc-200 last:border-0">
                      <td className="px-4 py-3 font-mono text-xs text-zinc-400">
                        {new Date(row.opened_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-3 font-semibold">{shortPair(row.pair)}</td>
                      <td className="px-4 py-3">
                        <span className={row.direction === 'long' ? 'text-emerald-300' : 'text-red-300'}>
                          {row.direction.toUpperCase()}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="rounded bg-sky-500/15 px-2 py-1 text-xs text-sky-200">
                          {row.setup_type || '-'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right font-mono">{Number(row.entry_price).toFixed(2)}</td>
                      <td className="px-4 py-3 text-right font-mono">{mark ? Number(mark).toFixed(2) : '-'}</td>
                      <td className="px-4 py-3 text-right font-mono">${Number(row.margin_usd).toFixed(2)}</td>
                      <td className="px-4 py-3 text-right font-mono">${Number(row.notional_usd).toFixed(2)}</td>
                      <td className={`px-4 py-3 text-right font-mono ${positive ? 'text-emerald-300' : Number(row.pnl_usd) < 0 ? 'text-red-300' : 'text-zinc-400'}`}>
                        {money(row.pnl_usd)} <span className="text-xs text-zinc-500">{pct(row.pnl_pct)}</span>
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-emerald-300">{pct(row.peak_pnl_pct)}</td>
                      <td className="px-4 py-3 font-mono text-xs text-zinc-400">{holdTime(row)}</td>
                      <td className="px-4 py-3 font-mono text-xs text-zinc-500">
                        {row.option_trade_id ? `Option #${row.option_trade_id}` : 'Independent'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

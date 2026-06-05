'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import type { PaperFuturesTrade } from '@/lib/types';

type WindowKey = 'today' | '7d' | '14d' | '28d' | 'all';

interface PaperBotStatus {
  bot_state?: string | null;
  is_running?: boolean | null;
  is_paused?: boolean | null;
  uptime_seconds?: number | null;
  timestamp?: string | null;
  created_at?: string | null;
  inr_usd_rate?: number | null;
}

const WINDOW_LABELS: Record<WindowKey, string> = {
  today: 'Today',
  '7d': '7 days',
  '14d': '14 days',
  '28d': '28 days',
  all: 'All',
};

const SETUP_LABELS: Record<string, string> = {
  DONCHIAN_BREAKOUT: 'Donchian',
  EMA_PULLBACK: 'EMA Pullback',
  MOMENTUM_IMPULSE: 'Momentum',
  SIGNAL_MIX: 'Signal Mix',
  OPTIONS_TWIN: 'Options Twin',
};

function money(value?: number | null, decimals = 4): string {
  const n = Number(value ?? 0);
  const sign = n > 0 ? '+' : n < 0 ? '-' : '';
  return `${sign}$${Math.abs(n).toFixed(decimals)}`;
}

function money2(value?: number | null): string {
  return money(value, 2);
}

function pct(value?: number | null): string {
  const n = Number(value ?? 0);
  const sign = n > 0 ? '+' : '';
  return `${sign}${n.toFixed(2)}%`;
}

function signedClass(value?: number | null): string {
  const n = Number(value ?? 0);
  if (n > 0) return 'text-emerald-300';
  if (n < 0) return 'text-red-300';
  return 'text-white';
}

function winRateClass(value: number, count: number): string {
  if (count === 0 || value === 0) return 'text-white';
  if (value < 20) return 'text-red-300';
  if (value < 40) return 'text-amber-300';
  if (value < 67) return 'text-emerald-300';
  return 'text-fuchsia-300';
}

function peakClass(value?: number | null): string {
  const n = Number(value ?? 0);
  if (n <= 0) return 'text-white';
  if (n < 2) return 'text-lime-200';
  if (n < 6) return 'text-emerald-300';
  return 'text-green-300';
}

function shortPair(pair: string): string {
  return pair.replace('/USD:USD', '').replace('/USDT', '');
}

function setupLabel(setup?: string | null): string {
  if (!setup) return '-';
  return SETUP_LABELS[setup] || setup.replace(/_/g, ' ');
}

function holdSeconds(row: PaperFuturesTrade, nowMs = Date.now()): number {
  const start = new Date(row.opened_at).getTime();
  const end = row.closed_at ? new Date(row.closed_at).getTime() : nowMs;
  if (!Number.isFinite(start) || !Number.isFinite(end)) return 0;
  return Math.max(0, Math.round((end - start) / 1000));
}

function holdTime(rowOrSeconds: PaperFuturesTrade | number, nowMs = Date.now()): string {
  const seconds = typeof rowOrSeconds === 'number' ? rowOrSeconds : holdSeconds(rowOrSeconds, nowMs);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const rem = seconds % 60;
  if (minutes < 60) return `${minutes}m ${rem}s`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
}

function windowStart(key: WindowKey): number {
  const now = new Date();
  if (key === 'all') return 0;
  if (key === 'today') {
    const start = new Date(now);
    start.setHours(0, 0, 0, 0);
    return start.getTime();
  }
  const days = key === '7d' ? 7 : key === '14d' ? 14 : 28;
  return now.getTime() - days * 24 * 60 * 60 * 1000;
}

function capturePct(row: PaperFuturesTrade): number | null {
  const peak = Number(row.peak_pnl_pct ?? 0);
  const pnl = Number(row.pnl_pct ?? 0);
  if (peak <= 0 || row.status !== 'closed') return null;
  return (pnl / peak) * 100;
}

function confidenceScore(row: PaperFuturesTrade): number | null {
  const raw = row.metadata?.confidence_score;
  if (raw === null || raw === undefined) return null;
  const score = Number(raw);
  return Number.isFinite(score) ? score : null;
}

interface GroupStats {
  key: string;
  label: string;
  trades: number;
  closed: number;
  wins: number;
  net: number;
  fees: number;
  avgPeak: number;
  avgHold: number;
  capture: number | null;
  confidence: number | null;
  winRate: number;
}

function buildGroupStats(rows: PaperFuturesTrade[], keyFor: (row: PaperFuturesTrade) => string, labelFor = keyFor): GroupStats[] {
  const buckets = new Map<string, PaperFuturesTrade[]>();
  for (const row of rows) {
    const key = keyFor(row);
    buckets.set(key, [...(buckets.get(key) || []), row]);
  }

  return Array.from(buckets.entries())
    .map(([key, bucket]) => {
      const closed = bucket.filter((row) => row.status === 'closed');
      const wins = closed.filter((row) => Number(row.pnl_usd ?? 0) > 0).length;
      const net = closed.reduce((sum, row) => sum + Number(row.pnl_usd ?? 0), 0);
      const fees = closed.reduce((sum, row) => sum + Number(row.fees_usd ?? 0), 0);
      const avgPeak = closed.length
        ? closed.reduce((sum, row) => sum + Number(row.peak_pnl_pct ?? 0), 0) / closed.length
        : 0;
      const avgHold = closed.length
        ? Math.round(closed.reduce((sum, row) => sum + holdSeconds(row), 0) / closed.length)
        : 0;
      const captures = closed.map(capturePct).filter((value): value is number => value !== null);
      const confidences = bucket.map(confidenceScore).filter((value): value is number => value !== null);
      return {
        key,
        label: labelFor(bucket[0]),
        trades: bucket.length,
        closed: closed.length,
        wins,
        net,
        fees,
        avgPeak,
        avgHold,
        capture: captures.length ? captures.reduce((sum, value) => sum + value, 0) / captures.length : null,
        confidence: confidences.length ? confidences.reduce((sum, value) => sum + value, 0) / confidences.length : null,
        winRate: closed.length ? (wins / closed.length) * 100 : 0,
      };
    })
    .sort((a, b) => b.net - a.net);
}

export default function PaperFuturesPage() {
  const [rows, setRows] = useState<PaperFuturesTrade[]>([]);
  const [botStatus, setBotStatus] = useState<PaperBotStatus | null>(null);
  const [paperAccountUsd, setPaperAccountUsd] = useState(50);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [windowKey, setWindowKey] = useState<WindowKey>('today');
  const [nowMs, setNowMs] = useState(() => Date.now());

  const fetchRows = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/paper-futures', { cache: 'no-store' });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        setRows([]);
        setError(payload.error || 'Failed to load paper futures rows.');
      } else {
        setRows((payload.rows ?? []) as PaperFuturesTrade[]);
        setBotStatus((payload.botStatus ?? null) as PaperBotStatus | null);
        setPaperAccountUsd(Number(payload.paperAccountUsd ?? 50));
      }
    } catch (err) {
      setRows([]);
      setError(err instanceof Error ? err.message : 'Failed to load paper futures rows.');
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchRows();
  }, [fetchRows]);

  useEffect(() => {
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const filteredRows = useMemo(() => {
    const start = windowStart(windowKey);
    return rows
      .filter((row) => new Date(row.opened_at).getTime() >= start)
      .sort((a, b) => {
        if (a.status === 'open' && b.status !== 'open') return -1;
        if (a.status !== 'open' && b.status === 'open') return 1;
        return new Date(b.opened_at).getTime() - new Date(a.opened_at).getTime();
      });
  }, [rows, windowKey]);

  const stats = useMemo(() => {
    const closed = filteredRows.filter((r) => r.status === 'closed');
    const wins = closed.filter((r) => Number(r.pnl_usd) > 0).length;
    const net = closed.reduce((sum, r) => sum + Number(r.pnl_usd ?? 0), 0);
    const gross = closed.reduce((sum, r) => sum + Number(r.gross_pnl_usd ?? 0), 0);
    const fees = closed.reduce((sum, r) => sum + Number(r.fees_usd ?? 0), 0);
    const peakAvg = closed.length
      ? closed.reduce((sum, r) => sum + Number(r.peak_pnl_pct ?? 0), 0) / closed.length
      : 0;
    const captures = closed.map(capturePct).filter((value): value is number => value !== null);
    const openRows = filteredRows.filter((r) => r.status === 'open');
    const leverages = Array.from(new Set(filteredRows.map((r) => `${Number(r.leverage).toFixed(0)}x`))).join(', ') || '-';
    const liveNet = openRows.reduce((sum, r) => sum + Number(r.pnl_usd ?? 0), 0);
    const closedAllNet = rows
      .filter((r) => r.status === 'closed')
      .reduce((sum, r) => sum + Number(r.pnl_usd ?? 0), 0);

    return {
      total: filteredRows.length,
      open: openRows.length,
      closed: closed.length,
      winRate: closed.length ? (wins / closed.length) * 100 : 0,
      net,
      gross,
      fees,
      peakAvg,
      avgCapture: captures.length ? captures.reduce((sum, value) => sum + value, 0) / captures.length : null,
      avgHold: closed.length ? Math.round(closed.reduce((sum, row) => sum + holdSeconds(row, nowMs), 0) / closed.length) : 0,
      leverages,
      liveNet,
      paperBalance: paperAccountUsd + closedAllNet,
    };
  }, [filteredRows, nowMs, paperAccountUsd, rows]);

  const setupStats = useMemo(
    () => buildGroupStats(filteredRows, (row) => row.setup_type || 'UNKNOWN', (row) => setupLabel(row.setup_type)),
    [filteredRows],
  );

  const leverageStats = useMemo(
    () => buildGroupStats(filteredRows, (row) => `${Number(row.leverage).toFixed(0)}x`),
    [filteredRows],
  );

  const pairStats = useMemo(
    () => buildGroupStats(filteredRows, (row) => `${shortPair(row.pair)} ${row.direction}`, (row) => `${shortPair(row.pair)} ${row.direction.toUpperCase()}`),
    [filteredRows],
  );

  const exitStats = useMemo(
    () => buildGroupStats(
      filteredRows.filter((row) => row.status === 'closed'),
      (row) => row.exit_reason || 'open',
      (row) => (row.exit_reason || 'unknown').replace(/_/g, ' '),
    ),
    [filteredRows],
  );

  return (
    <div className="min-h-screen bg-[#050507] p-4 text-zinc-100 md:p-6">
      <div className="mb-5 flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Paper Futures</h1>
          <p className="mt-1 max-w-3xl text-sm text-zinc-400">
            Paper-only futures lab. Delta BTC/ETH futures support leverage up to 100x by product; this lab currently records the modeled leverage on every row so we can compare risk before enabling real futures.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={fetchRows}
            className="inline-flex items-center gap-2 rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm font-semibold text-zinc-100 hover:bg-zinc-800"
          >
            <RefreshCw size={15} />
            Refresh
          </button>
        </div>
      </div>

      <div className="mb-5 rounded-xl border border-zinc-800 bg-[#101116] p-4 shadow-sm shadow-black">
        <div className="mb-2 flex items-center justify-between gap-4">
          <span className="text-xs uppercase tracking-wider text-zinc-500">Paper Account Balance</span>
          <div className="flex gap-1">
            {(['today', '7d', '14d', '28d'] as WindowKey[]).map((key) => (
              <button
                key={key}
                onClick={() => setWindowKey(key)}
                className={`rounded px-2 py-1 text-[10px] font-bold transition-colors ${
                  windowKey === key
                    ? 'bg-white/10 text-white'
                    : 'border border-white/10 text-zinc-500 hover:text-zinc-200'
                }`}
              >
                {WINDOW_LABELS[key].toUpperCase()}
              </button>
            ))}
          </div>
        </div>
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <div className="font-mono text-4xl font-bold leading-none text-white">{money2(stats.paperBalance)}</div>
            <div className="mt-1 font-mono text-xs text-zinc-500">
              Starting {money2(paperAccountUsd)} | {money2(stats.paperBalance * Number(botStatus?.inr_usd_rate ?? 86.5)).replace('$', '₹')}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <span className={`h-2 w-2 rounded-full ${botStatus?.bot_state === 'running' || botStatus?.is_running ? 'bg-emerald-400' : 'bg-amber-400'}`} />
              <span className={`text-sm font-semibold ${botStatus?.bot_state === 'running' || botStatus?.is_running ? 'text-emerald-300' : 'text-amber-300'}`}>
                {botStatus?.bot_state === 'running' || botStatus?.is_running ? 'Running' : 'Paused'}
              </span>
              <span className="font-mono text-xs text-zinc-500">{holdTime(Number(botStatus?.uptime_seconds ?? 0), nowMs)}</span>
            </div>
            <div className={`font-mono text-sm font-bold ${signedClass(stats.net)}`}>
              {WINDOW_LABELS[windowKey]} {money(stats.net)}
            </div>
            {stats.open > 0 && (
              <div className={`font-mono text-sm font-bold ${signedClass(stats.liveNet)}`}>
                Live {money(stats.liveNet)}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4 xl:grid-cols-8">
        {[
          ['Net P&L', money(stats.net), signedClass(stats.net)],
          ['Gross', money(stats.gross), signedClass(stats.gross)],
          ['Fees', money(-stats.fees), 'text-amber-300'],
          ['Win Rate', `${stats.winRate.toFixed(0)}%`, winRateClass(stats.winRate, stats.closed)],
          ['Trades', `${stats.total}`, 'text-white'],
          ['Live', `${stats.open}`, stats.open ? 'text-emerald-300' : 'text-white'],
          ['Avg Peak', pct(stats.peakAvg), peakClass(stats.peakAvg)],
          ['Leverage', stats.leverages, 'text-violet-200'],
        ].map(([label, value, valueClass]) => (
          <div key={label} className="rounded-md border border-zinc-800 bg-[#0d0e12] p-3 shadow-sm shadow-black">
            <div className="text-[10px] uppercase tracking-wider text-zinc-500">{label}</div>
            <div className={`mt-1 font-mono text-lg ${valueClass}`}>{value}</div>
          </div>
        ))}
      </div>

      <div className="mb-5 grid gap-3 xl:grid-cols-3">
        <PerformancePanel title="Setup Edge" rows={setupStats} />
        <PerformancePanel title="Leverage Read" rows={leverageStats} />
        <PerformancePanel title="Pair Direction" rows={pairStats} />
      </div>

      <div className="mb-5 grid gap-3 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-lg border border-zinc-800 bg-[#0d0e12] p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-bold text-white">What To Watch</h2>
            <span className="text-xs text-zinc-500">{WINDOW_LABELS[windowKey]}</span>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            <Insight label="Net after fees" value={money(stats.net)} tone={stats.net >= 0 ? 'good' : 'bad'} />
            <Insight label="Avg capture" value={stats.avgCapture === null ? '-' : pct(stats.avgCapture)} tone={(stats.avgCapture ?? 0) >= 50 ? 'good' : 'warn'} />
            <Insight label="Avg hold" value={holdTime(stats.avgHold, nowMs)} tone={stats.avgHold >= 300 ? 'good' : 'warn'} />
          </div>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-[#0d0e12] p-4">
          <h2 className="mb-3 text-sm font-bold text-white">Exit Reasons</h2>
          <div className="space-y-2">
            {exitStats.slice(0, 5).map((row) => (
              <div key={row.key} className="flex items-center justify-between gap-3 text-sm">
                <span className="capitalize text-zinc-300">{row.label}</span>
                <span className={`font-mono ${signedClass(row.net)}`}>{money(row.net)}</span>
              </div>
            ))}
            {!exitStats.length && <div className="text-sm text-zinc-500">No closed exits in this window.</div>}
          </div>
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border border-zinc-800 bg-[#08090c]">
        {error ? (
          <div className="p-5 text-sm text-red-300">{error}</div>
        ) : loading ? (
          <div className="p-5 text-sm text-zinc-400">Loading paper trades...</div>
        ) : filteredRows.length === 0 ? (
          <div className="p-5 text-sm text-zinc-400">No paper futures rows in this window.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1360px] text-left text-sm">
              <thead className="border-b border-zinc-800 bg-[#15161a] text-[10px] uppercase tracking-wider text-zinc-400">
                <tr>
                  <th className="px-4 py-3">Time</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Pair</th>
                  <th className="px-4 py-3">Dir</th>
                  <th className="px-4 py-3">Setup</th>
                  <th className="px-4 py-3 text-right">Conf</th>
                  <th className="px-4 py-3 text-right">Lev</th>
                  <th className="px-4 py-3 text-right">Entry</th>
                  <th className="px-4 py-3 text-right">Exit/Mark</th>
                  <th className="px-4 py-3 text-right">Margin</th>
                  <th className="px-4 py-3 text-right">Notional</th>
                  <th className="px-4 py-3 text-right">Gross</th>
                  <th className="px-4 py-3 text-right">Fees</th>
                  <th className="px-4 py-3 text-right">Net P&L</th>
                  <th className="px-4 py-3 text-right">P&L %</th>
                  <th className="px-4 py-3 text-right">Peak</th>
                  <th className="px-4 py-3 text-right">Capture</th>
                  <th className="px-4 py-3">Hold</th>
                  <th className="px-4 py-3">Exit</th>
                  <th className="px-4 py-3">Source</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((row) => {
                  const mark = row.exit_price ?? row.current_price;
                  const cap = capturePct(row);
                  const confidence = confidenceScore(row);
                  const isLive = row.status === 'open';
                  return (
                    <tr
                      key={row.id}
                      className={`border-b border-zinc-900 text-zinc-100 last:border-0 hover:bg-zinc-900/55 ${
                        isLive ? 'bg-emerald-950/20 shadow-[inset_3px_0_0_rgba(52,211,153,0.85)]' : ''
                      }`}
                    >
                      <td className="px-4 py-3 font-mono text-xs text-zinc-300">
                        {new Date(row.opened_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-3">
                        {isLive ? (
                          <span className="inline-flex items-center gap-2 rounded border border-emerald-400/40 bg-emerald-400/15 px-2 py-1 text-xs font-bold text-emerald-200">
                            <span className="h-2 w-2 rounded-full bg-emerald-300 shadow-[0_0_10px_rgba(52,211,153,0.9)]" />
                            LIVE
                          </span>
                        ) : (
                          <span className="text-xs text-zinc-500">Closed</span>
                        )}
                      </td>
                      <td className="px-4 py-3 font-bold text-white">{shortPair(row.pair)}</td>
                      <td className="px-4 py-3">
                        <span className={row.direction === 'long' ? 'font-bold text-emerald-300' : 'font-bold text-red-300'}>
                          {row.direction.toUpperCase()}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="rounded border border-sky-400/30 bg-sky-500/20 px-2 py-1 text-xs font-semibold text-sky-100">
                          {setupLabel(row.setup_type)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-cyan-200">{confidence === null ? '-' : confidence.toFixed(0)}</td>
                      <td className="px-4 py-3 text-right font-mono text-violet-200">{Number(row.leverage).toFixed(0)}x</td>
                      <td className="px-4 py-3 text-right font-mono">{Number(row.entry_price).toFixed(2)}</td>
                      <td className="px-4 py-3 text-right font-mono">{mark ? Number(mark).toFixed(2) : '-'}</td>
                      <td className="px-4 py-3 text-right font-mono">${Number(row.margin_usd).toFixed(2)}</td>
                      <td className="px-4 py-3 text-right font-mono">${Number(row.notional_usd).toFixed(2)}</td>
                      <td className={`px-4 py-3 text-right font-mono ${signedClass(row.gross_pnl_usd)}`}>{money(row.gross_pnl_usd)}</td>
                      <td className="px-4 py-3 text-right font-mono text-amber-300">{money(-(Number(row.fees_usd ?? 0)))}</td>
                      <td className={`px-4 py-3 text-right font-mono font-bold ${signedClass(row.pnl_usd)}`}>
                        {money(row.pnl_usd)}
                      </td>
                      <td className={`px-4 py-3 text-right font-mono ${signedClass(row.pnl_pct)}`}>{pct(row.pnl_pct)}</td>
                      <td className={`px-4 py-3 text-right font-mono ${peakClass(row.peak_pnl_pct)}`}>{pct(row.peak_pnl_pct)}</td>
                      <td className={`px-4 py-3 text-right font-mono ${cap === null ? 'text-zinc-500' : cap >= 50 ? 'text-emerald-300' : 'text-amber-300'}`}>
                        {cap === null ? '-' : pct(cap)}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-zinc-300">{holdTime(row, nowMs)}</td>
                      <td className="px-4 py-3 text-xs capitalize text-zinc-300">{(row.exit_reason || row.status).replace(/_/g, ' ')}</td>
                      <td className="px-4 py-3 font-mono text-xs text-zinc-400">
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

function Insight({ label, value, tone }: { label: string; value: string; tone: 'good' | 'bad' | 'warn' }) {
  const color = tone === 'good' ? 'text-emerald-300' : tone === 'bad' ? 'text-red-300' : 'text-amber-300';
  return (
    <div className="rounded-md border border-zinc-800 bg-black/35 p-3">
      <div className="text-[10px] uppercase tracking-wider text-zinc-500">{label}</div>
      <div className={`mt-1 font-mono text-lg font-bold ${color}`}>{value}</div>
    </div>
  );
}

function PerformancePanel({ title, rows }: { title: string; rows: GroupStats[] }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-[#0d0e12] p-4">
      <h2 className="mb-3 text-sm font-bold text-white">{title}</h2>
      <div className="space-y-3">
        {rows.slice(0, 5).map((row) => (
          <div key={row.key} className="rounded-md border border-zinc-900 bg-black/30 p-3">
            <div className="mb-2 flex items-center justify-between gap-3">
              <span className="text-sm font-bold text-white">{row.label}</span>
              <span className={`font-mono text-sm font-bold ${signedClass(row.net)}`}>{money(row.net)}</span>
            </div>
            <div className="grid grid-cols-5 gap-2 text-[11px]">
              <Metric label="Trades" value={row.trades.toString()} />
              <Metric label="Win" value={`${row.winRate.toFixed(0)}%`} className={winRateClass(row.winRate, row.closed)} />
              <Metric label="Peak" value={pct(row.avgPeak)} className={peakClass(row.avgPeak)} />
              <Metric label="Conf" value={row.confidence === null ? '-' : row.confidence.toFixed(0)} tone={(row.confidence ?? 0) >= 76 ? 'good' : 'warn'} />
              <Metric label="Hold" value={holdTime(row.avgHold)} />
            </div>
          </div>
        ))}
        {!rows.length && <div className="text-sm text-zinc-500">No rows in this window.</div>}
      </div>
    </div>
  );
}

function Metric({ label, value, tone, className }: { label: string; value: string; tone?: 'good' | 'bad' | 'warn'; className?: string }) {
  const color = className || (tone === 'good' ? 'text-emerald-300' : tone === 'bad' ? 'text-red-300' : tone === 'warn' ? 'text-amber-300' : 'text-zinc-100');
  return (
    <div>
      <div className="uppercase tracking-wider text-zinc-600">{label}</div>
      <div className={`mt-0.5 font-mono font-semibold ${color}`}>{value}</div>
    </div>
  );
}

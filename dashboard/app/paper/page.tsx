'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { RefreshCw } from 'lucide-react';

type WindowKey = 'today' | '7d' | '14d' | '28d' | 'all';
type Instrument = 'options' | 'futures';

interface PaperBotStatus {
  bot_state?: string | null;
  is_running?: boolean | null;
  is_paused?: boolean | null;
  uptime_seconds?: number | null;
  created_at?: string | null;
  inr_usd_rate?: number | null;
}

interface URow {
  id: number;
  instrument: Instrument;
  pair: string;
  setup_type?: string | null;
  direction: string;
  status: string;
  opened_at: string;
  closed_at?: string | null;
  entry: number;
  mark: number | null;
  sizeUsd: number;
  notional: number;
  gross: number;
  fees: number;
  net: number;
  pnlPct: number;
  peakPct: number;
  exit_reason?: string | null;
  leverage: number;
  confidence: number | null;
  moneyness?: string | null;
  optionType?: string | null;
  strike?: number | null;
}

const WINDOW_LABELS: Record<WindowKey, string> = {
  today: 'Today', '7d': '7 days', '14d': '14 days', '28d': '28 days', all: 'All',
};

const SETUP_LABELS: Record<string, string> = {
  DONCHIAN_BREAKOUT: 'Donchian', EMA_PULLBACK: 'EMA Pullback', MOMENTUM_IMPULSE: 'Momentum',
  SIGNAL_MIX: 'Signal Mix', OPTIONS_TWIN: 'Options Twin',
  OPT_TREND_RIDE: 'Trend Ride', OPT_DONCHIAN: 'Donchian', OPT_MOMENTUM: 'Momentum', OPT_EMA_PULLBACK: 'EMA Pullback',
  OPT_TREND_RIDE_OTM: 'Trend Ride OTM', OPT_DONCHIAN_OTM: 'Donchian OTM', OPT_TREND_RUNNER: 'Trend Runner', OPT_MEAN_REVERT: 'Mean Revert',
};

const num = (v: unknown): number => {
  const n = Number(v ?? 0);
  return Number.isFinite(n) ? n : 0;
};

function money(value?: number | null, decimals = 4): string {
  const n = num(value);
  const sign = n > 0 ? '+' : n < 0 ? '-' : '';
  return `${sign}$${Math.abs(n).toFixed(decimals)}`;
}
const money2 = (v?: number | null) => money(v, 2);
function pct(value?: number | null): string {
  const n = num(value);
  return `${n > 0 ? '+' : ''}${n.toFixed(2)}%`;
}
function signedClass(value?: number | null): string {
  const n = num(value);
  return n > 0 ? 'text-emerald-300' : n < 0 ? 'text-red-300' : 'text-white';
}
function winRateClass(value: number, count: number): string {
  if (count === 0 || value === 0) return 'text-white';
  if (value < 20) return 'text-red-300';
  if (value < 40) return 'text-amber-300';
  if (value < 67) return 'text-emerald-300';
  return 'text-fuchsia-300';
}
function peakClass(value?: number | null): string {
  const n = num(value);
  if (n <= 0) return 'text-white';
  if (n < 2) return 'text-lime-200';
  if (n < 6) return 'text-emerald-300';
  return 'text-green-300';
}
const shortPair = (pair: string) => (pair || '').replace('/USD:USD', '').replace('/USDT', '');
function setupLabel(setup?: string | null): string {
  if (!setup) return '-';
  return SETUP_LABELS[setup] || setup.replace(/_/g, ' ');
}

function confFromMeta(meta: Record<string, unknown> | null | undefined): number | null {
  const raw = meta?.confidence_score;
  if (raw === null || raw === undefined) return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

function mapFutures(r: Record<string, any>): URow {
  return {
    id: r.id, instrument: 'futures', pair: r.pair, setup_type: r.setup_type, direction: r.direction,
    status: r.status, opened_at: r.opened_at, closed_at: r.closed_at,
    entry: num(r.entry_price), mark: r.exit_price ?? r.current_price ?? null,
    sizeUsd: num(r.margin_usd), notional: num(r.notional_usd),
    gross: num(r.gross_pnl_usd), fees: num(r.fees_usd), net: num(r.pnl_usd),
    pnlPct: num(r.pnl_pct), peakPct: num(r.peak_pnl_pct), exit_reason: r.exit_reason,
    leverage: num(r.leverage), confidence: confFromMeta(r.metadata),
  };
}
function mapOptions(r: Record<string, any>): URow {
  return {
    id: r.id, instrument: 'options', pair: r.pair, setup_type: r.setup_type, direction: r.direction,
    status: r.status, opened_at: r.opened_at, closed_at: r.closed_at,
    entry: num(r.entry_premium), mark: r.exit_premium ?? r.current_premium ?? null,
    sizeUsd: num(r.stake_usd), notional: num(r.notional_usd),
    gross: num(r.gross_pnl_usd), fees: num(r.fees_usd), net: num(r.pnl_usd),
    pnlPct: num(r.pnl_pct), peakPct: num(r.peak_pnl_pct), exit_reason: r.exit_reason,
    leverage: 1, confidence: confFromMeta(r.metadata),
    moneyness: r.moneyness, optionType: r.option_type, strike: r.strike,
  };
}

function holdSeconds(row: URow, nowMs = Date.now()): number {
  const start = new Date(row.opened_at).getTime();
  const end = row.closed_at ? new Date(row.closed_at).getTime() : nowMs;
  if (!Number.isFinite(start) || !Number.isFinite(end)) return 0;
  return Math.max(0, Math.round((end - start) / 1000));
}
function holdTime(rowOrSeconds: URow | number, nowMs = Date.now()): string {
  const seconds = typeof rowOrSeconds === 'number' ? rowOrSeconds : holdSeconds(rowOrSeconds, nowMs);
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60), rem = seconds % 60;
  if (m < 60) return `${m}m ${rem}s`;
  return `${Math.floor(m / 60)}h ${m % 60}m`;
}
function windowStart(key: WindowKey): number {
  const now = new Date();
  if (key === 'all') return 0;
  if (key === 'today') { const s = new Date(now); s.setHours(0, 0, 0, 0); return s.getTime(); }
  const days = key === '7d' ? 7 : key === '14d' ? 14 : 28;
  return now.getTime() - days * 86400000;
}
function returnPct(row: URow): number | null {
  return row.sizeUsd > 0 ? (row.net / row.sizeUsd) * 100 : null;
}

interface GroupStats {
  key: string; label: string; trades: number; closed: number; wins: number;
  net: number; avgPeak: number; avgHold: number; confidence: number | null; winRate: number;
}
function buildGroupStats(rows: URow[], keyFor: (r: URow) => string, labelFor?: (r: URow) => string): GroupStats[] {
  const buckets = new Map<string, URow[]>();
  for (const row of rows) {
    const key = keyFor(row);
    buckets.set(key, [...(buckets.get(key) || []), row]);
  }
  return Array.from(buckets.entries()).map(([key, bucket]) => {
    const closed = bucket.filter((r) => r.status === 'closed');
    const wins = closed.filter((r) => r.net > 0).length;
    const net = closed.reduce((s, r) => s + r.net, 0);
    const avgPeak = closed.length ? closed.reduce((s, r) => s + r.peakPct, 0) / closed.length : 0;
    const avgHold = closed.length ? Math.round(closed.reduce((s, r) => s + holdSeconds(r), 0) / closed.length) : 0;
    const confs = bucket.map((r) => r.confidence).filter((v): v is number => v !== null);
    return {
      key, label: (labelFor || keyFor)(bucket[0]),
      trades: bucket.length, closed: closed.length, wins, net, avgPeak, avgHold,
      confidence: confs.length ? confs.reduce((s, v) => s + v, 0) / confs.length : null,
      winRate: closed.length ? (wins / closed.length) * 100 : 0,
    };
  }).sort((a, b) => b.net - a.net);
}

export default function PaperLabPage() {
  const [futures, setFutures] = useState<URow[]>([]);
  const [options, setOptions] = useState<URow[]>([]);
  const [botStatus, setBotStatus] = useState<PaperBotStatus | null>(null);
  const [paperAccountUsd, setPaperAccountUsd] = useState(100);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [instrument, setInstrument] = useState<Instrument>('options');
  const [windowKey, setWindowKey] = useState<WindowKey>('today');
  const [nowMs, setNowMs] = useState(() => Date.now());

  const fetchRows = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/paper-futures', { cache: 'no-store' });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        setFutures([]); setOptions([]);
        setError(payload.error || 'Failed to load paper rows.');
      } else {
        setFutures(((payload.futures ?? payload.rows ?? []) as Record<string, any>[]).map(mapFutures));
        setOptions(((payload.options ?? []) as Record<string, any>[]).map(mapOptions));
        setBotStatus((payload.botStatus ?? null) as PaperBotStatus | null);
        setPaperAccountUsd(num(payload.paperAccountUsd) || 100);
      }
    } catch (err) {
      setFutures([]); setOptions([]);
      setError(err instanceof Error ? err.message : 'Failed to load paper rows.');
    }
    if (showLoading) setLoading(false);
  }, []);

  useEffect(() => { fetchRows(); }, [fetchRows]);
  useEffect(() => {
    const timer = window.setInterval(() => fetchRows(false), 15_000);
    const onVisible = () => { if (!document.hidden) fetchRows(false); };
    document.addEventListener('visibilitychange', onVisible);
    window.addEventListener('focus', onVisible);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisible);
      window.removeEventListener('focus', onVisible);
    };
  }, [fetchRows]);
  useEffect(() => {
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const allRows = instrument === 'options' ? options : futures;
  const isOpt = instrument === 'options';

  const filteredRows = useMemo(() => {
    const start = windowStart(windowKey);
    return allRows
      .filter((row) => new Date(row.opened_at).getTime() >= start)
      .sort((a, b) => {
        if (a.status === 'open' && b.status !== 'open') return -1;
        if (a.status !== 'open' && b.status === 'open') return 1;
        return new Date(b.opened_at).getTime() - new Date(a.opened_at).getTime();
      });
  }, [allRows, windowKey]);

  const stats = useMemo(() => {
    const closed = filteredRows.filter((r) => r.status === 'closed');
    const wins = closed.filter((r) => r.net > 0).length;
    const net = closed.reduce((s, r) => s + r.net, 0);
    const gross = closed.reduce((s, r) => s + r.gross, 0);
    const fees = closed.reduce((s, r) => s + r.fees, 0);
    const peakAvg = closed.length ? closed.reduce((s, r) => s + r.peakPct, 0) / closed.length : 0;
    const rets = closed.map(returnPct).filter((v): v is number => v !== null);
    const openRows = filteredRows.filter((r) => r.status === 'open');
    const closedAllNet = allRows.filter((r) => r.status === 'closed').reduce((s, r) => s + r.net, 0);
    const mix = isOpt
      ? Array.from(new Set(filteredRows.map((r) => r.moneyness).filter(Boolean))).join(', ') || '-'
      : Array.from(new Set(filteredRows.map((r) => `${r.leverage.toFixed(0)}x`))).join(', ') || '-';
    return {
      total: filteredRows.length, open: openRows.length, closed: closed.length,
      winRate: closed.length ? (wins / closed.length) * 100 : 0,
      net, gross, fees, peakAvg,
      avgReturn: rets.length ? rets.reduce((s, v) => s + v, 0) / rets.length : null,
      avgHold: closed.length ? Math.round(closed.reduce((s, r) => s + holdSeconds(r, nowMs), 0) / closed.length) : 0,
      mix,
      liveNet: openRows.reduce((s, r) => s + r.net, 0),
      paperBalance: paperAccountUsd + closedAllNet,
    };
  }, [filteredRows, nowMs, paperAccountUsd, allRows, isOpt]);

  const setupStats = useMemo(() => buildGroupStats(filteredRows, (r) => r.setup_type || 'UNKNOWN', (r) => setupLabel(r.setup_type)), [filteredRows]);
  const pairStats = useMemo(() => buildGroupStats(filteredRows, (r) => `${shortPair(r.pair)} ${r.direction}`, (r) => `${shortPair(r.pair)} ${r.direction.toUpperCase()}`), [filteredRows]);
  const thirdStats = useMemo(
    () => isOpt
      ? buildGroupStats(filteredRows, (r) => r.moneyness || 'ATM')
      : buildGroupStats(filteredRows, (r) => `${r.leverage.toFixed(0)}x`),
    [filteredRows, isOpt],
  );
  const exitStats = useMemo(
    () => buildGroupStats(filteredRows.filter((r) => r.status === 'closed'), (r) => r.exit_reason || 'open', (r) => (r.exit_reason || 'unknown').replace(/_/g, ' ')),
    [filteredRows],
  );

  const inr = num(botStatus?.inr_usd_rate) || 86.5;
  const running = botStatus?.bot_state === 'running' || botStatus?.is_running;

  return (
    <div className="min-h-screen bg-[#050507] p-4 text-zinc-100 md:p-6">
      <div className="mb-5 flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Paper Lab</h1>
          <p className="mt-0.5 text-xs text-zinc-500">BTC + ETH · buy-only options &amp; futures · price-action · no real money</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex overflow-hidden rounded-md border border-zinc-700">
            {(['options', 'futures'] as Instrument[]).map((key) => (
              <button
                key={key}
                onClick={() => setInstrument(key)}
                className={`px-4 py-2 text-sm font-bold capitalize transition-colors ${
                  instrument === key
                    ? (key === 'options' ? 'bg-lime-500/20 text-lime-200' : 'bg-violet-500/20 text-violet-200')
                    : 'bg-zinc-900 text-zinc-500 hover:text-zinc-200'
                }`}
              >
                {key === 'options' ? 'Options' : 'Futures'}
              </button>
            ))}
          </div>
          <button
            onClick={() => fetchRows()}
            className="inline-flex items-center gap-2 rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm font-semibold text-zinc-100 hover:bg-zinc-800"
          >
            <RefreshCw size={15} />
            Refresh
          </button>
        </div>
      </div>

      <div className="mb-5 rounded-xl border border-zinc-800 bg-[#101116] p-4 shadow-sm shadow-black">
        <div className="mb-2 flex items-center justify-between gap-4">
          <span className="text-xs uppercase tracking-wider text-zinc-500">
            Paper {isOpt ? 'Options' : 'Futures'} Balance
          </span>
          <div className="flex gap-1">
            {(['today', '7d', '14d', '28d', 'all'] as WindowKey[]).map((key) => (
              <button
                key={key}
                onClick={() => setWindowKey(key)}
                className={`rounded px-2 py-1 text-[10px] font-bold transition-colors ${
                  windowKey === key ? 'bg-white/10 text-white' : 'border border-white/10 text-zinc-500 hover:text-zinc-200'
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
              Starting {money2(paperAccountUsd)} | ₹{(stats.paperBalance * inr).toFixed(0)}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <span className={`h-2 w-2 rounded-full ${running ? 'bg-emerald-400' : 'bg-amber-400'}`} />
              <span className={`text-sm font-semibold ${running ? 'text-emerald-300' : 'text-amber-300'}`}>
                {running ? 'Running' : 'Paused'}
              </span>
              <span className="font-mono text-xs text-zinc-500">{holdTime(num(botStatus?.uptime_seconds), nowMs)}</span>
            </div>
            <div className={`font-mono text-sm font-bold ${signedClass(stats.net)}`}>
              {WINDOW_LABELS[windowKey]} {money(stats.net)}
            </div>
            {stats.open > 0 && (
              <div className={`font-mono text-sm font-bold ${signedClass(stats.liveNet)}`}>Live {money(stats.liveNet)}</div>
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
          [isOpt ? 'Moneyness' : 'Leverage', stats.mix, isOpt ? 'text-lime-200' : 'text-violet-200'],
        ].map(([label, value, valueClass]) => (
          <div key={label} className="rounded-md border border-zinc-800 bg-[#0d0e12] p-3 shadow-sm shadow-black">
            <div className="text-[10px] uppercase tracking-wider text-zinc-500">{label}</div>
            <div className={`mt-1 truncate font-mono text-lg ${valueClass}`}>{value}</div>
          </div>
        ))}
      </div>

      <div className="mb-5 grid gap-3 xl:grid-cols-3">
        <PerformancePanel title="Setup Edge" rows={setupStats} />
        <PerformancePanel title={isOpt ? 'Moneyness Read' : 'Leverage Read'} rows={thirdStats} />
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
            <Insight label="Avg return" value={stats.avgReturn === null ? '-' : pct(stats.avgReturn)} tone={(stats.avgReturn ?? 0) >= 0 ? 'good' : 'bad'} />
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
          <div className="p-5 text-sm text-zinc-400">No paper {isOpt ? 'options' : 'futures'} trades in this window yet.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1500px] text-left text-sm">
              <thead className="border-b border-zinc-800 bg-[#15161a] text-[10px] uppercase tracking-wider text-zinc-500">
                <tr>
                  <th className="sticky left-0 z-20 w-[320px] bg-[#15161a] px-4 py-3">Trade</th>
                  <th className="px-3 py-3">Opened</th>
                  <th className="px-3 py-3 text-right">Conf</th>
                  <th className="px-3 py-3 text-right">{isOpt ? 'Strike' : 'Lev'}</th>
                  <th className="px-3 py-3 text-right">{isOpt ? 'Entry $' : 'Entry'}</th>
                  <th className="px-3 py-3 text-right">{isOpt ? 'Mark $' : 'Mark'}</th>
                  <th className="px-3 py-3 text-right">{isOpt ? 'Stake' : 'Margin'}</th>
                  <th className="px-3 py-3 text-right">Notional</th>
                  <th className="px-3 py-3 text-right">Gross</th>
                  <th className="px-3 py-3 text-right">Fees</th>
                  <th className="px-3 py-3 text-right">Net</th>
                  <th className="px-3 py-3 text-right">Return</th>
                  <th className="px-3 py-3 text-right">Peak</th>
                  <th className="px-3 py-3">Hold</th>
                  <th className="px-3 py-3">Exit</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((row) => {
                  const isLive = row.status === 'open';
                  const ret = returnPct(row);
                  const entryDec = isOpt ? 2 : 2;
                  return (
                    <tr
                      key={`${row.instrument}-${row.id}`}
                      className={`border-b border-zinc-900 text-zinc-100 last:border-0 hover:bg-zinc-900/55 ${isLive ? 'bg-emerald-950/15' : ''}`}
                    >
                      <td className={`sticky left-0 z-10 whitespace-nowrap px-4 py-3 ${isLive ? 'bg-[#071611]' : 'bg-[#08090c]'}`}>
                        <div className="grid grid-cols-[54px_50px_46px_104px] items-center gap-2">
                          {isLive ? (
                            <span className="inline-flex items-center justify-center gap-1 rounded border border-emerald-400/40 bg-emerald-400/15 px-2 py-0.5 text-[10px] font-bold text-emerald-200">
                              <span className="h-1.5 w-1.5 rounded-full bg-emerald-300" />LIVE
                            </span>
                          ) : (
                            <span className="text-[10px] font-semibold text-zinc-500">Closed</span>
                          )}
                          <span className="font-bold text-white">{shortPair(row.pair)}</span>
                          <span className={row.direction === 'long' ? 'font-bold text-emerald-300' : 'font-bold text-red-300'}>
                            {isOpt ? (row.optionType === 'call' ? 'CALL' : 'PUT') : row.direction.toUpperCase()}
                          </span>
                          <span className={`truncate rounded border px-2 py-0.5 text-center text-[10px] font-semibold ${isOpt ? 'border-lime-400/30 bg-lime-500/15 text-lime-100' : 'border-sky-400/30 bg-sky-500/20 text-sky-100'}`}>
                            {setupLabel(row.setup_type)}
                          </span>
                        </div>
                      </td>
                      <td className="whitespace-nowrap px-3 py-3 font-mono text-xs text-zinc-500">{new Date(row.opened_at).toLocaleString()}</td>
                      <td className="px-3 py-3 text-right font-mono text-cyan-200">{row.confidence === null ? '-' : row.confidence.toFixed(0)}</td>
                      <td className="px-3 py-3 text-right font-mono text-violet-200">
                        {isOpt ? `${row.strike ?? '-'}${row.moneyness ? ` ${row.moneyness}` : ''}` : `${row.leverage.toFixed(0)}x`}
                      </td>
                      <td className="px-3 py-3 text-right font-mono">{row.entry.toFixed(entryDec)}</td>
                      <td className="px-3 py-3 text-right font-mono">{row.mark === null ? '-' : num(row.mark).toFixed(entryDec)}</td>
                      <td className="px-3 py-3 text-right font-mono">${row.sizeUsd.toFixed(2)}</td>
                      <td className="px-3 py-3 text-right font-mono">${row.notional.toFixed(2)}</td>
                      <td className={`px-3 py-3 text-right font-mono ${signedClass(row.gross)}`}>{money(row.gross)}</td>
                      <td className="px-3 py-3 text-right font-mono text-amber-300">{money(-row.fees)}</td>
                      <td className={`px-3 py-3 text-right font-mono font-bold ${signedClass(row.net)}`}>{money(row.net)}</td>
                      <td className={`px-3 py-3 text-right font-mono font-bold ${signedClass(ret)}`}>{ret === null ? '-' : pct(ret)}</td>
                      <td className={`px-3 py-3 text-right font-mono ${peakClass(row.peakPct)}`}>{pct(row.peakPct)}</td>
                      <td className="whitespace-nowrap px-3 py-3 font-mono text-xs text-zinc-300">{holdTime(row, nowMs)}</td>
                      <td className="whitespace-nowrap px-3 py-3 text-xs capitalize text-zinc-300">{(row.exit_reason || row.status).replace(/_/g, ' ')}</td>
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

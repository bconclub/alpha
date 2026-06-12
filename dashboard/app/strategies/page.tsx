'use client';

import { useCallback, useMemo, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import { getSupabase } from '@/lib/supabase';
import { SetupChip } from '@/components/ui/SetupChip';
import LiveMirrorPanel from '@/components/LiveMirrorPanel';
import { cn, formatDate, formatDuration, formatPnL, getPnLColor } from '@/lib/utils';
import type { SetupConfig, Trade } from '@/lib/types';

type TimeWindow = 'today' | '7d' | '14d' | '28d';

const TIME_WINDOWS: { key: TimeWindow; label: string }[] = [
  { key: 'today', label: 'Today' },
  { key: '7d', label: '7 days' },
  { key: '14d', label: '14 days' },
  { key: '28d', label: '28 days' },
];

const LIVE_SETUPS = ['SQUEEZE', 'MOM_BURST', 'PULLBACK', 'TREND_FLOW', 'PREMIUM_WAVE'] as const;
const LIVE_SETUP_SET = new Set<string>(LIVE_SETUPS);
const IST_OFFSET_MS = 5.5 * 60 * 60 * 1000;

type SetupStats = {
  setup: string;
  enabled: boolean;
  trades: Trade[];
  total: number;
  wins: number;
  losses: number;
  net: number;
  gross: number;
  fees: number;
  winRate: number;
  avgPeak: number;
  avgCapture: number;
  avgHoldSec: number;
  bestPeak: number;
  lastTrade?: Trade;
};

function canonicalSetup(setup: string | null | undefined): string {
  const raw = (setup || '').trim().toUpperCase();
  if (!raw) return 'UNLABELED';
  if (raw === 'BB_SQUEEZE' || raw === 'BB_SQUEEZE_BREAKOUT' || raw === 'SQUEEZE_BREAKOUT') return 'SQUEEZE';
  if (raw === 'MOMENTUM_BURST' || raw === 'MOMENTUM_BURST_ENTRY') return 'MOM_BURST';
  if (raw === 'MOVE_PULLBACK' || raw === 'PULL_BACK') return 'PULLBACK';
  if (raw === 'PREMIUM_WAVE' || raw === 'WAVE') return 'PREMIUM_WAVE';
  if (raw === 'FVG_REVERSAL' || raw === 'FVG_REVERSE') return 'FVG_CHOCH';
  return raw;
}

function getWindowCutoff(window: TimeWindow): Date {
  const now = new Date();
  if (window === '7d') return new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  if (window === '14d') return new Date(now.getTime() - 14 * 24 * 60 * 60 * 1000);
  if (window === '28d') return new Date(now.getTime() - 28 * 24 * 60 * 60 * 1000);

  const istNow = new Date(now.getTime() + IST_OFFSET_MS);
  const startIst = Date.UTC(istNow.getUTCFullYear(), istNow.getUTCMonth(), istNow.getUTCDate());
  return new Date(startIst - IST_OFFSET_MS);
}

function getTradeTime(trade: Trade): number {
  return new Date(trade.timestamp).getTime();
}

function holdSeconds(trade: Trade): number {
  const start = new Date(trade.timestamp).getTime();
  const end = trade.closed_at ? new Date(trade.closed_at).getTime() : Date.now();
  if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return 0;
  return Math.round((end - start) / 1000);
}

function pct(value: number | null | undefined): string {
  const n = Number(value ?? 0);
  const sign = n > 0 ? '+' : '';
  return `${sign}${n.toFixed(2)}%`;
}

function capturePct(trade: Trade): number | null {
  const peak = Number(trade.peak_pnl ?? 0);
  const taken = Number(trade.pnl_pct ?? 0);
  if (peak <= 0) return null;
  return (taken / peak) * 100;
}

function formatSetupName(setup: string): string {
  if (setup === 'MOM_BURST') return 'Momentum Burst';
  if (setup === 'TREND_FLOW') return 'Trend Flow';
  if (setup === 'PREMIUM_WAVE') return 'Premium Wave';
  if (setup === 'UNLABELED') return 'Unlabeled';
  return setup.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
}

function shortPair(pair: string): string {
  const m = pair.match(/^(\w+)\/.*-(\d{6})-(\d+)-([CP])$/);
  if (!m) return pair.replace('/USD:USD', '');
  const [, asset, , strike, cp] = m;
  return `${asset} ${strike}${cp}`;
}

function buildConfigMap(configs: SetupConfig[]): Record<string, SetupConfig> {
  const map: Record<string, SetupConfig> = {};
  for (const config of configs) {
    map[canonicalSetup(config.setup_type)] = config;
  }
  return map;
}

function computeStats(setup: string, trades: Trade[], configMap: Record<string, SetupConfig>): SetupStats {
  const setupTrades = trades.filter((trade) => canonicalSetup(trade.setup_type) === setup);
  const wins = setupTrades.filter((trade) => Number(trade.pnl ?? 0) > 0).length;
  const losses = setupTrades.length - wins;
  const net = setupTrades.reduce((sum, trade) => sum + Number(trade.pnl ?? 0), 0);
  const gross = setupTrades.reduce((sum, trade) => sum + Number(trade.gross_pnl ?? trade.pnl ?? 0), 0);
  const fees = setupTrades.reduce((sum, trade) => sum + Number(trade.entry_fee ?? 0) + Number(trade.exit_fee ?? 0), 0);
  const peaks = setupTrades.map((trade) => Number(trade.peak_pnl ?? 0));
  const captures = setupTrades.map(capturePct).filter((value): value is number => value != null);
  const holdTotal = setupTrades.reduce((sum, trade) => sum + holdSeconds(trade), 0);

  return {
    setup,
    enabled: configMap[setup]?.enabled ?? true,
    trades: setupTrades,
    total: setupTrades.length,
    wins,
    losses,
    net,
    gross,
    fees,
    winRate: setupTrades.length ? (wins / setupTrades.length) * 100 : 0,
    avgPeak: peaks.length ? peaks.reduce((sum, value) => sum + value, 0) / peaks.length : 0,
    avgCapture: captures.length ? captures.reduce((sum, value) => sum + value, 0) / captures.length : 0,
    avgHoldSec: setupTrades.length ? holdTotal / setupTrades.length : 0,
    bestPeak: peaks.length ? Math.max(...peaks) : 0,
    lastTrade: setupTrades[0],
  };
}

export default function StrategiesPage() {
  const { trades, setupConfigs, refreshViews } = useSupabase();
  const [timeWindow, setTimeWindow] = useState<TimeWindow>('today');
  const [savingSetup, setSavingSetup] = useState<string | null>(null);

  const cutoff = useMemo(() => getWindowCutoff(timeWindow), [timeWindow]);
  const configMap = useMemo(() => buildConfigMap(setupConfigs), [setupConfigs]);

  const recentClosedTrades = useMemo(() => {
    return trades
      .filter((trade) => trade.status === 'closed')
      .filter((trade) => getTradeTime(trade) >= cutoff.getTime())
      .filter((trade) => LIVE_SETUP_SET.has(canonicalSetup(trade.setup_type)))
      .sort((a, b) => getTradeTime(b) - getTradeTime(a));
  }, [trades, cutoff]);

  const setupOrder = useMemo(() => {
    const found = new Set<string>(LIVE_SETUPS);
    for (const trade of recentClosedTrades) {
      found.add(canonicalSetup(trade.setup_type));
    }
    return Array.from(found).filter((setup) => setup !== 'UNLABELED' || recentClosedTrades.some((trade) => canonicalSetup(trade.setup_type) === 'UNLABELED'));
  }, [recentClosedTrades]);

  const setupStats = useMemo(() => {
    return setupOrder
      .map((setup) => computeStats(setup, recentClosedTrades, configMap))
      .sort((a, b) => {
        if (b.total !== a.total) return b.total - a.total;
        return a.net - b.net;
      });
  }, [setupOrder, recentClosedTrades, configMap]);

  const totals = useMemo(() => {
    const wins = recentClosedTrades.filter((trade) => Number(trade.pnl ?? 0) > 0).length;
    const net = recentClosedTrades.reduce((sum, trade) => sum + Number(trade.pnl ?? 0), 0);
    const avgPeak = recentClosedTrades.length
      ? recentClosedTrades.reduce((sum, trade) => sum + Number(trade.peak_pnl ?? 0), 0) / recentClosedTrades.length
      : 0;
    const avgHold = recentClosedTrades.length
      ? recentClosedTrades.reduce((sum, trade) => sum + holdSeconds(trade), 0) / recentClosedTrades.length
      : 0;
    return {
      trades: recentClosedTrades.length,
      winRate: recentClosedTrades.length ? (wins / recentClosedTrades.length) * 100 : 0,
      net,
      avgPeak,
      avgHold,
    };
  }, [recentClosedTrades]);

  const handleSetupToggle = useCallback(async (setup: string, enabled: boolean) => {
    const client = getSupabase();
    if (!client) return;
    setSavingSetup(setup);
    try {
      const existing = setupConfigs.find((config) => canonicalSetup(config.setup_type) === setup);
      const setupTypeForDb = existing?.setup_type ?? setup;
      await client.from('setup_config').upsert({
        setup_type: setupTypeForDb,
        enabled,
        updated_at: new Date().toISOString(),
      });
      await client.from('bot_commands').insert({
        command: 'update_config',
        params: { setup_type: setupTypeForDb, enabled },
        executed: false,
      });
      refreshViews();
    } finally {
      setSavingSetup(null);
    }
  }, [refreshViews, setupConfigs]);

  return (
    <div className="space-y-5">
      {/* The live strategy: what the mirror trades, which paper lane it copies,
          rails and live W/L. Belongs here — not on the home page. */}
      <LiveMirrorPanel />

      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white">Strategy Performance</h1>
          <p className="mt-1 text-sm text-zinc-500">
            Recent performance by the setups Alpha is actually trading.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {TIME_WINDOWS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setTimeWindow(key)}
              className={cn(
                'rounded-md px-3 py-1.5 text-xs font-semibold transition-colors',
                timeWindow === key
                  ? 'bg-sky-500/20 text-sky-200 ring-1 ring-sky-400/30'
                  : 'bg-zinc-900 text-zinc-400 ring-1 ring-zinc-800 hover:text-zinc-200',
              )}
            >
              {label}
            </button>
          ))}
          <button
            onClick={refreshViews}
            className="inline-flex items-center gap-1.5 rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-semibold text-zinc-300 ring-1 ring-zinc-800 hover:text-white"
          >
            <RefreshCw size={13} />
            Refresh
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {[
          ['Trades', totals.trades.toString(), 'text-zinc-100'],
          ['Win Rate', `${totals.winRate.toFixed(0)}%`, totals.winRate >= 50 ? 'text-emerald-300' : 'text-red-300'],
          ['Net P&L', formatPnL(totals.net), getPnLColor(totals.net)],
          ['Avg Peak', pct(totals.avgPeak), 'text-emerald-300'],
          ['Avg Hold', formatDuration(totals.avgHold), 'text-zinc-100'],
        ].map(([label, value, color]) => (
          <div key={label} className="rounded-md border border-zinc-800 bg-[#0d1117] p-3">
            <div className="text-[10px] uppercase tracking-wider text-zinc-500">{label}</div>
            <div className={cn('mt-1 font-mono text-lg font-semibold', color)}>{value}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        {setupStats.map((stats) => {
          const hasTrades = stats.total > 0;
          const cold = hasTrades && stats.winRate < 35 && stats.net < 0;
          const hot = hasTrades && stats.winRate >= 50 && stats.net > 0;

          return (
            <section
              key={stats.setup}
              className={cn(
                'rounded-lg border bg-[#0d1117] p-4',
                cold ? 'border-red-500/30' : hot ? 'border-emerald-500/30' : 'border-zinc-800',
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <SetupChip setup={stats.setup} />
                    <span className="text-sm font-semibold text-white">{formatSetupName(stats.setup)}</span>
                    {hot && <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-[9px] font-bold uppercase text-emerald-300">Working</span>}
                    {cold && <span className="rounded bg-red-500/15 px-1.5 py-0.5 text-[9px] font-bold uppercase text-red-300">Bleeding</span>}
                  </div>
                  <p className="mt-1 text-xs text-zinc-500">
                    {hasTrades
                      ? `${stats.wins} wins / ${stats.losses} losses in selected window`
                      : 'No closed trades in selected window'}
                  </p>
                </div>
                <button
                  disabled={savingSetup === stats.setup}
                  onClick={() => handleSetupToggle(stats.setup, !stats.enabled)}
                  className={cn(
                    'relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors',
                    stats.enabled ? 'bg-emerald-500' : 'bg-zinc-700',
                    savingSetup === stats.setup && 'opacity-60',
                  )}
                  title={stats.enabled ? 'Disable setup' : 'Enable setup'}
                >
                  <span
                    className={cn(
                      'inline-block h-4 w-4 rounded-full bg-white transition-transform',
                      stats.enabled ? 'translate-x-6' : 'translate-x-1',
                    )}
                  />
                </button>
              </div>

              <div className="mt-4 grid grid-cols-3 gap-3 md:grid-cols-6">
                <Metric label="Trades" value={stats.total.toString()} />
                <Metric label="Win" value={`${stats.winRate.toFixed(0)}%`} color={stats.winRate >= 50 ? 'text-emerald-300' : 'text-red-300'} />
                <Metric label="Net" value={formatPnL(stats.net)} color={getPnLColor(stats.net)} />
                <Metric label="Avg Peak" value={pct(stats.avgPeak)} color="text-emerald-300" />
                <Metric label="Capture" value={`${stats.avgCapture.toFixed(0)}%`} color={stats.avgCapture >= 50 ? 'text-emerald-300' : 'text-amber-300'} />
                <Metric label="Hold" value={formatDuration(stats.avgHoldSec)} />
              </div>

              {stats.lastTrade && (
                <div className="mt-4 rounded-md bg-zinc-950/70 px-3 py-2 text-xs">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-semibold text-zinc-200">Last trade</span>
                    <span className="font-mono text-zinc-500">{formatDate(stats.lastTrade.timestamp)}</span>
                  </div>
                  <div className="mt-2 grid grid-cols-2 gap-2 md:grid-cols-5">
                    <Mini label="Pair" value={shortPair(stats.lastTrade.pair)} />
                    <Mini label="Net" value={formatPnL(stats.lastTrade.pnl)} color={getPnLColor(stats.lastTrade.pnl)} />
                    <Mini label="Peak" value={pct(stats.lastTrade.peak_pnl)} color="text-emerald-300" />
                    <Mini label="Taken" value={pct(stats.lastTrade.pnl_pct)} color={getPnLColor(stats.lastTrade.pnl_pct ?? 0)} />
                    <Mini label="Exit" value={stats.lastTrade.exit_reason || 'Unknown'} />
                  </div>
                </div>
              )}
            </section>
          );
        })}
      </div>

      <section className="rounded-lg border border-zinc-800 bg-[#0d1117]">
        <div className="border-b border-zinc-800 px-4 py-3">
          <h2 className="text-sm font-semibold text-white">Recent Setup Trades</h2>
        </div>
        {recentClosedTrades.length === 0 ? (
          <div className="p-6 text-sm text-zinc-500">No closed trades in this window.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[920px] text-left text-sm">
              <thead className="bg-zinc-900/70 text-[10px] uppercase tracking-wider text-zinc-500">
                <tr>
                  <th className="px-4 py-3">Time</th>
                  <th className="px-4 py-3">Pair</th>
                  <th className="px-4 py-3">Setup</th>
                  <th className="px-4 py-3 text-right">Net</th>
                  <th className="px-4 py-3 text-right">P&L %</th>
                  <th className="px-4 py-3 text-right">Peak</th>
                  <th className="px-4 py-3 text-right">Capture</th>
                  <th className="px-4 py-3 text-right">Hold</th>
                  <th className="px-4 py-3">Exit</th>
                </tr>
              </thead>
              <tbody>
                {recentClosedTrades.slice(0, 80).map((trade) => {
                  const capture = capturePct(trade);
                  return (
                    <tr key={trade.id} className="border-t border-zinc-900 text-zinc-300">
                      <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-zinc-500">{formatDate(trade.timestamp)}</td>
                      <td className="whitespace-nowrap px-4 py-3 font-semibold text-zinc-100">{shortPair(trade.pair)}</td>
                      <td className="whitespace-nowrap px-4 py-3"><SetupChip setup={canonicalSetup(trade.setup_type)} /></td>
                      <td className={cn('whitespace-nowrap px-4 py-3 text-right font-mono', getPnLColor(trade.pnl))}>{formatPnL(trade.pnl)}</td>
                      <td className={cn('whitespace-nowrap px-4 py-3 text-right font-mono', getPnLColor(trade.pnl_pct ?? 0))}>{pct(trade.pnl_pct)}</td>
                      <td className="whitespace-nowrap px-4 py-3 text-right font-mono text-emerald-300">{pct(trade.peak_pnl)}</td>
                      <td className={cn('whitespace-nowrap px-4 py-3 text-right font-mono', capture != null && capture >= 50 ? 'text-emerald-300' : 'text-amber-300')}>
                        {capture == null ? '-' : `${capture.toFixed(0)}%`}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-right font-mono text-zinc-400">{formatDuration(holdSeconds(trade))}</td>
                      <td className="whitespace-nowrap px-4 py-3 text-xs text-zinc-400">{trade.exit_reason || 'Unknown'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function Metric({
  label,
  value,
  color = 'text-zinc-100',
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-zinc-500">{label}</div>
      <div className={cn('mt-1 font-mono text-sm font-semibold', color)}>{value}</div>
    </div>
  );
}

function Mini({
  label,
  value,
  color = 'text-zinc-300',
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-zinc-600">{label}</div>
      <div className={cn('mt-0.5 truncate font-mono text-xs', color)}>{value}</div>
    </div>
  );
}

'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { Activity, AlertTriangle, ArrowRight, Crosshair, History, Wallet } from 'lucide-react';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import { cn, formatCurrency } from '@/lib/utils';
import { computePnLStats, istTodayStartMs } from '@/lib/pnl-utils';

// Heartbeat older than this = the engine is not reporting in.
const STALE_SEC = 5 * 60;
// No trade for this long while funded = worth a visible nudge.
const QUIET_DAYS = 3;

type Health = 'live' | 'paused' | 'stale' | 'offline';

const HEALTH: Record<Health, { label: string; dot: string; text: string; ring: string; glow: string }> = {
  live:    { label: 'Running',  dot: 'bg-emerald-400', text: 'text-emerald-300', ring: 'ring-emerald-400/30', glow: 'from-emerald-500/20' },
  paused:  { label: 'Paused',   dot: 'bg-amber-400',   text: 'text-amber-300',   ring: 'ring-amber-400/30',   glow: 'from-amber-500/20' },
  stale:   { label: 'Not reporting', dot: 'bg-red-400', text: 'text-red-300',    ring: 'ring-red-400/30',     glow: 'from-red-500/20' },
  offline: { label: 'Connecting', dot: 'bg-zinc-500',  text: 'text-zinc-400',    ring: 'ring-zinc-500/30',    glow: 'from-zinc-500/10' },
};

function ago(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

function Tile({
  icon, label, children, href,
}: { icon: React.ReactNode; label: string; children: React.ReactNode; href?: string }) {
  const body = (
    <div className="group h-full rounded-2xl border border-white/[0.07] bg-white/[0.03] p-4 transition-colors hover:border-white/15 hover:bg-white/[0.05]">
      <div className="flex items-center justify-between text-zinc-500">
        <span className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.14em]">
          {icon}
          {label}
        </span>
        {href && <ArrowRight className="h-3.5 w-3.5 opacity-0 transition-opacity group-hover:opacity-100" />}
      </div>
      <div className="mt-3">{children}</div>
    </div>
  );
  return href ? <Link href={href} className="block h-full">{body}</Link> : body;
}

export function StatusHero() {
  const { botStatus, isConnected, trades, openPositions, liveSignals } = useSupabase();
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 5000);
    return () => clearInterval(id);
  }, []);

  // ── Engine health: newest of heartbeat row and scanner publish ───────
  const lastSeenMs = useMemo(() => {
    const stamps = [botStatus?.timestamp, ...(liveSignals ?? []).map((s) => s.updated_at)]
      .filter(Boolean)
      .map((t) => new Date(t as string).getTime());
    return stamps.length ? Math.max(...stamps) : null;
  }, [botStatus?.timestamp, liveSignals]);

  const health: Health = !botStatus
    ? 'offline'
    : lastSeenMs != null && (now - lastSeenMs) / 1000 > STALE_SEC
      ? 'stale'
      : botStatus.bot_state === 'error'
        ? 'stale'
        : 'live';
  const h = HEALTH[health];

  // ── Money ────────────────────────────────────────────────────────────
  const balance = Number(botStatus?.delta_balance ?? 0) || Number(botStatus?.capital ?? 0);
  const inr = Math.round(balance * (botStatus?.inr_usd_rate ?? 86.5));

  const closed = useMemo(
    () =>
      trades
        .filter((t) => t.status === 'closed')
        .sort(
          (a, b) =>
            new Date(b.closed_at || b.timestamp).getTime() -
            new Date(a.closed_at || a.timestamp).getTime(),
        ),
    [trades],
  );
  const today = useMemo(() => {
    const cut = istTodayStartMs();
    return computePnLStats(closed.filter((t) => new Date(t.timestamp).getTime() >= cut));
  }, [closed]);

  const lastTrade = closed[0];
  const lastTradeMs = lastTrade ? new Date(lastTrade.closed_at || lastTrade.timestamp).getTime() : null;
  const quietDays = lastTradeMs ? (now - lastTradeMs) / 86_400_000 : null;

  // ── What happens next: closest tradeable setup ──────────────────────
  const next = useMemo(() => {
    let best: { asset: string; side: string; readiness: number; watching: string; firing: boolean } | null = null;
    for (const sig of liveSignals ?? []) {
      const scan = sig.scan;
      if (!scan || scan.tradeable === false || scan.in_position) continue;
      for (const l of scan.lanes ?? []) {
        const firing = scan.status === 'READY' && sig.lane === l.lane;
        const r = firing ? 100 : l.readiness;
        if (!best || r > best.readiness) {
          best = { asset: sig.pair.split('/')[0], side: l.side, readiness: r, watching: l.watching, firing };
        }
      }
    }
    return best;
  }, [liveSignals]);

  const tradeableCount = useMemo(
    () => (liveSignals ?? []).filter((s) => s.scan && s.scan.tradeable !== false).length,
    [liveSignals],
  );
  const openCount = openPositions?.length ?? 0;

  // ── One plain-English line ───────────────────────────────────────────
  const headline =
    health === 'offline' ? 'Connecting to the engine…'
    : health === 'stale' ? 'Engine has stopped reporting. It may be down.'
    : openCount > 0 ? `Managing ${openCount} open trade${openCount > 1 ? 's' : ''}.`
    : next?.firing ? `${next.asset} breakout firing now.`
    : `Watching ${tradeableCount || 'the'} markets for a breakout.`;

  const showQuietWarning =
    health === 'live' && openCount === 0 && quietDays != null && quietDays >= QUIET_DAYS && balance >= 3;
  const showLowBalance = health === 'live' && balance > 0 && balance < 3;

  return (
    <section className="relative overflow-hidden rounded-3xl border border-white/[0.08] bg-[#0f1016]">
      <div className={cn('pointer-events-none absolute -left-24 -top-32 h-72 w-72 rounded-full bg-gradient-to-br to-transparent blur-3xl', h.glow)} />

      <div className="relative p-4 sm:p-6">
        {/* Status line */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className={cn('inline-flex items-center gap-2 rounded-full bg-white/[0.04] px-3 py-1.5 text-xs font-semibold ring-1 ring-inset', h.text, h.ring)}>
              <span className="relative flex h-2 w-2">
                {health === 'live' && <span className={cn('absolute inline-flex h-full w-full animate-ping rounded-full opacity-60', h.dot)} />}
                <span className={cn('relative inline-flex h-2 w-2 rounded-full', h.dot)} />
              </span>
              {h.label}
            </span>
            <span className="text-xs text-zinc-500">
              {lastSeenMs ? `last check ${ago(now - lastSeenMs)}` : isConnected ? 'waiting for data' : 'no connection'}
            </span>
          </div>
          <span className="text-[11px] uppercase tracking-[0.16em] text-zinc-600">Delta · live money</span>
        </div>

        <h1 className="mt-4 text-xl font-semibold tracking-tight text-white sm:text-2xl">{headline}</h1>

        {(showQuietWarning || showLowBalance) && (
          <div className="mt-3 flex items-start gap-2.5 rounded-xl border border-amber-400/20 bg-amber-400/[0.06] px-3.5 py-2.5 text-[13px] leading-snug text-amber-200">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              {showLowBalance
                ? `Balance ${formatCurrency(balance)} is below the ~$3 needed per trade. Entries will fail until you top up.`
                : `No trade in ${Math.floor(quietDays!)} days even though the account is funded. If breakouts have come and gone, check the engine logs.`}
            </span>
          </div>
        )}

        {/* Four answers: money, today, positions, next */}
        <div className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Tile icon={<Wallet className="h-3.5 w-3.5" />} label="Balance">
            <p className="font-mono text-2xl font-semibold tabular-nums text-white sm:text-3xl">{formatCurrency(balance)}</p>
            <p className="mt-1 text-xs text-zinc-500">≈ ₹{inr.toLocaleString('en-IN')}</p>
          </Tile>

          <Tile icon={<Activity className="h-3.5 w-3.5" />} label="Today" href="/pnl">
            <p className={cn(
              'font-mono text-2xl font-semibold tabular-nums sm:text-3xl',
              today.pnl > 0 ? 'text-emerald-400' : today.pnl < 0 ? 'text-red-400' : 'text-white',
            )}>
              {today.pnl >= 0 ? '+' : ''}{formatCurrency(today.pnl)}
            </p>
            <p className="mt-1 text-xs text-zinc-500">
              {today.total === 0 ? 'no trades yet' : `${today.total} trade${today.total > 1 ? 's' : ''} · ${today.wins}W ${today.losses}L`}
            </p>
          </Tile>

          <Tile icon={<Crosshair className="h-3.5 w-3.5" />} label="Next likely trade">
            {next ? (
              <>
                <p className="flex items-baseline gap-2">
                  <span className="text-2xl font-semibold text-white sm:text-3xl">{next.asset}</span>
                  <span className={cn('text-xs font-bold', next.side === 'LONG' ? 'text-emerald-400' : 'text-red-400')}>
                    {next.side === 'LONG' ? '▲' : '▼'} {next.side}
                  </span>
                </p>
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/[0.07]">
                  <div
                    className={cn('h-full rounded-full transition-all', next.firing ? 'bg-emerald-400' : 'bg-gradient-to-r from-amber-500 to-emerald-400')}
                    style={{ width: `${Math.max(4, next.readiness)}%` }}
                  />
                </div>
                <p className="mt-1.5 truncate text-xs text-zinc-500">
                  {next.firing ? 'firing now' : `${next.readiness.toFixed(0)}% there · ${next.watching}`}
                </p>
              </>
            ) : (
              <p className="text-sm text-zinc-500">{openCount > 0 ? 'All slots watching open trades' : 'No scan data yet'}</p>
            )}
          </Tile>

          <Tile icon={<History className="h-3.5 w-3.5" />} label="Last trade" href="/trades">
            {lastTrade && lastTradeMs ? (
              <>
                <p className="flex items-baseline gap-2">
                  <span className={cn(
                    'font-mono text-2xl font-semibold tabular-nums sm:text-3xl',
                    lastTrade.pnl >= 0 ? 'text-emerald-400' : 'text-red-400',
                  )}>
                    {lastTrade.pnl >= 0 ? '+' : ''}{formatCurrency(lastTrade.pnl)}
                  </span>
                </p>
                <p className="mt-1 truncate text-xs text-zinc-500">
                  {lastTrade.pair.split('/')[0]} {lastTrade.position_type} · {ago(now - lastTradeMs)}
                </p>
              </>
            ) : (
              <p className="text-sm text-zinc-500">No closed trades yet</p>
            )}
          </Tile>
        </div>
      </div>
    </section>
  );
}

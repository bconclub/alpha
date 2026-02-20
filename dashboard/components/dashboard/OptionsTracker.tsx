'use client';

import { useMemo } from 'react';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import { formatShortDate, cn } from '@/lib/utils';
import type { ActivityLogRow, StrategyLog } from '@/lib/types';

// Options-eligible assets (options_scalp only runs on BTC + ETH)
const OPTIONS_ASSETS = ['BTC', 'ETH'] as const;

function extractBaseAsset(pair: string): string {
  if (pair.includes('/')) return pair.split('/')[0];
  return pair.replace(/USD.*$/, '');
}

interface OptionsPairState {
  asset: string;
  pair: string;
  // Signal state from scalp (via strategy_log)
  signalStrength: number;
  signalSide: 'long' | 'short' | null;
  signalReason: string;
  // Latest options decision
  lastEvent: ActivityLogRow | null;
  lastEventType: 'options_entry' | 'options_skip' | 'options_exit' | null;
  // Derived
  optionType: string | null;   // call / put
  strike: number | null;
  premium: number | null;
  expiry: string | null;
  // History
  recentEvents: ActivityLogRow[];
}

function EventBadge({ type }: { type: string }) {
  const cfg: Record<string, { label: string; color: string; bg: string }> = {
    options_entry: { label: 'ENTERED', color: 'text-[#7c4dff]', bg: 'bg-[#7c4dff]/10' },
    options_exit:  { label: 'EXITED',  color: 'text-[#7c4dff]', bg: 'bg-[#7c4dff]/10' },
    options_skip:  { label: 'SKIP',    color: 'text-zinc-500',   bg: 'bg-zinc-700/30' },
  };
  const c = cfg[type] ?? cfg.options_skip;
  return (
    <span className={cn('px-1.5 py-0.5 rounded text-[9px] font-mono font-medium', c.color, c.bg)}>
      {c.label}
    </span>
  );
}

export function OptionsTracker() {
  const { strategyLog, optionsLog } = useSupabase();

  const pairStates = useMemo(() => {
    const results: OptionsPairState[] = [];

    for (const asset of OPTIONS_ASSETS) {
      const pair = `${asset}/USD:USD`;

      // Get latest strategy_log for this asset (signal state)
      const log = strategyLog.find((l) => {
        const a = extractBaseAsset(l.pair ?? '');
        return a === asset && (l.exchange ?? 'delta') === 'delta';
      });

      const signalStrength = log?.signal_count ?? 0;
      const signalSide = (log?.signal_side === 'long' || log?.signal_side === 'short')
        ? log.signal_side : null;
      const signalReason = log?.reason ?? '';

      // Get options events for this asset (sorted newest first already)
      const assetEvents = optionsLog.filter((e) => {
        const a = extractBaseAsset(e.pair);
        return a === asset;
      });

      const lastEvent = assetEvents[0] ?? null;
      const lastEventType = lastEvent
        ? (lastEvent.event_type as OptionsPairState['lastEventType'])
        : null;

      const meta = lastEvent?.metadata ?? {};
      const optionType = meta.option_type ?? null;
      const strike = meta.strike ?? null;
      const premium = meta.premium ?? meta.entry_premium ?? null;
      const expiry = meta.expiry ?? null;

      results.push({
        asset,
        pair,
        signalStrength,
        signalSide,
        signalReason,
        lastEvent,
        lastEventType,
        optionType,
        strike,
        premium,
        expiry,
        recentEvents: assetEvents.slice(0, 5),
      });
    }

    return results;
  }, [strategyLog, optionsLog]);

  return (
    <div className="bg-[#0d1117] border border-zinc-800 rounded-xl p-3 md:p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-zinc-400 uppercase tracking-wider">
          Options Tracker
        </h3>
        <span className="text-[9px] text-zinc-600 font-mono">BTC + ETH | need 3/4</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {pairStates.map((s) => {
          const isReady = s.signalStrength >= 3;
          const inPosition = s.lastEventType === 'options_entry';
          const hasExited = s.lastEventType === 'options_exit';

          return (
            <div
              key={s.asset}
              className={cn(
                'bg-zinc-900/40 border rounded-lg p-3',
                inPosition ? 'border-[#7c4dff]/40' : 'border-zinc-800/50',
              )}
            >
              {/* Header row */}
              <div className="flex items-center justify-between mb-2.5">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-white">{s.asset}</span>
                  <span className="text-[10px] font-mono text-zinc-500">{s.pair}</span>
                </div>
                {s.lastEventType && <EventBadge type={s.lastEventType} />}
              </div>

              {/* Signal strength bar */}
              <div className="mb-2.5">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[10px] font-mono text-zinc-500 w-16 shrink-0">Scalp Sig</span>
                  <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-700"
                      style={{
                        width: `${(s.signalStrength / 4) * 100}%`,
                        backgroundColor: s.signalStrength >= 3 ? '#7c4dff' : s.signalStrength >= 1 ? '#ffd600' : '#71717a',
                      }}
                    />
                  </div>
                  <span className={cn(
                    'text-[10px] font-mono w-8 text-right',
                    s.signalStrength >= 3 ? 'text-[#7c4dff]' : s.signalStrength >= 1 ? 'text-[#ffd600]' : 'text-zinc-600',
                  )}>
                    {s.signalStrength}/4
                  </span>
                </div>
                {s.signalSide && (
                  <span className={cn(
                    'text-[9px] font-mono',
                    s.signalSide === 'long' ? 'text-[#00c853]' : 'text-[#ff1744]',
                  )}>
                    {s.signalSide === 'long' ? 'CALL' : 'PUT'} ready
                    {isReady && ' \u2714'}
                  </span>
                )}
              </div>

              {/* Active option position or last action */}
              {inPosition && s.lastEvent ? (
                <div className="bg-[#7c4dff]/5 border border-[#7c4dff]/20 rounded p-2 mb-2">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-medium text-[#7c4dff] uppercase">
                      {s.optionType?.toUpperCase()} Position
                    </span>
                    <span className="text-[9px] font-mono text-zinc-500">
                      {s.lastEvent ? formatShortDate(s.lastEvent.created_at) : ''}
                    </span>
                  </div>
                  <div className="flex gap-3 text-[9px] font-mono text-zinc-400">
                    {s.strike != null && <span>Strike ${s.strike.toLocaleString()}</span>}
                    {s.premium != null && <span>Premium ${s.premium.toFixed(4)}</span>}
                    {s.expiry && (
                      <span>Exp {new Date(s.expiry).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                    )}
                  </div>
                </div>
              ) : hasExited && s.lastEvent ? (
                <div className="bg-zinc-800/30 rounded p-2 mb-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[9px] font-mono text-zinc-500">
                      Last: {s.lastEvent.metadata?.exit_type ?? 'closed'}
                      {' '}{s.lastEvent.metadata?.option_side?.toUpperCase() ?? ''}
                    </span>
                    <span className={cn(
                      'text-[9px] font-mono font-medium',
                      (s.lastEvent.metadata?.pnl_pct ?? 0) >= 0 ? 'text-[#00c853]' : 'text-[#ff1744]',
                    )}>
                      {(s.lastEvent.metadata?.pnl_pct ?? 0) >= 0 ? '+' : ''}{(s.lastEvent.metadata?.pnl_pct ?? 0).toFixed(1)}%
                      {' '}${(s.lastEvent.metadata?.pnl_usd ?? 0) >= 0 ? '+' : ''}{(s.lastEvent.metadata?.pnl_usd ?? 0).toFixed(4)}
                    </span>
                  </div>
                  <span className="text-[9px] font-mono text-zinc-600">
                    {formatShortDate(s.lastEvent.created_at)}
                  </span>
                </div>
              ) : s.lastEventType === 'options_skip' && s.lastEvent ? (
                <div className="text-[9px] font-mono text-zinc-600 truncate mb-2">
                  {s.lastEvent.description.replace(/.*OPTIONS SKIP:\s*/, '')}
                </div>
              ) : (
                <div className="text-[9px] font-mono text-zinc-600 mb-2">
                  Waiting for 3/4+ signal...
                </div>
              )}

              {/* Recent events mini-log */}
              {s.recentEvents.length > 0 && (
                <div className="border-t border-zinc-800/50 pt-1.5 space-y-0.5">
                  {s.recentEvents.slice(0, 3).map((ev) => (
                    <div key={ev.id} className="flex items-center gap-1.5">
                      <span className={cn(
                        'w-1 h-1 rounded-full shrink-0',
                        ev.event_type === 'options_entry' ? 'bg-[#7c4dff]'
                          : ev.event_type === 'options_exit' ? 'bg-[#7c4dff]/50'
                          : 'bg-zinc-700',
                      )} />
                      <span className="text-[8px] font-mono text-zinc-600 truncate">
                        {formatShortDate(ev.created_at)} {ev.event_type.replace('options_', '').toUpperCase()}
                        {ev.metadata?.pnl_pct != null && ` ${ev.metadata.pnl_pct >= 0 ? '+' : ''}${ev.metadata.pnl_pct.toFixed(1)}%`}
                        {ev.metadata?.option_type && ` ${ev.metadata.option_type.toUpperCase()}`}
                        {ev.metadata?.strike && ` $${ev.metadata.strike}`}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

'use client';

import { useMemo, useEffect, useState } from 'react';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import { cn } from '@/lib/utils';
import type { OptionsState } from '@/lib/types';

const OPTIONS_ASSETS = ['BTC', 'ETH'] as const;
const OPTIONS_LEVERAGE = 50;

function fmtSpot(v: number | null): string {
  if (v == null) return '—';
  return `$${v.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
}

function fmtPrem(v: number | null | undefined): string {
  if (v == null || v <= 0) return '—';
  return `$${v.toFixed(2)}`;
}

function fmtHoursRemaining(expiryIso: string | null | undefined): string | null {
  if (!expiryIso) return null;
  const expiry = new Date(expiryIso).getTime();
  const now = Date.now();
  const msRemaining = expiry - now;
  if (msRemaining <= 0) return 'Expired';
  const hours = Math.floor(msRemaining / (1000 * 60 * 60));
  const mins = Math.floor((msRemaining % (1000 * 60 * 60)) / (1000 * 60));
  if (hours >= 24) {
    const days = Math.floor(hours / 24);
    return `${days}d ${hours % 24}h`;
  }
  return `${hours}h ${mins}m`;
}

function useSecondsAgo(isoTimestamp: string | null | undefined): number | null {
  const [secs, setSecs] = useState<number | null>(null);
  useEffect(() => {
    if (!isoTimestamp) { setSecs(null); return; }
    const update = () => setSecs(Math.round((Date.now() - new Date(isoTimestamp).getTime()) / 1000));
    update();
    const id = setInterval(update, 5000);
    return () => clearInterval(id);
  }, [isoTimestamp]);
  return secs;
}

// ---------------------------------------------------------------------------
// Squeeze Bar
// ---------------------------------------------------------------------------

function SqueezeBar({ bb_width_pct, bb_width_threshold, squeeze_active }: {
  bb_width_pct: number | null | undefined;
  bb_width_threshold: number | null | undefined;
  squeeze_active: boolean | null | undefined;
}) {
  if (bb_width_pct == null || bb_width_threshold == null) {
    return <div className="text-[9px] font-mono text-zinc-600 mb-2">BB: waiting...</div>;
  }

  const ratio = Math.min(bb_width_pct / bb_width_threshold, 1);
  let barColor = 'bg-[#ff1744]';
  if (ratio < 0.5) barColor = 'bg-[#00e676]';
  else if (ratio < 0.75) barColor = 'bg-[#00c853]';
  else if (ratio < 1) barColor = 'bg-[#ffd600]';

  return (
    <div className="bg-zinc-800/40 border border-zinc-800/60 rounded p-2.5 mb-2">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[9px] font-semibold text-zinc-400 uppercase tracking-wide">BB Squeeze</span>
        <span className={cn(
          'px-1.5 py-0.5 rounded text-[8px] font-mono font-bold uppercase border',
          squeeze_active
            ? 'bg-[#00c853]/15 text-[#00c853] border-[#00c853]/30'
            : 'bg-zinc-800 text-zinc-500 border-zinc-700'
        )}>
          {squeeze_active ? 'ACTIVE' : 'WAITING'}
        </span>
      </div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-[8px] text-zinc-500">Width</span>
        <span className="text-[8px] font-mono text-zinc-300">
          {bb_width_pct.toFixed(2)}% / {bb_width_threshold}% thresh
        </span>
      </div>
      <div className="h-2 rounded-full bg-zinc-800 overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all duration-500', barColor)}
          style={{ width: `${ratio * 100}%` }}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Chain Table (CALLS or PUTS)
// ---------------------------------------------------------------------------

interface ChainEntry {
  strike: number;
  bid: number;
  ask: number;
}

function ChainTable({
  label,
  entries,
  targetStrike,
  affordableLimit,
  isCall,
  spotPrice,
}: {
  label: string;
  entries: ChainEntry[];
  targetStrike: number | null;
  affordableLimit: number;
  isCall: boolean;
  spotPrice: number | null;
}) {
  if (entries.length === 0) {
    return (
      <div className="text-[9px] font-mono text-zinc-600 py-1">
        {label}: No data
      </div>
    );
  }

  const textColor = isCall ? 'text-[#00c853]' : 'text-[#ff1744]';
  const dimColor  = isCall ? 'text-[#00c853]/60' : 'text-[#ff1744]/60';

  return (
    <div className="mb-2">
      <div className={cn('text-[9px] font-mono uppercase mb-1 font-medium', textColor)}>
        {label}
      </div>
      <table className="w-full text-[9px] font-mono">
        <thead>
          <tr className="text-zinc-600">
            <th className="text-left font-normal pb-0.5 pr-1">Strike</th>
            <th className="text-right font-normal pb-0.5 px-1">OTM%</th>
            <th className="text-right font-normal pb-0.5 px-1">Bid</th>
            <th className="text-right font-normal pb-0.5 px-1">Ask</th>
            <th className="text-right font-normal pb-0.5 px-1">Col@50x</th>
            <th className="text-right font-normal pb-0.5 pl-1">Sprd%</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => {
            const isTarget   = targetStrike != null && e.strike === targetStrike;
            const collateral = e.ask > 0 ? e.ask / OPTIONS_LEVERAGE : 0;
            const unaffordable = collateral > affordableLimit;
            const otmPct = spotPrice && spotPrice > 0
              ? Math.abs(e.strike - spotPrice) / spotPrice * 100
              : 0;
            const spreadPct = e.ask > 0 && e.bid > 0
              ? ((e.ask - e.bid) / e.ask) * 100
              : 0;

            return (
              <tr
                key={e.strike}
                className={cn(
                  'border-t border-zinc-800/30',
                  isTarget && 'bg-amber-500/10',
                  unaffordable && !isTarget && 'opacity-40',
                )}
              >
                <td className={cn(
                  'py-0.5 text-left pr-1 whitespace-nowrap',
                  isTarget ? 'text-amber-400 font-medium' : 'text-zinc-300',
                )}>
                  ${e.strike.toLocaleString()}
                  {isTarget && (
                    <span className="ml-1 px-1 py-px rounded text-[7px] bg-amber-500/20 text-amber-400 font-bold">
                      TARGET
                    </span>
                  )}
                </td>
                <td className="py-0.5 text-right px-1 text-zinc-500">
                  {otmPct.toFixed(1)}%
                </td>
                <td className={cn('py-0.5 text-right px-1', dimColor)}>
                  {fmtPrem(e.bid)}
                </td>
                <td className={cn('py-0.5 text-right px-1', textColor)}>
                  {fmtPrem(e.ask)}
                </td>
                <td className="py-0.5 text-right px-1 text-zinc-400">
                  ${collateral.toFixed(2)}
                </td>
                <td className={cn(
                  'py-0.5 text-right pl-1',
                  spreadPct > 20 ? 'text-[#ff1744]/60' : 'text-zinc-500',
                )}>
                  {spreadPct.toFixed(0)}%
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Chain Card (one per asset)
// ---------------------------------------------------------------------------

function ChainCard({ asset, state }: { asset: string; state: OptionsState | null }) {
  const scanSecsAgo = useSecondsAgo(state?.updated_at);
  const hoursRemaining = fmtHoursRemaining(state?.expiry);

  // Debug: Log options_state row for BTC to diagnose premium value issue
  console.log(`BB Squeeze Panel - ${asset} options_state row:`, state);

  if (!state) {
    return (
      <div className="bg-zinc-900/40 border border-zinc-800/50 rounded-lg p-3">
        <span className="text-sm font-medium text-zinc-500">{asset}</span>
        <span className="text-[9px] font-mono text-zinc-600 ml-2">No data</span>
      </div>
    );
  }

  const inPosition     = !!state.position_side;
  const balance        = state.balance ?? null;
  const targetStrike   = state.target_strike ?? null;
  const affordableLimit = balance != null ? balance * 0.40 : Infinity;

  // Breakout state badge
  const breakoutState = state.breakout_state ?? 'NONE';
  const breakoutDir = state.breakout_direction;
  const getBreakoutBadge = () => {
    if (breakoutState === 'DETECTED') {
      const label = breakoutDir === 'UP' ? 'DETECTED UP' : breakoutDir === 'DOWN' ? 'DETECTED DOWN' : 'DETECTED';
      const color = breakoutDir === 'UP' ? 'bg-[#00c853]/20 text-[#00c853] border-[#00c853]/40' : 
                    breakoutDir === 'DOWN' ? 'bg-[#ff1744]/20 text-[#ff1744] border-[#ff1744]/40' :
                    'bg-zinc-800 text-zinc-400 border-zinc-700';
      return { label, color };
    }
    if (breakoutState === 'CONFIRMED' || breakoutState === 'BREAKOUT_CONFIRMED') {
      return { label: 'CONFIRMED', color: 'bg-[#00c853]/20 text-[#00c853] border-[#00c853]/40' };
    }
    if (breakoutState === 'FAKEOUT' || breakoutState === 'BREAKOUT_FAKEOUT') {
      return { label: 'FAKEOUT', color: 'bg-[#ff6d00]/20 text-[#ff6d00] border-[#ff6d00]/40' };
    }
    if (breakoutState === 'BREAKOUT_NO_FILL') {
      return { label: 'NO FILL', color: 'bg-zinc-800 text-zinc-500 border-zinc-700' };
    }
    return { label: 'NONE', color: 'bg-zinc-800 text-zinc-600 border-zinc-700' };
  };
  const breakoutBadge = getBreakoutBadge();

  return (
    <div className="bg-zinc-900/40 border border-zinc-800/50 rounded-lg p-3">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-white">{asset}</span>
          <span className="text-[10px] font-mono text-zinc-500">{fmtSpot(state.spot_price)}</span>
        </div>
        <div className="text-right">
          {hoursRemaining && (
            <span className="text-[9px] font-mono text-zinc-400">
              Exp: {hoursRemaining}
            </span>
          )}
        </div>
      </div>

      {/* 1. Compression progress bar */}
      <SqueezeBar
        bb_width_pct={state.bb_width_pct}
        bb_width_threshold={state.bb_width_threshold}
        squeeze_active={state.squeeze_active}
      />

      {/* 2. Squeeze active message */}
      {state.squeeze_active && (
        <div className="mb-2 px-2 py-1.5 bg-[#00c853]/10 border border-[#00c853]/30 rounded">
          <span className="text-[10px] font-medium text-[#00c853]">
            Squeeze active! Ready to enter.
          </span>
        </div>
      )}

      {/* 3. CALL and PUT premium boxes - price only */}
      <div className="grid grid-cols-2 gap-2 mb-2">
        <div className="bg-zinc-800/40 border border-zinc-800/60 rounded p-2">
          <div className="text-[7px] text-[#00c853]/60 uppercase mb-0.5">Call</div>
          <div className="text-[14px] font-mono font-semibold text-zinc-200">
            {fmtPrem(state.call_premium)}
          </div>
        </div>
        <div className="bg-zinc-800/40 border border-zinc-800/60 rounded p-2">
          <div className="text-[7px] text-[#ff1744]/60 uppercase mb-0.5">Put</div>
          <div className="text-[14px] font-mono font-semibold text-zinc-200">
            {fmtPrem(state.put_premium)}
          </div>
        </div>
      </div>

      {/* 4. Position Active bar */}
      {inPosition && (
        <div className="mb-2 px-2.5 py-2 bg-[#7c4dff]/10 border border-[#7c4dff]/30 rounded">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-[#7c4dff] animate-pulse" />
            <span className="text-[10px] font-medium text-[#7c4dff]">
              Position Active: {state.position_side?.toUpperCase()} ${state.position_strike?.toLocaleString()}
            </span>
          </div>
        </div>
      )}

      {/* 5. Breakout state row */}
      <div className="flex items-center justify-between mb-2 px-2 py-1.5 bg-zinc-800/30 rounded">
        <span className="text-[9px] text-zinc-500 uppercase tracking-wide">Breakout</span>
        <span className={cn(
          'px-2 py-0.5 rounded text-[9px] font-mono font-bold uppercase border',
          breakoutBadge.color
        )}>
          {breakoutBadge.label}
        </span>
      </div>

      {/* 6. Strike being watched */}
      {state.atm_strike != null && state.atm_strike > 0 && (
        <div className="mb-2 px-2 py-1.5 bg-zinc-800/30 rounded">
          <span className="text-[9px] text-zinc-500 uppercase tracking-wide">Strike Watching</span>
          <span className="ml-2 text-[11px] font-mono font-semibold text-amber-400">
            ATM: ${state.atm_strike.toLocaleString()}
          </span>
        </div>
      )}

      {/* 7. Last scan timestamp */}
      {scanSecsAgo != null && (
        <div className="mb-3 text-[8px] font-mono text-zinc-600 text-right">
          Last scan: {scanSecsAgo < 60 ? `${scanSecsAgo}s` : `${Math.round(scanSecsAgo / 60)}m`} ago
        </div>
      )}

      {/* CALLS chain */}
      <ChainTable
        label="CALLS"
        entries={state.chain_calls ?? []}
        targetStrike={targetStrike}
        affordableLimit={affordableLimit}
        isCall={true}
        spotPrice={state.spot_price}
      />

      {/* PUTS chain */}
      <ChainTable
        label="PUTS"
        entries={state.chain_puts ?? []}
        targetStrike={targetStrike}
        affordableLimit={affordableLimit}
        isCall={false}
        spotPrice={state.spot_price}
      />

      {balance != null && (
        <div className="text-[9px] font-mono text-zinc-600 mt-2 pt-1.5 border-t border-zinc-800/30 text-right">
          Delta balance: ${balance.toFixed(2)}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Panel
// ---------------------------------------------------------------------------

export function OptionsChainPanel() {
  const { optionsState } = useSupabase();

  const pairData = useMemo(() => {
    return OPTIONS_ASSETS.map(asset => {
      const pair  = `${asset}/USD:USD`;
      const state = optionsState.find(s => s.pair === pair) ?? null;
      return { asset, state };
    });
  }, [optionsState]);

  return (
    <div className="bg-[#0d1117] border border-zinc-800 rounded-xl p-3 md:p-5">
      <h3 className="text-sm font-medium text-zinc-400 uppercase tracking-wider mb-4">
        Options Chain
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {pairData.map(pd => (
          <ChainCard key={pd.asset} asset={pd.asset} state={pd.state} />
        ))}
      </div>
    </div>
  );
}

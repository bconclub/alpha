'use client';

import { useMemo } from 'react';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import { cn } from '@/lib/utils';
import type { OptionsState } from '@/lib/types';

const OPTIONS_ASSETS = ['BTC', 'ETH'] as const;
const OPTIONS_LEVERAGE = 50;

function fmtSpot(v: number | null): string {
  if (v == null) return '—';
  return `$${v.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
}

function fmtPrem(v: number): string {
  if (v <= 0) return '—';
  return `$${v.toFixed(2)}`;
}

// ---------------------------------------------------------------------------
// Candle Momentum Bar
// ---------------------------------------------------------------------------

function CandleMomentumBar({ momentum }: { momentum: OptionsState['candle_momentum'] }) {
  if (!momentum) {
    return (
      <div className="text-[9px] font-mono text-zinc-600 mb-2">
        Candles: waiting...
      </div>
    );
  }

  const { count, total, cum_pct, direction, passed } = momentum;

  // Build blocks: first `count` are directional color, rest gray
  const blocks = Array.from({ length: total }, (_, i) => {
    if (i < count) {
      return direction === 'long' ? 'bg-[#00c853]' : 'bg-[#ff1744]';
    }
    return 'bg-zinc-700';
  });

  return (
    <div className="flex items-center gap-2 mb-2">
      <span className="text-[9px] text-zinc-500 uppercase w-14 shrink-0">Candles</span>
      <div className={cn('flex gap-0.5', passed && 'animate-pulse')}>
        {blocks.map((color, i) => (
          <div key={i} className={cn('w-4 h-3 rounded-sm', color)} />
        ))}
      </div>
      <span className="text-[9px] font-mono text-zinc-500">
        {count}/{total}
      </span>
      <span className={cn(
        'text-[10px] font-mono',
        cum_pct >= 0 ? 'text-[#00c853]' : 'text-[#ff1744]',
      )}>
        {cum_pct >= 0 ? '+' : ''}{cum_pct.toFixed(2)}%
      </span>
      <span className={cn(
        'px-1.5 py-0.5 rounded text-[8px] font-bold uppercase',
        passed
          ? 'bg-[#00c853]/15 text-[#00c853] border border-[#00c853]/30'
          : 'bg-zinc-800 text-zinc-500 border border-zinc-700',
      )}>
        {passed ? 'PASS' : 'FAIL'}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Bot State Badge
// ---------------------------------------------------------------------------

function BotStateBadge({ state }: { state: string }) {
  let label = state;
  let colorClass = 'bg-zinc-800 text-zinc-400 border-zinc-700';

  if (state === 'scanning') {
    label = 'SCANNING';
  } else if (state === 'ready') {
    label = 'READY';
    colorClass = 'bg-[#00c853]/15 text-[#00c853] border-[#00c853]/30';
  } else if (state === 'in_position') {
    label = 'IN POSITION';
    colorClass = 'bg-[#7c4dff]/15 text-[#7c4dff] border-[#7c4dff]/30';
  } else if (state.startsWith('blocked:')) {
    const parts = state.replace('blocked:', '').split(':');
    const reason = parts[0].replace(/_/g, ' ');
    const timer = parts[1] ?? null;
    label = timer ? `BLOCKED: ${reason} (${timer})` : `BLOCKED: ${reason}`;
    colorClass = 'bg-[#ff1744]/10 text-[#ff1744]/80 border-[#ff1744]/20';
  }

  return (
    <div className="mb-2">
      <span className={cn(
        'inline-flex items-center px-2 py-0.5 rounded text-[9px] font-mono font-medium border',
        colorClass,
      )}>
        {label}
      </span>
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
  const dimColor = isCall ? 'text-[#00c853]/60' : 'text-[#ff1744]/60';

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
            const isTarget = targetStrike != null && e.strike === targetStrike;
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
  if (!state) {
    return (
      <div className="bg-zinc-900/40 border border-zinc-800/50 rounded-lg p-3">
        <span className="text-sm font-medium text-zinc-500">{asset}</span>
        <span className="text-[9px] font-mono text-zinc-600 ml-2">No data</span>
      </div>
    );
  }

  const balance = state.balance ?? null;
  const momentum = state.candle_momentum;
  const botState = state.bot_state ?? 'scanning';
  const targetStrike = state.target_strike ?? null;
  const affordableLimit = balance != null ? balance * 0.40 : Infinity;

  return (
    <div className="bg-zinc-900/40 border border-zinc-800/50 rounded-lg p-3">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-white">{asset}</span>
          <span className="text-[10px] font-mono text-zinc-500">
            {fmtSpot(state.spot_price)}
          </span>
        </div>
        <span className="text-[9px] font-mono text-zinc-600 truncate max-w-[160px]">
          {state.expiry_label ?? '—'}
        </span>
      </div>

      {/* Candle Momentum */}
      <CandleMomentumBar momentum={momentum} />

      {/* Bot State */}
      <BotStateBadge state={botState} />

      {/* CALLS Table */}
      <ChainTable
        label="CALLS"
        entries={state.chain_calls ?? []}
        targetStrike={targetStrike}
        affordableLimit={affordableLimit}
        isCall={true}
        spotPrice={state.spot_price}
      />

      {/* PUTS Table */}
      <ChainTable
        label="PUTS"
        entries={state.chain_puts ?? []}
        targetStrike={targetStrike}
        affordableLimit={affordableLimit}
        isCall={false}
        spotPrice={state.spot_price}
      />

      {/* Balance Footer */}
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
      const pair = `${asset}/USD:USD`;
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

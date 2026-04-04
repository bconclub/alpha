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
// BB Squeeze Signals Panel (replaces candle momentum)
// ---------------------------------------------------------------------------

function BBSqueezeSignalsPanel({ signals }: { signals: OptionsState['signals_panel'] }) {
  if (!signals) {
    return (
      <div className="text-[9px] font-mono text-zinc-600 mb-2">
        BB Squeeze: waiting...
      </div>
    );
  }

  const {
    bb_width_pct,
    bb_width_threshold,
    squeeze_status,
    bb_position,
    direction_bias,
    premium_current_ask,
    premium_cheap_threshold,
    last_action,
    squeeze_duration_candles,
  } = signals;

  const isSqueezeActive = squeeze_status === 'ACTIVE';
  const widthRatio = Math.min((bb_width_pct / bb_width_threshold) * 100, 100);
  
  // Determine color based on how tight the squeeze is
  let widthColor = 'bg-[#ff1744]';  // Wide/red
  if (bb_width_pct < bb_width_threshold * 0.5) widthColor = 'bg-[#00e676]';  // Very tight
  else if (bb_width_pct < bb_width_threshold * 0.75) widthColor = 'bg-[#00c853]';  // Tight
  else if (bb_width_pct < bb_width_threshold) widthColor = 'bg-[#ffd600]';  // Getting tight

  // BB position indicator (0 = lower band, 1 = upper band)
  const positionPct = Math.max(0, Math.min(100, bb_position * 100));
  
  // Direction bias colors
  const biasColor = direction_bias === 'CALL' 
    ? 'text-[#00c853]' 
    : direction_bias === 'PUT' 
      ? 'text-[#ff1744]' 
      : 'text-zinc-400';
  const biasBg = direction_bias === 'CALL' 
    ? 'bg-[#00c853]/15 border-[#00c853]/30' 
    : direction_bias === 'PUT' 
      ? 'bg-[#ff1744]/15 border-[#ff1744]/30' 
      : 'bg-zinc-800/50 border-zinc-700';

  // Last action color
  const actionColor = last_action === 'SQUEEZE_FILL' 
    ? 'text-[#00c853]' 
    : last_action === 'SQUEEZE_NO_FILL' 
      ? 'text-[#ff1744]' 
      : 'text-zinc-500';

  return (
    <div className="bg-zinc-800/40 border border-zinc-800/60 rounded p-2.5 mb-2.5">
      {/* Header: Title + Status Badge */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-[9px] font-semibold text-zinc-400 uppercase tracking-wide">BB Squeeze</span>
        <span className={cn(
          'px-1.5 py-0.5 rounded text-[8px] font-mono font-bold uppercase border',
          isSqueezeActive 
            ? 'bg-[#00c853]/15 text-[#00c853] border-[#00c853]/30' 
            : 'bg-zinc-800 text-zinc-500 border-zinc-700'
        )}>
          {squeeze_status}
        </span>
      </div>

      {/* BB Width % with threshold bar */}
      <div className="mb-2.5">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[8px] text-zinc-500">BB Width</span>
          <span className="text-[8px] font-mono text-zinc-300">{bb_width_pct.toFixed(2)}% / {bb_width_threshold}% thresh</span>
        </div>
        <div className="relative h-2 rounded-full bg-zinc-800 overflow-hidden">
          <div
            className={cn('absolute inset-y-0 left-0 rounded-full transition-all duration-500', widthColor)}
            style={{ width: `${widthRatio}%` }}
          />
          {/* Threshold marker */}
          <div 
            className="absolute inset-y-0 w-0.5 bg-white/50"
            style={{ left: '100%' }}
          />
        </div>
      </div>

      {/* BB Position indicator (where price sits in bands) */}
      <div className="mb-2.5">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[8px] text-zinc-500">BB Position</span>
          <span className="text-[8px] font-mono text-zinc-300">{bb_position.toFixed(2)}</span>
        </div>
        <div className="relative h-1.5 rounded-full bg-gradient-to-r from-[#00c853]/30 via-zinc-700 to-[#ff1744]/30 overflow-hidden">
          <div 
            className="absolute top-1/2 w-2 h-2 rounded-full bg-white shadow-[0_0_4px_rgba(255,255,255,0.5)]"
            style={{ left: `${positionPct}%`, transform: `translateX(-50%) translateY(-50%)` }}
          />
        </div>
        <div className="flex justify-between text-[7px] text-zinc-600 mt-0.5">
          <span>Lower</span>
          <span>Middle</span>
          <span>Upper</span>
        </div>
      </div>

      {/* Direction Bias */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-[8px] text-zinc-500">Direction Bias</span>
        <span className={cn(
          'px-2 py-0.5 rounded text-[9px] font-mono font-bold border',
          biasBg, biasColor
        )}>
          {direction_bias}
        </span>
      </div>

      {/* Premium: current ask vs cheap threshold */}
      {(premium_current_ask != null || premium_cheap_threshold != null) && (
        <div className="mb-2 p-1.5 bg-zinc-900/50 rounded">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[8px] text-zinc-500">Premium Ask</span>
            <span className="text-[9px] font-mono text-zinc-300">
              ${premium_current_ask?.toFixed(4) ?? '—'}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[8px] text-zinc-500">Cheap Threshold</span>
            <span className="text-[9px] font-mono text-[#00c853]">
              ${premium_cheap_threshold?.toFixed(4) ?? '—'}
            </span>
          </div>
          {premium_current_ask != null && premium_cheap_threshold != null && (
            <div className="mt-1 text-[7px] font-mono">
              {premium_current_ask <= premium_cheap_threshold ? (
                <span className="text-[#00c853]">✓ Below threshold — cheap entry</span>
              ) : (
                <span className="text-[#ffd600]">Waiting for cheap entry...</span>
              )}
            </div>
          )}
        </div>
      )}

      {/* Squeeze duration */}
      <div className="flex items-center justify-between text-[8px] font-mono text-zinc-500 mb-1.5">
        <span>Squeeze duration</span>
        <span>{squeeze_duration_candles} candles</span>
      </div>

      {/* Last action */}
      <div className="flex items-center justify-between text-[8px]">
        <span className="text-zinc-500">Last action</span>
        <span className={cn('font-mono font-medium', actionColor)}>
          {last_action}
        </span>
      </div>
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

      {/* BB Squeeze Signals Panel */}
      <BBSqueezeSignalsPanel signals={state.signals_panel} />

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

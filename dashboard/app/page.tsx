'use client';

import { useSupabase } from '@/components/providers/SupabaseProvider';
import { LiveStatusBar } from '@/components/dashboard/LiveStatusBar';
import { MarketOverview } from '@/components/dashboard/MarketOverview';
import { LivePositions } from '@/components/dashboard/LivePositions';
import { PerformancePanel } from '@/components/dashboard/PerformancePanel';
import { OptionsChainPanel } from '@/components/dashboard/OptionsChainPanel';
import { OptionsTracker } from '@/components/dashboard/OptionsTracker';

function LiveInfoBar() {
  const { isConnected, trades, botStatus } = useSupabase();

  const botState = botStatus?.bot_state ?? (isConnected ? 'running' : 'paused');
  const openPositions = botStatus?.open_positions ?? 0;
  const leverageLevel = botStatus?.leverage ?? botStatus?.leverage_level ?? 1;
  const shortingEnabled = botStatus?.shorting_enabled ?? false;
  const uptimeSeconds = botStatus?.uptime_seconds ?? 0;

  const uptimeLabel = (() => {
    if (uptimeSeconds <= 0) return null;
    const h = Math.floor(uptimeSeconds / 3600);
    const m = Math.floor((uptimeSeconds % 3600) / 60);
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
  })();

  const closedTrades = trades.filter((t) => t.status === 'closed');

  const pills: { label: string; color: string; pulse?: boolean }[] = [
    {
      label: botState === 'running' ? 'Live' : 'Paused',
      color: botState === 'running' ? 'bg-[#00c853]/15 text-[#00c853] border-[#00c853]/30' : 'bg-[#ffd600]/15 text-[#ffd600] border-[#ffd600]/30',
      pulse: botState === 'running',
    },
  ];

  if (openPositions > 0) {
    pills.push({ label: `${openPositions} Open`, color: 'bg-amber-500/15 text-amber-400 border-amber-500/30' });
  }

  pills.push({ label: `${leverageLevel}x Lev`, color: 'bg-zinc-800/80 text-[#ffd600] border-zinc-700' });

  if (shortingEnabled) {
    pills.push({ label: 'Short ON', color: 'bg-[#00c853]/10 text-[#00c853]/80 border-[#00c853]/20' });
  }

  if (closedTrades.length > 0) {
    pills.push({ label: `${closedTrades.length} Trades`, color: 'bg-zinc-800/80 text-zinc-300 border-zinc-700' });
  }

  if (uptimeLabel) {
    pills.push({ label: `Up ${uptimeLabel}`, color: 'bg-zinc-800/80 text-zinc-400 border-zinc-700' });
  }

  return (
    <div className="overflow-x-auto scrollbar-hide -mx-1 px-1">
      <div className="flex items-center gap-1.5 min-w-max">
        {pills.map((pill, i) => (
          <span
            key={i}
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-semibold border whitespace-nowrap ${pill.color}`}
          >
            {i === 0 && (
              <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${botState === 'running' ? 'bg-[#00c853] animate-pulse' : 'bg-[#ffd600]'}`} />
            )}
            {pill.label}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <div className="space-y-3 md:space-y-4">
      {/* Live status pills */}
      <LiveInfoBar />

      {/* 1. Live Status Bar — full width */}
      <LiveStatusBar />

      {/* 2. Market Overview + Live Positions | Options Signals */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-3 space-y-2">
          <MarketOverview />
          <LivePositions />
        </div>
        <div className="lg:col-span-2">
          <OptionsTracker />
        </div>
      </div>

      {/* Options Chain — full width */}
      <OptionsChainPanel />

      {/* 5. Performance — full width, collapsible */}
      <PerformancePanel />
    </div>
  );
}

'use client';

import { StatusHero } from '@/components/dashboard/StatusHero';
import { LivePositions } from '@/components/dashboard/LivePositions';
import { StrategyScanner } from '@/components/dashboard/StrategyScanner';
import { RecentTrades } from '@/components/dashboard/RecentTrades';
import { MarketOverview } from '@/components/dashboard/MarketOverview';
import { MarketSentiment } from '@/components/dashboard/MarketSentiment';
import { BottomStats } from '@/components/dashboard/BottomStats';

// Home reads top-down in the order you'd ask the questions:
//   1. Is it running, and how much money is there?   (StatusHero)
//   2. What is it holding right now?                 (LivePositions, hidden when flat)
//   3. What will it do next / what did it just do?   (Scanner + RecentTrades)
//   4. Market context and longer-run performance.    (Market*, BottomStats)
export default function DashboardPage() {
  return (
    <div className="space-y-4 pb-6">
      <StatusHero />
      <LivePositions />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
        <div className="lg:col-span-2 lg:order-2">
          <StrategyScanner />
        </div>
        <div className="space-y-4 lg:col-span-3 lg:order-1">
          <RecentTrades />
          <BottomStats />
          <MarketOverview />
          <MarketSentiment />
        </div>
      </div>
    </div>
  );
}

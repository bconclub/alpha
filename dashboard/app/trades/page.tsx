'use client';

import { useSupabase } from '@/components/providers/SupabaseProvider';
import { ExchangeToggle } from '@/components/dashboard/ExchangeToggle';
import TradeTable from '@/components/tables/TradeTable';

export default function TradesPage() {
  const { filteredTrades } = useSupabase();

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-4">
        <h1 className="text-xl md:text-2xl font-bold tracking-tight text-white">
          Trade History
        </h1>
        <ExchangeToggle />
      </div>

      <TradeTable trades={filteredTrades} />
    </div>
  );
}

'use client';

import { useState } from 'react';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import { ExchangeToggle } from '@/components/dashboard/ExchangeToggle';
import TradeTable from '@/components/tables/TradeTable';
import { getSupabase } from '@/lib/supabase';

export default function TradesPage() {
  const { filteredTrades } = useSupabase();
  const [reconciling, setReconciling] = useState(false);
  const [reconcileResult, setReconcileResult] = useState<string | null>(null);

  const handleReconcile = async () => {
    const sb = getSupabase();
    if (!sb) return;

    setReconciling(true);
    setReconcileResult(null);

    try {
      // Insert command for the bot to pick up
      const { data, error } = await sb
        .from('bot_commands')
        .insert({
          command: 'reconcile',
          params: { hours: 24 },
          status: 'pending',
        })
        .select('id')
        .single();

      if (error) throw error;
      const cmdId = data?.id;

      // Poll for completion (bot polls every 5s, give it up to 60s)
      let attempts = 0;
      while (attempts < 12) {
        await new Promise((r) => setTimeout(r, 5000));
        attempts++;

        const { data: cmd } = await sb
          .from('bot_commands')
          .select('status, result')
          .eq('id', cmdId)
          .single();

        if (cmd?.status === 'executed' || cmd?.status === 'done') {
          setReconcileResult(cmd.result || 'Reconciliation complete');
          break;
        }
      }

      if (attempts >= 12) {
        setReconcileResult('Timeout — bot may still be processing');
      }
    } catch (err) {
      setReconcileResult(`Error: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setReconciling(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-4">
        <h1 className="text-xl md:text-2xl font-bold tracking-tight text-white">
          Trade History
        </h1>
        <ExchangeToggle />
        <button
          onClick={handleReconcile}
          disabled={reconciling}
          className={`ml-auto px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            reconciling
              ? 'bg-zinc-700 text-zinc-400 cursor-not-allowed'
              : 'bg-blue-600 hover:bg-blue-500 text-white'
          }`}
        >
          {reconciling ? (
            <span className="flex items-center gap-2">
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Reconciling...
            </span>
          ) : (
            'Reconcile with Exchange'
          )}
        </button>
      </div>

      {reconcileResult && (
        <div className={`px-4 py-3 rounded-lg text-sm ${
          reconcileResult.startsWith('Error') || reconcileResult.startsWith('Timeout')
            ? 'bg-red-900/50 text-red-300 border border-red-700'
            : 'bg-green-900/50 text-green-300 border border-green-700'
        }`}>
          {reconcileResult}
        </div>
      )}

      <TradeTable trades={filteredTrades} />
    </div>
  );
}

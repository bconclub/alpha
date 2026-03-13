'use client';

import { useState } from 'react';
import { useSupabase } from '@/components/providers/SupabaseProvider';
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
        })
        .select('id')
        .single();

      if (error) throw new Error(error.message || 'Insert failed');
      const cmdId = data?.id;
      if (!cmdId) throw new Error('No command ID returned');

      // Poll for completion (bot polls every 5s, give it up to 90s)
      let attempts = 0;
      let done = false;
      while (attempts < 18) {
        await new Promise((r) => setTimeout(r, 5000));
        attempts++;

        const { data: cmd } = await sb
          .from('bot_commands')
          .select('executed, result')
          .eq('id', cmdId)
          .single();

        if (cmd?.executed) {
          setReconcileResult(cmd.result || 'Reconciliation complete');
          done = true;
          break;
        }
      }

      if (!done) {
        setReconcileResult('Timeout — bot may still be processing');
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : JSON.stringify(err);
      setReconcileResult(`Error: ${msg}`);
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

        {/* Reconcile icon button */}
        <button
          onClick={handleReconcile}
          disabled={reconciling}
          title="Reconcile with Delta Exchange"
          className={`ml-auto p-2 rounded-lg transition-colors ${
            reconciling
              ? 'text-zinc-500 cursor-not-allowed'
              : 'text-zinc-400 hover:text-white hover:bg-zinc-800'
          }`}
        >
          {reconciling ? (
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          ) : (
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0118.8-4.3M22 12.5a10 10 0 01-18.8 4.3" />
            </svg>
          )}
        </button>
      </div>

      {reconcileResult && (
        <div
          className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-mono ${
            reconcileResult.startsWith('Error') || reconcileResult.startsWith('Timeout')
              ? 'bg-red-900/30 text-red-400 border border-red-800/50'
              : 'bg-green-900/30 text-green-400 border border-green-800/50'
          }`}
        >
          <span className="flex-1">{reconcileResult}</span>
          <button
            onClick={() => setReconcileResult(null)}
            className="text-zinc-500 hover:text-zinc-300 shrink-0"
          >
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

      <TradeTable trades={filteredTrades} />
    </div>
  );
}

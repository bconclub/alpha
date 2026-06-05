import { NextResponse } from 'next/server';
import { getServerSupabase } from '@/lib/supabase-server';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

export async function GET() {
  const supabase = getServerSupabase();
  if (!supabase) {
    return NextResponse.json(
      { error: 'Server Supabase client is not configured.' },
      { status: 500 },
    );
  }

  const { data, error } = await supabase
    .from('paper_futures_trades')
    .select('*')
    .order('opened_at', { ascending: false })
    .limit(200);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  const { data: statusRows } = await supabase
    .from('bot_status')
    .select('bot_state,is_running,is_paused,uptime_seconds,timestamp,created_at,inr_usd_rate')
    .order('created_at', { ascending: false })
    .limit(1);

  return NextResponse.json({
    rows: data ?? [],
    botStatus: statusRows?.[0] ?? null,
    paperAccountUsd: 50,
  });
}

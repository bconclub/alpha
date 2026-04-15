import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

/**
 * POST /api/reconcile
 *
 * Queues a smart_reconcile command for the bot to execute.
 * The bot polls the bot_commands table every ~5s.
 *
 * Body: {
 *   date_from?: string   // ISO date (default: 24h ago)
 *   date_to?: string     // ISO date (default: now)
 *   dry_run?: boolean    // default: true
 * }
 *
 * Returns: { command_id: number, message: string }
 */

export const dynamic = 'force-dynamic';

export async function POST(req: NextRequest) {
  try {
    const body = await req.json().catch(() => ({}));
    const { date_from, date_to, dry_run = true } = body;

    const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const key = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

    if (!url || !key) {
      return NextResponse.json({ error: 'Supabase credentials not configured' }, { status: 500 });
    }

    const supabase = createClient(url, key);

    const params: Record<string, any> = { dry_run };
    if (date_from) params.date_from = date_from;
    if (date_to) params.date_to = date_to;

    const { data, error } = await supabase
      .from('bot_commands')
      .insert({ command: 'smart_reconcile', params })
      .select('id')
      .single();

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    return NextResponse.json({
      command_id: data?.id,
      message: `Smart reconcile command queued (dry_run=${dry_run}). Bot will process shortly.`,
    });
  } catch (err: any) {
    return NextResponse.json({ error: err?.message || 'Unexpected error' }, { status: 500 });
  }
}

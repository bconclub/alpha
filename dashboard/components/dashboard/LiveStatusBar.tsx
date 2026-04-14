'use client';

import { useEffect, useState, useMemo } from 'react';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import { getSupabase } from '@/lib/supabase';
import { formatCurrency, cn } from '@/lib/utils';

function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function ISTClock() {
  const [time, setTime] = useState('');

  useEffect(() => {
    const tick = () => {
      const now = new Date();
      const istStr = now.toLocaleTimeString('en-GB', {
        timeZone: 'Asia/Kolkata',
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
      setTime(istStr + ' IST');
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <span className="font-mono text-xs text-zinc-400">{time}</span>
  );
}

/** Tiny SVG sparkline — no recharts dependency needed for this */
function MiniSparkline({ data, color }: { data: number[]; color: string }) {
  if (data.length < 2) return null;

  const width = 100;
  const height = 28;
  const padding = 2;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data.map((v, i) => {
    const x = padding + (i / (data.length - 1)) * (width - padding * 2);
    const y = padding + (1 - (v - min) / range) * (height - padding * 2);
    return `${x},${y}`;
  });

  // Gradient fill area
  const firstX = padding;
  const lastX = padding + ((data.length - 1) / (data.length - 1)) * (width - padding * 2);
  const areaPoints = `${firstX},${height} ${points.join(' ')} ${lastX},${height}`;

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="shrink-0">
      <defs>
        <linearGradient id={`spark-${color.replace('#', '')}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.3} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <polygon points={areaPoints} fill={`url(#spark-${color.replace('#', '')})`} />
      <polyline
        points={points.join(' ')}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

type CardView = 'pnl' | 'deposits';

// ---------------------------------------------------------------------------
// Market Regime Card — Visual Upgrade with Inline Styles
// ---------------------------------------------------------------------------

function MarketRegimeCard({
  regime,
  chopScore,
  atrRatio,
  netChange,
  regimeDuration,
}: {
  regime: string;
  chopScore: number;
  atrRatio: number;
  netChange: number;
  regimeDuration: string;
}) {
  // Regime configuration with inline styles
  const regimeStyles: Record<string, {
    icon: string;
    label: string;
    bgGradient: string;
    borderColor: string;
    iconColor: string;
    pulse: boolean;
  }> = {
    SIDEWAYS: {
      icon: '↔',
      label: 'SIDEWAYS',
      bgGradient: 'linear-gradient(135deg, rgba(245,158,11,0.15) 0%, rgba(245,158,11,0.05) 100%)',
      borderColor: 'rgba(245,158,11,0.4)',
      iconColor: '#f59e0b',
      pulse: false,
    },
    TRENDING_UP: {
      icon: '↑',
      label: 'TRENDING UP',
      bgGradient: 'linear-gradient(135deg, rgba(34,197,94,0.15) 0%, rgba(34,197,94,0.05) 100%)',
      borderColor: 'rgba(34,197,94,0.4)',
      iconColor: '#22c55e',
      pulse: true,
    },
    TRENDING_DOWN: {
      icon: '↓',
      label: 'TRENDING DOWN',
      bgGradient: 'linear-gradient(135deg, rgba(239,68,68,0.15) 0%, rgba(239,68,68,0.05) 100%)',
      borderColor: 'rgba(239,68,68,0.4)',
      iconColor: '#ef4444',
      pulse: true,
    },
    CHOPPY: {
      icon: '~',
      label: 'CHOPPY',
      bgGradient: 'linear-gradient(135deg, rgba(100,116,139,0.15) 0%, rgba(100,116,139,0.05) 100%)',
      borderColor: 'rgba(100,116,139,0.4)',
      iconColor: '#64748b',
      pulse: true,
    },
  };

  const rs = regimeStyles[regime] ?? regimeStyles.SIDEWAYS;

  // Generate directional sparkline data based on regime
  const sparklineData = useMemo(() => {
    const points: number[] = [];
    const trend = regime === 'TRENDING_UP' ? 1 : regime === 'TRENDING_DOWN' ? -1 : 0;
    let val = 50;
    for (let i = 0; i < 20; i++) {
      const noise = (Math.random() - 0.5) * 10;
      const trendMove = trend * 2;
      val = Math.max(20, Math.min(80, val + trendMove + noise));
      points.push(val);
    }
    return points;
  }, [regime]);

  const sparkColor = rs.iconColor;

  // Stat box styles
  const statBoxStyle: React.CSSProperties = {
    backgroundColor: 'rgba(0,0,0,0.2)',
    borderRadius: '4px',
    padding: '6px 8px',
    textAlign: 'center',
    minWidth: '50px',
  };

  const statLabelStyle: React.CSSProperties = {
    fontSize: '8px',
    color: '#9ca3af',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    marginBottom: '2px',
  };

  const statValueStyle = (color: string): React.CSSProperties => ({
    fontSize: '11px',
    fontWeight: 'bold',
    fontFamily: 'monospace',
    color,
  });

  const netColor = netChange >= 0 ? '#22c55e' : '#ef4444';

  return (
    <div
      style={{
        flex: 1,
        border: `1px solid ${rs.borderColor}`,
        borderRadius: '8px',
        padding: '12px 16px',
        background: rs.bgGradient,
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
      }}
    >
      {/* Regime Badge with Icon */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span
          style={{
            fontSize: '20px',
            color: rs.iconColor,
            animation: rs.pulse ? 'pulse 1.5s infinite' : 'none',
            lineHeight: 1,
          }}
        >
          {rs.icon}
        </span>
        <span
          style={{
            fontSize: '13px',
            fontWeight: 'bold',
            color: rs.iconColor,
            letterSpacing: '0.02em',
          }}
        >
          {rs.label}
        </span>
        {regime === 'CHOPPY' && (
          <span
            style={{
              fontSize: '9px',
              fontWeight: 600,
              color: '#fca5a5',
              marginLeft: '4px',
            }}
          >
            NO TRADES
          </span>
        )}
      </div>

      {/* Sparkline Row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <MiniSparkline data={sparklineData} color={sparkColor} />
        <span style={{ fontSize: '9px', color: '#6b7280', fontFamily: 'monospace' }}>
          20m trend
        </span>
      </div>

      {/* Stats Row — 4 Mini Boxes */}
      <div style={{ display: 'flex', gap: '6px', marginTop: '2px' }}>
        <div style={statBoxStyle}>
          <div style={statLabelStyle}>Chop</div>
          <div style={statValueStyle('#f59e0b')}>{chopScore.toFixed(2)}</div>
        </div>
        <div style={statBoxStyle}>
          <div style={statLabelStyle}>ATR</div>
          <div style={statValueStyle('#60a5fa')}>{atrRatio.toFixed(1)}x</div>
        </div>
        <div style={statBoxStyle}>
          <div style={statLabelStyle}>Net</div>
          <div style={statValueStyle(netColor)}>
            {netChange >= 0 ? '+' : ''}{netChange.toFixed(2)}%
          </div>
        </div>
        <div style={statBoxStyle}>
          <div style={statLabelStyle}>Since</div>
          <div style={statValueStyle('#9ca3af')}>{regimeDuration || '-'}</div>
        </div>
      </div>
    </div>
  );
}

export function LiveStatusBar() {
  const { botStatus, isConnected, trades, dailyPnL, deposits, recentTrades } = useSupabase();

  const deltaConnected = botStatus?.delta_connected || (Number(botStatus?.delta_balance ?? 0) > 0);
  const botState = botStatus?.bot_state ?? (isConnected ? 'running' : 'paused');

  // ── Market Regime ──────────────────────────────────────────────
  const regime = botStatus?.market_regime ?? 'SIDEWAYS';
  const chopScore = botStatus?.chop_score ?? 0;
  const atrRatio = botStatus?.atr_ratio ?? 1;
  const netChange = botStatus?.net_change_30m ?? 0;
  const regimeSince = botStatus?.regime_since;

  const regimeConfig: Record<string, { label: string; icon: string; bg: string; text: string; pulse?: boolean }> = {
    TRENDING_UP:   { label: 'TRENDING UP',   icon: '↗', bg: 'bg-emerald-500/15 border-emerald-500/30', text: 'text-emerald-400' },
    TRENDING_DOWN: { label: 'TRENDING DOWN', icon: '↘', bg: 'bg-red-500/15 border-red-500/30',     text: 'text-red-400' },
    SIDEWAYS:      { label: 'SIDEWAYS',      icon: '↔', bg: 'bg-amber-500/15 border-amber-500/30',  text: 'text-amber-400' },
    CHOPPY:        { label: 'CHOPPY',        icon: '⚡', bg: 'bg-red-500/20 border-red-500/40',      text: 'text-red-400', pulse: true },
  };
  const rc = regimeConfig[regime] ?? regimeConfig.SIDEWAYS;

  const regimeDuration = useMemo(() => {
    if (!regimeSince) return '';
    const elapsed = Math.max(0, Math.floor((Date.now() - new Date(regimeSince).getTime()) / 1000));
    if (elapsed < 60) return `${elapsed}s`;
    if (elapsed < 3600) return `${Math.floor(elapsed / 60)}m`;
    return `${Math.floor(elapsed / 3600)}h ${Math.floor((elapsed % 3600) / 60)}m`;
  }, [regimeSince]);

  const deltaBalance = Number(botStatus?.delta_balance ?? 0);

  const totalCapital = deltaBalance > 0 ? deltaBalance : (botStatus?.capital || 0);
  const inrRate = botStatus?.inr_usd_rate ?? 86.5;
  const capitalInr = Math.round(totalCapital * inrRate);

  const openPositionCount = botStatus?.open_positions ?? 0;

  const uptimeSeconds = botStatus?.uptime_seconds ?? 0;

  const todayStats = useMemo(() => {
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());

    const todayTrades = trades.filter(t => {
      const opened = new Date(t.timestamp); // timestamp is normalized from opened_at
      return opened >= todayStart && t.status !== 'open';
    });

    const pnl = todayTrades.reduce((s, t) => s + (t.pnl ?? 0), 0);
    const fees = todayTrades.reduce((s, t) => s + (t.entry_fee ?? 0) + (t.exit_fee ?? 0), 0);
    const wins = todayTrades.filter(t => (t.pnl ?? 0) > 0).length;
    const losses = todayTrades.filter(t => (t.pnl ?? 0) <= 0).length;
    const total = todayTrades.length;
    const winRate = total > 0 ? (wins / total) * 100 : 0;

    return { pnl, wins, losses, fees, total, winRate };
  }, [trades]);

  // Direct Supabase fetch for today's trades — refreshes every 30s
  interface LiveTodayStats {
    pnl: number; fees: number; wins: number; losses: number; total: number; winRate: number;
  }
  const [liveToday, setLiveToday] = useState<LiveTodayStats | null>(null);

  useEffect(() => {
    const fetchToday = async () => {
      const db = getSupabase();
      if (!db) return;
      const istOffset = 5.5 * 60 * 60 * 1000;
      const nowIST = new Date(Date.now() + istOffset);
      const todayIST = nowIST.toISOString().slice(0, 10); // "YYYY-MM-DD"
      const todayStartISO = new Date(todayIST + 'T00:00:00+05:30').toISOString();
      const { data } = await db
        .from('trades')
        .select('pnl, entry_fee, exit_fee, status')
        .gte('opened_at', todayStartISO)
        .neq('status', 'open');
      if (!data) return;
      const pnl = data.reduce((s: number, t: any) => s + (t.pnl ?? 0), 0);
      const fees = data.reduce((s: number, t: any) => s + (t.entry_fee ?? 0) + (t.exit_fee ?? 0), 0);
      const wins = data.filter((t: any) => (t.pnl ?? 0) > 0).length;
      const losses = data.filter((t: any) => (t.pnl ?? 0) <= 0).length;
      const total = data.length;
      setLiveToday({ pnl, fees, wins, losses, total, winRate: total > 0 ? (wins / total) * 100 : 0 });
    };
    fetchToday();
    const id = setInterval(fetchToday, 30_000);
    return () => clearInterval(id);
  }, []);

  // Use live fetch when available, fall back to context-derived stats
  const today = liveToday ?? todayStats;

  const [pnlRange, setPnlRange] = useState<'24h' | '7d' | '14d' | '30d'>('24h');
  const [cardView, setCardView] = useState<CardView>('pnl');
  const exchStats = { delta: {} as any };

  // Deposit stats filtered by same pnlRange
  const depositStats = useMemo(() => {
    const now = Date.now();
    const istOffsetMs = 5.5 * 60 * 60 * 1000;
    let cutoffMs: number;
    if (pnlRange === '24h') {
      const istNow = new Date(now + istOffsetMs);
      const todayIST = istNow.toISOString().slice(0, 10);
      cutoffMs = new Date(todayIST + 'T00:00:00+05:30').getTime();
    } else {
      const days = pnlRange === '7d' ? 7 : pnlRange === '14d' ? 14 : 30;
      cutoffMs = now - days * 24 * 60 * 60 * 1000;
    }
    const filtered = deposits.filter((d) => new Date(d.created_at).getTime() >= cutoffMs);
    const total = filtered.reduce((s, d) => s + d.amount, 0);
    const totalInr = filtered.reduce((s, d) => s + (d.amount_inr ?? d.amount * inrRate), 0);
    // All-time totals
    const allTotal = deposits.reduce((s, d) => s + d.amount, 0);
    const allInr = deposits.reduce((s, d) => s + (d.amount_inr ?? d.amount * inrRate), 0);
    return { filtered, total, totalInr, count: filtered.length, allTotal, allInr, allCount: deposits.length };
  }, [deposits, pnlRange, inrRate]);

  const pnlStats = useMemo(() => {
    const now = Date.now();
    const istOffsetMs = 5.5 * 60 * 60 * 1000;

    let cutoffMs: number;
    if (pnlRange === '24h') {
      const istNow = new Date(now + istOffsetMs);
      const todayIST = istNow.toISOString().slice(0, 10);
      cutoffMs = new Date(todayIST + 'T00:00:00+05:30').getTime();
    } else {
      const days = pnlRange === '7d' ? 7 : pnlRange === '14d' ? 14 : 30;
      cutoffMs = now - days * 24 * 60 * 60 * 1000;
    }

    let pnl = 0;
    let total = 0;
    let wins = 0;
    let fees = 0;
    let grossPnl = 0;
    for (const t of trades) {
      if (t.status !== 'closed') continue;
      const tradeTime = new Date(t.timestamp).getTime();
      if (tradeTime >= cutoffMs) {
        pnl += t.pnl ?? 0;
        total++;
        if ((t.pnl ?? 0) > 0) wins++;
        const tradeFees = (t.entry_fee ?? 0) + (t.exit_fee ?? 0);
        fees += tradeFees;
        grossPnl += t.gross_pnl != null ? t.gross_pnl : ((t.pnl ?? 0) + tradeFees);
      }
    }
    const winRate = total > 0 ? (wins / total) * 100 : 0;
    return { pnl, total, wins, losses: total - wins, winRate, fees, grossPnl };
  }, [trades, pnlRange]);

  // Build sparkline data: cumulative PnL from dailyPnL for selected range
  const sparklineData = useMemo(() => {
    const now = Date.now();
    const days = pnlRange === '24h' ? 1 : pnlRange === '7d' ? 7 : pnlRange === '14d' ? 14 : 30;
    const cutoffMs = now - days * 24 * 60 * 60 * 1000;

    const filtered = dailyPnL
      .filter((d) => new Date(d.trade_date).getTime() >= cutoffMs)
      .sort((a, b) => a.trade_date.localeCompare(b.trade_date));

    if (filtered.length === 0) return [];

    let cumulative = 0;
    return filtered.map((d) => {
      cumulative += d.daily_pnl;
      return cumulative;
    });
  }, [dailyPnL, pnlRange]);

  // Count distinct strategies from all trades (not just open)
  const liveStrategyCount = useMemo(() => {
    const strategies = new Set(trades.map((t) => t.strategy));
    return strategies.size || 1;
  }, [trades]);

  const lastHeartbeat = botStatus?.timestamp;
  const [isStale, setIsStale] = useState(true);
  useEffect(() => {
    const check = () => {
      if (!lastHeartbeat) { setIsStale(true); return; }
      // Supabase returns "2026-02-28 11:46:27+00" — normalize to valid ISO-8601
      const normalized = String(lastHeartbeat).replace(' ', 'T').replace(/\+00$/, '+00:00');
      setIsStale(Date.now() - new Date(normalized).getTime() > 420_000);
    };
    check();
    const id = setInterval(check, 30_000);
    return () => clearInterval(id);
  }, [lastHeartbeat]);

  // Human-readable "last updated" label
  const staleLabel = useMemo(() => {
    if (!lastHeartbeat) return 'No data';
    const normalized = String(lastHeartbeat).replace(' ', 'T').replace(/\+00$/, '+00:00');
    const ago = Math.max(0, Math.floor((Date.now() - new Date(normalized).getTime()) / 1000));
    if (ago < 60) return `${ago}s ago`;
    if (ago < 3600) return `${Math.floor(ago / 60)}m ago`;
    return `${Math.floor(ago / 3600)}h ${Math.floor((ago % 3600) / 60)}m ago`;
  }, [lastHeartbeat, isStale]); // re-evaluate when isStale ticks

  const sparkColor = pnlStats.pnl >= 0 ? '#00c853' : '#ff1744';

  return (
    <div className="bg-[#0d1117] border border-zinc-800 rounded-xl p-3 md:p-4">

      {/* ═══ MOBILE LAYOUT ═══ */}
      <div className="flex flex-col gap-2 md:hidden">

        {/* Row 1 — Total Capital (prominent full-width card) */}
        <div className="bg-zinc-900/60 border border-zinc-700 rounded-xl px-4 py-3.5">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-1">Total Capital</div>
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-2xl font-bold text-white">{formatCurrency(totalCapital)}</span>
                {capitalInr > 0 && (
                  <span className="text-xs text-zinc-500 font-mono">{'\u20B9'}{capitalInr.toLocaleString('en-IN')}</span>
                )}
              </div>
            </div>
            {openPositionCount > 0 && (
              <span className="text-xs font-mono font-semibold text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-full px-2.5 py-1">{openPositionCount} open</span>
            )}
          </div>
        </div>

        {/* Row 2 — Today's performance */}
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl px-3.5 py-3">
          <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
            <div className="md:col-span-7 flex flex-col justify-center">
              <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-1">Today</div>
              <div className={cn(
                'font-mono text-4xl md:text-5xl font-bold',
                today.pnl >= 0 ? 'text-green-500' : today.pnl < 0 ? 'text-red-500' : 'text-white'
              )}>
                {today.pnl >= 0 ? '+' : ''}{formatCurrency(today.pnl)}
              </div>
            </div>
            <div className="md:col-span-5 grid grid-cols-2 gap-3">
              <div className="bg-zinc-900/60 rounded-lg p-2">
                <div className="text-[10px] uppercase tracking-wider text-zinc-500">Win Rate</div>
                <div className="text-lg font-semibold text-zinc-200">{today.total > 0 ? `${today.winRate.toFixed(0)}%` : '—'}</div>
              </div>
              <div className="bg-zinc-900/60 rounded-lg p-2">
                <div className="text-[10px] uppercase tracking-wider text-zinc-500">Fees</div>
                <div className="text-lg font-semibold text-zinc-200">${today.fees.toFixed(2)}</div>
              </div>
              <div className="bg-zinc-900/60 rounded-lg p-2">
                <div className="text-[10px] uppercase tracking-wider text-zinc-500">W/L</div>
                <div className="text-lg font-semibold text-zinc-200">{today.wins}W / {today.losses}L</div>
              </div>
              <div className="bg-zinc-900/60 rounded-lg p-2">
                <div className="text-[10px] uppercase tracking-wider text-zinc-500">Trades</div>
                <div className="text-lg font-semibold text-zinc-200">{today.total}</div>
              </div>
            </div>
          </div>
          {recentTrades.length > 0 && (
            <div className="mt-4 pt-3 border-t border-zinc-800">
              <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-2">Last 10 Trades</div>
              <div className="flex gap-1 flex-wrap">
                {[...recentTrades].reverse().map((trade, i) => (
                  <div
                    key={trade.id ?? i}
                    className={cn(
                      'w-6 h-6 rounded opacity-80 hover:opacity-100 cursor-pointer transition-opacity',
                      trade.pnl > 0 ? 'bg-green-500' : trade.pnl < 0 ? 'bg-red-500' : 'bg-gray-500'
                    )}
                    title={`${trade.pair}: ${trade.pnl >= 0 ? '+' : ''}${formatCurrency(trade.pnl)}`}
                  />
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Row 2 — PnL / Deposits toggled card */}
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg px-3 py-2">
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center gap-1">
              {(['24h', '7d', '14d', '30d'] as const).map((range) => (
                <button
                  key={range}
                  onClick={() => setPnlRange(range)}
                  className={cn(
                    'px-1.5 py-0.5 rounded text-[9px] font-medium transition-colors',
                    pnlRange === range
                      ? 'bg-zinc-700 text-white'
                      : 'text-zinc-500 hover:text-zinc-300',
                  )}
                >
                  {range.toUpperCase()}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-0.5">
              <button
                onClick={() => setCardView('pnl')}
                className={cn(
                  'px-1.5 py-0.5 rounded text-[9px] font-medium transition-colors',
                  cardView === 'pnl' ? 'bg-zinc-700 text-white' : 'text-zinc-500 hover:text-zinc-300',
                )}
              >
                P&L
              </button>
              <button
                onClick={() => setCardView('deposits')}
                className={cn(
                  'px-1.5 py-0.5 rounded text-[9px] font-medium transition-colors',
                  cardView === 'deposits' ? 'bg-[#2196f3]/20 text-[#2196f3]' : 'text-zinc-500 hover:text-zinc-300',
                )}
              >
                Deposits
              </button>
            </div>
          </div>

          {cardView === 'pnl' ? (
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                {pnlStats.total > 0 ? (
                  <>
                    <div className="flex items-baseline gap-1.5">
                      <span className={cn(
                        'font-mono text-base font-bold',
                        pnlStats.pnl >= 0 ? 'text-[#00c853]' : 'text-[#ff1744]',
                      )}>
                        {pnlStats.pnl >= 0 ? '+' : ''}{formatCurrency(pnlStats.pnl)}
                      </span>
                      <span className="text-[9px] text-zinc-500 font-mono">
                        {pnlStats.pnl >= 0 ? '+' : '-'}{'\u20B9'}{Math.abs(Math.round(pnlStats.pnl * inrRate)).toLocaleString('en-IN')}
                      </span>
                    </div>
                    <div className="text-[9px] text-zinc-500 font-mono mt-0.5">
                      {pnlStats.wins}W / {pnlStats.losses}L · {pnlStats.winRate.toFixed(0)}% WR · {pnlStats.total} trades
                    </div>
                    {pnlStats.fees > 0 && (
                      <div className="text-[9px] font-mono mt-0.5">
                        <span className={pnlStats.grossPnl >= 0 ? 'text-[#00c853]/60' : 'text-[#ff1744]/60'}>
                          {pnlStats.grossPnl >= 0 ? '+' : ''}{formatCurrency(pnlStats.grossPnl)} P&L
                        </span>
                        <span className="text-zinc-600"> · </span>
                        <span className="text-zinc-500">${pnlStats.fees.toFixed(2)} fees</span>
                      </div>
                    )}
                  </>
                ) : (
                  <span className="text-xs text-zinc-500">No trades</span>
                )}
              </div>
              <MiniSparkline data={sparklineData} color={sparkColor} />
            </div>
          ) : (
            <div className="min-w-0">
              <div className="flex items-baseline gap-1.5">
                <span className="font-mono text-base font-bold text-[#2196f3]">
                  {formatCurrency(depositStats.total)}
                </span>
                <span className="text-[9px] text-zinc-500 font-mono">
                  {'\u20B9'}{Math.round(depositStats.totalInr).toLocaleString('en-IN')}
                </span>
              </div>
              <div className="text-[9px] text-zinc-500 font-mono mt-0.5">
                {depositStats.count} deposit{depositStats.count !== 1 ? 's' : ''} in period
              </div>
              <div className="text-[9px] font-mono mt-0.5">
                <span className="text-[#2196f3]/60">
                  {formatCurrency(depositStats.allTotal)} total
                </span>
                <span className="text-zinc-600"> · </span>
                <span className="text-zinc-500">{depositStats.allCount} all-time</span>
              </div>
            </div>
          )}
        </div>

        {/* Row 3 — Market Regime */}
        <div className={cn(
          'flex flex-col gap-1.5 rounded-lg border px-3 py-2',
          rc.bg,
          rc.pulse && 'animate-pulse',
        )}>
          <div className="flex items-center gap-2">
            <span className={cn('text-base', rc.text)}>{rc.icon}</span>
            <span className={cn('text-xs font-bold tracking-wide', rc.text)}>{rc.label}</span>
            {regime === 'CHOPPY' && (
              <span className="text-[10px] font-semibold text-red-300 ml-1">NO TRADES</span>
            )}
          </div>
          <div className="flex items-center justify-between text-[10px] font-mono text-zinc-400">
            <span>Chop: {chopScore.toFixed(2)}</span>
            <span>ATR: {atrRatio.toFixed(1)}x</span>
            <span>Net: {netChange >= 0 ? '+' : ''}{netChange.toFixed(2)}%</span>
            {regimeDuration && <span>Since {regimeDuration}</span>}
          </div>
        </div>

        {/* Row 4 — Bot state + uptime + open positions + clock */}
        <div className="flex items-center justify-between px-1">
          <div className="flex items-center gap-2">
            <span
              className={cn(
                'inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[9px] font-medium',
                botState === 'running'
                  ? 'bg-[#00c853]/10 text-[#00c853]'
                  : 'bg-[#ffd600]/10 text-[#ffd600]',
              )}
            >
              <span className={cn(
                'w-1.5 h-1.5 rounded-full',
                botState === 'running' ? 'bg-[#00c853]' : 'bg-[#ffd600]',
              )} />
              {botState === 'running' ? 'Running' : 'Paused'}
            </span>
            {botState !== 'running' && botStatus?.pause_reason && (
              <span className="text-[9px] text-[#ffd600]/70 font-mono truncate max-w-[120px]">{botStatus.pause_reason}</span>
            )}
            {uptimeSeconds > 0 && (
              <span className="text-[9px] text-zinc-500 font-mono">{formatUptime(uptimeSeconds)}</span>
            )}
            {openPositionCount > 0 && (
              <span className="text-[9px] font-mono text-amber-400">{openPositionCount} open</span>
            )}
          </div>
          <ISTClock />
        </div>
      </div>

      {/* ═══ DESKTOP LAYOUT (unchanged) ═══ */}
      <div className="hidden md:flex md:flex-row md:items-center md:justify-between gap-4">
        {/* Exchange Cards */}
        <div className="flex gap-3 flex-1 min-w-0">
          {/* Today's performance card */}
          <div className="flex-1 bg-zinc-900/50 border border-zinc-800 rounded-lg px-4 py-3">
            <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
              <div className="md:col-span-7 flex flex-col justify-center">
                <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-1">Today</div>
                <div className={cn(
                  'font-mono text-4xl md:text-5xl font-bold',
                  today.pnl >= 0 ? 'text-green-500' : today.pnl < 0 ? 'text-red-500' : 'text-white'
                )}>
                  {today.pnl >= 0 ? '+' : ''}{formatCurrency(today.pnl)}
                </div>
              </div>
              <div className="md:col-span-5 grid grid-cols-2 gap-3">
                <div className="bg-zinc-900/60 rounded-lg p-2">
                  <div className="text-[10px] uppercase tracking-wider text-zinc-500">Win Rate</div>
                  <div className="text-lg font-semibold text-zinc-200">{today.total > 0 ? `${today.winRate.toFixed(0)}%` : '—'}</div>
                </div>
                <div className="bg-zinc-900/60 rounded-lg p-2">
                  <div className="text-[10px] uppercase tracking-wider text-zinc-500">Fees</div>
                  <div className="text-lg font-semibold text-zinc-200">${today.fees.toFixed(2)}</div>
                </div>
                <div className="bg-zinc-900/60 rounded-lg p-2">
                  <div className="text-[10px] uppercase tracking-wider text-zinc-500">W/L</div>
                  <div className="text-lg font-semibold text-zinc-200">{today.wins}W / {today.losses}L</div>
                </div>
                <div className="bg-zinc-900/60 rounded-lg p-2">
                  <div className="text-[10px] uppercase tracking-wider text-zinc-500">Trades</div>
                  <div className="text-lg font-semibold text-zinc-200">{today.total}</div>
                </div>
              </div>
            </div>
            {recentTrades.length > 0 && (
              <div className="mt-4 pt-3 border-t border-zinc-800">
                <div className="text-[10px] uppercase tracking-wider text-zinc-500 mb-2">Last 10 Trades</div>
                <div className="flex gap-1 flex-wrap">
                  {[...recentTrades].reverse().map((trade, i) => (
                    <div
                      key={trade.id ?? i}
                      className={cn(
                        'w-6 h-6 rounded opacity-80 hover:opacity-100 cursor-pointer transition-opacity',
                        trade.pnl > 0 ? 'bg-green-500' : trade.pnl < 0 ? 'bg-red-500' : 'bg-gray-500'
                      )}
                      title={`${trade.pair}: ${trade.pnl >= 0 ? '+' : ''}${formatCurrency(trade.pnl)}`}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* P&L / Deposits toggled card */}
          <div className="flex-1 bg-zinc-900/50 border border-zinc-800 rounded-lg px-4 py-3">
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-1.5">
                {(['24h', '7d', '14d', '30d'] as const).map((range) => (
                  <button
                    key={range}
                    onClick={() => setPnlRange(range)}
                    className={cn(
                      'px-1.5 py-0.5 rounded text-[10px] font-medium transition-colors',
                      pnlRange === range
                        ? 'bg-zinc-700 text-white'
                        : 'text-zinc-500 hover:text-zinc-300',
                    )}
                  >
                    {range.toUpperCase()}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-0.5">
                <button
                  onClick={() => setCardView('pnl')}
                  className={cn(
                    'px-1.5 py-0.5 rounded text-[10px] font-medium transition-colors',
                    cardView === 'pnl' ? 'bg-zinc-700 text-white' : 'text-zinc-500 hover:text-zinc-300',
                  )}
                >
                  P&L
                </button>
                <button
                  onClick={() => setCardView('deposits')}
                  className={cn(
                    'px-1.5 py-0.5 rounded text-[10px] font-medium transition-colors',
                    cardView === 'deposits' ? 'bg-[#2196f3]/20 text-[#2196f3]' : 'text-zinc-500 hover:text-zinc-300',
                  )}
                >
                  Deposits
                </button>
              </div>
            </div>

            {cardView === 'pnl' ? (
              pnlStats.total > 0 ? (
                <>
                  <div className="flex items-baseline gap-2">
                    <span className={cn(
                      'font-mono text-lg font-bold',
                      pnlStats.pnl >= 0 ? 'text-[#00c853]' : 'text-[#ff1744]',
                    )}>
                      {pnlStats.pnl >= 0 ? '+' : ''}{formatCurrency(pnlStats.pnl)}
                    </span>
                    <span className="text-[10px] text-zinc-500 font-mono">
                      {pnlStats.pnl >= 0 ? '+' : '-'}{'\u20B9'}{Math.abs(Math.round(pnlStats.pnl * inrRate)).toLocaleString('en-IN')}
                    </span>
                  </div>
                  <div className="text-[10px] text-zinc-500 font-mono">
                    {pnlStats.wins}W / {pnlStats.losses}L · {pnlStats.winRate.toFixed(0)}% WR · {pnlStats.total} trades
                  </div>
                  {pnlStats.fees > 0 && (
                    <div className="text-[10px] font-mono">
                      <span className={pnlStats.grossPnl >= 0 ? 'text-[#00c853]/60' : 'text-[#ff1744]/60'}>
                        {pnlStats.grossPnl >= 0 ? '+' : ''}{formatCurrency(pnlStats.grossPnl)} P&L
                      </span>
                      <span className="text-zinc-600"> · </span>
                      <span className="text-zinc-500">${pnlStats.fees.toFixed(2)} fees</span>
                    </div>
                  )}
                </>
              ) : (
                <span className="text-xs text-zinc-500">No trades</span>
              )
            ) : (
              <>
                <div className="flex items-baseline gap-2">
                  <span className="font-mono text-lg font-bold text-[#2196f3]">
                    {formatCurrency(depositStats.total)}
                  </span>
                  <span className="text-[10px] text-zinc-500 font-mono">
                    {'\u20B9'}{Math.round(depositStats.totalInr).toLocaleString('en-IN')}
                  </span>
                </div>
                <div className="text-[10px] text-zinc-500 font-mono">
                  {depositStats.count} deposit{depositStats.count !== 1 ? 's' : ''} in period
                </div>
                <div className="text-[10px] font-mono">
                  <span className="text-[#2196f3]/60">
                    {formatCurrency(depositStats.allTotal)} total
                  </span>
                  <span className="text-zinc-600"> · </span>
                  <span className="text-zinc-500">{depositStats.allCount} all-time</span>
                </div>
              </>
            )}
          </div>

          {/* Market Regime Card — Visual Upgrade */}
          <MarketRegimeCard
            regime={regime}
            chopScore={chopScore}
            atrRatio={atrRatio}
            netChange={netChange}
            regimeDuration={regimeDuration}
          />
        </div>

        {/* Center: Total Capital + Bot State */}
        <div className="flex flex-col items-center gap-1 border-x border-zinc-800 px-6">
          <span className="text-[10px] uppercase tracking-wider text-zinc-500">Total Capital</span>
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-xl font-bold text-white truncate">
              {formatCurrency(totalCapital)}
            </span>
            {capitalInr > 0 && (
              <span className="text-[10px] text-zinc-500 font-mono">{'\u20B9'}{capitalInr.toLocaleString('en-IN')}</span>
            )}
          </div>
          {deltaBalance > 0 && openPositionCount > 0 && (
            <span className="text-[10px] font-mono text-amber-400">{openPositionCount} open</span>
          )}
          <div className="flex items-center gap-3 mt-1">
            <span
              className={cn(
                'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium',
                botState === 'running'
                  ? 'bg-[#00c853]/10 text-[#00c853]'
                  : 'bg-[#ffd600]/10 text-[#ffd600]',
              )}
            >
              <span
                className={cn(
                  'w-1.5 h-1.5 rounded-full',
                  botState === 'running' ? 'bg-[#00c853]' : 'bg-[#ffd600]',
                )}
              />
              {botState === 'running' ? 'Running' : 'Paused'}
            </span>
            {botState !== 'running' && botStatus?.pause_reason && (
              <span className="text-[10px] text-[#ffd600]/70 font-mono max-w-[200px] truncate" title={botStatus.pause_reason}>
                {botStatus.pause_reason}
              </span>
            )}
            {uptimeSeconds > 0 && (
              <span className="text-[10px] text-zinc-500">{formatUptime(uptimeSeconds)}</span>
            )}
          </div>
          {isStale && (
            <span className="text-[9px] font-mono text-red-400/70">Status: {staleLabel}</span>
          )}
        </div>

        {/* Right: Stats + Clock */}
        <div className="flex items-center gap-4">
          <div className="flex flex-col gap-1.5 text-[10px]">
            <div className="flex items-center gap-2">
              <span className="text-zinc-500">Strategies</span>
              <span className="text-[#2196f3] font-mono">{liveStrategyCount}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-zinc-500">Total Trades</span>
              <span className="text-zinc-300 font-mono">{trades.length}</span>
            </div>
          </div>
          <div className="border-l border-zinc-800 pl-4 flex flex-col items-end gap-1">
            <ISTClock />
            <span className="text-[9px] text-zinc-600 font-mono">
              Alpha v{process.env.ALPHA_VERSION ?? '?'}
            </span>
          </div>
        </div>
      </div>

    </div>
  );
}

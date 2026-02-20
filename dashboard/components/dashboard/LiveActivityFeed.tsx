'use client';

import { useRef, useEffect, useState, useMemo } from 'react';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import { formatShortDate, cn } from '@/lib/utils';
import type { ActivityEventType, ActivityFilter } from '@/lib/types';

const EVENT_ICONS: Record<ActivityEventType, string> = {
  trade_open: '\u{1F7E2}',
  trade_close: '\u2705',
  short_open: '\u{1F534}',
  options_entry: '\u{1F4C8}',
  options_skip: '\u23F8\uFE0F',
  options_exit: '\u{1F4C9}',
  risk_alert: '\u26A0\uFE0F',
};

const EVENT_COLORS: Record<ActivityEventType, string> = {
  trade_open: 'border-l-[#00c853]',
  trade_close: 'border-l-[#00c853]',
  short_open: 'border-l-[#ff1744]',
  options_entry: 'border-l-[#7c4dff]',
  options_skip: 'border-l-zinc-600',
  options_exit: 'border-l-[#7c4dff]',
  risk_alert: 'border-l-[#ffd600]',
};

const FILTER_OPTIONS: { value: ActivityFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'trades', label: 'Trades' },
  { value: 'options', label: 'Options' },
];

export function LiveActivityFeed() {
  const { activityFeed } = useSupabase();
  const [filter, setFilter] = useState<ActivityFilter>('all');
  const scrollRef = useRef<HTMLDivElement>(null);

  const filtered = useMemo(() => {
    if (filter === 'all') return activityFeed;
    if (filter === 'trades') {
      return activityFeed.filter((e) =>
        e.eventType === 'trade_open' ||
        e.eventType === 'trade_close' ||
        e.eventType === 'short_open',
      );
    }
    // Options filter
    return activityFeed.filter((e) =>
      e.eventType === 'options_entry' ||
      e.eventType === 'options_skip' ||
      e.eventType === 'options_exit',
    );
  }, [activityFeed, filter]);

  // Auto-scroll when new items arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [filtered.length]);

  return (
    <div className="bg-[#0d1117] border border-zinc-800 rounded-xl p-3 md:p-5">
      <div className="flex items-center justify-between mb-3 md:mb-4">
        <h3 className="text-sm font-medium text-zinc-400 uppercase tracking-wider">
          Live Activity
        </h3>
        <div className="flex gap-1">
          {FILTER_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setFilter(opt.value)}
              className={cn(
                'px-3 py-1.5 md:px-2.5 md:py-1 rounded text-xs md:text-[10px] font-medium transition-colors',
                filter === opt.value
                  ? 'bg-zinc-700 text-white'
                  : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50',
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div ref={scrollRef} className="max-h-64 overflow-y-auto space-y-1 pr-1">
        {filtered.length === 0 ? (
          <p className="text-sm text-zinc-500 text-center py-6">No activity yet</p>
        ) : (
          filtered.map((event) => (
            <div
              key={`${event.id}-${event.eventType}`}
              className={cn(
                'flex items-start gap-3 px-3 py-2 rounded-md border-l-2 bg-zinc-900/30',
                EVENT_COLORS[event.eventType],
              )}
            >
              <span className="text-sm mt-0.5 flex-shrink-0">
                {EVENT_ICONS[event.eventType]}
              </span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono text-zinc-500 flex-shrink-0">
                    {formatShortDate(event.timestamp)}
                  </span>
                  {event.pair && (
                    <span className="text-[10px] font-medium text-zinc-400">{event.pair}</span>
                  )}
                </div>
                <p className={cn(
                  'text-xs mt-0.5',
                  event.eventType === 'options_skip' ? 'text-zinc-500 truncate' : 'text-zinc-300 truncate',
                )}>
                  {event.description}
                </p>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

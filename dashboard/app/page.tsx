'use client';

import { useState, useMemo } from 'react';
import { useSupabase } from '@/components/providers/SupabaseProvider';
import { BBsqueezeCard, type SqueezeData } from '@/components/dashboard/BBsqueezeCard';
import { PremiumRange } from '@/components/dashboard/PremiumRange';
import { DirectionBias, DirectionBiasMeter, type BiasType } from '@/components/dashboard/DirectionBias';

// Import the new CSS
import '@/styles/dashboard.css';

// Sample data for demonstration - replace with real data from your API
const SAMPLE_ASSETS: SqueezeData[] = [
  { symbol: 'BTCUSDT', price: 67245.32, squeezeValue: 92, bias: 'long', bbPosition: 85, momentum: 78, change24h: 3.45, isActive: true },
  { symbol: 'ETHUSDT', price: 3521.18, squeezeValue: 87, bias: 'long', bbPosition: 72, momentum: 65, change24h: 2.12, isActive: true },
  { symbol: 'SOLUSDT', price: 148.92, squeezeValue: 45, bias: 'neutral', bbPosition: 15, momentum: -12, change24h: -0.85 },
  { symbol: 'BNBUSDT', price: 612.45, squeezeValue: 78, bias: 'short', bbPosition: -45, momentum: -55, change24h: -1.23 },
  { symbol: 'XRPUSDT', price: 0.6234, squeezeValue: 34, bias: 'neutral', bbPosition: -5, momentum: 8, change24h: 0.45 },
  { symbol: 'ADAUSDT', price: 0.4521, squeezeValue: 89, bias: 'long', bbPosition: 68, momentum: 72, change24h: 4.56, isActive: true },
  { symbol: 'DOGEUSDT', price: 0.1234, squeezeValue: 23, bias: 'short', bbPosition: -65, momentum: -35, change24h: -2.34 },
  { symbol: 'DOTUSDT', price: 7.89, squeezeValue: 67, bias: 'neutral', bbPosition: 25, momentum: 15, change24h: 1.12 },
];

/**
 * Status Pill Component
 */
function StatusPill({ 
  label, 
  color, 
  pulse = false 
}: { 
  label: string; 
  color: 'green' | 'amber' | 'red' | 'blue' | 'neutral';
  pulse?: boolean;
}) {
  const colorMap = {
    green: 'bg-[rgba(0,255,136,0.15)] text-[#00ff88] border-[rgba(0,255,136,0.3)]',
    amber: 'bg-[rgba(255,184,0,0.15)] text-[#ffb800] border-[rgba(255,184,0,0.3)]',
    red: 'bg-[rgba(255,71,87,0.15)] text-[#ff4757] border-[rgba(255,71,87,0.3)]',
    blue: 'bg-[rgba(59,130,246,0.15)] text-[#3b82f6] border-[rgba(59,130,246,0.3)]',
    neutral: 'bg-[rgba(255,255,255,0.05)] text-[#9ca3af] border-[rgba(255,255,255,0.1)]',
  };

  return (
    <span className={`
      inline-flex items-center gap-1.5 px-3 py-1.5 
      rounded-full text-[11px] font-semibold border
      ${colorMap[color]}
    `}>
      {pulse && (
        <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
      )}
      {label}
    </span>
  );
}

/**
 * Filter Section Component
 */
function FilterSection({
  minSqueeze,
  setMinSqueeze,
  selectedBias,
  setSelectedBias,
  showActiveOnly,
  setShowActiveOnly,
}: {
  minSqueeze: number;
  setMinSqueeze: (v: number) => void;
  selectedBias: BiasType | 'all';
  setSelectedBias: (v: BiasType | 'all') => void;
  showActiveOnly: boolean;
  setShowActiveOnly: (v: boolean) => void;
}) {
  return (
    <div className="glass-elevated p-4 rounded-[14px] space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-white">Filters</h3>
        <button
          onClick={() => {
            setMinSqueeze(0);
            setSelectedBias('all');
            setShowActiveOnly(false);
          }}
          className="text-[11px] text-[#9ca3af] hover:text-white transition-colors"
        >
          Reset
        </button>
      </div>

      {/* Squeeze Threshold Slider */}
      <PremiumRange
        label="Min Squeeze %"
        min={0}
        max={100}
        step={5}
        value={minSqueeze}
        onChange={setMinSqueeze}
        variant="blue"
        size="sm"
      />

      {/* Bias Filter */}
      <div className="space-y-2">
        <span className="text-[11px] font-medium text-[#9ca3af] uppercase tracking-wide">Bias</span>
        <div className="flex flex-wrap gap-2">
          {(['all', 'long', 'short', 'neutral'] as const).map((bias) => (
            <button
              key={bias}
              onClick={() => setSelectedBias(bias)}
              className={`
                px-3 py-1.5 rounded-lg text-[11px] font-medium capitalize
                transition-all duration-150
                ${selectedBias === bias 
                  ? 'bg-white text-[#0a0a0f]' 
                  : 'bg-[rgba(255,255,255,0.05)] text-[#9ca3af] hover:bg-[rgba(255,255,255,0.1)]'
                }
              `}
            >
              {bias}
            </button>
          ))}
        </div>
      </div>

      {/* Active Only Toggle */}
      <label className="flex items-center gap-3 cursor-pointer group">
        <div className="relative">
          <input
            type="checkbox"
            checked={showActiveOnly}
            onChange={(e) => setShowActiveOnly(e.target.checked)}
            className="sr-only"
          />
          <div className={`
            w-10 h-5 rounded-full transition-colors duration-200
            ${showActiveOnly ? 'bg-[#00ff88]' : 'bg-[rgba(255,255,255,0.1)]'}
          `}>
            <div className={`
              absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white
              transition-transform duration-200
              ${showActiveOnly ? 'translate-x-5' : 'translate-x-0'}
            `} />
          </div>
        </div>
        <span className="text-xs text-[#9ca3af] group-hover:text-white transition-colors">
          Active signals only
        </span>
      </label>
    </div>
  );
}

/**
 * Stats Overview Component
 */
function StatsOverview({ assets }: { assets: SqueezeData[] }) {
  const stats = useMemo(() => {
    const active = assets.filter(a => a.isActive).length;
    const long = assets.filter(a => a.bias === 'long').length;
    const short = assets.filter(a => a.bias === 'short').length;
    const avgSqueeze = assets.reduce((acc, a) => acc + a.squeezeValue, 0) / assets.length;
    
    return { active, long, short, avgSqueeze };
  }, [assets]);

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      <div className="glass-card p-3 rounded-xl">
        <div className="text-[10px] font-medium text-[#6b7280] uppercase tracking-wide mb-1">Active</div>
        <div className="text-xl font-bold text-white font-mono">{stats.active}</div>
      </div>
      <div className="glass-card p-3 rounded-xl">
        <div className="text-[10px] font-medium text-[#6b7280] uppercase tracking-wide mb-1">Long Bias</div>
        <div className="text-xl font-bold text-[#00ff88] font-mono">{stats.long}</div>
      </div>
      <div className="glass-card p-3 rounded-xl">
        <div className="text-[10px] font-medium text-[#6b7280] uppercase tracking-wide mb-1">Short Bias</div>
        <div className="text-xl font-bold text-[#ff4757] font-mono">{stats.short}</div>
      </div>
      <div className="glass-card p-3 rounded-xl">
        <div className="text-[10px] font-medium text-[#6b7280] uppercase tracking-wide mb-1">Avg Squeeze</div>
        <div className="text-xl font-bold text-[#3b82f6] font-mono">{stats.avgSqueeze.toFixed(0)}%</div>
      </div>
    </div>
  );
}

/**
 * Main Dashboard Page
 */
export default function DashboardPage() {
  const { isConnected, trades, botStatus } = useSupabase();
  
  // Filter states
  const [minSqueeze, setMinSqueeze] = useState(50);
  const [selectedBias, setSelectedBias] = useState<BiasType | 'all'>('all');
  const [showActiveOnly, setShowActiveOnly] = useState(false);
  const [selectedAsset, setSelectedAsset] = useState<SqueezeData | null>(null);

  // Bot state
  const botState = botStatus?.bot_state ?? (isConnected ? 'running' : 'paused');
  const openPositions = botStatus?.open_positions ?? 0;
  const leverageLevel = botStatus?.leverage ?? 1;

  // Filter assets
  const filteredAssets = useMemo(() => {
    return SAMPLE_ASSETS.filter(asset => {
      if (asset.squeezeValue < minSqueeze) return false;
      if (selectedBias !== 'all' && asset.bias !== selectedBias) return false;
      if (showActiveOnly && !asset.isActive) return false;
      return true;
    });
  }, [minSqueeze, selectedBias, showActiveOnly]);

  return (
    <div className="min-h-screen pb-safe">
      {/* Header */}
      <header className="sticky top-0 z-40 backdrop-blur-xl bg-[rgba(10,10,15,0.8)] border-b border-[rgba(255,255,255,0.06)]">
        <div className="px-4 py-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <h1 className="text-xl font-bold text-white tracking-tight">GPFC Dashboard</h1>
              <p className="text-xs text-[#6b7280] mt-0.5">Bollinger Bands Squeeze Monitor</p>
            </div>
            
            {/* Status Pills */}
            <div className="flex flex-wrap items-center gap-2">
              <StatusPill 
                label={botState === 'running' ? 'Live' : 'Paused'} 
                color={botState === 'running' ? 'green' : 'amber'}
                pulse={botState === 'running'}
              />
              {openPositions > 0 && (
                <StatusPill label={`${openPositions} Open`} color="blue" />
              )}
              <StatusPill label={`${leverageLevel}x Lev`} color="neutral" />
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="px-4 py-4 space-y-4">
        {/* Stats Overview */}
        <StatsOverview assets={filteredAssets} />

        {/* Mobile: Stacked Layout */}
        <div className="block lg:hidden space-y-4">
          {/* Filters */}
          <FilterSection
            minSqueeze={minSqueeze}
            setMinSqueeze={setMinSqueeze}
            selectedBias={selectedBias}
            setSelectedBias={setSelectedBias}
            showActiveOnly={showActiveOnly}
            setShowActiveOnly={setShowActiveOnly}
          />

          {/* Asset Grid */}
          <div className="asset-grid">
            {filteredAssets.map((asset, index) => (
              <BBsqueezeCard
                key={asset.symbol}
                data={asset}
                onClick={setSelectedAsset}
                className={`animate-slide-up stagger-${Math.min(index + 1, 6)}`}
              />
            ))}
          </div>

          {filteredAssets.length === 0 && (
            <div className="text-center py-12">
              <p className="text-sm text-[#6b7280]">No assets match your filters</p>
              <button
                onClick={() => {
                  setMinSqueeze(0);
                  setSelectedBias('all');
                  setShowActiveOnly(false);
                }}
                className="mt-3 text-xs text-[#3b82f6] hover:underline"
              >
                Clear filters
              </button>
            </div>
          )}
        </div>

        {/* Desktop: Side-by-side Layout */}
        <div className="hidden lg:grid lg:grid-cols-12 gap-4">
          {/* Left Panel - Filters & Stats */}
          <div className="lg:col-span-3 space-y-4">
            <FilterSection
              minSqueeze={minSqueeze}
              setMinSqueeze={setMinSqueeze}
              selectedBias={selectedBias}
              setSelectedBias={setSelectedBias}
              showActiveOnly={showActiveOnly}
              setShowActiveOnly={setShowActiveOnly}
            />

            {/* Selected Asset Detail */}
            {selectedAsset && (
              <div className="glass-card p-4 rounded-[14px] space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-white">{selectedAsset.symbol}</h3>
                  <button
                    onClick={() => setSelectedAsset(null)}
                    className="text-[#6b7280] hover:text-white transition-colors"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>

                <div className="space-y-4">
                  <div>
                    <div className="text-[10px] text-[#6b7280] uppercase tracking-wide mb-1">Price</div>
                    <div className="text-2xl font-bold text-white font-mono">
                      ${selectedAsset.price.toLocaleString()}
                    </div>
                    <div className={`text-xs ${selectedAsset.change24h && selectedAsset.change24h >= 0 ? 'text-[#00ff88]' : 'text-[#ff4757]'}`}>
                      {selectedAsset.change24h && selectedAsset.change24h >= 0 ? '+' : ''}{selectedAsset.change24h?.toFixed(2)}%
                    </div>
                  </div>

                  <DirectionBiasMeter 
                    value={selectedAsset.bias === 'long' ? selectedAsset.momentum : selectedAsset.bias === 'short' ? -selectedAsset.momentum : 0}
                    size="md"
                  />

                  <div className="pt-2 border-t border-[rgba(255,255,255,0.06)]">
                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div>
                        <span className="text-[#6b7280]">Squeeze</span>
                        <div className="font-mono font-semibold text-white">{selectedAsset.squeezeValue}%</div>
                      </div>
                      <div>
                        <span className="text-[#6b7280]">Momentum</span>
                        <div className={`font-mono font-semibold ${selectedAsset.momentum > 0 ? 'text-[#00ff88]' : 'text-[#ff4757]'}`}>
                          {selectedAsset.momentum > 0 ? '+' : ''}{selectedAsset.momentum}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Right Panel - Asset Grid */}
          <div className="lg:col-span-9">
            <div className="asset-grid">
              {filteredAssets.map((asset, index) => (
                <BBsqueezeCard
                  key={asset.symbol}
                  data={asset}
                  onClick={setSelectedAsset}
                  className={`animate-slide-up stagger-${Math.min(index + 1, 6)}`}
                />
              ))}
            </div>

            {filteredAssets.length === 0 && (
              <div className="text-center py-16">
                <p className="text-sm text-[#6b7280]">No assets match your filters</p>
                <button
                  onClick={() => {
                    setMinSqueeze(0);
                    setSelectedBias('all');
                    setShowActiveOnly(false);
                  }}
                  className="mt-3 text-xs text-[#3b82f6] hover:underline"
                >
                  Clear filters
                </button>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

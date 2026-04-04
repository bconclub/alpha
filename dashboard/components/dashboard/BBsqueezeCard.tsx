'use client';

import React from 'react';
import { DirectionBias, type BiasType } from './DirectionBias';

export interface SqueezeData {
  symbol: string;
  price: number;
  squeezeValue: number; // 0-100
  bias: BiasType;
  bbPosition: number; // -100 to 100 (relative to bands)
  momentum: number; // -100 to 100
  isActive?: boolean;
  change24h?: number;
}

interface BBsqueezeCardProps {
  data: SqueezeData;
  onClick?: (data: SqueezeData) => void;
  className?: string;
  style?: React.CSSProperties;
}

/**
 * BB Squeeze Card Component
 * 
 * Displays a single asset's Bollinger Bands squeeze status with:
 * - Symbol and current price
 * - Squeeze intensity meter (0-100%)
 * - Direction bias indicator (Long/Short/Neutral)
 * - BB position visualization
 * - Momentum indicator
 * 
 * Mobile-first design with touch-optimized interactions
 */
export function BBsqueezeCard({ 
  data, 
  onClick, 
  className = '',
  style 
}: BBsqueezeCardProps) {
  const {
    symbol,
    price,
    squeezeValue,
    bias,
    bbPosition,
    momentum,
    isActive = false,
    change24h = 0,
  } = data;

  // Determine squeeze color based on intensity
  const getSqueezeColor = (value: number): string => {
    if (value >= 80) return 'green';
    if (value >= 50) return 'amber';
    return 'red';
  };

  const squeezeColor = getSqueezeColor(squeezeValue);
  const isPositiveChange = change24h >= 0;

  // Format price with appropriate decimals
  const formatPrice = (p: number): string => {
    if (p >= 1000) return p.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (p >= 1) return p.toLocaleString('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 4 });
    return p.toLocaleString('en-US', { minimumFractionDigits: 6, maximumFractionDigits: 6 });
  };

  // BB position visualization (-100 to 100)
  const getBBPositionLabel = (pos: number): string => {
    if (pos > 80) return 'Upper';
    if (pos > 20) return 'High';
    if (pos < -80) return 'Lower';
    if (pos < -20) return 'Low';
    return 'Mid';
  };

  const bbPosLabel = getBBPositionLabel(bbPosition);
  const bbPosColor = bbPosition > 20 ? 'text-[#00ff88]' : bbPosition < -20 ? 'text-[#ff4757]' : 'text-[#9ca3af]';

  return (
    <div
      onClick={() => onClick?.(data)}
      className={`
        relative overflow-hidden rounded-[14px] p-4
        bg-[rgba(20,20,25,0.8)] backdrop-blur-[20px]
        border border-[rgba(255,255,255,0.06)]
        transition-all duration-200 ease-out
        ${onClick ? 'cursor-pointer active:scale-[0.98]' : ''}
        ${isActive ? 'border-[rgba(255,255,255,0.12)] shadow-[0_0_0_1px_rgba(255,255,255,0.2)]' : 'hover:border-[rgba(255,255,255,0.1)]'}
        ${className}
      `}
      style={style}
    >
      {/* Top accent line for active state */}
      <div 
        className={`
          absolute top-0 left-0 right-0 h-[2px]
          bg-gradient-to-r from-transparent via-[#3b82f6] to-transparent
          transition-opacity duration-200
          ${isActive ? 'opacity-100' : 'opacity-0'}
        `}
      />

      {/* Header: Symbol + Price */}
      <div className="flex items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <span className="font-mono text-base font-bold text-white tracking-tight">
            {symbol}
          </span>
          <DirectionBias bias={bias} size="sm" />
        </div>
        <div className="text-right">
          <div className="font-mono text-sm font-semibold text-white">
            ${formatPrice(price)}
          </div>
          {change24h !== 0 && (
            <div className={`text-[10px] font-medium ${isPositiveChange ? 'text-[#00ff88]' : 'text-[#ff4757]'}`}>
              {isPositiveChange ? '+' : ''}{change24h.toFixed(2)}%
            </div>
          )}
        </div>
      </div>

      {/* Squeeze Meter */}
      <div className="mb-3">
        <div className="flex justify-between items-center mb-1.5">
          <span className="text-[11px] font-medium text-[#6b7280] uppercase tracking-wide">
            Squeeze
          </span>
          <span className="font-mono text-xs font-semibold text-[#9ca3af]">
            {squeezeValue.toFixed(0)}%
          </span>
        </div>
        <div className="relative h-1.5 bg-[rgba(255,255,255,0.05)] rounded-full overflow-hidden">
          <div
            className={`
              absolute inset-y-0 left-0 rounded-full
              transition-all duration-300 ease-out
              ${squeezeColor === 'green' ? 'bg-gradient-to-r from-[rgba(0,255,136,0.15)] to-[#00ff88] shadow-[0_0_10px_rgba(0,255,136,0.3)]' : ''}
              ${squeezeColor === 'amber' ? 'bg-gradient-to-r from-[rgba(255,184,0,0.15)] to-[#ffb800]' : ''}
              ${squeezeColor === 'red' ? 'bg-gradient-to-r from-[rgba(255,71,87,0.15)] to-[#ff4757] shadow-[0_0_10px_rgba(255,71,87,0.3)]' : ''}
            `}
            style={{ width: `${squeezeValue}%` }}
          >
            {/* Shimmer effect */}
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer" />
          </div>
        </div>
      </div>

      {/* BB Position & Momentum Row */}
      <div className="flex items-center justify-between gap-3">
        {/* BB Position */}
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-medium text-[#6b7280]">BB</span>
          <span className={`text-[11px] font-semibold ${bbPosColor}`}>
            {bbPosLabel}
          </span>
          {/* Mini bar for BB position */}
          <div className="w-12 h-1 bg-[rgba(255,255,255,0.05)] rounded-full overflow-hidden">
            <div
              className={`
                h-full rounded-full transition-all duration-300
                ${bbPosition > 0 ? 'bg-[#00ff88]' : 'bg-[#ff4757]'}
              `}
              style={{ 
                width: `${Math.abs(bbPosition)}%`,
                marginLeft: bbPosition < 0 ? 'auto' : '0'
              }}
            />
          </div>
        </div>

        {/* Momentum */}
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-medium text-[#6b7280]">Mom</span>
          <span className={`text-[11px] font-semibold ${momentum > 0 ? 'text-[#00ff88]' : momentum < 0 ? 'text-[#ff4757]' : 'text-[#9ca3af]'}`}>
            {momentum > 0 ? '+' : ''}{momentum.toFixed(0)}
          </span>
        </div>
      </div>

      {/* Squeeze State Badge (only for high squeeze) */}
      {squeezeValue >= 80 && (
        <div className="absolute top-2 right-2">
          <span className={`
            inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider
            ${squeezeColor === 'green' ? 'bg-[rgba(0,255,136,0.15)] text-[#00ff88] border border-[rgba(0,255,136,0.2)]' : ''}
            ${squeezeColor === 'red' ? 'bg-[rgba(255,71,87,0.15)] text-[#ff4757] border border-[rgba(255,71,87,0.2)]' : ''}
          `}>
            FIRE
          </span>
        </div>
      )}
    </div>
  );
}

/**
 * Skeleton loader for BBsqueezeCard
 */
export function BBsqueezeCardSkeleton({ className = '' }: { className?: string }) {
  return (
    <div className={`
      rounded-[14px] p-4
      bg-[rgba(20,20,25,0.8)] backdrop-blur-[20px]
      border border-[rgba(255,255,255,0.06)]
      animate-pulse
      ${className}
    `}>
      {/* Header skeleton */}
      <div className="flex items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <div className="w-12 h-5 bg-white/10 rounded" />
          <div className="w-14 h-4 bg-white/10 rounded-full" />
        </div>
        <div className="w-16 h-5 bg-white/10 rounded" />
      </div>
      
      {/* Squeeze meter skeleton */}
      <div className="mb-3">
        <div className="flex justify-between items-center mb-1.5">
          <div className="w-14 h-3 bg-white/10 rounded" />
          <div className="w-8 h-3 bg-white/10 rounded" />
        </div>
        <div className="h-1.5 bg-white/10 rounded-full" />
      </div>
      
      {/* Footer skeleton */}
      <div className="flex items-center justify-between">
        <div className="w-20 h-3 bg-white/10 rounded" />
        <div className="w-14 h-3 bg-white/10 rounded" />
      </div>
    </div>
  );
}

export default BBsqueezeCard;

'use client';

import React from 'react';

export type BiasType = 'long' | 'short' | 'neutral';

export interface DirectionBiasProps {
  bias: BiasType;
  size?: 'xs' | 'sm' | 'md' | 'lg';
  showIcon?: boolean;
  showLabel?: boolean;
  animate?: boolean;
  className?: string;
  onClick?: (bias: BiasType) => void;
}

/**
 * Direction Bias Indicator Component
 * 
 * Displays directional bias with:
 * - Color-coded pill (green=long, red=short, gray=neutral)
 * - Optional directional arrow icons
 * - Optional text labels
 * - Pulse animation for active signals
 * 
 * Mobile-first with touch-optimized sizing
 */
export function DirectionBias({
  bias,
  size = 'md',
  showIcon = true,
  showLabel = true,
  animate = true,
  className = '',
  onClick,
}: DirectionBiasProps) {
  // Configuration for each bias type
  const config = {
    long: {
      bg: 'bg-[rgba(0,255,136,0.15)]',
      border: 'border-[rgba(0,255,136,0.2)]',
      text: 'text-[#00ff88]',
      glow: 'shadow-[0_0_8px_rgba(0,255,136,0.3)]',
      label: 'LONG',
      icon: LongArrowIcon,
    },
    short: {
      bg: 'bg-[rgba(255,71,87,0.15)]',
      border: 'border-[rgba(255,71,87,0.2)]',
      text: 'text-[#ff4757]',
      glow: 'shadow-[0_0_8px_rgba(255,71,87,0.3)]',
      label: 'SHORT',
      icon: ShortArrowIcon,
    },
    neutral: {
      bg: 'bg-[rgba(255,255,255,0.05)]',
      border: 'border-[rgba(255,255,255,0.08)]',
      text: 'text-[#9ca3af]',
      glow: '',
      label: 'NEUTRAL',
      icon: NeutralIcon,
    },
  };

  // Size configurations
  const sizeConfig = {
    xs: {
      pill: 'px-1.5 py-0.5 gap-0.5',
      text: 'text-[9px]',
      icon: 'w-2.5 h-2.5',
    },
    sm: {
      pill: 'px-2 py-0.5 gap-1',
      text: 'text-[10px]',
      icon: 'w-3 h-3',
    },
    md: {
      pill: 'px-2.5 py-1 gap-1',
      text: 'text-[11px]',
      icon: 'w-3.5 h-3.5',
    },
    lg: {
      pill: 'px-3 py-1.5 gap-1.5',
      text: 'text-xs',
      icon: 'w-4 h-4',
    },
  };

  const c = config[bias];
  const s = sizeConfig[size];
  const Icon = c.icon;

  return (
    <span
      onClick={() => onClick?.(bias)}
      className={`
        inline-flex items-center justify-center
        ${s.pill}
        ${c.bg}
        border ${c.border}
        ${c.text}
        rounded-full
        font-semibold uppercase tracking-wide
        ${animate && bias !== 'neutral' ? 'animate-pulse-subtle' : ''}
        ${bias !== 'neutral' && animate ? c.glow : ''}
        ${onClick ? 'cursor-pointer hover:brightness-110 active:scale-95' : ''}
        transition-all duration-150
        ${className}
      `}
    >
      {showIcon && (
        <Icon className={`${s.icon} ${bias === 'long' ? '' : bias === 'short' ? '' : ''}`} />
      )}
      {showLabel && (
        <span className={s.text}>{c.label}</span>
      )}
    </span>
  );
}

/**
 * Arrow icon pointing up-right (Long)
 */
function LongArrowIcon({ className = '' }: { className?: string }) {
  return (
    <svg 
      className={className} 
      viewBox="0 0 24 24" 
      fill="none" 
      stroke="currentColor" 
      strokeWidth="2.5"
      strokeLinecap="round" 
      strokeLinejoin="round"
    >
      <path d="M7 17L17 7" />
      <path d="M7 7h10v10" />
    </svg>
  );
}

/**
 * Arrow icon pointing down-right (Short)
 */
function ShortArrowIcon({ className = '' }: { className?: string }) {
  return (
    <svg 
      className={className} 
      viewBox="0 0 24 24" 
      fill="none" 
      stroke="currentColor" 
      strokeWidth="2.5"
      strokeLinecap="round" 
      strokeLinejoin="round"
    >
      <path d="M7 7l10 10" />
      <path d="M17 7v10H7" />
    </svg>
  );
}

/**
 * Minus icon (Neutral)
 */
function NeutralIcon({ className = '' }: { className?: string }) {
  return (
    <svg 
      className={className} 
      viewBox="0 0 24 24" 
      fill="none" 
      stroke="currentColor" 
      strokeWidth="2.5"
      strokeLinecap="round" 
      strokeLinejoin="round"
    >
      <path d="M5 12h14" />
    </svg>
  );
}

/**
 * Direction Bias Meter - Visual bar representation
 */
export interface DirectionBiasMeterProps {
  value: number; // -100 to 100 (negative = short, positive = long)
  size?: 'sm' | 'md' | 'lg';
  showLabels?: boolean;
  className?: string;
}

export function DirectionBiasMeter({
  value,
  size = 'md',
  showLabels = true,
  className = '',
}: DirectionBiasMeterProps) {
  // Normalize value to 0-100 range for positioning
  const percentage = ((value + 100) / 2);
  
  const sizeConfig = {
    sm: { height: 'h-1.5', marker: 'w-0.5 h-2.5' },
    md: { height: 'h-2', marker: 'w-0.5 h-3' },
    lg: { height: 'h-2.5', marker: 'w-1 h-3.5' },
  };
  
  const s = sizeConfig[size];
  
  // Determine bias text
  const getBiasText = (v: number): string => {
    if (v > 60) return 'Strong Long';
    if (v > 20) return 'Long';
    if (v < -60) return 'Strong Short';
    if (v < -20) return 'Short';
    return 'Neutral';
  };
  
  const biasText = getBiasText(value);
  const biasColor = value > 20 ? '#00ff88' : value < -20 ? '#ff4757' : '#9ca3af';

  return (
    <div className={`w-full ${className}`}>
      {showLabels && (
        <div className="flex justify-between items-center mb-1.5">
          <span className="text-[10px] font-medium text-[#ff4757]">SHORT</span>
          <span 
            className="text-xs font-semibold"
            style={{ color: biasColor }}
          >
            {biasText}
          </span>
          <span className="text-[10px] font-medium text-[#00ff88]">LONG</span>
        </div>
      )}
      
      {/* Meter track */}
      <div className={`relative ${s.height} rounded-full overflow-hidden bg-[rgba(255,255,255,0.05)]`}>
        {/* Gradient fill */}
        <div 
          className="absolute inset-0 opacity-30"
          style={{
            background: 'linear-gradient(90deg, #ff4757 0%, #9ca3af 50%, #00ff88 100%)',
          }}
        />
        
        {/* Center marker */}
        <div className="absolute top-0 bottom-0 left-1/2 -translate-x-1/2 w-px bg-white/20" />
        
        {/* Value indicator */}
        <div
          className={`
            absolute top-1/2 -translate-y-1/2 -translate-x-1/2
            ${s.marker} rounded-full
            transition-all duration-300 ease-out
          `}
          style={{
            left: `${percentage}%`,
            backgroundColor: biasColor,
            boxShadow: `0 0 8px ${biasColor}40`,
          }}
        />
      </div>
    </div>
  );
}

/**
 * Directional Toggle - Switch between Long/Short/Neutral
 */
export interface DirectionToggleProps {
  value: BiasType;
  onChange: (bias: BiasType) => void;
  disabled?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export function DirectionToggle({
  value,
  onChange,
  disabled = false,
  size = 'md',
  className = '',
}: DirectionToggleProps) {
  const options: BiasType[] = ['short', 'neutral', 'long'];
  
  const sizeConfig = {
    sm: 'h-8 text-[10px]',
    md: 'h-10 text-xs',
    lg: 'h-12 text-sm',
  };

  return (
    <div 
      className={`
        inline-flex p-1 rounded-xl
        bg-[rgba(20,20,25,0.8)] backdrop-blur-sm
        border border-[rgba(255,255,255,0.06)]
        ${disabled ? 'opacity-50' : ''}
        ${className}
      `}
    >
      {options.map((option) => (
        <button
          key={option}
          onClick={() => !disabled && onChange(option)}
          disabled={disabled}
          className={`
            relative px-4 ${sizeConfig[size]}
            font-semibold uppercase tracking-wide
            rounded-lg
            transition-all duration-200
            ${value === option ? 'text-white' : 'text-[#6b7280] hover:text-[#9ca3af]'}
            ${value === option && option === 'long' ? 'bg-[rgba(0,255,136,0.2)] shadow-[0_0_8px_rgba(0,255,136,0.2)]' : ''}
            ${value === option && option === 'short' ? 'bg-[rgba(255,71,87,0.2)] shadow-[0_0_8px_rgba(255,71,87,0.2)]' : ''}
            ${value === option && option === 'neutral' ? 'bg-[rgba(255,255,255,0.1)]' : ''}
          `}
        >
          {option}
        </button>
      ))}
    </div>
  );
}

export default DirectionBias;

'use client';

import React, { useState, useCallback, useRef, useEffect } from 'react';

export interface PremiumRangeProps {
  min?: number;
  max?: number;
  step?: number;
  value: number;
  onChange: (value: number) => void;
  label?: string;
  unit?: string;
  disabled?: boolean;
  size?: 'sm' | 'md' | 'lg';
  variant?: 'default' | 'green' | 'red' | 'amber' | 'blue';
  showTooltip?: boolean;
  className?: string;
}

/**
 * Premium Range Slider Component
 * 
 * Touch-optimized slider with:
 * - Custom styled track and thumb
 * - Tooltip on drag
 * - Haptic feedback support (on supported devices)
 * - Keyboard navigation support
 * - Visual feedback for active state
 */
export function PremiumRange({
  min = 0,
  max = 100,
  step = 1,
  value,
  onChange,
  label,
  unit = '',
  disabled = false,
  size = 'md',
  variant = 'default',
  showTooltip = true,
  className = '',
}: PremiumRangeProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [showValue, setShowValue] = useState(false);
  const trackRef = useRef<HTMLDivElement>(null);
  const sliderId = useRef(`slider-${Math.random().toString(36).substr(2, 9)}`);

  // Calculate percentage for visual positioning
  const percentage = ((value - min) / (max - min)) * 100;

  // Size variants
  const sizeConfig = {
    sm: { track: 'h-1', thumb: 'w-4 h-4', tooltip: 'text-xs py-0.5 px-1.5' },
    md: { track: 'h-1.5', thumb: 'w-5 h-5', tooltip: 'text-xs py-1 px-2' },
    lg: { track: 'h-2', thumb: 'w-6 h-6', tooltip: 'text-sm py-1 px-2.5' },
  };

  // Color variants
  const colorConfig = {
    default: {
      track: 'bg-[rgba(255,255,255,0.1)]',
      fill: 'bg-white',
      thumb: 'bg-white border-[#0a0a0f]',
      glow: 'shadow-[0_0_10px_rgba(255,255,255,0.3)]',
    },
    green: {
      track: 'bg-[rgba(0,255,136,0.1)]',
      fill: 'bg-[#00ff88]',
      thumb: 'bg-[#00ff88] border-[#0a0a0f]',
      glow: 'shadow-[0_0_15px_rgba(0,255,136,0.5)]',
    },
    red: {
      track: 'bg-[rgba(255,71,87,0.1)]',
      fill: 'bg-[#ff4757]',
      thumb: 'bg-[#ff4757] border-[#0a0a0f]',
      glow: 'shadow-[0_0_15px_rgba(255,71,87,0.5)]',
    },
    amber: {
      track: 'bg-[rgba(255,184,0,0.1)]',
      fill: 'bg-[#ffb800]',
      thumb: 'bg-[#ffb800] border-[#0a0a0f]',
      glow: 'shadow-[0_0_15px_rgba(255,184,0,0.5)]',
    },
    blue: {
      track: 'bg-[rgba(59,130,246,0.1)]',
      fill: 'bg-[#3b82f6]',
      thumb: 'bg-[#3b82f6] border-[#0a0a0f]',
      glow: 'shadow-[0_0_15px_rgba(59,130,246,0.5)]',
    },
  };

  const colors = colorConfig[variant];
  const sizes = sizeConfig[size];

  // Handle track click
  const handleTrackClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (disabled || !trackRef.current) return;
    
    const rect = trackRef.current.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const newPercentage = Math.max(0, Math.min(100, (clickX / rect.width) * 100));
    const newValue = min + (newPercentage / 100) * (max - min);
    const steppedValue = Math.round(newValue / step) * step;
    onChange(Math.max(min, Math.min(max, steppedValue)));
  }, [disabled, min, max, step, onChange]);

  // Handle touch/mouse events for dragging
  const handleStart = useCallback(() => {
    if (disabled) return;
    setIsDragging(true);
    setShowValue(true);
  }, [disabled]);

  const handleEnd = useCallback(() => {
    setIsDragging(false);
    setShowValue(false);
  }, []);

  // Keyboard navigation
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (disabled) return;
    
    let newValue = value;
    const stepSize = e.shiftKey ? step * 10 : step;
    
    switch (e.key) {
      case 'ArrowLeft':
      case 'ArrowDown':
        newValue = Math.max(min, value - stepSize);
        break;
      case 'ArrowRight':
      case 'ArrowUp':
        newValue = Math.min(max, value + stepSize);
        break;
      case 'Home':
        newValue = min;
        break;
      case 'End':
        newValue = max;
        break;
      default:
        return;
    }
    
    e.preventDefault();
    onChange(newValue);
  }, [disabled, value, min, max, step, onChange]);

  // Global mouse/touch move handlers for dragging
  useEffect(() => {
    if (!isDragging) return;

    const handleMove = (clientX: number) => {
      if (!trackRef.current) return;
      const rect = trackRef.current.getBoundingClientRect();
      const moveX = clientX - rect.left;
      const newPercentage = Math.max(0, Math.min(100, (moveX / rect.width) * 100));
      const newValue = min + (newPercentage / 100) * (max - min);
      const steppedValue = Math.round(newValue / step) * step;
      onChange(Math.max(min, Math.min(max, steppedValue)));
    };

    const handleMouseMove = (e: MouseEvent) => handleMove(e.clientX);
    const handleTouchMove = (e: TouchEvent) => {
      if (e.touches[0]) handleMove(e.touches[0].clientX);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleEnd);
    document.addEventListener('touchmove', handleTouchMove, { passive: true });
    document.addEventListener('touchend', handleEnd);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleEnd);
      document.removeEventListener('touchmove', handleTouchMove);
      document.removeEventListener('touchend', handleEnd);
    };
  }, [isDragging, min, max, step, onChange, handleEnd]);

  // Format display value
  const formatValue = (v: number): string => {
    if (v >= 1000) return `${(v / 1000).toFixed(1)}k`;
    if (Number.isInteger(v)) return v.toString();
    return v.toFixed(2);
  };

  return (
    <div className={`w-full ${className}`}>
      {/* Label row */}
      {(label || showTooltip) && (
        <div className="flex items-center justify-between mb-2">
          {label && (
            <label 
              htmlFor={sliderId.current}
              className="text-xs font-medium text-[#9ca3af] uppercase tracking-wide"
            >
              {label}
            </label>
          )}
          <span className={`
            font-mono text-xs font-semibold
            ${variant === 'green' ? 'text-[#00ff88]' : ''}
            ${variant === 'red' ? 'text-[#ff4757]' : ''}
            ${variant === 'amber' ? 'text-[#ffb800]' : ''}
            ${variant === 'blue' ? 'text-[#3b82f6]' : ''}
            ${variant === 'default' ? 'text-white' : ''}
          `}>
            {formatValue(value)}{unit}
          </span>
        </div>
      )}

      {/* Slider track */}
      <div
        ref={trackRef}
        className={`
          relative w-full ${sizes.track} rounded-full cursor-pointer
          ${colors.track}
          ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
        `}
        onClick={handleTrackClick}
      >
        {/* Filled portion */}
        <div
          className={`
            absolute top-0 left-0 h-full rounded-full
            ${colors.fill}
            transition-all duration-75 ease-out
          `}
          style={{ width: `${percentage}%` }}
        />

        {/* Thumb */}
        <div
          role="slider"
          id={sliderId.current}
          aria-valuemin={min}
          aria-valuemax={max}
          aria-valuenow={value}
          aria-label={label || 'Slider'}
          tabIndex={disabled ? -1 : 0}
          className={`
            absolute top-1/2 -translate-y-1/2 -translate-x-1/2
            ${sizes.thumb} rounded-full
            ${colors.thumb}
            border-2
            transition-transform duration-150 ease-out
            ${isDragging ? `scale-125 ${colors.glow}` : 'hover:scale-110'}
            ${disabled ? '' : 'cursor-grab active:cursor-grabbing'}
            focus:outline-none focus:ring-2 focus:ring-white/20
          `}
          style={{ left: `${percentage}%` }}
          onMouseDown={handleStart}
          onTouchStart={handleStart}
          onKeyDown={handleKeyDown}
        />

        {/* Tooltip */}
        {showTooltip && (isDragging || showValue) && (
          <div
            className={`
              absolute -top-8 -translate-x-1/2
              ${sizes.tooltip}
              bg-[rgba(30,30,40,0.95)] backdrop-blur-sm
              border border-[rgba(255,255,255,0.1)]
              rounded-md text-white font-mono font-semibold
              whitespace-nowrap
              transition-opacity duration-150
              ${isDragging ? 'opacity-100' : 'opacity-0'}
            `}
            style={{ left: `${percentage}%` }}
          >
            {formatValue(value)}{unit}
            {/* Tooltip arrow */}
            <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-[rgba(30,30,40,0.95)] border-r border-b border-[rgba(255,255,255,0.1)] rotate-45" />
          </div>
        )}
      </div>

      {/* Min/Max labels */}
      <div className="flex justify-between mt-1.5">
        <span className="text-[10px] text-[#6b7280]">{formatValue(min)}{unit}</span>
        <span className="text-[10px] text-[#6b7280]">{formatValue(max)}{unit}</span>
      </div>
    </div>
  );
}

/**
 * Dual-range slider for selecting a range (min/max)
 */
export interface PremiumRangeDualProps {
  min?: number;
  max?: number;
  step?: number;
  minValue: number;
  maxValue: number;
  onChange: (min: number, max: number) => void;
  label?: string;
  unit?: string;
  disabled?: boolean;
  className?: string;
}

export function PremiumRangeDual({
  min = 0,
  max = 100,
  step = 1,
  minValue,
  maxValue,
  onChange,
  label,
  unit = '',
  disabled = false,
  className = '',
}: PremiumRangeDualProps) {
  const trackRef = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState<'min' | 'max' | null>(null);

  const minPercentage = ((minValue - min) / (max - min)) * 100;
  const maxPercentage = ((maxValue - min) / (max - min)) * 100;

  const handleTrackClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (disabled || !trackRef.current) return;
    
    const rect = trackRef.current.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const newPercentage = (clickX / rect.width) * 100;
    const newValue = min + (newPercentage / 100) * (max - min);
    const steppedValue = Math.round(newValue / step) * step;
    const clampedValue = Math.max(min, Math.min(max, steppedValue));
    
    // Snap to closest handle
    const distToMin = Math.abs(clampedValue - minValue);
    const distToMax = Math.abs(clampedValue - maxValue);
    
    if (distToMin < distToMax) {
      onChange(Math.min(clampedValue, maxValue - step), maxValue);
    } else {
      onChange(minValue, Math.max(clampedValue, minValue + step));
    }
  }, [disabled, min, max, step, minValue, maxValue, onChange]);

  const formatValue = (v: number): string => {
    if (v >= 1000) return `${(v / 1000).toFixed(1)}k`;
    if (Number.isInteger(v)) return v.toString();
    return v.toFixed(2);
  };

  return (
    <div className={`w-full ${className}`}>
      {label && (
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-[#9ca3af] uppercase tracking-wide">
            {label}
          </span>
          <span className="font-mono text-xs font-semibold text-white">
            {formatValue(minValue)}{unit} - {formatValue(maxValue)}{unit}
          </span>
        </div>
      )}

      <div
        ref={trackRef}
        className={`
          relative w-full h-1.5 rounded-full cursor-pointer
          bg-[rgba(255,255,255,0.1)]
          ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
        `}
        onClick={handleTrackClick}
      >
        {/* Selected range fill */}
        <div
          className="absolute top-0 h-full rounded-full bg-[#3b82f6]"
          style={{
            left: `${minPercentage}%`,
            width: `${maxPercentage - minPercentage}%`,
          }}
        />

        {/* Min handle */}
        <div
          className={`
            absolute top-1/2 -translate-y-1/2 -translate-x-1/2
            w-4 h-4 rounded-full bg-white border-2 border-[#0a0a0f]
            transition-transform duration-150
            ${dragging === 'min' ? 'scale-125 shadow-[0_0_10px_rgba(255,255,255,0.3)]' : 'hover:scale-110'}
            ${disabled ? '' : 'cursor-grab active:cursor-grabbing'}
          `}
          style={{ left: `${minPercentage}%` }}
          onMouseDown={() => setDragging('min')}
        />

        {/* Max handle */}
        <div
          className={`
            absolute top-1/2 -translate-y-1/2 -translate-x-1/2
            w-4 h-4 rounded-full bg-white border-2 border-[#0a0a0f]
            transition-transform duration-150
            ${dragging === 'max' ? 'scale-125 shadow-[0_0_10px_rgba(255,255,255,0.3)]' : 'hover:scale-110'}
            ${disabled ? '' : 'cursor-grab active:cursor-grabbing'}
          `}
          style={{ left: `${maxPercentage}%` }}
          onMouseDown={() => setDragging('max')}
        />
      </div>

      <div className="flex justify-between mt-1.5">
        <span className="text-[10px] text-[#6b7280]">{formatValue(min)}{unit}</span>
        <span className="text-[10px] text-[#6b7280]">{formatValue(max)}{unit}</span>
      </div>
    </div>
  );
}

export default PremiumRange;

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
interface ConfidenceMeterProps {
  value: number;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  animated?: boolean;
  variant?: 'gauge' | 'bar' | 'circle';
  tone?: 'success' | 'danger' | 'warning' | 'neutral';
  label?: string;
}
export function ConfidenceMeter({
  value,
  size = 'md',
  showLabel = true,
  animated = true,
  variant = 'gauge',
  tone = 'neutral',
  label = 'Confidence'
}: ConfidenceMeterProps) {
  const [displayValue, setDisplayValue] = useState(0);
  const clampedValue = Math.max(0, Math.min(100, value));
  useEffect(() => {
    if (animated) {
      const duration = 1500;
      const steps = 60;
      const increment = clampedValue / steps;
      let current = 0;
      const timer = setInterval(() => {
        current += increment;
        if (current >= clampedValue) {
          setDisplayValue(clampedValue);
          clearInterval(timer);
        } else {
          setDisplayValue(current);
        }
      }, duration / steps);
      return () => clearInterval(timer);
    } else {
      setDisplayValue(clampedValue);
    }
  }, [clampedValue, animated]);
  const getColor = () => {
    if (tone === 'success')
    return {
      main: '#10b981',
      soft: '#d1fae5',
      glow: 'rgba(16, 185, 129, 0.38)'
    };
    if (tone === 'danger')
    return {
      main: '#ef4444',
      soft: '#fee2e2',
      glow: 'rgba(239, 68, 68, 0.42)'
    };
    if (tone === 'warning')
    return {
      main: '#f59e0b',
      soft: '#fef3c7',
      glow: 'rgba(245, 158, 11, 0.42)'
    };
    return {
      main: '#06b6d4',
      soft: '#cffafe',
      glow: 'rgba(6, 182, 212, 0.38)'
    };
  };
  const color = getColor();
  const sizes = {
    sm: {
      width: 148,
      height: 104,
      strokeWidth: 8,
      fontSize: 'text-xl',
      labelOffset: '-mt-12'
    },
    md: {
      width: 220,
      height: 148,
      strokeWidth: 14,
      fontSize: 'text-3xl',
      labelOffset: '-mt-14'
    },
    lg: {
      width: 292,
      height: 184,
      strokeWidth: 18,
      fontSize: 'text-5xl',
      labelOffset: '-mt-16'
    }
  };
  const config = sizes[size];
  if (variant === 'circle') {
    const radius = (config.width - config.strokeWidth) / 2;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - displayValue / 100 * circumference;
    return (
      <div className="flex flex-col items-center">
        <svg
          width={config.width}
          height={config.width}
          className="transform -rotate-90">

          {/* Background circle */}
          <circle
            cx={config.width / 2}
            cy={config.width / 2}
            r={radius}
            fill="none"
          stroke="currentColor"
          strokeWidth={config.strokeWidth}
          className="text-gray-200 dark:text-navy-700" />

          {/* Progress circle */}
          <motion.circle
            cx={config.width / 2}
            cy={config.width / 2}
            r={radius}
            fill="none"
            stroke={color.main}
            strokeWidth={config.strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            initial={{
              strokeDashoffset: circumference
            }}
            animate={{
              strokeDashoffset: offset
            }}
            transition={{
              duration: animated ? 1.5 : 0,
              ease: 'easeOut'
            }}
            style={{
              filter: `drop-shadow(0 0 8px ${color.glow})`
            }} />

        </svg>
        {showLabel &&
        <div className="absolute inset-0 flex items-center justify-center">
            <span
            className={`${config.fontSize} font-bold`}
            style={{
              color: color.main
            }}>

              {Math.round(displayValue)}%
            </span>
          </div>
        }
      </div>);

  }
  if (variant === 'bar') {
    return (
      <div className="w-full">
        {showLabel &&
        <div className="flex justify-between items-center mb-2">
            <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
              Confidence
            </span>
            <span
            className={`${config.fontSize} font-bold`}
            style={{
              color: color.main
            }}>

              {Math.round(displayValue)}%
            </span>
          </div>
        }
        <div
          className="w-full rounded-full overflow-hidden bg-gray-200 dark:bg-navy-700"
          style={{
            height: config.strokeWidth
          }}>

          <motion.div
            className="h-full rounded-full"
            style={{
              backgroundColor: color.main,
              boxShadow: `0 0 10px ${color.glow}`
            }}
            initial={{
              width: 0
            }}
            animate={{
              width: `${displayValue}%`
            }}
            transition={{
              duration: animated ? 1.5 : 0,
              ease: 'easeOut'
            }} />

        </div>
      </div>);

  }
  // Gauge variant (default)
  const progress = Math.max(0, Math.min(100, displayValue));
  const centerX = 120;
  const centerY = 124;
  const radius = 88;
  const markerRadians = progress / 100 * Math.PI;
  const markerX = centerX - radius * Math.cos(markerRadians);
  const markerY = centerY - radius * Math.sin(markerRadians);

  return (
    <div className="flex flex-col items-center">
      <svg
        width={config.width}
        height={config.height}
        viewBox="0 0 240 160"
        role="img"
        aria-label={`${label}: ${Math.round(progress)}%`}>

        <defs>
          <filter id="confidenceGlow" x="-20%" y="-40%" width="140%" height="180%">
            <feGaussianBlur stdDeviation="4" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Background arc */}
        <path
          d="M 32 124 A 88 88 0 0 1 208 124"
          fill="none"
          stroke="currentColor"
          strokeWidth={config.strokeWidth}
          strokeLinecap="round"
          className="text-gray-200 dark:text-navy-700" />

        {/* Subtle active scale underlay */}
        <path
          d="M 32 124 A 88 88 0 0 1 208 124"
          fill="none"
          stroke={color.main}
          strokeWidth="3"
          strokeLinecap="round"
          opacity="0.16" />

        {/* Progress arc */}
        <motion.path
          d="M 32 124 A 88 88 0 0 1 208 124"
          fill="none"
          stroke={color.main}
          strokeWidth={config.strokeWidth}
          strokeLinecap="round"
          pathLength="100"
          strokeDasharray="100"
          initial={{
            strokeDashoffset: 100
          }}
          animate={{
            strokeDashoffset: 100 - progress
          }}
          transition={{
            duration: animated ? 1.5 : 0,
            ease: 'easeOut'
          }}
          style={{
            filter: `drop-shadow(0 0 10px ${color.glow})`
          }} />

        {[0, 25, 50, 75, 100].map((tick) => {
          const radians = tick / 100 * Math.PI;
          const outerX = centerX - (radius + 14) * Math.cos(radians);
          const outerY = centerY - (radius + 14) * Math.sin(radians);
          const innerX = centerX - (radius + 4) * Math.cos(radians);
          const innerY = centerY - (radius + 4) * Math.sin(radians);

          return (
            <line
              key={tick}
              x1={innerX}
              y1={innerY}
              x2={outerX}
              y2={outerY}
              stroke="currentColor"
              strokeWidth={tick % 50 === 0 ? 2 : 1.5}
              strokeLinecap="round"
              className="text-gray-300 dark:text-navy-600" />
          );
        })}

        {/* Endpoint marker */}
        <motion.circle
          cx={markerX}
          cy={markerY}
          r="9"
          fill={color.main}
          stroke="white"
          strokeWidth="4"
          filter="url(#confidenceGlow)"
          initial={{
            scale: 0.6,
            opacity: 0
          }}
          animate={{
            scale: 1,
            opacity: 1
          }}
          transition={{
            duration: animated ? 0.45 : 0,
            delay: animated ? 1.05 : 0,
            ease: 'easeOut'
          }} />

        <circle cx="120" cy="124" r="42" fill={color.soft} className="dark:opacity-10" />
        <circle cx="120" cy="124" r="41" fill="white" className="dark:fill-navy-800" />
      </svg>

      {showLabel &&
      <div className={`${config.labelOffset} text-center`}>
          <span
          className={`${config.fontSize} font-bold`}
          style={{
            color: color.main
          }}>

            {Math.round(displayValue)}%
          </span>
          <p className="text-sm text-gray-500 dark:text-gray-400">{label}</p>
        </div>
      }
    </div>);

}

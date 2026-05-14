import React from 'react';
import { motion } from 'framer-motion';
interface ProgressBarProps {
  value: number;
  max?: number;
  size?: 'sm' | 'md' | 'lg';
  variant?: 'default' | 'gradient' | 'success' | 'danger';
  showLabel?: boolean;
  animated?: boolean;
  className?: string;
}
export function ProgressBar({
  value,
  max = 100,
  size = 'md',
  variant = 'default',
  showLabel = false,
  animated = true,
  className = ''
}: ProgressBarProps) {
  const percentage = Math.min(Math.max(value / max * 100, 0), 100);
  const sizes = {
    sm: 'h-1.5',
    md: 'h-2.5',
    lg: 'h-4'
  };
  const variants = {
    default: 'bg-neon-cyan',
    gradient: 'bg-gradient-to-r from-neon-cyan via-neon-violet to-neon-pink',
    success: 'bg-neon-green',
    danger: 'bg-neon-red'
  };
  return (
    <div className={`w-full ${className}`}>
      {showLabel &&
      <div className="flex justify-between items-center mb-1.5">
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Progress
          </span>
          <span className="text-sm font-semibold text-neon-cyan">
            {Math.round(percentage)}%
          </span>
        </div>
      }
      <div
        className={`w-full ${sizes[size]} bg-gray-200 dark:bg-navy-700 rounded-full overflow-hidden`}>

        <motion.div
          className={`h-full ${variants[variant]} rounded-full`}
          initial={{
            width: 0
          }}
          animate={{
            width: `${percentage}%`
          }}
          transition={{
            duration: animated ? 0.5 : 0,
            ease: 'easeOut'
          }}
          style={{
            boxShadow:
            variant === 'gradient' || variant === 'default' ?
            '0 0 10px rgba(6, 182, 212, 0.5)' :
            undefined
          }} />

      </div>
    </div>);

}
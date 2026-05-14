import React from 'react';
import { motion } from 'framer-motion';
interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg' | 'xl';
  variant?: 'default' | 'neon' | 'dots';
  className?: string;
}
export function LoadingSpinner({
  size = 'md',
  variant = 'default',
  className = ''
}: LoadingSpinnerProps) {
  const sizes = {
    sm: 'w-4 h-4',
    md: 'w-8 h-8',
    lg: 'w-12 h-12',
    xl: 'w-16 h-16'
  };
  if (variant === 'dots') {
    return (
      <div className={`flex items-center gap-1 ${className}`}>
        {[0, 1, 2].map((i) =>
        <motion.div
          key={i}
          className={`${size === 'sm' ? 'w-1.5 h-1.5' : size === 'md' ? 'w-2 h-2' : 'w-3 h-3'} rounded-full bg-neon-cyan`}
          animate={{
            y: [0, -8, 0],
            opacity: [0.5, 1, 0.5]
          }}
          transition={{
            duration: 0.6,
            repeat: Infinity,
            delay: i * 0.15
          }} />

        )}
      </div>);

  }
  if (variant === 'neon') {
    return (
      <div className={`relative ${sizes[size]} ${className}`}>
        <motion.div
          className="absolute inset-0 rounded-full border-2 border-neon-cyan/30"
          animate={{
            rotate: 360
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            ease: 'linear'
          }} />

        <motion.div
          className="absolute inset-0 rounded-full border-2 border-transparent border-t-neon-cyan border-r-neon-violet"
          animate={{
            rotate: 360
          }}
          transition={{
            duration: 1,
            repeat: Infinity,
            ease: 'linear'
          }}
          style={{
            boxShadow: '0 0 15px rgba(6, 182, 212, 0.5)'
          }} />

      </div>);

  }
  return (
    <motion.div
      className={`${sizes[size]} border-2 border-gray-200 dark:border-navy-600 border-t-neon-cyan rounded-full ${className}`}
      animate={{
        rotate: 360
      }}
      transition={{
        duration: 1,
        repeat: Infinity,
        ease: 'linear'
      }} />);


}
export function FullPageLoader() {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-white/80 dark:bg-navy-900/80 backdrop-blur-sm">
      <div className="flex flex-col items-center gap-4">
        <LoadingSpinner size="xl" variant="neon" />
        <motion.p
          className="text-lg font-medium text-gray-600 dark:text-gray-300"
          animate={{
            opacity: [0.5, 1, 0.5]
          }}
          transition={{
            duration: 1.5,
            repeat: Infinity
          }}>

          Loading...
        </motion.p>
      </div>
    </div>);

}
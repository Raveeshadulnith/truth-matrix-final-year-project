import React from 'react';
interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'success' | 'danger' | 'warning' | 'info' | 'outline';
  size?: 'sm' | 'md' | 'lg';
  glow?: boolean;
  className?: string;
}
export function Badge({
  children,
  variant = 'default',
  size = 'md',
  glow = false,
  className = ''
}: BadgeProps) {
  const baseStyles = 'inline-flex items-center font-semibold rounded-full';
  const variants = {
    default: 'bg-gray-100 text-gray-800 dark:bg-navy-700 dark:text-gray-200',
    success:
    'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400',
    danger: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
    warning:
    'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400',
    info: 'bg-cyan-100 text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-400',
    outline: 'bg-transparent border-2 border-current'
  };
  const sizes = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-3 py-1 text-sm',
    lg: 'px-4 py-1.5 text-base'
  };
  const glowStyles = glow ?
  variant === 'success' ?
  'shadow-neon-green' :
  variant === 'danger' ?
  'shadow-neon-red' :
  variant === 'info' ?
  'shadow-neon-cyan' :
  '' :
  '';
  return (
    <span
      className={`${baseStyles} ${variants[variant]} ${sizes[size]} ${glowStyles} ${className}`}>

      {children}
    </span>);

}
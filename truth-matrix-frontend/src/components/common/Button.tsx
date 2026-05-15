import React from 'react';
import { motion } from 'framer-motion';
import { Loader2Icon } from 'lucide-react';
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'success';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  glow?: boolean;
  children: React.ReactNode;
}
export function Button({
  variant = 'primary',
  size = 'md',
  isLoading = false,
  leftIcon,
  rightIcon,
  glow = false,
  children,
  className = '',
  disabled,
  ...props
}: ButtonProps) {
  const baseStyles = `
    inline-flex items-center justify-center font-semibold rounded-xl
    transition-all duration-200 ease-out
    focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2
    disabled:opacity-50 disabled:cursor-not-allowed
  `;
  const variants = {
    primary: `
      bg-gradient-to-r from-neon-cyan to-neon-violet text-white
      hover:shadow-neon-cyan hover:scale-[1.02]
      focus-visible:ring-neon-cyan
      dark:from-neon-cyan dark:to-neon-violet
    `,
    secondary: `
      bg-transparent border-2 border-neon-cyan text-neon-cyan
      hover:bg-neon-cyan/10 hover:shadow-neon-cyan
      focus-visible:ring-neon-cyan
      dark:border-neon-cyan dark:text-neon-cyan
    `,
    ghost: `
      bg-transparent text-gray-700 dark:text-gray-300
      hover:bg-gray-100 dark:hover:bg-navy-700
      focus-visible:ring-gray-400
    `,
    danger: `
      bg-neon-red text-white
      hover:bg-red-600 hover:shadow-neon-red
      focus-visible:ring-neon-red
    `,
    success: `
      bg-neon-green text-white
      hover:bg-emerald-600 hover:shadow-neon-green
      focus-visible:ring-neon-green
    `
  };
  const sizes = {
    sm: 'px-3 py-1.5 text-sm gap-1.5',
    md: 'px-5 py-2.5 text-base gap-2',
    lg: 'px-8 py-3.5 text-lg gap-2.5'
  };
  const glowStyles = glow ? 'animate-glow' : '';
  return (
    <motion.button
      whileTap={{
        scale: 0.98
      }}
      className={`${baseStyles} ${variants[variant]} ${sizes[size]} ${glowStyles} ${className}`}
      disabled={disabled || isLoading}
      {...props}>

      {isLoading && <Loader2Icon className="w-5 h-5 animate-spin" />}
      {!isLoading && leftIcon && <span className="flex-shrink-0">{leftIcon}</span>}
      {children}
      {!isLoading && rightIcon && <span className="flex-shrink-0">{rightIcon}</span>}
    </motion.button>);

}

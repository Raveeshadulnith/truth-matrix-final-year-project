import type { ReactNode } from 'react';
import { motion } from 'framer-motion';
interface CardProps {
  children: ReactNode;
  className?: string;
  variant?: 'default' | 'glass' | 'bordered' | 'elevated';
  hover?: boolean;
  padding?: 'none' | 'sm' | 'md' | 'lg';
  onClick?: () => void;
}
export function Card({
  children,
  className = '',
  variant = 'default',
  hover = false,
  padding = 'md',
  onClick
}: CardProps) {
  const baseStyles = 'rounded-2xl overflow-hidden';
  const variants = {
    default:
    'bg-white dark:bg-navy-800 border border-gray-200 dark:border-navy-700',
    glass: 'glass-card',
    bordered: 'bg-transparent border-2 border-gray-200 dark:border-navy-600',
    elevated: 'bg-white dark:bg-navy-800 shadow-lg dark:shadow-glass-dark'
  };
  const paddings = {
    none: '',
    sm: 'p-4',
    md: 'p-6',
    lg: 'p-8'
  };
  const hoverStyles = hover ?
  'cursor-pointer transition-all duration-300 hover:shadow-lg hover:border-neon-cyan/50 dark:hover:border-neon-cyan/30 hover:-translate-y-1' :
  '';
  const Component = hover ? motion.div : 'div';
  const motionProps = hover ?
  {
    whileHover: {
      scale: 1.02
    },
    whileTap: {
      scale: 0.98
    }
  } :
  {};
  return (
    <Component
      className={`${baseStyles} ${variants[variant]} ${paddings[padding]} ${hoverStyles} ${className}`}
      onClick={onClick}
      {...motionProps}>

      {children}
    </Component>);

}

import React from 'react';
import { motion } from 'framer-motion';
import { SunIcon, MoonIcon, MonitorIcon } from 'lucide-react';
import { useUIStore } from '../../store/uiStore';
interface ThemeToggleProps {
  showLabel?: boolean;
  size?: 'sm' | 'md' | 'lg';
}
export function ThemeToggle({
  showLabel = false,
  size = 'md'
}: ThemeToggleProps) {
  const { theme, setTheme } = useUIStore();
  const themes = [
  {
    value: 'light' as const,
    icon: SunIcon,
    label: 'Light'
  },
  {
    value: 'dark' as const,
    icon: MoonIcon,
    label: 'Dark'
  },
  {
    value: 'system' as const,
    icon: MonitorIcon,
    label: 'System'
  }];

  const sizes = {
    sm: 'p-1.5',
    md: 'p-2',
    lg: 'p-2.5'
  };
  const iconSizes = {
    sm: 'w-4 h-4',
    md: 'w-5 h-5',
    lg: 'w-6 h-6'
  };
  if (showLabel) {
    return (
      <div className="flex items-center gap-1 p-1 rounded-xl bg-gray-100 dark:bg-navy-800">
        {themes.map(({ value, icon: Icon, label }) =>
        <button
          key={value}
          onClick={() => setTheme(value)}
          className={`
              flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium
              transition-all duration-200
              ${theme === value ? 'bg-white dark:bg-navy-700 text-gray-900 dark:text-white shadow-sm' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}
            `}>

            <Icon className={iconSizes[size]} />
            {label}
          </button>
        )}
      </div>);

  }
  const cycleTheme = () => {
    const order: ('light' | 'dark' | 'system')[] = ['light', 'dark', 'system'];
    const currentIndex = order.indexOf(theme);
    const nextIndex = (currentIndex + 1) % order.length;
    setTheme(order[nextIndex]);
  };
  const currentTheme = themes.find((t) => t.value === theme)!;
  const Icon = currentTheme.icon;
  return (
    <motion.button
      whileTap={{
        scale: 0.95
      }}
      onClick={cycleTheme}
      className={`
        ${sizes[size]} rounded-xl
        bg-gray-100 dark:bg-navy-800
        text-gray-600 dark:text-gray-300
        hover:bg-gray-200 dark:hover:bg-navy-700
        transition-colors duration-200
      `}
      title={`Current: ${currentTheme.label}. Click to change.`}>

      <Icon className={iconSizes[size]} />
    </motion.button>);

}
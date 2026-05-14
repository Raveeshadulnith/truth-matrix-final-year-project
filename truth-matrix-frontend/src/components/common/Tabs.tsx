import React, { useState } from 'react';
import { motion } from 'framer-motion';
interface Tab {
  id: string;
  label: string;
  icon?: React.ReactNode;
  content: React.ReactNode;
  disabled?: boolean;
}
interface TabsProps {
  tabs: Tab[];
  defaultTab?: string;
  variant?: 'default' | 'pills' | 'underline';
  onChange?: (tabId: string) => void;
  className?: string;
}
export function Tabs({
  tabs,
  defaultTab,
  variant = 'default',
  onChange,
  className = ''
}: TabsProps) {
  const [activeTab, setActiveTab] = useState(defaultTab || tabs[0]?.id);
  const handleTabChange = (tabId: string) => {
    setActiveTab(tabId);
    onChange?.(tabId);
  };
  const activeContent = tabs.find((tab) => tab.id === activeTab)?.content;
  const tabListStyles = {
    default: 'flex gap-1 p-1 bg-gray-100 dark:bg-navy-800 rounded-xl',
    pills: 'flex gap-2',
    underline: 'flex gap-6 border-b border-gray-200 dark:border-navy-700'
  };
  const getTabStyles = (isActive: boolean, isDisabled: boolean) => {
    const base =
    'flex items-center gap-2 font-medium transition-all duration-200';
    if (isDisabled) {
      return `${base} opacity-50 cursor-not-allowed`;
    }
    const variants = {
      default: isActive ?
      'px-4 py-2 rounded-lg bg-white dark:bg-navy-700 text-gray-900 dark:text-white shadow-sm' :
      'px-4 py-2 rounded-lg text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300',
      pills: isActive ?
      'px-4 py-2 rounded-full bg-neon-cyan text-white shadow-neon-cyan' :
      'px-4 py-2 rounded-full text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-navy-800',
      underline: isActive ?
      'pb-3 text-neon-cyan border-b-2 border-neon-cyan -mb-px' :
      'pb-3 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
    };
    return `${base} ${variants[variant]}`;
  };
  return (
    <div className={className}>
      <div className={tabListStyles[variant]} role="tablist">
        {tabs.map((tab) =>
        <button
          key={tab.id}
          role="tab"
          aria-selected={activeTab === tab.id}
          aria-controls={`tabpanel-${tab.id}`}
          disabled={tab.disabled}
          onClick={() => !tab.disabled && handleTabChange(tab.id)}
          className={getTabStyles(activeTab === tab.id, !!tab.disabled)}>

            {tab.icon}
            {tab.label}
          </button>
        )}
      </div>

      <motion.div
        key={activeTab}
        initial={{
          opacity: 0,
          y: 10
        }}
        animate={{
          opacity: 1,
          y: 0
        }}
        transition={{
          duration: 0.2
        }}
        role="tabpanel"
        id={`tabpanel-${activeTab}`}
        className="mt-4">

        {activeContent}
      </motion.div>
    </div>);

}
import { motion } from 'framer-motion';
import {
  ScanIcon,
  ShieldAlertIcon,
  ShieldCheckIcon,
  TargetIcon
} from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { useAnalysisStore } from '../../store/analysisStore';
export function StatsCards() {
  const { user } = useAuthStore();
  const { analyses } = useAnalysisStore();
  const deepfakesFound = analyses.filter((a) => a.result === 'fake').length;
  const authenticResults = analyses.filter((a) => a.result === 'real').length;
  const accuracyRate =
  analyses.length > 0 ?
  (
  analyses.filter((a) => a.confidence > 80).length / analyses.length *
  100).
  toFixed(1) :
  '0';
  const stats = [
  {
    label: 'Total Analyses',
    value: user?.totalAnalyses || analyses.length,
    icon: ScanIcon,
    color: 'from-neon-cyan to-blue-500',
    bgColor: 'bg-cyan-50 dark:bg-cyan-900/20',
    iconColor: 'text-neon-cyan'
  },
  {
    label: 'Deepfakes Found',
    value: deepfakesFound,
    icon: ShieldAlertIcon,
    color: 'from-neon-red to-pink-500',
    bgColor: 'bg-red-50 dark:bg-red-900/20',
    iconColor: 'text-neon-red'
  },
  {
    label: 'Authentic Results',
    value: authenticResults,
    icon: ShieldCheckIcon,
    color: 'from-neon-violet to-purple-500',
    bgColor: 'bg-violet-50 dark:bg-violet-900/20',
    iconColor: 'text-neon-violet'
  },
  {
    label: 'Accuracy Rate',
    value: `${accuracyRate}%`,
    icon: TargetIcon,
    color: 'from-neon-green to-emerald-500',
    bgColor: 'bg-emerald-50 dark:bg-emerald-900/20',
    iconColor: 'text-neon-green'
  }];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 lg:gap-6">
      {stats.map((stat, index) =>
      <motion.div
        key={stat.label}
        initial={{
          opacity: 0,
          y: 20
        }}
        animate={{
          opacity: 1,
          y: 0
        }}
        transition={{
          delay: index * 0.1
        }}
        className="relative overflow-hidden rounded-2xl bg-white dark:bg-navy-800 border border-gray-200 dark:border-navy-700 p-6">

          {/* Background gradient */}
          <div
          className={`absolute top-0 right-0 w-32 h-32 rounded-full bg-gradient-to-br ${stat.color} opacity-10 blur-2xl -translate-y-1/2 translate-x-1/2`} />


          <div className="relative flex items-start justify-between">
            <div>
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">
                {stat.label}
              </p>
              <p className="text-3xl font-bold text-gray-900 dark:text-white">
                {stat.value}
              </p>
            </div>
            <div className={`p-3 rounded-xl ${stat.bgColor}`}>
              <stat.icon className={`w-6 h-6 ${stat.iconColor}`} />
            </div>
          </div>
        </motion.div>
      )}
    </div>);

}

import React from 'react';
import { motion } from 'framer-motion';
import { useAnalysisStore } from '../../store/analysisStore';
export function ActivityChart() {
  const { analyses } = useAnalysisStore();
  // Generate last 7 days data
  const last7Days = Array.from(
    {
      length: 7
    },
    (_, i) => {
      const date = new Date();
      date.setDate(date.getDate() - (6 - i));
      return {
        date: date.toLocaleDateString('en-US', {
          weekday: 'short'
        }),
        fullDate: date.toISOString().split('T')[0]
      };
    }
  );
  // Count analyses per day
  const chartData = last7Days.map((day) => {
    const dayAnalyses = analyses.filter((a) => {
      const analysisDate = new Date(a.createdAt).toISOString().split('T')[0];
      return analysisDate === day.fullDate;
    });
    return {
      ...day,
      total: dayAnalyses.length,
      fake: dayAnalyses.filter((a) => a.result === 'fake').length,
      real: dayAnalyses.filter((a) => a.result === 'real').length
    };
  });
  const maxValue = Math.max(...chartData.map((d) => d.total), 5);
  return (
    <div className="rounded-2xl bg-white dark:bg-navy-800 border border-gray-200 dark:border-navy-700 p-6">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-6">
        Activity (Last 7 Days)
      </h3>

      <div className="flex items-end justify-between gap-2 h-40">
        {chartData.map((day, index) =>
        <div
          key={day.date}
          className="flex-1 flex flex-col items-center gap-2">

            <div className="relative w-full flex flex-col items-center justify-end h-32">
              {/* Bar */}
              <motion.div
              initial={{
                height: 0
              }}
              animate={{
                height: `${day.total / maxValue * 100}%`
              }}
              transition={{
                delay: index * 0.1,
                duration: 0.5
              }}
              className="w-full max-w-[40px] rounded-t-lg overflow-hidden">

                {/* Fake portion */}
                <div
                className="w-full bg-neon-red/80"
                style={{
                  height: `${day.total > 0 ? day.fake / day.total * 100 : 0}%`
                }} />

                {/* Real portion */}
                <div
                className="w-full bg-neon-green/80"
                style={{
                  height: `${day.total > 0 ? day.real / day.total * 100 : 0}%`
                }} />

              </motion.div>

              {/* Value label */}
              {day.total > 0 &&
            <span className="absolute -top-6 text-xs font-medium text-gray-600 dark:text-gray-400">
                  {day.total}
                </span>
            }
            </div>

            {/* Day label */}
            <span className="text-xs text-gray-500 dark:text-gray-400">
              {day.date}
            </span>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="flex items-center justify-center gap-6 mt-6 pt-4 border-t border-gray-200 dark:border-navy-700">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded bg-neon-red" />
          <span className="text-sm text-gray-600 dark:text-gray-400">
            Deepfakes
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded bg-neon-green" />
          <span className="text-sm text-gray-600 dark:text-gray-400">
            Authentic
          </span>
        </div>
      </div>
    </div>);

}
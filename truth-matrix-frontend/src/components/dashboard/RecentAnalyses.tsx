import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ImageIcon,
  VideoIcon,
  MusicIcon,
  ArrowRightIcon,
  ShieldAlertIcon,
  ShieldCheckIcon } from
'lucide-react';
import { Badge } from '../common/Badge';
import { useAnalysisStore } from '../../store/analysisStore';
import { formatRelativeTime, truncateFilename } from '../../utils/formatters';
import { ROUTES } from '../../utils/constants';
export function RecentAnalyses() {
  const { analyses, setCurrentAnalysis } = useAnalysisStore();
  const recentAnalyses = analyses.slice(0, 5);
  const getFileIcon = (type: string) => {
    if (type === 'video') return VideoIcon;
    if (type === 'audio') return MusicIcon;
    return ImageIcon;
  };
  if (recentAnalyses.length === 0) {
    return (
      <div className="rounded-2xl bg-white dark:bg-navy-800 border border-gray-200 dark:border-navy-700 p-8 text-center">
        <div className="w-16 h-16 mx-auto rounded-2xl bg-gray-100 dark:bg-navy-700 flex items-center justify-center mb-4">
          <ImageIcon className="w-8 h-8 text-gray-400" />
        </div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
          No analyses yet
        </h3>
        <p className="text-gray-500 dark:text-gray-400 mb-4">
          Upload your first image or video to get started
        </p>
        <Link
          to={ROUTES.ANALYZE}
          className="inline-flex items-center gap-2 text-neon-cyan hover:underline font-medium">

          Start Analyzing
          <ArrowRightIcon className="w-4 h-4" />
        </Link>
      </div>);

  }
  return (
    <div className="rounded-2xl bg-white dark:bg-navy-800 border border-gray-200 dark:border-navy-700 overflow-hidden">
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-navy-700">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
          Recent Analyses
        </h3>
        <Link
          to={ROUTES.HISTORY}
          className="text-sm text-neon-cyan hover:underline font-medium flex items-center gap-1">

          View All
          <ArrowRightIcon className="w-4 h-4" />
        </Link>
      </div>

      <div className="divide-y divide-gray-200 dark:divide-navy-700">
        {recentAnalyses.map((analysis, index) => {
          const FileIcon = getFileIcon(analysis.fileType);
          const isFake = analysis.result === 'fake';
          return (
            <motion.div
              key={analysis.id}
              initial={{
                opacity: 0,
                x: -20
              }}
              animate={{
                opacity: 1,
                x: 0
              }}
              transition={{
                delay: index * 0.05
              }}>

              <Link
                to={ROUTES.RESULTS}
                onClick={() => setCurrentAnalysis(analysis)}
                className="flex items-center gap-4 px-6 py-4 hover:bg-gray-50 dark:hover:bg-navy-700/50 transition-colors">

                {/* Thumbnail */}
                <div className="relative w-12 h-12 rounded-xl overflow-hidden bg-gray-100 dark:bg-navy-700 flex-shrink-0">
                  {analysis.thumbnailUrl ?
                  <img
                    src={analysis.thumbnailUrl}
                    alt={analysis.filename}
                    className="w-full h-full object-cover" /> :


                  <div className="w-full h-full flex items-center justify-center">
                      <FileIcon className="w-6 h-6 text-gray-400" />
                    </div>
                  }
                  {/* Result indicator */}
                  <div
                    className={`absolute -bottom-1 -right-1 w-5 h-5 rounded-full flex items-center justify-center ${isFake ? 'bg-neon-red' : 'bg-neon-green'}`}>

                    {isFake ?
                    <ShieldAlertIcon className="w-3 h-3 text-white" /> :

                    <ShieldCheckIcon className="w-3 h-3 text-white" />
                    }
                  </div>
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-900 dark:text-white truncate">
                    {truncateFilename(analysis.filename, 25)}
                  </p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {formatRelativeTime(analysis.createdAt)}
                  </p>
                </div>

                {/* Result */}
                <div className="flex items-center gap-3">
                  <Badge variant={isFake ? 'danger' : 'success'} size="sm">
                    {analysis.confidence.toFixed(0)}%
                  </Badge>
                </div>
              </Link>
            </motion.div>);

        })}
      </div>
    </div>);

}

import React from 'react';
import { motion } from 'framer-motion';
import {
  ShieldAlertIcon,
  ShieldCheckIcon,
  AlertTriangleIcon,
  DownloadIcon,
  ShareIcon,
  FlagIcon,
  VideoIcon,
  ImageIcon,
  MicIcon,
} from 'lucide-react';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';
import { ConfidenceMeter } from './ConfidenceMeter';
import { formatProcessingTime } from '../../utils/formatters';
import type { Analysis } from '../../store/analysisStore';

interface ResultCardProps {
  analysis: Analysis;
  onShare?: () => void;
  onDownload?: () => void;
  onFlag?: () => void;
}
// -- Model display metadata ----------------------------------------------------
const MODEL_INFO: Record<string, { name: string; Icon: React.ElementType }> = {
  image: { name: 'EfficientNet-B4 Image Model', Icon: ImageIcon },
  video: { name: 'Keras .h5 Frame CNN', Icon: VideoIcon },
  audio: { name: 'Audio Deepfake Model',        Icon: MicIcon },
};

// -- Result display config -----------------------------------------------------
const RESULT_CONFIG = {
  fake: {
    icon: ShieldAlertIcon,
    label: 'DEEPFAKE DETECTED',
    color: 'text-neon-red',
    bgColor: 'bg-red-50 dark:bg-red-900/20',
    borderColor: 'border-neon-red',
    glowColor: 'shadow-neon-red',
  },
  real: {
    icon: ShieldCheckIcon,
    label: 'AUTHENTIC',
    color: 'text-neon-green',
    bgColor: 'bg-emerald-50 dark:bg-emerald-900/20',
    borderColor: 'border-neon-green',
    glowColor: 'shadow-neon-green',
  },
  uncertain: {
    icon: AlertTriangleIcon,
    label: 'UNCERTAIN',
    color: 'text-neon-orange',
    bgColor: 'bg-amber-50 dark:bg-amber-900/20',
    borderColor: 'border-neon-orange',
    glowColor: 'shadow-neon-orange',
  },
} as const;

export function ResultCard({
  analysis,
  onShare,
  onDownload,
  onFlag,
}: ResultCardProps) {
  const isFake      = analysis.result === 'fake';
  const isUncertain = analysis.result === 'uncertain';

  const config    = RESULT_CONFIG[analysis.result];
  const Icon      = config.icon;
  const meterTone = isFake ? 'danger' : isUncertain ? 'warning' : 'success';

  const modelInfo = MODEL_INFO[analysis.fileType] ?? {
    name: `${analysis.fileType} Model`,
    Icon: ImageIcon,
  };
  const ModelIcon = modelInfo.Icon;
  const analyzedSegment = analysis.videoMetadata?.analyzed_segment;
  const xaiTarget = analysis.xaiTargetClass
    ? ` (${analysis.xaiTargetClass.replace(/_/g, ' ')})`
    : '';
  const xaiBadge = analysis.heatmapUrl
    ? `${analysis.xaiMethod || 'Grad-CAM'}${xaiTarget}`
    : analysis.fileType === 'audio'
      ? 'Audio XAI pending'
      : 'XAI unavailable';

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={`rounded-2xl border-2 ${config.borderColor} ${config.bgColor} overflow-hidden`}
    >
      {/* -- Result Header ------------------------------------------------- */}
      <div className={`p-6 ${config.bgColor}`}>
        <motion.div
          initial={{ scale: 0.8 }}
          animate={{ scale: 1 }}
          transition={{ delay: 0.2, type: 'spring' }}
          className="flex flex-col items-center text-center"
        >
          <div className={`p-4 rounded-2xl ${config.bgColor} ${config.glowColor} mb-4`}>
            <Icon className={`w-12 h-12 ${config.color}`} />
          </div>
          <h2 className={`text-2xl sm:text-3xl font-bold ${config.color} mb-2`}>
            {config.label}
          </h2>
          <p className="text-gray-600 dark:text-gray-400">
            Analysis completed in {formatProcessingTime(analysis.processingTime)}
          </p>
        </motion.div>
      </div>

      {/* -- Confidence Section -------------------------------------------- */}
      <div className="p-6 bg-white dark:bg-navy-800 border-t border-gray-200 dark:border-navy-700">
        <div className="flex flex-col lg:flex-row items-center gap-8">
          {/* Gauge */}
          <div className="flex-shrink-0">
            <ConfidenceMeter
              value={analysis.confidence}
              size="lg"
              variant="gauge"
              tone={meterTone}
              label="Confidence"
            />
          </div>

          {/* Probability breakdown */}
          <div className="flex-1 w-full space-y-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              Probability Breakdown
            </h3>

            <div className="space-y-3">
              {/* Fake probability */}
              <div>
                <div className="flex justify-between items-center mb-1">
                  <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
                    Fake Probability
                  </span>
                  <span className="text-sm font-bold text-neon-red">
                    {analysis.fakeProb.toFixed(1)}%
                  </span>
                </div>
                <div className="h-2 bg-gray-200 dark:bg-navy-700 rounded-full overflow-hidden">
                  <motion.div
                    className="h-full bg-neon-red rounded-full"
                    initial={{ width: 0 }}
                    animate={{ width: `${analysis.fakeProb}%` }}
                    transition={{ duration: 1, delay: 0.5 }}
                  />
                </div>
              </div>

              {/* Real probability */}
              <div>
                <div className="flex justify-between items-center mb-1">
                  <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
                    Real Probability
                  </span>
                  <span className="text-sm font-bold text-neon-green">
                    {analysis.realProb.toFixed(1)}%
                  </span>
                </div>
                <div className="h-2 bg-gray-200 dark:bg-navy-700 rounded-full overflow-hidden">
                  <motion.div
                    className="h-full bg-neon-green rounded-full"
                    initial={{ width: 0 }}
                    animate={{ width: `${analysis.realProb}%` }}
                    transition={{ duration: 1, delay: 0.7 }}
                  />
                </div>
              </div>
            </div>

            {/* -- Model badges (live, from real model data) -------------- */}
            <div className="flex flex-wrap gap-2 pt-4">
              {/* Model name badge */}
              <Badge variant="info" size="sm">
                <ModelIcon className="w-3 h-3 mr-1 inline-block" />
                {modelInfo.name}
              </Badge>

              {/* Frames analysed badge - only for video */}
              {analysis.fileType === 'video' && analysis.framesAnalyzed != null && (
                <Badge variant="default" size="sm">
                  {analysis.framesAnalyzed} frames analysed
                </Badge>
              )}

              {analysis.fileType === 'video' &&
                analyzedSegment?.selection_applied &&
                analyzedSegment.end_seconds != null && (
                  <Badge variant="info" size="sm">
                    {analyzedSegment.start_seconds.toFixed(1)}s -{' '}
                    {analyzedSegment.end_seconds.toFixed(1)}s segment
                  </Badge>
                )}

              {analysis.fileType !== 'video' && (
                <Badge variant={analysis.heatmapUrl ? 'default' : 'warning'} size="sm">
                  {xaiBadge}
                </Badge>
              )}

              {/* High-confidence warning */}
              {isFake && analysis.confidence >= 80 && (
                <Badge variant="danger" size="sm">
                  High Confidence
                </Badge>
              )}
            </div>

            {/* -- Explanation from the model ----------------------------- */}
            {analysis.explanation && (
              <p className="text-sm text-gray-500 dark:text-gray-400 leading-relaxed pt-2 border-t border-gray-100 dark:border-navy-700">
                {analysis.explanation}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* -- Actions ------------------------------------------------------- */}
      <div className="p-6 bg-gray-50 dark:bg-navy-900/50 border-t border-gray-200 dark:border-navy-700">
        <div className="flex flex-wrap items-center justify-center gap-3">
          <Button
            variant="secondary"
            size="sm"
            leftIcon={<ShareIcon className="w-4 h-4" />}
            onClick={onShare}
          >
            Share Report
          </Button>
          <Button
            variant="secondary"
            size="sm"
            leftIcon={<DownloadIcon className="w-4 h-4" />}
            onClick={onDownload}
          >
            Download PDF
          </Button>
          <Button
            variant="ghost"
            size="sm"
            leftIcon={<FlagIcon className="w-4 h-4" />}
            onClick={onFlag}
          >
            Flag Incorrect
          </Button>
        </div>
      </div>
    </motion.div>
  );
}

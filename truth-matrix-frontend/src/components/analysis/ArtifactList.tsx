import React from 'react';
import { motion } from 'framer-motion';
import {
  AlertTriangleIcon,
  SunIcon,
  LayersIcon,
  VolumeXIcon,
  UserIcon,
  SparklesIcon } from
'lucide-react';
import type { Artifact } from '../../store/analysisStore';
interface ArtifactListProps {
  artifacts: Artifact[];
}
const artifactIcons: Record<string, React.ElementType> = {
  blending_artifact: LayersIcon,
  lighting_inconsistency: SunIcon,
  texture_anomaly: SparklesIcon,
  face_swap: UserIcon,
  lip_sync: VolumeXIcon,
  audio_visual_mismatch: VolumeXIcon,
  gan_artifact: SparklesIcon,
  visual_manipulation_signal: AlertTriangleIcon,
  frame_manipulation_signal: AlertTriangleIcon,
  gradcam_heatmap: LayersIcon,
  gradcam_frame_heatmap: LayersIcon,
  uncertain_model_signal: AlertTriangleIcon,
  xai_generation_error: AlertTriangleIcon,
  default: AlertTriangleIcon
};
export function ArtifactList({ artifacts }: ArtifactListProps) {
  if (artifacts.length === 0) {
    return (
      <div className="text-center py-8">
        <div className="w-16 h-16 mx-auto rounded-2xl bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center mb-4">
          <SparklesIcon className="w-8 h-8 text-emerald-500" />
        </div>
        <p className="text-gray-600 dark:text-gray-400">
          No XAI findings returned for this analysis
        </p>
      </div>);

  }
  return (
    <div className="space-y-3">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
        XAI Findings ({artifacts.length})
      </h3>

      {artifacts.map((artifact, index) => {
        const Icon = artifactIcons[artifact.type] || artifactIcons.default;
        const isHeatmap = artifact.type.includes('gradcam');
        const isUncertain = artifact.type.includes('uncertain');
        const toneClass = isHeatmap
          ? 'bg-cyan-50 dark:bg-cyan-900/20 border-cyan-200 dark:border-cyan-800/50'
          : isUncertain
            ? 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800/50'
            : 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800/50';
        const iconClass = isHeatmap
          ? 'bg-cyan-100 dark:bg-cyan-900/40 text-cyan-600 dark:text-cyan-400'
          : isUncertain
            ? 'bg-amber-100 dark:bg-amber-900/40 text-amber-600 dark:text-amber-400'
            : 'bg-red-100 dark:bg-red-900/40 text-red-600 dark:text-red-400';
        const badgeClass = isHeatmap
          ? 'bg-cyan-100 dark:bg-cyan-900/40 text-cyan-700 dark:text-cyan-400'
          : isUncertain
            ? 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-400'
            : 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-400';
        return (
          <motion.div
            key={artifact.id}
            initial={{
              opacity: 0,
              x: -20
            }}
            animate={{
              opacity: 1,
              x: 0
            }}
            transition={{
              delay: index * 0.1
            }}
            className={`flex items-start gap-4 p-4 rounded-xl border ${toneClass}`}>

            <div className={`flex-shrink-0 p-2 rounded-lg ${iconClass}`}>
              <Icon className="w-5 h-5" />
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2 mb-1">
                <h4 className="font-semibold text-gray-900 dark:text-white capitalize">
                  {artifact.type.replace(/_/g, ' ')}
                </h4>
                <span className={`flex-shrink-0 px-2 py-0.5 rounded-full text-xs font-bold ${badgeClass}`}>
                  {artifact.confidence.toFixed(1)}%
                </span>
              </div>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                {artifact.description}
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">
                Location:{' '}
                <span className="capitalize">
                  {artifact.location.replace(/_/g, ' ')}
                </span>
              </p>
            </div>
          </motion.div>);

      })}
    </div>);

}

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
          No manipulation artifacts detected
        </p>
      </div>);

  }
  return (
    <div className="space-y-3">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
        Detected Artifacts ({artifacts.length})
      </h3>

      {artifacts.map((artifact, index) => {
        const Icon = artifactIcons[artifact.type] || artifactIcons.default;
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
            className="flex items-start gap-4 p-4 rounded-xl bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800/50">

            <div className="flex-shrink-0 p-2 rounded-lg bg-red-100 dark:bg-red-900/40">
              <Icon className="w-5 h-5 text-red-600 dark:text-red-400" />
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2 mb-1">
                <h4 className="font-semibold text-gray-900 dark:text-white capitalize">
                  {artifact.type.replace(/_/g, ' ')}
                </h4>
                <span className="flex-shrink-0 px-2 py-0.5 rounded-full text-xs font-bold bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-400">
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
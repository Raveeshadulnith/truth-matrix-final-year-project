import { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import {
  EyeIcon,
  EyeOffIcon,
  LayersIcon,
  ZoomInIcon,
  ZoomOutIcon,
  DownloadIcon } from
'lucide-react';
import { Button } from '../common/Button';
interface HeatmapViewerProps {
  originalUrl: string;
  heatmapUrl?: string;
  xaiOverlayUrl?: string;
  xaiPanelUrl?: string;
  filename: string;
  mediaType?: 'image' | 'video' | 'audio';
}
export function HeatmapViewer({
  originalUrl,
  heatmapUrl,
  xaiOverlayUrl,
  xaiPanelUrl,
  filename,
  mediaType = 'image'
}: HeatmapViewerProps) {
  const [viewMode, setViewMode] = useState<'original' | 'heatmap' | 'overlay' | 'panel'>(
    'overlay'
  );
  const [overlayOpacity, setOverlayOpacity] = useState(50);
  const [zoom, setZoom] = useState(100);
  const isImage = mediaType === 'image';
  const primaryXaiUrl = heatmapUrl || xaiOverlayUrl;
  const overlayUrl = xaiOverlayUrl || heatmapUrl;
  const supportsHeatmap = isImage && Boolean(primaryXaiUrl);
  const availableViewModes = useMemo(() => {
    const originalMode = {
      id: 'original' as const,
      label: 'Original',
      icon: EyeIcon
    };
    const heatmapMode = {
      id: 'heatmap' as const,
      label: 'Heatmap',
      icon: LayersIcon
    };
    const overlayMode = {
      id: 'overlay' as const,
      label: 'Overlay',
      icon: EyeOffIcon
    };
    const panelMode = {
      id: 'panel' as const,
      label: 'XAI Panel',
      icon: LayersIcon
    };

    if (!supportsHeatmap) {
      return [originalMode];
    }

    return isImage
      ? xaiPanelUrl
        ? [originalMode, heatmapMode, overlayMode, panelMode]
        : [originalMode, heatmapMode, overlayMode]
      : [originalMode, heatmapMode];
  }, [isImage, supportsHeatmap, xaiPanelUrl]);
  useEffect(() => {
    if (!availableViewModes.some((mode) => mode.id === viewMode)) {
      setViewMode('original');
    }
  }, [availableViewModes, viewMode]);

  const sharedMediaClassName = 'max-h-full max-w-full object-contain rounded-lg shadow-lg';

  const renderOriginalMedia = () => {
    if (!originalUrl) {
      return (
        <div className="flex h-[220px] w-full items-center justify-center rounded-xl border border-dashed border-gray-300 bg-white/70 px-6 text-center text-sm text-gray-500 dark:border-navy-600 dark:bg-navy-800/70 dark:text-gray-400">
          No media preview is available for this analysis yet.
        </div>
      );
    }

    if (mediaType === 'video') {
      return (
        <motion.video
          src={originalUrl}
          controls
          playsInline
          className={sharedMediaClassName}
          initial={{
            opacity: 0
          }}
          animate={{
            opacity: 1
          }}
          transition={{
            duration: 0.3
          }} />

      );
    }

    if (mediaType === 'audio') {
      return (
        <motion.div
          className="flex w-full max-w-xl flex-col items-center gap-4 rounded-2xl border border-gray-200 bg-white/90 px-6 py-8 shadow-lg dark:border-navy-700 dark:bg-navy-800"
          initial={{
            opacity: 0
          }}
          animate={{
            opacity: 1
          }}
          transition={{
            duration: 0.3
          }}>

          <div className="text-center">
            <p className="text-sm font-medium text-gray-900 dark:text-white">
              Audio preview
            </p>
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              Listen to the uploaded media while reviewing the analysis output.
            </p>
          </div>
          <audio
            src={originalUrl}
            controls
            className="w-full max-w-md" />

        </motion.div>
      );
    }

    return (
      <motion.img
        src={originalUrl}
        alt={filename}
        className={sharedMediaClassName}
        initial={{
          opacity: 0
        }}
        animate={{
          opacity: viewMode === 'heatmap' ? 0 : 1
        }}
        transition={{
          duration: 0.3
        }} />

    );
  };
  const renderHeatmapMedia = (sourceUrl?: string) => {
    if (!sourceUrl) {
      return null;
    }

    return (
        <motion.img
        src={sourceUrl}
        alt={`${filename} XAI visualization`}
        className={sharedMediaClassName}
        initial={{
          opacity: 0
        }}
        animate={{
          opacity: 1
        }}
        transition={{
          duration: 0.3
        }} />

    );
  };

  const openCurrentView = () => {
    const url =
      viewMode === 'panel' && xaiPanelUrl
        ? xaiPanelUrl
        : viewMode === 'overlay' && overlayUrl
          ? overlayUrl
          : viewMode !== 'original' && primaryXaiUrl
          ? primaryXaiUrl
          : originalUrl;
    if (url) {
      window.open(url, '_blank', 'noopener,noreferrer');
    }
  };

  const showOriginalMedia =
    viewMode === 'original' || (viewMode === 'overlay' && !xaiOverlayUrl);
  const showStandaloneHeatmap =
    supportsHeatmap && (viewMode === 'heatmap' || viewMode === 'panel');
  const showPrecomputedOverlay = isImage && Boolean(xaiOverlayUrl) && viewMode === 'overlay';
  const showImageOverlay = isImage && supportsHeatmap && viewMode === 'overlay' && !xaiOverlayUrl;
  const standaloneXaiUrl =
    viewMode === 'panel' && xaiPanelUrl ? xaiPanelUrl : primaryXaiUrl;

  return (
    <div className="rounded-2xl border border-gray-200 dark:border-navy-700 overflow-hidden bg-white dark:bg-navy-800">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 border-b border-gray-200 dark:border-navy-700 bg-gray-50 dark:bg-navy-900/50">
        {/* View Mode Toggle */}
        <div className="flex items-center gap-1 p-1 bg-gray-100 dark:bg-navy-800 rounded-xl">
          {availableViewModes.map((mode) =>
          <button
            key={mode.id}
            onClick={() => setViewMode(mode.id)}
            className={`
                flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all
                ${viewMode === mode.id ? 'bg-white dark:bg-navy-700 text-neon-cyan shadow-sm' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}
              `}>

              <mode.icon className="w-4 h-4" />
              <span className="hidden sm:inline">{mode.label}</span>
            </button>
          )}
        </div>

        {/* Controls */}
        <div className="flex items-center gap-4">
          {/* Opacity Slider (only for overlay mode) */}
          {viewMode === 'overlay' && supportsHeatmap && !xaiOverlayUrl &&
          <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500 dark:text-gray-400">
                Opacity
              </span>
              <input
              type="range"
              min="0"
              max="100"
              value={overlayOpacity}
              onChange={(e) => setOverlayOpacity(Number(e.target.value))}
              className="w-24 h-2 bg-gray-200 dark:bg-navy-700 rounded-lg appearance-none cursor-pointer accent-neon-cyan" />

              <span className="text-xs font-medium text-gray-700 dark:text-gray-300 w-8">
                {overlayOpacity}%
              </span>
            </div>
          }

          {/* Zoom Controls */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => setZoom(Math.max(50, zoom - 25))}
              className="p-2 rounded-lg text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-navy-700"
              disabled={zoom <= 50}>

              <ZoomOutIcon className="w-4 h-4" />
            </button>
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300 w-12 text-center">
              {zoom}%
            </span>
            <button
              onClick={() => setZoom(Math.min(200, zoom + 25))}
              className="p-2 rounded-lg text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-navy-700"
              disabled={zoom >= 200}>

              <ZoomInIcon className="w-4 h-4" />
            </button>
          </div>

          {/* Download */}
          <Button
            variant="ghost"
            size="sm"
            leftIcon={<DownloadIcon className="w-4 h-4" />}
            onClick={openCurrentView}>

            Open
          </Button>
        </div>
      </div>

      {/* Image Viewer */}
      <div
        className="relative overflow-auto bg-gray-100 dark:bg-navy-900"
        style={{
          height: mediaType === 'image' ? 'min(70vh, 620px)' : '400px',
          minHeight: mediaType === 'image' ? '420px' : undefined
        }}>

        <div
          className="absolute inset-0 flex items-center justify-center p-6 sm:p-8"
          style={{
            transform: `scale(${zoom / 100})`,
            transformOrigin: 'center'
          }}>

          <div className="relative flex h-full w-full items-center justify-center">
            {/* Original Media */}
            {showOriginalMedia && renderOriginalMedia()}
            {showStandaloneHeatmap && renderHeatmapMedia(standaloneXaiUrl)}
            {showPrecomputedOverlay && renderHeatmapMedia(xaiOverlayUrl)}

            {/* Heatmap Overlay */}
            {showImageOverlay &&
            <motion.img
              src={heatmapUrl}
              alt={`${filename} heatmap`}
              className="absolute inset-0 h-full w-full rounded-lg object-contain mix-blend-multiply"
              initial={{
                opacity: 0
              }}
              animate={{
                opacity: overlayOpacity / 100
              }}
              transition={{
                duration: 0.3
              }} />
            }
          </div>
        </div>
      </div>

      {mediaType === 'audio' &&
      <div className="border-t border-gray-200 bg-blue-50/70 px-4 py-3 text-sm text-blue-800 dark:border-navy-700 dark:bg-blue-500/10 dark:text-blue-200">
          Audio XAI is not available yet because the trained audio model is still in progress.
        </div>
      }

      {mediaType === 'image' && supportsHeatmap &&
      <div className="border-t border-gray-200 bg-blue-50/70 px-4 py-3 text-sm text-blue-800 dark:border-navy-700 dark:bg-blue-500/10 dark:text-blue-200">
          The Heatmap view shows the XAI regions returned by the backend. Overlay blends the heatmap with the original image.
        </div>
      }

      {mediaType === 'image' && !supportsHeatmap &&
      <div className="border-t border-gray-200 bg-amber-50/70 px-4 py-3 text-sm text-amber-800 dark:border-navy-700 dark:bg-amber-500/10 dark:text-amber-200">
          No XAI heatmap was returned for this analysis. Try reanalyzing after confirming XAI is enabled in the backend.
        </div>
      }

      {/* Legend */}
      {supportsHeatmap &&
      <div className="p-4 border-t border-gray-200 dark:border-navy-700 bg-gray-50 dark:bg-navy-900/50">
          <div className="flex items-center justify-center gap-6">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-gradient-to-r from-red-500 to-red-600" />
              <span className="text-sm text-gray-600 dark:text-gray-400">
                High manipulation
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-gradient-to-r from-orange-400 to-orange-500" />
              <span className="text-sm text-gray-600 dark:text-gray-400">
                Medium
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-gradient-to-r from-yellow-400 to-yellow-500" />
              <span className="text-sm text-gray-600 dark:text-gray-400">
                Low
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-gradient-to-r from-blue-400 to-blue-500" />
              <span className="text-sm text-gray-600 dark:text-gray-400">
                Authentic
              </span>
            </div>
          </div>
        </div>
      }
    </div>);

}

import React, { useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowLeftIcon,
  RefreshCwIcon,
  DownloadIcon,
  ShareIcon,
  BookmarkIcon } from
'lucide-react';
import { toast } from 'sonner';
import { Button } from '../components/common/Button';
import { Card } from '../components/common/Card';
import { ResultCard } from '../components/analysis/ResultCard';
import { HeatmapViewer } from '../components/analysis/HeatmapViewer';
import { ArtifactList } from '../components/analysis/ArtifactList';
import { ShareModal } from '../components/analysis/ShareModal';
import { useAnalysisStore } from '../store/analysisStore';
import { useUIStore } from '../store/uiStore';
import { ROUTES } from '../utils/constants';
import { formatFileSize, formatDate } from '../utils/formatters';
export function ResultsPage() {
  const navigate = useNavigate();
  const { currentAnalysis, resetAnalysis } = useAnalysisStore();
  const { openModal } = useUIStore();
  useEffect(() => {
    if (!currentAnalysis) {
      navigate(ROUTES.ANALYZE);
    }
  }, [currentAnalysis, navigate]);
  if (!currentAnalysis) {
    return null;
  }
  const handleNewAnalysis = () => {
    resetAnalysis();
    navigate(ROUTES.ANALYZE);
  };
  const handleShare = () => {
    openModal('share-modal');
  };
  const handleDownload = () => {
    toast.success('Report downloaded!', {
      description: 'Your PDF report has been generated and downloaded.'
    });
  };
  const handleFlag = () => {
    toast.success('Feedback submitted!', {
      description: 'Thank you! Our team will review this result.'
    });
  };
  return (
    <div className="min-h-screen py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <motion.div
          initial={{
            opacity: 0,
            y: 20
          }}
          animate={{
            opacity: 1,
            y: 0
          }}
          className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">

          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate(-1)}
              className="p-2 rounded-xl bg-gray-100 dark:bg-navy-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-navy-700 transition-colors">

              <ArrowLeftIcon className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white">
                Analysis Results
              </h1>
              <p className="text-gray-600 dark:text-gray-400">
                {currentAnalysis.filename}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              leftIcon={<BookmarkIcon className="w-4 h-4" />}>

              Save
            </Button>
            <Button
              variant="secondary"
              leftIcon={<RefreshCwIcon className="w-4 h-4" />}
              onClick={handleNewAnalysis}>

              New Analysis
            </Button>
          </div>
        </motion.div>

        {/* Main Content */}
        <div className="grid lg:grid-cols-3 gap-6 lg:gap-8">
          {/* Left Column - Media & Heatmap */}
          <div className="lg:col-span-2 space-y-6">
            {/* Result Card */}
            <motion.div
              initial={{
                opacity: 0,
                y: 20
              }}
              animate={{
                opacity: 1,
                y: 0
              }}
              transition={{
                delay: 0.1
              }}>

              <ResultCard
                analysis={currentAnalysis}
                onShare={handleShare}
                onDownload={handleDownload}
                onFlag={handleFlag} />

            </motion.div>

            {/* Heatmap Viewer */}
            <motion.div
              initial={{
                opacity: 0,
                y: 20
              }}
              animate={{
                opacity: 1,
                y: 0
              }}
              transition={{
                delay: 0.2
              }}>

              <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">
                Explainable AI Visualization
              </h2>
              <HeatmapViewer
                originalUrl={
                currentAnalysis.mediaUrl || currentAnalysis.thumbnailUrl
                }
                heatmapUrl={currentAnalysis.heatmapUrl}
                filename={currentAnalysis.filename}
                mediaType={currentAnalysis.fileType} />

            </motion.div>
          </div>

          {/* Right Column - Details */}
          <div className="space-y-6">
            {/* File Info */}
            <motion.div
              initial={{
                opacity: 0,
                y: 20
              }}
              animate={{
                opacity: 1,
                y: 0
              }}
              transition={{
                delay: 0.3
              }}>

              <Card variant="default">
                <div className="p-6">
                  <h3 className="font-semibold text-gray-900 dark:text-white mb-4">
                    File Information
                  </h3>
                  <dl className="space-y-3">
                    <div className="flex justify-between">
                      <dt className="text-sm text-gray-500 dark:text-gray-400">
                        Filename
                      </dt>
                      <dd className="text-sm font-medium text-gray-900 dark:text-white truncate max-w-[180px]">
                        {currentAnalysis.filename}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-sm text-gray-500 dark:text-gray-400">
                        File Size
                      </dt>
                      <dd className="text-sm font-medium text-gray-900 dark:text-white">
                        {formatFileSize(currentAnalysis.fileSize)}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-sm text-gray-500 dark:text-gray-400">
                        Type
                      </dt>
                      <dd className="text-sm font-medium text-gray-900 dark:text-white capitalize">
                        {currentAnalysis.fileType}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-sm text-gray-500 dark:text-gray-400">
                        Analyzed
                      </dt>
                      <dd className="text-sm font-medium text-gray-900 dark:text-white">
                        {formatDate(currentAnalysis.createdAt)}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-sm text-gray-500 dark:text-gray-400">
                        Processing Time
                      </dt>
                      <dd className="text-sm font-medium text-gray-900 dark:text-white">
                        {currentAnalysis.processingTime.toFixed(2)}s
                      </dd>
                    </div>
                  </dl>
                </div>
              </Card>
            </motion.div>

            {/* Artifacts */}
            <motion.div
              initial={{
                opacity: 0,
                y: 20
              }}
              animate={{
                opacity: 1,
                y: 0
              }}
              transition={{
                delay: 0.4
              }}>

              <Card variant="default">
                <div className="p-6">
                  <ArtifactList artifacts={currentAnalysis.artifacts} />
                </div>
              </Card>
            </motion.div>

            {/* Actions */}
            <motion.div
              initial={{
                opacity: 0,
                y: 20
              }}
              animate={{
                opacity: 1,
                y: 0
              }}
              transition={{
                delay: 0.5
              }}>

              <Card variant="glass">
                <div className="p-6 space-y-3">
                  <Button
                    variant="primary"
                    className="w-full"
                    leftIcon={<DownloadIcon className="w-4 h-4" />}
                    onClick={handleDownload}>

                    Download Full Report
                  </Button>
                  <Button
                    variant="secondary"
                    className="w-full"
                    leftIcon={<ShareIcon className="w-4 h-4" />}
                    onClick={handleShare}>

                    Share Results
                  </Button>
                </div>
              </Card>
            </motion.div>
          </div>
        </div>
      </div>

      {/* Share Modal */}
      <ShareModal
        shareUrl={`${window.location.origin}/share/${currentAnalysis.shareToken || currentAnalysis.id}`}
        title={`TruthMatrix Analysis: ${currentAnalysis.filename}`} />

    </div>);

}

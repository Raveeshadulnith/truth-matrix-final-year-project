import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeftIcon,
  FileSearchIcon,
  ScanSearchIcon,
  RefreshCwIcon,
  WrenchIcon,
} from 'lucide-react';
import { toast } from 'sonner';
import { ShareModal } from '../components/analysis/ShareModal';
import { Button } from '../components/common/Button';
import { ForensicTechnicalDetails } from '../components/forensics/ForensicTechnicalDetails';
import { AnalysisResultHero } from '../components/results/AnalysisResultHero';
import { EvidenceAtGlance } from '../components/results/EvidenceAtGlance';
import { ExplainableAiSection } from '../components/results/ExplainableAiSection';
import { RelatedHistorySection } from '../components/results/RelatedHistorySection';
import { ResultsActionBar } from '../components/results/ResultsActionBar';
import { useAnalysisStore } from '../store/analysisStore';
import { useAuthStore } from '../store/authStore';
import { useUIStore } from '../store/uiStore';
import { ROUTES } from '../utils/constants';
import { formatDate, formatFileSize, formatProcessingTime } from '../utils/formatters';

function LegacyTechnicalDetails({
  fileSize,
  processingTime,
  modelVersion,
}: {
  fileSize: number;
  processingTime: number;
  modelVersion: string | null;
}) {
  return (
    <details className="rounded-2xl border border-gray-200 bg-white dark:border-navy-700 dark:bg-navy-800">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-2xl p-4 font-semibold text-gray-900 hover:bg-gray-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500 dark:text-white dark:hover:bg-navy-700/50 sm:p-5">
        <span className="flex items-center gap-2"><WrenchIcon className="h-5 w-5 text-gray-500" />Technical details</span>
        <span className="text-xs font-normal text-gray-500 dark:text-gray-400">File and model information</span>
      </summary>
      <dl className="grid gap-4 border-t border-gray-200 p-4 text-sm dark:border-navy-700 sm:grid-cols-3 sm:p-5">
        <div><dt className="text-gray-500 dark:text-gray-400">File size</dt><dd className="mt-1 font-medium text-gray-900 dark:text-white">{formatFileSize(fileSize)}</dd></div>
        <div><dt className="text-gray-500 dark:text-gray-400">Model version</dt><dd className="mt-1 font-medium text-gray-900 dark:text-white">{modelVersion ?? 'Not recorded'}</dd></div>
        <div><dt className="text-gray-500 dark:text-gray-400">Processing time</dt><dd className="mt-1 font-medium text-gray-900 dark:text-white">{formatProcessingTime(processingTime)}</dd></div>
      </dl>
    </details>
  );
}

export function ResultsPage() {
  const navigate = useNavigate();
  const { currentAnalysis, resetAnalysis, analysisStatus } = useAnalysisStore();
  const { openModal } = useUIStore();
  const { isAuthenticated, user } = useAuthStore();
  const [isDownloadingReport, setIsDownloadingReport] = useState(false);
  const [isDownloadingEvidence, setIsDownloadingEvidence] = useState(false);

  useEffect(() => {
    if (!currentAnalysis) navigate(ROUTES.ANALYZE, { replace: true });
  }, [currentAnalysis, navigate]);

  if (!currentAnalysis) return null;

  const handleNewAnalysis = () => {
    resetAnalysis();
    navigate(ROUTES.ANALYZE);
  };

  const handleDownload = async () => {
    if (isDownloadingReport) return;
    setIsDownloadingReport(true);
    try {
      const { downloadAnalysisReport } = await import('../utils/reportGenerator');
      await downloadAnalysisReport(currentAnalysis);
      toast.success('Report downloaded', { description: 'Your professional Truth Matrix PDF is ready.' });
    } catch (error) {
      toast.error('Report download failed', {
        description: error instanceof Error ? error.message : 'Could not generate the report. Please try again.',
      });
    } finally {
      setIsDownloadingReport(false);
    }
  };

  const handleForensicJsonDownload = async () => {
    if (isDownloadingEvidence || !currentAnalysis.forensicEvidence) return;
    setIsDownloadingEvidence(true);
    try {
      const { downloadForensicEvidenceJson } = await import('../utils/forensicExport');
      downloadForensicEvidenceJson(currentAnalysis);
      toast.success('Forensic evidence downloaded', { description: 'The privacy-filtered, versioned JSON report is ready.' });
    } catch (error) {
      toast.error('Evidence download failed', {
        description: error instanceof Error ? error.message : 'Could not export forensic evidence. Please try again.',
      });
    } finally {
      setIsDownloadingEvidence(false);
    }
  };

  const matches = currentAnalysis.forensicEvidence?.similarity_matches ?? [];

  return (
    <div className="min-h-screen px-4 py-6 sm:px-6 lg:px-8">
      <main className="mx-auto max-w-[92rem]">
        <header className="mb-6 flex flex-col gap-4 border-b border-gray-200 pb-5 dark:border-navy-700 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 items-start gap-3">
            <button
              type="button"
              onClick={() => navigate(ROUTES.HISTORY)}
              aria-label="Back to analysis history"
              className="mt-0.5 rounded-xl p-2 text-gray-600 hover:bg-gray-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500 dark:text-gray-300 dark:hover:bg-navy-700"
            >
              <ArrowLeftIcon className="h-5 w-5" />
            </button>
            <div className="min-w-0">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Analysis result</p>
              <h1 className="max-w-3xl truncate text-xl font-bold text-gray-900 dark:text-white sm:text-2xl" title={currentAnalysis.filename}>
                {currentAnalysis.filename}
              </h1>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                {formatDate(currentAnalysis.createdAt)} <span aria-hidden="true">/</span> <span className="capitalize">{currentAnalysis.fileType}</span>
              </p>
            </div>
          </div>

          <Button className="self-end sm:self-auto" variant="secondary" size="sm" leftIcon={<RefreshCwIcon className="h-4 w-4" />} onClick={handleNewAnalysis}>New analysis</Button>
        </header>

        <div className="space-y-12 sm:space-y-16">
          <section data-result-section="model-analysis" aria-labelledby="model-analysis-heading">
            <div className="mb-5 flex items-start gap-3">
              <span className="rounded-xl bg-cyan-100 p-2 text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-200">
                <ScanSearchIcon className="h-5 w-5" aria-hidden="true" />
              </span>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-700 dark:text-cyan-300">Part 1</p>
                <h2 id="model-analysis-heading" className="text-2xl font-bold text-gray-900 dark:text-white">Model detection</h2>
                <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">The detection result, class probabilities, and any supporting output returned by the model.</p>
              </div>
            </div>
            <div className="space-y-8">
              <AnalysisResultHero analysis={currentAnalysis} />
              <ExplainableAiSection analysis={currentAnalysis} />
            </div>
          </section>

          <section data-result-section="forensic-evidence" aria-labelledby="forensic-evidence-heading" className="border-t border-gray-200 pt-10 dark:border-navy-700 sm:pt-12">
            <div className="mb-5 flex items-start gap-3">
              <span className="rounded-xl bg-violet-100 p-2 text-violet-700 dark:bg-violet-900/40 dark:text-violet-200">
                <FileSearchIcon className="h-5 w-5" aria-hidden="true" />
              </span>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-violet-700 dark:text-violet-300">Part 2</p>
                <h2 id="forensic-evidence-heading" className="text-2xl font-bold text-gray-900 dark:text-white">File forensics</h2>
                <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">Origin, Content Credentials, and file consistency checks. Independent from the model result.</p>
              </div>
            </div>

            <div className="space-y-6">
              <EvidenceAtGlance
                evidence={currentAnalysis.forensicEvidence}
                isLoading={analysisStatus === 'processing'}
                analysisId={currentAnalysis.id}
                canRevealPreciseLocation={
                  isAuthenticated &&
                  !currentAnalysis.isPublic &&
                  Boolean(currentAnalysis.ownerId) &&
                  currentAnalysis.ownerId === user?.id
                }
              />

              <RelatedHistorySection matches={matches} />

              <div data-result-component="technical-details" aria-label="Technical analysis details">
                {currentAnalysis.forensicEvidence ? (
                  <ForensicTechnicalDetails evidence={currentAnalysis.forensicEvidence} />
                ) : (
                  <LegacyTechnicalDetails
                    fileSize={currentAnalysis.fileSize}
                    processingTime={currentAnalysis.processingTime}
                    modelVersion={currentAnalysis.modelVersion}
                  />
                )}
              </div>
            </div>
          </section>

          <ResultsActionBar
            onDownloadReport={() => void handleDownload()}
            onDownloadEvidence={() => void handleForensicJsonDownload()}
            onShare={() => openModal('share-modal')}
            onFlag={() => toast.success('Feedback submitted!', { description: 'Thank you! Our team will review this result.' })}
            reportLoading={isDownloadingReport}
            evidenceLoading={isDownloadingEvidence}
            evidenceAvailable={Boolean(currentAnalysis.forensicEvidence)}
          />
        </div>
      </main>

      <ShareModal
        shareUrl={`${window.location.origin}/share/${currentAnalysis.shareToken || currentAnalysis.id}`}
        title={`TruthMatrix Analysis: ${currentAnalysis.filename}`}
      />
    </div>
  );
}

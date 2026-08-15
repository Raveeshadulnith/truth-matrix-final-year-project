import { DownloadIcon, FileJsonIcon, FlagIcon, ShareIcon } from 'lucide-react';
import { Button } from '../common/Button';

export function ResultsActionBar({
  onDownloadReport,
  onDownloadEvidence,
  onShare,
  onFlag,
  reportLoading,
  evidenceLoading,
  evidenceAvailable,
}: {
  onDownloadReport: () => void;
  onDownloadEvidence: () => void;
  onShare: () => void;
  onFlag: () => void;
  reportLoading: boolean;
  evidenceLoading: boolean;
  evidenceAvailable: boolean;
}) {
  return (
    <aside
      data-result-section="result-actions"
      aria-label="Analysis actions"
      className="sticky bottom-3 z-20 rounded-2xl border border-gray-200 bg-white/95 p-3 shadow-xl backdrop-blur dark:border-navy-700 dark:bg-navy-900/95"
    >
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:flex lg:items-center lg:justify-end">
        <Button
          variant="primary"
          size="sm"
          leftIcon={<DownloadIcon className="h-4 w-4" />}
          onClick={onDownloadReport}
          isLoading={reportLoading}
        >
          {reportLoading ? 'Generating report' : 'Download full report'}
        </Button>
        <Button
          variant="secondary"
          size="sm"
          leftIcon={<FileJsonIcon className="h-4 w-4" />}
          onClick={onDownloadEvidence}
          isLoading={evidenceLoading}
          disabled={!evidenceAvailable}
          title={evidenceAvailable ? 'Download privacy-filtered forensic evidence' : 'Forensic evidence is unavailable'}
        >
          {evidenceLoading ? 'Preparing JSON' : 'Download forensic JSON'}
        </Button>
        <Button variant="secondary" size="sm" leftIcon={<ShareIcon className="h-4 w-4" />} onClick={onShare}>Share results</Button>
        <Button variant="ghost" size="sm" leftIcon={<FlagIcon className="h-4 w-4" />} onClick={onFlag}>Flag incorrect result</Button>
      </div>
    </aside>
  );
}

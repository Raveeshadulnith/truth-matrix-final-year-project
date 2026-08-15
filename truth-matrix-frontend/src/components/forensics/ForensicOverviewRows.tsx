import { FileIcon, HistoryIcon } from 'lucide-react';
import type { ForensicEvidence } from '../../api/deepfakeApi';
import { formatFileSize } from '../../utils/formatters';
import { SimilarityMatchesCard } from './SimilarityMatchesCard';

const FRIENDLY_MEDIA_TYPES: Record<string, string> = {
  'image/jpeg': 'JPEG image',
  'image/png': 'PNG image',
  'image/webp': 'WebP image',
  'video/mp4': 'MP4 video',
  'video/quicktime': 'QuickTime video',
  'audio/wav': 'WAV audio',
  'audio/mpeg': 'MP3 audio',
};

function objectValue(value: unknown, key: string): unknown {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)[key]
    : undefined;
}

function dimension(evidence: ForensicEvidence, key: 'width' | 'height'): number | null {
  const image = objectValue(evidence.metadata.normalized, 'image');
  const video = objectValue(evidence.metadata.normalized, 'video');
  const value = objectValue(image, key) ?? objectValue(video, key) ?? objectValue(evidence.metadata.normalized, key);
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

export function FileOverviewRow({ evidence }: { evidence: ForensicEvidence }) {
  const width = dimension(evidence, 'width');
  const height = dimension(evidence, 'height');
  const facts = [
    evidence.detected_mime_type
      ? FRIENDLY_MEDIA_TYPES[evidence.detected_mime_type] ?? evidence.detected_mime_type
      : 'File type unavailable',
    evidence.file_size_bytes != null ? formatFileSize(evidence.file_size_bytes) : null,
    width != null && height != null ? `${width} x ${height} pixels` : null,
  ].filter((value): value is string => Boolean(value));

  return (
    <div className="flex min-w-0 items-start gap-3 rounded-2xl border border-gray-200 bg-white p-4 shadow-sm dark:border-navy-700 dark:bg-navy-800">
      <FileIcon className="mt-0.5 h-5 w-5 flex-none text-blue-600 dark:text-blue-400" aria-hidden="true" />
      <div className="min-w-0"><p className="text-sm font-semibold text-gray-900 dark:text-white">File overview</p><p className="mt-1 break-words text-sm text-gray-600 dark:text-gray-300">{facts.join(' | ')}</p></div>
    </div>
  );
}

export function MatchesOverview({ evidence }: { evidence: ForensicEvidence }) {
  if (evidence.similarity_matches.length === 0) {
    return (
      <p className="flex items-center gap-2 px-1 text-sm text-gray-500 dark:text-gray-400">
        <HistoryIcon className="h-4 w-4 flex-none" aria-hidden="true" />
        {evidence.similarity_status === 'available'
          ? 'No duplicate or near-duplicate was found in your bounded history search.'
          : 'History matching was not available for this analysis.'}
      </p>
    );
  }
  return <SimilarityMatchesCard status={evidence.similarity_status} matches={evidence.similarity_matches} />;
}

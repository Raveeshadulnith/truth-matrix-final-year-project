import type { MetadataEvidence } from '../../api/deepfakeApi';
import {
  EmptyEvidenceMessage,
  EvidenceCard,
  SafeJsonFields,
  TechnicalDetails,
  WarningList,
} from './ForensicPrimitives';

export function MetadataViewer({ metadata }: { metadata: MetadataEvidence }) {
  const hasNormalized = Object.keys(metadata.normalized).length > 0;
  const hasRaw = Object.keys(metadata.raw).length > 0;

  return (
    <EvidenceCard
      title="Metadata"
      status={metadata.status}
      description="Normalized image, stream, container, device, and software facts. Missing metadata is neutral."
      className="md:col-span-2"
    >
      {hasNormalized ? (
        <SafeJsonFields value={metadata.normalized} />
      ) : (
        <EmptyEvidenceMessage>
          No normalized metadata was returned. Many platforms routinely remove metadata.
        </EmptyEvidenceMessage>
      )}

      <TechnicalDetails label="Advanced sanitized metadata">
        <div className="mb-3 flex flex-wrap gap-x-5 gap-y-1 text-sm text-gray-600 dark:text-gray-400">
          <span>Source: {metadata.source ?? 'Not available'}</span>
          <span>Version: {metadata.source_version ?? 'Not available'}</span>
        </div>
        {hasRaw ? (
          <SafeJsonFields value={metadata.raw} />
        ) : (
          <EmptyEvidenceMessage>No sanitized raw fields were retained.</EmptyEvidenceMessage>
        )}
        <p className="mt-3 text-xs text-gray-500 dark:text-gray-400">
          Precise GPS coordinates and serial-number fields are redacted. Metadata is rendered only as text.
        </p>
      </TechnicalDetails>
      <WarningList warnings={metadata.warnings} />
    </EvidenceCard>
  );
}

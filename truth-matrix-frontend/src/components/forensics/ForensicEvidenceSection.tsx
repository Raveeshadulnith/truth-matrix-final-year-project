import { FlaskConicalIcon } from 'lucide-react';
import type { ForensicEvidence, ModelForensicAlignment } from '../../api/deepfakeApi';
import { ForensicTechnicalDetails } from './ForensicTechnicalDetails';
import { ForensicSummaryCard } from './ForensicSummaryCard';
import { FileOverviewRow, MatchesOverview } from './ForensicOverviewRows';
import { OriginHistoryCard } from './OriginHistoryCard';
import { ProvenanceCredentialsCard } from './ProvenanceCredentialsCard';

export function ForensicEvidenceSkeleton() {
  return (
    <section aria-label="Forensic evidence loading" aria-busy="true">
      <div className="mb-4 h-8 w-64 rounded-lg shimmer" />
      <div className="grid gap-4 md:grid-cols-2">
        {[0, 1, 2, 3].map((item) => (
          <div key={item} className="h-48 rounded-2xl shimmer" />
        ))}
      </div>
    </section>
  );
}

export function ForensicEvidenceUnavailable() {
  return (
    <section
      aria-label="Forensic evidence"
      className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-navy-700 dark:bg-navy-800 sm:p-6"
    >
      <div className="flex items-start gap-3">
        <div className="rounded-xl bg-gray-100 p-2.5 text-gray-500 dark:bg-navy-700 dark:text-gray-300">
          <FlaskConicalIcon className="h-5 w-5" />
        </div>
        <div>
          <h2 className="text-xl font-bold text-gray-900 dark:text-white">Forensic Evidence</h2>
          <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
            Forensic evidence is unavailable for this analysis. Older history records may predate evidence collection.
          </p>
          <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
            Unavailable evidence does not imply that the file is manipulated.
          </p>
        </div>
      </div>
    </section>
  );
}

export function ForensicEvidenceSection({
  evidence,
  alignment,
  isLoading = false,
}: {
  evidence?: ForensicEvidence;
  alignment?: ModelForensicAlignment;
  isLoading?: boolean;
}) {
  if (isLoading) return <ForensicEvidenceSkeleton />;
  if (!evidence) return <ForensicEvidenceUnavailable />;

  return (
    <section aria-labelledby="forensic-evidence-heading" className="space-y-4 sm:space-y-5">
      <div>
        <div className="flex items-center gap-2">
          <FlaskConicalIcon className="h-6 w-6 text-cyan-600 dark:text-cyan-400" />
          <h2 id="forensic-evidence-heading" className="text-2xl font-bold text-gray-900 dark:text-white">
            Forensic Evidence
          </h2>
        </div>
        <p className="mt-1 max-w-3xl text-sm text-gray-600 dark:text-gray-400">
          File identity, embedded metadata, provenance, encoding observations, and user-scoped similarity evidence.
        </p>
      </div>

      <ForensicSummaryCard evidence={evidence} alignment={alignment} />

      <ProvenanceCredentialsCard c2pa={evidence.c2pa} />

      <FileOverviewRow evidence={evidence} />

      <div className="grid min-w-0 gap-4 lg:grid-cols-2">
        <OriginHistoryCard creationInfo={evidence.creation_info} metadata={evidence.metadata} />
        <div className="space-y-4">
          <MatchesOverview evidence={evidence} />
        </div>
      </div>

      <ForensicTechnicalDetails evidence={evidence} />
    </section>
  );
}

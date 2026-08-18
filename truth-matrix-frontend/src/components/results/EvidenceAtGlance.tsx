import { CheckCircle2Icon, FlaskConicalIcon, InfoIcon } from 'lucide-react';
import type { ForensicEvidence, ForensicInsight } from '../../api/deepfakeApi';
import { OriginHistoryCard } from '../forensics/OriginHistoryCard';
import { ProvenanceCredentialsCard } from '../forensics/ProvenanceCredentialsCard';
import { ForensicStatusBadge, WarningList } from '../forensics/ForensicPrimitives';
import { evidenceStatusItems } from '../../utils/videoForensicPresentation';
import { FileOverviewRow } from '../forensics/ForensicOverviewRows';

function usefulFileInsights(evidence: ForensicEvidence): ForensicInsight[] {
  return (evidence.assessment?.key_insights ?? [])
    .filter((insight) =>
      !insight.code.startsWith('c2pa.') &&
      insight.category !== 'provenance' &&
      insight.category !== 'similarity' &&
      insight.code !== 'timeline.capture_time_not_present' &&
      insight.code !== 'origin.embedded_device' &&
      insight.code !== 'origin.location_metadata_present' &&
      !insight.code.startsWith('workflow.'),
    )
    .slice(0, 2);
}

function FileChecksCard({ evidence }: { evidence: ForensicEvidence }) {
  const assessment = evidence.assessment;
  const insufficient = !assessment || assessment.assessment_state === 'insufficient_evidence' || assessment.assessment_state === 'collection_failed';
  const hasMaterialConcerns = Boolean(
    assessment &&
    (assessment.assessment_state === 'review_signals_present' || assessment.assessment_state === 'strong_conflicts_present'),
  );
  const insights = usefulFileInsights(evidence);
  const tone = insufficient
    ? 'border-gray-200 bg-gray-50 dark:border-navy-700 dark:bg-navy-800'
    : assessment?.concern_band === 'high'
      ? 'border-red-200 bg-red-50/60 dark:border-red-900 dark:bg-red-950/20'
      : assessment?.concern_band === 'moderate'
        ? 'border-amber-200 bg-amber-50/60 dark:border-amber-900 dark:bg-amber-950/20'
        : 'border-blue-200 bg-blue-50/60 dark:border-blue-900 dark:bg-blue-950/20';

  const heading = insufficient
    ? 'Not enough file evidence was available'
    : hasMaterialConcerns
      ? assessment?.headline ?? 'Some file details need review'
      : 'No additional file conflicts found';

  return (
    <section className={`min-w-0 rounded-2xl border p-4 shadow-sm sm:p-5 ${tone}`} aria-labelledby="file-checks-heading">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">File checks</p>
          <h3 id="file-checks-heading" className="mt-1 text-lg font-semibold text-gray-900 dark:text-white">{heading}</h3>
        </div>
        {!insufficient && !hasMaterialConcerns ? <CheckCircle2Icon className="h-6 w-6 flex-none text-blue-600 dark:text-blue-300" aria-hidden="true" /> : null}
      </div>

      {assessment ? (
        <div className="mt-3 flex flex-wrap gap-2 text-xs font-medium">
          <span className="rounded-full border border-current/15 bg-white/70 px-2.5 py-1 text-gray-700 dark:bg-navy-900/50 dark:text-gray-200">
            {insufficient ? 'Limited evidence' : `${assessment.concern_band} file-conflict concern`}
          </span>
          <span className="rounded-full border border-current/15 bg-white/70 px-2.5 py-1 text-gray-700 dark:bg-navy-900/50 dark:text-gray-200" aria-label={`Evidence coverage ${assessment.evidence_coverage_score} percent`}>
            {assessment.evidence_coverage_score}% evidence collected
          </span>
        </div>
      ) : null}

      {insights.length > 0 ? (
        <ul className="mt-4 space-y-2 text-sm text-gray-700 dark:text-gray-300">
          {insights.map((insight) => (
            <li key={insight.code} className="flex items-start gap-2">
              <InfoIcon className="mt-0.5 h-4 w-4 flex-none text-gray-500" aria-hidden="true" />
              <span>{insight.user_message}</span>
            </li>
          ))}
        </ul>
      ) : null}

      {!assessment ? (
        <p className="mt-3 text-sm text-gray-600 dark:text-gray-400">This older result has no summarized file checks.</p>
      ) : null}
    </section>
  );
}

function EvidenceCollectionStatus({ evidence }: { evidence: ForensicEvidence }) {
  const warnings = [...new Set([
    ...evidence.warnings,
    ...evidence.metadata.warnings,
    ...evidence.c2pa.warnings,
    ...evidence.perceptual_fingerprint.warnings,
  ])];
  return (
    <section className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm dark:border-navy-700 dark:bg-navy-800 sm:p-5" aria-labelledby="evidence-collection-heading">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 id="evidence-collection-heading" className="font-semibold text-gray-900 dark:text-white">Evidence collection status</h3>
          <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">Each extractor reports independently; unavailable evidence does not imply manipulation.</p>
        </div>
        <ForensicStatusBadge status={evidence.status} />
      </div>
      <dl className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {evidenceStatusItems(evidence).slice(1).map((item) => (
          <div key={item.label} className="flex min-w-0 items-center justify-between gap-2 rounded-lg border border-gray-200 p-2.5 dark:border-navy-700">
            <dt className="min-w-0 text-xs font-medium text-gray-600 dark:text-gray-300">{item.label}</dt>
            <dd><ForensicStatusBadge status={item.status} /></dd>
          </div>
        ))}
      </dl>
      <WarningList warnings={warnings} />
    </section>
  );
}

export function EvidenceAtGlance({ evidence, isLoading, analysisId, canRevealPreciseLocation = false }: { evidence?: ForensicEvidence; isLoading: boolean; analysisId?: string; canRevealPreciseLocation?: boolean }) {
  if (isLoading) {
    return (
      <div data-result-component="forensic-summary" aria-busy="true" aria-label="Collecting forensic evidence">
        <div className="h-48 rounded-2xl shimmer" />
      </div>
    );
  }

  if (!evidence) {
    return (
      <div data-result-component="forensic-summary" className="flex items-start gap-3 rounded-2xl border border-gray-200 bg-gray-50 p-5 dark:border-navy-700 dark:bg-navy-800">
        <FlaskConicalIcon className="mt-0.5 h-5 w-5 flex-none text-gray-500" aria-hidden="true" />
        <div>
          <h3 className="font-semibold text-gray-900 dark:text-white">Forensic evidence is unavailable</h3>
          <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">This saved result may predate forensic collection.</p>
        </div>
      </div>
    );
  }

  return (
    <div data-result-component="forensic-summary" className="space-y-4">
      <EvidenceCollectionStatus evidence={evidence} />
      <FileOverviewRow evidence={evidence} />
      <ProvenanceCredentialsCard c2pa={evidence.c2pa} />
      <div className="grid min-w-0 gap-4 lg:grid-cols-2">
        <FileChecksCard evidence={evidence} />
        <OriginHistoryCard creationInfo={evidence.creation_info} metadata={evidence.metadata} analysisId={analysisId} canRevealPreciseLocation={canRevealPreciseLocation} />
      </div>
    </div>
  );
}

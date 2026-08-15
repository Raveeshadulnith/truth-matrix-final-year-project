import {
  AlertTriangleIcon,
  CheckCircle2Icon,
  CircleHelpIcon,
  InfoIcon,
} from 'lucide-react';
import type {
  ForensicEvidence,
  ForensicConcernBand,
  ForensicInsightTone,
  ModelForensicAlignment,
} from '../../api/deepfakeApi';
import { ForensicStatusBadge } from './ForensicPrimitives';

const TONE_STYLES: Record<ForensicInsightTone, string> = {
  positive: 'border-blue-200 bg-blue-50/70 dark:border-blue-900 dark:bg-blue-950/20',
  neutral: 'border-gray-200 bg-white dark:border-navy-700 dark:bg-navy-800',
  caution: 'border-amber-200 bg-amber-50/70 dark:border-amber-900 dark:bg-amber-950/20',
  warning: 'border-red-200 bg-red-50/70 dark:border-red-900 dark:bg-red-950/20',
};

const TONE_ICONS = {
  positive: CheckCircle2Icon,
  neutral: InfoIcon,
  caution: CircleHelpIcon,
  warning: AlertTriangleIcon,
} as const;

function alignmentStyle(alignment: ModelForensicAlignment): string {
  if (alignment.alignment_state === 'insufficient_for_comparison') {
    return 'border-gray-200 bg-gray-50 text-gray-800 dark:border-navy-700 dark:bg-navy-800 dark:text-gray-200';
  }
  if (alignment.forensic_assessment_state === 'strong_conflicts_present') {
    return 'border-red-200 bg-red-50/70 text-red-900 dark:border-red-900 dark:bg-red-950/20 dark:text-red-200';
  }
  if (
    alignment.alignment_state === 'conflicts_with_model_result' ||
    alignment.forensic_assessment_state === 'review_signals_present'
  ) {
    return 'border-amber-200 bg-amber-50/70 text-amber-900 dark:border-amber-900 dark:bg-amber-950/20 dark:text-amber-200';
  }
  return 'border-violet-200 bg-violet-50/70 text-violet-900 dark:border-violet-900 dark:bg-violet-950/20 dark:text-violet-200';
}

function summaryStyle(
  band: ForensicConcernBand | undefined,
  unavailable: boolean,
): string {
  if (unavailable) {
    return 'border-gray-200 bg-gray-50/70 dark:border-navy-700 dark:bg-navy-800/70';
  }
  if (band === 'high') {
    return 'border-red-200 bg-red-50/50 dark:border-red-900 dark:bg-red-950/15';
  }
  if (band === 'moderate') {
    return 'border-amber-200 bg-amber-50/50 dark:border-amber-900 dark:bg-amber-950/15';
  }
  return 'border-blue-200 bg-blue-50/50 dark:border-blue-900 dark:bg-blue-950/15';
}

export function ForensicSummaryCard({
  evidence,
  alignment,
}: {
  evidence: ForensicEvidence;
  alignment?: ModelForensicAlignment;
}) {
  const assessment = evidence.assessment;
  const effectiveAlignment = alignment ?? assessment?.model_alignment ?? undefined;
  const credentialInsightPresent = assessment?.key_insights.some((insight) =>
    insight.code.startsWith('c2pa.')
  ) ?? false;
  const primaryInsights = assessment?.key_insights
    .filter((insight) => !insight.code.startsWith('c2pa.'))
    .slice(0, 5) ?? [];
  const assessmentUnavailable =
    assessment?.assessment_state === 'insufficient_evidence' ||
    assessment?.assessment_state === 'collection_failed';
  const badgeStatus = assessmentUnavailable
    ? 'insufficient_evidence'
    : assessment?.concern_band ?? evidence.status;
  const badgeLabel = assessmentUnavailable
    ? 'Insufficient evidence'
    : assessment
      ? `${assessment.concern_band[0].toUpperCase()}${assessment.concern_band.slice(1)} concern`
      : undefined;

  return (
    <section
      className={`rounded-2xl border p-4 sm:p-5 ${summaryStyle(assessment?.concern_band, assessmentUnavailable)}`}
      aria-label="Forensic evidence summary"
    >
      <div className="flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-start">
        <div className="min-w-0">
          <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Forensic review
          </p>
          <h3 className="mt-1 text-xl font-semibold text-gray-900 dark:text-white">
            {assessment?.headline ?? 'Detailed forensic evidence is available'}
          </h3>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-gray-700 dark:text-gray-300">
            {assessment?.summary ??
              'This older result contains technical evidence but does not include a plain-language assessment.'}
          </p>
        </div>
        <ForensicStatusBadge status={badgeStatus} label={badgeLabel} />
      </div>

      {assessment ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <div className="rounded-xl border border-gray-200 bg-white p-3 dark:border-navy-700 dark:bg-navy-800">
            <p className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
              Review concern
            </p>
            <p
              className="mt-1 text-2xl font-bold text-gray-900 dark:text-white"
              aria-label={`Review concern score ${assessment.review_concern_score} out of 100`}
            >
              {assessment.review_concern_score}<span className="text-sm font-normal text-gray-500">/100</span>
            </p>
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              This score prioritizes file-level signals for review. It is not the probability that the media is fake.
            </p>
          </div>
          <div className="rounded-xl border border-gray-200 bg-white p-3 dark:border-navy-700 dark:bg-navy-800">
            <p className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
              Evidence coverage
            </p>
            <p
              className="mt-1 text-2xl font-bold text-gray-900 dark:text-white"
              aria-label={`Evidence coverage score ${assessment.evidence_coverage_score} out of 100`}
            >
              {assessment.evidence_coverage_score}<span className="text-sm font-normal text-gray-500">/100</span>
            </p>
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              How much applicable file evidence was collected successfully.
            </p>
          </div>
        </div>
      ) : null}

      {effectiveAlignment ? (
        <div className={`mt-4 rounded-xl border p-3 ${alignmentStyle(effectiveAlignment)}`}>
          <p className="text-sm font-semibold">
            {effectiveAlignment.headline}
          </p>
          <p className="mt-1 text-sm leading-relaxed opacity-90">
            {effectiveAlignment.summary}
          </p>
        </div>
      ) : null}

      {primaryInsights.length > 0 ? (
        <div className="mt-5">
          <h4 className="text-sm font-semibold text-gray-900 dark:text-white">What the file evidence says</h4>
          <ul className="mt-3 space-y-2">
            {primaryInsights.map((insight) => {
              const Icon = TONE_ICONS[insight.tone];
              return (
                <li key={insight.code} className={`rounded-xl border p-3 ${TONE_STYLES[insight.tone]}`}>
                  <div className="flex items-start gap-2.5">
                    <Icon className="mt-0.5 h-4 w-4 flex-none text-gray-600 dark:text-gray-300" />
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-gray-900 dark:text-white">{insight.title}</p>
                      <p className="mt-1 break-words text-sm leading-relaxed text-gray-700 dark:text-gray-300">
                        {insight.user_message}
                      </p>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}

      {credentialInsightPresent ? (
        <p className="mt-4 text-sm text-gray-600 dark:text-gray-300">
          Content Credentials origin and verification details are shown in the{' '}
          <a href="#content-credentials" className="font-semibold text-violet-700 underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 dark:text-violet-300">
            Provenance and Content Credentials card
          </a>.
        </p>
      ) : null}

    </section>
  );
}

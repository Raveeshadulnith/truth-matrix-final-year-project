import React from 'react';
import type {
  ExtractorStatus,
  ForensicFinding,
  ForensicFindingSeverity,
} from '../../api/deepfakeApi';
import {
  EmptyEvidenceMessage,
  EvidenceCard,
  ForensicStatusBadge,
  SafeJsonFields,
  TechnicalDetails,
} from './ForensicPrimitives';

const SEVERITY_STYLES: Record<ForensicFindingSeverity, string> = {
  info: 'border-cyan-200 bg-cyan-50/60 dark:border-cyan-900 dark:bg-cyan-950/20',
  low: 'border-gray-200 bg-gray-50 dark:border-navy-700 dark:bg-navy-900/40',
  medium: 'border-amber-200 bg-amber-50/60 dark:border-amber-900 dark:bg-amber-950/20',
  high: 'border-red-200 bg-red-50/60 dark:border-red-900 dark:bg-red-950/20',
};

function FindingItem({ finding }: { finding: ForensicFinding }) {
  return (
    <li className={`rounded-xl border p-3 sm:p-4 ${SEVERITY_STYLES[finding.severity]}`}>
      <div className="flex flex-col items-start justify-between gap-2 sm:flex-row sm:items-center">
        <div className="min-w-0">
          <p className="break-words font-semibold text-gray-900 dark:text-white">{finding.title}</p>
          <p className="mt-0.5 break-all font-mono text-xs text-gray-500 dark:text-gray-400">
            {finding.code}
          </p>
        </div>
        <ForensicStatusBadge status={finding.severity} label={`${finding.severity} severity`} />
      </div>
      <p className="mt-3 break-words text-sm leading-6 text-gray-700 dark:text-gray-300">
        {finding.explanation}
      </p>
      <TechnicalDetails>
        <div className="mb-3 grid gap-2 text-sm sm:grid-cols-2">
          <div>
            <span className="text-gray-500 dark:text-gray-400">Method: </span>
            <span className="break-words text-gray-900 dark:text-white">
              {finding.method ?? 'Not specified'}
            </span>
          </div>
          <div>
            <span className="text-gray-500 dark:text-gray-400">Version: </span>
            <span className="break-words text-gray-900 dark:text-white">
              {finding.method_version ?? 'Not specified'}
            </span>
          </div>
        </div>
        <SafeJsonFields value={finding.evidence} />
        {finding.limitations.length > 0 ? (
          <div className="mt-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
              Limitations
            </p>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-gray-700 dark:text-gray-300">
              {finding.limitations.map((limitation, index) => (
                <li key={`${limitation}-${index}`} className="break-words">{limitation}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </TechnicalDetails>
    </li>
  );
}

function FindingList({
  title,
  description,
  status,
  findings,
  emptyMessage,
}: {
  title: string;
  description: string;
  status: ExtractorStatus;
  findings: ForensicFinding[];
  emptyMessage: string;
}) {
  return (
    <EvidenceCard title={title} description={description} status={status}>
      {findings.length > 0 ? (
        <ul className="space-y-3">
          {findings.map((finding) => (
            <FindingItem key={`${finding.code}-${finding.title}`} finding={finding} />
          ))}
        </ul>
      ) : (
        <EmptyEvidenceMessage>{emptyMessage}</EmptyEvidenceMessage>
      )}
    </EvidenceCard>
  );
}

export function InconsistencyList({
  status,
  findings,
}: {
  status: ExtractorStatus;
  findings: ForensicFinding[];
}) {
  return (
    <FindingList
      title="Metadata consistency"
      description="Deterministic conflicts or workflow observations, with conservative limitations."
      status={status}
      findings={findings}
      emptyMessage={
        status === 'available'
          ? 'No deterministic metadata inconsistencies were identified.'
          : `Consistency checks were ${status.replace(/_/g, ' ')}.`
      }
    />
  );
}

export function CompressionIndicatorList({
  status,
  findings,
}: {
  status: ExtractorStatus;
  findings: ForensicFinding[];
}) {
  return (
    <FindingList
      title="Compression & encoding indicators"
      description="Encoding observations are heuristic review signals, not proof of editing or fakery."
      status={status}
      findings={findings}
      emptyMessage={
        status === 'available'
          ? 'No reportable compression or encoding indicators were returned.'
          : `Compression checks were ${status.replace(/_/g, ' ')}.`
      }
    />
  );
}

import type { ExtractorStatus, SimilarityMatch } from '../../api/deepfakeApi';
import { formatDate } from '../../utils/formatters';
import {
  EmptyEvidenceMessage,
  EvidenceCard,
  ForensicStatusBadge,
  SafeJsonFields,
  TechnicalDetails,
} from './ForensicPrimitives';

export function SimilarityMatchesCard({
  status,
  matches,
}: {
  status: ExtractorStatus;
  matches: SimilarityMatch[];
}) {
  return (
    <EvidenceCard
      title="Duplicate & similarity matches"
      status={status}
      description="Matches are restricted to your history and do not prove common authorship or malicious editing."
    >
      {matches.length > 0 ? (
        <ul className="space-y-3">
          {matches.map((match) => (
            <li key={match.analysis_id} className="min-w-0 rounded-xl border border-gray-200 p-3 dark:border-navy-700 sm:p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <p className="break-words font-semibold text-gray-900 dark:text-white">{match.filename}</p>
                  <p className="mt-1 break-all font-mono text-xs text-gray-500 dark:text-gray-400">{match.analysis_id}</p>
                  <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{formatDate(match.created_at)}</p>
                </div>
                <div className="flex flex-wrap items-center gap-2 sm:justify-end">
                  <ForensicStatusBadge status={match.match_type} label={match.match_type === 'exact' ? 'Exact match' : 'Near match'} />
                  <span className="rounded-full bg-cyan-100 px-2.5 py-1 text-xs font-semibold text-cyan-900 dark:bg-cyan-900/40 dark:text-cyan-200">
                    {(match.similarity_score * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
              <TechnicalDetails>
                <dl className="mb-3 grid gap-2 text-sm sm:grid-cols-2">
                  <div>
                    <dt className="text-gray-500 dark:text-gray-400">Algorithm</dt>
                    <dd className="break-words font-medium text-gray-900 dark:text-white">
                      {match.algorithm}{match.algorithm_version ? ` @ ${match.algorithm_version}` : ''}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-gray-500 dark:text-gray-400">Distance</dt>
                    <dd className="font-medium text-gray-900 dark:text-white">
                      {match.distance != null ? match.distance.toFixed(4) : 'Not applicable'}
                    </dd>
                  </div>
                </dl>
                <SafeJsonFields value={match.details} />
              </TechnicalDetails>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyEvidenceMessage>
          {status === 'available'
            ? 'No exact or compatible near matches were found in your bounded history search.'
            : `History matching was ${status.replace(/_/g, ' ')}.`}
        </EmptyEvidenceMessage>
      )}
    </EvidenceCard>
  );
}

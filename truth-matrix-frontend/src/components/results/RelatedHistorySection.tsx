import { CopyCheckIcon, HistoryIcon } from 'lucide-react';
import type { SimilarityMatch } from '../../api/deepfakeApi';
import { formatDate } from '../../utils/formatters';

function sortMatches(matches: SimilarityMatch[]): SimilarityMatch[] {
  return [...matches].sort((left, right) => {
    if (left.match_type !== right.match_type) return left.match_type === 'exact' ? -1 : 1;
    return right.similarity_score - left.similarity_score;
  });
}

export function RelatedHistorySection({ matches }: { matches: SimilarityMatch[] }) {
  if (matches.length === 0) return null;
  const ranked = sortMatches(matches);
  const best = ranked[0];

  return (
    <section data-result-section="related-history" aria-labelledby="related-history-heading">
      <h3 id="related-history-heading" className="text-lg font-semibold text-gray-900 dark:text-white">Found in your history</h3>
      <div className="mt-3 flex flex-col gap-3 rounded-2xl border border-gray-200 bg-white p-4 dark:border-navy-700 dark:bg-navy-800 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          {best.match_type === 'exact' ? <CopyCheckIcon className="mt-0.5 h-5 w-5 flex-none text-violet-600" /> : <HistoryIcon className="mt-0.5 h-5 w-5 flex-none text-cyan-600" />}
          <div className="min-w-0">
            <p className="break-words font-semibold text-gray-900 dark:text-white">{best.filename}</p>
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{formatDate(best.created_at)}{ranked.length > 1 ? ` / ${ranked.length - 1} more match${ranked.length === 2 ? '' : 'es'}` : ''}</p>
          </div>
        </div>
        <div className="flex flex-none items-center gap-2">
          <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${best.match_type === 'exact' ? 'bg-violet-100 text-violet-800 dark:bg-violet-900/40 dark:text-violet-200' : 'bg-cyan-100 text-cyan-800 dark:bg-cyan-900/40 dark:text-cyan-200'}`}>
            {best.match_type === 'exact' ? 'Exact match' : 'Near match'}
          </span>
          <span className="text-sm font-semibold text-gray-900 dark:text-white">{(best.similarity_score * 100).toFixed(1)}%</span>
        </div>
      </div>
      <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">Matches are limited to your saved analyses and do not prove who created or changed the file.</p>
    </section>
  );
}

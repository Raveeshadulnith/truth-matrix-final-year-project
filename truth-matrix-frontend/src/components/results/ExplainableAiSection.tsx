import { BrainCircuitIcon } from 'lucide-react';
import type { Analysis } from '../../store/analysisStore';
import { ArtifactList } from '../analysis/ArtifactList';
import { HeatmapViewer } from '../analysis/HeatmapViewer';

export function ExplainableAiSection({ analysis }: { analysis: Analysis }) {
  const hasVisualExplanation = Boolean(analysis.heatmapUrl || analysis.xaiOverlayUrl || analysis.xaiPanelUrl);
  const hasFindings = analysis.artifacts.length > 0;
  const isAudio = analysis.fileType === 'audio';
  const unavailableMessage = isAudio
    ? 'This audio result includes its verdict and class probabilities, but the classifier does not return a visual explanation or temporal localization.'
    : analysis.fileType === 'image'
      ? 'This CvT-13 result includes its verdict and class probabilities, but no heatmap, overlay, or explanation panel was generated.'
      : 'This result includes its verdict and class probabilities, but no visual explanation asset was returned.';

  return (
    <section data-result-component="explainable-ai" aria-labelledby="explainable-ai-heading">
      <div>
        <h3 id="explainable-ai-heading" className="text-xl font-bold text-gray-900 dark:text-white">{isAudio ? 'Model explanation details' : 'Visual model explanation'}</h3>
        <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{isAudio ? 'Audio model output is shown without fabricated waveform highlights; no temporal localization is available.' : 'Visual explanation assets appear here only when the backend actually returns them.'}</p>
      </div>

      {!hasVisualExplanation ? (
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <div className="flex items-start gap-3 rounded-2xl border border-gray-200 bg-gray-50 p-5 dark:border-navy-700 dark:bg-navy-800">
            <BrainCircuitIcon className="mt-0.5 h-5 w-5 flex-none text-gray-500" aria-hidden="true" />
            <div>
              <h3 className="font-semibold text-gray-900 dark:text-white">No visual explanation is available</h3>
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{unavailableMessage}</p>
            </div>
          </div>
          {hasFindings ? (
            <aside className="min-w-0 rounded-2xl border border-gray-200 bg-white p-4 dark:border-navy-700 dark:bg-navy-800 sm:p-5" aria-label="Model findings">
              <ArtifactList artifacts={analysis.artifacts} />
            </aside>
          ) : null}
        </div>
      ) : (
        <div className="mt-4 grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1.65fr)_minmax(18rem,0.85fr)]">
          <HeatmapViewer
            key={analysis.id}
            originalUrl={analysis.mediaUrl || analysis.thumbnailUrl}
            heatmapUrl={analysis.heatmapUrl}
            xaiOverlayUrl={analysis.xaiOverlayUrl}
            xaiPanelUrl={analysis.xaiPanelUrl}
            filename={analysis.filename}
            mediaType={analysis.fileType}
          />
          <aside className="min-w-0 rounded-2xl border border-gray-200 bg-white p-4 dark:border-navy-700 dark:bg-navy-800 sm:p-5" aria-label="Model findings">
            <ArtifactList artifacts={analysis.artifacts} />
          </aside>
        </div>
      )}
    </section>
  );
}

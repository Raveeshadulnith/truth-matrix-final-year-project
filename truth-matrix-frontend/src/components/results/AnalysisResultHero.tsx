import {
  AlertTriangleIcon,
  FileAudioIcon,
  ShieldAlertIcon,
  ShieldCheckIcon,
} from 'lucide-react';
import type { Analysis } from '../../store/analysisStore';

const RESULT_STYLES = {
  fake: {
    label: 'Suspected Deepfake',
    Icon: ShieldAlertIcon,
    surface: 'border-red-200 bg-red-50/70 dark:border-red-900 dark:bg-red-950/20',
    text: 'text-red-700 dark:text-red-300',
  },
  real: {
    label: 'Authentic',
    Icon: ShieldCheckIcon,
    surface: 'border-blue-200 bg-blue-50/70 dark:border-blue-900 dark:bg-blue-950/20',
    text: 'text-blue-700 dark:text-blue-300',
  },
  uncertain: {
    label: 'Uncertain',
    Icon: AlertTriangleIcon,
    surface: 'border-amber-200 bg-amber-50/70 dark:border-amber-900 dark:bg-amber-950/20',
    text: 'text-amber-700 dark:text-amber-300',
  },
} as const;

function MediaPreview({ analysis }: { analysis: Analysis }) {
  const source = analysis.mediaUrl || analysis.thumbnailUrl;

  if (!source) {
    return (
      <div className="flex min-h-72 items-center justify-center rounded-2xl border border-dashed border-gray-300 bg-gray-50 px-6 text-center text-sm text-gray-500 dark:border-navy-600 dark:bg-navy-900/60 dark:text-gray-400">
        A preview is not available for this saved analysis.
      </div>
    );
  }

  if (analysis.fileType === 'video') {
    return (
      <video
        controls
        playsInline
        preload="metadata"
        src={source}
        className="max-h-[28rem] w-full rounded-2xl bg-black object-contain"
        aria-label={`Video preview for ${analysis.filename}`}
      />
    );
  }

  if (analysis.fileType === 'audio') {
    return (
      <div className="flex min-h-72 flex-col items-center justify-center gap-5 rounded-2xl border border-gray-200 bg-gray-50 p-6 dark:border-navy-700 dark:bg-navy-900/60">
        <span className="rounded-2xl bg-violet-100 p-4 text-violet-700 dark:bg-violet-900/40 dark:text-violet-200">
          <FileAudioIcon className="h-9 w-9" aria-hidden="true" />
        </span>
        <p className="text-sm font-medium text-gray-800 dark:text-gray-200">Audio preview</p>
        <audio controls preload="metadata" src={source} className="w-full max-w-md" aria-label={`Audio preview for ${analysis.filename}`} />
      </div>
    );
  }

  return (
    <div className="flex min-h-72 items-center justify-center overflow-hidden rounded-2xl bg-gray-100 dark:bg-navy-900">
      <img
        src={source}
        alt={`Uploaded media preview: ${analysis.filename}`}
        className="max-h-[28rem] w-full object-contain"
      />
    </div>
  );
}

function ProbabilityBar({ label, value, tone }: { label: string; value: number; tone: 'red' | 'blue' }) {
  const safeValue = Math.max(0, Math.min(100, value));
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between gap-3 text-sm">
        <span className="font-medium text-gray-700 dark:text-gray-300">{label}</span>
        <span className="font-semibold text-gray-900 dark:text-white">{safeValue.toFixed(1)}%</span>
      </div>
      <div
        className="h-2 overflow-hidden rounded-full bg-gray-200 dark:bg-navy-700"
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={safeValue}
      >
        <div
          className={`h-full rounded-full ${tone === 'red' ? 'bg-red-500' : 'bg-blue-500'}`}
          style={{ width: `${safeValue}%` }}
        />
      </div>
    </div>
  );
}

export function AnalysisResultHero({ analysis }: { analysis: Analysis }) {
  const config = RESULT_STYLES[analysis.result];
  const limitation =
    analysis.fileType === 'audio'
      ? 'This model classifies audio between authentic/real and synthetic/fake classes. It does not prove speaker identity or a voice-cloning method, and it does not provide temporal localization.'
      : analysis.fileType === 'video'
        ? 'This model classifies sampled video frames between authentic/real and suspected-deepfake classes. It does not prove a particular manipulation method.'
        : 'This model classifies images between authentic/real and AI-generated/fake classes. It does not prove a particular editing or facial-manipulation technique.';

  return (
    <section
      data-result-component="model-verdict"
      aria-labelledby="primary-result-heading"
      className="grid gap-6 rounded-3xl border border-gray-200 bg-white p-4 shadow-sm dark:border-navy-700 dark:bg-navy-800 sm:p-6 lg:grid-cols-12 lg:gap-8"
    >
      <div className="min-w-0 lg:col-span-5">
        <MediaPreview analysis={analysis} />
      </div>

      <div className="min-w-0 lg:col-span-7">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-gray-500 dark:text-gray-400">Model verdict</p>
        <div className={`mt-2 rounded-2xl border p-4 ${config.surface}`}>
          <div className="flex items-center gap-3">
            <config.Icon className={`h-8 w-8 flex-none ${config.text}`} aria-hidden="true" />
            <div>
              <h2 id="primary-result-heading" className={`text-2xl font-bold sm:text-3xl ${config.text}`}>{config.label}</h2>
              <p className="mt-1 text-sm text-gray-700 dark:text-gray-300">Predicted-class confidence: <strong>{analysis.confidence.toFixed(1)}%</strong></p>
            </div>
          </div>
        </div>

        <div className="mt-5 space-y-4" aria-label="Model probability breakdown">
          <ProbabilityBar label="AI-generated / fake class probability" value={analysis.fakeProb} tone="red" />
          <ProbabilityBar label="Authentic / real class probability" value={analysis.realProb} tone="blue" />
        </div>

        <p className="mt-4 text-sm text-gray-600 dark:text-gray-400">
          Model version: <strong className="font-semibold text-gray-900 dark:text-white">{analysis.modelVersion ?? 'Not available for this legacy result'}</strong>
        </p>

        {analysis.explanation ? (
          <div className="mt-5">
            <h2 className="text-sm font-semibold text-gray-900 dark:text-white">Model explanation</h2>
            <p className="mt-1 text-sm leading-relaxed text-gray-700 dark:text-gray-300">{analysis.explanation}</p>
          </div>
        ) : null}

        <p className="mt-5 border-t border-gray-200 pt-4 text-xs text-gray-500 dark:border-navy-700 dark:text-gray-400">
          {limitation}
        </p>
      </div>
    </section>
  );
}

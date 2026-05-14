import React, { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAnalysisStore } from '../store/analysisStore';
import { ROUTES } from '../utils/constants';

const mediaOptions = [
  {
    value: 'image',
    label: 'Image',
    accept: '.jpg,.jpeg,.png,.webp',
    helperText: 'Upload JPG, JPEG, PNG, or WEBP images.',
  },
  {
    value: 'video',
    label: 'Video',
    accept: '.mp4,.mov,.avi,.mkv',
    helperText: 'Upload MP4, MOV, AVI, or MKV videos.',
  },
  {
    value: 'audio',
    label: 'Audio',
    accept: '.wav,.mp3,.m4a',
    helperText: 'Upload WAV, MP3, or M4A audio clips.',
  },
];

function getSelectedOption(mediaType: string) {
  return mediaOptions.find((option) => option.value === mediaType) ?? mediaOptions[0];
}

function formatTitle(value?: string) {
  if (!value) {
    return 'Unknown';
  }

  return value.charAt(0).toUpperCase() + value.slice(1);
}

export function AnalysisPage() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const { startUpload } = useAnalysisStore();
  const [mediaType, setMediaType] = useState('image');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<any>(null);

  const selectedOption = getSelectedOption(mediaType);
  const heatmapSource = result?.heatmapUrl;
  const isSuspectedDeepfake = result?.result === 'fake';

  function handleMediaTypeChange(event: React.ChangeEvent<HTMLSelectElement>) {
    setMediaType(event.target.value);
    setSelectedFile(null);
    setResult(null);
    setError('');

    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] || null;
    setSelectedFile(file);
    setResult(null);
    setError('');
  }

  async function handleAnalyze(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setResult(null);

    if (!selectedFile) {
      setError('Please choose a file before starting analysis.');
      return;
    }

    setIsLoading(true);

    try {
      await startUpload(selectedFile);
      const analysisResult = useAnalysisStore.getState().currentAnalysis;
      setResult(analysisResult);
      navigate(ROUTES.RESULTS);
    } catch (apiError) {
      setError(
        apiError instanceof Error
          ? apiError.message
          : 'Something went wrong during analysis.'
      );
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-cyan-50 to-blue-100 px-4 py-10 text-slate-950 dark:from-navy-900 dark:via-navy-800 dark:to-slate-950 dark:text-white sm:px-6 lg:px-8">
      <div className="mx-auto max-w-5xl">
        <section className="mb-8 text-center">
          <p className="mb-3 text-sm font-semibold uppercase tracking-[0.3em] text-cyan-600 dark:text-neon-cyan">
            Truth Matrix
          </p>
          <h1 className="text-4xl font-black tracking-tight sm:text-5xl">
            Truth Matrix Deepfake Detection
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-base text-slate-600 dark:text-slate-300 sm:text-lg">
            Upload image, video, or audio evidence and let the FastAPI backend return
            the analysis result.
          </p>
        </section>

        <div className="grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
          <form
            onSubmit={handleAnalyze}
            className="rounded-3xl border border-white/70 bg-white/85 p-6 shadow-2xl shadow-cyan-950/10 backdrop-blur dark:border-cyan-400/15 dark:bg-navy-800/80 dark:shadow-black/30 sm:p-8"
          >
            <div className="mb-6">
              <label
                htmlFor="mediaType"
                className="mb-2 block text-sm font-semibold text-slate-700 dark:text-slate-200"
              >
                Media type
              </label>
              <select
                id="mediaType"
                value={mediaType}
                onChange={handleMediaTypeChange}
                disabled={isLoading}
                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-slate-950 outline-none transition focus:border-cyan-500 focus:ring-4 focus:ring-cyan-500/15 disabled:cursor-not-allowed disabled:opacity-70 dark:border-navy-600 dark:bg-navy-900 dark:text-white"
              >
                {mediaOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
                {selectedOption.helperText}
              </p>
            </div>

            <div className="mb-6">
              <label
                htmlFor="mediaFile"
                className="mb-2 block text-sm font-semibold text-slate-700 dark:text-slate-200"
              >
                Select file
              </label>
              <div className="rounded-3xl border-2 border-dashed border-cyan-200 bg-cyan-50/70 p-5 transition dark:border-cyan-400/25 dark:bg-cyan-400/5">
                <input
                  ref={fileInputRef}
                  id="mediaFile"
                  type="file"
                  accept={selectedOption.accept}
                  onChange={handleFileChange}
                  disabled={isLoading}
                  className="block w-full cursor-pointer text-sm text-slate-600 file:mr-4 file:rounded-full file:border-0 file:bg-cyan-600 file:px-5 file:py-2.5 file:text-sm file:font-semibold file:text-white hover:file:bg-cyan-700 disabled:cursor-not-allowed dark:text-slate-300 dark:file:bg-neon-cyan dark:file:text-navy-900"
                />
                {selectedFile ? (
                  <p className="mt-4 rounded-2xl bg-white px-4 py-3 text-sm font-medium text-slate-700 shadow-sm dark:bg-navy-900 dark:text-slate-200">
                    Selected: {selectedFile.name}
                  </p>
                ) : (
                  <p className="mt-4 text-sm text-slate-500 dark:text-slate-400">
                    Choose one file to send to the backend using the form key named
                    &quot;file&quot;.
                  </p>
                )}
              </div>
            </div>

            {error && (
              <div className="mb-6 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-200">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={isLoading || !selectedFile}
              className="w-full rounded-2xl bg-gradient-to-r from-cyan-600 to-blue-700 px-6 py-3.5 text-base font-bold text-white shadow-lg shadow-cyan-600/25 transition hover:-translate-y-0.5 hover:shadow-xl hover:shadow-cyan-600/30 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0 dark:from-neon-cyan dark:to-neon-violet"
            >
              {isLoading ? 'Analyzing...' : 'Analyze'}
            </button>
          </form>

          <aside className="rounded-3xl border border-white/70 bg-white/70 p-6 shadow-2xl shadow-blue-950/10 backdrop-blur dark:border-cyan-400/15 dark:bg-navy-800/70 dark:shadow-black/30 sm:p-8">
            <div className="mb-5 flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-semibold uppercase tracking-[0.25em] text-slate-500 dark:text-slate-400">
                  Result
                </p>
                <h2 className="mt-1 text-2xl font-black">Analysis Card</h2>
              </div>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-600 dark:bg-navy-900 dark:text-slate-300">
                API Live
              </span>
            </div>

            {!result && !isLoading && (
              <div className="rounded-3xl border border-slate-200 bg-slate-50 p-6 text-slate-600 dark:border-navy-600 dark:bg-navy-900/70 dark:text-slate-300">
                Your backend response will appear here after analysis. No dummy frontend
                data is shown.
              </div>
            )}

            {isLoading && (
              <div className="rounded-3xl border border-cyan-200 bg-cyan-50 p-6 text-cyan-800 dark:border-cyan-400/25 dark:bg-cyan-400/10 dark:text-cyan-100">
                <div className="mb-4 h-2 overflow-hidden rounded-full bg-cyan-100 dark:bg-navy-900">
                  <div className="h-full w-2/3 animate-pulse rounded-full bg-cyan-600 dark:bg-neon-cyan" />
                </div>
                Analyzing...
              </div>
            )}

            {result && (
              <div className="space-y-4">
                <div
                  className={`rounded-3xl border p-5 ${
                    isSuspectedDeepfake
                      ? 'border-red-200 bg-red-50 text-red-950 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-100'
                      : 'border-emerald-200 bg-emerald-50 text-emerald-950 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-100'
                  }`}
                >
                  <p className="text-sm font-semibold uppercase tracking-[0.25em] opacity-75">
                    Result label
                  </p>
                  <p className="mt-2 text-3xl font-black">
                    {isSuspectedDeepfake ? 'Suspected Deepfake' : 'Authentic'}
                  </p>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="rounded-2xl bg-slate-50 p-4 dark:bg-navy-900/80">
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">
                      Media type
                    </p>
                    <p className="mt-2 text-lg font-bold">{formatTitle(result.fileType)}</p>
                  </div>

                  <div className="rounded-2xl bg-slate-50 p-4 dark:bg-navy-900/80">
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">
                      Confidence
                    </p>
                    <p className="mt-2 text-lg font-bold">
                      {Number(result.confidence).toFixed(2)}%
                    </p>
                  </div>
                </div>

                <div className="rounded-2xl bg-slate-50 p-4 dark:bg-navy-900/80">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">
                    Explanation
                  </p>
                  <p className="mt-2 leading-relaxed text-slate-700 dark:text-slate-200">
                    The backend saved this analysis to your Supabase-backed history.
                  </p>
                </div>

                {heatmapSource && (
                  <div className="rounded-2xl bg-slate-50 p-4 dark:bg-navy-900/80">
                    <p className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">
                      Heatmap
                    </p>
                    <img
                      src={heatmapSource}
                      alt="Explainable AI heatmap"
                      className="max-h-80 w-full rounded-xl object-contain"
                    />
                  </div>
                )}
              </div>
            )}
          </aside>
        </div>
      </div>
    </div>
  );
}

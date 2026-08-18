import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import {
  API_BASE_URL,
  ApiError,
  analyzeAudio,
  analyzeImage,
  analyzeImageUrl,
  analyzeVideo,
  deleteAnalysisResult,
  getAnalysisResults,
  type BackendAnalysisRecord,
  type BackendAnalysisResponse,
  type ForensicEvidence,
  type ModelForensicAlignment,
  type VideoSegmentSelection,
  type VideoMetadata,
} from '../api/deepfakeApi';
import { useAuthStore } from './authStore';
import { selectAnalysisEvidence } from '../utils/analysisEvidenceMapping';

export interface Analysis {
  id: string;
  ownerId?: string;
  filename: string;
  fileSize: number;
  fileType: 'image' | 'video' | 'audio';
  mediaUrl: string;
  thumbnailUrl: string;
  result: 'real' | 'fake' | 'uncertain';
  confidence: number;
  fakeProb: number;
  realProb: number;
  processingTime: number;
  heatmapUrl?: string;
  xaiOverlayUrl?: string;
  xaiPanelUrl?: string;
  xaiMethod?: string;
  xaiTargetClass?: string;
  xaiPredictedClass?: string;
  xaiLayer?: string;
  xaiMapStrength?: number;
  xaiError?: string;
  modelVersion: string | null;
  artifacts: Artifact[];
  createdAt: string;
  isPublic: boolean;
  shareToken?: string;
  explanation?: string;
  framesAnalyzed?: number;
  videoMetadata?: VideoMetadata;
  forensicEvidence?: ForensicEvidence;
  modelForensicAlignment?: ModelForensicAlignment;
}

export interface Artifact {
  id: string;
  type: string;
  confidence: number;
  location: string;
  description: string;
}

interface AnalysisState {
  analyses: Analysis[];
  currentAnalysis: Analysis | null;
  uploadProgress: number;
  isAnalyzing: boolean;
  isHistoryLoading: boolean;
  analysisStatus: 'idle' | 'uploading' | 'processing' | 'complete' | 'error';
  error: string | null;

  startUpload: (file: File, videoSegment?: VideoSegmentSelection) => Promise<void>;
  analyzeUrl: (url: string) => Promise<void>;
  fetchHistory: () => Promise<void>;
  setCurrentAnalysis: (analysis: Analysis | null) => void;
  deleteAnalysis: (id: string) => Promise<void>;
  clearHistory: () => void;
  setUploadProgress: (progress: number) => void;
  resetAnalysis: () => void;
}

type BackendAnalysis = BackendAnalysisRecord | BackendAnalysisResponse;

function resolveBackendUrl(url?: string | null): string {
  if (!url) {
    return '';
  }

  if (url.startsWith('http://') || url.startsWith('https://')) {
    return url;
  }

  if (url.startsWith('/')) {
    return `${API_BASE_URL}${url}`;
  }

  return `${API_BASE_URL}/${url}`;
}

function getSavedRecord(
  analysis: BackendAnalysis
): BackendAnalysisRecord | undefined {
  if ('saved_record' in analysis && analysis.saved_record) {
    return analysis.saved_record;
  }

  if ('created_at' in analysis) {
    return analysis;
  }

  return undefined;
}

function getFileType(file: File): 'image' | 'video' | 'audio' {
  const extension = file.name.split('.').pop()?.toLowerCase() || '';

  if (
    file.type.startsWith('video/') ||
    ['mp4', 'mov', 'avi', 'mkv', 'webm'].includes(extension)
  ) {
    return 'video';
  }

  if (file.type.startsWith('audio/') || ['wav', 'mp3', 'm4a'].includes(extension)) {
    return 'audio';
  }

  return 'image';
}

function resultFromLabel(label: string): 'real' | 'fake' | 'uncertain' {
  if (label === 'Authentic') {
    return 'real';
  }

  if (label === 'Suspected Deepfake') {
    return 'fake';
  }

  return 'uncertain';
}

function boundedFiniteNumber(value: unknown, fieldName: string): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    throw new Error(`The backend returned an invalid ${fieldName}.`);
  }
  return Math.max(0, Math.min(100, value));
}

function optionalBoundedProbability(
  value: unknown,
  fieldName: string
): number | undefined {
  if (value == null) return undefined;
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    throw new Error(`The backend returned an invalid ${fieldName}.`);
  }
  if (value < 0 || value > 100) {
    throw new Error(`The backend returned an out-of-range ${fieldName}.`);
  }
  return value;
}

function nullableModelVersion(value: unknown): string | null {
  if (value == null) return null;
  if (typeof value !== 'string' || !value.trim()) {
    throw new Error('The backend returned an invalid model version.');
  }
  return value;
}

function buildArtifacts(input: {
  mediaType: 'image' | 'video' | 'audio';
  result: 'real' | 'fake' | 'uncertain';
  confidence: number;
  fakeProb: number;
  realProb: number;
  heatmapUrl: string;
  hasVisualExplanation: boolean;
  xaiMethod?: string;
  xaiTargetClass?: string;
  xaiLayer?: string;
  xaiError?: string;
  framesAnalyzed?: number | null;
}): Artifact[] {
  const artifacts: Artifact[] = [];
  const method = input.xaiMethod?.trim();
  const targetText = input.xaiTargetClass
    ? input.xaiTargetClass.replace(/_/g, ' ')
    : 'model';

  if (input.result === 'fake') {
    artifacts.push({
      id: 'model_manipulation_signal',
      type:
        input.mediaType === 'video'
          ? 'frame_manipulation_signal'
          : input.mediaType === 'audio'
            ? 'audio_fake_classification'
          : 'ai_generated_classification',
      confidence: input.fakeProb,
      location:
        input.mediaType === 'video'
          ? 'sampled_video_frames'
          : 'model_output',
      description:
        input.mediaType === 'video'
          ? `The Keras video model found manipulation signals after averaging sampled frame predictions with ${input.fakeProb.toFixed(1)}% deepfake probability.`
          : input.mediaType === 'audio'
            ? `The Wav2Vec2 audio classifier assigned ${input.fakeProb.toFixed(1)}% probability to its fake class. This file-level classification does not identify a cloning tool, speaker, or manipulated interval.`
            : `The image classifier assigned ${input.fakeProb.toFixed(1)}% probability to its AI-generated/fake class. This classification does not identify a particular editing technique.`,
    });
  }

  if (input.mediaType === 'image' && input.hasVisualExplanation) {
    artifacts.push({
      id: 'xai_visual_explanation',
      type: 'model_visual_explanation',
      confidence:
        input.result === 'fake'
          ? input.fakeProb
          : input.result === 'real'
            ? input.realProb
            : input.confidence,
      location: 'image_attention_map',
      description: method
        ? `${method} returned a visual explanation for the ${targetText} class${input.xaiLayer ? ` using ${input.xaiLayer}` : ''}.`
        : 'The backend returned a visual explanation for this model result.',
    });
  }

  if (input.mediaType === 'image' && !input.hasVisualExplanation && input.xaiError) {
    artifacts.push({
      id: 'xai_generation_error',
      type: 'xai_generation_error',
      confidence: input.confidence,
      location: 'xai_backend',
      description: `A visual model explanation was unavailable for this request: ${input.xaiError}`,
    });
  }

  if (input.result === 'uncertain') {
    artifacts.push({
      id: 'low_confidence_signal',
      type: 'uncertain_model_signal',
      confidence: input.confidence,
      location: 'model_output',
      description:
        'The model confidence is not strong enough for a definitive artifact-level verdict.',
    });
  }

  return artifacts;
}

export function mapBackendAnalysis(
  backendAnalysis: BackendAnalysis,
  options: {
    file?: File;
    sourceUrl?: string;
    processingTime?: number;
  } = {}
): Analysis {
  const savedRecord = getSavedRecord(backendAnalysis);
  const mediaType = backendAnalysis.media_type ?? savedRecord?.media_type ?? 'image';
  const label = backendAnalysis.label ?? savedRecord?.label ?? 'Authentic';
  const confidence = boundedFiniteNumber(
    backendAnalysis.confidence ?? savedRecord?.confidence ?? 0,
    'predicted-class confidence'
  );
  const result = resultFromLabel(label);
  const mediaUrl = options.file
    ? URL.createObjectURL(options.file)
    : resolveBackendUrl(
        options.sourceUrl ||
          savedRecord?.local_url ||
          ('local_url' in backendAnalysis ? backendAnalysis.local_url : null) ||
          savedRecord?.firebase_url ||
          ('firebase_url' in backendAnalysis ? backendAnalysis.firebase_url : null)
      );
  const heatmapUrl = resolveBackendUrl(
    savedRecord?.heatmap_url ??
      ('heatmap_url' in backendAnalysis ? backendAnalysis.heatmap_url : null)
  );
  const xaiOverlayUrl = resolveBackendUrl(
    savedRecord?.xai_overlay_url ??
      ('xai_overlay_url' in backendAnalysis ? backendAnalysis.xai_overlay_url : null)
  );
  const xaiPanelUrl = resolveBackendUrl(
    savedRecord?.xai_panel_url ??
      ('xai_panel_url' in backendAnalysis ? backendAnalysis.xai_panel_url : null)
  );
  const xaiMethod =
    savedRecord?.xai_method ??
    ('xai_method' in backendAnalysis ? backendAnalysis.xai_method ?? undefined : undefined);
  const xaiTargetClass =
    savedRecord?.xai_target_class ??
    ('xai_target_class' in backendAnalysis
      ? backendAnalysis.xai_target_class ?? undefined
      : undefined);
  const xaiPredictedClass =
    savedRecord?.xai_predicted_class ??
    ('xai_predicted_class' in backendAnalysis
      ? backendAnalysis.xai_predicted_class ?? undefined
      : undefined);
  const xaiLayer =
    savedRecord?.xai_layer ??
    ('xai_layer' in backendAnalysis ? backendAnalysis.xai_layer ?? undefined : undefined);
  const xaiMapStrength =
    'xai_map_strength' in backendAnalysis &&
    typeof backendAnalysis.xai_map_strength === 'number'
      ? backendAnalysis.xai_map_strength
      : undefined;
  const xaiError =
    savedRecord?.xai_error ??
    ('xai_error' in backendAnalysis ? backendAnalysis.xai_error ?? undefined : undefined);
  const modelVersion = nullableModelVersion(
    backendAnalysis.model_version ?? savedRecord?.model_version
  );
  const directFakeProb = backendAnalysis.fake_probability;
  const directAuthenticProb = backendAnalysis.authentic_probability;
  const hasAnyDirectProbability =
    directFakeProb != null || directAuthenticProb != null;
  const backendFakeProb = hasAnyDirectProbability
    ? directFakeProb
    : savedRecord?.fake_probability;
  const backendAuthenticProb = hasAnyDirectProbability
    ? directAuthenticProb
    : savedRecord?.authentic_probability;
  const returnedFakeProb = optionalBoundedProbability(
    backendFakeProb,
    'fake probability'
  );
  const returnedAuthenticProb = optionalBoundedProbability(
    backendAuthenticProb,
    'authentic probability'
  );
  if (
    (returnedFakeProb === undefined) !==
    (returnedAuthenticProb === undefined)
  ) {
    throw new Error('The backend returned an incomplete class-probability pair.');
  }
  if (
    returnedFakeProb !== undefined &&
    returnedAuthenticProb !== undefined &&
    Math.abs(returnedFakeProb + returnedAuthenticProb - 100) > 0.1
  ) {
    throw new Error('The backend returned inconsistent class probabilities.');
  }
  const hasBackendProbabilityPair = returnedFakeProb !== undefined;
  const boundedFakeProb = hasBackendProbabilityPair
    ? returnedFakeProb
    : result === 'fake'
      ? confidence
      : 100 - confidence;
  const boundedRealProb = hasBackendProbabilityPair
    ? returnedAuthenticProb as number
    : result === 'real'
      ? confidence
      : 100 - confidence;

  // -- Pull model-provided explanation & frames_analyzed ---------------------
  const explanation: string | undefined =
    ('explanation' in backendAnalysis
      ? backendAnalysis.explanation ?? undefined
      : undefined) ??
    savedRecord?.explanation ??
    undefined;

  const framesAnalyzed: number | undefined =
    (('frames_analyzed' in backendAnalysis
      ? (backendAnalysis.frames_analyzed ?? undefined)
      : undefined) ??
    savedRecord?.frames_analyzed) ??
    undefined;
  const { forensicEvidence, videoMetadata, modelForensicAlignment } =
    selectAnalysisEvidence(backendAnalysis, savedRecord);
  const artifacts = buildArtifacts({
    mediaType,
    result,
    confidence,
    fakeProb: boundedFakeProb,
    realProb: boundedRealProb,
    heatmapUrl,
    hasVisualExplanation: Boolean(heatmapUrl || xaiOverlayUrl || xaiPanelUrl),
    xaiMethod,
    xaiTargetClass,
    xaiLayer,
    xaiError,
    framesAnalyzed,
  });

  return {
    id:
      savedRecord?.id ||
      ('id' in backendAnalysis && backendAnalysis.id) ||
      `analysis_${Date.now()}`,
    ownerId: savedRecord?.user_id || undefined,
    filename:
      options.file?.name ||
      savedRecord?.original_filename ||
      ('original_filename' in backendAnalysis
        ? backendAnalysis.original_filename || undefined
        : undefined) ||
      options.sourceUrl?.split('/').pop() ||
      'remote-image',
    fileSize: options.file?.size || forensicEvidence?.file_size_bytes || 0,
    fileType: mediaType,
    mediaUrl,
    thumbnailUrl: mediaType === 'image' ? mediaUrl || heatmapUrl : '',
    result,
    confidence,
    fakeProb: boundedFakeProb,
    realProb: boundedRealProb,
    processingTime: options.processingTime || 0,
    heatmapUrl: heatmapUrl || undefined,
    xaiOverlayUrl: xaiOverlayUrl || undefined,
    xaiPanelUrl: xaiPanelUrl || undefined,
    xaiMethod,
    xaiTargetClass,
    xaiPredictedClass,
    xaiLayer,
    xaiMapStrength,
    xaiError,
    modelVersion,
    artifacts,
    createdAt: savedRecord?.created_at || new Date().toISOString(),
    isPublic: Boolean(options.sourceUrl && !savedRecord),
    // -- Real model fields --------------------------------------------------
    explanation,
    framesAnalyzed,
    videoMetadata,
    forensicEvidence,
    modelForensicAlignment,
  };
}

export function mapBackendHistory(
  records: BackendAnalysisRecord[]
): Analysis[] {
  const analyses: Analysis[] = [];
  for (const record of records) {
    try {
      analyses.push(mapBackendAnalysis(record));
    } catch {
      continue;
    }
  }
  return analyses;
}

async function withAuthenticatedRequest<T>(
  request: (accessToken: string) => Promise<T>
): Promise<T> {
  const authState = useAuthStore.getState();
  const token = authState.accessToken || (await authState.refreshSession());

  if (!token) {
    throw new ApiError('Please sign in before analyzing media.', 401);
  }

  try {
    return await request(token);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      const refreshedToken = await useAuthStore.getState().refreshSession();

      if (refreshedToken) {
        return request(refreshedToken);
      }
    }

    throw error;
  }
}

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error) {
    return error.message;
  }

  return fallback;
}

export const useAnalysisStore = create<AnalysisState>()(
  persist(
    (set, get) => ({
      analyses: [],
      currentAnalysis: null,
      uploadProgress: 0,
      isAnalyzing: false,
      isHistoryLoading: false,
      analysisStatus: 'idle',
      error: null,

      startUpload: async (file, videoSegment) => {
        const fileType = getFileType(file);
        set({
          isAnalyzing: true,
          analysisStatus: 'uploading',
          uploadProgress: 10,
          error: null,
        });

        const startTime = performance.now();

        try {
          const backendResult = await withAuthenticatedRequest((token) => {
            set({ analysisStatus: 'uploading', uploadProgress: 50 });

            if (fileType === 'video') {
              return analyzeVideo(file, token, videoSegment);
            }

            if (fileType === 'audio') {
              return analyzeAudio(file, token);
            }

            return analyzeImage(file, token);
          });
          const analysis = mapBackendAnalysis(backendResult, {
            file,
            processingTime: (performance.now() - startTime) / 1000,
          });

          set((state) => ({
            analyses: [
              analysis,
              ...state.analyses.filter((item) => item.id !== analysis.id),
            ],
            currentAnalysis: analysis,
            isAnalyzing: false,
            analysisStatus: 'complete',
            uploadProgress: 100,
          }));
        } catch (error) {
          set({
            isAnalyzing: false,
            analysisStatus: 'error',
            uploadProgress: 0,
            error: getErrorMessage(error, 'Something went wrong during analysis.'),
          });
          throw error;
        }
      },

      analyzeUrl: async (url) => {
        set({
          isAnalyzing: true,
          analysisStatus: 'processing',
          uploadProgress: 0,
          error: null,
        });

        const startTime = performance.now();

        try {
          const backendResult = await analyzeImageUrl(url);
          const analysis = mapBackendAnalysis(backendResult, {
            sourceUrl: url,
            processingTime: (performance.now() - startTime) / 1000,
          });

          set((state) => ({
            analyses: [
              analysis,
              ...state.analyses.filter((item) => item.id !== analysis.id),
            ],
            currentAnalysis: analysis,
            isAnalyzing: false,
            analysisStatus: 'complete',
            uploadProgress: 100,
          }));
        } catch (error) {
          set({
            isAnalyzing: false,
            analysisStatus: 'error',
            uploadProgress: 0,
            error: getErrorMessage(error, 'Something went wrong during URL analysis.'),
          });
          throw error;
        }
      },

      fetchHistory: async () => {
        set({ isHistoryLoading: true, error: null });

        try {
          const response = await withAuthenticatedRequest((token) =>
            getAnalysisResults(token, 100)
          );
          const analyses = mapBackendHistory(response.results);

          set({
            analyses,
            isHistoryLoading: false,
          });
        } catch (error) {
          set({
            isHistoryLoading: false,
            error: getErrorMessage(error, 'Could not load analysis history.'),
          });
        }
      },

      setCurrentAnalysis: (analysis) => set({ currentAnalysis: analysis }),

      deleteAnalysis: async (id) => {
        const previousState = get();

        set((state) => ({
          analyses: state.analyses.filter((analysis) => analysis.id !== id),
          currentAnalysis:
            state.currentAnalysis?.id === id ? null : state.currentAnalysis,
        }));

        try {
          await withAuthenticatedRequest((token) => deleteAnalysisResult(token, id));
        } catch (error) {
          set({
            analyses: previousState.analyses,
            currentAnalysis: previousState.currentAnalysis,
            error: getErrorMessage(error, 'Could not delete that analysis.'),
          });
        }
      },

      clearHistory: () => set({ analyses: [], currentAnalysis: null }),

      setUploadProgress: (progress) => set({ uploadProgress: progress }),

      resetAnalysis: () =>
        set({
          currentAnalysis: null,
          uploadProgress: 0,
          isAnalyzing: false,
          analysisStatus: 'idle',
          error: null,
        }),
    }),
    {
      name: 'truth-matrix-analysis',
      partialize: (state) => ({
        analyses: state.analyses,
      }),
    }
  )
);

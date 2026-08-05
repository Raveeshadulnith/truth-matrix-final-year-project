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
  type VideoMetadata,
} from '../api/deepfakeApi';
import { useAuthStore } from './authStore';

export interface Analysis {
  id: string;
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
  artifacts: Artifact[];
  createdAt: string;
  isPublic: boolean;
  shareToken?: string;
  explanation?: string;
  framesAnalyzed?: number;
  videoMetadata?: VideoMetadata;
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

  startUpload: (file: File) => Promise<void>;
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

  if (file.type.startsWith('video/') || ['mp4', 'mov', 'avi', 'mkv'].includes(extension)) {
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

function buildArtifacts(input: {
  mediaType: 'image' | 'video' | 'audio';
  result: 'real' | 'fake' | 'uncertain';
  confidence: number;
  fakeProb: number;
  realProb: number;
  heatmapUrl: string;
  xaiMethod?: string;
  xaiTargetClass?: string;
  xaiLayer?: string;
  xaiError?: string;
  framesAnalyzed?: number | null;
}): Artifact[] {
  const artifacts: Artifact[] = [];
  const method = input.xaiMethod || 'Grad-CAM';
  const targetText = input.xaiTargetClass
    ? input.xaiTargetClass.replace(/_/g, ' ')
    : 'model';

  if (input.result === 'fake') {
    artifacts.push({
      id: 'model_manipulation_signal',
      type:
        input.mediaType === 'video'
          ? 'frame_manipulation_signal'
          : 'visual_manipulation_signal',
      confidence: input.fakeProb,
      location:
        input.mediaType === 'video'
          ? 'sampled_video_frames'
          : 'grad_cam_attention_regions',
      description:
        input.mediaType === 'video'
          ? `The Keras video model found manipulation signals after averaging sampled frame predictions with ${input.fakeProb.toFixed(1)}% deepfake probability.`
          : `The trained image model found manipulation signals in the Grad-CAM attention regions with ${input.fakeProb.toFixed(1)}% deepfake probability.`,
    });
  }

  if (input.mediaType === 'image' && input.heatmapUrl) {
    artifacts.push({
      id: 'xai_gradcam_heatmap',
      type: 'gradcam_heatmap',
      confidence:
        input.result === 'fake'
          ? input.fakeProb
          : input.result === 'real'
            ? input.realProb
            : input.confidence,
      location: 'image_attention_map',
      description: `${method} generated an image heatmap for the ${targetText} class using ${input.xaiLayer || 'the configured model layer'}.`,
    });
  }

  if (input.mediaType === 'image' && !input.heatmapUrl && input.xaiError) {
    artifacts.push({
      id: 'xai_generation_error',
      type: 'xai_generation_error',
      confidence: input.confidence,
      location: 'grad_cam_backend',
      description: `Grad-CAM could not produce a heatmap for this request: ${input.xaiError}`,
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

function mapBackendAnalysis(
  backendAnalysis: BackendAnalysis,
  options: {
    file?: File;
    sourceUrl?: string;
    processingTime?: number;
  } = {}
): Analysis {
  const savedRecord = getSavedRecord(backendAnalysis);
  const mediaType =
    savedRecord?.media_type ||
    ('media_type' in backendAnalysis ? backendAnalysis.media_type : 'image');
  const label =
    savedRecord?.label ||
    ('label' in backendAnalysis ? backendAnalysis.label : 'Authentic');
  const confidence = Number(
    savedRecord?.confidence ||
      ('confidence' in backendAnalysis ? backendAnalysis.confidence : 0)
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
    savedRecord?.heatmap_url ||
      ('heatmap_url' in backendAnalysis ? backendAnalysis.heatmap_url : null)
  );
  const xaiOverlayUrl = resolveBackendUrl(
    savedRecord?.xai_overlay_url ||
      ('xai_overlay_url' in backendAnalysis ? backendAnalysis.xai_overlay_url : null)
  );
  const xaiPanelUrl = resolveBackendUrl(
    savedRecord?.xai_panel_url ||
      ('xai_panel_url' in backendAnalysis ? backendAnalysis.xai_panel_url : null)
  );
  const xaiMethod =
    savedRecord?.xai_method ||
    ('xai_method' in backendAnalysis ? backendAnalysis.xai_method || undefined : undefined);
  const xaiTargetClass =
    savedRecord?.xai_target_class ||
    ('xai_target_class' in backendAnalysis
      ? backendAnalysis.xai_target_class || undefined
      : undefined);
  const xaiPredictedClass =
    savedRecord?.xai_predicted_class ||
    ('xai_predicted_class' in backendAnalysis
      ? backendAnalysis.xai_predicted_class || undefined
      : undefined);
  const xaiLayer =
    savedRecord?.xai_layer ||
    ('xai_layer' in backendAnalysis ? backendAnalysis.xai_layer || undefined : undefined);
  const xaiMapStrength =
    'xai_map_strength' in backendAnalysis &&
    typeof backendAnalysis.xai_map_strength === 'number'
      ? backendAnalysis.xai_map_strength
      : undefined;
  const xaiError =
    savedRecord?.xai_error ||
    ('xai_error' in backendAnalysis ? backendAnalysis.xai_error || undefined : undefined);
  const backendFakeProb =
    'fake_probability' in backendAnalysis
      ? backendAnalysis.fake_probability
      : undefined;
  const backendAuthenticProb =
    'authentic_probability' in backendAnalysis
      ? backendAnalysis.authentic_probability
      : undefined;
  const fakeProb =
    typeof backendFakeProb === 'number'
      ? backendFakeProb
      : result === 'fake'
        ? confidence
        : 100 - confidence;
  const realProb =
    typeof backendAuthenticProb === 'number'
      ? backendAuthenticProb
      : result === 'real'
        ? confidence
        : 100 - confidence;
  const boundedFakeProb = Math.max(0, Math.min(100, fakeProb));
  const boundedRealProb = Math.max(0, Math.min(100, realProb));

  // -- Pull model-provided explanation & frames_analyzed ---------------------
  const explanation: string | undefined =
    ('explanation' in backendAnalysis ? backendAnalysis.explanation : undefined) ||
    (savedRecord && 'explanation' in savedRecord ? (savedRecord as any).explanation : undefined) ||
    undefined;

  const framesAnalyzed: number | undefined =
    ('frames_analyzed' in backendAnalysis
      ? (backendAnalysis.frames_analyzed ?? undefined)
      : undefined) ||
    (savedRecord && 'frames_analyzed' in savedRecord
      ? ((savedRecord as any).frames_analyzed ?? undefined)
      : undefined);
  const videoMetadata =
    'video_metadata' in backendAnalysis
      ? backendAnalysis.video_metadata || undefined
      : undefined;
  const artifacts = buildArtifacts({
    mediaType,
    result,
    confidence,
    fakeProb: boundedFakeProb,
    realProb: boundedRealProb,
    heatmapUrl,
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
    filename:
      options.file?.name ||
      savedRecord?.original_filename ||
      ('original_filename' in backendAnalysis
        ? backendAnalysis.original_filename || undefined
        : undefined) ||
      options.sourceUrl?.split('/').pop() ||
      'remote-image',
    fileSize: options.file?.size || 0,
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
    artifacts,
    createdAt: savedRecord?.created_at || new Date().toISOString(),
    isPublic: false,
    // -- Real model fields --------------------------------------------------
    explanation,
    framesAnalyzed,
    videoMetadata,
  };
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

      startUpload: async (file) => {
        set({
          isAnalyzing: true,
          analysisStatus: 'uploading',
          uploadProgress: 10,
          error: null,
        });

        const fileType = getFileType(file);
        const startTime = performance.now();

        try {
          const backendResult = await withAuthenticatedRequest((token) => {
            set({ analysisStatus: 'processing', uploadProgress: 55 });

            if (fileType === 'video') {
              return analyzeVideo(file, token);
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
          const analyses = response.results.map((item) => mapBackendAnalysis(item));

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

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
  artifacts: Artifact[];
  createdAt: string;
  isPublic: boolean;
  shareToken?: string;
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
  const mediaUrl = resolveBackendUrl(
    options.sourceUrl ||
      savedRecord?.firebase_url ||
      ('firebase_url' in backendAnalysis ? backendAnalysis.firebase_url : null)
  );
  const heatmapUrl = resolveBackendUrl(
    savedRecord?.heatmap_url ||
      ('heatmap_url' in backendAnalysis ? backendAnalysis.heatmap_url : null)
  );
  const fakeProb = result === 'fake' ? confidence : 100 - confidence;
  const realProb = result === 'real' ? confidence : 100 - confidence;

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
    fakeProb: Math.max(0, Math.min(100, fakeProb)),
    realProb: Math.max(0, Math.min(100, realProb)),
    processingTime: options.processingTime || 0,
    heatmapUrl: heatmapUrl || undefined,
    artifacts: [],
    createdAt: savedRecord?.created_at || new Date().toISOString(),
    isPublic: false,
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

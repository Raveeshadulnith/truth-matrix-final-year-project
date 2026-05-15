export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
).replace(/\/$/, '');

export interface BackendProfile {
  id: string;
  email?: string;
  full_name?: string;
  avatar_url?: string | null;
  role?: 'user' | 'admin';
  created_at?: string | null;
  updated_at?: string | null;
}

export interface BackendUser {
  id?: string;
  email?: string;
  user_metadata?: {
    full_name?: string;
    avatar_url?: string;
  };
  profile?: BackendProfile;
}

export interface AuthResponse {
  access_token: string | null;
  refresh_token: string | null;
  user: BackendUser;
}

export interface BackendAnalysisRecord {
  id: string;
  user_id?: string;
  media_type: 'image' | 'video' | 'audio';
  original_filename?: string | null;
  firebase_url?: string | null;
  heatmap_url?: string | null;
  label: 'Authentic' | 'Suspected Deepfake';
  confidence: number;
  explanation?: string | null;
  frames_analyzed?: number | null;
  created_at?: string;
}

export interface BackendAnalysisResponse {
  id?: string | null;
  media_type: 'image' | 'video' | 'audio';
  label: 'Authentic' | 'Suspected Deepfake';
  confidence: number;
  explanation?: string;
  frames_analyzed?: number | null;
  firebase_url?: string | null;
  heatmap_url?: string | null;
  original_filename?: string | null;
  saved_record?: BackendAnalysisRecord | null;
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function readResponseBody(response: Response) {
  const contentType = response.headers.get('content-type') || '';

  if (contentType.includes('application/json')) {
    return response.json();
  }

  return response.text();
}

function getBackendErrorMessage(data: unknown, fallbackMessage: string) {
  const friendlyMessage = (message: string) => {
    if (message.toLowerCase().includes('email rate limit exceeded')) {
      return 'Supabase is temporarily rate-limiting signup emails. Please wait a few minutes and try again.';
    }

    return message;
  };

  if (!data) {
    return fallbackMessage;
  }

  if (typeof data === 'string') {
    return data ? friendlyMessage(data) : fallbackMessage;
  }

  if (typeof data === 'object' && data !== null) {
    const maybeError = data as {
      detail?: string | Array<{ msg?: string; message?: string }>;
      message?: string;
    };

    if (typeof maybeError.detail === 'string') {
      return friendlyMessage(maybeError.detail);
    }

    if (Array.isArray(maybeError.detail)) {
      return maybeError.detail
        .map((item) => item.msg || item.message)
        .filter(Boolean)
        .join(', ');
    }

    if (typeof maybeError.message === 'string') {
      return friendlyMessage(maybeError.message);
    }
  }

  return fallbackMessage;
}

async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {},
  fallbackMessage = 'Request failed. Please try again.'
): Promise<T> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}${endpoint}`, options);
  } catch {
    throw new ApiError(
      `Could not connect to the Truth Matrix backend at ${API_BASE_URL}.`,
      0
    );
  }

  const data = await readResponseBody(response);

  if (!response.ok) {
    throw new ApiError(getBackendErrorMessage(data, fallbackMessage), response.status);
  }

  return data as T;
}

function authHeaders(accessToken?: string | null): HeadersInit {
  return accessToken ? { Authorization: `Bearer ${accessToken}` } : {};
}

export function loginUser(email: string, password: string) {
  return apiRequest<AuthResponse>(
    '/api/auth/login',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    },
    'Invalid email or password.'
  );
}

export function registerUser(fullName: string, email: string, password: string) {
  return apiRequest<AuthResponse>(
    '/api/auth/signup',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ full_name: fullName, email, password }),
    },
    'Could not create your account.'
  );
}

export function refreshUserSession(refreshToken: string) {
  return apiRequest<AuthResponse>(
    '/api/auth/refresh',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    },
    'Your session has expired. Please sign in again.'
  );
}

export function requestPasswordReset(email: string) {
  return apiRequest<{ message: string }>(
    '/api/auth/reset-password',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    },
    'Could not send a password reset email.'
  );
}

export function getCurrentProfile(accessToken: string) {
  return apiRequest<BackendProfile>(
    '/api/auth/me',
    {
      headers: authHeaders(accessToken),
    },
    'Could not load your profile.'
  );
}

export function updateCurrentProfile(
  accessToken: string,
  data: { full_name?: string; avatar_url?: string | null }
) {
  return apiRequest<BackendProfile>(
    '/api/auth/profile',
    {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders(accessToken),
      },
      body: JSON.stringify(data),
    },
    'Could not update your profile.'
  );
}

async function uploadForAnalysis(
  endpoint: string,
  file: File,
  accessToken: string
) {
  if (!file) {
    throw new Error('Please select a file before analyzing.');
  }

  const formData = new FormData();
  formData.append('file', file);

  return apiRequest<BackendAnalysisResponse>(
    endpoint,
    {
      method: 'POST',
      headers: authHeaders(accessToken),
      body: formData,
    },
    'Analysis failed. Please try again.'
  );
}

export function analyzeImage(file: File, accessToken: string) {
  return uploadForAnalysis('/api/analyze/image', file, accessToken);
}

export function analyzeVideo(file: File, accessToken: string) {
  return uploadForAnalysis('/api/analyze/video', file, accessToken);
}

export function analyzeAudio(file: File, accessToken: string) {
  return uploadForAnalysis('/api/analyze/audio', file, accessToken);
}

export function analyzeImageUrl(imageUrl: string) {
  return apiRequest<BackendAnalysisResponse>(
    '/api/analyze/image-url',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image_url: imageUrl }),
    },
    'URL analysis failed. Please try again.'
  );
}

export function getAnalysisResults(accessToken: string, limit = 50) {
  return apiRequest<{ results: BackendAnalysisRecord[] }>(
    `/api/results?limit=${limit}`,
    {
      headers: authHeaders(accessToken),
    },
    'Could not load analysis history.'
  );
}

export function deleteAnalysisResult(accessToken: string, resultId: string) {
  return apiRequest<{ message: string; deleted: BackendAnalysisRecord }>(
    `/api/results/${resultId}`,
    {
      method: 'DELETE',
      headers: authHeaders(accessToken),
    },
    'Could not delete that analysis.'
  );
}

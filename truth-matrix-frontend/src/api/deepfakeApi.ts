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

export interface VideoMetadata {
  duration_seconds?: number | null;
  fps?: number | null;
  width?: number | null;
  height?: number | null;
  total_frames?: number | null;
  analyzed_segment?: {
    start_seconds: number;
    end_seconds?: number | null;
    duration_seconds?: number | null;
    selection_applied: boolean;
  };
}

export interface VideoSegmentSelection {
  startSeconds: number;
  durationSeconds: number;
  sourceDurationSeconds?: number;
}

export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };
export type JsonObject = { [key: string]: JsonValue };

export type OverallForensicStatus =
  | 'complete'
  | 'partial'
  | 'unavailable'
  | 'error';

export type ExtractorStatus =
  | 'available'
  | 'not_present'
  | 'unsupported'
  | 'unavailable'
  | 'error';

export type ForensicFindingSeverity = 'info' | 'low' | 'medium' | 'high';

export type C2paSignatureState =
  | 'valid'
  | 'invalid'
  | 'not_applicable'
  | 'unknown';

export type C2paTrustState =
  | 'trusted'
  | 'untrusted'
  | 'not_checked'
  | 'not_applicable'
  | 'unknown';

export type C2paValidationState =
  | 'valid'
  | 'invalid'
  | 'not_applicable'
  | 'unknown';

export type C2paValidationCategory =
  | 'success'
  | 'informational'
  | 'failure';

export type C2paOriginState =
  | 'verified_ai_generated'
  | 'declared_ai_generated_untrusted'
  | 'verified_ai_edited'
  | 'declared_ai_edited_untrusted'
  | 'verified_camera_capture'
  | 'verified_screen_capture'
  | 'verified_human_edited'
  | 'verified_digital_creation'
  | 'verified_mixed_or_synthetic'
  | 'no_origin_declaration'
  | 'invalid_credential'
  | 'verification_unavailable'
  | 'unknown';

export type C2paOriginCategory =
  | 'ai_generated'
  | 'ai_edited'
  | 'camera_capture'
  | 'screen_capture'
  | 'human_edited'
  | 'digital_creation'
  | 'mixed_or_synthetic'
  | 'unknown';

export type C2paBasisStrength =
  | 'valid_trusted'
  | 'valid_untrusted'
  | 'invalid'
  | 'unavailable'
  | 'none';

export type SimilarityMatchType = 'exact' | 'near';

export type ForensicAssessmentState =
  | 'no_material_concerns'
  | 'review_signals_present'
  | 'strong_conflicts_present'
  | 'insufficient_evidence'
  | 'collection_failed';

export type ForensicConcernBand = 'low' | 'moderate' | 'high';

export type ForensicInsightCategory =
  | 'integrity'
  | 'origin'
  | 'timeline'
  | 'workflow'
  | 'provenance'
  | 'encoding'
  | 'similarity'
  | 'availability';

export type ForensicInsightTone =
  | 'positive'
  | 'neutral'
  | 'caution'
  | 'warning';

export type ForensicEvidenceStrength = 'limited' | 'moderate' | 'strong';

export type ModelForensicAlignmentState =
  | 'supports_model_result'
  | 'no_material_effect'
  | 'conflicts_with_model_result'
  | 'insufficient_for_comparison';

export interface MetadataEvidence {
  status: ExtractorStatus;
  source?: string | null;
  source_version?: string | null;
  normalized: JsonObject;
  raw: JsonObject;
  warnings: string[];
}

export type SoftwareCategory =
  | 'capture_processing'
  | 'editor'
  | 'encoder'
  | 'ai_generation'
  | 'social_platform'
  | 'metadata_tool'
  | 'unknown';

export interface SoftwareObservation {
  name: string;
  category: SoftwareCategory;
  source_tags: string[];
  user_description: string;
}

export interface CreationInfo {
  software: string[];
  software_observations?: SoftwareObservation[];
  device_make?: string | null;
  device_model?: string | null;
  creator?: string | null;
  created_at?: string | null;
  modified_at?: string | null;
  digitized_at?: string | null;
  timezone_present: boolean;
  location_present: boolean;
  source_tags: Record<string, string[]>;
}

export type PreciseLocationStatus =
  | 'available'
  | 'not_present'
  | 'invalid'
  | 'unavailable'
  | 'forbidden';

export interface PreciseLocationResponse {
  status: PreciseLocationStatus;
  latitude?: number | null;
  longitude?: number | null;
  altitude_meters?: number | null;
  source?: string | null;
  accuracy_meters?: number | null;
}

export interface ForensicFinding {
  code: string;
  title: string;
  explanation: string;
  evidence: JsonObject;
  severity: ForensicFindingSeverity;
  method?: string | null;
  method_version?: string | null;
  limitations: string[];
}

export interface C2paAction {
  action: string;
  digital_source_type?: string | null;
  software_agent?: string | null;
  description?: string | null;
  parameters: JsonObject;
}

export interface C2paProvenanceConclusion {
  origin_state: C2paOriginState;
  origin_category: C2paOriginCategory;
  basis_strength: C2paBasisStrength;
  provider?: string | null;
  claim_generator?: string | null;
  signer?: string | null;
  source_action?: string | null;
  digital_source_type?: string | null;
  headline: string;
  user_message: string;
  technical_references: string[];
  limitations: string[];
  classification_method: string;
  classification_version: string;
}

export interface C2paValidationStatus {
  code: string;
  summary: string;
  category: C2paValidationCategory;
}

export interface C2paEvidence {
  status: ExtractorStatus;
  manifest_present: boolean;
  active_manifest?: string | null;
  validation_state?: C2paValidationState;
  signature_state: C2paSignatureState;
  trust_state: C2paTrustState;
  signer?: string | null;
  issuer?: string | null;
  claim_generator?: string | null;
  claim_generator_version?: string | null;
  assertion_labels?: string[];
  actions: C2paAction[];
  ingredient_count?: number;
  validation_statuses?: C2paValidationStatus[];
  validation_errors: string[];
  provenance?: C2paProvenanceConclusion | null;
  remote_references_present?: boolean;
  remote_fetch_performed?: false;
  raw_manifest?: JsonObject | null;
  warnings: string[];
}

export interface FingerprintComponent {
  value: string;
  index: number;
  timestamp_seconds?: number | null;
}

export interface PerceptualFingerprint {
  status: ExtractorStatus;
  algorithm?: string | null;
  algorithm_version?: string | null;
  value?: string | null;
  hash_size?: number | null;
  components: FingerprintComponent[];
  duration_seconds?: number | null;
  warnings: string[];
}

export interface SimilarityMatch {
  analysis_id: string;
  filename: string;
  created_at: string;
  match_type: SimilarityMatchType;
  similarity_score: number;
  distance?: number | null;
  details: JsonObject;
  algorithm: string;
  algorithm_version?: string | null;
}

export interface ForensicInsight {
  code: string;
  category: ForensicInsightCategory;
  tone: ForensicInsightTone;
  title: string;
  user_message: string;
  technical_references: string[];
}

export interface ForensicScoreContribution {
  finding_code: string;
  points: number;
  reason: string;
  evidence_strength: ForensicEvidenceStrength;
  limitations: string[];
}

export interface ModelForensicAlignment {
  alignment_state: ModelForensicAlignmentState;
  headline: string;
  summary: string;
  model_label: 'Authentic' | 'Suspected Deepfake';
  forensic_assessment_state: ForensicAssessmentState;
  limitations: string[];
  alignment_method: string;
  alignment_version: string;
}

export interface ForensicAssessment {
  assessment_state: ForensicAssessmentState;
  review_concern_score: number;
  concern_band: ForensicConcernBand;
  evidence_coverage_score: number;
  headline: string;
  summary: string;
  key_insights: ForensicInsight[];
  score_contributions: ForensicScoreContribution[];
  limitations: string[];
  scoring_method: string;
  scoring_version: string;
  model_alignment?: ModelForensicAlignment | null;
}

export interface ForensicEvidence {
  schema_version: '1.0' | '1.1' | '1.2';
  status: OverallForensicStatus;
  file_identity_status: ExtractorStatus;
  sha256?: string | null;
  file_size_bytes?: number | null;
  detected_mime_type?: string | null;
  metadata: MetadataEvidence;
  creation_info: CreationInfo;
  metadata_inconsistency_status: ExtractorStatus;
  metadata_inconsistencies: ForensicFinding[];
  compression_status: ExtractorStatus;
  compression_indicators: ForensicFinding[];
  c2pa: C2paEvidence;
  perceptual_fingerprint: PerceptualFingerprint;
  similarity_status: ExtractorStatus;
  similarity_matches: SimilarityMatch[];
  assessment?: ForensicAssessment | null;
  warnings: string[];
  processing_time_ms: number;
}

export interface AuthResponse {
  access_token: string | null;
  refresh_token: string | null;
  user: BackendUser;
}

export interface BackendModelResultFields {
  label: 'Authentic' | 'Suspected Deepfake';
  confidence: number;
  fake_probability: number | null;
  authentic_probability: number | null;
  model_version: string | null;
}

export interface BackendAnalysisRecord extends BackendModelResultFields {
  id: string;
  user_id?: string;
  media_type: 'image' | 'video' | 'audio';
  original_filename?: string | null;
  local_url?: string | null;
  firebase_url?: string | null;
  heatmap_url?: string | null;
  xai_overlay_url?: string | null;
  xai_panel_url?: string | null;
  explanation?: string | null;
  frames_analyzed?: number | null;
  created_at?: string;
  xai_method?: string | null;
  xai_target_class?: string | null;
  xai_predicted_class?: string | null;
  xai_layer?: string | null;
  xai_map_strength?: number | null;
  xai_error?: string | null;
  sha256?: string | null;
  perceptual_fingerprint?: string | null;
  fingerprint_algorithm?: string | null;
  forensic_schema_version?: string | null;
  forensic_evidence?: ForensicEvidence | null;
  model_forensic_alignment?: ModelForensicAlignment | null;
}

export interface BackendAnalysisResponse extends BackendModelResultFields {
  id?: string | null;
  media_type: 'image' | 'video' | 'audio';
  explanation?: string;
  frames_analyzed?: number | null;
  video_metadata?: VideoMetadata | null;
  local_url?: string | null;
  firebase_url?: string | null;
  heatmap_url: string | null;
  xai_overlay_url: string | null;
  xai_panel_url: string | null;
  xai_method: string | null;
  xai_target_class: string | null;
  xai_predicted_class: string | null;
  xai_layer: string | null;
  xai_map_strength: number | null;
  xai_error: string | null;
  original_filename?: string | null;
  forensic_evidence?: ForensicEvidence | null;
  model_forensic_alignment?: ModelForensicAlignment | null;
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
  accessToken: string,
  fields?: Record<string, string>
) {
  if (!file) {
    throw new Error('Please select a file before analyzing.');
  }

  const formData = new FormData();
  formData.append('file', file);
  Object.entries(fields || {}).forEach(([key, value]) => formData.append(key, value));

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

export function analyzeVideo(
  file: File,
  accessToken: string
) {
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

export function getPreciseLocation(accessToken: string, analysisId: string) {
  return apiRequest<PreciseLocationResponse>(
    `/api/analyses/${encodeURIComponent(analysisId)}/precise-location`,
    {
      headers: authHeaders(accessToken),
      cache: 'no-store',
    },
    'Could not reveal the embedded location.'
  );
}

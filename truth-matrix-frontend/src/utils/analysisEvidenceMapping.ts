import type {
  BackendAnalysisRecord,
  BackendAnalysisResponse,
  ForensicEvidence,
  ModelForensicAlignment,
  VideoMetadata,
} from '../api/deepfakeApi';

type BackendAnalysis = BackendAnalysisRecord | BackendAnalysisResponse;

export function selectAnalysisEvidence(
  backend: BackendAnalysis,
  savedRecord?: BackendAnalysisRecord
): {
  forensicEvidence?: ForensicEvidence;
  videoMetadata?: VideoMetadata;
  modelForensicAlignment?: ModelForensicAlignment;
} {
  const directEvidence =
    'forensic_evidence' in backend ? backend.forensic_evidence ?? undefined : undefined;
  const forensicEvidence = savedRecord?.forensic_evidence ?? directEvidence;
  const directVideoMetadata =
    'video_metadata' in backend ? backend.video_metadata ?? undefined : undefined;
  const videoMetadata = directVideoMetadata ?? savedRecord?.video_metadata ?? undefined;
  const directAlignment =
    'model_forensic_alignment' in backend
      ? backend.model_forensic_alignment ?? undefined
      : undefined;
  const modelForensicAlignment =
    savedRecord?.model_forensic_alignment ??
    directAlignment ??
    forensicEvidence?.assessment?.model_alignment ??
    undefined;
  return { forensicEvidence, videoMetadata, modelForensicAlignment };
}

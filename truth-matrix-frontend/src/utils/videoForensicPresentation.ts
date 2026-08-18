import type {
  CreationInfo,
  ForensicEvidence,
  MetadataEvidence,
} from '../api/deepfakeApi';

export interface EvidenceStatusItem {
  label: string;
  status: string;
}

export interface VideoMetadataFact {
  label: string;
  value: string;
}

function objectValue(value: unknown, key: string): unknown {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)[key]
    : undefined;
}

function readableNumber(value: unknown, suffix = ''): string | null {
  return typeof value === 'number' && Number.isFinite(value)
    ? `${value.toLocaleString()}${suffix}`
    : null;
}

export function videoMetadataFacts(metadata: MetadataEvidence): VideoMetadataFact[] {
  const file = objectValue(metadata.normalized, 'file');
  const video = objectValue(metadata.normalized, 'video');
  const width = objectValue(video, 'width');
  const height = objectValue(video, 'height');
  const dimensions =
    typeof width === 'number' && typeof height === 'number'
      ? `${width} × ${height}`
      : null;
  const values: Array<[string, unknown]> = [
    ['Container', objectValue(file, 'format_long_name') ?? objectValue(file, 'format')],
    ['Video codec', objectValue(video, 'codec')],
    ['Codec profile', objectValue(video, 'profile')],
    ['Pixel format', objectValue(video, 'pixel_format')],
    ['Dimensions', dimensions],
    ['Duration', readableNumber(objectValue(video, 'duration_seconds'), ' seconds')],
    ['Frame rate', readableNumber(objectValue(video, 'frame_rate'), ' fps')],
    ['Bit rate', readableNumber(objectValue(video, 'bit_rate'), ' bit/s')],
    ['Stream count', readableNumber(objectValue(video, 'stream_count'))],
  ];
  return values
    .filter((entry): entry is [string, string | number] =>
      typeof entry[1] === 'string' || typeof entry[1] === 'number'
    )
    .map(([label, value]) => ({ label, value: String(value) }));
}

export function hasOriginDetails(creation: CreationInfo): boolean {
  return Boolean(
    creation.device_make ||
      creation.device_model ||
      creation.creator ||
      creation.created_at ||
      creation.modified_at ||
      creation.digitized_at ||
      creation.location_present ||
      creation.software.length > 0 ||
      (creation.software_observations?.length ?? 0) > 0
  );
}

export function metadataStatusMessage(metadata: MetadataEvidence): string | null {
  if (metadata.status === 'available') return null;
  const reason = metadata.warnings.find((warning) => warning.trim().length > 0);
  const label = metadata.status.replace(/_/g, ' ');
  return reason
    ? `Metadata extraction is ${label}: ${reason}`
    : `Metadata extraction is ${label} for this file.`;
}

export function evidenceStatusItems(evidence: ForensicEvidence): EvidenceStatusItem[] {
  return [
    { label: 'Overall collection', status: evidence.status },
    { label: 'File identity', status: evidence.file_identity_status },
    { label: 'Metadata', status: evidence.metadata.status },
    { label: 'Metadata consistency', status: evidence.metadata_inconsistency_status },
    { label: 'Encoding/compression', status: evidence.compression_status },
    { label: 'Content Credentials', status: evidence.c2pa.status },
    { label: 'Perceptual fingerprint', status: evidence.perceptual_fingerprint.status },
    { label: 'History similarity', status: evidence.similarity_status },
  ];
}

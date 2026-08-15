import type {
  C2paEvidence,
  ForensicEvidence,
  ForensicFinding,
  JsonObject,
  MetadataEvidence,
  SimilarityMatch,
} from '../api/deepfakeApi';
import type { Analysis } from '../store/analysisStore';
import { redactSensitiveJson } from './forensicEvidence';

export const FORENSIC_REPORT_SCHEMA_VERSION = '1.2' as const;
const MAX_EXPORTED_JSON_BYTES = 512 * 1024;

export type ExportMetadataEvidence = Omit<MetadataEvidence, 'raw'>;
export type ExportC2paEvidence = Omit<C2paEvidence, 'raw_manifest'>;
export type ExportForensicEvidence = Omit<ForensicEvidence, 'metadata' | 'c2pa'> & {
  metadata: ExportMetadataEvidence;
  c2pa: ExportC2paEvidence;
};

export interface ForensicEvidenceReport {
  report_schema_version: typeof FORENSIC_REPORT_SCHEMA_VERSION;
  generated_at: string;
  analysis: {
    id: string;
    filename: string;
    media_type: Analysis['fileType'];
    model_version: string | null;
  };
  model_result: {
    verdict: 'Authentic' | 'Suspected Deepfake' | 'Uncertain';
    predicted_class_confidence: number;
    fake_probability: number;
    authentic_probability: number;
    model_version: string | null;
    explanation: string | null;
    limitations: string[];
  };
  forensic_evidence: ExportForensicEvidence;
}

export function modelResultLimitations(
  mediaType: Analysis['fileType']
): string[] {
  if (mediaType === 'audio') {
    return [
      'This is a file-level classifier signal, not proof of origin, speaker identity, or a voice-cloning method.',
      'The classifier does not return a visual explanation, waveform highlight, or temporal localization.',
    ];
  }
  if (mediaType === 'video') {
    return [
      'This result summarizes sampled video-frame classifications and does not prove a particular manipulation method.',
    ];
  }
  return [
    'This image classification does not prove a particular editing or generation method.',
  ];
}

function sanitizeObject(value: JsonObject): JsonObject {
  return redactSensitiveJson(value) as JsonObject;
}

function sanitizeFinding(finding: ForensicFinding): ForensicFinding {
  return { ...finding, evidence: sanitizeObject(finding.evidence) };
}

function sanitizeMatch(match: SimilarityMatch): SimilarityMatch {
  return { ...match, details: sanitizeObject(match.details) };
}

export function evidenceForDefaultExport(
  evidence: ForensicEvidence
): ExportForensicEvidence {
  const metadata: ExportMetadataEvidence = {
    status: evidence.metadata.status,
    source: evidence.metadata.source,
    source_version: evidence.metadata.source_version,
    normalized: sanitizeObject(evidence.metadata.normalized),
    warnings: [...evidence.metadata.warnings],
  };
  const c2pa: ExportC2paEvidence = {
    status: evidence.c2pa.status,
    manifest_present: evidence.c2pa.manifest_present,
    active_manifest: evidence.c2pa.active_manifest,
    validation_state: evidence.c2pa.validation_state,
    signature_state: evidence.c2pa.signature_state,
    trust_state: evidence.c2pa.trust_state,
    signer: evidence.c2pa.signer,
    issuer: evidence.c2pa.issuer,
    claim_generator: evidence.c2pa.claim_generator,
    claim_generator_version: evidence.c2pa.claim_generator_version,
    assertion_labels: evidence.c2pa.assertion_labels
      ? [...evidence.c2pa.assertion_labels]
      : undefined,
    actions: evidence.c2pa.actions.map((action) => ({
      ...action,
      parameters: sanitizeObject(action.parameters),
    })),
    ingredient_count: evidence.c2pa.ingredient_count,
    validation_statuses: evidence.c2pa.validation_statuses
      ? [...evidence.c2pa.validation_statuses]
      : undefined,
    validation_errors: [...evidence.c2pa.validation_errors],
    provenance: evidence.c2pa.provenance
      ? {
          ...evidence.c2pa.provenance,
          technical_references: [...evidence.c2pa.provenance.technical_references],
          limitations: [...evidence.c2pa.provenance.limitations],
        }
      : evidence.c2pa.provenance,
    remote_references_present: evidence.c2pa.remote_references_present,
    remote_fetch_performed: evidence.c2pa.remote_fetch_performed,
    warnings: [...evidence.c2pa.warnings],
  };

  return {
    ...evidence,
    metadata,
    c2pa,
    metadata_inconsistencies: evidence.metadata_inconsistencies.map(sanitizeFinding),
    compression_indicators: evidence.compression_indicators.map(sanitizeFinding),
    similarity_matches: evidence.similarity_matches.map(sanitizeMatch),
  };
}

export function buildForensicEvidenceReport(
  analysis: Analysis,
  generatedAt: Date = new Date()
): ForensicEvidenceReport {
  if (!analysis.forensicEvidence) {
    throw new Error('Forensic evidence is unavailable for this analysis.');
  }
  const analysisIdentity: ForensicEvidenceReport['analysis'] = {
    id: analysis.id,
    filename: analysis.filename,
    media_type: analysis.fileType,
    model_version: analysis.modelVersion ?? null,
  };

  const report: ForensicEvidenceReport = {
    report_schema_version: FORENSIC_REPORT_SCHEMA_VERSION,
    generated_at: generatedAt.toISOString(),
    analysis: analysisIdentity,
    model_result: {
      verdict:
        analysis.result === 'real'
          ? 'Authentic'
          : analysis.result === 'fake'
            ? 'Suspected Deepfake'
            : 'Uncertain',
      predicted_class_confidence: analysis.confidence,
      fake_probability: analysis.fakeProb,
      authentic_probability: analysis.realProb,
      model_version: analysis.modelVersion ?? null,
      explanation: analysis.explanation ?? null,
      limitations: modelResultLimitations(analysis.fileType),
    },
    forensic_evidence: evidenceForDefaultExport(analysis.forensicEvidence),
  };
  const byteLength = new TextEncoder().encode(JSON.stringify(report)).length;
  if (byteLength > MAX_EXPORTED_JSON_BYTES) {
    throw new Error('Forensic evidence exceeds the privacy-safe export size limit.');
  }
  return report;
}

function sortSerializable(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortSerializable);
  if (typeof value === 'object' && value !== null) {
    const record = value as Record<string, unknown>;
    return Object.fromEntries(
      Object.keys(record)
        .filter((key) => record[key] !== undefined)
        .sort((left, right) => left.localeCompare(right))
        .map((key) => [key, sortSerializable(record[key])])
    );
  }
  return value;
}

export function serializeForensicEvidenceReport(
  report: ForensicEvidenceReport
): string {
  return `${JSON.stringify(sortSerializable(report), null, 2)}\n`;
}

export function sanitizeReportFilename(filename: string): string {
  const stem = filename.replace(/\.[^.]+$/, '').trim() || 'analysis';
  return stem
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/gi, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60)
    .toLowerCase() || 'analysis';
}

export function downloadForensicEvidenceJson(analysis: Analysis): void {
  const report = buildForensicEvidenceReport(analysis);
  const blob = new Blob([serializeForensicEvidenceReport(report)], {
    type: 'application/json;charset=utf-8',
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  try {
    link.href = url;
    link.download = `truth-matrix-forensic-${sanitizeReportFilename(analysis.filename)}.json`;
    link.click();
  } finally {
    URL.revokeObjectURL(url);
  }
}

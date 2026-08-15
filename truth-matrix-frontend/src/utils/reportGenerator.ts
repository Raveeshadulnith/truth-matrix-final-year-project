import { jsPDF } from 'jspdf';
import type { ForensicFinding, JsonValue } from '../api/deepfakeApi';
import type { Analysis, Artifact } from '../store/analysisStore';
import { formatDate, formatFileSize, formatProcessingTime } from './formatters';
import { evidenceForDefaultExport, modelResultLimitations } from './forensicExport';
import { humanizeForensicLabel } from './forensicEvidence';

type Rgb = [number, number, number];

const PAGE_WIDTH = 210;
const MARGIN = 18;
const CONTENT_WIDTH = PAGE_WIDTH - MARGIN * 2;
const PAGE_BOTTOM = 276;

const INK: Rgb = [17, 24, 39];
const MUTED: Rgb = [100, 116, 139];
const LINE: Rgb = [226, 232, 240];
const SOFT: Rgb = [248, 250, 252];
const BRAND: Rgb = [8, 145, 178];
const DANGER: Rgb = [220, 38, 38];
const SUCCESS: Rgb = [5, 150, 105];
const WARNING: Rgb = [217, 119, 6];
const MAX_PDF_VALUE_CHARS = 8000;
const MAX_PDF_METADATA_FIELDS = 24;

function setText(
  doc: jsPDF,
  color: Rgb = INK,
  size = 10,
  weight: 'normal' | 'bold' = 'normal',
) {
  doc.setTextColor(...color);
  doc.setFont('helvetica', weight);
  doc.setFontSize(size);
}

function toneForResult(result: Analysis['result']): Rgb {
  if (result === 'fake') return DANGER;
  if (result === 'real') return SUCCESS;
  return WARNING;
}

function verdictLabel(result: Analysis['result']) {
  if (result === 'fake') return 'Suspected Deepfake';
  if (result === 'real') return 'Authentic';
  return 'Uncertain';
}

function slugifyFilename(filename: string) {
  return (filename.replace(/\.[^.]+$/, '').trim() || 'analysis')
    .replace(/[^a-z0-9]+/gi, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60)
    .toLowerCase();
}

function addFooter(doc: jsPDF, pageNumber: number) {
  doc.setDrawColor(...LINE);
  doc.line(MARGIN, 282, PAGE_WIDTH - MARGIN, 282);
  setText(doc, MUTED, 8);
  doc.text('Truth Matrix Report', MARGIN, 287);
  doc.text(`Page ${pageNumber}`, PAGE_WIDTH - MARGIN, 287, { align: 'right' });
}

function ensureSpace(doc: jsPDF, y: number, requiredHeight: number) {
  if (y + requiredHeight <= PAGE_BOTTOM) return y;
  doc.addPage();
  return MARGIN;
}

function textHeight(doc: jsPDF, text: string, width: number, lineHeight = 5) {
  return doc.splitTextToSize(text || 'Not available', width).length * lineHeight;
}

function addWrappedText(
  doc: jsPDF,
  text: string,
  x: number,
  y: number,
  width: number,
  lineHeight = 5,
) {
  const lines = doc.splitTextToSize(text || 'Not available', width) as string[];
  let cursor = y;
  lines.forEach((line) => {
    if (cursor + lineHeight > PAGE_BOTTOM) {
      doc.addPage();
      cursor = MARGIN;
    }
    doc.text(line, x, cursor);
    cursor += lineHeight;
  });
  return cursor;
}

function addSection(doc: jsPDF, title: string, y: number) {
  y = ensureSpace(doc, y, 15);
  setText(doc, INK, 12, 'bold');
  doc.text(title, MARGIN, y);
  doc.setDrawColor(...LINE);
  doc.line(MARGIN, y + 3, PAGE_WIDTH - MARGIN, y + 3);
  return y + 11;
}

function addField(doc: jsPDF, label: string, value: string, x: number, y: number, width: number) {
  setText(doc, MUTED, 7.5, 'bold');
  doc.text(label.toUpperCase(), x, y);
  setText(doc, INK, 9.5);
  return addWrappedText(doc, value || 'Not available', x, y + 5, width, 4.7);
}

function addTwoColumnRows(doc: jsPDF, rows: Array<[string, string, string, string]>, y: number) {
  const columnGap = 10;
  const columnWidth = (CONTENT_WIDTH - columnGap) / 2;

  rows.forEach(([leftLabel, leftValue, rightLabel, rightValue]) => {
    const leftHeight = 8 + textHeight(doc, leftValue, columnWidth, 4.7);
    const rightHeight = 8 + textHeight(doc, rightValue, columnWidth, 4.7);
    y = ensureSpace(doc, y, Math.max(leftHeight, rightHeight));
    const nextLeftY = addField(doc, leftLabel, leftValue, MARGIN, y, columnWidth);
    const nextRightY = addField(
      doc,
      rightLabel,
      rightValue,
      MARGIN + columnWidth + columnGap,
      y,
      columnWidth,
    );
    y = Math.max(nextLeftY, nextRightY) + 5;
  });

  return y;
}

function addBar(doc: jsPDF, label: string, value: number, y: number, color: Rgb) {
  y = ensureSpace(doc, y, 16);
  const bounded = Math.max(0, Math.min(100, value));
  setText(doc, INK, 9.5, 'bold');
  doc.text(label, MARGIN, y);
  doc.text(`${bounded.toFixed(1)}%`, PAGE_WIDTH - MARGIN, y, { align: 'right' });
  doc.setFillColor(241, 245, 249);
  doc.roundedRect(MARGIN, y + 4, CONTENT_WIDTH, 4, 2, 2, 'F');
  doc.setFillColor(...color);
  doc.roundedRect(MARGIN, y + 4, CONTENT_WIDTH * (bounded / 100), 4, 2, 2, 'F');
  return y + 14;
}

function addHeader(doc: jsPDF, analysis: Analysis) {
  setText(doc, BRAND, 11, 'bold');
  doc.text('TRUTH MATRIX', MARGIN, 20);
  setText(doc, INK, 20, 'bold');
  doc.text('Analysis Report', MARGIN, 31);
  setText(doc, MUTED, 9);
  doc.text(`Generated ${formatDate(new Date().toISOString())}`, MARGIN, 39);

  const tone = toneForResult(analysis.result);
  doc.setDrawColor(...tone);
  doc.setFillColor(...SOFT);
  doc.roundedRect(127, 18, 65, 23, 2, 2, 'FD');
  setText(doc, tone, 12, 'bold');
  doc.text(verdictLabel(analysis.result), 159.5, 28, { align: 'center' });
  setText(doc, MUTED, 8, 'bold');
  doc.text(`${analysis.confidence.toFixed(1)}% CONFIDENCE`, 159.5, 35, { align: 'center' });

  doc.setDrawColor(...LINE);
  doc.line(MARGIN, 49, PAGE_WIDTH - MARGIN, 49);
}

async function readImage(url?: string) {
  if (!url) return null;

  const response = await fetch(url, { mode: 'cors' });
  if (!response.ok) throw new Error(`Could not fetch image: ${response.status}`);
  const blob = await response.blob();
  if (!blob.type.startsWith('image/')) return null;

  const objectUrl = URL.createObjectURL(blob);
  try {
    const image = await new Promise<HTMLImageElement>((resolve, reject) => {
      const element = new Image();
      element.onload = () => resolve(element);
      element.onerror = () => reject(new Error('Could not decode image'));
      element.src = objectUrl;
    });

    const canvas = document.createElement('canvas');
    canvas.width = image.naturalWidth || image.width;
    canvas.height = image.naturalHeight || image.height;
    const context = canvas.getContext('2d');
    if (!context) throw new Error('Could not prepare image canvas');
    context.fillStyle = '#ffffff';
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(image, 0, 0);

    return {
      dataUrl: canvas.toDataURL('image/jpeg', 0.9),
      width: canvas.width,
      height: canvas.height,
    };
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

async function addImageBlock(doc: jsPDF, title: string, url: string | undefined, y: number) {
  if (!url) return y;

  y = addSection(doc, title, y);

  try {
    const image = await readImage(url);
    if (!image) {
      setText(doc, MUTED, 9);
      return addWrappedText(doc, `Open file: ${url}`, MARGIN, y, CONTENT_WIDTH, 4.7) + 5;
    }

    const maxHeight = 74;
    const scale = Math.min(CONTENT_WIDTH / image.width, maxHeight / image.height, 1);
    const width = image.width * scale;
    const height = image.height * scale;

    y = ensureSpace(doc, y, height + 10);
    doc.setFillColor(255, 255, 255);
    doc.setDrawColor(...LINE);
    doc.roundedRect(MARGIN, y, CONTENT_WIDTH, height + 8, 2, 2, 'FD');
    doc.addImage(image.dataUrl, 'JPEG', MARGIN + (CONTENT_WIDTH - width) / 2, y + 4, width, height);
    return y + height + 14;
  } catch {
    setText(doc, MUTED, 9);
    return addWrappedText(
      doc,
      `Preview could not be embedded. Open it here: ${url}`,
      MARGIN,
      y,
      CONTENT_WIDTH,
      4.7,
    ) + 5;
  }
}

function addFinding(doc: jsPDF, artifact: Artifact, index: number, y: number) {
  const title = `${index + 1}. ${artifact.type.replace(/_/g, ' ')}`;
  const body = `${artifact.description} Location: ${artifact.location.replace(/_/g, ' ')}. Confidence: ${artifact.confidence.toFixed(1)}%.`;
  const requiredHeight = 11 + textHeight(doc, body, CONTENT_WIDTH - 6, 4.5);
  y = ensureSpace(doc, y, requiredHeight);

  setText(doc, INK, 9.5, 'bold');
  doc.text(title, MARGIN, y);
  setText(doc, MUTED, 8.5);
  y = addWrappedText(doc, body, MARGIN + 3, y + 5, CONTENT_WIDTH - 6, 4.5) + 4;
  return y;
}

function addLinks(doc: jsPDF, analysis: Analysis, y: number) {
  const links: Array<[string, string | undefined]> = [
    ['Analysis ID', analysis.id],
    ['Media URL', analysis.mediaUrl],
    ['Heatmap URL', analysis.heatmapUrl],
  ];

  y = addSection(doc, 'Reference Links', y);
  links.forEach(([label, value]) => {
    if (!value) return;
    y = ensureSpace(doc, y, 12 + textHeight(doc, value, CONTENT_WIDTH, 4.5));
    setText(doc, MUTED, 7.5, 'bold');
    doc.text(label.toUpperCase(), MARGIN, y);
    setText(doc, INK, 8.5);
    y = addWrappedText(doc, value, MARGIN, y + 5, CONTENT_WIDTH, 4.5) + 3;
  });

  return y;
}

function boundedPdfText(value: string, maximum = MAX_PDF_VALUE_CHARS): string {
  if (value.length <= maximum) return value;
  return `${value.slice(0, maximum)}\n[Value truncated in PDF; use the forensic JSON export for the complete bounded value.]`;
}

function printableValue(value: JsonValue): string {
  if (value === null) return 'Not available';
  if (typeof value === 'string') return boundedPdfText(value);
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return boundedPdfText(JSON.stringify(value));
}

function addReportField(doc: jsPDF, label: string, value: string, y: number): number {
  y = ensureSpace(doc, y, 12);
  setText(doc, MUTED, 7.5, 'bold');
  y = addWrappedText(doc, label.toUpperCase(), MARGIN, y, CONTENT_WIDTH, 4.1);
  setText(doc, INK, 9);
  return addWrappedText(doc, boundedPdfText(value || 'Not available'), MARGIN, y + 1, CONTENT_WIDTH, 4.6) + 3;
}

function addSubsection(doc: jsPDF, title: string, y: number): number {
  y = ensureSpace(doc, y, 10);
  setText(doc, INK, 10, 'bold');
  doc.text(title, MARGIN, y);
  return y + 7;
}

function addForensicFinding(
  doc: jsPDF,
  finding: ForensicFinding,
  index: number,
  y: number
): number {
  y = ensureSpace(doc, y, 18);
  setText(doc, INK, 9.5, 'bold');
  y = addWrappedText(
    doc,
    `${index + 1}. ${boundedPdfText(finding.title, 600)}`,
    MARGIN,
    y,
    CONTENT_WIDTH,
    4.5
  );
  setText(doc, MUTED, 8);
  y = addWrappedText(
    doc,
    `${finding.severity.toUpperCase()} | ${finding.code}`,
    MARGIN,
    y,
    CONTENT_WIDTH,
    4.2
  );
  setText(doc, INK, 8.8);
  y = addWrappedText(doc, finding.explanation, MARGIN, y + 1, CONTENT_WIDTH, 4.5) + 1;
  if (finding.method || finding.method_version) {
    setText(doc, MUTED, 8);
    y = addWrappedText(
      doc,
      `Method: ${finding.method ?? 'Not specified'}${finding.method_version ? ` @ ${finding.method_version}` : ''}`,
      MARGIN,
      y,
      CONTENT_WIDTH,
      4.2
    );
  }
  if (Object.keys(finding.evidence).length > 0) {
    setText(doc, MUTED, 8);
    y = addWrappedText(
      doc,
      `Measured values: ${printableValue(finding.evidence)}`,
      MARGIN,
      y,
      CONTENT_WIDTH,
      4.2
    );
  }
  if (finding.limitations.length > 0) {
    setText(doc, MUTED, 8);
    y = addWrappedText(
      doc,
      `Limitations: ${finding.limitations.join(' ')}`,
      MARGIN,
      y,
      CONTENT_WIDTH,
      4.2
    );
  }
  return y + 4;
}

export function addForensicReviewSummary(
  doc: jsPDF,
  analysis: Analysis,
  y: number
): number {
  y = addSection(doc, 'Forensic Review', y);
  if (!analysis.forensicEvidence?.assessment) {
    setText(doc, MUTED, 9);
    return addWrappedText(
      doc,
      'A plain-language forensic assessment is unavailable for this analysis. This does not imply manipulation.',
      MARGIN,
      y,
      CONTENT_WIDTH,
      4.7
    ) + 5;
  }

  const assessment = analysis.forensicEvidence.assessment;
  y = addReportField(doc, 'Forensic conclusion', assessment.headline, y);
  y = addReportField(
    doc,
    'Review concern',
    `${assessment.review_concern_score}/100 - ${assessment.concern_band} concern. This is review prioritization, not fake probability. A low score does not prove authenticity.`,
    y
  );
  y = addReportField(
    doc,
    'Evidence coverage',
    `${assessment.evidence_coverage_score}/100. Coverage describes how much applicable evidence was collected; it is separate from concern.`,
    y
  );
  const alignment = analysis.modelForensicAlignment ?? assessment.model_alignment;
  const c2pa = analysis.forensicEvidence.c2pa;
  const provenance = c2pa.provenance;
  if (provenance) {
    y = addReportField(doc, 'Content Credentials origin', provenance.headline, y);
    y = addReportField(
      doc,
      'Provider or claim generator',
      provenance.provider ?? provenance.claim_generator ?? c2pa.claim_generator ?? 'Not declared',
      y
    );
    y = addReportField(doc, 'Credential signature', c2pa.signature_state, y);
    y = addReportField(doc, 'Signer trust', c2pa.trust_state, y);
  }
  if (alignment) {
    y = addReportField(doc, 'Model and provenance alignment', alignment.summary, y);
  }
  assessment.key_insights.slice(0, 5).forEach((insight, index) => {
    y = addReportField(doc, `Key insight ${index + 1}: ${insight.title}`, insight.user_message, y);
  });
  setText(doc, MUTED, 8.5);
  return addWrappedText(
    doc,
    'Missing metadata and missing Content Credentials are neutral. Verified origin describes a signed workflow declaration; it does not prove that the depicted event or claim is true.',
    MARGIN,
    y,
    CONTENT_WIDTH,
    4.5
  ) + 5;
}

export function addForensicTechnicalAppendix(
  doc: jsPDF,
  analysis: Analysis,
  y: number
): number {
  y = addSection(doc, 'Technical Forensic Appendix', y);
  setText(doc, MUTED, 8.5);
  y = addWrappedText(
    doc,
    'Forensic observations are separate from the model verdict. Compression and metadata findings are review indicators, not proof of editing, fakery, authorship, or malicious intent.',
    MARGIN,
    y,
    CONTENT_WIDTH,
    4.5
  ) + 4;

  if (!analysis.forensicEvidence) {
    setText(doc, MUTED, 9);
    return addWrappedText(
      doc,
      'Forensic evidence is unavailable for this analysis. Older records may predate evidence collection; absence is not evidence of manipulation.',
      MARGIN,
      y,
      CONTENT_WIDTH,
      4.7
    ) + 5;
  }

  const evidence = evidenceForDefaultExport(analysis.forensicEvidence);
  y = addReportField(doc, 'Overall status', evidence.status, y);
  y = addReportField(doc, 'SHA-256', evidence.sha256 ?? 'Not available', y);
  y = addReportField(
    doc,
    'Detected type and size',
    `${evidence.detected_mime_type ?? 'Not available'} | ${evidence.file_size_bytes != null ? `${evidence.file_size_bytes.toLocaleString()} bytes` : 'Byte size unavailable'}`,
    y
  );

  y = addSubsection(doc, 'Creation information', y);
  const device = [evidence.creation_info.device_make, evidence.creation_info.device_model]
    .filter(Boolean)
    .join(' ');
  y = addReportField(
    doc,
    'Software and device',
    `Software: ${evidence.creation_info.software.join(', ') || 'Not available'} | Device: ${device || 'Not available'}`,
    y
  );
  y = addReportField(
    doc,
    'Embedded dates',
    `Created: ${evidence.creation_info.created_at ?? 'Not available'} | Modified: ${evidence.creation_info.modified_at ?? 'Not available'} | Digitized: ${evidence.creation_info.digitized_at ?? 'Not available'}`,
    y
  );
  y = addReportField(
    doc,
    'Location disclosure',
    evidence.creation_info.location_present
      ? 'Location metadata was present; precise coordinates are intentionally omitted.'
      : 'No location metadata was reported.',
    y
  );
  y = addSubsection(doc, 'Source tags', y);
  const sourceTagEntries = Object.entries(evidence.creation_info.source_tags).slice(0, 64);
  if (sourceTagEntries.length === 0) {
    y = addReportField(doc, 'Source tags', 'No source tags were reported.', y);
  } else {
    sourceTagEntries.forEach(([field, tags]) => {
      y = addReportField(doc, humanizeForensicLabel(field), tags.slice(0, 16).join(', '), y);
    });
  }

  y = addSubsection(doc, 'Important normalized metadata', y);
  const importantMetadataKey = /(?:format|mime|width|height|dimension|orientation|color|bit.depth|duration|codec|profile|frame.rate|bitrate|stream.count|sample.rate|channels|software|encoder|handler|application|writing.library|timestamp|created|modified)/i;
  const metadataEntries = Object.entries(evidence.metadata.normalized)
    .sort(([left], [right]) => {
      const leftPriority = importantMetadataKey.test(left) ? 0 : 1;
      const rightPriority = importantMetadataKey.test(right) ? 0 : 1;
      return leftPriority - rightPriority || left.localeCompare(right);
    })
    .slice(0, MAX_PDF_METADATA_FIELDS);
  if (metadataEntries.length === 0) {
    y = addReportField(
      doc,
      'Metadata',
      'No normalized metadata was returned. Missing metadata is not evidence of manipulation.',
      y
    );
  } else {
    metadataEntries.forEach(([key, value]) => {
      y = addReportField(doc, humanizeForensicLabel(key), printableValue(value), y);
    });
  }

  y = addSubsection(doc, 'Metadata inconsistency findings', y);
  if (evidence.metadata_inconsistencies.length === 0) {
    y = addReportField(doc, 'Findings', 'No deterministic metadata inconsistencies were reported.', y);
  } else {
    evidence.metadata_inconsistencies.slice(0, 64).forEach((finding, index) => {
      y = addForensicFinding(doc, finding, index, y);
    });
  }

  y = addSubsection(doc, 'Compression and editing indicators', y);
  if (evidence.compression_indicators.length === 0) {
    y = addReportField(doc, 'Indicators', 'No compression or editing indicators were reported.', y);
  } else {
    evidence.compression_indicators.slice(0, 64).forEach((finding, index) => {
      y = addForensicFinding(doc, finding, index, y);
    });
  }

  y = addSubsection(doc, 'C2PA Content Credentials', y);
  if (evidence.c2pa.provenance) {
    y = addReportField(
      doc,
      'Provenance conclusion',
      `${evidence.c2pa.provenance.headline}. ${evidence.c2pa.provenance.user_message}`,
      y
    );
    if (evidence.c2pa.provenance.provider) {
      y = addReportField(doc, 'Declared provider', evidence.c2pa.provenance.provider, y);
    }
  }
  y = addReportField(
    doc,
    'Manifest, signature, and trust',
    `Manifest: ${evidence.c2pa.manifest_present ? evidence.c2pa.active_manifest ?? 'present' : 'not present'} | Signature: ${evidence.c2pa.signature_state} | Trust: ${evidence.c2pa.trust_state} | Asset validation: ${evidence.c2pa.validation_state ?? 'unknown'}`,
    y
  );
  y = addReportField(doc, 'Signer summary', evidence.c2pa.signer ?? 'Not available', y);
  y = addReportField(doc, 'Issuer summary', evidence.c2pa.issuer ?? 'Not available', y);
  if (evidence.c2pa.provenance?.digital_source_type) {
    y = addReportField(
      doc,
      'Controlled Digital Source Type URI',
      evidence.c2pa.provenance.digital_source_type,
      y
    );
  }
  if ((evidence.c2pa.assertion_labels ?? []).length > 0) {
    y = addReportField(
      doc,
      'Assertion labels',
      (evidence.c2pa.assertion_labels ?? []).slice(0, 64).join(' | '),
      y
    );
  }
  evidence.c2pa.actions.slice(0, 64).forEach((action, index) => {
    y = addReportField(
      doc,
      `Action ${index + 1}`,
      `${action.action} | Digital Source Type: ${action.digital_source_type ?? 'not declared'} | Software agent: ${action.software_agent ?? 'not declared'}`,
      y
    );
  });
  if (!evidence.c2pa.manifest_present) {
    y = addReportField(
      doc,
      'C2PA interpretation',
      'No C2PA credential was present. This is neutral and is not evidence of manipulation.',
      y
    );
  }
  (evidence.c2pa.validation_statuses ?? []).slice(0, 64).forEach((validation) => {
    y = addReportField(
      doc,
      `Validation ${validation.category}`,
      `${validation.code}: ${validation.summary}`,
      y
    );
  });

  y = addSubsection(doc, 'Perceptual fingerprint', y);
  y = addReportField(
    doc,
    'Algorithm',
    `${evidence.perceptual_fingerprint.algorithm ?? 'Not available'}${evidence.perceptual_fingerprint.algorithm_version ? ` @ ${evidence.perceptual_fingerprint.algorithm_version}` : ''}`,
    y
  );
  y = addReportField(
    doc,
    'Value',
    evidence.perceptual_fingerprint.value ?? 'Not available',
    y
  );

  y = addSubsection(doc, 'Duplicate and near-duplicate matches', y);
  if (evidence.similarity_matches.length === 0) {
    y = addReportField(doc, 'Matches', 'No compatible matches were returned from the bounded user-history search.', y);
  } else {
    evidence.similarity_matches.slice(0, 25).forEach((match, index) => {
      y = addReportField(
        doc,
        `${index + 1}. ${match.match_type} match`,
        `${match.filename} | ${match.analysis_id} | Score ${(match.similarity_score * 100).toFixed(1)}% | Distance ${match.distance ?? 'not applicable'} | ${match.algorithm}${match.algorithm_version ? ` @ ${match.algorithm_version}` : ''}`,
        y
      );
    });
  }

  const warnings = [
    ...evidence.warnings,
    ...evidence.metadata.warnings,
    ...evidence.c2pa.warnings,
    ...evidence.perceptual_fingerprint.warnings,
  ];
  y = addSubsection(doc, 'Extractor warnings and timing', y);
  y = addReportField(
    doc,
    'Forensic processing time',
    `${evidence.processing_time_ms.toLocaleString()} ms`,
    y
  );
  y = addReportField(
    doc,
    'Warnings',
    warnings.length > 0 ? warnings.slice(0, 64).join(' | ') : 'No extractor warnings were reported.',
    y
  );
  return y;
}

export function addForensicEvidenceSection(
  doc: jsPDF,
  analysis: Analysis,
  y: number
): number {
  y = addForensicReviewSummary(doc, analysis, y);
  return addForensicTechnicalAppendix(doc, analysis, y + 2);
}

export function addModelResultSection(
  doc: jsPDF,
  analysis: Analysis,
  y: number
): number {
  y = addSection(doc, 'Model Classification', y);
  y = addTwoColumnRows(
    doc,
    [
      [
        'Verdict',
        verdictLabel(analysis.result),
        'Predicted-class confidence',
        `${analysis.confidence.toFixed(1)}%`,
      ],
      [
        'Model version',
        analysis.modelVersion ?? 'Not available for this legacy result',
        'Media type',
        analysis.fileType.toUpperCase(),
      ],
    ],
    y,
  );

  y = addSection(doc, 'Model Class Probabilities', y + 2);
  y = addBar(doc, 'AI-generated / fake class probability', analysis.fakeProb, y, DANGER);
  y = addBar(doc, 'Authentic / real class probability', analysis.realProb, y, SUCCESS);

  if (analysis.explanation) {
    y = addSection(doc, 'Model Explanation', y + 2);
    setText(doc, INK, 9.5);
    y = addWrappedText(doc, analysis.explanation, MARGIN, y, CONTENT_WIDTH, 5) + 6;
  }
  y = addSection(
    doc,
    analysis.fileType === 'audio' ? 'Audio Model Limitations' : 'Model Limitations',
    y + 2,
  );
  setText(doc, MUTED, 9);
  y = addWrappedText(
    doc,
    modelResultLimitations(analysis.fileType).join(' '),
    MARGIN,
    y,
    CONTENT_WIDTH,
    5,
  ) + 6;
  return y;
}

export async function downloadAnalysisReport(analysis: Analysis) {
  const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
  let y = 58;

  addHeader(doc, analysis);

  y = addModelResultSection(doc, analysis, y);

  y = addForensicReviewSummary(doc, analysis, y + 2);

  y = addSection(doc, 'Details', y + 2);
  y = addTwoColumnRows(
    doc,
    [
      ['File size', formatFileSize(analysis.fileSize), 'Analyzed', formatDate(analysis.createdAt)],
      ['Processing time', formatProcessingTime(analysis.processingTime), 'XAI method', analysis.xaiMethod || 'Not available'],
      [
        'Frames analyzed',
        analysis.framesAnalyzed != null ? String(analysis.framesAnalyzed) : 'Not applicable',
        'Model target',
        analysis.xaiTargetClass?.replace(/_/g, ' ') || 'Not available',
      ],
    ],
    y,
  );

  const originalPreview =
    analysis.fileType === 'image' ? analysis.mediaUrl || analysis.thumbnailUrl : undefined;
  y = await addImageBlock(doc, 'Original Image', originalPreview, y + 2);
  y = await addImageBlock(doc, 'XAI Heatmap', analysis.xaiPanelUrl || analysis.heatmapUrl, y + 2);

  y = addSection(doc, 'Findings', y + 2);
  if (analysis.artifacts.length === 0) {
    setText(doc, MUTED, 9);
    y = addWrappedText(doc, 'No additional model findings were returned for this analysis.', MARGIN, y, CONTENT_WIDTH, 5) + 5;
  } else {
    analysis.artifacts.forEach((artifact, index) => {
      y = addFinding(doc, artifact, index, y);
    });
  }

  y = addForensicTechnicalAppendix(doc, analysis, y + 2);

  y = addLinks(doc, analysis, y + 2);

  const pageCount = doc.getNumberOfPages();
  for (let page = 1; page <= pageCount; page += 1) {
    doc.setPage(page);
    addFooter(doc, page);
  }

  doc.save(`truth-matrix-report-${slugifyFilename(analysis.filename)}.pdf`);
}

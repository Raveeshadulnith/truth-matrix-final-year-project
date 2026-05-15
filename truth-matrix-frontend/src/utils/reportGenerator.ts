import { jsPDF } from 'jspdf';
import type { Analysis, Artifact } from '../store/analysisStore';
import { formatDate, formatFileSize, formatProcessingTime } from './formatters';

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
  const lines = doc.splitTextToSize(text || 'Not available', width);
  doc.text(lines, x, y);
  return y + lines.length * lineHeight;
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

export async function downloadAnalysisReport(analysis: Analysis) {
  const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
  let y = 58;

  addHeader(doc, analysis);

  y = addSection(doc, 'Summary', y);
  y = addTwoColumnRows(
    doc,
    [
      ['Verdict', verdictLabel(analysis.result), 'Confidence', `${analysis.confidence.toFixed(1)}%`],
      ['File', analysis.filename, 'Type', analysis.fileType.toUpperCase()],
    ],
    y,
  );

  y = addSection(doc, 'Probability', y + 2);
  y = addBar(doc, 'Fake probability', analysis.fakeProb, y, DANGER);
  y = addBar(doc, 'Authentic probability', analysis.realProb, y, SUCCESS);

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

  if (analysis.explanation) {
    y = addSection(doc, 'Explanation', y + 2);
    setText(doc, INK, 9.5);
    y = addWrappedText(doc, analysis.explanation, MARGIN, y, CONTENT_WIDTH, 5) + 6;
  }

  const originalPreview =
    analysis.fileType === 'image' ? analysis.mediaUrl || analysis.thumbnailUrl : undefined;
  y = await addImageBlock(doc, 'Original Image', originalPreview, y + 2);
  y = await addImageBlock(doc, 'XAI Heatmap', analysis.xaiPanelUrl || analysis.heatmapUrl, y + 2);

  y = addSection(doc, 'Findings', y + 2);
  if (analysis.artifacts.length === 0) {
    setText(doc, MUTED, 9);
    y = addWrappedText(doc, 'No XAI findings were returned for this analysis.', MARGIN, y, CONTENT_WIDTH, 5) + 5;
  } else {
    analysis.artifacts.forEach((artifact, index) => {
      y = addFinding(doc, artifact, index, y);
    });
  }

  y = addLinks(doc, analysis, y + 2);

  const pageCount = doc.getNumberOfPages();
  for (let page = 1; page <= pageCount; page += 1) {
    doc.setPage(page);
    addFooter(doc, page);
  }

  doc.save(`truth-matrix-report-${slugifyFilename(analysis.filename)}.pdf`);
}

import { jsPDF } from 'jspdf';
import type { Analysis } from '../store/analysisStore';
import { formatDate, formatFileSize } from './formatters';

const PAGE_MARGIN = 44;
const PAGE_WIDTH = 595.28;
const PAGE_HEIGHT = 841.89;
const CONTENT_WIDTH = PAGE_WIDTH - PAGE_MARGIN * 2;

function safeFilename(value: string) {
  return value
    .replace(/\.[^.]+$/, '')
    .replace(/[^a-z0-9_-]+/gi, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 80) || 'analysis';
}

function verdictLabel(analysis: Analysis) {
  if (analysis.result === 'fake') {
    return 'Suspected Deepfake';
  }

  if (analysis.result === 'real') {
    return 'Authentic';
  }

  return 'Uncertain';
}

function modelLabel(analysis: Analysis) {
  if (analysis.fileType === 'video') {
    return 'EfficientNet-B4 + BiLSTM';
  }

  if (analysis.fileType === 'image') {
    return 'EfficientNet-B4';
  }

  return 'Audio model pending';
}

function setMutedText(doc: jsPDF) {
  doc.setTextColor(90, 98, 112);
}

function setBodyText(doc: jsPDF) {
  doc.setTextColor(20, 25, 35);
}

function ensureSpace(doc: jsPDF, y: number, requiredHeight: number) {
  if (y + requiredHeight <= PAGE_HEIGHT - PAGE_MARGIN) {
    return y;
  }

  doc.addPage();
  return PAGE_MARGIN;
}

function addSectionTitle(doc: jsPDF, title: string, y: number) {
  y = ensureSpace(doc, y, 42);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(14);
  doc.setTextColor(17, 24, 39);
  doc.text(title, PAGE_MARGIN, y);
  doc.setDrawColor(210, 216, 226);
  doc.line(PAGE_MARGIN, y + 8, PAGE_WIDTH - PAGE_MARGIN, y + 8);
  return y + 28;
}

function addWrappedText(
  doc: jsPDF,
  text: string,
  x: number,
  y: number,
  maxWidth = CONTENT_WIDTH,
  lineHeight = 13
) {
  const lines = doc.splitTextToSize(text, maxWidth);
  const height = lines.length * lineHeight;
  y = ensureSpace(doc, y, height + 8);
  doc.text(lines, x, y);
  return y + height;
}

function addKeyValue(doc: jsPDF, label: string, value: string, y: number) {
  y = ensureSpace(doc, y, 18);
  doc.setFontSize(10);
  doc.setFont('helvetica', 'bold');
  setMutedText(doc);
  doc.text(label, PAGE_MARGIN, y);
  doc.setFont('helvetica', 'normal');
  setBodyText(doc);
  const lines = doc.splitTextToSize(value || 'N/A', CONTENT_WIDTH - 150);
  doc.text(lines, PAGE_MARGIN + 150, y);
  return y + Math.max(16, lines.length * 12);
}

function readBlobAsDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

function getImageSize(dataUrl: string): Promise<{ width: number; height: number }> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () =>
      resolve({
        width: image.naturalWidth || image.width,
        height: image.naturalHeight || image.height,
      });
    image.onerror = () => reject(new Error('Could not load report image.'));
    image.src = dataUrl;
  });
}

async function loadImageForPdf(url: string) {
  if (!url) {
    return null;
  }

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Could not load image: ${response.status}`);
  }

  const blob = await response.blob();
  const dataUrl = await readBlobAsDataUrl(blob);
  const size = await getImageSize(dataUrl);
  const mime = blob.type.toLowerCase();
  const format = mime.includes('png') ? 'PNG' : 'JPEG';

  return {
    dataUrl,
    format,
    ...size,
  };
}

async function addImageBlock(
  doc: jsPDF,
  title: string,
  url: string | undefined,
  y: number,
  options: { maxHeight?: number } = {}
) {
  if (!url) {
    return y;
  }

  y = addSectionTitle(doc, title, y);

  try {
    const image = await loadImageForPdf(url);
    if (!image) {
      return y;
    }

    const maxHeight = options.maxHeight || 250;
    const ratio = Math.min(CONTENT_WIDTH / image.width, maxHeight / image.height, 1);
    const width = image.width * ratio;
    const height = image.height * ratio;
    y = ensureSpace(doc, y, height + 20);
    doc.addImage(
      image.dataUrl,
      image.format,
      PAGE_MARGIN,
      y,
      width,
      height,
      undefined,
      'FAST'
    );
    return y + height + 18;
  } catch {
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(10);
    setMutedText(doc);
    return addWrappedText(
      doc,
      `Preview could not be embedded because the file server did not allow browser PDF access. Open it here: ${url}`,
      PAGE_MARGIN,
      y,
      CONTENT_WIDTH,
      12
    ) + 8;
  }
}

export async function downloadAnalysisReport(analysis: Analysis) {
  const doc = new jsPDF({
    unit: 'pt',
    format: 'a4',
    compress: true,
  });

  const isFake = analysis.result === 'fake';
  const verdictColor: [number, number, number] = isFake
    ? [185, 28, 28]
    : analysis.result === 'real'
      ? [4, 120, 87]
      : [180, 83, 9];

  doc.setFillColor(8, 13, 28);
  doc.rect(0, 0, PAGE_WIDTH, 98, 'F');
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(22);
  doc.setTextColor(255, 255, 255);
  doc.text('TruthMatrix Analysis Report', PAGE_MARGIN, 42);
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(10);
  doc.setTextColor(190, 205, 220);
  doc.text(`Generated ${formatDate(new Date().toISOString())}`, PAGE_MARGIN, 62);
  doc.text(`Report ID: ${analysis.id}`, PAGE_MARGIN, 78);

  let y = 124;

  doc.setFillColor(...verdictColor);
  doc.roundedRect(PAGE_MARGIN, y, CONTENT_WIDTH, 72, 8, 8, 'F');
  doc.setTextColor(255, 255, 255);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(18);
  doc.text(verdictLabel(analysis), PAGE_MARGIN + 18, y + 30);
  doc.setFontSize(11);
  doc.setFont('helvetica', 'normal');
  doc.text(
    `${analysis.confidence.toFixed(2)}% confidence | Deepfake ${analysis.fakeProb.toFixed(
      2
    )}% | Authentic ${analysis.realProb.toFixed(2)}%`,
    PAGE_MARGIN + 18,
    y + 52
  );
  y += 100;

  y = addSectionTitle(doc, 'Summary', y);
  y = addKeyValue(doc, 'Filename', analysis.filename, y);
  y = addKeyValue(doc, 'Media type', analysis.fileType, y);
  y = addKeyValue(doc, 'File size', formatFileSize(analysis.fileSize), y);
  y = addKeyValue(doc, 'Analyzed', formatDate(analysis.createdAt), y);
  y = addKeyValue(doc, 'Processing time', `${analysis.processingTime.toFixed(2)}s`, y);
  y = addKeyValue(doc, 'Model', modelLabel(analysis), y);
  y = addKeyValue(doc, 'XAI method', analysis.xaiMethod || 'Not returned', y);
  y = addKeyValue(doc, 'XAI target', analysis.xaiTargetClass || 'Not returned', y);
  y = addKeyValue(doc, 'XAI layer', analysis.xaiLayer || 'Not returned', y);

  y = addSectionTitle(doc, 'Model Explanation', y + 10);
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(10);
  setBodyText(doc);
  const explanation =
    isFake
      ? `The trained ${analysis.fileType} model detected manipulation signals. The report includes the model probabilities and any Grad-CAM XAI artifact returned by the backend.`
      : `The trained ${analysis.fileType} model did not detect strong manipulation signals. Review the probabilities and XAI artifact for supporting context.`;
  y = addWrappedText(doc, explanation, PAGE_MARGIN, y, CONTENT_WIDTH, 13) + 8;

  y = addSectionTitle(doc, 'XAI Findings', y);
  if (analysis.artifacts.length > 0) {
    analysis.artifacts.forEach((artifact, index) => {
      y = ensureSpace(doc, y, 60);
      doc.setFillColor(248, 250, 252);
      doc.roundedRect(PAGE_MARGIN, y - 12, CONTENT_WIDTH, 54, 6, 6, 'F');
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(11);
      doc.setTextColor(17, 24, 39);
      doc.text(
        `${index + 1}. ${artifact.type.replace(/_/g, ' ')}`,
        PAGE_MARGIN + 12,
        y + 4
      );
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(9);
      setMutedText(doc);
      doc.text(
        `${artifact.confidence.toFixed(1)}% | Location: ${artifact.location.replace(/_/g, ' ')}`,
        PAGE_MARGIN + 12,
        y + 18
      );
      setBodyText(doc);
      y = addWrappedText(
        doc,
        artifact.description,
        PAGE_MARGIN + 12,
        y + 32,
        CONTENT_WIDTH - 24,
        11
      ) + 8;
    });
  } else {
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(10);
    setMutedText(doc);
    y = addWrappedText(
      doc,
      'No XAI findings were returned for this analysis.',
      PAGE_MARGIN,
      y
    ) + 8;
  }

  if (analysis.fileType === 'image') {
    y = await addImageBlock(
      doc,
      'Original Image Preview',
      analysis.mediaUrl || analysis.thumbnailUrl,
      y + 8,
      { maxHeight: 220 }
    );
  } else if (analysis.mediaUrl) {
    y = addSectionTitle(doc, 'Original Media', y + 8);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(10);
    setBodyText(doc);
    y = addWrappedText(doc, analysis.mediaUrl, PAGE_MARGIN, y, CONTENT_WIDTH, 12) + 8;
  }

  const xaiArtifactUrl =
    analysis.xaiPanelUrl || analysis.xaiOverlayUrl || analysis.heatmapUrl;
  y = await addImageBlock(doc, 'Grad-CAM XAI Artifact', xaiArtifactUrl, y + 8, {
    maxHeight: 280,
  });

  y = addSectionTitle(doc, 'Reference Links', y + 8);
  y = addKeyValue(doc, 'Media URL', analysis.mediaUrl || 'N/A', y);
  y = addKeyValue(doc, 'Heatmap URL', analysis.heatmapUrl || 'N/A', y);
  y = addKeyValue(doc, 'Overlay URL', analysis.xaiOverlayUrl || 'N/A', y);
  y = addKeyValue(doc, 'XAI panel URL', analysis.xaiPanelUrl || 'N/A', y);

  const pageCount = doc.getNumberOfPages();
  for (let page = 1; page <= pageCount; page += 1) {
    doc.setPage(page);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8);
    doc.setTextColor(120, 130, 145);
    doc.text(
      `TruthMatrix | Page ${page} of ${pageCount}`,
      PAGE_MARGIN,
      PAGE_HEIGHT - 24
    );
  }

  const filename = `truthmatrix-report-${safeFilename(analysis.filename)}-${analysis.id.slice(
    0,
    8
  )}.pdf`;
  doc.save(filename);
}

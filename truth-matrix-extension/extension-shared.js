(function initializeTruthMatrixExtension(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.TruthMatrixExtension = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function createExtensionApi() {
  'use strict';

  const API_BASE_URL = 'http://127.0.0.1:8000';
  const STORAGE_SCHEMA_VERSION = 5;
  const FORENSIC_SUMMARY_VERSION = 4;
  const MAX_HISTORY_ITEMS = 5;
  const MAX_URL_CHARS = 2048;
  const MAX_ERROR_CHARS = 600;
  const MAX_SHORT_TEXT_CHARS = 160;
  const MAX_EXPLANATION_CHARS = 600;
  const MAX_MODEL_VERSION_CHARS = 128;
  const MAX_STORAGE_STATE_BYTES = 24 * 1024;

  function boundedText(value, maximum = MAX_SHORT_TEXT_CHARS) {
    if (value === null || value === undefined) return null;
    const text = String(value).replace(/[\u0000-\u001f\u007f]/g, ' ').trim();
    return text ? text.slice(0, maximum) : null;
  }

  function boundedNumber(value, minimum, maximum) {
    if (typeof value !== 'number' || !Number.isFinite(value)) return null;
    return Math.min(maximum, Math.max(minimum, value));
  }

  function statusValue(value, fallback = 'unavailable') {
    return boundedText(value, 32) || fallback;
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function serializedByteLength(value) {
    return new TextEncoder().encode(JSON.stringify(value)).length;
  }

  function c2paDisplay(c2pa) {
    const evidence = c2pa && typeof c2pa === 'object' ? c2pa : {};
    const status = statusValue(evidence.status);
    const signatureState = statusValue(evidence.signature_state, 'unknown');
    const trustState = statusValue(evidence.trust_state, 'unknown');
    const validationState = statusValue(evidence.validation_state, 'unknown');
    const manifestPresent = evidence.manifest_present === true;

    if (status === 'unsupported') {
      return { key: 'unsupported', label: 'Unsupported', tone: 'neutral', signatureState, trustState };
    }
    if (status === 'unavailable' || status === 'error') {
      return { key: 'unavailable', label: 'Unavailable', tone: 'neutral', signatureState, trustState };
    }
    if (status === 'not_present' || !manifestPresent) {
      return {
        key: 'not_present',
        label: 'Not present',
        tone: 'neutral',
        signatureState,
        trustState,
      };
    }
    if (signatureState === 'invalid' || validationState === 'invalid') {
      return { key: 'invalid', label: 'Invalid', tone: 'negative', signatureState, trustState };
    }
    if (signatureState === 'valid' && trustState === 'trusted') {
      return { key: 'valid_trusted', label: 'Valid - trusted', tone: 'positive', signatureState, trustState };
    }
    if (signatureState === 'valid' && trustState === 'untrusted') {
      return { key: 'valid_untrusted', label: 'Valid - untrusted', tone: 'caution', signatureState, trustState };
    }
    if (signatureState === 'valid') {
      return { key: 'valid_trust_unknown', label: 'Valid - trust not checked', tone: 'neutral', signatureState, trustState };
    }
    return { key: 'unknown', label: 'Unknown', tone: 'neutral', signatureState, trustState };
  }

  function concernBand(value) {
    return ['low', 'moderate', 'high'].includes(value) ? value : 'insufficient';
  }

  function buildForensicSummary(evidence) {
    if (!evidence || typeof evidence !== 'object') return null;
    const creation = evidence.creation_info && typeof evidence.creation_info === 'object' ? evidence.creation_info : {};
    const assessment = evidence.assessment && typeof evidence.assessment === 'object' ? evidence.assessment : {};
    const observations = Array.isArray(creation.software_observations)
      ? creation.software_observations
      : [];
    const workflow = {
      editing: observations
        .filter((item) => item && item.category === 'editor')
        .map((item) => boundedText(item.name, 100)).filter(Boolean).slice(0, 2),
      aiGeneration: observations
        .filter((item) => item && item.category === 'ai_generation')
        .map((item) => boundedText(item.name, 100)).filter(Boolean).slice(0, 2),
    };
    const deviceParts = [boundedText(creation.device_make, 80), boundedText(creation.device_model, 80)].filter(Boolean);
    const c2pa = c2paDisplay(evidence.c2pa);
    const provenanceSource = evidence.c2pa && typeof evidence.c2pa.provenance === 'object'
      ? evidence.c2pa.provenance
      : null;
    const provenance = provenanceSource ? {
      originState: boundedText(provenanceSource.origin_state, 64),
      headline: boundedText(provenanceSource.headline, 160),
      provider: boundedText(provenanceSource.provider, 100),
    } : null;
    const matches = Array.isArray(evidence.similarity_matches) ? evidence.similarity_matches : [];
    const best = [...matches].sort((left, right) => {
      const typeDifference = (left?.match_type === 'exact' ? 0 : 1) - (right?.match_type === 'exact' ? 0 : 1);
      return typeDifference || Number(right?.similarity_score || 0) - Number(left?.similarity_score || 0);
    })[0];

    return {
      summaryVersion: FORENSIC_SUMMARY_VERSION,
      concernBand: concernBand(assessment.concern_band),
      summary: boundedText(
        assessment.summary || assessment.headline ||
        'A plain-language forensic assessment was not available for this result.',
        360,
      ),
      device: boundedText(deviceParts.join(' '), MAX_SHORT_TEXT_CHARS),
      workflow,
      c2pa,
      provenance,
      bestMatch: best ? {
        matchType: best.match_type === 'exact' ? 'exact' : 'near',
        filename: boundedText(best.filename, 120),
        similarityScore: boundedNumber(best.similarity_score, 0, 1),
      } : null,
    };
  }

  function normalizeForensicSummary(summary) {
    if (!summary || typeof summary !== 'object') return null;
    const source = {
      assessment: {
        concern_band: summary.concernBand,
        summary: summary.summary,
      },
      creation_info: {
        device_make: summary.device || summary.creation?.device,
        software_observations: [
          ...(Array.isArray(summary.workflow?.editing) ? summary.workflow.editing.map((name) => ({ name, category: 'editor' })) : []),
          ...(Array.isArray(summary.workflow?.aiGeneration) ? summary.workflow.aiGeneration.map((name) => ({ name, category: 'ai_generation' })) : []),
        ],
      },
      c2pa: {
        status: summary.c2pa?.key === 'not_present' ? 'not_present' : summary.c2pa?.key === 'unsupported' ? 'unsupported' : summary.c2pa?.key === 'unavailable' ? 'unavailable' : 'available',
        manifest_present: !['not_present', 'unsupported', 'unavailable'].includes(summary.c2pa?.key),
        signature_state: summary.c2pa?.signatureState,
        trust_state: summary.c2pa?.trustState,
        validation_state: summary.c2pa?.key === 'invalid' ? 'invalid' : 'unknown',
        provenance: summary.provenance ? {
          origin_state: summary.provenance.originState,
          origin_category: 'unknown',
          basis_strength: 'none',
          provider: summary.provenance.provider,
          headline: summary.provenance.headline,
          user_message: summary.provenance.headline,
          technical_references: [],
          limitations: [],
          classification_method: 'stored-summary',
          classification_version: '1',
        } : null,
      },
      similarity_matches: summary.bestMatch ? [{
        match_type: summary.bestMatch.matchType,
        filename: summary.bestMatch.filename,
        similarity_score: summary.bestMatch.similarityScore,
      }] : [],
    };
    return buildForensicSummary(source);
  }

  function buildBoundedResult(result) {
    if (!result || typeof result !== 'object') return null;
    const forensicSummary = result.forensic_summary
      ? normalizeForensicSummary(result.forensic_summary)
      : buildForensicSummary(result.forensic_evidence);
    let fakeProbability = boundedNumber(result.fake_probability, 0, 100);
    let authenticProbability = boundedNumber(result.authentic_probability, 0, 100);
    if (
      fakeProbability !== null &&
      authenticProbability !== null &&
      Math.abs(fakeProbability + authenticProbability - 100) > 0.1
    ) {
      fakeProbability = null;
      authenticProbability = null;
    }
    return {
      label: boundedText(result.label, 80) || 'Unknown',
      confidence: boundedNumber(result.confidence, 0, 100),
      fake_probability: fakeProbability,
      authentic_probability: authenticProbability,
      model_version: boundedText(result.model_version, MAX_MODEL_VERSION_CHARS),
      explanation: boundedText(result.explanation, MAX_EXPLANATION_CHARS),
      forensic_summary: forensicSummary,
    };
  }

  function normalizeBackendAnalysisResponse(result) {
    return buildBoundedResult(result);
  }

  function renderModelResultHtml(result) {
    const normalized = buildBoundedResult(result);
    if (!normalized) return '';
    const confidence = normalized.confidence === null
      ? 'Not stored'
      : `${normalized.confidence.toFixed(1)}%`;
    const hasAnyProbability =
      normalized.fake_probability !== null ||
      normalized.authentic_probability !== null;
    const probabilities = hasAnyProbability
        ? `<div class="metric-row model-probabilities">
            <div class="metric-box"><span class="metric-label">AI-generated / fake</span><strong class="metric-value">${normalized.fake_probability === null ? 'Not stored' : `${normalized.fake_probability.toFixed(1)}%`}</strong></div>
            <div class="metric-box"><span class="metric-label">Authentic / real</span><strong class="metric-value">${normalized.authentic_probability === null ? 'Not stored' : `${normalized.authentic_probability.toFixed(1)}%`}</strong></div>
          </div>`
        : '<p class="model-legacy-note">Class probabilities were not stored for this legacy result.</p>';
    const explanation = normalized.explanation
      ? `<div class="explain-box"><span class="section-tag">Model explanation</span><p>${escapeHtml(normalized.explanation)}</p></div>`
      : '';

    return `<section class="model-result-summary" aria-label="Model result">
      <div class="model-result-head"><span class="section-tag">Model output</span><strong>${escapeHtml(normalized.label)}</strong></div>
      <div class="model-result-meta">
        <span>Predicted-class confidence</span><strong>${escapeHtml(confidence)}</strong>
        <span>Model version</span><strong>${escapeHtml(normalized.model_version || 'Not stored for this legacy result')}</strong>
      </div>
      ${probabilities}
      ${explanation}
      <p class="model-meaning-note">Confidence applies to the displayed predicted class; it is not always the fake-class probability.</p>
    </section>`;
  }

  function normalizeAnalysisState(state, now = new Date().toISOString()) {
    if (!state || typeof state !== 'object') return null;
    const allowedStatus = ['loading', 'success', 'error'].includes(state.status)
      ? state.status
      : null;
    if (!allowedStatus) return null;
    const normalized = {
      schemaVersion: STORAGE_SCHEMA_VERSION,
      updatedAt: boundedText(state.updatedAt, 40) || now,
      status: allowedStatus,
      imageUrl: boundedText(state.imageUrl, MAX_URL_CHARS),
      result: state.result ? buildBoundedResult(state.result) : null,
      error: boundedText(state.error, MAX_ERROR_CHARS),
      startedAt: boundedText(state.startedAt, 40),
      completedAt: boundedText(state.completedAt, 40),
    };
    if (normalized.result && serializedByteLength(normalized) > MAX_STORAGE_STATE_BYTES) {
      normalized.imageUrl = boundedText(normalized.imageUrl, 1024);
    }
    if (normalized.result && serializedByteLength(normalized) > MAX_STORAGE_STATE_BYTES) {
      normalized.imageUrl = null;
    }
    return normalized;
  }

  function normalizeHistory(history) {
    if (!Array.isArray(history)) return [];
    return history
      .map((item) => normalizeAnalysisState(item))
      .filter(Boolean)
      .slice(0, MAX_HISTORY_ITEMS);
  }

  function renderForensicSummaryHtml(summary) {
    const normalized = normalizeForensicSummary(summary);
    if (!normalized) {
      return '<div class="forensic-summary forensic-summary--neutral"><div class="forensic-head"><span class="section-tag">Forensic evidence</span><span class="forensic-state neutral">Unavailable</span></div><p class="forensic-note">No forensic summary was stored for this result. Older extension results may predate evidence collection.</p></div>';
    }
    const overallTone = normalized.concernBand === 'high'
      ? 'negative'
      : normalized.concernBand === 'moderate' ? 'caution' : 'neutral';
    const workflowRows = [
      normalized.workflow.editing.length
        ? `<div class="forensic-row"><span>Editing software</span><strong>${escapeHtml(normalized.workflow.editing.join(', '))}</strong></div>`
        : '',
      normalized.workflow.aiGeneration.length
        ? `<div class="forensic-row"><span>AI-generation software</span><strong>${escapeHtml(normalized.workflow.aiGeneration.join(', '))}</strong></div>`
        : '',
    ].join('');
    const match = normalized.bestMatch;
    const provenance = normalized.provenance;
    const prominentProvenanceStates = new Set([
      'verified_ai_generated',
      'declared_ai_generated_untrusted',
      'verified_ai_edited',
      'declared_ai_edited_untrusted',
      'invalid_credential',
    ]);
    const prominentProvenance = provenance && prominentProvenanceStates.has(provenance.originState)
      ? provenance
      : null;
    return `
      <div class="forensic-summary">
        <div class="forensic-head">
          <span class="section-tag">Forensic review</span>
          <span class="forensic-state ${overallTone}">${escapeHtml(normalized.concernBand === 'insufficient' ? 'Insufficient evidence' : `${normalized.concernBand} concern`)}</span>
        </div>
        <p class="forensic-note">${escapeHtml(normalized.summary)}</p>
        ${prominentProvenance?.headline ? `<div class="forensic-origin forensic-origin--${escapeHtml(normalized.c2pa.tone)}"><span class="section-tag">Content Credentials origin</span><strong>${escapeHtml(prominentProvenance.headline)}</strong>${prominentProvenance.provider ? `<small>Provider: ${escapeHtml(prominentProvenance.provider)}</small>` : ''}</div>` : ''}
        ${normalized.device ? `<div class="forensic-row"><span>Device / origin</span><strong>${escapeHtml(normalized.device)}</strong></div>` : ''}
        ${workflowRows}
        <div class="forensic-row"><span>Credential signature</span><strong>${escapeHtml(normalized.c2pa.signatureState)}</strong></div>
        <div class="forensic-row"><span>Signer trust</span><strong>${escapeHtml(normalized.c2pa.trustState)}</strong></div>
        <div class="forensic-row"><span>Content Credentials</span><strong class="forensic-state ${escapeHtml(normalized.c2pa.tone)}">${escapeHtml(normalized.c2pa.label)}</strong></div>
        ${match ? `<div class="forensic-row"><span>Best history match</span><strong>${escapeHtml(`${match.matchType} - ${match.filename || 'previous analysis'}${match.similarityScore === null ? '' : ` (${(match.similarityScore * 100).toFixed(1)}%)`}`)}</strong></div>` : ''}
        <p class="forensic-note">Review concern is not fake probability. Low concern does not prove authenticity. A verified origin declaration does not prove that the depicted claim is true.</p>
      </div>`;
  }

  return {
    API_BASE_URL,
    STORAGE_SCHEMA_VERSION,
    FORENSIC_SUMMARY_VERSION,
    MAX_HISTORY_ITEMS,
    MAX_STORAGE_STATE_BYTES,
    escapeHtml,
    c2paDisplay,
    buildForensicSummary,
    buildBoundedResult,
    normalizeBackendAnalysisResponse,
    normalizeAnalysisState,
    normalizeHistory,
    renderModelResultHtml,
    renderForensicSummaryHtml,
  };
});

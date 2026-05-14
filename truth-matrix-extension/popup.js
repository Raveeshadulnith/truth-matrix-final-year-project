const API_BASE_URL   = 'http://127.0.0.1:8000';
const STORAGE_KEY    = 'truthMatrixAnalysisState';
const HISTORY_KEY    = 'truthMatrixAnalysisHistory';

const statusContainer  = document.getElementById('statusContainer');
const historyContainer = document.getElementById('historyContainer');
const refreshButton    = document.getElementById('refreshButton');
const reanalyzeButton  = document.getElementById('reanalyzeButton');
const clearButton      = document.getElementById('clearButton');

let latestState   = null;
let latestHistory = [];

/* ── helpers ─────────────────────────────────────────── */
function esc(v) {
  return String(v ?? '')
    .replaceAll('&','&amp;').replaceAll('<','&lt;')
    .replaceAll('>','&gt;').replaceAll('"','&quot;')
    .replaceAll("'",'&#039;');
}

function truncateUrl(url) {
  if (!url) return 'No image URL';
  try {
    const p = new URL(url);
    const path = p.pathname.length > 22 ? p.pathname.slice(0,22)+'…' : p.pathname;
    return p.hostname + path;
  } catch { return url.length > 36 ? url.slice(0,36)+'…' : url; }
}

function formatTime(v) {
  if (!v) return '—';
  return new Intl.DateTimeFormat(undefined, { hour:'2-digit', minute:'2-digit' }).format(new Date(v));
}

function getHeatmapUrl(u) {
  if (!u) return null;
  if (u.startsWith('http://') || u.startsWith('https://')) return u;
  return u.startsWith('/') ? `${API_BASE_URL}${u}` : `${API_BASE_URL}/${u}`;
}

function isDeepfake(result) { return result?.label === 'Suspected Deepfake'; }

/* ── empty ───────────────────────────────────────────── */
function renderEmptyState() {
  statusContainer.innerHTML = `
    <div class="panel empty-panel anim-in">
      <div class="empty-icon">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="url(#eg)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <defs>
            <linearGradient id="eg" x1="0" y1="0" x2="24" y2="24" gradientUnits="userSpaceOnUse">
              <stop stop-color="#a78bfa"/>
              <stop offset="1" stop-color="#38bdf8"/>
            </linearGradient>
          </defs>
          <circle cx="11" cy="11" r="8"/>
          <path d="m21 21-4.35-4.35"/>
          <circle cx="11" cy="11" r="3"/>
        </svg>
      </div>
      <h2>No analysis yet</h2>
      <p>Right-click any image on the web and select <strong>Verify with Truth Matrix</strong> to scan it.</p>
      <div class="steps">
        <span class="step-pill"><span class="step-num">1</span>Right-click image</span>
        <span class="step-pill"><span class="step-num">2</span>Click Verify</span>
        <span class="step-pill"><span class="step-num">3</span>See result</span>
      </div>
    </div>`;
}

/* ── loading ─────────────────────────────────────────── */
function renderLoadingState(state) {
  const imgHtml = state?.imageUrl
    ? `<img src="${esc(state.imageUrl)}" alt="Image being analyzed" />`
    : `<div class="scan-shimmer"></div>`;

  statusContainer.innerHTML = `
    <div class="panel loading-panel anim-in">
      <div class="scan-frame">
        ${imgHtml}
        <span class="scan-line"></span>
      </div>
      <div class="loading-info">
        <span class="loading-chip"><span class="spin"></span> ANALYZING</span>
        <h2>Scanning for signals…</h2>
        <p>Sending image to your local FastAPI backend for deepfake analysis.</p>
        <div class="progress-bar"><div class="progress-fill"></div></div>
      </div>
    </div>`;
}

/* ── error ───────────────────────────────────────────── */
function renderErrorState(state) {
  const err = state?.error || 'Something went wrong during analysis.';
  const imgHtml = state?.imageUrl
    ? `<div class="result-image-wrap" style="border-radius:14px;margin-bottom:12px;"><img src="${esc(state.imageUrl)}" alt="Analyzed image" /></div>`
    : '';

  statusContainer.innerHTML = `
    <div class="panel error-panel anim-in">
      ${imgHtml}
      <div class="error-icon">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#f87171" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/>
          <line x1="12" y1="8" x2="12" y2="12"/>
          <line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
      </div>
      <h2>Analysis failed</h2>
      <p>${esc(err)}</p>
      <div class="error-hint">Make sure FastAPI is running at <strong>http://127.0.0.1:8000</strong>, then try again.</div>
    </div>`;
}

/* ── result ──────────────────────────────────────────── */
function renderResultState(state) {
  const result     = state.result;
  const imageUrl   = state.imageUrl;
  const confidence = Math.max(0, Math.min(100, Number(result.confidence || 0)));
  const confText   = confidence.toFixed(1);
  const fake       = isDeepfake(result);
  const heatUrl    = getHeatmapUrl(result.heatmap_url);

  /* SVG ring: circumference ≈ 2π×32 = 201 */
  const dashOffset = 201 - (201 * confidence / 100);
  const ringClass  = fake ? 'deepfake' : 'authentic';
  const chipClass  = fake ? 'deepfake' : 'authentic';
  const chipLabel  = esc(result.label);
  const verdictTitle = fake ? 'Manipulation signals detected' : 'Authenticity signals detected';
  const verdictSub   = fake
    ? 'Review carefully before trusting or sharing.'
    : 'No strong deepfake signal detected by the model.';

  const reportText = `Truth Matrix: ${result.label} (${confText}% confidence). ${result.explanation || ''}`;

  statusContainer.innerHTML = `
    <div class="panel result-panel anim-in">
      ${imageUrl ? `
        <div class="result-image-wrap">
          <img src="${esc(imageUrl)}" alt="Analyzed image" />
          <span class="img-tag">Analyzed source</span>
        </div>` : ''}

      <div class="result-body">
        <div class="verdict-row">
          <div class="verdict-left">
            <span class="verdict-chip ${chipClass}">
              <span class="verdict-chip-dot"></span>${chipLabel}
            </span>
            <div class="verdict-title">${verdictTitle}</div>
            <div class="verdict-sub">${verdictSub}</div>
          </div>

          <div class="conf-ring">
            <svg width="76" height="76" viewBox="0 0 76 76">
              <circle class="ring-track" cx="38" cy="38" r="32"/>
              <circle class="ring-fill ${ringClass}" cx="38" cy="38" r="32"
                style="stroke-dashoffset:${dashOffset.toFixed(2)}"/>
            </svg>
            <div class="ring-label">
              <span class="ring-val">${confText}</span>
              <span class="ring-pct">% conf</span>
            </div>
          </div>
        </div>

        <div class="metric-row">
          <div class="metric-box">
            <span class="metric-label">Media type</span>
            <span class="metric-value">${esc(result.media_type || 'image')}</span>
          </div>
          <div class="metric-box">
            <span class="metric-label">Confidence</span>
            <span class="metric-value">${confText}%</span>
          </div>
        </div>

        <div class="explain-box">
          <span class="section-tag">AI Explanation</span>
          <p>${esc(result.explanation || 'No explanation was returned by the backend.')}</p>
        </div>

        ${heatUrl ? `
          <div class="heatmap-box">
            <span class="section-tag">XAI Heatmap</span>
            <img src="${esc(heatUrl)}" alt="Truth Matrix heatmap" />
          </div>` : `
          <div class="heatmap-box no-heat">
            <span class="section-tag">XAI Heatmap</span>
            <p>No heatmap returned yet — available once the explainable AI model is connected.</p>
          </div>`}

        <div class="quick-actions">
          <button class="action-btn" data-action="copy" data-report="${esc(reportText)}">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            Copy result
          </button>
          ${imageUrl ? `
          <button class="action-btn" data-action="open" data-url="${esc(imageUrl)}">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
            Open image
          </button>` : ''}
        </div>
      </div>
    </div>`;
}

/* ── history ─────────────────────────────────────────── */
function renderHistory(history) {
  if (!history.length) { historyContainer.innerHTML = ''; return; }

  const items = history.map((item, i) => {
    const label = item.result?.label || 'Failed';
    const conf  = item.result?.confidence ? `${Number(item.result.confidence).toFixed(1)}%` : '—';
    const cls   = item.status === 'error' ? 'error' : isDeepfake(item.result) ? 'deepfake' : 'authentic';
    return `
      <button class="history-item" data-index="${i}" type="button">
        <span class="h-dot ${cls}"></span>
        <span class="h-main">
          <strong>${esc(label)}</strong>
          <small>${esc(truncateUrl(item.imageUrl))}</small>
        </span>
        <span class="h-meta">
          <strong>${esc(conf)}</strong>
          <small>${esc(formatTime(item.completedAt || item.updatedAt))}</small>
        </span>
      </button>`;
  }).join('');

  historyContainer.innerHTML = `
    <div class="history-header">
      <span class="history-title">Recent scans</span>
      <span class="history-count">${history.length} / 5</span>
    </div>
    <div class="history-list anim-in">${items}</div>`;
}

/* ── state machine ───────────────────────────────────── */
function renderState(state) {
  latestState = state || null;
  reanalyzeButton.disabled = !(state?.imageUrl && state.status !== 'loading');

  if (!state?.status)              { renderEmptyState();       return; }
  if (state.status === 'loading')  { renderLoadingState(state); return; }
  if (state.status === 'error')    { renderErrorState(state);   return; }
  if (state.status === 'success' && state.result) { renderResultState(state); return; }
  renderEmptyState();
}

function loadState() {
  chrome.storage.local.get([STORAGE_KEY, HISTORY_KEY], (items) => {
    latestHistory = Array.isArray(items[HISTORY_KEY]) ? items[HISTORY_KEY] : [];
    renderState(items[STORAGE_KEY]);
    renderHistory(latestHistory);
  });
}

function sendMsg(msg) {
  return new Promise(res => chrome.runtime.sendMessage(msg, res));
}

/* ── events ──────────────────────────────────────────── */
refreshButton.addEventListener('click', loadState);

reanalyzeButton.addEventListener('click', async () => {
  if (!latestState?.imageUrl) return;
  await sendMsg({ type: 'TRUTH_MATRIX_ANALYZE_URL', imageUrl: latestState.imageUrl });
  loadState();
});

clearButton.addEventListener('click', async () => {
  await sendMsg({ type: 'TRUTH_MATRIX_CLEAR_RESULTS' });
  latestHistory = [];
  renderState(null);
  renderHistory([]);
});

statusContainer.addEventListener('click', async (e) => {
  const btn = e.target.closest('button[data-action]');
  if (!btn) return;
  if (btn.dataset.action === 'copy') {
    await navigator.clipboard.writeText(btn.dataset.report || '');
    const orig = btn.innerHTML;
    btn.textContent = '✓ Copied!';
    setTimeout(() => { btn.innerHTML = orig; }, 1400);
  }
  if (btn.dataset.action === 'open' && btn.dataset.url) {
    window.open(btn.dataset.url, '_blank', 'noopener,noreferrer');
  }
});

historyContainer.addEventListener('click', (e) => {
  const item = e.target.closest('.history-item');
  if (!item) return;
  const sel = latestHistory[Number(item.dataset.index)];
  if (sel) renderState(sel);
});

document.addEventListener('DOMContentLoaded', loadState);

chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== 'local') return;
  if (changes[HISTORY_KEY]) {
    latestHistory = Array.isArray(changes[HISTORY_KEY].newValue) ? changes[HISTORY_KEY].newValue : [];
    renderHistory(latestHistory);
  }
  if (changes[STORAGE_KEY]) renderState(changes[STORAGE_KEY].newValue);
});

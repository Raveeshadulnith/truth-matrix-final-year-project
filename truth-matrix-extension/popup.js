const STORAGE_KEY    = 'truthMatrixAnalysisState';
const HISTORY_KEY    = 'truthMatrixAnalysisHistory';

const {
  API_BASE_URL,
  escapeHtml: esc,
  normalizeAnalysisState,
  normalizeHistory,
  renderModelResultHtml,
  renderForensicSummaryHtml,
} = globalThis.TruthMatrixExtension;

const statusContainer  = document.getElementById('statusContainer');
const historyContainer = document.getElementById('historyContainer');
const refreshButton    = document.getElementById('refreshButton');
const reanalyzeButton  = document.getElementById('reanalyzeButton');
const clearButton      = document.getElementById('clearButton');

let latestState   = null;
let latestHistory = [];

/* ── helpers ─────────────────────────────────────────── */
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
    ? `<div class="result-image-wrap error-image-wrap"><img src="${esc(state.imageUrl)}" alt="Analyzed image" /></div>`
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
      <div class="error-hint">Make sure FastAPI is running at <strong>${esc(API_BASE_URL)}</strong>, then try again.</div>
    </div>`;
}

/* ── result ──────────────────────────────────────────── */
function renderResultState(state) {
  const result     = state.result;
  const confidence = typeof result.confidence === 'number' && Number.isFinite(result.confidence)
    ? Math.max(0, Math.min(100, result.confidence))
    : null;
  const confText   = confidence === null ? '—' : confidence.toFixed(1);
  const fake       = isDeepfake(result);

  /* SVG ring: circumference ≈ 2π×32 = 201 */
  const dashOffset = 201 - (201 * (confidence ?? 0) / 100);
  const ringClass  = fake ? 'deepfake' : 'authentic';
  const chipClass  = fake ? 'deepfake' : 'authentic';
  const chipLabel  = esc(result.label);
  const verdictTitle = fake ? 'AI-generated / fake class predicted' : 'Authentic / real class predicted';
  const verdictSub   = fake
    ? 'This is a model classification, not proof of a particular editing technique.'
    : 'The model assigned the image to its authentic/real class.';


  statusContainer.innerHTML = `
    <div class="panel result-panel anim-in">
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
                stroke-dashoffset="${dashOffset.toFixed(2)}"/>
            </svg>
            <div class="ring-label">
              <span class="ring-val">${confText}</span>
              <span class="ring-pct">${confidence === null ? 'not stored' : '% class conf'}</span>
            </div>
          </div>
        </div>

        ${renderModelResultHtml(result)}
        ${renderForensicSummaryHtml(result.forensic_summary)}

      </div>
    </div>`;
}

/* ── history ─────────────────────────────────────────── */
function renderHistory(history) {
  if (!history.length) { historyContainer.innerHTML = ''; return; }

  const items = history.map((item, i) => {
    const label = item.result?.label || 'Failed';
    const conf  = typeof item.result?.confidence === 'number'
      ? `${item.result.confidence.toFixed(1)}%`
      : '—';
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
  state = normalizeAnalysisState(state);
  latestState = state;
  reanalyzeButton.disabled = !(state?.imageUrl && state.status !== 'loading');

  if (!state?.status)              { renderEmptyState();       return; }
  if (state.status === 'loading')  { renderLoadingState(state); return; }
  if (state.status === 'error')    { renderErrorState(state);   return; }
  if (state.status === 'success' && state.result) { renderResultState(state); return; }
  renderEmptyState();
}

function loadState() {
  chrome.storage.local.get([STORAGE_KEY, HISTORY_KEY], (items) => {
    const state = normalizeAnalysisState(items[STORAGE_KEY]);
    latestHistory = normalizeHistory(items[HISTORY_KEY]);
    const updates = {};
    if (state && JSON.stringify(state) !== JSON.stringify(items[STORAGE_KEY])) {
      updates[STORAGE_KEY] = state;
    }
    if (JSON.stringify(latestHistory) !== JSON.stringify(items[HISTORY_KEY] || [])) {
      updates[HISTORY_KEY] = latestHistory;
    }
    if (Object.keys(updates).length) chrome.storage.local.set(updates);
    renderState(state);
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
  if (btn.dataset.action === 'copy' || btn.dataset.action === 'copy-hash') {
    const text = btn.dataset.action === 'copy-hash'
      ? btn.dataset.hash || ''
      : btn.dataset.report || '';
    const originalText = btn.textContent;
    await navigator.clipboard.writeText(text);
    btn.textContent = 'Copied!';
    setTimeout(() => { btn.textContent = originalText; }, 1400);
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
    latestHistory = normalizeHistory(changes[HISTORY_KEY].newValue);
    renderHistory(latestHistory);
  }
  if (changes[STORAGE_KEY]) renderState(normalizeAnalysisState(changes[STORAGE_KEY].newValue));
});

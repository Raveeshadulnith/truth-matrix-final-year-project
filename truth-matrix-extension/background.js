const API_BASE_URL = 'http://127.0.0.1:8000';
const IMAGE_URL_ENDPOINT = `${API_BASE_URL}/api/analyze/image-url`;
const IMAGE_PUBLIC_ENDPOINT = `${API_BASE_URL}/api/analyze/image-public`;
const CONTEXT_MENU_ID = 'truth-matrix-verify-image';
const STORAGE_KEY = 'truthMatrixAnalysisState';
const HISTORY_KEY = 'truthMatrixAnalysisHistory';
const MAX_HISTORY_ITEMS = 5;

function createContextMenu() {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: CONTEXT_MENU_ID,
      title: 'Verify with Truth Matrix',
      contexts: ['image'],
    });
  });
}

chrome.runtime.onInstalled.addListener(createContextMenu);
chrome.runtime.onStartup.addListener(createContextMenu);

async function saveAnalysisState(state) {
  await chrome.storage.local.set({
    [STORAGE_KEY]: {
      updatedAt: new Date().toISOString(),
      ...state,
    },
  });
}

async function addHistoryItem(item) {
  const stored = await chrome.storage.local.get(HISTORY_KEY);
  const history = Array.isArray(stored[HISTORY_KEY]) ? stored[HISTORY_KEY] : [];
  const nextHistory = [item, ...history].slice(0, MAX_HISTORY_ITEMS);
  await chrome.storage.local.set({ [HISTORY_KEY]: nextHistory });
}

function getErrorMessage(data, fallbackMessage) {
  if (!data) {
    return fallbackMessage;
  }

  if (typeof data === 'string') {
    return data || fallbackMessage;
  }

  if (typeof data.detail === 'string') {
    return data.detail;
  }

  if (Array.isArray(data.detail)) {
    return data.detail.map((item) => item.msg || item.message).join(', ');
  }

  if (typeof data.message === 'string') {
    return data.message;
  }

  return fallbackMessage;
}

async function readResponseBody(response) {
  const contentType = response.headers.get('content-type') || '';

  if (contentType.includes('application/json')) {
    return response.json();
  }

  return response.text();
}

function extensionFromContentType(contentType) {
  const cleanType = String(contentType || '').split(';', 1)[0].trim().toLowerCase();

  if (cleanType === 'image/png') return 'png';
  if (cleanType === 'image/webp') return 'webp';
  if (cleanType === 'image/jpeg' || cleanType === 'image/jpg') return 'jpg';

  return 'jpg';
}

function filenameFromImageUrl(imageUrl, contentType) {
  try {
    const url = new URL(imageUrl);
    const lastSegment = url.pathname.split('/').filter(Boolean).pop() || '';
    const cleanName = lastSegment.split('?')[0].replace(/[^\w.-]/g, '_');

    if (/\.(jpe?g|png|webp)$/i.test(cleanName)) {
      return cleanName;
    }
  } catch {
    // Use a generated filename below.
  }

  return `truth-matrix-image.${extensionFromContentType(contentType)}`;
}

function showNotification(title, message) {
  chrome.notifications.create({
    type: 'basic',
    iconUrl: 'icons/icon128.png',
    title,
    message,
  });
}

async function requestImageUrlAnalysis(imageUrl) {
  const response = await fetch(IMAGE_URL_ENDPOINT, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ image_url: imageUrl }),
  });

  const data = await readResponseBody(response);

  if (!response.ok) {
    throw new Error(
      getErrorMessage(data, 'Truth Matrix analysis failed. Please try again.')
    );
  }

  return data;
}

async function requestImageUploadAnalysis(imageUrl) {
  const imageResponse = await fetch(imageUrl, {
    credentials: 'include',
    cache: 'no-store',
  });

  if (!imageResponse.ok) {
    throw new Error(`Could not fetch image in browser: HTTP ${imageResponse.status}`);
  }

  const blob = await imageResponse.blob();
  const contentType = blob.type || imageResponse.headers.get('content-type') || '';

  if (contentType && !contentType.toLowerCase().startsWith('image/')) {
    throw new Error('Selected URL did not return an image.');
  }

  const formData = new FormData();
  formData.append('file', blob, filenameFromImageUrl(imageUrl, contentType));

  const response = await fetch(IMAGE_PUBLIC_ENDPOINT, {
    method: 'POST',
    body: formData,
  });

  const data = await readResponseBody(response);

  if (!response.ok) {
    throw new Error(
      getErrorMessage(data, 'Truth Matrix upload analysis failed. Please try again.')
    );
  }

  return data;
}

async function analyzeImageUrl(imageUrl) {
  const startedAt = new Date().toISOString();

  await saveAnalysisState({
    status: 'loading',
    imageUrl,
    result: null,
    error: null,
    startedAt,
  });

  try {
    let data;

    try {
      data = await requestImageUrlAnalysis(imageUrl);
    } catch (urlError) {
      data = await requestImageUploadAnalysis(imageUrl).catch((uploadError) => {
        const primaryMessage =
          urlError instanceof Error ? urlError.message : String(urlError);
        const fallbackMessage =
          uploadError instanceof Error ? uploadError.message : String(uploadError);
        throw new Error(`${primaryMessage} Upload fallback failed: ${fallbackMessage}`);
      });
    }

    const completedAt = new Date().toISOString();
    const successState = {
      status: 'success',
      imageUrl,
      result: data,
      error: null,
      startedAt,
      completedAt,
    };

    await saveAnalysisState(successState);
    await addHistoryItem(successState);

    showNotification(
      'Truth Matrix analysis complete',
      `${data.label} - ${Number(data.confidence).toFixed(2)}% confidence`
    );
  } catch (error) {
    const message =
      error.message ||
      'Could not connect to Truth Matrix. Make sure the FastAPI backend is running.';

    const errorState = {
      status: 'error',
      imageUrl,
      result: null,
      error: message,
      startedAt,
      completedAt: new Date().toISOString(),
    };

    await saveAnalysisState(errorState);
    await addHistoryItem(errorState);

    showNotification('Truth Matrix analysis failed', message);
  }
}

chrome.contextMenus.onClicked.addListener((info) => {
  if (info.menuItemId !== CONTEXT_MENU_ID) {
    return;
  }

  const imageUrl = info.srcUrl;

  if (!imageUrl) {
    saveAnalysisState({
      status: 'error',
      imageUrl: null,
      result: null,
      error: 'No image URL was found for the selected image.',
    });
    showNotification('Truth Matrix', 'No image URL was found.');
    return;
  }

  analyzeImageUrl(imageUrl);
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === 'TRUTH_MATRIX_ANALYZE_URL' && message.imageUrl) {
    analyzeImageUrl(message.imageUrl);
    sendResponse({ ok: true });
    return true;
  }

  if (message?.type === 'TRUTH_MATRIX_CLEAR_RESULTS') {
    chrome.storage.local.remove([STORAGE_KEY, HISTORY_KEY], () => {
      sendResponse({ ok: true });
    });
    return true;
  }

  return false;
});

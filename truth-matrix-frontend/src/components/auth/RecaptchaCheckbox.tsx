import { useEffect, useId, useRef, useState } from 'react';

interface RecaptchaV2Api {
  render: (container: string | HTMLElement, parameters: Record<string, unknown>) => number;
  reset: (widgetId?: number) => void;
}

declare global {
  interface Window {
    grecaptcha?: Partial<RecaptchaV2Api>;
    __truthMatrixRecaptchaReady?: Promise<RecaptchaV2Api>;
  }
}

function currentRecaptchaApi(): RecaptchaV2Api | null {
  const api = window.grecaptcha;
  return api && typeof api.render === 'function' && typeof api.reset === 'function'
    ? api as RecaptchaV2Api
    : null;
}

function waitForRecaptchaApi(timeoutMs = 10_000): Promise<RecaptchaV2Api> {
  return new Promise((resolve, reject) => {
    const startedAt = Date.now();
    const check = () => {
      const api = currentRecaptchaApi();
      if (api) {
        resolve(api);
        return;
      }
      if (Date.now() - startedAt >= timeoutMs) {
        reject(new Error('CAPTCHA checkbox API did not become ready. Please reload and try again.'));
        return;
      }
      window.setTimeout(check, 25);
    };
    check();
  });
}

function loadRecaptcha(): Promise<RecaptchaV2Api> {
  const readyApi = currentRecaptchaApi();
  if (readyApi) return Promise.resolve(readyApi);
  if (window.__truthMatrixRecaptchaReady) return window.__truthMatrixRecaptchaReady;

  const loading = new Promise<RecaptchaV2Api>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>('script[data-truth-matrix-recaptcha]');
    const waitUntilReady = () => waitForRecaptchaApi().then(resolve, reject);
    if (existing) {
      waitUntilReady();
      existing.addEventListener('load', waitUntilReady, { once: true });
      existing.addEventListener('error', () => reject(new Error('Could not load CAPTCHA.')), { once: true });
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://www.google.com/recaptcha/api.js?render=explicit';
    script.async = true;
    script.defer = true;
    script.dataset.truthMatrixRecaptcha = 'true';
    script.onload = waitUntilReady;
    script.onerror = () => reject(new Error('Could not load CAPTCHA.'));
    document.head.appendChild(script);
  });
  window.__truthMatrixRecaptchaReady = loading.catch((error) => {
    window.__truthMatrixRecaptchaReady = undefined;
    throw error;
  });
  return window.__truthMatrixRecaptchaReady;
}

interface RecaptchaCheckboxProps {
  onToken: (token: string | null) => void;
  resetKey?: number;
}

export function RecaptchaCheckbox({ onToken, resetKey = 0 }: RecaptchaCheckboxProps) {
  const reactId = useId().replace(/:/g, '');
  const containerId = `recaptcha-${reactId}`;
  const widgetId = useRef<number>();
  const [error, setError] = useState('');
  const siteKey = import.meta.env.VITE_RECAPTCHA_SITE_KEY as string | undefined;

  useEffect(() => {
    let active = true;
    if (!siteKey) {
      setError('CAPTCHA site key is not configured.');
      return;
    }
    loadRecaptcha()
      .then((api) => {
        if (!active || widgetId.current !== undefined) return;
        widgetId.current = api.render(containerId, {
          sitekey: siteKey,
          callback: (token: string) => onToken(token),
          'expired-callback': () => onToken(null),
          'error-callback': () => {
            onToken(null);
            setError('CAPTCHA could not be completed. Please try again.');
          },
          theme: document.documentElement.classList.contains('dark') ? 'dark' : 'light',
        });
      })
      .catch((loadError) => active && setError(loadError instanceof Error ? loadError.message : 'Could not load CAPTCHA.'));
    return () => {
      active = false;
    };
  }, [containerId, onToken, siteKey]);

  useEffect(() => {
    const api = currentRecaptchaApi();
    if (widgetId.current !== undefined && api) {
      api.reset(widgetId.current);
      onToken(null);
    }
  }, [onToken, resetKey]);

  return (
    <div className="space-y-2">
      <div id={containerId} aria-label="Bot verification" />
      {error && <p role="alert" className="text-sm text-red-600 dark:text-red-400">{error}</p>}
    </div>
  );
}

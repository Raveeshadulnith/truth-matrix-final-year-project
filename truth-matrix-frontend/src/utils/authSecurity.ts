export function normalizeOtpCode(value: string): string {
  return value.replace(/\D/g, '').slice(0, 6);
}

export function secondsUntilExpiry(expiresAt: number, now = Date.now()): number {
  return Math.max(0, Math.ceil((expiresAt - now) / 1000));
}

export function shouldRequireCaptcha(errorCode: string | null | undefined, alreadyRequired = false): boolean {
  return alreadyRequired || errorCode === 'CAPTCHA_REQUIRED';
}

export function isCompleteOtp(value: string): boolean {
  return /^\d{6}$/.test(value);
}

export function idleSessionCountdown(
  lastActivityAt: number,
  idleTimeoutSeconds: number,
  now = Date.now()
): { state: 'active' | 'warning' | 'expired'; secondsLeft: number } {
  const idleSeconds = Math.floor((now - lastActivityAt) / 1000);
  const secondsLeft = Math.max(0, idleTimeoutSeconds - idleSeconds);
  return {
    state: secondsLeft === 0 ? 'expired' : secondsLeft <= 60 ? 'warning' : 'active',
    secondsLeft,
  };
}

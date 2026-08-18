import React, { useCallback, useEffect, useState } from 'react';
import { ArrowLeftIcon, MailCheckIcon } from 'lucide-react';
import { Button } from '../common/Button';
import { Input } from '../common/Input';
import { RecaptchaCheckbox } from './RecaptchaCheckbox';
import { useAuthStore } from '../../store/authStore';
import { isCompleteOtp, normalizeOtpCode, secondsUntilExpiry } from '../../utils/authSecurity';

interface MfaChallengePanelProps {
  onSuccess: () => void;
}

export function MfaChallengePanel({ onSuccess }: MfaChallengePanelProps) {
  const {
    pendingChallenge, verifyMfa, resendMfa, cancelPendingChallenge,
    isLoading, error, message, clearError,
  } = useAuthStore();
  const [code, setCode] = useState('');
  const [remaining, setRemaining] = useState(0);
  const [resendCooldown, setResendCooldown] = useState(60);
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const [captchaReset, setCaptchaReset] = useState(0);
  const captchaCallback = useCallback((token: string | null) => setCaptchaToken(token), []);

  useEffect(() => {
    const update = () => setRemaining(secondsUntilExpiry(pendingChallenge?.expiresAt || 0));
    update();
    const timer = window.setInterval(update, 1000);
    return () => window.clearInterval(timer);
  }, [pendingChallenge?.expiresAt]);

  useEffect(() => {
    if (resendCooldown <= 0) return;
    const timer = window.setTimeout(() => setResendCooldown((value) => value - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [resendCooldown]);

  if (!pendingChallenge) return null;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    clearError();
    if (await verifyMfa(code)) onSuccess();
  };

  const resend = async () => {
    if (!captchaToken) return;
    const sent = await resendMfa(captchaToken);
    setCaptchaReset((value) => value + 1);
    if (sent) setResendCooldown(60);
  };

  return (
    <div className="p-6 space-y-5">
      <div className="text-center">
        <MailCheckIcon className="w-12 h-12 text-neon-cyan mx-auto mb-3" />
        <h2 className="text-xl font-bold text-gray-900 dark:text-white">Enter your security code</h2>
        <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
          We sent a six-digit code to {pendingChallenge.maskedDestination}.
        </p>
      </div>
      {error && <p role="alert" className="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 text-sm text-red-600 dark:text-red-400">{error}</p>}
      {message && <p role="status" className="text-sm text-gray-600 dark:text-gray-300">{message}</p>}
      <form onSubmit={submit} className="space-y-4">
        <Input
          label="Verification code"
          value={code}
          onChange={(event) => setCode(normalizeOtpCode(event.target.value))}
          inputMode="numeric"
          autoComplete="one-time-code"
          pattern="[0-9]{6}"
          maxLength={6}
          disabled={remaining === 0}
        />
        <p className="text-xs text-gray-500" aria-live="polite">
          {remaining > 0 ? `Code expires in ${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, '0')}` : 'This code has expired. Request a new one.'}
        </p>
        <Button type="submit" className="w-full" size="lg" isLoading={isLoading} disabled={!isCompleteOtp(code) || remaining === 0}>
          Verify and continue
        </Button>
      </form>
      <div className="border-t border-gray-200 dark:border-navy-700 pt-4 space-y-3">
        <p className="text-xs text-gray-500">Complete a fresh CAPTCHA to request a new code.</p>
        <RecaptchaCheckbox onToken={captchaCallback} resetKey={captchaReset} />
        <Button type="button" variant="secondary" className="w-full" onClick={resend} disabled={!captchaToken || resendCooldown > 0}>
          {resendCooldown > 0 ? `Resend available in ${resendCooldown}s` : 'Resend code'}
        </Button>
      </div>
      <button type="button" onClick={cancelPendingChallenge} className="inline-flex items-center gap-2 text-sm text-gray-500 hover:text-neon-cyan">
        <ArrowLeftIcon className="w-4 h-4" /> Start again
      </button>
    </div>
  );
}

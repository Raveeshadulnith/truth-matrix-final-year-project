import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../common/Button';
import { useAuthStore } from '../../store/authStore';
import { ROUTES } from '../../utils/constants';
import { getCurrentProfile } from '../../api/deepfakeApi';
import { idleSessionCountdown } from '../../utils/authSecurity';

const ACTIVITY_EVENTS: Array<keyof WindowEventMap> = ['pointerdown', 'keydown', 'scroll', 'touchstart'];

export function SessionTimeoutManager() {
  const navigate = useNavigate();
  const {
    isAuthenticated, accessToken, idleTimeoutSeconds,
    refreshSession, logout, clearLocalSession,
  } = useAuthStore();
  const lastActivity = useRef(Date.now());
  const lastServerTouch = useRef(Date.now());
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);

  useEffect(() => {
    const crossTabLogout = (event: StorageEvent) => {
      if (event.key === 'truth-matrix-logout-event') {
        clearLocalSession('You were signed out in another tab.');
        navigate(ROUTES.LOGIN);
      }
    };
    window.addEventListener('storage', crossTabLogout);
    return () => window.removeEventListener('storage', crossTabLogout);
  }, [clearLocalSession, navigate]);

  useEffect(() => {
    const sessionExpired = () => {
      clearLocalSession('Your session has expired. Please sign in again.');
      navigate(ROUTES.LOGIN);
    };
    window.addEventListener('truth-matrix-session-expired', sessionExpired);
    return () => window.removeEventListener('truth-matrix-session-expired', sessionExpired);
  }, [clearLocalSession, navigate]);

  useEffect(() => {
    if (!isAuthenticated) {
      setSecondsLeft(null);
      return;
    }
    lastActivity.current = Date.now();
    const markActivity = () => {
      lastActivity.current = Date.now();
      setSecondsLeft(null);
      if (accessToken && Date.now() - lastServerTouch.current >= 60_000) {
        lastServerTouch.current = Date.now();
        void getCurrentProfile(accessToken).catch(async () => {
          const refreshed = await refreshSession();
          if (!refreshed) navigate(ROUTES.LOGIN);
        });
      }
    };
    ACTIVITY_EVENTS.forEach((eventName) => window.addEventListener(eventName, markActivity, { passive: true }));
    const timer = window.setInterval(() => {
      const countdown = idleSessionCountdown(lastActivity.current, idleTimeoutSeconds);
      if (countdown.state === 'expired') {
        void logout('You were signed out after a period of inactivity.').then(() => navigate(ROUTES.LOGIN));
      } else if (countdown.state === 'warning') {
        setSecondsLeft(countdown.secondsLeft);
      }
    }, 1000);
    return () => {
      window.clearInterval(timer);
      ACTIVITY_EVENTS.forEach((eventName) => window.removeEventListener(eventName, markActivity));
    };
  }, [accessToken, idleTimeoutSeconds, isAuthenticated, logout, navigate, refreshSession]);

  const continueSession = async () => {
    if (!accessToken) return;
    try {
      await getCurrentProfile(accessToken);
      lastActivity.current = Date.now();
      lastServerTouch.current = Date.now();
      setSecondsLeft(null);
    } catch {
      const refreshed = await refreshSession();
      if (!refreshed) navigate(ROUTES.LOGIN);
    }
  };

  if (secondsLeft === null) return null;
  return (
    <div role="alertdialog" aria-live="assertive" className="fixed bottom-5 right-5 z-50 max-w-sm rounded-xl border border-amber-300 bg-white dark:bg-navy-800 p-4 shadow-xl">
      <p className="font-semibold text-gray-900 dark:text-white">Session expiring soon</p>
      <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">You will be signed out in {secondsLeft} seconds due to inactivity.</p>
      <Button className="mt-3 w-full" size="sm" onClick={() => void continueSession()}>
        Continue session
      </Button>
    </div>
  );
}

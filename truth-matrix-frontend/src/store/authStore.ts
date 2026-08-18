import { create } from 'zustand';
import {
  ApiError,
  getCurrentProfile,
  loginUser,
  logoutUser,
  refreshUserSession,
  registerUser,
  requestPasswordReset,
  resendMfaChallenge,
  updateCurrentProfile,
  verifyMfaChallenge,
  type AuthChallengeResponse,
  type AuthResponse,
  type BackendProfile,
  type BackendUser,
} from '../api/deepfakeApi';
import { shouldRequireCaptcha } from '../utils/authSecurity';

type UserRole = 'user' | 'admin';

export interface User {
  id: string;
  email: string;
  fullName: string;
  profilePicture?: string;
  role: UserRole;
  creditsRemaining: number;
  totalAnalyses: number;
  emailVerified: boolean;
  createdAt: string;
}

export interface PendingAuthChallenge {
  id: string;
  purpose: AuthChallengeResponse['purpose'];
  maskedDestination: string;
  expiresAt: number;
  email: string;
  fullName?: string;
}

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isInitialized: boolean;
  isLoading: boolean;
  error: string | null;
  errorCode: string | null;
  message: string | null;
  captchaRequired: boolean;
  pendingChallenge: PendingAuthChallenge | null;
  idleTimeoutSeconds: number;
  pendingPassword: string | null;

  initialize: () => Promise<void>;
  login: (email: string, password: string, captchaToken?: string | null) => Promise<'authenticated' | 'mfa_required' | 'failed'>;
  register: (data: RegisterData, captchaToken: string) => Promise<'mfa_required' | 'failed'>;
  verifyMfa: (code: string) => Promise<boolean>;
  resendMfa: (captchaToken: string) => Promise<boolean>;
  cancelPendingChallenge: () => void;
  refreshSession: () => Promise<string | null>;
  logout: (reason?: string) => Promise<void>;
  clearLocalSession: (message?: string) => void;
  updateProfile: (data: Partial<User>) => Promise<void>;
  resetPassword: (email: string, captchaToken: string) => Promise<void>;
  clearError: () => void;
}

interface RegisterData {
  email: string;
  password: string;
  fullName: string;
}

function getMetadataFullName(user: BackendUser): string {
  return user.user_metadata?.full_name?.trim() || '';
}

function normalizeUser(authUser: BackendUser | BackendProfile, existingUser?: User | null): User {
  const profile = 'profile' in authUser && authUser.profile ? authUser.profile : undefined;
  const id = profile?.id || authUser.id || existingUser?.id || '';
  const email = profile?.email || authUser.email || existingUser?.email || '';
  const fullName =
    profile?.full_name ||
    ('user_metadata' in authUser ? getMetadataFullName(authUser) : '') ||
    existingUser?.fullName || email.split('@')[0] || 'Truth Matrix User';
  return {
    id,
    email,
    fullName,
    profilePicture:
      profile?.avatar_url ||
      ('user_metadata' in authUser ? authUser.user_metadata?.avatar_url : undefined) ||
      existingUser?.profilePicture,
    role: profile?.role || existingUser?.role || 'user',
    creditsRemaining: existingUser?.creditsRemaining ?? 10,
    totalAnalyses: existingUser?.totalAnalyses ?? 0,
    emailVerified: true,
    createdAt: profile?.created_at || existingUser?.createdAt || new Date().toISOString(),
  };
}

function challengeState(
  response: AuthChallengeResponse,
  email: string,
  fullName?: string
): PendingAuthChallenge {
  return {
    id: response.challenge_id,
    purpose: response.purpose,
    maskedDestination: response.masked_destination,
    expiresAt: Date.now() + response.expires_in * 1000,
    email,
    fullName,
  };
}

function errorDetails(error: unknown, fallback: string) {
  if (error instanceof ApiError) return { message: error.message, code: error.code || null };
  if (error instanceof Error) return { message: error.message, code: null };
  return { message: fallback, code: null };
}

function authenticatedState(response: AuthResponse, existingUser?: User | null) {
  return {
    accessToken: response.access_token,
    refreshToken: response.refresh_token,
    user: normalizeUser(response.user, existingUser),
    isAuthenticated: true,
    pendingChallenge: null,
    pendingPassword: null,
    captchaRequired: false,
    idleTimeoutSeconds: response.idle_timeout_seconds,
  };
}

const clearedSession = {
  user: null,
  accessToken: null,
  refreshToken: null,
  isAuthenticated: false,
  pendingChallenge: null,
  pendingPassword: null,
};

export const useAuthStore = create<AuthState>()((set, get) => ({
  ...clearedSession,
  isInitialized: false,
  isLoading: false,
  error: null,
  errorCode: null,
  message: null,
  captchaRequired: false,
  idleTimeoutSeconds: 900,

  initialize: async () => {
    const { accessToken } = get();
    if (!accessToken) {
      set({ isAuthenticated: false, isInitialized: true });
      return;
    }
    try {
      const profile = await getCurrentProfile(accessToken);
      set({ user: normalizeUser(profile, get().user), isAuthenticated: true, isInitialized: true });
    } catch {
      await get().logout('Your session has expired. Please sign in again.');
      set({ isInitialized: true });
    }
  },

  login: async (email, password, captchaToken) => {
    set({ isLoading: true, error: null, errorCode: null, message: null });
    try {
      const response = await loginUser(email, password, captchaToken);
      if (!('access_token' in response)) {
        set({
          pendingChallenge: challengeState(response, email),
          pendingPassword: password,
          isLoading: false,
          captchaRequired: false,
          message: `A verification code was sent to ${response.masked_destination}.`,
        });
        return 'mfa_required';
      }
      set({ ...authenticatedState(response, get().user), isLoading: false, error: null });
      return 'authenticated';
    } catch (error) {
      const details = errorDetails(error, 'Invalid email or password.');
      set({
        error: details.message,
        errorCode: details.code,
        captchaRequired: shouldRequireCaptcha(details.code, get().captchaRequired),
        isLoading: false,
      });
      return 'failed';
    }
  },

  register: async (data, captchaToken) => {
    set({ isLoading: true, error: null, errorCode: null, message: null });
    try {
      const response = await registerUser(data.fullName, data.email, data.password, captchaToken);
      set({
        pendingChallenge: challengeState(response, data.email, data.fullName),
        pendingPassword: data.password,
        isLoading: false,
        message: `A verification code was sent to ${response.masked_destination}.`,
      });
      return 'mfa_required';
    } catch (error) {
      const details = errorDetails(error, 'Could not create your account.');
      set({ error: details.message, errorCode: details.code, isLoading: false });
      return 'failed';
    }
  },

  verifyMfa: async (code) => {
    const { pendingChallenge, pendingPassword } = get();
    if (!pendingChallenge || !pendingPassword) {
      set({ error: 'The authentication challenge has expired. Please start again.' });
      return false;
    }
    set({ isLoading: true, error: null, errorCode: null });
    try {
      const response = await verifyMfaChallenge(
        pendingChallenge.id,
        code,
        pendingPassword,
        pendingChallenge.email,
        pendingChallenge.fullName
      );
      set({ ...authenticatedState(response, get().user), isLoading: false, message: null });
      return true;
    } catch (error) {
      const details = errorDetails(error, 'The verification code is invalid or expired.');
      const challengeCannotBeRetried = details.code === 'AUTHENTICATION_RESTART_REQUIRED';
      set({
        error: challengeCannotBeRetried
          ? 'That code was accepted, but the account could not be completed. Please sign in if this email is already registered.'
          : details.message,
        errorCode: details.code,
        isLoading: false,
        ...(challengeCannotBeRetried
          ? { pendingChallenge: null, pendingPassword: null, message: null }
          : {}),
      });
      return false;
    }
  },

  resendMfa: async (captchaToken) => {
    const pendingChallenge = get().pendingChallenge;
    if (!pendingChallenge) return false;
    set({ isLoading: true, error: null, errorCode: null });
    try {
      const response = await resendMfaChallenge(
        pendingChallenge.id,
        pendingChallenge.email,
        captchaToken
      );
      set({
        isLoading: false,
        message: response.message,
        pendingChallenge: {
          ...pendingChallenge,
          expiresAt: Date.now() + response.expires_in * 1000,
        },
      });
      return true;
    } catch (error) {
      const details = errorDetails(error, 'Could not resend the verification code.');
      set({ error: details.message, errorCode: details.code, isLoading: false });
      return false;
    }
  },

  cancelPendingChallenge: () => set({ pendingChallenge: null, pendingPassword: null, error: null, message: null }),

  refreshSession: async () => {
    const refreshToken = get().refreshToken;
    if (!refreshToken) return null;
    try {
      const response = await refreshUserSession(refreshToken);
      set({ ...authenticatedState(response, get().user), error: null });
      return response.access_token;
    } catch {
      await get().logout('Your session has expired. Please sign in again.');
      return null;
    }
  },

  logout: async (reason) => {
    const { accessToken, refreshToken } = get();
    set({ ...clearedSession, message: reason || null, error: null, errorCode: null });
    if (accessToken || refreshToken) {
      try {
        await logoutUser(accessToken, refreshToken);
      } catch {
        // Local cleanup is unconditional; server session will also hit its idle/absolute limit.
      }
    }
    localStorage.setItem('truth-matrix-logout-event', String(Date.now()));
    localStorage.removeItem('truth-matrix-logout-event');
  },

  clearLocalSession: (message) => set({ ...clearedSession, message: message || null }),

  updateProfile: async (data) => {
    const token = get().accessToken;
    if (!token) return;
    set({ isLoading: true, error: null });
    try {
      const profile = await updateCurrentProfile(token, { full_name: data.fullName, avatar_url: data.profilePicture ?? null });
      set({ user: normalizeUser(profile, get().user), isLoading: false, message: 'Profile updated.' });
    } catch (error) {
      set({ error: errorDetails(error, 'Could not update your profile.').message, isLoading: false });
    }
  },

  resetPassword: async (email, captchaToken) => {
    set({ isLoading: true, error: null, errorCode: null, message: null });
    try {
      const response = await requestPasswordReset(email, captchaToken);
      set({ isLoading: false, message: response.message });
    } catch (error) {
      const details = errorDetails(error, 'Could not request a password reset.');
      set({ error: details.message, errorCode: details.code, isLoading: false });
    }
  },

  clearError: () => set({ error: null, errorCode: null, message: null }),
}));

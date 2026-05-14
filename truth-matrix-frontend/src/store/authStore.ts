import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import {
  ApiError,
  getCurrentProfile,
  loginUser,
  refreshUserSession,
  registerUser,
  requestPasswordReset,
  updateCurrentProfile,
  type AuthResponse,
  type BackendProfile,
  type BackendUser,
} from '../api/deepfakeApi';

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

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  message: string | null;

  initialize: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  refreshSession: () => Promise<string | null>;
  logout: () => void;
  updateProfile: (data: Partial<User>) => Promise<void>;
  resetPassword: (email: string) => Promise<void>;
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

function normalizeUser(
  authUser: BackendUser | BackendProfile,
  existingUser?: User | null
): User {
  const profile =
    'profile' in authUser && authUser.profile ? authUser.profile : undefined;
  const id = profile?.id || authUser.id || existingUser?.id || '';
  const email = profile?.email || authUser.email || existingUser?.email || '';
  const fullName =
    profile?.full_name ||
    ('user_metadata' in authUser ? getMetadataFullName(authUser) : '') ||
    existingUser?.fullName ||
    email.split('@')[0] ||
    'Truth Matrix User';

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
    emailVerified: existingUser?.emailVerified ?? true,
    createdAt: profile?.created_at || existingUser?.createdAt || new Date().toISOString(),
  };
}

function authResponseToState(response: AuthResponse, existingUser?: User | null) {
  return {
    accessToken: response.access_token,
    refreshToken: response.refresh_token,
    user: normalizeUser(response.user, existingUser),
    isAuthenticated: Boolean(response.access_token),
  };
}

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError || error instanceof Error) {
    return error.message;
  }

  return fallback;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
      message: null,

      initialize: async () => {
        const { accessToken, refreshToken, user } = get();

        if (!accessToken) {
          set({ isAuthenticated: false });
          return;
        }

        try {
          const profile = await getCurrentProfile(accessToken);
          set({
            user: normalizeUser(profile, user),
            isAuthenticated: true,
            error: null,
          });
        } catch (error) {
          if (refreshToken) {
            await get().refreshSession();
            return;
          }

          set({
            user: null,
            accessToken: null,
            refreshToken: null,
            isAuthenticated: false,
            error: getErrorMessage(error, 'Please sign in again.'),
          });
        }
      },

      login: async (email, password) => {
        set({ isLoading: true, error: null, message: null });

        try {
          const response = await loginUser(email, password);

          if (!response.access_token) {
            set({
              isLoading: false,
              error:
                'Login succeeded but no access token was returned. Check Supabase email confirmation settings.',
            });
            return;
          }

          set({
            ...authResponseToState(response, get().user),
            isLoading: false,
            error: null,
            message: null,
          });
        } catch (error) {
          set({
            error: getErrorMessage(error, 'Invalid email or password.'),
            isLoading: false,
          });
        }
      },

      register: async (data) => {
        set({ isLoading: true, error: null, message: null });

        try {
          const response = await registerUser(
            data.fullName,
            data.email,
            data.password
          );

          if (!response.access_token) {
            set({
              user: normalizeUser(response.user),
              accessToken: null,
              refreshToken: null,
              isAuthenticated: false,
              isLoading: false,
              message:
                'Account created. Please confirm your email, then sign in.',
            });
            return;
          }

          set({
            ...authResponseToState(response, get().user),
            isLoading: false,
            error: null,
            message: 'Account created successfully.',
          });
        } catch (error) {
          set({
            error: getErrorMessage(error, 'Please fill in all fields correctly.'),
            isLoading: false,
          });
        }
      },

      refreshSession: async () => {
        const refreshToken = get().refreshToken;

        if (!refreshToken) {
          set({
            user: null,
            accessToken: null,
            isAuthenticated: false,
            error: 'Please sign in again.',
          });
          return null;
        }

        try {
          const response = await refreshUserSession(refreshToken);

          if (!response.access_token) {
            throw new Error('Session refresh did not return an access token.');
          }

          set({
            ...authResponseToState(response, get().user),
            error: null,
          });
          return response.access_token;
        } catch (error) {
          set({
            user: null,
            accessToken: null,
            refreshToken: null,
            isAuthenticated: false,
            error: getErrorMessage(error, 'Please sign in again.'),
          });
          return null;
        }
      },

      logout: () => {
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          isAuthenticated: false,
          error: null,
          message: null,
        });
      },

      updateProfile: async (data) => {
        const token = get().accessToken;

        if (!token) {
          set({ error: 'Please sign in again.' });
          return;
        }

        set({ isLoading: true, error: null, message: null });

        try {
          const profile = await updateCurrentProfile(token, {
            full_name: data.fullName,
            avatar_url: data.profilePicture ?? null,
          });

          set({
            user: normalizeUser(profile, get().user),
            isLoading: false,
            message: 'Profile updated.',
          });
        } catch (error) {
          set({
            error: getErrorMessage(error, 'Could not update your profile.'),
            isLoading: false,
          });
        }
      },

      resetPassword: async (email) => {
        set({ isLoading: true, error: null, message: null });

        try {
          await requestPasswordReset(email);
          set({
            isLoading: false,
            message: 'Password reset email sent.',
          });
        } catch (error) {
          set({
            error: getErrorMessage(error, 'Please enter a valid email address.'),
            isLoading: false,
          });
        }
      },

      clearError: () => set({ error: null, message: null }),
    }),
    {
      name: 'truth-matrix-auth',
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);

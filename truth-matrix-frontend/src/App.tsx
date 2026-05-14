import React, { useEffect } from 'react';
import {
  BrowserRouter as Router,
  Navigate,
  Route,
  Routes,
  useNavigate,
} from 'react-router-dom';
import { Toaster, toast } from 'sonner';
import { Navbar } from './components/common/Navbar';
import { Footer } from './components/common/Footer';
import { UploadModal } from './components/upload/UploadModal';
import { useAuthStore } from './store/authStore';
import { useUIStore } from './store/uiStore';
import { useAnalysisStore } from './store/analysisStore';
import { ROUTES } from './utils/constants';
import { LandingPage } from './pages/LandingPage';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { ForgotPasswordPage } from './pages/ForgotPasswordPage';
import { DashboardPage } from './pages/DashboardPage';
import { AnalysisPage } from './pages/AnalysisPage';
import { ResultsPage } from './pages/ResultsPage';
import { HistoryPage } from './pages/HistoryPage';
import { ProfilePage } from './pages/ProfilePage';
import { SettingsPage } from './pages/SettingsPage';
import { ApiDocsPage } from './pages/ApiDocsPage';
import { AboutPage } from './pages/AboutPage';
import { HelpPage } from './pages/HelpPage';
import { AdminDashboardPage } from './pages/AdminDashboardPage';
import { NotFoundPage } from './pages/NotFoundPage';

const ProtectedRoute = ({
  children,
  requireAdmin = false,
}: {
  children: React.ReactNode;
  requireAdmin?: boolean;
}) => {
  const { isAuthenticated, user } = useAuthStore();

  if (!isAuthenticated) {
    return <Navigate to={ROUTES.LOGIN} replace />;
  }

  if (requireAdmin && user?.role !== 'admin') {
    return <Navigate to={ROUTES.DASHBOARD} replace />;
  }

  return <>{children}</>;
};

function AppShell() {
  const navigate = useNavigate();
  const { theme } = useUIStore();
  const { initialize, isAuthenticated, accessToken } = useAuthStore();
  const { fetchHistory, startUpload, analyzeUrl } = useAnalysisStore();

  useEffect(() => {
    const root = document.documentElement;

    if (theme === 'system') {
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      root.classList.toggle('dark', prefersDark);
    } else {
      root.classList.toggle('dark', theme === 'dark');
    }
  }, [theme]);

  useEffect(() => {
    void initialize();
  }, [initialize]);

  useEffect(() => {
    if (isAuthenticated && accessToken) {
      void fetchHistory();
    }
  }, [accessToken, fetchHistory, isAuthenticated]);

  const handleFileSelect = async (file: File) => {
    try {
      await startUpload(file);
      navigate(ROUTES.RESULTS);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Analysis failed.');
    }
  };

  const handleUrlSubmit = async (url: string) => {
    try {
      await analyzeUrl(url);
      navigate(ROUTES.RESULTS);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'URL analysis failed.');
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-white dark:bg-navy-900 text-gray-900 dark:text-white transition-colors duration-300">
      <Toaster
        position="top-right"
        theme={theme === 'system' ? undefined : theme}
        richColors
        closeButton
        toastOptions={{
          style: {
            background: theme === 'dark' ? '#0f1629' : '#ffffff',
            border:
              theme === 'dark' ? '1px solid #1a2342' : '1px solid #e2e8f0',
            color: theme === 'dark' ? '#f8fafc' : '#0f172a',
          },
        }}
      />

      <Navbar />

      <main className="flex-grow relative z-10">
        <Routes>
          <Route path={ROUTES.HOME} element={<LandingPage />} />
          <Route path={ROUTES.LOGIN} element={<LoginPage />} />
          <Route path={ROUTES.REGISTER} element={<RegisterPage />} />
          <Route path={ROUTES.FORGOT_PASSWORD} element={<ForgotPasswordPage />} />
          <Route path={ROUTES.ABOUT} element={<AboutPage />} />
          <Route path={ROUTES.HELP} element={<HelpPage />} />
          <Route path={ROUTES.API_DOCS} element={<ApiDocsPage />} />

          <Route
            path={ROUTES.DASHBOARD}
            element={
              <ProtectedRoute>
                <DashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path={ROUTES.ANALYZE}
            element={
              <ProtectedRoute>
                <AnalysisPage />
              </ProtectedRoute>
            }
          />
          <Route
            path={ROUTES.RESULTS}
            element={
              <ProtectedRoute>
                <ResultsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path={ROUTES.HISTORY}
            element={
              <ProtectedRoute>
                <HistoryPage />
              </ProtectedRoute>
            }
          />
          <Route
            path={ROUTES.PROFILE}
            element={
              <ProtectedRoute>
                <ProfilePage />
              </ProtectedRoute>
            }
          />
          <Route
            path={ROUTES.SETTINGS}
            element={
              <ProtectedRoute>
                <SettingsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path={ROUTES.ADMIN}
            element={
              <ProtectedRoute requireAdmin>
                <AdminDashboardPage />
              </ProtectedRoute>
            }
          />

          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>

      <Footer />

      <UploadModal onFileSelect={handleFileSelect} onUrlSubmit={handleUrlSubmit} />
    </div>
  );
}

export function App() {
  return (
    <Router>
      <AppShell />
    </Router>
  );
}

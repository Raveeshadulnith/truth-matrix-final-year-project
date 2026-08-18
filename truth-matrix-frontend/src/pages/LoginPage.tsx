import React, { useCallback, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ShieldCheckIcon, MailIcon, LockIcon } from 'lucide-react';
import { Button } from '../components/common/Button';
import { Input } from '../components/common/Input';
import { Card } from '../components/common/Card';
import { useAuthStore } from '../store/authStore';
import { ROUTES } from '../utils/constants';
import { RecaptchaCheckbox } from '../components/auth/RecaptchaCheckbox';
import { MfaChallengePanel } from '../components/auth/MfaChallengePanel';
export function LoginPage() {
  const navigate = useNavigate();
  const { login, isLoading, error, clearError, pendingChallenge } = useAuthStore();
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const [captchaReset, setCaptchaReset] = useState(0);
  const captchaCallback = useCallback((token: string | null) => setCaptchaToken(token), []);
  const [formData, setFormData] = useState({
    email: '',
    password: ''
  });
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const validateForm = () => {
    const errors: Record<string, string> = {};
    if (!formData.email) {
      errors.email = 'Email is required';
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      errors.email = 'Please enter a valid email';
    }
    if (!formData.password) {
      errors.password = 'Password is required';
    } else if (formData.password.length < 6) {
      errors.password = 'Password must be at least 6 characters';
    }
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();
    if (!validateForm()) return;
    if (!captchaToken) {
      setFormErrors((current) => ({ ...current, captcha: 'Complete the CAPTCHA before signing in.' }));
      return;
    }
    const result = await login(formData.email, formData.password, captchaToken);
    setCaptchaToken(null);
    setCaptchaReset((value) => value + 1);
    if (result === 'authenticated') {
      navigate(ROUTES.DASHBOARD);
    }
  };
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
    // Clear field error on change
    if (formErrors[name]) {
      setFormErrors((prev) => ({
        ...prev,
        [name]: ''
      }));
    }
  };
  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <motion.div
          initial={{
            opacity: 0,
            y: 20
          }}
          animate={{
            opacity: 1,
            y: 0
          }}
          transition={{
            duration: 0.5
          }}>

          {/* Logo */}
          <div className="text-center mb-8">
            <Link
              to={ROUTES.HOME}
              className="inline-flex items-center gap-2 mb-4">

              <ShieldCheckIcon className="w-10 h-10 text-neon-cyan" />
              <span className="text-2xl font-bold gradient-text">
                TruthMatrix
              </span>
            </Link>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              Welcome back
            </h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Sign in to your account to continue
            </p>
          </div>

          <Card variant="glass">
            {pendingChallenge ? (
              <MfaChallengePanel onSuccess={() => navigate(ROUTES.DASHBOARD)} />
            ) : (
            <form onSubmit={handleSubmit} className="p-6 space-y-5">
              {/* Error Message */}
              {error &&
              <motion.div
                initial={{
                  opacity: 0,
                  y: -10
                }}
                animate={{
                  opacity: 1,
                  y: 0
                }}
                className="p-4 rounded-xl bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">

                  <p className="text-sm text-red-600 dark:text-red-400">
                    {error}
                  </p>
                </motion.div>
              }

              {/* Email */}
              <Input
                label="Email Address"
                name="email"
                type="email"
                placeholder="you@example.com"
                value={formData.email}
                onChange={handleChange}
                error={formErrors.email}
                leftIcon={<MailIcon className="w-5 h-5" />}
                autoComplete="email" />


              {/* Password */}
              <Input
                label="Password"
                name="password"
                type="password"
                placeholder="••••••••"
                value={formData.password}
                onChange={handleChange}
                error={formErrors.password}
                leftIcon={<LockIcon className="w-5 h-5" />}
                autoComplete="current-password" />


              {/* Password recovery */}
              <div className="flex items-center justify-end">
                <Link
                  to={ROUTES.FORGOT_PASSWORD}
                  className="text-sm text-neon-cyan hover:underline font-medium">

                  Forgot password?
                </Link>
              </div>

              <RecaptchaCheckbox onToken={captchaCallback} resetKey={captchaReset} />
              {formErrors.captcha && <p className="text-sm text-neon-red">{formErrors.captcha}</p>}

              {/* Submit Button */}
              <Button
                type="submit"
                variant="primary"
                size="lg"
                className="w-full"
                isLoading={isLoading}
                disabled={!captchaToken}>

                Sign In
              </Button>
            </form>
            )}
          </Card>

          {/* Sign Up Link */}
          <p className="text-center mt-6 text-gray-600 dark:text-gray-400">
            Don't have an account?{' '}
            <Link
              to={ROUTES.REGISTER}
              className="text-neon-cyan hover:underline font-medium">

              Sign up for free
            </Link>
          </p>
        </motion.div>
      </div>
    </div>);

}

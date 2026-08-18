import React, { useCallback, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ShieldCheckIcon,
  MailIcon,
  LockIcon,
  UserIcon,
  CheckIcon,
  XIcon } from
'lucide-react';
import { Button } from '../components/common/Button';
import { Input } from '../components/common/Input';
import { Card } from '../components/common/Card';
import { useAuthStore } from '../store/authStore';
import { ROUTES } from '../utils/constants';
import { RecaptchaCheckbox } from '../components/auth/RecaptchaCheckbox';
import { MfaChallengePanel } from '../components/auth/MfaChallengePanel';
export function RegisterPage() {
  const navigate = useNavigate();
  const { register, isLoading, error, clearError, pendingChallenge } = useAuthStore();
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const [captchaReset, setCaptchaReset] = useState(0);
  const captchaCallback = useCallback((token: string | null) => setCaptchaToken(token), []);
  const [formData, setFormData] = useState({
    fullName: '',
    email: '',
    password: '',
    confirmPassword: '',
    agreeTerms: false
  });
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const passwordRequirements = [
  {
    label: 'At least 8 characters',
    met: formData.password.length >= 8
  },
  {
    label: 'Contains uppercase letter',
    met: /[A-Z]/.test(formData.password)
  },
  {
    label: 'Contains lowercase letter',
    met: /[a-z]/.test(formData.password)
  },
  {
    label: 'Contains number',
    met: /[0-9]/.test(formData.password)
  }];

  const passwordStrength = passwordRequirements.filter((r) => r.met).length;
  const validateForm = () => {
    const errors: Record<string, string> = {};
    if (!formData.fullName.trim()) {
      errors.fullName = 'Full name is required';
    }
    if (!formData.email) {
      errors.email = 'Email is required';
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      errors.email = 'Please enter a valid email';
    }
    if (!formData.password) {
      errors.password = 'Password is required';
    } else if (formData.password.length < 8) {
      errors.password = 'Password must be at least 8 characters';
    } else if (!/[A-Z]/.test(formData.password) || !/[a-z]/.test(formData.password) || !/[0-9]/.test(formData.password)) {
      errors.password = 'Password must contain uppercase, lowercase, and numeric characters';
    }
    if (formData.password !== formData.confirmPassword) {
      errors.confirmPassword = 'Passwords do not match';
    }
    if (!formData.agreeTerms) {
      errors.agreeTerms = 'You must agree to the terms';
    }
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();
    if (!validateForm()) return;
    if (!captchaToken) {
      setFormErrors((current) => ({ ...current, captcha: 'Bot verification is still loading. Please try again.' }));
      return;
    }
    await register({
      fullName: formData.fullName,
      email: formData.email,
      password: formData.password
    }, captchaToken);
    setCaptchaToken(null);
    setCaptchaReset((value) => value + 1);
  };
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
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
              Create your account
            </h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Start detecting deepfakes in minutes
            </p>
          </div>

          <Card variant="glass">
            {pendingChallenge ? (
              <MfaChallengePanel onSuccess={() => navigate(ROUTES.DASHBOARD)} />
            ) : (
            <form onSubmit={handleSubmit} className="p-6 space-y-5">
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

              {/* Full Name */}
              <Input
                label="Full Name"
                name="fullName"
                type="text"
                placeholder="John Doe"
                value={formData.fullName}
                onChange={handleChange}
                error={formErrors.fullName}
                leftIcon={<UserIcon className="w-5 h-5" />}
                autoComplete="name" />


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
              <div>
                <Input
                  label="Password"
                  name="password"
                  type="password"
                  placeholder="••••••••"
                  value={formData.password}
                  onChange={handleChange}
                  error={formErrors.password}
                  leftIcon={<LockIcon className="w-5 h-5" />}
                  autoComplete="new-password" />


                {/* Password Strength */}
                {formData.password &&
                <div className="mt-3 space-y-2">
                    <div className="flex gap-1">
                      {[1, 2, 3, 4].map((level) =>
                    <div
                      key={level}
                      className={`h-1.5 flex-1 rounded-full transition-colors ${passwordStrength >= level ? passwordStrength <= 1 ? 'bg-red-500' : passwordStrength <= 2 ? 'bg-orange-500' : passwordStrength <= 3 ? 'bg-yellow-500' : 'bg-green-500' : 'bg-gray-200 dark:bg-navy-700'}`} />

                    )}
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      {passwordRequirements.map((req) =>
                    <div
                      key={req.label}
                      className={`flex items-center gap-1.5 text-xs ${req.met ? 'text-green-600 dark:text-green-400' : 'text-gray-400'}`}>

                          {req.met ?
                      <CheckIcon className="w-3.5 h-3.5" /> :

                      <XIcon className="w-3.5 h-3.5" />
                      }
                          {req.label}
                        </div>
                    )}
                    </div>
                  </div>
                }
              </div>

              {/* Confirm Password */}
              <Input
                label="Confirm Password"
                name="confirmPassword"
                type="password"
                placeholder="••••••••"
                value={formData.confirmPassword}
                onChange={handleChange}
                error={formErrors.confirmPassword}
                leftIcon={<LockIcon className="w-5 h-5" />}
                autoComplete="new-password" />


              {/* Terms */}
              <div>
                <label className="flex items-start gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    name="agreeTerms"
                    checked={formData.agreeTerms}
                    onChange={handleChange}
                    className="w-4 h-4 mt-0.5 rounded border-gray-300 text-neon-cyan focus:ring-neon-cyan" />

                  <span className="text-sm text-gray-600 dark:text-gray-400">
                    I agree to the{' '}
                    <Link to="#" className="text-neon-cyan hover:underline">
                      Terms of Service
                    </Link>{' '}
                    and{' '}
                    <Link to="#" className="text-neon-cyan hover:underline">
                      Privacy Policy
                    </Link>
                  </span>
                </label>
                {formErrors.agreeTerms &&
                <p className="mt-1 text-sm text-red-500">
                    {formErrors.agreeTerms}
                  </p>
                }
              </div>

              <RecaptchaCheckbox onToken={captchaCallback} resetKey={captchaReset} />
              {formErrors.captcha && <p className="text-sm text-neon-red">{formErrors.captcha}</p>}

              {/* Submit */}
              <Button
                type="submit"
                variant="primary"
                size="lg"
                className="w-full"
                isLoading={isLoading}
                disabled={!captchaToken}>

                Create Account
              </Button>
            </form>
            )}
          </Card>

          {/* Sign In Link */}
          <p className="text-center mt-6 text-gray-600 dark:text-gray-400">
            Already have an account?{' '}
            <Link
              to={ROUTES.LOGIN}
              className="text-neon-cyan hover:underline font-medium">

              Sign in
            </Link>
          </p>
        </motion.div>
      </div>
    </div>);

}

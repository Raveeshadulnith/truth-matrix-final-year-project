import React, { useCallback, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ShieldCheckIcon,
  MailIcon,
  ArrowLeftIcon,
  CheckCircleIcon } from
'lucide-react';
import { Button } from '../components/common/Button';
import { Input } from '../components/common/Input';
import { Card } from '../components/common/Card';
import { useAuthStore } from '../store/authStore';
import { ROUTES } from '../utils/constants';
import { RecaptchaCheckbox } from '../components/auth/RecaptchaCheckbox';
export function ForgotPasswordPage() {
  const { resetPassword, isLoading, error, clearError } = useAuthStore();
  const [email, setEmail] = useState('');
  const [emailError, setEmailError] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const [captchaReset, setCaptchaReset] = useState(0);
  const captchaCallback = useCallback((token: string | null) => setCaptchaToken(token), []);
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();
    setEmailError('');
    if (!email) {
      setEmailError('Email is required');
      return;
    }
    if (!/\S+@\S+\.\S+/.test(email)) {
      setEmailError('Please enter a valid email');
      return;
    }
    if (!captchaToken) {
      setEmailError('Bot verification is still loading. Please try again.');
      return;
    }
    await resetPassword(email, captchaToken);
    setCaptchaToken(null);
    setCaptchaReset((value) => value + 1);
    const { error: resetError } = useAuthStore.getState();
    if (!resetError) {
      setSubmitted(true);
    }
  };
  if (submitted) {
    return (
      <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-md">
          <motion.div
            initial={{
              opacity: 0,
              scale: 0.95
            }}
            animate={{
              opacity: 1,
              scale: 1
            }}
            transition={{
              duration: 0.5
            }}>

            <Card variant="glass" className="text-center">
              <div className="p-8">
                <div className="w-16 h-16 mx-auto rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center mb-6">
                  <CheckCircleIcon className="w-8 h-8 text-green-600 dark:text-green-400" />
                </div>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
                  Check your email
                </h1>
                <p className="text-gray-600 dark:text-gray-400 mb-6">
                  If an account exists, reset instructions will be sent to{' '}
                  <span className="font-medium text-gray-900 dark:text-white">
                    {email}
                  </span>
                </p>
                <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
                  Didn't receive the email? Check your spam folder or{' '}
                  <button
                    onClick={() => setSubmitted(false)}
                    className="text-neon-cyan hover:underline">

                    try again
                  </button>
                </p>
                <Link to={ROUTES.LOGIN}>
                  <Button variant="primary" className="w-full">
                    Back to Sign In
                  </Button>
                </Link>
              </div>
            </Card>
          </motion.div>
        </div>
      </div>);

  }
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
              Forgot your password?
            </h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              No worries, we'll send you reset instructions.
            </p>
          </div>

          <Card variant="glass">
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

              <Input
                label="Email Address"
                name="email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  setEmailError('');
                }}
                error={emailError}
                leftIcon={<MailIcon className="w-5 h-5" />}
                autoComplete="email" />

              <RecaptchaCheckbox onToken={captchaCallback} resetKey={captchaReset} />


              <Button
                type="submit"
                variant="primary"
                size="lg"
                className="w-full"
                isLoading={isLoading}
                disabled={!captchaToken}>

                Send Reset Link
              </Button>
            </form>
          </Card>

          <div className="text-center mt-6">
            <Link
              to={ROUTES.LOGIN}
              className="inline-flex items-center gap-2 text-gray-600 dark:text-gray-400 hover:text-neon-cyan transition-colors">

              <ArrowLeftIcon className="w-4 h-4" />
              Back to Sign In
            </Link>
          </div>
        </motion.div>
      </div>
    </div>);

}

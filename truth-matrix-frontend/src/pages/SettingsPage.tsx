import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  BellIcon,
  MonitorIcon,
  ShieldIcon,
  KeyIcon,
  } from
'lucide-react';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { Badge } from '../components/common/Badge';
import { ThemeToggle } from '../components/common/ThemeToggle';
import { Input } from '../components/common/Input';
import { useAuthStore } from '../store/authStore';
import { disableMfa, getMfaStatus, startMfaStepUp, verifyMfaStepUp, type MfaStatusResponse } from '../api/deepfakeApi';
import { isCompleteOtp, normalizeOtpCode } from '../utils/authSecurity';
export function SettingsPage() {
  const { user, accessToken } = useAuthStore();
  const [mfaStatus, setMfaStatus] = useState<MfaStatusResponse | null>(null);
  const [securityStage, setSecurityStage] = useState<'idle' | 'password' | 'code'>('idle');
  const [securityPassword, setSecurityPassword] = useState('');
  const [securityCode, setSecurityCode] = useState('');
  const [stepUpChallenge, setStepUpChallenge] = useState('');
  const [securityMessage, setSecurityMessage] = useState('');
  const [securityBusy, setSecurityBusy] = useState(false);

  useEffect(() => {
    if (accessToken) {
      void getMfaStatus(accessToken).then(setMfaStatus).catch(() => setSecurityMessage('Could not load MFA status.'));
    }
  }, [accessToken]);

  const beginDisable = async () => {
    if (!accessToken) return;
    setSecurityBusy(true);
    setSecurityMessage('');
    try {
      const challenge = await startMfaStepUp(accessToken, securityPassword);
      setStepUpChallenge(challenge.challenge_id);
      setSecurityPassword('');
      setSecurityStage('code');
      setSecurityMessage(`A fresh verification code was sent to ${challenge.masked_destination}.`);
    } catch (error) {
      setSecurityMessage(error instanceof Error ? error.message : 'Verification failed.');
    } finally {
      setSecurityBusy(false);
    }
  };

  const finishDisable = async () => {
    if (!accessToken) return;
    setSecurityBusy(true);
    try {
      const verified = await verifyMfaStepUp(accessToken, stepUpChallenge, securityCode);
      await disableMfa(accessToken, verified.step_up_token);
      setMfaStatus((current) => current ? { ...current, mfa_enabled: false } : current);
      setSecurityStage('idle');
      setSecurityCode('');
      setSecurityMessage('MFA was disabled after recent password and MFA verification.');
    } catch (error) {
      setSecurityMessage(error instanceof Error ? error.message : 'Verification failed.');
    } finally {
      setSecurityBusy(false);
    }
  };
  return (
    <div className="min-h-screen py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto space-y-8">
        <motion.div
          initial={{
            opacity: 0,
            y: 20
          }}
          animate={{
            opacity: 1,
            y: 0
          }}>

          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white mb-2">
            Settings
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Manage your app preferences and integrations
          </p>
        </motion.div>

        {/* Appearance */}
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
            delay: 0.1
          }}>

          <Card variant="default">
            <div className="p-6">
              <div className="flex items-center gap-3 mb-6">
                <div className="p-2 rounded-lg bg-gray-100 dark:bg-navy-800">
                  <MonitorIcon className="w-5 h-5 text-gray-600 dark:text-gray-400" />
                </div>
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Appearance
                </h2>
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-medium text-gray-900 dark:text-white">
                    Theme
                  </h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    Select your preferred color theme
                  </p>
                </div>
                <ThemeToggle showLabel />
              </div>
            </div>
          </Card>
        </motion.div>

        {/* Account security */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
          <Card variant="default">
            <div className="p-6">
              <div className="flex items-center gap-3 mb-5">
                <div className="p-2 rounded-lg bg-neon-cyan/10"><ShieldIcon className="w-5 h-5 text-neon-cyan" /></div>
                <div>
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Multi-factor authentication</h2>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Email security code protection for sign-in.</p>
                </div>
                <Badge variant={!mfaStatus ? 'default' : mfaStatus.mfa_enabled ? 'success' : 'warning'} size="sm">
                  {!mfaStatus ? 'Loading' : mfaStatus.mfa_enabled ? 'Enabled' : 'Disabled'}
                </Badge>
              </div>
              {mfaStatus?.required_by_policy && (
                <p className="rounded-lg bg-neon-cyan/10 p-3 text-sm text-gray-700 dark:text-gray-300">MFA is required by the Truth Matrix security policy and cannot be disabled.</p>
              )}
              {securityMessage && <p role="status" className="my-3 text-sm text-gray-600 dark:text-gray-300">{securityMessage}</p>}
              {mfaStatus?.disable_allowed && securityStage === 'idle' && (
                <Button variant="danger" onClick={() => setSecurityStage('password')}>Disable MFA</Button>
              )}
              {securityStage === 'password' && (
                <div className="space-y-3">
                  <Input label="Current password" type="password" autoComplete="current-password" value={securityPassword} onChange={(event) => setSecurityPassword(event.target.value)} />
                  <Button variant="danger" isLoading={securityBusy} disabled={!securityPassword} onClick={beginDisable}>Verify password</Button>
                </div>
              )}
              {securityStage === 'code' && (
                <div className="space-y-3">
                  <Input label="Fresh MFA code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={securityCode} onChange={(event) => setSecurityCode(normalizeOtpCode(event.target.value))} />
                  <Button variant="danger" isLoading={securityBusy} disabled={!isCompleteOtp(securityCode)} onClick={finishDisable}>Confirm MFA removal</Button>
                </div>
              )}
            </div>
          </Card>
        </motion.div>

        {/* Notifications */}
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
            delay: 0.2
          }}>

          <Card variant="default">
            <div className="p-6">
              <div className="flex items-center gap-3 mb-6">
                <div className="p-2 rounded-lg bg-gray-100 dark:bg-navy-800">
                  <BellIcon className="w-5 h-5 text-gray-600 dark:text-gray-400" />
                </div>
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Notifications
                </h2>
              </div>

              <div className="space-y-4">
                {[
                {
                  id: 'email-alerts',
                  label: 'Email Alerts',
                  desc: 'Receive analysis results via email'
                },
                {
                  id: 'browser-notif',
                  label: 'Browser Notifications',
                  desc: 'Get notified when analysis completes'
                },
                {
                  id: 'marketing',
                  label: 'Marketing Updates',
                  desc: 'Receive news and feature updates'
                }].
                map((item) =>
                <div
                  key={item.id}
                  className="flex items-center justify-between">

                    <div>
                      <h3 className="font-medium text-gray-900 dark:text-white">
                        {item.label}
                      </h3>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        {item.desc}
                      </p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                      type="checkbox"
                      className="sr-only peer"
                      defaultChecked={item.id !== 'marketing'} />

                      <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-neon-cyan/20 dark:peer-focus:ring-neon-cyan/20 rounded-full peer dark:bg-navy-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-neon-cyan"></div>
                    </label>
                  </div>
                )}
              </div>
            </div>
          </Card>
        </motion.div>

        {/* API Keys */}
        {user?.role !== 'user' &&
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
            delay: 0.3
          }}>

            <Card variant="default">
              <div className="p-6">
                <div className="flex items-center gap-3 mb-6">
                  <div className="p-2 rounded-lg bg-gray-100 dark:bg-navy-800">
                    <KeyIcon className="w-5 h-5 text-gray-600 dark:text-gray-400" />
                  </div>
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                    API Access
                  </h2>
                </div>

                <div className="space-y-4">
                  <div className="p-4 rounded-xl bg-gray-50 dark:bg-navy-900/50 border border-gray-200 dark:border-navy-700">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-medium text-gray-900 dark:text-white">
                        Production Key
                      </span>
                      <Badge variant="success" size="sm">
                        Active
                      </Badge>
                    </div>
                    <div className="flex items-center gap-2">
                      <code className="flex-1 p-2 rounded bg-gray-200 dark:bg-navy-800 text-sm text-gray-600 dark:text-gray-400 font-mono">
                        dg_live_**********************
                      </code>
                      <Button variant="secondary" size="sm">
                        Reveal
                      </Button>
                    </div>
                  </div>
                  <Button variant="secondary" className="w-full border-dashed">
                    Generate New API Key
                  </Button>
                </div>
              </div>
            </Card>
          </motion.div>
        }

        {/* Danger Zone */}
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
            delay: 0.4
          }}>

          <Card
            variant="bordered"
            className="border-red-200 dark:border-red-900/50">

            <div className="p-6">
              <h2 className="text-lg font-semibold text-red-600 dark:text-red-400 mb-4">
                Danger Zone
              </h2>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <h3 className="font-medium text-gray-900 dark:text-white">
                    Delete Account
                  </h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    Permanently delete your account and all data
                  </p>
                </div>
                <Button variant="danger">Delete Account</Button>
              </div>
            </div>
          </Card>
        </motion.div>
      </div>
    </div>);

}

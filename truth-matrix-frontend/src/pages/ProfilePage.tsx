import React, { useState } from 'react';
import { motion } from 'framer-motion';
import {
  UserIcon,
  MailIcon,
  CameraIcon,
  ShieldCheckIcon,
  KeyIcon } from
'lucide-react';
import { Button } from '../components/common/Button';
import { Input } from '../components/common/Input';
import { Card } from '../components/common/Card';
import { useAuthStore } from '../store/authStore';
export function ProfilePage() {
  const { user, updateProfile, isLoading, error } = useAuthStore();
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState({
    fullName: user?.fullName || '',
    email: user?.email || ''
  });
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await updateProfile({ fullName: formData.fullName });
    setIsEditing(false);
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
            Profile Settings
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Manage your account details and preferences
          </p>
        </motion.div>

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
            <div className="p-6 sm:p-8">
              {/* Profile Picture */}
              <div className="flex flex-col sm:flex-row items-center gap-6 mb-8 pb-8 border-b border-gray-200 dark:border-navy-700">
                <div className="relative">
                  {user?.profilePicture ?
                  <img
                    src={user.profilePicture}
                    alt={user.fullName}
                    className="w-24 h-24 rounded-full object-cover ring-4 ring-gray-50 dark:ring-navy-900" /> :


                  <div className="w-24 h-24 rounded-full bg-gradient-to-br from-neon-cyan to-neon-violet flex items-center justify-center ring-4 ring-gray-50 dark:ring-navy-900">
                      <UserIcon className="w-10 h-10 text-white" />
                    </div>
                  }
                  <button className="absolute bottom-0 right-0 p-2 rounded-full bg-white dark:bg-navy-700 shadow-lg border border-gray-200 dark:border-navy-600 text-gray-600 dark:text-gray-300 hover:text-neon-cyan transition-colors">
                    <CameraIcon className="w-4 h-4" />
                  </button>
                </div>
                <div className="text-center sm:text-left">
                  <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                    {user?.fullName}
                  </h2>
                  <p className="text-gray-500 dark:text-gray-400 mb-2">
                    {user?.email}
                  </p>
                  <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-neon-cyan/10 text-neon-cyan text-xs font-semibold uppercase tracking-wider">
                    <ShieldCheckIcon className="w-3.5 h-3.5" />
                    {user?.role} Plan
                  </div>
                </div>
              </div>

              {/* Personal Info Form */}
              <form onSubmit={handleSubmit} className="space-y-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                    Personal Information
                  </h3>
                  {!isEditing &&
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setIsEditing(true)}>

                      Edit
                    </Button>
                  }
                </div>

                {error &&
                <p className="text-sm text-red-500">
                    {error}
                  </p>
                }

                <div className="grid sm:grid-cols-2 gap-6">
                  <Input
                    label="Full Name"
                    value={formData.fullName}
                    onChange={(e) =>
                    setFormData({
                      ...formData,
                      fullName: e.target.value
                    })
                    }
                    disabled={!isEditing}
                    leftIcon={<UserIcon className="w-5 h-5" />} />

                  <Input
                    label="Email Address"
                    type="email"
                    value={formData.email}
                    onChange={(e) =>
                    setFormData({
                      ...formData,
                      email: e.target.value
                    })
                    }
                    disabled
                    leftIcon={<MailIcon className="w-5 h-5" />} />

                </div>

                {isEditing &&
                <div className="flex justify-end gap-3 pt-4">
                    <Button
                    type="button"
                    variant="ghost"
                    onClick={() => {
                      setIsEditing(false);
                      setFormData({
                        fullName: user?.fullName || '',
                        email: user?.email || ''
                      });
                    }}>

                      Cancel
                    </Button>
                    <Button type="submit" variant="primary" isLoading={isLoading}>
                      Save Changes
                    </Button>
                  </div>
                }
              </form>
            </div>
          </Card>
        </motion.div>

        {/* Security Section */}
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
            <div className="p-6 sm:p-8">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-6">
                Security
              </h3>

              <div className="space-y-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-gray-200 dark:border-navy-700">
                  <div>
                    <h4 className="font-medium text-gray-900 dark:text-white">
                      Password
                    </h4>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      Last changed 3 months ago
                    </p>
                  </div>
                  <Button
                    variant="secondary"
                    leftIcon={<KeyIcon className="w-4 h-4" />}>

                    Change Password
                  </Button>
                </div>

                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <h4 className="font-medium text-gray-900 dark:text-white">
                      Two-Factor Authentication
                    </h4>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      Add an extra layer of security to your account
                    </p>
                  </div>
                  <Button variant="primary">Enable 2FA</Button>
                </div>
              </div>
            </div>
          </Card>
        </motion.div>
      </div>
    </div>);

}

import React from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  UploadCloudIcon,
  SparklesIcon,
  BellIcon } from
'lucide-react';
import { Button } from '../components/common/Button';
import { Card } from '../components/common/Card';
import { StatsCards } from '../components/dashboard/StatsCards';
import { RecentAnalyses } from '../components/dashboard/RecentAnalyses';
import { ActivityChart } from '../components/dashboard/ActivityChart';
import { useAuthStore } from '../store/authStore';
import { useUIStore } from '../store/uiStore';
import { ROUTES } from '../utils/constants';
export function DashboardPage() {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { openModal } = useUIStore();
  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 18) return 'Good afternoon';
    return 'Good evening';
  };
  return (
    <div className="min-h-screen py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Welcome Header */}
        <motion.div
          initial={{
            opacity: 0,
            y: 20
          }}
          animate={{
            opacity: 1,
            y: 0
          }}
          className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">

          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white">
              {getGreeting()}, {user?.fullName?.split(' ')[0] || 'User'}! 👋
            </h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Here's what's happening with your deepfake detection
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button className="relative p-2 rounded-xl bg-gray-100 dark:bg-navy-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-navy-700 transition-colors">
              <BellIcon className="w-5 h-5" />
              <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-neon-red" />
            </button>
            <Button
              variant="primary"
              leftIcon={<UploadCloudIcon className="w-5 h-5" />}
              onClick={() => navigate(ROUTES.ANALYZE)}>

              New Analysis
            </Button>
          </div>
        </motion.div>

        {/* Stats Cards */}
        <StatsCards />

        {/* Main Content Grid */}
        <div className="grid lg:grid-cols-3 gap-6 lg:gap-8">
          {/* Recent Analyses - Takes 2 columns */}
          <div className="lg:col-span-2">
            <RecentAnalyses />
          </div>

          {/* Right Sidebar */}
          <div className="space-y-6">
            {/* Quick Upload Card */}
            <Card variant="glass">
              <div className="p-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="p-2 rounded-xl bg-neon-cyan/10">
                    <SparklesIcon className="w-5 h-5 text-neon-cyan" />
                  </div>
                  <h3 className="font-semibold text-gray-900 dark:text-white">
                    Quick Analysis
                  </h3>
                </div>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                  Drag and drop any image or video to instantly check for
                  deepfakes.
                </p>
                <Button
                  variant="secondary"
                  className="w-full"
                  onClick={() => openModal('upload-modal')}>

                  Upload Media
                </Button>
              </div>
            </Card>

            {/* Activity Chart */}
            <ActivityChart />

          </div>
        </div>
      </div>
    </div>);

}
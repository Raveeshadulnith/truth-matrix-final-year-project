import React from 'react';
import { motion } from 'framer-motion';
import {
  UsersIcon,
  ActivityIcon,
  ServerIcon,
  AlertTriangleIcon } from
'lucide-react';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
export function AdminDashboardPage() {
  return (
    <div className="min-h-screen py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto space-y-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              Admin Dashboard
            </h1>
            <p className="text-gray-600 dark:text-gray-400">
              System overview and management
            </p>
          </div>
          <Badge variant="danger" glow>
            Admin Access
          </Badge>
        </div>

        {/* System Stats */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          <Card variant="default" className="p-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-blue-100 dark:bg-blue-900/30">
                <UsersIcon className="w-6 h-6 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <p className="text-sm text-gray-500">Total Users</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                  12,450
                </p>
              </div>
            </div>
          </Card>
          <Card variant="default" className="p-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-purple-100 dark:bg-purple-900/30">
                <ActivityIcon className="w-6 h-6 text-purple-600 dark:text-purple-400" />
              </div>
              <div>
                <p className="text-sm text-gray-500">Analyses Today</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                  3,842
                </p>
              </div>
            </div>
          </Card>
          <Card variant="default" className="p-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-green-100 dark:bg-green-900/30">
                <ServerIcon className="w-6 h-6 text-green-600 dark:text-green-400" />
              </div>
              <div>
                <p className="text-sm text-gray-500">Server Status</p>
                <p className="text-2xl font-bold text-green-600 dark:text-green-400">
                  Healthy
                </p>
              </div>
            </div>
          </Card>
          <Card variant="default" className="p-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-orange-100 dark:bg-orange-900/30">
                <AlertTriangleIcon className="w-6 h-6 text-orange-600 dark:text-orange-400" />
              </div>
              <div>
                <p className="text-sm text-gray-500">Flagged Results</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                  24
                </p>
              </div>
            </div>
          </Card>
        </div>

        {/* Recent Users Table */}
        <Card variant="default">
          <div className="p-6 border-b border-gray-200 dark:border-navy-700">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Recent Users
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-gray-50 dark:bg-navy-900/50">
                  <th className="px-6 py-3 text-sm font-semibold text-gray-900 dark:text-white">
                    User
                  </th>
                  <th className="px-6 py-3 text-sm font-semibold text-gray-900 dark:text-white">
                    Role
                  </th>
                  <th className="px-6 py-3 text-sm font-semibold text-gray-900 dark:text-white">
                    Status
                  </th>
                  <th className="px-6 py-3 text-sm font-semibold text-gray-900 dark:text-white">
                    Joined
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-navy-700">
                {[1, 2, 3, 4].map((i) =>
                <tr key={i}>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-gray-200 dark:bg-navy-700" />
                        <div>
                          <p className="font-medium text-gray-900 dark:text-white">
                            User {i}
                          </p>
                          <p className="text-sm text-gray-500">
                            user{i}@example.com
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <Badge size="sm">Pro</Badge>
                    </td>
                    <td className="px-6 py-4">
                      <Badge variant="success" size="sm">
                        Active
                      </Badge>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      2 hours ago
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>);

}
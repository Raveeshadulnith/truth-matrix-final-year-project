import React from 'react';
import { motion } from 'framer-motion';
import { CodeIcon, TerminalIcon, KeyIcon, BookOpenIcon } from 'lucide-react';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
export function ApiDocsPage() {
  return (
    <div className="min-h-screen py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto space-y-8">
        <motion.div
          initial={{
            opacity: 0,
            y: 20
          }}
          animate={{
            opacity: 1,
            y: 0
          }}>

          <h1 className="text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white mb-4">
            API Documentation
          </h1>
          <p className="text-lg text-gray-600 dark:text-gray-400">
            Integrate TruthMatrix's deepfake detection into your own
            applications.
          </p>
        </motion.div>

        <div className="grid sm:grid-cols-3 gap-6">
          <Card variant="glass" className="p-6">
            <KeyIcon className="w-8 h-8 text-neon-cyan mb-4" />
            <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
              Authentication
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Use Bearer tokens for secure API access.
            </p>
          </Card>
          <Card variant="glass" className="p-6">
            <TerminalIcon className="w-8 h-8 text-neon-violet mb-4" />
            <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
              Rate Limits
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Up to 1000 requests per minute.
            </p>
          </Card>
          <Card variant="glass" className="p-6">
            <BookOpenIcon className="w-8 h-8 text-neon-pink mb-4" />
            <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
              SDKs
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Available for Python, Node.js, and Go.
            </p>
          </Card>
        </div>

        <Card variant="default">
          <div className="p-6 sm:p-8">
            <div className="flex items-center gap-3 mb-6">
              <Badge variant="info">POST</Badge>
              <h2 className="text-xl font-mono font-bold text-gray-900 dark:text-white">
                /v1/analyze
              </h2>
            </div>

            <p className="text-gray-600 dark:text-gray-400 mb-6">
              Submit an image or video URL for deepfake analysis.
            </p>

            <h3 className="font-semibold text-gray-900 dark:text-white mb-3">
              Request Example (cURL)
            </h3>
            <div className="bg-gray-900 rounded-xl p-4 mb-8 overflow-x-auto">
              <pre className="text-sm text-green-400 font-mono">
                {`curl -X POST https://api.deepguardian.ai/v1/analyze \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "media_url": "https://example.com/image.jpg",
    "include_heatmap": true
  }'`}
              </pre>
            </div>

            <h3 className="font-semibold text-gray-900 dark:text-white mb-3">
              Response
            </h3>
            <div className="bg-gray-900 rounded-xl p-4 overflow-x-auto">
              <pre className="text-sm text-blue-400 font-mono">
                {`{
  "id": "ana_123456789",
  "status": "success",
  "result": "fake",
  "confidence": 94.7,
  "probabilities": {
    "fake": 94.7,
    "real": 5.3
  },
  "artifacts": [
    {
      "type": "blending_artifact",
      "confidence": 89.5,
      "location": "facial_boundaries"
    }
  ],
  "heatmap_url": "https://api.deepguardian.ai/heatmaps/hm_123.png"
}`}
              </pre>
            </div>
          </div>
        </Card>
      </div>
    </div>);

}
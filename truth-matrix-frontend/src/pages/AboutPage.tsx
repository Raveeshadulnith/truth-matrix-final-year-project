import React from 'react';
import { motion } from 'framer-motion';
import {ShieldCheckIcon, BrainCircuitIcon, CodeIcon, GlobeIcon } from 'lucide-react';
import { Card } from '../components/common/Card';
export function AboutPage() {
  return (
    <div className="min-h-screen py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto space-y-16">
        {/* Hero */}
        <div className="text-center">
          <motion.div
            initial={{
              opacity: 0,
              scale: 0.9
            }}
            animate={{
              opacity: 1,
              scale: 1
            }}
            className="w-20 h-20 mx-auto bg-neon-cyan/10 rounded-2xl flex items-center justify-center mb-6">

            <ShieldCheckIcon className="w-10 h-10 text-neon-cyan" />
          </motion.div>
          <motion.h1
            initial={{
              opacity: 0,
              y: 20
            }}
            animate={{
              opacity: 1,
              y: 0
            }}
            className="text-4xl sm:text-5xl font-bold text-gray-900 dark:text-white mb-6">

            Protecting Truth in the{' '}
            <span className="gradient-text">Digital Age</span>
          </motion.h1>
          <motion.p
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
            }}
            className="text-xl text-gray-600 dark:text-gray-400 max-w-2xl mx-auto">

            TruthMatrix was founded with a single mission: to provide reliable,
            accessible tools for detecting AI-generated media and deepfakes.
          </motion.p>
        </div>

        {/* Tech Stack */}
        <div className="grid sm:grid-cols-2 gap-8">
          <Card variant="glass" className="p-8">
            <BrainCircuitIcon className="w-8 h-8 text-neon-violet mb-4" />
            <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-3">
              Our AI Model
            </h3>
            <p className="text-gray-600 dark:text-gray-400">
              We utilize a fine-tuned XceptionNet architecture, trained on
              massive datasets including FaceForensics++ and Celeb-DF. Our model
              doesn't just give a score; it uses Grad-CAM to generate heatmaps
              explaining exactly *why* it made its decision.
            </p>
          </Card>
          <Card variant="glass" className="p-8">
            <CodeIcon className="w-8 h-8 text-neon-cyan mb-4" />
            <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-3">
              The Platform
            </h3>
            <p className="text-gray-600 dark:text-gray-400">
              Built with React, TypeScript, and TailwindCSS on the frontend,
              powered by a high-performance Python/FastAPI backend. We process
              media in real-time, ensuring you get answers when you need them
              most.
            </p>
          </Card>
        </div>

        {/* Story */}
        <Card variant="default">
          <div className="p-8 sm:p-12 prose prose-lg dark:prose-invert max-w-none">
            <h2>The Deepfake Threat</h2>
            <p>
              As generative AI becomes more advanced, the line between reality
              and fabrication is blurring. Deepfakes pose significant risks to
              journalism, personal security, and democratic processes.
            </p>
            <p>
              We built TruthMatrix because we believe that everyoneâ€”from
              newsrooms to everyday internet usersâ€”deserves the ability to
              verify the media they consume. Our explainable AI approach ensures
              that our detection isn't a "black box," but a transparent tool
              that highlights specific manipulation artifacts.
            </p>
          </div>
        </Card>
      </div>
    </div>);

}

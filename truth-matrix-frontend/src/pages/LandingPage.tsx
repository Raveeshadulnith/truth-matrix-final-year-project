import React from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ZapIcon,
  EyeIcon,
  GlobeIcon,
  FileImageIcon,
  FileTextIcon,
  HistoryIcon,
  ImageIcon,
  ShieldAlertIcon,
  UsersIcon,
  TargetIcon,
  ArrowRightIcon,
  CheckIcon,
  StarIcon } from
'lucide-react';
import { Button } from '../components/common/Button';
import { Card } from '../components/common/Card';
import { AnimatedBackground } from '../components/common/AnimatedBackground';
import { ROUTES, FEATURES, STATS, TESTIMONIALS } from '../utils/constants';
import { useAuthStore } from '../store/authStore';
const iconMap: Record<string, React.ElementType> = {
  Zap: ZapIcon,
  Eye: EyeIcon,
  Globe: GlobeIcon,
  FileImage: FileImageIcon,
  FileText: FileTextIcon,
  History: HistoryIcon,
  Image: ImageIcon,
  ShieldAlert: ShieldAlertIcon,
  Users: UsersIcon,
  Target: TargetIcon
};
export function LandingPage() {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuthStore();
  const handleGetStarted = () => {
    navigate(isAuthenticated ? ROUTES.ANALYZE : ROUTES.REGISTER);
  };
  return (
    <div className="relative min-h-screen">
      <AnimatedBackground variant="particles" />

      {/* Hero Section */}
      <section className="relative pt-20 pb-32 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center">
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
                duration: 0.6
              }}>

              <span className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-neon-cyan/10 border border-neon-cyan/30 text-neon-cyan text-sm font-medium mb-8">
                <span className="w-2 h-2 rounded-full bg-neon-cyan animate-pulse" />
                AI-Powered Deepfake Detection
              </span>
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
              transition={{
                duration: 0.6,
                delay: 0.1
              }}
              className="text-4xl sm:text-5xl lg:text-7xl font-bold text-gray-900 dark:text-white mb-6">

              Expose the Truth
              <br />
              <span className="gradient-text">Behind Every Pixel</span>
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
                duration: 0.6,
                delay: 0.2
              }}
              className="text-lg sm:text-xl text-gray-600 dark:text-gray-400 max-w-3xl mx-auto mb-10">

              TruthMatrix uses trained EfficientNet-B4 image and temporal video
              models with Grad-CAM XAI heatmaps to explain deepfake signals in
              uploaded media.
            </motion.p>

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
                duration: 0.6,
                delay: 0.3
              }}
              className="flex flex-col sm:flex-row items-center justify-center gap-4">

              <Button
                variant="primary"
                size="lg"
                glow
                onClick={handleGetStarted}
                rightIcon={<ArrowRightIcon className="w-5 h-5" />}>

                Get Started Free
              </Button>
              <Button
                variant="secondary"
                size="lg"
                leftIcon={<UsersIcon className="w-5 h-5" />}
                onClick={() => navigate(ROUTES.ABOUT)}>

                About Us
              </Button>
            </motion.div>
          </div>

          {/* Hero Image/Demo */}
          <motion.div
            initial={{
              opacity: 0,
              y: 40
            }}
            animate={{
              opacity: 1,
              y: 0
            }}
            transition={{
              duration: 0.8,
              delay: 0.4
            }}
            className="mt-20 relative">

            <div className="relative mx-auto max-w-5xl">
              <div className="absolute inset-0 bg-gradient-to-r from-neon-cyan/20 via-neon-violet/20 to-neon-pink/20 rounded-3xl blur-3xl" />
              <div className="relative glass-card p-2 sm:p-4">
                <img
                  src="https://images.unsplash.com/photo-1633356122544-f134324a6cee?w=1200&h=600&fit=crop"
                  alt="TruthMatrix Dashboard"
                  className="w-full rounded-2xl shadow-2xl" />

                {/* Floating elements */}
                <motion.div
                  animate={{
                    y: [0, -10, 0]
                  }}
                  transition={{
                    duration: 3,
                    repeat: Infinity
                  }}
                  className="absolute -top-6 -right-6 glass-card p-4 hidden sm:block">

                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-neon-red/20 flex items-center justify-center">
                      <ShieldAlertIcon className="w-5 h-5 text-neon-red" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-gray-900 dark:text-white">
                        Deepfake Detected
                      </p>
                      <p className="text-xs text-gray-500">94.7% confidence</p>
                    </div>
                  </div>
                </motion.div>

                <motion.div
                  animate={{
                    y: [0, 10, 0]
                  }}
                  transition={{
                    duration: 4,
                    repeat: Infinity
                  }}
                  className="absolute -bottom-6 -left-6 glass-card p-4 hidden sm:block">

                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-neon-green/20 flex items-center justify-center">
                      <CheckIcon className="w-5 h-5 text-neon-green" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-gray-900 dark:text-white">
                        Authentic
                      </p>
                      <p className="text-xs text-gray-500">Verified original</p>
                    </div>
                  </div>
                </motion.div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-16 px-4 sm:px-6 lg:px-8 bg-gray-50 dark:bg-navy-900/50">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 lg:gap-8">
            {STATS.map((stat, index) => {
              const Icon = iconMap[stat.icon];
              return (
                <motion.div
                  key={stat.label}
                  initial={{
                    opacity: 0,
                    y: 20
                  }}
                  whileInView={{
                    opacity: 1,
                    y: 0
                  }}
                  viewport={{
                    once: true
                  }}
                  transition={{
                    delay: index * 0.1
                  }}
                  className="text-center">

                  <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-neon-cyan/10 mb-4">
                    <Icon className="w-6 h-6 text-neon-cyan" />
                  </div>
                  <p className="text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white mb-1">
                    {stat.value}
                  </p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {stat.label}
                  </p>
                </motion.div>);

            })}
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-24 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <motion.h2
              initial={{
                opacity: 0,
                y: 20
              }}
              whileInView={{
                opacity: 1,
                y: 0
              }}
              viewport={{
                once: true
              }}
              className="text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white mb-4">

              Powerful Features for
              <span className="gradient-text"> Truth Detection</span>
            </motion.h2>
            <p className="text-lg text-gray-600 dark:text-gray-400 max-w-2xl mx-auto">
              Everything you need to verify media authenticity and protect
              against misinformation.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 lg:gap-8">
            {FEATURES.map((feature, index) => {
              const Icon = iconMap[feature.icon];
              return (
                <motion.div
                  key={feature.title}
                  initial={{
                    opacity: 0,
                    y: 20
                  }}
                  whileInView={{
                    opacity: 1,
                    y: 0
                  }}
                  viewport={{
                    once: true
                  }}
                  transition={{
                    delay: index * 0.1
                  }}>

                  <Card
                    variant="glass"
                    hover
                    padding="none"
                    className="group relative h-full border border-white/10 bg-white/[0.03] shadow-[0_20px_60px_rgba(4,10,28,0.35)]">

                    <div className="absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent via-neon-cyan/80 to-transparent" />
                    <div className="absolute -right-10 -top-10 h-28 w-28 rounded-full bg-neon-cyan/10 blur-3xl transition-all duration-300 group-hover:bg-neon-violet/15 group-hover:scale-110" />

                    <div className="relative flex h-full flex-col p-7">
                      <div className="mb-6 flex items-start justify-between gap-4">
                        <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-white/10 bg-gradient-to-br from-neon-cyan/20 to-neon-violet/20 shadow-[0_12px_30px_rgba(34,211,238,0.18)]">
                          <Icon className="w-6 h-6 text-neon-cyan" />
                        </div>
                        <span className="rounded-full border border-neon-cyan/20 bg-neon-cyan/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-neon-cyan">
                          {feature.eyebrow}
                        </span>
                      </div>

                      <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-3">
                        {feature.title}
                      </h3>
                      <p className="text-[15px] leading-7 text-gray-600 dark:text-gray-400">
                        {feature.description}
                      </p>
                    </div>
                  </Card>
                </motion.div>);

            })}
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-24 px-4 sm:px-6 lg:px-8 bg-gray-50 dark:bg-navy-900/50">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <motion.h2
              initial={{
                opacity: 0,
                y: 20
              }}
              whileInView={{
                opacity: 1,
                y: 0
              }}
              viewport={{
                once: true
              }}
              className="text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white mb-4">

              How It Works
            </motion.h2>
            <p className="text-lg text-gray-600 dark:text-gray-400">
              Three simple steps to verify any media
            </p>
          </div>

          <div className="relative grid md:grid-cols-3 gap-8">
            <div className="hidden md:block absolute top-12 left-[16.666%] right-[16.666%] h-0.5 bg-gradient-to-r from-neon-cyan via-neon-cyan to-neon-violet" />
            {[
            {
              step: '01',
              title: 'Upload Media',
              description:
              'Drag and drop your image or video, or paste a URL to analyze.'
            },
            {
              step: '02',
              title: 'AI Analysis',
              description:
              'The connected image or video checkpoint processes your media.'
            },
            {
              step: '03',
              title: 'Get Results',
              description:
              'View detailed results with explainable AI heatmaps.'
            }].
            map((item, index) =>
            <motion.div
              key={item.step}
              initial={{
                opacity: 0,
                y: 20
              }}
              whileInView={{
                opacity: 1,
                y: 0
              }}
              viewport={{
                once: true
              }}
              transition={{
                delay: index * 0.2
              }}
              className="relative z-10">

                <div className="text-center">
                  <div className="inline-flex items-center justify-center w-24 h-24 rounded-2xl bg-gradient-to-br from-neon-cyan to-neon-violet text-white text-3xl font-bold mb-6 shadow-neon-cyan">
                    {item.step}
                  </div>
                  <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
                    {item.title}
                  </h3>
                  <p className="text-gray-600 dark:text-gray-400">
                    {item.description}
                  </p>
                </div>
              </motion.div>
            )}
          </div>
        </div>
      </section>

      {/* Testimonials */}
      <section className="py-24 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <motion.h2
              initial={{
                opacity: 0,
                y: 20
              }}
              whileInView={{
                opacity: 1,
                y: 0
              }}
              viewport={{
                once: true
              }}
              className="text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white mb-4">

              Trusted by Professionals
            </motion.h2>
          </div>

          <div className="grid md:grid-cols-3 gap-6 lg:gap-8">
            {TESTIMONIALS.map((testimonial, index) =>
            <motion.div
              key={testimonial.name}
              initial={{
                opacity: 0,
                y: 20
              }}
              whileInView={{
                opacity: 1,
                y: 0
              }}
              viewport={{
                once: true
              }}
              transition={{
                delay: index * 0.1
              }}>

                <Card variant="default" className="h-full">
                  <div className="p-6">
                    <div className="flex items-center gap-1 mb-4">
                      {[...Array(5)].map((_, i) =>
                    <StarIcon
                      key={i}
                      className="w-4 h-4 fill-yellow-400 text-yellow-400" />

                    )}
                    </div>
                    <p className="text-gray-600 dark:text-gray-400 mb-6">
                      "{testimonial.content}"
                    </p>
                    <div className="flex items-center gap-3">
                      <img
                      src={testimonial.avatar}
                      alt={testimonial.name}
                      className="w-12 h-12 rounded-full object-cover" />

                      <div>
                        <p className="font-semibold text-gray-900 dark:text-white">
                          {testimonial.name}
                        </p>
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                          {testimonial.role}, {testimonial.company}
                        </p>
                      </div>
                    </div>
                  </div>
                </Card>
              </motion.div>
            )}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-24 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto">
          <motion.div
            initial={{
              opacity: 0,
              scale: 0.95
            }}
            whileInView={{
              opacity: 1,
              scale: 1
            }}
            viewport={{
              once: true
            }}
            className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-neon-cyan via-neon-violet to-neon-pink p-px">

            <div className="relative bg-navy-900 rounded-3xl px-8 py-16 sm:px-16 text-center">
              <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
                Ready to Detect Deepfakes?
              </h2>
              <p className="text-lg text-gray-300 mb-8 max-w-2xl mx-auto">
                Join thousands of journalists, researchers, and security
                professionals using TruthMatrix to verify media authenticity.
              </p>
              <Button
                variant="primary"
                size="lg"
                onClick={handleGetStarted}
                rightIcon={<ArrowRightIcon className="w-5 h-5" />}>

                Get Started
              </Button>
            </div>
          </motion.div>
        </div>
      </section>
    </div>);

}

import { motion } from 'framer-motion';
import { CheckIcon } from 'lucide-react';
import { Button } from '../components/common/Button';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { PRICING_PLANS } from '../utils/constants';
export function PricingPage() {
  return (
    <div className="min-h-screen py-16 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-16">
          <motion.h1
            initial={{
              opacity: 0,
              y: 20
            }}
            animate={{
              opacity: 1,
              y: 0
            }}
            className="text-4xl sm:text-5xl font-bold text-gray-900 dark:text-white mb-4">

            Simple, Transparent <span className="gradient-text">Pricing</span>
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
            className="text-xl text-gray-600 dark:text-gray-400">

            Choose the plan that fits your deepfake detection needs.
          </motion.p>
        </div>

        <div className="grid md:grid-cols-3 gap-8 max-w-6xl mx-auto">
          {PRICING_PLANS.map((plan, index) =>
          <motion.div
            key={plan.name}
            initial={{
              opacity: 0,
              y: 20
            }}
            animate={{
              opacity: 1,
              y: 0
            }}
            transition={{
              delay: index * 0.1
            }}>

              <Card
              variant={plan.popular ? 'glass' : 'default'}
              className={`relative h-full flex flex-col ${plan.popular ? 'border-neon-cyan shadow-neon-cyan scale-105 z-10' : ''}`}>

                {plan.popular &&
              <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2">
                    <Badge variant="info" glow>
                      Most Popular
                    </Badge>
                  </div>
              }

                <div className="p-8 flex-1 flex flex-col">
                  <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
                    {plan.name}
                  </h3>
                  <p className="text-gray-500 dark:text-gray-400 mb-6 h-10">
                    {plan.description}
                  </p>

                  <div className="mb-8">
                    <span className="text-4xl font-bold text-gray-900 dark:text-white">
                      ${plan.price}
                    </span>
                    <span className="text-gray-500 dark:text-gray-400">
                      /{plan.period}
                    </span>
                  </div>

                  <ul className="space-y-4 mb-8 flex-1">
                    {plan.features.map((feature) =>
                  <li key={feature} className="flex items-start gap-3">
                        <CheckIcon className="w-5 h-5 text-neon-green flex-shrink-0 mt-0.5" />
                        <span className="text-gray-700 dark:text-gray-300">
                          {feature}
                        </span>
                      </li>
                  )}
                  </ul>

                  <Button
                  variant={plan.popular ? 'primary' : 'secondary'}
                  className="w-full"
                  glow={plan.popular}>

                    {plan.cta}
                  </Button>
                </div>
              </Card>
            </motion.div>
          )}
        </div>
      </div>
    </div>);

}

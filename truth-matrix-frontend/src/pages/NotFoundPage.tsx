import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ShieldAlertIcon, HomeIcon } from 'lucide-react';
import { Button } from '../components/common/Button';
import { ROUTES } from '../utils/constants';
export function NotFoundPage() {
  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4">
      <div className="text-center">
        <motion.div
          initial={{
            scale: 0.8,
            opacity: 0
          }}
          animate={{
            scale: 1,
            opacity: 1
          }}
          transition={{
            type: 'spring'
          }}
          className="inline-flex items-center justify-center w-24 h-24 rounded-full bg-red-100 dark:bg-red-900/30 mb-8">

          <ShieldAlertIcon className="w-12 h-12 text-neon-red" />
        </motion.div>

        <motion.h1
          initial={{
            y: 20,
            opacity: 0
          }}
          animate={{
            y: 0,
            opacity: 1
          }}
          transition={{
            delay: 0.1
          }}
          className="text-6xl font-bold text-gray-900 dark:text-white mb-4">

          404
        </motion.h1>

        <motion.p
          initial={{
            y: 20,
            opacity: 0
          }}
          animate={{
            y: 0,
            opacity: 1
          }}
          transition={{
            delay: 0.2
          }}
          className="text-xl text-gray-600 dark:text-gray-400 mb-8 max-w-md mx-auto">

          The page you're looking for seems to be missing or has been moved.
        </motion.p>

        <motion.div
          initial={{
            y: 20,
            opacity: 0
          }}
          animate={{
            y: 0,
            opacity: 1
          }}
          transition={{
            delay: 0.3
          }}>

          <Link to={ROUTES.HOME}>
            <Button
              variant="primary"
              size="lg"
              leftIcon={<HomeIcon className="w-5 h-5" />}>

              Back to Home
            </Button>
          </Link>
        </motion.div>
      </div>
    </div>);

}

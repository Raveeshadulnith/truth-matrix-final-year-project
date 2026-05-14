import React, { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { XIcon } from 'lucide-react';
import { useUIStore } from '../../store/uiStore';
interface ModalProps {
  id: string;
  title?: string;
  children: React.ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'full';
  showClose?: boolean;
  onClose?: () => void;
}
export function Modal({
  id,
  title,
  children,
  size = 'md',
  showClose = true,
  onClose
}: ModalProps) {
  const { activeModal, closeModal } = useUIStore();
  const isOpen = activeModal === id;
  const handleClose = () => {
    closeModal();
    onClose?.();
  };
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        handleClose();
      }
    };
    if (isOpen) {
      document.body.style.overflow = 'hidden';
      window.addEventListener('keydown', handleEscape);
    }
    return () => {
      document.body.style.overflow = '';
      window.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen]);
  const sizes = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-lg',
    xl: 'max-w-2xl',
    full: 'max-w-[90vw] max-h-[90vh]'
  };
  return (
    <AnimatePresence>
      {isOpen &&
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          {/* Backdrop */}
          <motion.div
          initial={{
            opacity: 0
          }}
          animate={{
            opacity: 1
          }}
          exit={{
            opacity: 0
          }}
          transition={{
            duration: 0.2
          }}
          className="absolute inset-0 bg-black/60 backdrop-blur-sm"
          onClick={handleClose} />


          {/* Modal */}
          <motion.div
          initial={{
            opacity: 0,
            scale: 0.95,
            y: 20
          }}
          animate={{
            opacity: 1,
            scale: 1,
            y: 0
          }}
          exit={{
            opacity: 0,
            scale: 0.95,
            y: 20
          }}
          transition={{
            duration: 0.2,
            ease: 'easeOut'
          }}
          className={`
              relative w-full ${sizes[size]}
              bg-white dark:bg-navy-800
              rounded-2xl shadow-2xl
              border border-gray-200 dark:border-navy-600
              overflow-hidden
            `}>

            {/* Header */}
            {(title || showClose) &&
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-navy-700">
                {title &&
            <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                    {title}
                  </h2>
            }
                {showClose &&
            <button
              onClick={handleClose}
              className="p-2 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-navy-700 transition-colors"
              aria-label="Close modal">

                    <XIcon className="w-5 h-5" />
                  </button>
            }
              </div>
          }

            {/* Content */}
            <div className="p-6">{children}</div>
          </motion.div>
        </div>
      }
    </AnimatePresence>);

}
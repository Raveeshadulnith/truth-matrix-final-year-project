import React, { useCallback, useState, createElement } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  UploadCloudIcon,
  ImageIcon,
  VideoIcon,
  MusicIcon,
  XIcon,
  FileIcon } from
'lucide-react';
import { formatFileSize } from '../../utils/formatters';
import {
  SUPPORTED_IMAGE_TYPES,
  SUPPORTED_VIDEO_TYPES,
  SUPPORTED_AUDIO_TYPES,
  MAX_FILE_SIZE } from
'../../utils/constants';
interface DropzoneProps {
  onFileSelect: (file: File) => void;
  accept?: string[];
  maxSize?: number;
  disabled?: boolean;
}
export function Dropzone({
  onFileSelect,
  accept = [
  ...SUPPORTED_IMAGE_TYPES,
  ...SUPPORTED_VIDEO_TYPES,
  ...SUPPORTED_AUDIO_TYPES],

  maxSize = MAX_FILE_SIZE,
  disabled = false
}: DropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<{
    file: File;
    url: string;
  } | null>(null);
  const validateFile = useCallback((file: File): string | null => {
    if (!accept.includes(file.type)) {
      return 'File type not supported. Please upload an image, video, or audio file.';
    }
    if (file.size > maxSize) {
      return `File too large. Maximum size is ${formatFileSize(maxSize)}.`;
    }
    return null;
  }, [accept, maxSize]);
  const handleFile = useCallback(
    (file: File) => {
      setError(null);
      const validationError = validateFile(file);
      if (validationError) {
        setError(validationError);
        return;
      }
      // Create preview for images
      if (file.type.startsWith('image/')) {
        const url = URL.createObjectURL(file);
        setPreview({
          file,
          url
        });
      } else {
        setPreview({
          file,
          url: ''
        });
      }
    },
    [validateFile]
  );
  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      if (disabled) return;
      const file = e.dataTransfer.files[0];
      if (file) {
        handleFile(file);
      }
    },
    [disabled, handleFile]
  );
  const handleDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      if (!disabled) {
        setIsDragging(true);
      }
    },
    [disabled]
  );
  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);
  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        handleFile(file);
      }
    },
    [handleFile]
  );
  const handleConfirm = () => {
    if (preview) {
      onFileSelect(preview.file);
    }
  };
  const handleClear = () => {
    if (preview?.url) {
      URL.revokeObjectURL(preview.url);
    }
    setPreview(null);
    setError(null);
  };
  const getFileIcon = (type: string) => {
    if (type.startsWith('image/')) return ImageIcon;
    if (type.startsWith('video/')) return VideoIcon;
    if (type.startsWith('audio/')) return MusicIcon;
    return FileIcon;
  };
  return (
    <div className="w-full">
      <AnimatePresence mode="wait">
        {preview ?
        <motion.div
          key="preview"
          initial={{
            opacity: 0,
            scale: 0.95
          }}
          animate={{
            opacity: 1,
            scale: 1
          }}
          exit={{
            opacity: 0,
            scale: 0.95
          }}
          className="relative rounded-2xl border-2 border-neon-cyan bg-neon-cyan/5 dark:bg-neon-cyan/10 p-6">

            <button
            onClick={handleClear}
            className="absolute top-4 right-4 p-2 rounded-lg bg-gray-100 dark:bg-navy-700 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition-colors">

              <XIcon className="w-5 h-5" />
            </button>

            <div className="flex flex-col sm:flex-row items-center gap-6">
              {/* Preview */}
              <div className="w-32 h-32 rounded-xl overflow-hidden bg-gray-100 dark:bg-navy-700 flex items-center justify-center flex-shrink-0">
                {preview.url ?
              <img
                src={preview.url}
                alt="Preview"
                className="w-full h-full object-cover" /> :


              createElement(getFileIcon(preview.file.type), {
                className: 'w-12 h-12 text-gray-400'
              })
              }
              </div>

              {/* File info */}
              <div className="flex-1 text-center sm:text-left">
                <p className="text-lg font-semibold text-gray-900 dark:text-white truncate max-w-xs">
                  {preview.file.name}
                </p>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  {formatFileSize(preview.file.size)} •{' '}
                  {preview.file.type.split('/')[1].toUpperCase()}
                </p>
                <div className="flex items-center gap-3 mt-4 justify-center sm:justify-start">
                  <button
                  onClick={handleConfirm}
                  className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-neon-cyan to-neon-violet text-white font-semibold hover:shadow-neon-cyan transition-all">

                    Analyze Now
                  </button>
                  <button
                  onClick={handleClear}
                  className="px-6 py-2.5 rounded-xl border-2 border-gray-300 dark:border-navy-600 text-gray-700 dark:text-gray-300 font-semibold hover:bg-gray-100 dark:hover:bg-navy-700 transition-all">

                    Choose Different
                  </button>
                </div>
              </div>
            </div>
          </motion.div> :

        <motion.div
          key="dropzone"
          initial={{
            opacity: 0
          }}
          animate={{
            opacity: 1
          }}
          exit={{
            opacity: 0
          }}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          className={`
              relative rounded-2xl border-2 border-dashed p-8 sm:p-12 text-center
              transition-all duration-300 cursor-pointer
              ${isDragging ? 'border-neon-cyan bg-neon-cyan/10 scale-[1.02]' : 'border-gray-300 dark:border-navy-600 hover:border-neon-cyan/50 hover:bg-gray-50 dark:hover:bg-navy-800/50'}
              ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
              ${error ? 'border-neon-red bg-red-50 dark:bg-red-900/10' : ''}
            `}>

            <input
            type="file"
            accept={accept.join(',')}
            onChange={handleInputChange}
            disabled={disabled}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed" />


            <motion.div
            animate={
            isDragging ?
            {
              scale: 1.1,
              y: -5
            } :
            {
              scale: 1,
              y: 0
            }
            }
            className="flex flex-col items-center">

              <div
              className={`
                  w-16 h-16 rounded-2xl flex items-center justify-center mb-4
                  ${isDragging ? 'bg-neon-cyan/20' : 'bg-gray-100 dark:bg-navy-700'}
                `}>

                <UploadCloudIcon
                className={`w-8 h-8 ${isDragging ? 'text-neon-cyan' : 'text-gray-400'}`} />

              </div>

              <p className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                {isDragging ? 'Drop your file here' : 'Drag & drop your file'}
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                or click to browse from your device
              </p>

              <div className="flex flex-wrap items-center justify-center gap-3">
                <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gray-100 dark:bg-navy-700 text-xs text-gray-600 dark:text-gray-400">
                  <ImageIcon className="w-3.5 h-3.5" />
                  Images
                </span>
                <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gray-100 dark:bg-navy-700 text-xs text-gray-600 dark:text-gray-400">
                  <VideoIcon className="w-3.5 h-3.5" />
                  Videos
                </span>
                <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gray-100 dark:bg-navy-700 text-xs text-gray-600 dark:text-gray-400">
                  <MusicIcon className="w-3.5 h-3.5" />
                  Audio
                </span>
              </div>

              <p className="text-xs text-gray-400 dark:text-gray-500 mt-4">
                Max file size: {formatFileSize(maxSize)}
              </p>
            </motion.div>
          </motion.div>
        }
      </AnimatePresence>

      {error &&
      <motion.p
        initial={{
          opacity: 0,
          y: -10
        }}
        animate={{
          opacity: 1,
          y: 0
        }}
        className="mt-3 text-sm text-neon-red text-center">

          {error}
        </motion.p>
      }
    </div>);

}

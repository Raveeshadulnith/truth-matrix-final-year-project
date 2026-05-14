import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  XIcon,
  ImageIcon,
  VideoIcon,
  MusicIcon,
  LinkIcon,
  CameraIcon } from
'lucide-react';
import { useUIStore } from '../../store/uiStore';
import { Dropzone } from './Dropzone';
import { Button } from '../common/Button';
import { Input } from '../common/Input';
import { Tabs } from '../common/Tabs';
interface UploadModalProps {
  onFileSelect: (file: File) => void;
  onUrlSubmit: (url: string) => void;
}
export function UploadModal({ onFileSelect, onUrlSubmit }: UploadModalProps) {
  const { activeModal, closeModal } = useUIStore();
  const [urlInput, setUrlInput] = useState('');
  const [activeTab, setActiveTab] = useState('upload');
  const isOpen = activeModal === 'upload-modal';
  const handleUrlSubmit = () => {
    if (urlInput.trim()) {
      onUrlSubmit(urlInput.trim());
      setUrlInput('');
      closeModal();
    }
  };
  const handleFileSelect = (file: File) => {
    onFileSelect(file);
    closeModal();
  };
  const tabs = [
  {
    id: 'upload',
    label: 'Upload File',
    icon: <ImageIcon className="w-4 h-4" />,
    content:
    <div className="py-4">
          <Dropzone onFileSelect={handleFileSelect} />
        </div>

  },
  {
    id: 'url',
    label: 'From URL',
    icon: <LinkIcon className="w-4 h-4" />,
    content:
    <div className="py-6 space-y-4">
          <Input
        label="Media URL"
        placeholder="https://example.com/image.jpg"
        value={urlInput}
        onChange={(e) => setUrlInput(e.target.value)}
        leftIcon={<LinkIcon className="w-5 h-5" />} />

          <Button
        variant="primary"
        className="w-full"
        onClick={handleUrlSubmit}
        disabled={!urlInput.trim()}>

            Analyze URL
          </Button>
        </div>

  },
  {
    id: 'camera',
    label: 'Camera',
    icon: <CameraIcon className="w-4 h-4" />,
    content:
    <div className="py-12 text-center">
          <div className="w-20 h-20 mx-auto rounded-2xl bg-gray-100 dark:bg-navy-700 flex items-center justify-center mb-4">
            <CameraIcon className="w-10 h-10 text-gray-400" />
          </div>
          <p className="text-gray-600 dark:text-gray-400 mb-4">
            Camera capture coming soon
          </p>
          <Button variant="secondary" disabled>
            Enable Camera
          </Button>
        </div>

  }];

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
          className="absolute inset-0 bg-black/60 backdrop-blur-sm"
          onClick={closeModal} />


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
          className="relative w-full max-w-2xl bg-white dark:bg-navy-800 rounded-2xl shadow-2xl border border-gray-200 dark:border-navy-600 overflow-hidden">

            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-navy-700">
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                Upload Media for Analysis
              </h2>
              <button
              onClick={closeModal}
              className="p-2 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-navy-700 transition-colors">

                <XIcon className="w-5 h-5" />
              </button>
            </div>

            {/* Content */}
            <div className="p-6">
              <Tabs
              tabs={tabs}
              defaultTab="upload"
              variant="pills"
              onChange={setActiveTab} />

            </div>

            {/* Footer */}
            <div className="px-6 py-4 bg-gray-50 dark:bg-navy-900/50 border-t border-gray-200 dark:border-navy-700">
              <div className="flex flex-wrap items-center justify-center gap-4 text-sm text-gray-500 dark:text-gray-400">
                <span className="flex items-center gap-1.5">
                  <ImageIcon className="w-4 h-4" />
                  JPG, PNG, WebP
                </span>
                <span className="flex items-center gap-1.5">
                  <VideoIcon className="w-4 h-4" />
                  MP4, MOV, AVI, MKV
                </span>
                <span className="flex items-center gap-1.5">
                  <MusicIcon className="w-4 h-4" />
                  MP3, WAV, M4A
                </span>
              </div>
            </div>
          </motion.div>
        </div>
      }
    </AnimatePresence>);

}

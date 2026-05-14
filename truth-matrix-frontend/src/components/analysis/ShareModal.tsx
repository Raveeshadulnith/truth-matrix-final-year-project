import React, { useState, Component } from 'react';
import { motion } from 'framer-motion';
import {
  XIcon,
  LinkIcon,
  CopyIcon,
  CheckIcon,
  TwitterIcon,
  FacebookIcon,
  LinkedinIcon,
  MailIcon } from
'lucide-react';
import { Button } from '../common/Button';
import { Input } from '../common/Input';
import { useUIStore } from '../../store/uiStore';
interface ShareModalProps {
  shareUrl: string;
  title?: string;
}
export function ShareModal({
  shareUrl,
  title = 'TruthMatrix Analysis Report'
}: ShareModalProps) {
  const { activeModal, closeModal } = useUIStore();
  const [copied, setCopied] = useState(false);
  const isOpen = activeModal === 'share-modal';
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };
  const socialLinks = [
  {
    name: 'Twitter',
    icon: TwitterIcon,
    color: 'bg-[#1DA1F2] hover:bg-[#1a8cd8]',
    url: `https://twitter.com/intent/tweet?url=${encodeURIComponent(shareUrl)}&text=${encodeURIComponent(title)}`
  },
  {
    name: 'Facebook',
    icon: FacebookIcon,
    color: 'bg-[#4267B2] hover:bg-[#365899]',
    url: `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(shareUrl)}`
  },
  {
    name: 'LinkedIn',
    icon: LinkedinIcon,
    color: 'bg-[#0077B5] hover:bg-[#006097]',
    url: `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(shareUrl)}`
  },
  {
    name: 'Email',
    icon: MailIcon,
    color: 'bg-gray-600 hover:bg-gray-700',
    url: `mailto:?subject=${encodeURIComponent(title)}&body=${encodeURIComponent(shareUrl)}`
  }];

  if (!isOpen) return null;
  return (
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
        className="relative w-full max-w-md bg-white dark:bg-navy-800 rounded-2xl shadow-2xl border border-gray-200 dark:border-navy-600 overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-navy-700">
          <h2 className="text-xl font-bold text-gray-900 dark:text-white">
            Share Report
          </h2>
          <button
            onClick={closeModal}
            className="p-2 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-navy-700 transition-colors">

            <XIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Copy Link */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Share Link
            </label>
            <div className="flex gap-2">
              <Input
                value={shareUrl}
                readOnly
                leftIcon={<LinkIcon className="w-5 h-5" />}
                className="flex-1" />

              <Button
                variant={copied ? 'success' : 'secondary'}
                onClick={handleCopy}
                leftIcon={
                copied ?
                <CheckIcon className="w-4 h-4" /> :

                <CopyIcon className="w-4 h-4" />

                }>

                {copied ? 'Copied!' : 'Copy'}
              </Button>
            </div>
          </div>

          {/* Social Share */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
              Share on Social Media
            </label>
            <div className="grid grid-cols-4 gap-3">
              {socialLinks.map((social) =>
              <a
                key={social.name}
                href={social.url}
                target="_blank"
                rel="noopener noreferrer"
                className={`
                    flex flex-col items-center gap-2 p-3 rounded-xl text-white transition-all
                    ${social.color}
                  `}>

                  <social.icon className="w-5 h-5" />
                  <span className="text-xs font-medium">{social.name}</span>
                </a>
              )}
            </div>
          </div>
        </div>
      </motion.div>
    </div>);

}
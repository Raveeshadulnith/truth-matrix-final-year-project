import React, { useEffect, useRef, useState } from 'react';
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
import { VideoClipTimeline } from '../analysis/VideoClipTimeline';
import type { VideoSegmentSelection } from '../../api/deepfakeApi';

const DEFAULT_VIDEO_SEGMENT_SECONDS = 10;

interface UploadModalProps {
  onFileSelect: (file: File, videoSegment?: VideoSegmentSelection) => void;
  onUrlSubmit: (url: string) => void;
}
export function UploadModal({ onFileSelect, onUrlSubmit }: UploadModalProps) {
  const { activeModal, closeModal } = useUIStore();
  const [urlInput, setUrlInput] = useState('');
  const [pendingVideo, setPendingVideo] = useState<File | null>(null);
  const [videoPreviewUrl, setVideoPreviewUrl] = useState('');
  const [videoDuration, setVideoDuration] = useState<number | null>(null);
  const [segmentStart, setSegmentStart] = useState(0);
  const [segmentEnd, setSegmentEnd] = useState(DEFAULT_VIDEO_SEGMENT_SECONDS);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const isOpen = activeModal === 'upload-modal';
  const segmentDuration = Math.max(0, segmentEnd - segmentStart);

  useEffect(() => {
    return () => {
      if (videoPreviewUrl) URL.revokeObjectURL(videoPreviewUrl);
    };
  }, [videoPreviewUrl]);

  const resetVideoSelection = () => {
    setPendingVideo(null);
    setVideoPreviewUrl('');
    setVideoDuration(null);
    setSegmentStart(0);
    setSegmentEnd(DEFAULT_VIDEO_SEGMENT_SECONDS);
  };

  const handleClose = () => {
    resetVideoSelection();
    closeModal();
  };
  const handleUrlSubmit = () => {
    if (urlInput.trim()) {
      onUrlSubmit(urlInput.trim());
      setUrlInput('');
      handleClose();
    }
  };
  const handleFileSelect = (file: File) => {
    if (file.type.startsWith('video/') || /\.(mp4|mov|avi|mkv|webm)$/i.test(file.name)) {
      setPendingVideo(file);
      setVideoPreviewUrl(URL.createObjectURL(file));
      setVideoDuration(null);
      setSegmentStart(0);
      setSegmentEnd(DEFAULT_VIDEO_SEGMENT_SECONDS);
      return;
    }
    onFileSelect(file);
    handleClose();
  };

  const handleVideoMetadata = (event: React.SyntheticEvent<HTMLVideoElement>) => {
    const duration = event.currentTarget.duration;
    if (Number.isFinite(duration) && duration > 0) {
      setVideoDuration(duration);
      setSegmentStart(0);
      setSegmentEnd(Math.min(DEFAULT_VIDEO_SEGMENT_SECONDS, duration));
      event.currentTarget.currentTime = 0;
    }
  };

  const handleSegmentChange = (start: number, end: number, previewTime: number) => {
    setSegmentStart(start);
    setSegmentEnd(end);
    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.currentTime = previewTime;
    }
  };

  const handleVideoPlay = (event: React.SyntheticEvent<HTMLVideoElement>) => {
    if (event.currentTarget.currentTime < segmentStart || event.currentTarget.currentTime >= segmentEnd) {
      event.currentTarget.currentTime = segmentStart;
    }
  };

  const handleVideoTimeUpdate = (event: React.SyntheticEvent<HTMLVideoElement>) => {
    if (event.currentTarget.currentTime >= segmentEnd) {
      event.currentTarget.pause();
      event.currentTarget.currentTime = segmentStart;
    }
  };

  const analyzeSelectedVideo = () => {
    if (!pendingVideo || videoDuration === null) return;
    onFileSelect(pendingVideo, {
      startSeconds: segmentStart,
      durationSeconds: segmentDuration,
      sourceDurationSeconds: videoDuration,
    });
    handleClose();
  };
  const tabs = [
  {
    id: 'upload',
    label: 'Upload File',
    icon: <ImageIcon className="w-4 h-4" />,
    content:
    <div className="py-4">
          {pendingVideo ? (
            <div className="space-y-4">
              <video
                ref={videoRef}
                src={videoPreviewUrl}
                controls
                preload="metadata"
                onLoadedMetadata={handleVideoMetadata}
                onPlay={handleVideoPlay}
                onTimeUpdate={handleVideoTimeUpdate}
                className="aspect-video w-full bg-black object-contain"
              />
              <VideoClipTimeline
                duration={videoDuration}
                start={segmentStart}
                end={segmentEnd}
                onChange={handleSegmentChange}
              />
              <div className="flex gap-3">
                <Button variant="secondary" className="flex-1" onClick={resetVideoSelection}>
                  Choose Different
                </Button>
                <Button
                  variant="primary"
                  className="flex-1"
                  onClick={analyzeSelectedVideo}
                  disabled={videoDuration === null}
                >
                  Analyze Segment
                </Button>
              </div>
            </div>
          ) : (
            <Dropzone onFileSelect={handleFileSelect} />
          )}
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
          className="relative max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-gray-200 bg-white shadow-2xl dark:border-navy-600 dark:bg-navy-800">

            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-navy-700">
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                Upload Media for Analysis
              </h2>
              <button
              onClick={handleClose}
              className="p-2 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-navy-700 transition-colors">

                <XIcon className="w-5 h-5" />
              </button>
            </div>

            {/* Content */}
            <div className="p-6">
              <Tabs
              tabs={tabs}
              defaultTab="upload"
              variant="pills" />

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
                  MP4, MOV, AVI, MKV, WebM
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

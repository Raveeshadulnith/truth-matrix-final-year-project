import { FFmpeg } from '@ffmpeg/ffmpeg';
import { fetchFile } from '@ffmpeg/util';
import coreURL from '@ffmpeg/core?url';
import wasmURL from '@ffmpeg/core/wasm?url';
import type { VideoSegmentSelection } from '../api/deepfakeApi';

const ffmpeg = new FFmpeg();
let loadPromise: Promise<void> | null = null;
let progressHandler: ((progress: number) => void) | undefined;

ffmpeg.on('progress', ({ progress }) => {
  progressHandler?.(Math.max(0, Math.min(1, progress)));
});

async function loadFFmpeg() {
  if (ffmpeg.loaded) return;
  loadPromise ??= ffmpeg
    .load({ coreURL, wasmURL })
    .then(() => undefined)
    .catch((error) => {
      loadPromise = null;
      throw error;
    });
  await loadPromise;
}

function clippedFilename(
  filename: string,
  selection: VideoSegmentSelection,
  extension: 'mp4' | 'mkv' | 'webm'
) {
  const base = filename.replace(/\.[^.]+$/, '') || 'video';
  const start = selection.startSeconds.toFixed(1).replace('.', '-');
  const end = (selection.startSeconds + selection.durationSeconds)
    .toFixed(1)
    .replace('.', '-');
  return `${base}-clip-${start}s-${end}s.${extension}`;
}

async function trimWithFFmpeg(
  file: File,
  selection: VideoSegmentSelection,
  onProgress?: (progress: number) => void
) {
  await loadFFmpeg();
  progressHandler = onProgress;

  const id = crypto.randomUUID();
  const inputExtension = file.name.split('.').pop()?.toLowerCase() || 'mp4';
  const inputName = `input-${id}.${inputExtension}`;
  const outputName = `clip-${id}.mp4`;
  const fallbackOutputName = `clip-${id}.mkv`;
  let selectedOutputName = outputName;
  let outputExtension: 'mp4' | 'mkv' = 'mp4';
  let outputType = 'video/mp4';

  try {
    await ffmpeg.writeFile(inputName, await fetchFile(file));
    let preciseExitCode = 1;
    try {
      preciseExitCode = await ffmpeg.exec([
        '-ss',
        selection.startSeconds.toFixed(3),
        '-i',
        inputName,
        '-t',
        selection.durationSeconds.toFixed(3),
        '-map',
        '0:v:0',
        '-an',
        '-c:v',
        'libx264',
        '-preset',
        'ultrafast',
        '-crf',
        '23',
        '-pix_fmt',
        'yuv420p',
        '-movflags',
        '+faststart',
        outputName,
      ]);
    } catch {
      preciseExitCode = 1;
    }

    if (preciseExitCode !== 0) {
      await ffmpeg.deleteFile(outputName).catch(() => undefined);
      let copyExitCode = 1;
      try {
        copyExitCode = await ffmpeg.exec([
          '-ss',
          selection.startSeconds.toFixed(3),
          '-i',
          inputName,
          '-t',
          selection.durationSeconds.toFixed(3),
          '-map',
          '0:v:0',
          '-an',
          '-c:v',
          'copy',
          '-avoid_negative_ts',
          'make_zero',
          '-movflags',
          '+faststart',
          outputName,
        ]);
      } catch {
        copyExitCode = 1;
      }

      if (copyExitCode !== 0) {
        let matroskaExitCode = 1;
        try {
          matroskaExitCode = await ffmpeg.exec([
            '-ss',
            selection.startSeconds.toFixed(3),
            '-i',
            inputName,
            '-t',
            selection.durationSeconds.toFixed(3),
            '-map',
            '0:v:0',
            '-an',
            '-c:v',
            'copy',
            '-avoid_negative_ts',
            'make_zero',
            fallbackOutputName,
          ]);
        } catch {
          matroskaExitCode = 1;
        }

        if (matroskaExitCode !== 0) {
          throw new Error(
            'This video codec cannot be trimmed in your browser. Try an MP4 video encoded with H.264.'
          );
        }

        selectedOutputName = fallbackOutputName;
        outputExtension = 'mkv';
        outputType = 'video/x-matroska';
      }
    }

    const output = await ffmpeg.readFile(selectedOutputName);
    if (typeof output === 'string' || output.byteLength === 0) {
      throw new Error('The selected clip is empty. Choose a different range.');
    }

    const bytes = new Uint8Array(output);
    return new File([bytes], clippedFilename(file.name, selection, outputExtension), {
      type: outputType,
      lastModified: Date.now(),
    });
  } finally {
    progressHandler = undefined;
    await Promise.allSettled([
      ffmpeg.deleteFile(inputName),
      ffmpeg.deleteFile(outputName),
      ffmpeg.deleteFile(fallbackOutputName),
    ]);
  }
}

function waitForMediaEvent(
  video: HTMLVideoElement,
  eventName: 'loadedmetadata' | 'loadeddata' | 'seeked'
) {
  return new Promise<void>((resolve, reject) => {
    const handleSuccess = () => {
      cleanup();
      resolve();
    };
    const handleError = () => {
      cleanup();
      reject(new Error('The browser could not decode this video.'));
    };
    const cleanup = () => {
      video.removeEventListener(eventName, handleSuccess);
      video.removeEventListener('error', handleError);
    };
    video.addEventListener(eventName, handleSuccess, { once: true });
    video.addEventListener('error', handleError, { once: true });
  });
}

function getRecorderMimeType() {
  return [
    'video/webm;codecs=vp9',
    'video/webm;codecs=vp8',
    'video/webm',
  ].find((type) => MediaRecorder.isTypeSupported(type));
}

async function normalizeRecordedWebm(blob: Blob) {
  await loadFFmpeg();
  const id = crypto.randomUUID();
  const inputName = `recording-${id}.webm`;
  const outputName = `normalized-${id}.webm`;

  try {
    await ffmpeg.writeFile(inputName, await fetchFile(blob));
    const exitCode = await ffmpeg.exec([
      '-i',
      inputName,
      '-map',
      '0:v:0',
      '-an',
      '-c:v',
      'copy',
      outputName,
    ]);
    if (exitCode !== 0) return blob;

    const output = await ffmpeg.readFile(outputName);
    if (typeof output === 'string' || output.byteLength === 0) return blob;
    return new Blob([new Uint8Array(output)], { type: 'video/webm' });
  } catch {
    return blob;
  } finally {
    await Promise.allSettled([
      ffmpeg.deleteFile(inputName),
      ffmpeg.deleteFile(outputName),
    ]);
  }
}

async function recordPlayableVideoClip(
  file: File,
  selection: VideoSegmentSelection,
  onProgress?: (progress: number) => void
) {
  if (typeof MediaRecorder === 'undefined') {
    throw new Error('Your browser does not support local video trimming.');
  }

  const mimeType = getRecorderMimeType();
  if (!mimeType) {
    throw new Error('Your browser cannot create a compatible local video clip.');
  }

  const sourceUrl = URL.createObjectURL(file);
  const video = document.createElement('video');
  video.src = sourceUrl;
  video.muted = true;
  video.playsInline = true;
  video.preload = 'auto';

  let stream: MediaStream | null = null;
  let animationFrame = 0;

  try {
    if (video.readyState < HTMLMediaElement.HAVE_METADATA) {
      await waitForMediaEvent(video, 'loadedmetadata');
    }
    if (video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
      await waitForMediaEvent(video, 'loadeddata');
    }

    const clipEnd = Math.min(
      video.duration,
      selection.startSeconds + selection.durationSeconds
    );
    const clipStart = Math.min(selection.startSeconds, clipEnd);
    if (Math.abs(video.currentTime - clipStart) > 0.01) {
      video.currentTime = clipStart;
      await waitForMediaEvent(video, 'seeked');
    }

    const maxWidth = 1280;
    const scale = Math.min(1, maxWidth / Math.max(1, video.videoWidth));
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(2, Math.round((video.videoWidth * scale) / 2) * 2);
    canvas.height = Math.max(2, Math.round((video.videoHeight * scale) / 2) * 2);
    const context = canvas.getContext('2d', { alpha: false });
    if (!context) {
      throw new Error('The browser could not prepare the selected video frames.');
    }

    stream = canvas.captureStream(25);
    const recorder = new MediaRecorder(stream, {
      mimeType,
      videoBitsPerSecond: 4_000_000,
    });
    const chunks: Blob[] = [];
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.push(event.data);
    };
    const stopped = new Promise<void>((resolve, reject) => {
      recorder.onstop = () => resolve();
      recorder.onerror = () => reject(new Error('Local video recording failed.'));
    });

    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    recorder.start(250);
    await video.play();

    await new Promise<void>((resolve, reject) => {
      const timeout = window.setTimeout(() => {
        reject(new Error('Local video trimming timed out.'));
      }, (selection.durationSeconds + 15) * 1000);

      const drawFrame = () => {
        context.drawImage(video, 0, 0, canvas.width, canvas.height);
        const elapsed = Math.max(0, video.currentTime - selection.startSeconds);
        onProgress?.(Math.min(1, elapsed / selection.durationSeconds));

        if (video.ended || video.currentTime >= clipEnd) {
          window.clearTimeout(timeout);
          resolve();
          return;
        }
        animationFrame = window.requestAnimationFrame(drawFrame);
      };
      animationFrame = window.requestAnimationFrame(drawFrame);
    });

    video.pause();
    recorder.stop();
    await stopped;

    const blob = new Blob(chunks, { type: 'video/webm' });
    if (blob.size === 0) {
      throw new Error('The locally recorded clip is empty.');
    }
    const normalizedBlob = await normalizeRecordedWebm(blob);
    return new File([normalizedBlob], clippedFilename(file.name, selection, 'webm'), {
      type: 'video/webm',
      lastModified: Date.now(),
    });
  } finally {
    video.pause();
    video.removeAttribute('src');
    video.load();
    if (animationFrame) window.cancelAnimationFrame(animationFrame);
    stream?.getTracks().forEach((track) => track.stop());
    URL.revokeObjectURL(sourceUrl);
  }
}

export async function trimVideoClip(
  file: File,
  selection: VideoSegmentSelection,
  onProgress?: (progress: number) => void
) {
  try {
    return await recordPlayableVideoClip(file, selection, onProgress);
  } catch {
    onProgress?.(0);
    try {
      return await trimWithFFmpeg(file, selection, onProgress);
    } catch {
      throw new Error(
        'This video cannot be decoded locally. Try opening it in the preview before analyzing.'
      );
    }
  }
}

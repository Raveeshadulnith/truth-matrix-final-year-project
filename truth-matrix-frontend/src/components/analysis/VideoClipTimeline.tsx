import { useRef, type KeyboardEvent, type PointerEvent } from 'react';
import { MoveHorizontal } from 'lucide-react';

const MAX_SEGMENT_SECONDS = 30;
const MIN_SEGMENT_SECONDS = 1;

interface VideoClipTimelineProps {
  duration: number | null;
  start: number;
  end: number;
  onChange: (start: number, end: number, previewTime: number) => void;
}

interface DragState {
  pointerId: number;
  clientX: number;
  start: number;
  end: number;
}

function formatTime(seconds: number) {
  const safeSeconds = Math.max(0, seconds);
  const minutes = Math.floor(safeSeconds / 60);
  const remainder = Math.floor(safeSeconds % 60).toString().padStart(2, '0');
  return `${minutes}:${remainder}`;
}

export function VideoClipTimeline({
  duration,
  start,
  end,
  onChange,
}: VideoClipTimelineProps) {
  const timelineRef = useRef<HTMLDivElement | null>(null);
  const dragStateRef = useRef<DragState | null>(null);
  const clipDuration = Math.max(0, end - start);
  const startPercent = duration ? (start / duration) * 100 : 0;
  const endPercent = duration ? (end / duration) * 100 : 0;
  const midpointPercent = (startPercent + endPercent) / 2;

  const updateStart = (rawStart: number) => {
    if (duration === null) return;
    const minimumDuration = Math.min(MIN_SEGMENT_SECONDS, duration);
    const nextStart = Math.max(0, Math.min(rawStart, duration - minimumDuration));
    let nextEnd = end;

    if (nextStart >= end - minimumDuration) {
      nextEnd = Math.min(duration, nextStart + minimumDuration);
    } else if (end - nextStart > MAX_SEGMENT_SECONDS) {
      nextEnd = nextStart + MAX_SEGMENT_SECONDS;
    }

    onChange(nextStart, nextEnd, nextStart);
  };

  const updateEnd = (rawEnd: number) => {
    if (duration === null) return;
    const minimumDuration = Math.min(MIN_SEGMENT_SECONDS, duration);
    const nextEnd = Math.max(
      start + minimumDuration,
      Math.min(rawEnd, duration, start + MAX_SEGMENT_SECONDS)
    );
    onChange(start, nextEnd, Math.max(start, nextEnd - 0.05));
  };

  const moveClip = (rawStart: number) => {
    if (duration === null) return;
    const nextStart = Math.max(0, Math.min(rawStart, duration - clipDuration));
    onChange(nextStart, nextStart + clipDuration, nextStart);
  };

  const handleMovePointerDown = (event: PointerEvent<HTMLButtonElement>) => {
    if (duration === null) return;
    dragStateRef.current = {
      pointerId: event.pointerId,
      clientX: event.clientX,
      start,
      end,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const handleMovePointerMove = (event: PointerEvent<HTMLButtonElement>) => {
    const dragState = dragStateRef.current;
    const timelineWidth = timelineRef.current?.getBoundingClientRect().width;
    if (!dragState || !timelineWidth || duration === null) return;

    const deltaSeconds = ((event.clientX - dragState.clientX) / timelineWidth) * duration;
    const draggedDuration = dragState.end - dragState.start;
    const nextStart = Math.max(
      0,
      Math.min(dragState.start + deltaSeconds, duration - draggedDuration)
    );
    onChange(nextStart, nextStart + draggedDuration, nextStart);
  };

  const handleMovePointerEnd = (event: PointerEvent<HTMLButtonElement>) => {
    if (dragStateRef.current?.pointerId === event.pointerId) {
      dragStateRef.current = null;
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

  const handleMoveKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (duration === null) return;
    const step = event.shiftKey ? 1 : 0.1;

    if (event.key === 'ArrowLeft') {
      event.preventDefault();
      moveClip(start - step);
    } else if (event.key === 'ArrowRight') {
      event.preventDefault();
      moveClip(start + step);
    } else if (event.key === 'Home') {
      event.preventDefault();
      moveClip(0);
    } else if (event.key === 'End') {
      event.preventDefault();
      moveClip(duration - clipDuration);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">
          Select clip range
        </p>
        <span className="rounded-md bg-cyan-50 px-2 py-1 text-xs font-bold tabular-nums text-cyan-700 dark:bg-cyan-400/10 dark:text-neon-cyan">
          {clipDuration.toFixed(1)}s / 30s max
        </span>
      </div>

      <div
        ref={timelineRef}
        className="relative mx-auto h-14 w-[88%] max-w-sm select-none touch-none"
      >
        <div className="absolute inset-x-0 top-3 h-2 -translate-y-1/2 rounded bg-slate-200 dark:bg-navy-700" />
        <div
          className="absolute top-3 h-2 -translate-y-1/2 rounded bg-cyan-500"
          style={{ left: `${startPercent}%`, width: `${endPercent - startPercent}%` }}
        />
        <button
          type="button"
          aria-label="Move selected clip"
          title="Drag to move the selected clip"
          disabled={duration === null}
          onPointerDown={handleMovePointerDown}
          onPointerMove={handleMovePointerMove}
          onPointerUp={handleMovePointerEnd}
          onPointerCancel={handleMovePointerEnd}
          onKeyDown={handleMoveKeyDown}
          className="video-trim-window absolute top-7 z-10 flex h-5 w-9 -translate-x-1/2 items-center justify-center bg-cyan-600 text-white disabled:cursor-not-allowed"
          style={{ left: `${midpointPercent}%` }}
        >
          <MoveHorizontal className="h-4 w-4 shrink-0" aria-hidden="true" />
        </button>
        <input
          aria-label="Clip start time"
          type="range"
          min="0"
          max={duration || 0}
          step="0.1"
          value={start}
          onChange={(event) => updateStart(Number(event.target.value))}
          disabled={duration === null}
          className="video-trim-range video-trim-range-start absolute inset-x-0 top-3 w-full -translate-y-1/2"
        />
        <input
          aria-label="Clip end time"
          type="range"
          min="0"
          max={duration || 0}
          step="0.1"
          value={end}
          onChange={(event) => updateEnd(Number(event.target.value))}
          disabled={duration === null}
          className="video-trim-range video-trim-range-end absolute inset-x-0 top-3 w-full -translate-y-1/2"
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <label className="text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
          Start
          <input
            type="number"
            min="0"
            max={duration || 0}
            step="0.1"
            value={start.toFixed(1)}
            onChange={(event) => updateStart(Number(event.target.value))}
            className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold tabular-nums text-slate-900 dark:border-navy-600 dark:bg-navy-900 dark:text-white"
          />
        </label>
        <label className="text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
          End
          <input
            type="number"
            min="0"
            max={duration || 0}
            step="0.1"
            value={end.toFixed(1)}
            onChange={(event) => updateEnd(Number(event.target.value))}
            className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold tabular-nums text-slate-900 dark:border-navy-600 dark:bg-navy-900 dark:text-white"
          />
        </label>
      </div>

      <div className="flex justify-between text-xs text-slate-500 dark:text-slate-400">
        <span>0:00</span>
        <span className="font-semibold text-slate-700 dark:text-slate-200">
          {formatTime(start)} - {formatTime(end)}
        </span>
        <span>{duration === null ? '--:--' : formatTime(duration)}</span>
      </div>
    </div>
  );
}

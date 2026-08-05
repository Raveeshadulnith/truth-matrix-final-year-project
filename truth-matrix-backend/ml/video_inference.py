"""Video deepfake inference using the local Keras .h5 frame model.

The configured model is:
    ml/models/deepfake-detection-video-model1.h5

This HDF5 model is a Keras Conv2D image classifier with a single sigmoid
output. Video analysis samples frames from the uploaded video, runs the frame
classifier on each sampled frame, aggregates the frame probabilities, and
returns the same API contract used by the frontend.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# This venv uses Python 3.14, so standalone Keras is the compatible loader here.
# Standalone Keras can run this model on the already-installed PyTorch backend.
os.environ.setdefault("KERAS_BACKEND", os.getenv("VIDEO_KERAS_BACKEND", "torch"))

MODEL_PATH = Path(
    os.getenv(
        "VIDEO_KERAS_MODEL_PATH",
        str(Path(__file__).resolve().parent / "models" / "deepfake-detection-video-model1.h5"),
    )
)

LABELS = ["Authentic", "Suspected Deepfake"]
DEFAULT_NUM_FRAMES = 16
DEFAULT_FRAME_SIZE = 224
DEFAULT_FAKE_THRESHOLD = 0.50
DEFAULT_MAX_DECODE_FRAMES = 50_000

_model = None
_model_input: Optional[dict] = None
_keras = None
_load_lock = threading.Lock()
_predict_lock = threading.Lock()


class VideoInputError(ValueError):
    """Raised when an uploaded file cannot be decoded as a usable video."""


def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    value = os.getenv(name)
    if value is None:
        return default

    try:
        parsed = int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc

    if parsed < minimum:
        raise RuntimeError(f"{name} must be >= {minimum}")
    return parsed


def _env_float(name: str, default: float, *, minimum: float = 0.0, maximum: float = 1.0) -> float:
    value = os.getenv(name)
    if value is None:
        return default

    try:
        parsed = float(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a number") from exc

    if not minimum <= parsed <= maximum:
        raise RuntimeError(f"{name} must be between {minimum} and {maximum}")
    return parsed


def _fake_threshold() -> float:
    return _env_float("VIDEO_FAKE_THRESHOLD", DEFAULT_FAKE_THRESHOLD)


def _num_frames() -> int:
    return _env_int("VIDEO_NUM_FRAMES", DEFAULT_NUM_FRAMES, minimum=1)


def _default_frame_size() -> int:
    return _env_int("VIDEO_FRAME_SIZE", DEFAULT_FRAME_SIZE, minimum=32)


def _max_decode_frames() -> int:
    return _env_int("VIDEO_MAX_DECODE_FRAMES", DEFAULT_MAX_DECODE_FRAMES)


def _sigmoid_score_means_fake() -> bool:
    configured = os.getenv("VIDEO_SIGMOID_FAKE_VALUE", "1").strip()
    if configured not in {"0", "1"}:
        raise RuntimeError("VIDEO_SIGMOID_FAKE_VALUE must be 0 or 1")
    return configured == "1"


def _fake_class_index(output_width: int) -> int:
    configured = os.getenv("VIDEO_FAKE_CLASS_INDEX", "1").strip()
    try:
        value = int(configured)
    except ValueError as exc:
        raise RuntimeError("VIDEO_FAKE_CLASS_INDEX must be an integer") from exc

    if value < 0 or value >= output_width:
        raise RuntimeError(
            f"VIDEO_FAKE_CLASS_INDEX must be between 0 and {output_width - 1}"
        )
    return value


def _import_keras():
    global _keras
    if _keras is not None:
        return _keras

    try:
        import keras
    except ImportError as exc:
        raise RuntimeError(
            "Keras and h5py are required to run the local .h5 video model. "
            "Activate truth-matrix-backend/venv and run: pip install -r requirements.txt"
        ) from exc

    _keras = keras
    return keras


def _normalise_input_shape(input_shape) -> Tuple[Optional[int], ...]:
    if isinstance(input_shape, list):
        input_shape = input_shape[0]
    return tuple(input_shape)


def _resolve_model_input(model) -> dict:
    input_shape = _normalise_input_shape(model.input_shape)
    if len(input_shape) != 4:
        raise RuntimeError(
            f"Video Keras model must accept one image tensor, got input_shape={input_shape}"
        )

    channels_first = input_shape[1] in (1, 3)
    channels_last = input_shape[-1] in (1, 3) or (
        input_shape[-1] is None and not channels_first
    )
    if not channels_last and not channels_first:
        raise RuntimeError(
            f"Video Keras model input must have 1 or 3 channels, got input_shape={input_shape}"
        )

    if channels_last:
        height = input_shape[1] or _default_frame_size()
        width = input_shape[2] or _default_frame_size()
        channels = input_shape[3] or 3
        data_format = "channels_last"
    else:
        channels = input_shape[1]
        height = input_shape[2] or _default_frame_size()
        width = input_shape[3] or _default_frame_size()
        data_format = "channels_first"

    if channels != 3:
        raise RuntimeError(
            f"Video Keras model must use RGB frames with 3 channels, got {channels}"
        )

    return {
        "shape": input_shape,
        "height": int(height),
        "width": int(width),
        "data_format": data_format,
    }


def _load_model():
    global _model, _model_input
    if _model is not None and _model_input is not None:
        return _model, _model_input

    with _load_lock:
        if _model is not None and _model_input is not None:
            return _model, _model_input
        if not MODEL_PATH.is_file():
            raise FileNotFoundError(f"Video model not found at '{MODEL_PATH}'")

        keras = _import_keras()
        logger.info("Loading Keras video model from %s", MODEL_PATH)
        model = keras.models.load_model(str(MODEL_PATH), compile=False)
        model_input = _resolve_model_input(model)

        warmup = np.zeros(
            (1, model_input["height"], model_input["width"], 3),
            dtype=np.float32,
        )
        if model_input["data_format"] == "channels_first":
            warmup = np.transpose(warmup, (0, 3, 1, 2))
        model.predict(warmup, verbose=0)

        _model = model
        _model_input = model_input
        logger.info(
            "Keras video model ready: backend=%s input_shape=%s output_shape=%s",
            os.getenv("KERAS_BACKEND"),
            model.input_shape,
            model.output_shape,
        )
        return _model, _model_input


def _read_frame_at(cap, frame_index: int) -> Optional[np.ndarray]:
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_index))
    ok, frame = cap.read()
    if not ok or frame is None or frame.size == 0:
        return None
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def _positive_number(value: float) -> Optional[float]:
    return float(value) if np.isfinite(value) and value > 0 else None


def _video_metadata(cap: cv2.VideoCapture) -> Dict[str, Union[int, float, None]]:
    fps = _positive_number(cap.get(cv2.CAP_PROP_FPS))
    frame_count_value = _positive_number(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width_value = _positive_number(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height_value = _positive_number(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count = int(frame_count_value) if frame_count_value else None
    return {
        "duration_seconds": round(frame_count / fps, 3) if frame_count and fps else None,
        "fps": round(fps, 3) if fps else None,
        "width": int(width_value) if width_value else None,
        "height": int(height_value) if height_value else None,
        "total_frames": frame_count,
    }


def _stream_sample_frames(
    cap: cv2.VideoCapture, n: int
) -> Tuple[List[np.ndarray], int]:
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    samples: List[Tuple[int, np.ndarray]] = []
    seen = 0
    random = np.random.default_rng(0)

    while seen < _max_decode_frames():
        ok, frame = cap.read()
        if not ok or frame is None:
            break
        if frame.size == 0:
            continue

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        if len(samples) < n:
            samples.append((seen, rgb))
        else:
            replacement = int(random.integers(0, seen + 1))
            if replacement < n:
                samples[replacement] = (seen, rgb)
        seen += 1

    samples.sort(key=lambda item: item[0])
    return [frame for _, frame in samples], seen


def _extract_frames(
    video_path: str, n: int
) -> Tuple[List[np.ndarray], Dict[str, Union[int, float, None]]]:
    path = Path(video_path)
    if not path.is_file() or path.stat().st_size == 0:
        raise VideoInputError("The uploaded video is empty or missing.")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        cap.release()
        raise VideoInputError("The uploaded file is not a supported or readable video.")

    try:
        metadata = _video_metadata(cap)
        total = metadata["total_frames"]
        frames: List[np.ndarray] = []

        if isinstance(total, int) and total > 0:
            target_count = min(n, total)
            indices = np.unique(
                np.linspace(0, total - 1, target_count, dtype=int)
            )
            for index in indices:
                frame = _read_frame_at(cap, int(index))
                if frame is not None:
                    frames.append(frame)
            if len(frames) < target_count:
                sequential_frames, _ = _stream_sample_frames(cap, n)
                if sequential_frames:
                    frames = sequential_frames

        if not frames:
            frames, decoded_count = _stream_sample_frames(cap, n)
            if metadata["total_frames"] is None and decoded_count:
                metadata["total_frames"] = decoded_count
                fps = metadata["fps"]
                if isinstance(fps, float):
                    metadata["duration_seconds"] = round(decoded_count / fps, 3)

        if not frames:
            raise VideoInputError("No decodable frames were found in the uploaded video.")

        if metadata["width"] is None or metadata["height"] is None:
            metadata["height"], metadata["width"] = frames[0].shape[:2]
        return frames, metadata
    finally:
        cap.release()


def _preprocess_frames(frames: List[np.ndarray], model_input: dict) -> np.ndarray:
    resized_frames = []
    width = model_input["width"]
    height = model_input["height"]

    for frame in frames:
        resized = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
        arr = resized.astype(np.float32) / 255.0
        resized_frames.append(arr)

    batch = np.stack(resized_frames, axis=0)
    if model_input["data_format"] == "channels_first":
        batch = np.transpose(batch, (0, 3, 1, 2))
    return batch.astype(np.float32)


def _softmax(logits: np.ndarray) -> np.ndarray:
    logits = logits - np.max(logits, axis=1, keepdims=True)
    exp = np.exp(logits)
    return exp / np.sum(exp, axis=1, keepdims=True)


def _frame_fake_probabilities(predictions: np.ndarray, frame_count: int) -> np.ndarray:
    preds = np.asarray(predictions, dtype=np.float32)

    if preds.ndim == 0:
        preds = preds.reshape(1, 1)
    elif preds.ndim == 1:
        preds = preds.reshape(-1, 1)
    elif preds.ndim > 2:
        preds = preds.reshape(preds.shape[0], -1)

    if preds.shape[0] != frame_count:
        if preds.size == frame_count:
            preds = preds.reshape(frame_count, 1)
        else:
            raise RuntimeError(
                f"Model returned {preds.shape[0]} predictions for {frame_count} frames"
            )

    if preds.shape[1] == 1:
        scores = preds[:, 0]
        if np.any(scores < 0.0) or np.any(scores > 1.0):
            scores = 1.0 / (1.0 + np.exp(-np.clip(scores, -80.0, 80.0)))
        if not _sigmoid_score_means_fake():
            scores = 1.0 - scores
        return np.clip(scores, 0.0, 1.0)

    probs = preds
    row_sums = probs.sum(axis=1)
    if np.any(probs < 0.0) or np.any(probs > 1.0) or not np.allclose(row_sums, 1.0, atol=1e-3):
        probs = _softmax(probs)

    return np.clip(probs[:, _fake_class_index(probs.shape[1])], 0.0, 1.0)


def analyze_video(video_path: str) -> Dict[str, Any]:
    """Analyze sampled RGB frames and return video-level probabilities."""
    model, model_input = _load_model()
    frames, metadata = _extract_frames(video_path, _num_frames())
    batch = _preprocess_frames(frames, model_input)

    try:
        with _predict_lock:
            predictions = model.predict(batch, verbose=0)
        frame_fake_probs = _frame_fake_probabilities(predictions, len(frames))
    except Exception:
        logger.exception("Video model prediction failed")
        raise

    fake_prob = float(np.mean(frame_fake_probs))
    authentic_prob = 1.0 - fake_prob
    is_fake = fake_prob >= _fake_threshold()
    label = LABELS[1] if is_fake else LABELS[0]
    confidence = fake_prob if is_fake else authentic_prob

    explanation = (
        f"The Keras video model analyzed {len(frames)} frames sampled across the "
        f"video and averaged their predictions to a {fake_prob:.1%} deepfake "
        f"probability. The sampled frame scores ranged from "
        f"{float(np.min(frame_fake_probs)):.1%} to "
        f"{float(np.max(frame_fake_probs)):.1%}."
    )

    return {
        "media_type": "video",
        "label": label,
        "confidence": round(confidence * 100.0, 2),
        "fake_probability": round(fake_prob * 100.0, 2),
        "authentic_probability": round(authentic_prob * 100.0, 2),
        "frames_analyzed": len(frames),
        "video_metadata": metadata,
        "explanation": explanation,
    }

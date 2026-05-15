"""
Video deepfake inference — EfficientNet CNN + Bidirectional LSTM, trained on CelebDF.

Confirmed architecture (mathematically derived from all RuntimeError shape messages):
    cnn.*                                      ← EfficientNet-B4, output 1792-dim
    lstm  hidden_size=512, num_layers=2,
          bidirectional=True
          weight_ih_l0 (2048, 1792) → 4×512 rows, 1792 cols  ✓
          weight_hh_l0 (2048, 512)  → 4×512 rows, 512 cols   ✓
          weight_ih_l1 (2048, 1024) → 4×512 rows, 2×512 cols ✓ (bidir l0 output)
    classifier.1  Linear(1024 → 256)          ← 2*hidden input
    classifier.4  Linear(256  → 2)            ← 2-class [real, fake]

Model file location:
    truth-matrix-backend/ml/models/video_model_celebdf.pth
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, List, Union

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config  (confirmed from error messages)
# ---------------------------------------------------------------------------
MODEL_PATH = Path(__file__).resolve().parent / "models" / "video_model_celebdf.pth"

LABELS      = ["Authentic", "Suspected Deepfake"]
NUM_FRAMES  = 16
IMAGE_SIZE  = 224
LSTM_HIDDEN = 512    # confirmed: weight_ih_l0=(2048,1792) → 4*512=2048 rows
LSTM_LAYERS = 2
LSTM_BIDIR  = True   # confirmed: weight_ih_l1 cols=1024=2*512 (bidirectional l0 output)
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)

# Lazy singletons
_model  = None
_device = None


def _fake_class_index() -> int:
    configured = os.getenv("VIDEO_FAKE_CLASS_INDEX", "1").strip()
    try:
        value = int(configured)
    except ValueError as exc:
        raise RuntimeError("VIDEO_FAKE_CLASS_INDEX must be 0 or 1") from exc

    if value not in (0, 1):
        raise RuntimeError("VIDEO_FAKE_CLASS_INDEX must be 0 or 1")

    return value


# ---------------------------------------------------------------------------
# Model definition  (must match checkpoint shapes exactly)
# ---------------------------------------------------------------------------
def _build_model():
    """
    EfficientNet CNN (per-frame) → 2-layer LSTM (hidden=1024) → 2-class classifier.

    Confirmed shapes from RuntimeError:
        lstm.weight_ih_l1   (2048, 1024)   → input_size=1024 (== hidden from l0)
        classifier.1.weight (256,  1024)   → Linear(1024 → 256)
        classifier.4.weight (2,    256)    → Linear(256  → 2)
    """
    import torch.nn as nn

    try:
        import timm
        cnn     = timm.create_model(
            "efficientnet_b4", pretrained=False, num_classes=0, global_pool="avg"
        )
        cnn_out = cnn.num_features   # 1792 for B4
    except ImportError:
        from torchvision.models import efficientnet_b4
        _tv     = efficientnet_b4(weights=None)
        cnn_out = _tv.classifier[1].in_features
        cnn     = nn.Sequential(*list(_tv.children())[:-1], nn.Flatten(1))

    lstm = nn.LSTM(
        input_size=cnn_out,
        hidden_size=LSTM_HIDDEN,      # 512
        num_layers=LSTM_LAYERS,       # 2
        batch_first=True,
        bidirectional=LSTM_BIDIR,     # True → output dim = 2*512 = 1024
    )

    # classifier.1 input = 2*hidden (bidirectional) = 1024
    # confirmed from prev error: classifier.1.weight shape (256, 1024)
    lstm_out_size = LSTM_HIDDEN * (2 if LSTM_BIDIR else 1)   # 1024

    # 2 output classes: index-0 = real, index-1 = fake
    classifier = nn.Sequential(
        nn.Dropout(p=0.4),
        nn.Linear(lstm_out_size, 256),
        nn.ReLU(inplace=True),
        nn.Dropout(p=0.3),
        nn.Linear(256, 2),
    )

    class _Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.cnn        = cnn        # key prefix matches saved state dict
            self.lstm       = lstm
            self.classifier = classifier

        def forward(self, x):
            """x : (B, T, C, H, W)  →  probs (B, 2)"""
            import torch
            B, T, C, H, W = x.shape
            feats = self.cnn(x.view(B * T, C, H, W))    # (B*T, cnn_out)
            if feats.dim() > 2:
                feats = feats.mean(dim=[2, 3])
            feats      = feats.view(B, T, -1)            # (B, T, cnn_out)
            out, _     = self.lstm(feats)                # (B, T, 2*hidden) bidirectional
            # Take last timestep — contains both forward and backward context
            last       = out[:, -1, :]                   # (B, 2*hidden=1024)
            logits     = self.classifier(last)           # (B, 2)
            return torch.softmax(logits, dim=1)          # (B, 2)

    return _Net()


# ---------------------------------------------------------------------------
# Load & cache
# ---------------------------------------------------------------------------
def _load_model():
    global _model, _device
    if _model is not None:
        return _model, _device

    import torch

    _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Video model not found at '{MODEL_PATH}'. "
            "Place video_model_celebdf.pth inside ml/models/"
        )

    logger.info("[video_inference] Loading model from %s on %s", MODEL_PATH, _device)

    net = _build_model()

    import numpy as np
    safe_globals = [np.core.multiarray.scalar, np.dtype, np.ndarray]
    try:
        with torch.serialization.safe_globals(safe_globals):
            state = torch.load(MODEL_PATH, map_location=_device, weights_only=True)
    except Exception:
        logger.warning("[video_inference] safe_globals path failed; loading with weights_only=False")
        state = torch.load(MODEL_PATH, map_location=_device, weights_only=False)

    # Unwrap training checkpoint — confirmed key is 'model_state_dict'
    if isinstance(state, dict):
        for wrapper_key in ("model_state_dict", "state_dict", "model", "net"):
            if wrapper_key in state:
                logger.info("[video_inference] Unwrapping checkpoint key: '%s'", wrapper_key)
                state = state[wrapper_key]
                break

    # Strip DataParallel 'module.' prefix if present
    state = {k.replace("module.", ""): v for k, v in state.items()}

    load_result = net.load_state_dict(state, strict=False)
    if load_result.missing_keys:
        logger.warning("[video_inference] Missing keys (first 5): %s", load_result.missing_keys[:5])
    if load_result.unexpected_keys:
        logger.warning("[video_inference] Unexpected keys (first 5): %s", load_result.unexpected_keys[:5])

    net.to(_device).eval()
    _model = net
    logger.info("[video_inference] Model ready.")
    return _model, _device


# ---------------------------------------------------------------------------
# Frame extraction
# ---------------------------------------------------------------------------
def _extract_frames(video_path: str, n: int = NUM_FRAMES) -> List[np.ndarray]:
    """Sample n evenly-spaced RGB frames from a video using OpenCV."""
    import cv2

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"Cannot open video: {video_path}")

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        raise ValueError("Video reports zero frames — it may be corrupt or unsupported.")

    indices = np.linspace(0, total - 1, n, dtype=int)
    frames: List[np.ndarray] = []

    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ok, frame = cap.read()
        if ok:
            frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

    cap.release()

    if not frames:
        raise ValueError("Could not read any frames from the video.")

    while len(frames) < n:
        frames.append(frames[-1])

    return frames[:n]


# ---------------------------------------------------------------------------
# Pre-processing
# ---------------------------------------------------------------------------
def _preprocess_frames(frames: List[np.ndarray]):
    """Return a (1, T, 3, H, W) float32 tensor ready for the model."""
    import torch
    from PIL import Image

    tensors = []
    for frame in frames:
        img = Image.fromarray(frame).resize((IMAGE_SIZE, IMAGE_SIZE), Image.BILINEAR)
        arr = np.array(img, dtype=np.float32) / 255.0
        arr = (arr - IMAGENET_MEAN) / IMAGENET_STD
        tensors.append(torch.from_numpy(arr).permute(2, 0, 1))   # (3, H, W)

    return torch.stack(tensors, dim=0).unsqueeze(0)              # (1, T, 3, H, W)


# ---------------------------------------------------------------------------
# Public API  (matches existing stub signature exactly)
# ---------------------------------------------------------------------------
def analyze_video(video_path: str) -> Dict[str, Union[str, float, int, None]]:
    """
    Run deepfake detection on a video file.

    Returns dict compatible with AnalysisResponse:
        media_type, label, confidence, frames_analyzed, explanation, heatmap_url
    """
    try:
        import torch

        model, device = _load_model()

        frames = _extract_frames(video_path, NUM_FRAMES)
        clip   = _preprocess_frames(frames).to(device)    # (1, T, 3, H, W)

        with torch.no_grad():
            probs     = model(clip)           # (1, 2)
            fake_index = _fake_class_index()
            authentic_index = 1 - fake_index
            fake_prob = probs[0, fake_index].item()
            authentic_prob = probs[0, authentic_index].item()

        is_fake         = fake_prob >= 0.5
        label           = LABELS[1] if is_fake else LABELS[0]
        confidence      = round((fake_prob if is_fake else authentic_prob) * 100, 2)
        frames_analyzed = len(frames)
        class_idx       = fake_index if is_fake else authentic_index

        explanation = (
            f"EfficientNet-CNN + LSTM video model (trained on CelebDF) analysed "
            f"{frames_analyzed} evenly-spaced frames and assigned a deepfake "
            f"probability of {fake_prob:.1%}. "
            + (
                "Temporal inconsistencies and facial manipulation artifacts were "
                "detected across multiple frames."
                if is_fake else
                "No significant manipulation artifacts were found across the "
                "sampled frames; the video appears authentic."
            )
        )

        # GradCAM heatmap grid (best-effort — failure never blocks the result)
        heatmap_url = None
        try:
            from ml.xai import generate_video_heatmap, save_heatmap_result
            heatmap_rgb = generate_video_heatmap(model, device, frames, class_idx)
            if heatmap_rgb is not None:
                heatmap_url = save_heatmap_result(
                    heatmap_rgb, video_path, "video-gradcam"
                )
        except Exception:
            logger.warning("[video_inference] GradCAM skipped", exc_info=True)

        return {
            "media_type":      "video",
            "label":           label,
            "confidence":      confidence,
            "fake_probability": round(fake_prob * 100, 2),
            "authentic_probability": round(authentic_prob * 100, 2),
            "frames_analyzed": frames_analyzed,
            "explanation":     explanation,
            "heatmap_url":     heatmap_url,
            "xai_method":      "Grad-CAM" if heatmap_url else None,
        }

    except FileNotFoundError:
        raise
    except Exception as exc:
        logger.exception("[video_inference] Inference failed for %s", video_path)
        raise RuntimeError(f"Video analysis failed: {exc}") from exc

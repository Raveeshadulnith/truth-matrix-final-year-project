"""
Image deepfake inference — EfficientNet-B4 + 2-class classifier head.

Confirmed architecture (from size-mismatch errors in loading):
    backbone.*                               ← EfficientNet-B4 feature extractor
    classifier.1  Linear(1792 → 256)
    classifier.4  Linear(256  → 2)          ← 2-class output [real, fake]

Output: softmax([real_score, fake_score]) — index 1 is the deepfake probability.

Model file location:
    truth-matrix-backend/ml/models/image_model.pth
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Union

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MODEL_PATH = Path(__file__).resolve().parent / "models" / "image_model.pth"

LABELS = ["Authentic", "Suspected Deepfake"]
IMAGE_SIZE = 224
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)

# Lazy singletons
_model  = None
_device = None


# ---------------------------------------------------------------------------
# Model definition  (must match checkpoint shapes exactly)
# ---------------------------------------------------------------------------
def _build_model():
    """
    EfficientNet-B4 backbone + 2-class classifier head.

    Confirmed shapes from RuntimeError:
        classifier.1.weight  (256, in_features)   ← Linear(in_features → 256)
        classifier.4.weight  (2,   256)            ← Linear(256 → 2)
    """
    import torch.nn as nn

    try:
        import timm
        backbone    = timm.create_model(
            "efficientnet_b4", pretrained=False, num_classes=0, global_pool="avg"
        )
        in_features = backbone.num_features   # 1792 for B4
    except ImportError:
        from torchvision.models import efficientnet_b4
        _tv         = efficientnet_b4(weights=None)
        in_features = _tv.classifier[1].in_features
        backbone    = nn.Sequential(*list(_tv.children())[:-1], nn.Flatten(1))

    # 2 output classes: index-0 = real, index-1 = fake
    classifier = nn.Sequential(
        nn.Dropout(p=0.4),
        nn.Linear(in_features, 256),
        nn.ReLU(inplace=True),
        nn.Dropout(p=0.3),
        nn.Linear(256, 2),
    )

    class _Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.backbone   = backbone
            self.classifier = classifier

        def forward(self, x):
            import torch
            feats = self.backbone(x)
            if feats.dim() > 2:
                feats = feats.mean(dim=[2, 3])
            logits = self.classifier(feats)          # (B, 2)
            probs  = torch.softmax(logits, dim=1)    # (B, 2)
            return probs                             # caller uses [:, 1] for fake prob

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
            f"Image model not found at '{MODEL_PATH}'. "
            "Place image_model.pth inside ml/models/"
        )

    logger.info("[image_inference] Loading model from %s on %s", MODEL_PATH, _device)

    net = _build_model()

    # These checkpoints contain numpy scalars — need safe_globals or weights_only=False
    import numpy as np
    safe_globals = [np.core.multiarray.scalar, np.dtype, np.ndarray]
    try:
        with torch.serialization.safe_globals(safe_globals):
            state = torch.load(MODEL_PATH, map_location=_device, weights_only=True)
    except Exception:
        logger.warning("[image_inference] safe_globals path failed; loading with weights_only=False")
        state = torch.load(MODEL_PATH, map_location=_device, weights_only=False)

    # Unwrap training checkpoint — confirmed key is 'model_state_dict'
    if isinstance(state, dict):
        for wrapper_key in ("model_state_dict", "state_dict", "model", "net"):
            if wrapper_key in state:
                logger.info("[image_inference] Unwrapping checkpoint key: '%s'", wrapper_key)
                state = state[wrapper_key]
                break

    # Strip DataParallel 'module.' prefix if present
    state = {k.replace("module.", ""): v for k, v in state.items()}

    load_result = net.load_state_dict(state, strict=False)
    if load_result.missing_keys:
        logger.warning("[image_inference] Missing keys (first 5): %s", load_result.missing_keys[:5])
    if load_result.unexpected_keys:
        logger.warning("[image_inference] Unexpected keys (first 5): %s", load_result.unexpected_keys[:5])

    net.to(_device).eval()
    _model = net
    logger.info("[image_inference] Model ready.")
    return _model, _device


# ---------------------------------------------------------------------------
# Pre-processing
# ---------------------------------------------------------------------------
def _preprocess(image_path: str):
    """Load an image and return a (1, 3, H, W) float32 tensor."""
    import torch
    from PIL import Image

    img    = Image.open(image_path).convert("RGB")
    img    = img.resize((IMAGE_SIZE, IMAGE_SIZE), Image.BILINEAR)
    arr    = np.array(img, dtype=np.float32) / 255.0
    arr    = (arr - IMAGENET_MEAN) / IMAGENET_STD
    tensor = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)   # (1, 3, H, W)
    return tensor


# ---------------------------------------------------------------------------
# Public API  (matches existing stub signature exactly)
# ---------------------------------------------------------------------------
def analyze_image(image_path: str) -> Dict[str, Union[str, float, None]]:
    """
    Run deepfake detection on a single image file.

    Returns dict compatible with AnalysisResponse:
        media_type, label, confidence, explanation, heatmap_url
    """
    try:
        import torch

        model, device = _load_model()
        tensor = _preprocess(image_path).to(device)

        with torch.no_grad():
            probs    = model(tensor)          # (1, 2)
            fake_prob = probs[0, 1].item()    # probability of class "fake"

        is_fake    = fake_prob >= 0.5
        label      = LABELS[1] if is_fake else LABELS[0]
        confidence = round((fake_prob if is_fake else 1.0 - fake_prob) * 100, 2)

        explanation = (
            f"EfficientNet-B4 image model assigned a deepfake probability of "
            f"{fake_prob:.1%}. "
            + (
                "Facial manipulation artifacts or GAN-generated patterns were "
                "detected in the image."
                if is_fake else
                "No significant manipulation artifacts were detected; "
                "the image appears authentic."
            )
        )

        return {
            "media_type":  "image",
            "label":       label,
            "confidence":  confidence,
            "explanation": explanation,
            "heatmap_url": None,
        }

    except FileNotFoundError:
        raise
    except Exception as exc:
        logger.exception("[image_inference] Inference failed for %s", image_path)
        raise RuntimeError(f"Image analysis failed: {exc}") from exc

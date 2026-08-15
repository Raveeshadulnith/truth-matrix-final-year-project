from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from PIL import Image, ImageOps, UnidentifiedImageError
from torch import nn
from torchvision import transforms
from transformers import CvtConfig, CvtForImageClassification

logger = logging.getLogger(__name__)

LABELS = ("Authentic", "Suspected Deepfake")
MODEL_VERSION = "cvt-13-model_epoch_24"
MODEL_ENV_VAR = "IMAGE_MODEL_WEIGHTS_PATH"
BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_WEIGHTS_PATH = (
    Path(__file__).resolve().parent
    / "models"
    / "Image-Detection"
    / "models"
    / "model_epoch_24.pth"
)

_PREPROCESS = transforms.Compose(
    [
        transforms.Resize((200, 200), antialias=True),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=(0.485, 0.456, 0.406),
            std=(0.229, 0.224, 0.225),
        ),
    ]
)


@dataclass(frozen=True)
class _ModelBundle:
    model: nn.Module
    device: torch.device
    weights_path: Path


_MODEL_BUNDLE: _ModelBundle | None = None
_MODEL_LOCK = threading.Lock()


class ImageModelUnavailableError(RuntimeError):
    pass


class InvalidImageError(ValueError):
    pass


class CvtBinaryClassifier(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.fc1 = nn.Linear(384, 256)
        self.mish1 = nn.Mish(inplace=False)
        self.norm1 = nn.BatchNorm1d(256)
        self.dropout1 = nn.Dropout(p=0.5)
        self.fc2 = nn.Linear(256, 128)
        self.mish2 = nn.Mish(inplace=False)
        self.norm2 = nn.BatchNorm1d(128)
        self.dropout2 = nn.Dropout(p=0.3)
        self.fc_out = nn.Linear(128, 2)

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        features = self.dropout1(self.norm1(self.mish1(self.fc1(features))))
        features = self.dropout2(self.norm2(self.mish2(self.fc2(features))))
        return self.fc_out(features)


def build_cvt13_binary_model() -> CvtForImageClassification:
    config = CvtConfig(num_labels=2)
    model = CvtForImageClassification(config)
    model.classifier = CvtBinaryClassifier()
    return model


def _configured_weights_path() -> Path:
    configured = os.getenv(MODEL_ENV_VAR, "").strip()
    if not configured:
        return DEFAULT_WEIGHTS_PATH.resolve()

    path = Path(configured).expanduser()
    if not path.is_absolute():
        path = BACKEND_DIR / path
    return path.resolve()


def _select_device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _load_model_bundle(weights_path: Path) -> _ModelBundle:
    if not weights_path.is_file():
        raise ImageModelUnavailableError(
            f"CvT-13 image model checkpoint was not found: {weights_path}. "
            f"Set {MODEL_ENV_VAR} to the model_epoch_24.pth location."
        )

    device = _select_device()
    model = build_cvt13_binary_model()

    try:
        checkpoint = torch.load(weights_path, map_location="cpu", weights_only=True)
    except Exception as exc:
        raise ImageModelUnavailableError(
            f"Could not read the CvT-13 image model checkpoint at {weights_path}: {exc}"
        ) from exc

    if not isinstance(checkpoint, dict) or "model_state_dict" not in checkpoint:
        raise ImageModelUnavailableError(
            "The CvT-13 checkpoint is incompatible: expected a mapping containing "
            "'model_state_dict'."
        )

    try:
        model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    except (RuntimeError, TypeError, ValueError) as exc:
        raise ImageModelUnavailableError(
            "The CvT-13 checkpoint is incompatible with the configured model "
            f"architecture: {exc}"
        ) from exc

    model.to(device)
    model.eval()
    logger.info("Loaded local %s image model on %s", MODEL_VERSION, device)
    return _ModelBundle(model=model, device=device, weights_path=weights_path)


def _get_model_bundle() -> _ModelBundle:
    global _MODEL_BUNDLE

    weights_path = _configured_weights_path()
    if _MODEL_BUNDLE is not None and _MODEL_BUNDLE.weights_path == weights_path:
        return _MODEL_BUNDLE

    with _MODEL_LOCK:
        if _MODEL_BUNDLE is None or _MODEL_BUNDLE.weights_path != weights_path:
            _MODEL_BUNDLE = _load_model_bundle(weights_path)
        return _MODEL_BUNDLE


def get_image_model_readiness() -> dict[str, Any]:
    bundle = _get_model_bundle()
    return {
        "status": "ready",
        "model_version": MODEL_VERSION,
        "device": bundle.device.type,
        "loaded": True,
    }


def _reset_model_cache_for_tests() -> None:
    global _MODEL_BUNDLE
    with _MODEL_LOCK:
        _MODEL_BUNDLE = None


def _preprocess_image(image_path: Path) -> torch.Tensor:
    if not image_path.is_file():
        raise FileNotFoundError(f"Image file was not found: {image_path}")

    try:
        with Image.open(image_path) as image:
            image.load()
            rgb_image = ImageOps.exif_transpose(image).convert("RGB")
            return _PREPROCESS(rgb_image).unsqueeze(0)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise InvalidImageError(
            f"Invalid or unreadable image file: {image_path.name}"
        ) from exc


def _prediction_result(probabilities: torch.Tensor) -> dict[str, Any]:
    if probabilities.ndim != 1 or probabilities.numel() != 2:
        raise RuntimeError(
            "The CvT-13 image model returned an invalid probability tensor; "
            "expected exactly two classes."
        )

    authentic_probability = float(probabilities[0].item())
    fake_probability = float(probabilities[1].item())
    predicted_class = int(torch.argmax(probabilities).item())
    label = LABELS[predicted_class]
    confidence = authentic_probability if predicted_class == 0 else fake_probability

    if predicted_class == 0:
        explanation = (
            "The local CvT-13 image model found stronger evidence that this image "
            "belongs to the real-image class."
        )
    else:
        explanation = (
            "The local CvT-13 image model found stronger evidence that this image "
            "belongs to the AI-generated image class."
        )

    return {
        "media_type": "image",
        "label": label,
        "confidence": round(confidence * 100.0, 2),
        "fake_probability": round(fake_probability * 100.0, 2),
        "authentic_probability": round(authentic_probability * 100.0, 2),
        "explanation": explanation,
        "heatmap_url": None,
        "xai_overlay_url": None,
        "xai_panel_url": None,
        "xai_method": None,
        "xai_target_class": None,
        "xai_predicted_class": None,
        "xai_layer": None,
        "xai_map_strength": None,
        "xai_error": None,
        "model_version": MODEL_VERSION,
    }


def analyze_image(image_path: str) -> dict[str, Any]:
    path = Path(image_path)
    try:
        image_tensor = _preprocess_image(path)
        bundle = _get_model_bundle()
        image_tensor = image_tensor.to(bundle.device)

        with torch.inference_mode():
            logits = bundle.model(image_tensor).logits
            probabilities = torch.softmax(logits, dim=1)[0].detach().cpu()

        return _prediction_result(probabilities)
    except FileNotFoundError:
        raise
    except InvalidImageError:
        raise
    except RuntimeError:
        logger.exception("Local CvT-13 image analysis failed for %s", path)
        raise
    except Exception as exc:
        logger.exception("Local CvT-13 image analysis failed for %s", path)
        raise RuntimeError(f"Image analysis failed: {exc}") from exc

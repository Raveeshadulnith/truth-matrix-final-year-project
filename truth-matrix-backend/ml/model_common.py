from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Tuple

import numpy as np
from dotenv import load_dotenv
from PIL import Image, ImageOps

try:
    import timm
    import torch
    from torch import nn
except ImportError:  # pragma: no cover - exercised only when setup is incomplete.
    timm = None
    torch = None
    nn = None


BASE_DIR = Path(__file__).resolve().parents[1]
MODELS_DIR = BASE_DIR / "models"
RESULTS_DIR = BASE_DIR / "results"

load_dotenv(BASE_DIR / ".env", encoding="utf-8-sig")

IMAGE_MODEL_FILENAME = "image_model.pth"
VIDEO_MODEL_FILENAME = "video_model_celebdf.pth"

IMAGE_NET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGE_NET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

AUTHENTIC_LABEL = "Authentic"
DEEPFAKE_LABEL = "Suspected Deepfake"


class ModelSetupError(RuntimeError):
    """Raised when a trained model cannot be loaded or used."""


class ModelNotAvailableError(RuntimeError):
    """Raised when a modality intentionally has no trained model yet."""


def ensure_ml_dependencies() -> None:
    if torch is None or nn is None or timm is None:
        raise ModelSetupError(
            "PyTorch, torchvision, and timm are required for trained model inference. "
            "Install backend dependencies with: pip install -r requirements.txt"
        )


def env_int(name: str, default: int, *, minimum: int = 1) -> int:
    value = os.getenv(name)
    if not value:
        return default

    try:
        parsed = int(value)
    except ValueError as exc:
        raise ModelSetupError(f"{name} must be an integer, got {value!r}") from exc

    if parsed < minimum:
        raise ModelSetupError(f"{name} must be greater than or equal to {minimum}")

    return parsed


def env_bool(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_float(
    name: str,
    default: float,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    value = os.getenv(name)
    if not value:
        return default

    try:
        parsed = float(value)
    except ValueError as exc:
        raise ModelSetupError(f"{name} must be a number, got {value!r}") from exc

    if minimum is not None and parsed < minimum:
        raise ModelSetupError(f"{name} must be greater than or equal to {minimum}")

    if maximum is not None and parsed > maximum:
        raise ModelSetupError(f"{name} must be less than or equal to {maximum}")

    return parsed


def configured_model_path(env_name: str, filename: str) -> Path:
    configured = os.getenv(env_name)
    if configured:
        path = Path(configured).expanduser()
        if not path.is_absolute():
            path = BASE_DIR / path
        return path.resolve()

    return MODELS_DIR / filename


def model_input_size() -> int:
    return env_int("MODEL_INPUT_SIZE", 224)


def image_model_input_size() -> int:
    return env_int("IMAGE_MODEL_INPUT_SIZE", model_input_size())


def video_frame_count() -> int:
    return env_int("VIDEO_FRAME_COUNT", 16)


def fake_class_index(env_name: str) -> int:
    value = env_int(env_name, env_int("MODEL_FAKE_CLASS_INDEX", 1, minimum=0), minimum=0)
    if value not in (0, 1):
        raise ModelSetupError(f"{env_name} must be 0 or 1")
    return value


def select_device():
    ensure_ml_dependencies()

    requested = os.getenv("MODEL_DEVICE", "").strip()
    if requested:
        if requested.startswith("cuda") and not torch.cuda.is_available():
            raise ModelSetupError(
                f"MODEL_DEVICE is set to {requested!r}, but CUDA is not available."
            )
        return torch.device(requested)

    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def load_checkpoint_state(path: Path):
    ensure_ml_dependencies()

    if not path.exists():
        raise ModelSetupError(
            f"Trained model file not found at {path}. Place the .pth file there "
            "or set the matching *_MODEL_PATH environment variable."
        )

    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    if isinstance(checkpoint, dict):
        return checkpoint.get("model_state_dict") or checkpoint.get("state_dict") or checkpoint

    if hasattr(checkpoint, "state_dict"):
        return checkpoint.state_dict()

    raise ModelSetupError(f"Unsupported checkpoint format in {path}")


if nn is not None:

    class ImageDeepfakeModel(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.backbone = timm.create_model(
                "efficientnet_b4",
                pretrained=False,
                num_classes=0,
            )
            self.classifier = nn.Sequential(
                nn.Dropout(0.3),
                nn.Linear(self.backbone.num_features, 256),
                nn.ReLU(inplace=True),
                nn.Dropout(0.3),
                nn.Linear(256, 2),
            )

        def forward(self, images):
            features = self.backbone(images)
            return self.classifier(features)


    class VideoDeepfakeModel(nn.Module):
        def __init__(self, pooling: str = "last") -> None:
            super().__init__()
            self.pooling = pooling
            self.cnn = timm.create_model(
                "efficientnet_b4",
                pretrained=False,
                num_classes=0,
            )
            self.lstm = nn.LSTM(
                input_size=self.cnn.num_features,
                hidden_size=512,
                num_layers=2,
                batch_first=True,
                bidirectional=True,
            )
            self.classifier = nn.Sequential(
                nn.Dropout(0.3),
                nn.Linear(1024, 256),
                nn.ReLU(inplace=True),
                nn.Dropout(0.3),
                nn.Linear(256, 2),
            )

        def forward(self, frames):
            batch_size, frame_count, channels, height, width = frames.shape
            flat_frames = frames.reshape(batch_size * frame_count, channels, height, width)
            features = self.cnn(flat_frames)
            features = features.reshape(batch_size, frame_count, -1)
            sequence, _ = self.lstm(features)

            if self.pooling == "mean":
                pooled = sequence.mean(dim=1)
            else:
                pooled = sequence[:, -1, :]

            return self.classifier(pooled)

else:
    ImageDeepfakeModel = None
    VideoDeepfakeModel = None


@lru_cache(maxsize=1)
def load_image_model():
    ensure_ml_dependencies()
    path = configured_model_path("IMAGE_MODEL_PATH", IMAGE_MODEL_FILENAME)
    device = select_device()
    model = ImageDeepfakeModel()
    state_dict = load_checkpoint_state(path)
    model.load_state_dict(state_dict, strict=True)
    model.to(device)
    model.eval()
    return model, device


@lru_cache(maxsize=1)
def load_video_model():
    ensure_ml_dependencies()
    path = configured_model_path("VIDEO_MODEL_PATH", VIDEO_MODEL_FILENAME)
    pooling = os.getenv("VIDEO_LSTM_POOLING", "last").strip().lower()
    if pooling not in {"last", "mean"}:
        raise ModelSetupError("VIDEO_LSTM_POOLING must be either 'last' or 'mean'")

    device = select_device()
    model = VideoDeepfakeModel(pooling=pooling)
    state_dict = load_checkpoint_state(path)
    model.load_state_dict(state_dict, strict=True)
    model.to(device)
    model.eval()
    return model, device


def preprocess_pil_image(image: Image.Image, size: int | None = None):
    ensure_ml_dependencies()

    image_size = size or model_input_size()
    resample = getattr(Image, "Resampling", Image).BICUBIC
    rgb_image = ImageOps.exif_transpose(image).convert("RGB")
    square_image = ImageOps.fit(rgb_image, (image_size, image_size), method=resample)
    array = np.asarray(square_image, dtype=np.float32) / 255.0
    array = (array - IMAGE_NET_MEAN) / IMAGE_NET_STD
    array = np.transpose(array, (2, 0, 1))
    return torch.from_numpy(array)


def preprocess_image_path(image_path: str, size: int | None = None) -> Tuple[object, Image.Image]:
    with Image.open(image_path) as image:
        rgb_image = ImageOps.exif_transpose(image).convert("RGB")
        return preprocess_pil_image(rgb_image, size=size), rgb_image


def prediction_payload(logits, media_type: str, fake_index_env: str, extra: dict | None = None):
    ensure_ml_dependencies()

    probabilities = torch.softmax(logits, dim=1)[0].detach().cpu()
    predicted_index = int(probabilities.argmax().item())
    fake_index = fake_class_index(fake_index_env)
    authentic_index = 1 - fake_index

    fake_probability = float(probabilities[fake_index].item() * 100)
    authentic_probability = float(probabilities[authentic_index].item() * 100)

    if predicted_index == fake_index:
        label = DEEPFAKE_LABEL
        confidence = fake_probability
        explanation = (
            f"The trained {media_type} model detected manipulation signals. "
            f"Deepfake probability: {fake_probability:.2f}%; "
            f"authentic probability: {authentic_probability:.2f}%."
        )
    else:
        label = AUTHENTIC_LABEL
        confidence = authentic_probability
        explanation = (
            f"The trained {media_type} model did not detect strong manipulation signals. "
            f"Authentic probability: {authentic_probability:.2f}%; "
            f"deepfake probability: {fake_probability:.2f}%."
        )

    payload = {
        "media_type": media_type,
        "label": label,
        "confidence": round(confidence, 2),
        "fake_probability": round(fake_probability, 2),
        "authentic_probability": round(authentic_probability, 2),
        "explanation": explanation,
    }

    if extra:
        payload.update(extra)

    return payload

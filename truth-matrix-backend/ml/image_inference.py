"""
Image deepfake inference using the local Hugging Face SigLIP checkpoint.

Model bundle:
    ml/models/config.json
    ml/models/preprocessor_config.json
    ml/models/model.safetensors

The local config defines labels as:
    0 -> Fake
    1 -> Real
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Tuple, Union

logger = logging.getLogger(__name__)

MODEL_DIR = Path(
    os.getenv(
        "IMAGE_HF_MODEL_DIR",
        str(Path(__file__).resolve().parent / "models"),
    )
)

LABELS = ["Authentic", "Suspected Deepfake"]
DEFAULT_FAKE_THRESHOLD = 0.70

_model = None
_processor = None
_device = None
_fake_index = None
_real_index = None


def _normalise_label(label: Any) -> str:
    return str(label or "").strip().lower().replace("_", " ")


def _resolve_label_indices(config) -> Tuple[int, int]:
    id2label = getattr(config, "id2label", {}) or {}
    label_lookup = {
        _normalise_label(label): int(index) for index, label in id2label.items()
    }

    fake_index = label_lookup.get("fake")
    real_index = label_lookup.get("real")

    if fake_index is None:
        fake_index = label_lookup.get("deepfake", label_lookup.get("manipulated"))
    if real_index is None:
        real_index = label_lookup.get("authentic", label_lookup.get("genuine"))

    if fake_index is None or real_index is None:
        logger.warning(
            "[image_inference] Could not infer label ids from config id2label=%s; "
            "falling back to Fake=0, Real=1",
            id2label,
        )
        fake_index, real_index = 0, 1

    return int(fake_index), int(real_index)


def _fake_threshold() -> float:
    configured = os.getenv("IMAGE_FAKE_THRESHOLD", str(DEFAULT_FAKE_THRESHOLD)).strip()
    try:
        threshold = float(configured)
    except ValueError:
        logger.warning(
            "[image_inference] Invalid IMAGE_FAKE_THRESHOLD=%r; using %.2f",
            configured,
            DEFAULT_FAKE_THRESHOLD,
        )
        return DEFAULT_FAKE_THRESHOLD

    if not 0.50 <= threshold <= 0.95:
        logger.warning(
            "[image_inference] IMAGE_FAKE_THRESHOLD must be between 0.50 and 0.95; "
            "using %.2f",
            DEFAULT_FAKE_THRESHOLD,
        )
        return DEFAULT_FAKE_THRESHOLD

    return threshold


def _calibrate_fake_probability(raw_fake_prob: float, threshold: float) -> float:
    """
    Map the model's raw fake score onto a calibrated 0..1 display probability.

    The chosen threshold becomes the 50% decision point. This prevents a weak
    fake lean, such as 0.52, from being presented as a confident fake verdict.
    """
    raw_fake_prob = max(0.0, min(1.0, raw_fake_prob))

    if raw_fake_prob < threshold:
        return 0.5 * (raw_fake_prob / threshold)

    remaining = max(1e-8, 1.0 - threshold)
    return 0.5 + 0.5 * ((raw_fake_prob - threshold) / remaining)


def _load_model():
    global _model, _processor, _device, _fake_index, _real_index

    if _model is not None and _processor is not None:
        return _model, _processor, _device, _fake_index, _real_index

    import torch
    from transformers import AutoImageProcessor, AutoModelForImageClassification
    from transformers.utils import logging as transformers_logging

    transformers_logging.set_verbosity_error()
    try:
        transformers_logging.disable_progress_bar()
    except AttributeError:
        pass

    required_files = ("config.json", "preprocessor_config.json", "model.safetensors")
    missing_files = [name for name in required_files if not (MODEL_DIR / name).exists()]
    if missing_files:
        missing = ", ".join(missing_files)
        raise FileNotFoundError(
            f"Image model bundle is incomplete in '{MODEL_DIR}'. Missing: {missing}"
        )

    _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("[image_inference] Loading SigLIP model from %s on %s", MODEL_DIR, _device)

    _processor = AutoImageProcessor.from_pretrained(
        MODEL_DIR,
        local_files_only=True,
    )
    _model = AutoModelForImageClassification.from_pretrained(
        MODEL_DIR,
        local_files_only=True,
    )
    _model.to(_device).eval()

    _fake_index, _real_index = _resolve_label_indices(_model.config)

    logger.info(
        "[image_inference] SigLIP model ready. fake_index=%s real_index=%s",
        _fake_index,
        _real_index,
    )
    return _model, _processor, _device, _fake_index, _real_index


def _open_rgb_image(image_path: str):
    from PIL import Image, ImageOps

    with Image.open(image_path) as image:
        return ImageOps.exif_transpose(image).convert("RGB")


def _predict_probabilities(image_path: str) -> Tuple[float, float]:
    import torch

    model, processor, device, fake_index, real_index = _load_model()
    image = _open_rgb_image(image_path)
    inputs = processor(images=image, return_tensors="pt")
    inputs = {key: value.to(device) for key, value in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)
        probs = torch.softmax(outputs.logits, dim=-1)[0]

    fake_prob = float(probs[fake_index].detach().cpu().item())
    real_prob = float(probs[real_index].detach().cpu().item())
    total = fake_prob + real_prob

    if total > 0:
        fake_prob /= total
        real_prob /= total

    return fake_prob, real_prob


def _build_explanation(fake_prob: float, is_fake: bool, threshold: float) -> str:
    if is_fake:
        return (
            "The local SigLIP image classification model detected visual patterns "
            "associated with manipulated imagery. After threshold calibration, it "
            f"assigned a deepfake probability of {fake_prob:.1%} using a "
            f"{threshold:.0%} fake-decision threshold. Review the highlighted XAI "
            "regions before trusting or sharing the image."
        )

    return (
        "The local SigLIP image classification model did not find strong visual "
        "manipulation signals. After threshold calibration, it assigned a deepfake "
        f"probability of {fake_prob:.1%} using a {threshold:.0%} fake-decision "
        "threshold. The image is classified as authentic by the model."
    )


def analyze_image(image_path: str) -> Dict[str, Union[str, float, None]]:
    """
    Run image deepfake detection and return a response compatible with
    schemas.response_schema.AnalysisResponse.
    """
    try:
        model, processor, device, fake_index, real_index = _load_model()
        raw_fake_prob, _raw_authentic_prob = _predict_probabilities(image_path)
        threshold = _fake_threshold()
        fake_prob = _calibrate_fake_probability(raw_fake_prob, threshold)
        authentic_prob = 1.0 - fake_prob

        is_fake = raw_fake_prob >= threshold
        label = LABELS[1] if is_fake else LABELS[0]
        confidence = round((fake_prob if is_fake else authentic_prob) * 100, 2)
        target_index = fake_index if is_fake else real_index
        target_class = "Fake" if is_fake else "Real"

        heatmap_url = None
        overlay_url = None
        xai_layer = None
        xai_map_strength = None
        xai_error = None

        try:
            from ml.xai import generate_siglip_image_xai, save_heatmap_result

            xai_result = generate_siglip_image_xai(
                model=model,
                processor=processor,
                device=device,
                image_path=image_path,
                class_idx=target_index,
            )

            if xai_result:
                heatmap_url = save_heatmap_result(
                    xai_result["heatmap_rgb"],
                    image_path,
                    "siglip-heatmap",
                )
                overlay_url = save_heatmap_result(
                    xai_result["overlay_rgb"],
                    image_path,
                    "siglip-overlay",
                )
                xai_layer = xai_result.get("target_layer")
                xai_map_strength = xai_result.get("map_strength")
            else:
                xai_error = "SigLIP saliency did not return a heatmap."
        except Exception as exc:
            xai_error = str(exc)
            logger.warning("[image_inference] SigLIP XAI skipped", exc_info=True)

        return {
            "media_type": "image",
            "label": label,
            "confidence": confidence,
            "fake_probability": round(fake_prob * 100, 2),
            "authentic_probability": round(authentic_prob * 100, 2),
            "explanation": _build_explanation(fake_prob, is_fake, threshold),
            "heatmap_url": heatmap_url,
            "xai_overlay_url": overlay_url,
            "xai_method": "Gradient Saliency" if heatmap_url else None,
            "xai_target_class": target_class,
            "xai_predicted_class": target_class,
            "xai_layer": xai_layer,
            "xai_map_strength": xai_map_strength,
            "xai_error": xai_error,
        }

    except FileNotFoundError:
        raise
    except Exception as exc:
        logger.exception("[image_inference] Inference failed for %s", image_path)
        raise RuntimeError(f"Image analysis failed: {exc}") from exc

"""Image deepfake inference via the official TruthScan Python SDK."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Union

from truthscan.image_detection import ImageDetectionClient

logger = logging.getLogger(__name__)

LABELS = ["Authentic", "Suspected Deepfake"]
DEFAULT_FAKE_THRESHOLD = 0.70
TRUTHSCAN_API_KEY = os.getenv(
    "TRUTHSCAN_API_KEY",
    "ts_live_v2_DH6zrcnrYWUVkJSzLAYL6uMXigPhkZ5VTgjDoSCYLDv7m0SgtNSVatopBSonPJ6bShqfIM7awjwGGmCJJZWv4zLZis8_mdI0ltSHcevosMvyKadJuQQUXmZrtOpNmni5pHR90aN_e46f9a",
)
TRUTHSCAN_ORGANIZATION_ID = os.getenv(
    "TRUTHSCAN_ORGANIZATION_ID",
    "7046cff0-9684-4880-be13-668f41a1252b",
)


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
    raw_fake_prob = max(0.0, min(1.0, raw_fake_prob))

    if raw_fake_prob < threshold:
        return 0.5 * (raw_fake_prob / threshold)

    remaining = max(1e-8, 1.0 - threshold)
    return 0.5 + 0.5 * ((raw_fake_prob - threshold) / remaining)


def _build_explanation(final_result: str, fake_prob: float) -> str:
    result_text = str(final_result or "Unknown").strip()
    if result_text.lower() in {"ai-generated", "digitally edited", "ai-edited", "suspected deepfake"}:
        return (
            "The TruthScan API classified the image as manipulated or digitally edited. "
            f"The reported confidence is {fake_prob:.1%}."
        )

    return (
        "The TruthScan API classified the image as authentic or not strongly manipulated. "
        f"The reported confidence is {fake_prob:.1%}."
    )


def _result_label(final_result: str) -> str:
    normalized = str(final_result or "").strip().lower()
    if normalized in {"real", "authentic", "clean"}:
        return LABELS[0]

    return LABELS[1]


def analyze_image(image_path: str) -> Dict[str, Union[str, float, None]]:
    """
    Run image deepfake detection through the official TruthScan SDK client.
    """
    try:
        if not TRUTHSCAN_API_KEY:
            raise RuntimeError("TRUTHSCAN_API_KEY is required for image detection")

        client = ImageDetectionClient(api_key=TRUTHSCAN_API_KEY)
        detection_result = client.detect(
            image_path,
            generate_preview=False,
            max_poll_attempts=60,
            poll_interval_seconds=0.5,
        )

        raw_probability = float(detection_result.get("result") or 0.0)
        result_details = detection_result.get("result_details") or {}
        final_result = result_details.get("final_result") or "Unknown"
        label = _result_label(final_result)

        threshold = _fake_threshold()
        fake_prob = _calibrate_fake_probability(
            max(0.0, min(100.0, raw_probability)) / 100.0,
            threshold,
        )
        authentic_prob = 1.0 - fake_prob

        confidence = round((fake_prob if label == LABELS[1] else authentic_prob) * 100, 2)
        heatmap_url = result_details.get("heatmap_url")

        return {
            "media_type": "image",
            "label": label,
            "confidence": confidence,
            "fake_probability": round(fake_prob * 100, 2),
            "authentic_probability": round(authentic_prob * 100, 2),
            "explanation": _build_explanation(final_result, fake_prob),
            "heatmap_url": heatmap_url,
            "xai_overlay_url": None,
            "xai_method": "TruthScan SDK" if heatmap_url else None,
            "xai_target_class": final_result,
            "xai_predicted_class": final_result,
            "xai_layer": None,
            "xai_map_strength": None,
            "xai_error": None,
        }
    except FileNotFoundError:
        raise
    except Exception as exc:
        logger.exception("[image_inference] TruthScan SDK image detection failed for %s", image_path)
        raise RuntimeError(f"Image analysis failed: {exc}") from exc

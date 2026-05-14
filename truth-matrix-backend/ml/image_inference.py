from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Union
from uuid import uuid4

import cv2
import numpy as np
from PIL import Image, ImageDraw

from ml.model_common import (
    RESULTS_DIR,
    ModelSetupError,
    env_bool,
    env_float,
    env_int,
    fake_class_index,
    image_model_input_size,
    load_image_model,
    prediction_payload,
    preprocess_image_path,
    torch,
)


def _gradcam_colormap() -> int:
    configured = os.getenv("IMAGE_HEATMAP_COLORMAP", "turbo").strip().lower()
    colormaps = {
        "jet": cv2.COLORMAP_JET,
        "hot": cv2.COLORMAP_HOT,
        "magma": cv2.COLORMAP_MAGMA,
        "inferno": cv2.COLORMAP_INFERNO,
        "plasma": cv2.COLORMAP_PLASMA,
        "viridis": cv2.COLORMAP_VIRIDIS,
        "turbo": getattr(cv2, "COLORMAP_TURBO", cv2.COLORMAP_JET),
    }
    return colormaps.get(configured, colormaps["turbo"])


def _resolve_target_layer(model):
    configured = os.getenv("IMAGE_GRADCAM_LAYER", "blocks.4").strip().lower()
    blocks = model.backbone.blocks

    if configured.startswith("blocks."):
        try:
            block_index = int(configured.split(".", 1)[1])
        except ValueError as exc:
            raise ModelSetupError("IMAGE_GRADCAM_LAYER block index must be an integer") from exc

        if block_index < 0:
            block_index = len(blocks) + block_index

        if block_index < 0 or block_index >= len(blocks):
            raise ModelSetupError(
                f"IMAGE_GRADCAM_LAYER block index must be between 0 and {len(blocks) - 1}"
            )

        return blocks[block_index], f"blocks.{block_index}"

    if configured in {"blocks", "default"}:
        block_index = min(4, len(blocks) - 1)
        return blocks[block_index], f"blocks.{block_index}"

    if configured in {"last_block", "final_block"}:
        return blocks[-1], f"blocks.{len(blocks) - 1}"

    if configured in {"conv_head", "head"}:
        return model.backbone.conv_head, "conv_head"

    if configured in {"bn2", "final_norm"}:
        return model.backbone.bn2, "bn2"

    raise ModelSetupError(
        "IMAGE_GRADCAM_LAYER must be one of: blocks.0-6, blocks, conv_head, bn2"
    )


def _resolve_gradcam_target(logits):
    fake_index = fake_class_index("IMAGE_FAKE_CLASS_INDEX")
    authentic_index = 1 - fake_index
    predicted_index = int(logits.argmax(dim=1).item())
    configured = os.getenv("IMAGE_GRADCAM_TARGET", "fake").strip().lower()

    if configured in {"predicted", "prediction", "winner"}:
        target_index = predicted_index
        target_label = "fake" if target_index == fake_index else "authentic"
        return target_index, f"predicted_{target_label}", predicted_index

    if configured in {"authentic", "real"}:
        return authentic_index, "authentic", predicted_index

    if configured not in {"fake", "deepfake", "ai"}:
        raise ModelSetupError(
            "IMAGE_GRADCAM_TARGET must be one of: fake, authentic, predicted"
        )

    return fake_index, "fake", predicted_index


def _build_cam(activation, gradient, *, positive_gradients: bool):
    gradient_for_weights = torch.relu(gradient) if positive_gradients else gradient
    weights = gradient_for_weights.mean(dim=(2, 3), keepdim=True)
    cam = (weights * activation).sum(dim=1).squeeze()
    return torch.relu(cam)


def _normalize_cam(cam) -> tuple[np.ndarray | None, float]:
    cam_array = cam.detach().float().cpu().numpy()
    cam_array = np.nan_to_num(cam_array, nan=0.0, posinf=0.0, neginf=0.0)
    max_value = float(cam_array.max(initial=0.0))

    if max_value <= 1e-8:
        return None, 0.0

    high_percentile = env_float(
        "IMAGE_GRADCAM_PERCENTILE",
        98.0,
        minimum=50.0,
        maximum=100.0,
    )
    low_value = float(np.percentile(cam_array, 5.0))
    high_value = float(np.percentile(cam_array, high_percentile))

    if high_value - low_value <= 1e-8:
        low_value = float(cam_array.min(initial=0.0))
        high_value = max_value

    if high_value - low_value <= 1e-8:
        return None, max_value

    normalized = np.clip((cam_array - low_value) / (high_value - low_value), 0, 1)
    gamma = env_float("IMAGE_HEATMAP_GAMMA", 0.75, minimum=0.1, maximum=3.0)
    normalized = np.power(normalized, gamma)
    return normalized.astype(np.float32), max_value


def _resize_cam(cam: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    resized = cv2.resize(cam, size, interpolation=cv2.INTER_CUBIC)
    blur_size = env_int("IMAGE_HEATMAP_BLUR", 5, minimum=0)

    if blur_size > 1:
        if blur_size % 2 == 0:
            blur_size += 1
        resized = cv2.GaussianBlur(resized, (blur_size, blur_size), 0)

    return np.clip(resized, 0, 1)


def _label_panel_item(image: Image.Image, label: str) -> Image.Image:
    label_height = 34
    panel = Image.new("RGB", (image.width, image.height + label_height), "white")
    panel.paste(image, (0, label_height))
    draw = ImageDraw.Draw(panel)
    draw.rectangle((0, 0, image.width, label_height), fill=(17, 24, 39))
    draw.text((12, 10), label, fill=(255, 255, 255))
    return panel


def _make_xai_panel(
    original_image: Image.Image,
    heatmap_image: Image.Image,
    overlay_image: Image.Image,
) -> Image.Image:
    panel_height = env_int("IMAGE_XAI_PANEL_HEIGHT", 360, minimum=160)
    items = [
        (original_image.convert("RGB"), "Original"),
        (heatmap_image.convert("RGB"), "Fake-class Grad-CAM"),
        (overlay_image.convert("RGB"), "Overlay"),
    ]
    resized_items = []
    resample = getattr(Image, "Resampling", Image).BICUBIC

    for image, label in items:
        scale = panel_height / max(image.height, 1)
        size = (max(1, int(image.width * scale)), panel_height)
        resized = image.resize(size, resample)
        resized_items.append(_label_panel_item(resized, label))

    gap = 10
    width = sum(item.width for item in resized_items) + gap * (len(resized_items) - 1)
    height = max(item.height for item in resized_items)
    panel = Image.new("RGB", (width, height), (241, 245, 249))

    x_offset = 0
    for item in resized_items:
        panel.paste(item, (x_offset, 0))
        x_offset += item.width + gap

    return panel


def _save_gradcam_artifacts(
    original_image: Image.Image,
    cam: np.ndarray,
    source_path: str,
) -> Dict[str, str]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    source_stem = Path(source_path).stem or "image"
    output_stem = f"{source_stem}-{uuid4().hex[:12]}-gradcam"
    heatmap_name = f"{output_stem}-map.jpg"
    overlay_name = f"{output_stem}-overlay.jpg"
    panel_name = f"{output_stem}-panel.jpg"

    cam_resized = _resize_cam(cam, original_image.size)
    heatmap = cv2.applyColorMap(np.uint8(255 * cam_resized), _gradcam_colormap())
    heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)

    base = np.asarray(original_image.convert("RGB"), dtype=np.uint8)
    alpha = env_float("IMAGE_HEATMAP_ALPHA", 0.45, minimum=0.05, maximum=0.95)
    overlay = cv2.addWeighted(base, 1.0 - alpha, heatmap, alpha, 0)

    heatmap_image = Image.fromarray(heatmap)
    overlay_image = Image.fromarray(overlay)
    panel_image = _make_xai_panel(original_image, heatmap_image, overlay_image)

    heatmap_image.save(RESULTS_DIR / heatmap_name, quality=92)
    overlay_image.save(RESULTS_DIR / overlay_name, quality=92)
    panel_image.save(RESULTS_DIR / panel_name, quality=92)

    return {
        "heatmap_url": f"/results/{heatmap_name}",
        "xai_overlay_url": f"/results/{overlay_name}",
        "xai_panel_url": f"/results/{panel_name}",
    }


def _predict_with_gradcam(model, image_tensor, original_image: Image.Image, image_path: str, device):
    activations = []
    gradients = []
    target_layer, layer_name = _resolve_target_layer(model)

    def forward_hook(_module, _inputs, output):
        activations.append(output)

    def backward_hook(_module, _grad_input, grad_output):
        gradients.append(grad_output[0])

    forward_handle = target_layer.register_forward_hook(forward_hook)
    backward_handle = target_layer.register_full_backward_hook(backward_hook)

    try:
        input_tensor = image_tensor.unsqueeze(0).to(device)
        model.zero_grad(set_to_none=True)

        with torch.enable_grad():
            logits = model(input_tensor)
            target_index, target_label, predicted_index = _resolve_gradcam_target(logits)
            logits[0, target_index].backward()

        xai_extra = {
            "xai_method": "Grad-CAM",
            "xai_target_class": target_label,
            "xai_layer": layer_name,
            "xai_predicted_class": "fake"
            if predicted_index == fake_class_index("IMAGE_FAKE_CLASS_INDEX")
            else "authentic",
        }

        if not activations or not gradients:
            return logits.detach(), xai_extra

        activation = activations[-1].detach()
        gradient = gradients[-1].detach()
        use_positive_gradients = env_bool("IMAGE_GRADCAM_POSITIVE_GRADIENTS", True)
        cam = _build_cam(
            activation,
            gradient,
            positive_gradients=use_positive_gradients,
        )
        normalized_cam, map_strength = _normalize_cam(cam)

        if normalized_cam is None and use_positive_gradients:
            cam = _build_cam(activation, gradient, positive_gradients=False)
            normalized_cam, map_strength = _normalize_cam(cam)

        xai_extra["xai_map_strength"] = round(map_strength, 6)

        if normalized_cam is None:
            return logits.detach(), xai_extra

        xai_extra.update(
            _save_gradcam_artifacts(
                original_image,
                normalized_cam,
                image_path,
            )
        )
        return logits.detach(), xai_extra
    finally:
        forward_handle.remove()
        backward_handle.remove()
        model.zero_grad(set_to_none=True)


def _predict_without_gradcam(model, image_tensor, device):
    with torch.no_grad():
        return model(image_tensor.unsqueeze(0).to(device)), {}


def analyze_image(image_path: str) -> Dict[str, Union[str, float, None]]:
    model, device = load_image_model()
    image_tensor, original_image = preprocess_image_path(
        image_path,
        size=image_model_input_size(),
    )

    xai_extra = {}
    if env_bool("GENERATE_IMAGE_HEATMAPS", True):
        try:
            logits, xai_extra = _predict_with_gradcam(
                model,
                image_tensor,
                original_image,
                image_path,
                device,
            )
        except Exception as exc:
            logits, _ = _predict_without_gradcam(model, image_tensor, device)
            xai_extra = {"xai_error": str(exc)}
    else:
        logits, xai_extra = _predict_without_gradcam(model, image_tensor, device)

    return prediction_payload(
        logits,
        media_type="image",
        fake_index_env="IMAGE_FAKE_CLASS_INDEX",
        extra={
            "heatmap_url": xai_extra.get("heatmap_url"),
            "xai_overlay_url": xai_extra.get("xai_overlay_url"),
            "xai_panel_url": xai_extra.get("xai_panel_url"),
            "xai_method": xai_extra.get("xai_method")
            if xai_extra.get("heatmap_url")
            else None,
            "xai_target_class": xai_extra.get("xai_target_class"),
            "xai_predicted_class": xai_extra.get("xai_predicted_class"),
            "xai_layer": xai_extra.get("xai_layer"),
            "xai_map_strength": xai_extra.get("xai_map_strength"),
            "xai_error": xai_extra.get("xai_error"),
        },
    )

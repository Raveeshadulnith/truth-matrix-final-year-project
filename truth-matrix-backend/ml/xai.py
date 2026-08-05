"""
Grad-CAM (Gradient-weighted Class Activation Mapping) for the image model.

The EfficientNet-B4 (timm) SiLU activation outputs
(B, 1792, 7, 7) spatial feature maps *before* global average pooling.
A torchvision fallback hooks the last block in backbone.features instead.

Public API:
    generate_image_heatmap(model, device, image_path, class_idx) -> np.ndarray | None
    save_heatmap(heatmap_rgb)                                    -> str (temp file path)
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Optional
from uuid import uuid4

import cv2
import numpy as np

logger = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).resolve().parents[1] / "results"

# ImageNet normalisation constants (duplicated here to keep xai.py self-contained)
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)


# ---------------------------------------------------------------------------
# Hook container
# ---------------------------------------------------------------------------
class _Hooks:
    """Registers a forward hook and a full-backward hook on a single layer."""

    def __init__(self, layer):
        self.activations: Optional[np.ndarray] = None
        self.gradients:   Optional[np.ndarray] = None
        self._fh = layer.register_forward_hook(self._fwd)
        self._bh = layer.register_full_backward_hook(self._bwd)

    def _fwd(self, _module, _inp, out):
        # out shape: (B, C, H, W)
        self.activations = out.detach().cpu().numpy()

    def _bwd(self, _module, _gin, gout):
        # gout[0] shape: (B, C, H, W)  — gradient w.r.t. this layer's output
        self.gradients = gout[0].detach().cpu().numpy()

    def remove(self):
        self._fh.remove()
        self._bh.remove()


# ---------------------------------------------------------------------------
# Core GradCAM math
# ---------------------------------------------------------------------------
def _cam(acts: np.ndarray, grads: np.ndarray) -> np.ndarray:
    """
    Compute one GradCAM map from (C, H, W) activations and gradients.

    α_k  = mean_{i,j}( ∂y^c / ∂A^k_{ij} )
    L^c  = ReLU( Σ_k  α_k * A^k )

    Returns a (H, W) float32 array in [0, 1].
    """
    weights = grads.mean(axis=(1, 2), keepdims=True)   # (C, 1, 1)
    cam = (weights * acts).sum(axis=0)                  # (H, W)
    cam = np.maximum(cam, 0)                            # ReLU
    lo, hi = cam.min(), cam.max()
    return (cam - lo) / (hi - lo + 1e-8)


def _overlay(cam_hw: np.ndarray, img_rgb: np.ndarray) -> np.ndarray:
    """
    Resize cam to img dimensions, apply JET colormap, and alpha-blend
    with the original image.  Returns (H, W, 3) uint8 RGB.
    """
    h, w = img_rgb.shape[:2]
    cam_r    = cv2.resize(cam_hw, (w, h), interpolation=cv2.INTER_LINEAR)
    heat_bgr = cv2.applyColorMap(np.uint8(255 * cam_r), cv2.COLORMAP_JET)
    heat_rgb = cv2.cvtColor(heat_bgr, cv2.COLOR_BGR2RGB)
    return np.uint8(0.45 * heat_rgb + 0.55 * img_rgb)


def _heatmap_rgb(cam_hw: np.ndarray, img_rgb: np.ndarray) -> np.ndarray:
    """
    Resize a normalized saliency/CAM map to image dimensions and return a pure
    JET heatmap as RGB uint8.
    """
    h, w = img_rgb.shape[:2]
    cam_r = cv2.resize(cam_hw, (w, h), interpolation=cv2.INTER_LINEAR)
    heat_bgr = cv2.applyColorMap(np.uint8(255 * cam_r), cv2.COLORMAP_JET)
    return cv2.cvtColor(heat_bgr, cv2.COLOR_BGR2RGB)


def _normalise_map(cam_hw: np.ndarray) -> np.ndarray:
    cam = np.nan_to_num(cam_hw.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    cam = np.maximum(cam, 0.0)
    lo = float(cam.min())
    hi = float(cam.max())
    if hi - lo < 1e-8:
        return np.zeros_like(cam, dtype=np.float32)
    return (cam - lo) / (hi - lo)


# ---------------------------------------------------------------------------
# Target-layer discovery
# ---------------------------------------------------------------------------
def _target_layer(model):
    """
    Return the last spatial activation layer of the EfficientNet-B4 backbone.

    timm path  : model.backbone.act2
                 → output (B, 1792, 7, 7) for 224×224 input
    tv fallback: last block in model.backbone[0]
                 (features[-1] of torchvision EfficientNet-B4)
    """
    base = model.backbone

    for attr_name in ("conv_head", "bn2"):
        layer = getattr(base, attr_name, None)
        if layer is not None:
            return layer

    blocks = getattr(base, "blocks", None)
    if blocks is not None and len(blocks) > 0:
        return blocks[-1]

    features = getattr(base, "features", None)
    if features is not None and len(features) > 0:
        return features[-1]

    # torchvision Sequential backbone: nn.Sequential(features, avgpool, Flatten)
    try:
        return list(base.children())[0][-1]   # features[-1]
    except Exception as exc:
        raise RuntimeError(
            f"[xai] Cannot locate GradCAM target layer for image model: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Image GradCAM
# ---------------------------------------------------------------------------
def generate_image_heatmap(
    model,
    device,
    image_path: str,
    class_idx: int,
    image_size: int = 224,
) -> Optional[np.ndarray]:
    """
    Compute a GradCAM heatmap overlaid on the input image.

    Runs a second forward+backward pass (with gradient tracking) after the
    no-grad inference pass that already determined class_idx.

    Returns (H, W, 3) uint8 RGB, or None if GradCAM fails for any reason.
    """
    import torch
    from PIL import Image

    try:
        pil    = Image.open(image_path).convert("RGB").resize(
            (image_size, image_size), Image.BILINEAR
        )
        img_rgb = np.array(pil, dtype=np.uint8)

        # Preprocess — same pipeline as image_inference._preprocess
        arr    = img_rgb.astype(np.float32) / 255.0
        arr    = (arr - _MEAN) / _STD
        tensor = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0).to(device)

        layer = _target_layer(model)
        hooks = _Hooks(layer)

        try:
            model.eval()
            probs = model(tensor)          # (1, 2) — computation graph tracked
            model.zero_grad()
            probs[0, class_idx].backward()
        finally:
            hooks.remove()
            model.zero_grad()              # clean up accumulated parameter grads

        if hooks.activations is None or hooks.gradients is None:
            logger.warning("[xai] image: hooks captured nothing")
            return None

        cam_map = _cam(hooks.activations[0], hooks.gradients[0])
        return _overlay(cam_map, img_rgb)

    except Exception:
        logger.warning("[xai] image GradCAM failed", exc_info=True)
        return None


def generate_siglip_image_xai(
    model,
    processor,
    device,
    image_path: str,
    class_idx: int,
) -> Optional[dict]:
    """
    Generate a saliency heatmap for a Hugging Face SigLIP image classifier.

    SigLIP does not expose the EfficientNet activation layer used by the
    project Grad-CAM helper, so this uses input-gradient saliency. The returned
    images are resized to the original image dimensions, which keeps frontend
    overlay alignment correct.
    """
    import torch
    from PIL import Image, ImageOps

    try:
        with Image.open(image_path) as image:
            pil = ImageOps.exif_transpose(image).convert("RGB")
        img_rgb = np.array(pil, dtype=np.uint8)

        inputs = processor(images=pil, return_tensors="pt")
        inputs = {key: value.to(device) for key, value in inputs.items()}
        pixel_values = inputs.get("pixel_values")
        if pixel_values is None:
            raise RuntimeError("processor did not return pixel_values")

        pixel_values.requires_grad_(True)
        inputs["pixel_values"] = pixel_values

        model.eval()
        model.zero_grad(set_to_none=True)
        outputs = model(**inputs)
        score = outputs.logits[0, int(class_idx)]
        score.backward()

        gradients = pixel_values.grad
        if gradients is None:
            raise RuntimeError("no input gradients were produced")

        # Mean absolute gradient across RGB channels gives one saliency value
        # per processed image pixel.
        saliency = gradients.detach().abs().mean(dim=1)[0].cpu().numpy()
        saliency = cv2.GaussianBlur(saliency, (0, 0), sigmaX=1.2)
        saliency = _normalise_map(saliency)

        heatmap_rgb = _heatmap_rgb(saliency, img_rgb)
        overlay_rgb = _overlay(saliency, img_rgb)
        map_strength = float(np.clip(saliency.mean() * 100.0, 0.0, 100.0))

        model.zero_grad(set_to_none=True)
        return {
            "heatmap_rgb": heatmap_rgb,
            "overlay_rgb": overlay_rgb,
            "target_layer": "input_pixel_gradients",
            "map_strength": round(map_strength, 2),
        }

    except Exception:
        logger.warning("[xai] SigLIP image saliency failed", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Persist to a temporary PNG file
# ---------------------------------------------------------------------------
def save_heatmap(heatmap_rgb: np.ndarray) -> str:
    """
    Save an RGB heatmap array to a temporary PNG file.
    Returns the absolute path of the written file.
    """
    heatmap_bgr = cv2.cvtColor(heatmap_rgb, cv2.COLOR_RGB2BGR)
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.close()
    cv2.imwrite(tmp.name, heatmap_bgr)
    return tmp.name


def save_heatmap_result(
    heatmap_rgb: np.ndarray,
    source_path: str,
    suffix: str = "gradcam",
) -> str:
    """
    Save an RGB heatmap array under backend/results and return its public URL.
    This mirrors the backup implementation's /results/... behavior.
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    source_stem = Path(source_path).stem or "media"
    output_name = f"{source_stem}-{uuid4().hex[:12]}-{suffix}.png"
    output_path = RESULTS_DIR / output_name
    heatmap_bgr = cv2.cvtColor(heatmap_rgb, cv2.COLOR_RGB2BGR)

    if not cv2.imwrite(str(output_path), heatmap_bgr):
        raise RuntimeError(f"Could not write Grad-CAM heatmap to {output_path}")

    return f"/results/{output_name}"

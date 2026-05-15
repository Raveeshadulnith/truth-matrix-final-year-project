"""
Grad-CAM (Gradient-weighted Class Activation Mapping) for Truth Matrix models.

Supported models:
  Image model  — hook target: model.backbone.act2
  Video model  — hook target: model.cnn.act2

Both are the EfficientNet-B4 (timm) SiLU activation that outputs
(B, 1792, 7, 7) spatial feature maps *before* global average pooling.
A torchvision fallback hooks the last block in backbone.features instead.

Public API:
    generate_image_heatmap(model, device, image_path, class_idx) -> np.ndarray | None
    generate_video_heatmap(model, device, frames, class_idx)     -> np.ndarray | None
    save_heatmap(heatmap_rgb)                                    -> str (temp file path)
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import List, Optional
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


# ---------------------------------------------------------------------------
# Target-layer discovery
# ---------------------------------------------------------------------------
def _target_layer(model, model_type: str):
    """
    Return the last spatial activation layer of the EfficientNet-B4 backbone.

    timm path  : model.backbone.act2  (image)  |  model.cnn.act2  (video)
                 → output (B, 1792, 7, 7) for 224×224 input
    tv fallback: last block in model.backbone[0] / model.cnn[0]
                 (features[-1] of torchvision EfficientNet-B4)
    """
    base = model.backbone if model_type == "image" else model.cnn

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
            f"[xai] Cannot locate GradCAM target layer for {model_type} model: {exc}"
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

        layer = _target_layer(model, "image")
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


# ---------------------------------------------------------------------------
# Video GradCAM — 4×4 grid of per-frame heatmaps
# ---------------------------------------------------------------------------
def generate_video_heatmap(
    model,
    device,
    frames: List[np.ndarray],
    class_idx: int,
    image_size: int = 224,
    thumb_size: int = 112,
) -> Optional[np.ndarray]:
    """
    Per-frame GradCAM for a video clip, displayed as a grid image.

    A single forward+backward pass captures (B*T, C, H, W) activations and
    gradients at model.cnn.act2, giving one map per frame.

    Layout: 4 columns × ceil(T/4) rows, each cell thumb_size × thumb_size.
    Returns (rows*thumb_size, cols*thumb_size, 3) uint8 RGB, or None on failure.
    """
    import torch
    from PIL import Image

    try:
        T = len(frames)
        tensors, frame_rgbs = [], []

        for frame in frames:
            pil = Image.fromarray(frame).resize(
                (image_size, image_size), Image.BILINEAR
            )
            rgb = np.array(pil, dtype=np.uint8)
            frame_rgbs.append(rgb)
            arr = rgb.astype(np.float32) / 255.0
            arr = (arr - _MEAN) / _STD
            tensors.append(torch.from_numpy(arr).permute(2, 0, 1))

        # (1, T, 3, H, W)
        clip = torch.stack(tensors).unsqueeze(0).to(device)

        layer = _target_layer(model, "video")
        hooks = _Hooks(layer)

        try:
            model.eval()
            probs = model(clip)            # (1, 2) — hooks fire on cnn.act2
            model.zero_grad()
            probs[0, class_idx].backward()
        finally:
            hooks.remove()
            model.zero_grad()

        if hooks.activations is None or hooks.gradients is None:
            logger.warning("[xai] video: hooks captured nothing")
            return None

        acts  = hooks.activations   # (T, C, 7, 7)
        grads = hooks.gradients     # (T, C, 7, 7)

        # Build 4-column grid
        cols = 4
        rows = (T + cols - 1) // cols
        grid = np.zeros((rows * thumb_size, cols * thumb_size, 3), dtype=np.uint8)

        for t in range(T):
            cam_t  = _cam(acts[t], grads[t])
            thumb  = cv2.resize(frame_rgbs[t], (thumb_size, thumb_size))
            cell   = _overlay(cam_t, thumb)
            r, c   = divmod(t, cols)
            grid[r * thumb_size:(r + 1) * thumb_size,
                 c * thumb_size:(c + 1) * thumb_size] = cell

        return grid

    except Exception:
        logger.warning("[xai] video GradCAM failed", exc_info=True)
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

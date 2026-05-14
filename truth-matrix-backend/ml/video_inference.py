from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Union
from uuid import uuid4

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps

from ml.model_common import (
    ModelSetupError,
    RESULTS_DIR,
    env_bool,
    env_int,
    load_video_model,
    model_input_size,
    prediction_payload,
    preprocess_pil_image,
    torch,
    video_frame_count,
)


def _read_frame_at(cap: cv2.VideoCapture, frame_index: int):
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ok, frame = cap.read()
    return frame if ok else None


def _sample_video_frames(video_path: str, frame_count: int) -> List[Image.Image]:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ModelSetupError("Could not open the uploaded video file.")

    try:
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        frames = []

        if total_frames > 0:
            indices = np.linspace(0, max(total_frames - 1, 0), frame_count, dtype=int)
            for index in indices:
                frame = _read_frame_at(cap, int(index))
                if frame is not None:
                    frames.append(frame)

        if not frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            while len(frames) < frame_count:
                ok, frame = cap.read()
                if not ok:
                    break
                frames.append(frame)

        if not frames:
            raise ModelSetupError("No readable frames were found in the uploaded video.")

        while len(frames) < frame_count:
            frames.append(frames[-1].copy())

        return [
            Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            for frame in frames[:frame_count]
        ]
    finally:
        cap.release()


def _normalize_cam(cam):
    cam = torch.relu(cam)
    cam_min = cam.min()
    cam_max = cam.max()
    if float(cam_max - cam_min) <= 1e-8:
        return torch.zeros_like(cam)
    return (cam - cam_min) / (cam_max - cam_min)


def _predict_with_gradcam(model, batch):
    activations = []
    gradients = []

    def forward_hook(_module, _inputs, output):
        activations.append(output)

    def backward_hook(_module, _grad_input, grad_output):
        gradients.append(grad_output[0])

    target_layer = model.cnn.conv_head
    forward_handle = target_layer.register_forward_hook(forward_hook)
    backward_handle = target_layer.register_full_backward_hook(backward_hook)

    try:
        model.zero_grad(set_to_none=True)

        with torch.enable_grad():
            logits = model(batch)
            predicted_index = int(logits.argmax(dim=1).item())
            logits[0, predicted_index].backward()

        if not activations or not gradients:
            return logits.detach(), None

        activation = activations[-1].detach()
        gradient = gradients[-1].detach()
        weights = gradient.mean(dim=(2, 3), keepdim=True)
        cams = (weights * activation).sum(dim=1)
        cams = torch.stack([_normalize_cam(cam) for cam in cams], dim=0)
        return logits.detach(), cams.cpu().numpy()
    finally:
        forward_handle.remove()
        backward_handle.remove()
        model.zero_grad(set_to_none=True)


def _predict_without_gradcam(model, batch):
    with torch.no_grad():
        return model(batch), None


def _overlay_frame(frame: Image.Image, cam: np.ndarray) -> Image.Image:
    image_size = model_input_size()
    resample = getattr(Image, "Resampling", Image).BICUBIC
    square_frame = ImageOps.fit(frame.convert("RGB"), (image_size, image_size), method=resample)
    cam_resized = cv2.resize(cam, (image_size, image_size))
    heatmap = cv2.applyColorMap(np.uint8(255 * cam_resized), cv2.COLORMAP_JET)
    heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)
    base = np.asarray(square_frame, dtype=np.uint8)
    overlay = cv2.addWeighted(base, 0.55, heatmap, 0.45, 0)
    return Image.fromarray(overlay)


def _save_gradcam_contact_sheet(
    frames: List[Image.Image],
    cams: np.ndarray,
    source_path: str,
) -> str | None:
    if cams is None or len(frames) == 0:
        return None

    max_frames = min(env_int("VIDEO_HEATMAP_FRAMES", 8), len(frames), len(cams))
    if max_frames <= 0:
        return None

    selected_indices = np.linspace(0, len(frames) - 1, max_frames, dtype=int)
    cell_size = model_input_size()
    caption_height = 26
    columns = min(4, max_frames)
    rows = int(np.ceil(max_frames / columns))
    sheet = Image.new(
        "RGB",
        (columns * cell_size, rows * (cell_size + caption_height)),
        (12, 16, 24),
    )
    draw = ImageDraw.Draw(sheet)

    for position, frame_index in enumerate(selected_indices):
        row = position // columns
        column = position % columns
        x = column * cell_size
        y = row * (cell_size + caption_height)
        overlay = _overlay_frame(frames[int(frame_index)], cams[int(frame_index)])
        sheet.paste(overlay, (x, y))
        draw.rectangle(
            (x, y + cell_size, x + cell_size, y + cell_size + caption_height),
            fill=(12, 16, 24),
        )
        draw.text(
            (x + 8, y + cell_size + 6),
            f"Frame {int(frame_index) + 1}",
            fill=(235, 241, 245),
        )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    source_stem = Path(source_path).stem or "video"
    output_name = f"{source_stem}-{uuid4().hex[:12]}-video-gradcam.jpg"
    output_path = RESULTS_DIR / output_name
    sheet.save(output_path, quality=90)
    return f"/results/{output_name}"


def analyze_video(video_path: str) -> Dict[str, Union[str, float, int, None]]:
    model, device = load_video_model()
    frame_count = video_frame_count()
    frames = _sample_video_frames(video_path, frame_count)
    frame_tensors = [preprocess_pil_image(frame) for frame in frames]
    batch = torch.stack(frame_tensors, dim=0).unsqueeze(0).to(device)

    heatmap_url = None
    if env_bool("GENERATE_VIDEO_HEATMAPS", True):
        try:
            logits, cams = _predict_with_gradcam(model, batch)
            if cams is not None:
                heatmap_url = _save_gradcam_contact_sheet(frames, cams, video_path)
        except Exception:
            logits, heatmap_url = _predict_without_gradcam(model, batch)
    else:
        logits, heatmap_url = _predict_without_gradcam(model, batch)

    return prediction_payload(
        logits,
        media_type="video",
        fake_index_env="VIDEO_FAKE_CLASS_INDEX",
        extra={
            "frames_analyzed": len(frames),
            "heatmap_url": heatmap_url,
            "xai_method": "Grad-CAM" if heatmap_url else None,
        },
    )

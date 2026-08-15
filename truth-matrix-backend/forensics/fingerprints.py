from __future__ import annotations

import hashlib
import json
import math
import os
import re
import warnings as python_warnings
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple, Union

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field

from forensics.hashing import resolve_workspace_file
from forensics.metadata import ProcessOutput, _run_bounded_process, discover_executable
from schemas.forensic_schema import (
    ExtractorStatus,
    FingerprintComponent,
    PerceptualFingerprint,
)


PathLike = Union[str, Path]
PHASH_ALGORITHM = "phash-dct-64"
PHASH_VERSION = "1.0"
VIDEO_ALGORITHM = "video-phash-sequence"
VIDEO_VERSION = "1.0"
AUDIO_ALGORITHM = "chromaprint-raw-algorithm-2"
AUDIO_VERSION = "raw-v1"

DEFAULT_IMAGE_MAX_FILE_BYTES = 50 * 1024 * 1024
DEFAULT_IMAGE_MAX_DECODE_PIXELS = 50_000_000
DEFAULT_IMAGE_PHASH_MAX_DISTANCE = 12
DEFAULT_VIDEO_FRAME_COUNT = 12
DEFAULT_VIDEO_FRAME_MAX_DIMENSION = 512
DEFAULT_VIDEO_MAX_SOURCE_PIXELS = 50_000_000
DEFAULT_VIDEO_MAX_DECODE_FRAMES = 50_000
DEFAULT_VIDEO_MAX_DURATION_SECONDS = 3600.0
DEFAULT_VIDEO_TIMEOUT_SECONDS = 20.0
DEFAULT_VIDEO_COMPONENT_MAX_DISTANCE = 14
DEFAULT_VIDEO_TIMESTAMP_TOLERANCE = 0.20
DEFAULT_VIDEO_SIMILARITY_THRESHOLD = 0.65
DEFAULT_VIDEO_MIN_MATCH_RATIO = 0.50
DEFAULT_AUDIO_MAX_DURATION_SECONDS = 120
DEFAULT_AUDIO_TIMEOUT_SECONDS = 20.0
DEFAULT_AUDIO_OUTPUT_BYTES = 256 * 1024
DEFAULT_AUDIO_MAX_COMPONENTS = 4096
DEFAULT_AUDIO_MAX_ALIGNMENT_OFFSET = 120
DEFAULT_AUDIO_MAX_COMPONENT_BIT_ERRORS = 2
DEFAULT_AUDIO_MIN_OVERLAP_COMPONENTS = 16
DEFAULT_AUDIO_SIMILARITY_THRESHOLD = 0.50
DEFAULT_AUDIO_MIN_OVERLAP_RATIO = 0.50

_SUPPORTED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
_SUPPORTED_VIDEO_MIME_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/x-msvideo",
    "video/x-matroska",
    "video/webm",
}
_SUPPORTED_AUDIO_MIME_TYPES = {"audio/wav", "audio/mpeg", "audio/mp4"}
_HEX_64_PATTERN = re.compile(r"^[0-9a-fA-F]{16}$")


class FingerprintExtractionResult(BaseModel):
    """Independent perceptual fingerprint result with elapsed time."""

    model_config = ConfigDict(extra="forbid")

    fingerprint: PerceptualFingerprint
    processing_time_ms: int = Field(..., ge=0)


class FingerprintSimilarityResult(BaseModel):
    """Explainable similarity comparison result for compatible fingerprints."""

    model_config = ConfigDict(extra="forbid")

    media_type: Literal["image", "video", "audio"]
    similarity_score: float = Field(..., ge=0, le=1)
    distance: float = Field(..., ge=0)
    threshold: float = Field(..., ge=0, le=1)
    is_similar: bool
    matched_components: Optional[int] = Field(default=None, ge=0)
    overlap_ratio: Optional[float] = Field(default=None, ge=0, le=1)
    method: str
    method_version: str
    limitations: List[str] = Field(default_factory=list)


class _FingerprintUnavailable(RuntimeError):
    """Raised when a configured resource limit prevents fingerprinting."""


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _env_float(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def compute_image_phash(image: Image.Image) -> str:
    """Compute the version-1 orientation-normalized 64-bit DCT pHash.

    Version 1 uses EXIF transpose, 32x32 Lanczos luminance, OpenCV's 2-D DCT,
    the top-left 8x8 coefficients, and a median threshold including the DC term.
    """
    oriented = ImageOps.exif_transpose(image)
    try:
        luminance = oriented.convert("L").resize(
            (32, 32), Image.Resampling.LANCZOS
        )
        pixels = np.asarray(luminance, dtype=np.float32)
        coefficients = cv2.dct(pixels)
        low_frequency = coefficients[:8, :8]
        median = float(np.median(low_frequency))
        bits = (low_frequency > median).flatten()
        value = 0
        for bit in bits:
            value = (value << 1) | int(bool(bit))
        return f"{value:016x}"
    finally:
        if oriented is not image:
            oriented.close()


def phash_hamming_distance(first: str, second: str) -> int:
    """Return Hamming distance for two canonical 64-bit pHash values."""
    if not _HEX_64_PATTERN.fullmatch(first) or not _HEX_64_PATTERN.fullmatch(second):
        raise ValueError("pHash values must contain exactly 16 hexadecimal characters")
    return (int(first, 16) ^ int(second, 16)).bit_count()


def compare_image_phash(
    first: str,
    second: str,
    *,
    max_distance: Optional[int] = None,
) -> FingerprintSimilarityResult:
    """Compare two 64-bit image pHashes using configurable Hamming distance."""
    threshold_distance = (
        max_distance
        if max_distance is not None
        else _env_int(
            "FORENSIC_IMAGE_PHASH_MAX_DISTANCE",
            DEFAULT_IMAGE_PHASH_MAX_DISTANCE,
            0,
            64,
        )
    )
    if not 0 <= threshold_distance <= 64:
        raise ValueError("max_distance must be between 0 and 64")
    distance = phash_hamming_distance(first, second)
    score = 1.0 - (distance / 64.0)
    return FingerprintSimilarityResult(
        media_type="image",
        similarity_score=round(score, 6),
        distance=float(distance),
        threshold=round(1.0 - (threshold_distance / 64.0), 6),
        is_similar=distance <= threshold_distance,
        method="64-bit-phash-hamming-distance",
        method_version=PHASH_VERSION,
        limitations=[
            "Perceptual similarity does not prove identical origin, meaning, or authenticity.",
            "Large crops, overlays, rotations not represented by EXIF, and content-preserving edits can change pHash distance.",
        ],
    )


def _image_fingerprint(path: Path) -> PerceptualFingerprint:
    max_file_bytes = _env_int(
        "FORENSIC_FINGERPRINT_IMAGE_MAX_FILE_BYTES",
        DEFAULT_IMAGE_MAX_FILE_BYTES,
        1_048_576,
        500 * 1024 * 1024,
    )
    max_decode_pixels = _env_int(
        "FORENSIC_FINGERPRINT_IMAGE_MAX_DECODE_PIXELS",
        DEFAULT_IMAGE_MAX_DECODE_PIXELS,
        65_536,
        250_000_000,
    )
    if path.stat().st_size > max_file_bytes:
        raise _FingerprintUnavailable("Image exceeds the fingerprint file-size limit.")
    with python_warnings.catch_warnings():
        python_warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(path) as image:
            width, height = image.size
            if width <= 0 or height <= 0 or width * height > max_decode_pixels:
                raise _FingerprintUnavailable(
                    "Image dimensions exceed the fingerprint pixel limit."
                )
            image.load()
            value = compute_image_phash(image)
    return PerceptualFingerprint(
        status="available",
        algorithm=PHASH_ALGORITHM,
        algorithm_version=PHASH_VERSION,
        value=value,
        hash_size=64,
        warnings=[
            "This pHash is a similarity aid, not a security or integrity hash."
        ],
    )


def _frame_to_phash(frame: Union[Image.Image, np.ndarray]) -> str:
    if isinstance(frame, Image.Image):
        return compute_image_phash(frame)
    if not isinstance(frame, np.ndarray) or frame.ndim not in {2, 3} or frame.size == 0:
        raise ValueError("Video fingerprint frames must be non-empty image arrays")
    if frame.ndim == 2:
        image = Image.fromarray(frame.astype(np.uint8), mode="L")
    else:
        channels = frame.shape[2]
        if channels == 3:
            image = Image.fromarray(frame.astype(np.uint8), mode="RGB")
        elif channels == 4:
            image = Image.fromarray(frame.astype(np.uint8), mode="RGBA")
        else:
            raise ValueError("Video fingerprint frames must have 1, 3, or 4 channels")
    try:
        return compute_image_phash(image)
    finally:
        image.close()


def build_video_fingerprint(
    frames: Sequence[Union[Image.Image, np.ndarray]],
    timestamps_seconds: Sequence[float],
    *,
    duration_seconds: Optional[float],
) -> PerceptualFingerprint:
    """Build ordered video pHash components and a deterministic composite.

    The composite is a storage identity for this exact sampled sequence only.
    Video similarity must use component alignment, not composite equality.
    """
    if not frames or len(frames) != len(timestamps_seconds):
        raise ValueError("Video frames and timestamps must be non-empty and equal length")
    components: List[FingerprintComponent] = []
    for index, (frame, timestamp) in enumerate(zip(frames, timestamps_seconds)):
        numeric_timestamp = float(timestamp)
        if not math.isfinite(numeric_timestamp) or numeric_timestamp < 0:
            raise ValueError("Video component timestamps must be finite and non-negative")
        components.append(
            FingerprintComponent(
                index=index,
                timestamp_seconds=round(numeric_timestamp, 6),
                value=_frame_to_phash(frame),
            )
        )
    canonical = "|".join(
        f"{component.index}:{component.timestamp_seconds:.6f}:{component.value}"
        for component in components
    )
    composite = hashlib.sha256(canonical.encode("ascii")).hexdigest()
    return PerceptualFingerprint(
        status="available",
        algorithm=VIDEO_ALGORITHM,
        algorithm_version=VIDEO_VERSION,
        value=composite,
        hash_size=64,
        components=components,
        duration_seconds=(
            round(float(duration_seconds), 6)
            if duration_seconds is not None and float(duration_seconds) >= 0
            else None
        ),
        warnings=[
            "The composite identifies the sampled pHash sequence; similarity uses ordered components rather than composite equality.",
            "Video perceptual similarity does not prove identical origin, meaning, or authenticity.",
        ],
    )


def _positive_capture_value(value: float) -> Optional[float]:
    return float(value) if math.isfinite(float(value)) and value > 0 else None


def _bounded_frame(frame: np.ndarray, maximum_dimension: int) -> np.ndarray:
    height, width = frame.shape[:2]
    largest = max(width, height)
    if largest <= maximum_dimension:
        return frame
    scale = maximum_dimension / largest
    resized_width = max(1, round(width * scale))
    resized_height = max(1, round(height * scale))
    return cv2.resize(
        frame,
        (resized_width, resized_height),
        interpolation=cv2.INTER_AREA,
    )


def _read_video_samples(path: Path) -> Tuple[List[np.ndarray], List[float], Optional[float]]:
    frame_count_limit = _env_int(
        "FORENSIC_VIDEO_FINGERPRINT_FRAME_COUNT",
        DEFAULT_VIDEO_FRAME_COUNT,
        2,
        32,
    )
    frame_max_dimension = _env_int(
        "FORENSIC_VIDEO_FINGERPRINT_FRAME_MAX_DIMENSION",
        DEFAULT_VIDEO_FRAME_MAX_DIMENSION,
        32,
        2048,
    )
    max_source_pixels = _env_int(
        "FORENSIC_VIDEO_FINGERPRINT_MAX_SOURCE_PIXELS",
        DEFAULT_VIDEO_MAX_SOURCE_PIXELS,
        65_536,
        250_000_000,
    )
    max_decode_frames = _env_int(
        "FORENSIC_VIDEO_FINGERPRINT_MAX_DECODE_FRAMES",
        DEFAULT_VIDEO_MAX_DECODE_FRAMES,
        32,
        1_000_000,
    )
    max_duration = _env_float(
        "FORENSIC_VIDEO_FINGERPRINT_MAX_DURATION_SECONDS",
        DEFAULT_VIDEO_MAX_DURATION_SECONDS,
        1.0,
        86_400.0,
    )
    timeout_seconds = _env_float(
        "FORENSIC_VIDEO_FINGERPRINT_TIMEOUT_SECONDS",
        DEFAULT_VIDEO_TIMEOUT_SECONDS,
        0.1,
        120.0,
    )
    deadline = perf_counter() + timeout_seconds
    timeout_milliseconds = max(1, round(timeout_seconds * 1000))
    capture_parameters: List[int] = []
    if hasattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC"):
        capture_parameters.extend(
            [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_milliseconds]
        )
    if hasattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC"):
        capture_parameters.extend(
            [cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout_milliseconds]
        )
    capture = cv2.VideoCapture(str(path), cv2.CAP_ANY, capture_parameters)
    if not capture.isOpened():
        capture.release()
        raise ValueError("Video could not be opened for fingerprinting.")
    try:
        fps = _positive_capture_value(capture.get(cv2.CAP_PROP_FPS))
        total_value = _positive_capture_value(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width = _positive_capture_value(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = _positive_capture_value(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(total_value) if total_value else None
        if width and height and width * height > max_source_pixels:
            raise _FingerprintUnavailable(
                "Video frame dimensions exceed the fingerprint pixel limit."
            )
        duration = total_frames / fps if total_frames and fps else None
        if duration is not None and duration > max_duration:
            raise _FingerprintUnavailable(
                "Video duration exceeds the configured fingerprint limit."
            )

        samples: List[Tuple[int, np.ndarray]] = []
        if total_frames:
            target_count = min(frame_count_limit, total_frames)
            indices = np.unique(
                np.linspace(0, total_frames - 1, target_count, dtype=int)
            )
            for frame_index in indices:
                if perf_counter() > deadline:
                    raise _FingerprintUnavailable(
                        "Video fingerprinting exceeded the configured timeout."
                    )
                capture.set(cv2.CAP_PROP_POS_FRAMES, int(frame_index))
                ok, frame = capture.read()
                if ok and frame is not None and frame.size:
                    if frame.shape[0] * frame.shape[1] > max_source_pixels:
                        raise _FingerprintUnavailable(
                            "Decoded video frame exceeds the fingerprint pixel limit."
                        )
                    samples.append(
                        (int(frame_index), _bounded_frame(frame, frame_max_dimension))
                    )

        if len(samples) < min(frame_count_limit, total_frames or frame_count_limit):
            capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            reservoir: List[Tuple[int, np.ndarray]] = []
            random = np.random.default_rng(0)
            decoded = 0
            while decoded < max_decode_frames:
                if perf_counter() > deadline:
                    raise _FingerprintUnavailable(
                        "Video fingerprinting exceeded the configured timeout."
                    )
                ok, frame = capture.read()
                if not ok or frame is None:
                    break
                if not frame.size:
                    decoded += 1
                    continue
                if frame.shape[0] * frame.shape[1] > max_source_pixels:
                    raise _FingerprintUnavailable(
                        "Decoded video frame exceeds the fingerprint pixel limit."
                    )
                bounded = _bounded_frame(frame, frame_max_dimension)
                if len(reservoir) < frame_count_limit:
                    reservoir.append((decoded, bounded))
                else:
                    replacement = int(random.integers(0, decoded + 1))
                    if replacement < frame_count_limit:
                        reservoir[replacement] = (decoded, bounded)
                decoded += 1
            reservoir.sort(key=lambda item: item[0])
            if reservoir:
                samples = reservoir
                if total_frames is None:
                    total_frames = decoded
                    if fps:
                        duration = decoded / fps

        if duration is not None and duration > max_duration:
            raise _FingerprintUnavailable(
                "Video duration exceeds the configured fingerprint limit."
            )

        if not samples:
            raise ValueError("No decodable video frames were available for fingerprinting.")
        samples.sort(key=lambda item: item[0])
        frames = [cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) for _, frame in samples]
        timestamps = [
            (frame_index / fps if fps else float(position))
            for position, (frame_index, _) in enumerate(samples)
        ]
        return frames, timestamps, duration
    finally:
        capture.release()


def _video_fingerprint(path: Path) -> PerceptualFingerprint:
    frames, timestamps, duration = _read_video_samples(path)
    return build_video_fingerprint(
        frames,
        timestamps,
        duration_seconds=duration,
    )


def _normalized_component_positions(
    fingerprint: PerceptualFingerprint,
) -> List[float]:
    components = fingerprint.components
    if not components:
        return []
    duration = fingerprint.duration_seconds
    if duration and duration > 0 and all(
        component.timestamp_seconds is not None for component in components
    ):
        return [
            min(1.0, max(0.0, float(component.timestamp_seconds) / duration))
            for component in components
        ]
    denominator = max(1, len(components) - 1)
    return [index / denominator for index in range(len(components))]


def compare_video_fingerprints(
    first: PerceptualFingerprint,
    second: PerceptualFingerprint,
) -> FingerprintSimilarityResult:
    """Compare ordered video frame pHashes with timestamp-normalized alignment."""
    if first.algorithm != VIDEO_ALGORITHM or second.algorithm != VIDEO_ALGORITHM:
        raise ValueError("Video fingerprint algorithms are incompatible")
    if first.algorithm_version != VIDEO_VERSION or second.algorithm_version != VIDEO_VERSION:
        raise ValueError("Video fingerprint versions are incompatible")
    if not first.components or not second.components:
        raise ValueError("Video fingerprints require ordered components")
    component_distance = _env_int(
        "FORENSIC_VIDEO_COMPONENT_PHASH_MAX_DISTANCE",
        DEFAULT_VIDEO_COMPONENT_MAX_DISTANCE,
        0,
        64,
    )
    timestamp_tolerance = _env_float(
        "FORENSIC_VIDEO_TIMESTAMP_TOLERANCE",
        DEFAULT_VIDEO_TIMESTAMP_TOLERANCE,
        0.0,
        1.0,
    )
    score_threshold = _env_float(
        "FORENSIC_VIDEO_SIMILARITY_THRESHOLD",
        DEFAULT_VIDEO_SIMILARITY_THRESHOLD,
        0.0,
        1.0,
    )
    minimum_match_ratio = _env_float(
        "FORENSIC_VIDEO_MIN_MATCH_RATIO",
        DEFAULT_VIDEO_MIN_MATCH_RATIO,
        0.0,
        1.0,
    )
    first_positions = _normalized_component_positions(first)
    second_positions = _normalized_component_positions(second)
    rows, columns = len(first.components), len(second.components)
    # State is (accumulated similarity weight, matches, total Hamming distance).
    states: List[List[Tuple[float, int, int]]] = [
        [(0.0, 0, 0) for _ in range(columns + 1)] for _ in range(rows + 1)
    ]

    def better(
        left: Tuple[float, int, int], right: Tuple[float, int, int]
    ) -> Tuple[float, int, int]:
        return max(left, right, key=lambda item: (item[0], item[1], -item[2]))

    for row in range(1, rows + 1):
        for column in range(1, columns + 1):
            best = better(states[row - 1][column], states[row][column - 1])
            if abs(first_positions[row - 1] - second_positions[column - 1]) <= timestamp_tolerance:
                distance = phash_hamming_distance(
                    first.components[row - 1].value,
                    second.components[column - 1].value,
                )
                if distance <= component_distance:
                    previous = states[row - 1][column - 1]
                    candidate = (
                        previous[0] + (1.0 - distance / 64.0),
                        previous[1] + 1,
                        previous[2] + distance,
                    )
                    best = better(best, candidate)
            states[row][column] = best

    weight, matches, total_distance = states[rows][columns]
    shorter_length = min(rows, columns)
    score = weight / shorter_length
    overlap_ratio = matches / shorter_length
    average_distance = total_distance / matches if matches else 64.0
    return FingerprintSimilarityResult(
        media_type="video",
        similarity_score=round(score, 6),
        distance=round(average_distance, 6),
        threshold=score_threshold,
        is_similar=(
            score >= score_threshold and overlap_ratio >= minimum_match_ratio
        ),
        matched_components=matches,
        overlap_ratio=round(overlap_ratio, 6),
        method="timestamp-normalized-monotonic-frame-phash-alignment",
        method_version=VIDEO_VERSION,
        limitations=[
            "The score is based on a bounded frame sample and can miss changes between sampled frames.",
            "Similar frame sequences do not prove identical origin, meaning, or authenticity.",
        ],
    )


def _parse_fpcalc_output(
    output: ProcessOutput,
    max_components: int,
) -> Tuple[float, List[int]]:
    if output.timed_out:
        raise _FingerprintUnavailable("fpcalc exceeded the fingerprint timeout.")
    if output.stdout_truncated or output.stderr_truncated:
        raise ValueError("fpcalc output exceeded the configured byte limit.")
    if output.returncode != 0:
        raise ValueError(f"fpcalc failed with exit code {output.returncode}.")
    try:
        parsed = json.loads(output.stdout.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("fpcalc returned malformed JSON.") from exc
    if not isinstance(parsed, dict):
        raise ValueError("fpcalc returned an unexpected JSON structure.")
    duration = parsed.get("duration")
    fingerprint = parsed.get("fingerprint")
    if not isinstance(duration, (int, float)) or not math.isfinite(float(duration)):
        raise ValueError("fpcalc did not return a valid duration.")
    if not isinstance(fingerprint, list) or not fingerprint:
        raise ValueError("fpcalc did not return a raw fingerprint array.")
    if len(fingerprint) > max_components:
        raise ValueError("fpcalc raw fingerprint exceeds the configured component limit.")
    values: List[int] = []
    for value in fingerprint:
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 0xFFFFFFFF:
            raise ValueError("fpcalc raw fingerprint contains an invalid value.")
        values.append(value)
    return float(duration), values


def _audio_fingerprint(path: Path) -> PerceptualFingerprint:
    executable = discover_executable("FPCALC_PATH", ("fpcalc", "fpcalc.exe"))
    if not executable:
        return PerceptualFingerprint(
            status="unavailable",
            algorithm=AUDIO_ALGORITHM,
            algorithm_version=AUDIO_VERSION,
            hash_size=32,
            warnings=[
                "fpcalc is unavailable; only audio perceptual fingerprinting was disabled."
            ],
        )
    max_duration = _env_int(
        "FORENSIC_AUDIO_FINGERPRINT_MAX_DURATION_SECONDS",
        DEFAULT_AUDIO_MAX_DURATION_SECONDS,
        1,
        600,
    )
    timeout_seconds = _env_float(
        "FORENSIC_AUDIO_FINGERPRINT_TIMEOUT_SECONDS",
        DEFAULT_AUDIO_TIMEOUT_SECONDS,
        0.1,
        120.0,
    )
    output_bytes = _env_int(
        "FORENSIC_AUDIO_FINGERPRINT_OUTPUT_MAX_BYTES",
        DEFAULT_AUDIO_OUTPUT_BYTES,
        4096,
        4 * 1024 * 1024,
    )
    max_components = _env_int(
        "FORENSIC_AUDIO_FINGERPRINT_MAX_COMPONENTS",
        DEFAULT_AUDIO_MAX_COMPONENTS,
        16,
        65_536,
    )
    arguments = [
        executable,
        "-raw",
        "-json",
        "-algorithm",
        "2",
        "-length",
        str(max_duration),
        "--",
        str(path),
    ]
    output = _run_bounded_process(
        arguments,
        timeout_seconds=timeout_seconds,
        output_limit_bytes=output_bytes,
    )
    duration, values = _parse_fpcalc_output(output, max_components)
    warnings = [
        "Chromaprint is designed for near-identical audio matching, not semantic audio similarity or integrity verification."
    ]
    if duration > max_duration:
        warnings.append(
            f"The fingerprint covers at most the configured first {max_duration} seconds."
        )
    return PerceptualFingerprint(
        status="available",
        algorithm=AUDIO_ALGORITHM,
        algorithm_version=AUDIO_VERSION,
        value=",".join(str(value) for value in values),
        hash_size=32,
        duration_seconds=round(duration, 6),
        warnings=warnings,
    )


def _parse_audio_raw_value(value: Optional[str]) -> List[int]:
    if not value:
        raise ValueError("Audio fingerprint value is missing")
    parts = value.split(",")
    maximum = _env_int(
        "FORENSIC_AUDIO_FINGERPRINT_MAX_COMPONENTS",
        DEFAULT_AUDIO_MAX_COMPONENTS,
        16,
        65_536,
    )
    if not parts or len(parts) > maximum:
        raise ValueError("Audio fingerprint component count is invalid")
    values: List[int] = []
    for part in parts:
        if not part.isdigit():
            raise ValueError("Audio fingerprint contains a non-integer component")
        numeric = int(part)
        if not 0 <= numeric <= 0xFFFFFFFF:
            raise ValueError("Audio fingerprint component is outside uint32 range")
        values.append(numeric)
    return values


def compare_audio_fingerprints(
    first: PerceptualFingerprint,
    second: PerceptualFingerprint,
) -> FingerprintSimilarityResult:
    """Compare raw Chromaprint uint32 sequences by offset-aligned bit error.

    This operates on raw 32-bit subfingerprints, not edit distance over fpcalc's
    compressed textual representation.
    """
    if first.algorithm != AUDIO_ALGORITHM or second.algorithm != AUDIO_ALGORITHM:
        raise ValueError("Audio fingerprint algorithms are incompatible")
    if first.algorithm_version != AUDIO_VERSION or second.algorithm_version != AUDIO_VERSION:
        raise ValueError("Audio fingerprint versions are incompatible")
    first_values = _parse_audio_raw_value(first.value)
    second_values = _parse_audio_raw_value(second.value)
    max_offset = _env_int(
        "FORENSIC_AUDIO_FINGERPRINT_MAX_ALIGNMENT_OFFSET",
        DEFAULT_AUDIO_MAX_ALIGNMENT_OFFSET,
        0,
        4096,
    )
    max_bit_errors = _env_int(
        "FORENSIC_AUDIO_FINGERPRINT_MAX_COMPONENT_BIT_ERRORS",
        DEFAULT_AUDIO_MAX_COMPONENT_BIT_ERRORS,
        0,
        32,
    )
    min_overlap_config = _env_int(
        "FORENSIC_AUDIO_FINGERPRINT_MIN_OVERLAP_COMPONENTS",
        DEFAULT_AUDIO_MIN_OVERLAP_COMPONENTS,
        1,
        4096,
    )
    score_threshold = _env_float(
        "FORENSIC_AUDIO_SIMILARITY_THRESHOLD",
        DEFAULT_AUDIO_SIMILARITY_THRESHOLD,
        0.0,
        1.0,
    )
    min_overlap_ratio = _env_float(
        "FORENSIC_AUDIO_MIN_OVERLAP_RATIO",
        DEFAULT_AUDIO_MIN_OVERLAP_RATIO,
        0.0,
        1.0,
    )
    shorter_length = min(len(first_values), len(second_values))
    required_overlap = min(min_overlap_config, shorter_length)
    # This follows pyacoustid's public raw-fingerprint matcher: count pairs
    # within a small per-component XOR bit error at each alignment offset and
    # take the strongest offset, normalized by the shorter fingerprint.
    best: Optional[Tuple[int, int, int]] = None
    for offset in range(-min(max_offset, len(second_values) - 1), min(max_offset, len(first_values) - 1) + 1):
        first_start = max(0, offset)
        second_start = max(0, -offset)
        overlap = min(
            len(first_values) - first_start,
            len(second_values) - second_start,
        )
        if overlap < required_overlap:
            continue
        matched = sum(
            1
            for index in range(overlap)
            if (
                first_values[first_start + index]
                ^ second_values[second_start + index]
            ).bit_count()
            <= max_bit_errors
        )
        candidate = (matched, overlap, -abs(offset))
        if best is None or candidate > best:
            best = candidate
    if best is None:
        raise ValueError("Audio fingerprints do not have sufficient overlap")
    matched, overlap, _ = best
    overlap_ratio = overlap / shorter_length
    score = matched / shorter_length
    return FingerprintSimilarityResult(
        media_type="audio",
        similarity_score=round(score, 6),
        distance=round(1.0 - score, 6),
        threshold=score_threshold,
        is_similar=(score >= score_threshold and overlap_ratio >= min_overlap_ratio),
        matched_components=matched,
        overlap_ratio=round(overlap_ratio, 6),
        method="pyacoustid-offset-aligned-raw-subfingerprint-match",
        method_version=AUDIO_VERSION,
        limitations=[
            "The matcher follows pyacoustid's offset-count comparison over raw uint32 subfingerprints with a bounded XOR bit-error allowance.",
            "Chromaprint targets near-identical audio and is not a semantic audio comparison.",
            "A high score does not prove identical source, ownership, or authenticity.",
        ],
    )


def extract_perceptual_fingerprint(
    file_path: PathLike,
    *,
    detected_mime_type: str,
    allowed_root: Optional[PathLike] = None,
) -> FingerprintExtractionResult:
    """Extract one bounded media-specific fingerprint with structured failure."""
    started_at = perf_counter()

    def elapsed_ms() -> int:
        return max(0, round((perf_counter() - started_at) * 1000))

    supported = (
        detected_mime_type in _SUPPORTED_IMAGE_MIME_TYPES
        or detected_mime_type in _SUPPORTED_VIDEO_MIME_TYPES
        or detected_mime_type in _SUPPORTED_AUDIO_MIME_TYPES
    )
    if not supported:
        return FingerprintExtractionResult(
            fingerprint={
                "status": "unsupported",
                "warnings": ["Perceptual fingerprinting does not support this media type."],
            },
            processing_time_ms=elapsed_ms(),
        )
    try:
        path = resolve_workspace_file(file_path, allowed_root)
        if detected_mime_type in _SUPPORTED_IMAGE_MIME_TYPES:
            fingerprint = _image_fingerprint(path)
        elif detected_mime_type in _SUPPORTED_VIDEO_MIME_TYPES:
            fingerprint = _video_fingerprint(path)
        else:
            fingerprint = _audio_fingerprint(path)
        return FingerprintExtractionResult(
            fingerprint=fingerprint,
            processing_time_ms=elapsed_ms(),
        )
    except _FingerprintUnavailable as exc:
        return FingerprintExtractionResult(
            fingerprint={
                "status": "unavailable",
                "warnings": [str(exc)[:512]],
            },
            processing_time_ms=elapsed_ms(),
        )
    except ValueError as exc:
        return FingerprintExtractionResult(
            fingerprint={
                "status": "error",
                "warnings": [str(exc)[:512] or "Perceptual fingerprinting failed."],
            },
            processing_time_ms=elapsed_ms(),
        )
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
    ):
        return FingerprintExtractionResult(
            fingerprint={
                "status": "error",
                "warnings": ["Media decoding failed during perceptual fingerprinting."],
            },
            processing_time_ms=elapsed_ms(),
        )
    except Exception:
        return FingerprintExtractionResult(
            fingerprint={
                "status": "error",
                "warnings": ["Perceptual fingerprinting failed unexpectedly."],
            },
            processing_time_ms=elapsed_ms(),
        )

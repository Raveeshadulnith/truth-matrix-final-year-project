from __future__ import annotations

import io
import math
import os
import re
import warnings as python_warnings
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field

from forensics.hashing import resolve_workspace_file
from forensics.inconsistencies import deduplicate_findings
from schemas.forensic_schema import (
    CreationInfo,
    ExtractorStatus,
    FindingSeverity,
    ForensicFinding,
    MetadataEvidence,
    SoftwareCategory,
)


PathLike = Union[str, Path]
METHOD_VERSION = "1"

DEFAULT_MAX_FILE_BYTES = 50 * 1024 * 1024
DEFAULT_MAX_DECODE_PIXELS = 50_000_000
DEFAULT_MAX_ANALYSIS_PIXELS = 1_048_576
DEFAULT_BLOCK_SCORE_THRESHOLD = 0.15
DEFAULT_ELA_QUALITY = 90
DEFAULT_RATE_DIFFERENCE_RATIO = 0.01
DEFAULT_DURATION_TOLERANCE_SECONDS = 0.5
DEFAULT_DURATION_TOLERANCE_RATIO = 0.02

_SUPPORTED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
_SUPPORTED_VIDEO_MIME_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/x-msvideo",
    "video/x-matroska",
    "video/webm",
}
_SUPPORTED_AUDIO_MIME_TYPES = {"audio/wav", "audio/mpeg", "audio/mp4"}
_EDITING_SOFTWARE_MARKERS = (
    "photoshop",
    "lightroom",
    "gimp",
    "premiere",
    "after effects",
    "davinci resolve",
    "final cut",
    "capcut",
    "canva",
    "stable diffusion",
    "midjourney",
    "dall-e",
    "dalle",
    "generative ai",
    "ai generator",
)

# ITU-T T.81 / IJG reference quantization tables used by the common JPEG
# quality scaling convention. Custom encoders may use different tables.
_JPEG_LUMA_TABLE = (
    16, 11, 10, 16, 24, 40, 51, 61,
    12, 12, 14, 19, 26, 58, 60, 55,
    14, 13, 16, 24, 40, 57, 69, 56,
    14, 17, 22, 29, 51, 87, 80, 62,
    18, 22, 37, 56, 68, 109, 103, 77,
    24, 35, 55, 64, 81, 104, 113, 92,
    49, 64, 78, 87, 103, 121, 120, 101,
    72, 92, 95, 98, 112, 100, 103, 99,
)
_JPEG_CHROMA_TABLE = (
    17, 18, 24, 47, 99, 99, 99, 99,
    18, 21, 26, 66, 99, 99, 99, 99,
    24, 26, 56, 99, 99, 99, 99, 99,
    47, 66, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99,
)


class CompressionExtractionResult(BaseModel):
    """Independent compression extractor result."""

    model_config = ConfigDict(extra="forbid")

    status: ExtractorStatus
    indicators: List[ForensicFinding] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    processing_time_ms: int = Field(..., ge=0)


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


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")


def _finding(
    *,
    code: str,
    title: str,
    severity: FindingSeverity,
    explanation: str,
    evidence: Dict[str, Any],
    method: str,
    limitations: Sequence[str],
) -> ForensicFinding:
    return ForensicFinding(
        code=code,
        title=title,
        severity=severity,
        explanation=explanation,
        evidence=evidence,
        method=method,
        method_version=METHOD_VERSION,
        limitations=list(limitations),
    )


def _bit_depth(mode: str) -> Optional[int]:
    if mode == "1":
        return 1
    if mode.startswith("I;16"):
        return 16
    if mode in {"I", "F"}:
        return 32
    if mode in {"L", "LA", "P", "RGB", "RGBA", "RGBX", "CMYK", "YCbCr", "LAB", "HSV"}:
        return 8
    return None


def _scaled_jpeg_table(reference: Sequence[int], quality: int) -> Tuple[int, ...]:
    scale = 5000 / quality if quality < 50 else 200 - (2 * quality)
    return tuple(
        max(1, min(255, int((value * scale + 50) // 100)))
        for value in reference
    )


def estimate_jpeg_quality(
    quantization_tables: Dict[int, Sequence[int]],
) -> Optional[Tuple[int, float]]:
    """Estimate IJG-style JPEG quality from standard-layout quantization tables.

    Returns the closest quality in 1..100 and its mean absolute quantization
    error. The estimate is intentionally unavailable for malformed tables.
    """
    observed: List[Tuple[Tuple[int, ...], Tuple[int, ...]]] = []
    for table_id, reference in ((0, _JPEG_LUMA_TABLE), (1, _JPEG_CHROMA_TABLE)):
        table = quantization_tables.get(table_id)
        if table is None:
            continue
        try:
            values = tuple(int(value) for value in table)
        except (TypeError, ValueError):
            return None
        if len(values) != 64 or any(value < 1 or value > 255 for value in values):
            return None
        observed.append((values, reference))
    if not observed:
        return None

    candidates: List[Tuple[float, int]] = []
    for quality in range(1, 101):
        differences: List[int] = []
        for table, reference in observed:
            expected = _scaled_jpeg_table(reference, quality)
            differences.extend(abs(actual - predicted) for actual, predicted in zip(table, expected))
        candidates.append((sum(differences) / len(differences), quality))
    error, quality = min(candidates, key=lambda item: (item[0], -item[1]))
    return quality, round(error, 6)


def _analysis_crop(image: Image.Image, max_analysis_pixels: int) -> Image.Image:
    width, height = image.size
    if width * height <= max_analysis_pixels:
        return image.copy()
    scale = math.sqrt(max_analysis_pixels / (width * height))
    crop_width = max(1, min(width, int(width * scale)))
    crop_height = max(1, min(height, max_analysis_pixels // crop_width))
    # A top-left crop preserves the source JPEG 8x8 grid. Resizing would destroy
    # the block alignment the discontinuity method is intended to measure.
    return image.crop((0, 0, crop_width, crop_height))


def calculate_block_discontinuity(
    image: Image.Image,
) -> Optional[Dict[str, Union[float, int]]]:
    """Calculate excess discontinuity at the source-aligned 8x8 boundaries.

    The score is max(0, (B-N)/(B+N)), where B is mean luminance difference at
    block boundaries and N is the mean at other adjacent pixels. It ranges from
    zero (no excess boundary discontinuity) to one (maximal relative excess).
    """
    luminance = np.asarray(image.convert("L"), dtype=np.float32)
    height, width = luminance.shape
    if width < 16 or height < 16:
        return None

    horizontal = np.abs(np.diff(luminance, axis=1))
    vertical = np.abs(np.diff(luminance, axis=0))
    horizontal_boundary = np.arange(1, width) % 8 == 0
    vertical_boundary = np.arange(1, height) % 8 == 0
    if not horizontal_boundary.any() or not vertical_boundary.any():
        return None

    boundary_values = np.concatenate(
        (horizontal[:, horizontal_boundary].ravel(), vertical[vertical_boundary, :].ravel())
    )
    non_boundary_values = np.concatenate(
        (horizontal[:, ~horizontal_boundary].ravel(), vertical[~vertical_boundary, :].ravel())
    )
    if not boundary_values.size or not non_boundary_values.size:
        return None
    boundary_mean = float(boundary_values.mean()) / 255.0
    non_boundary_mean = float(non_boundary_values.mean()) / 255.0
    denominator = boundary_mean + non_boundary_mean
    score = max(0.0, (boundary_mean - non_boundary_mean) / denominator) if denominator else 0.0
    return {
        "score": round(min(1.0, score), 6),
        "boundary_mean_normalized": round(boundary_mean, 6),
        "non_boundary_mean_normalized": round(non_boundary_mean, 6),
        "analyzed_width": width,
        "analyzed_height": height,
    }


def calculate_ela_summary(image: Image.Image, jpeg_quality: int) -> Dict[str, float]:
    """Return a bounded numeric ELA difference summary without a visualization."""
    rgb = image.convert("RGB")
    buffer = io.BytesIO()
    rgb.save(buffer, format="JPEG", quality=jpeg_quality, optimize=False)
    buffer.seek(0)
    with Image.open(buffer) as recompressed:
        source = np.asarray(rgb, dtype=np.int16)
        comparison = np.asarray(recompressed.convert("RGB"), dtype=np.int16)
    difference = np.abs(source - comparison).astype(np.float32) / 255.0
    return {
        "mean_absolute_error": round(float(difference.mean()), 6),
        "p95_absolute_error": round(float(np.percentile(difference, 95)), 6),
        "maximum_absolute_error": round(float(difference.max()), 6),
    }


def _software_indicators(creation_info: CreationInfo) -> List[ForensicFinding]:
    if not creation_info.software:
        return []
    editing_values = [
        observation.name
        for observation in creation_info.software_observations
        if observation.category
        in {SoftwareCategory.EDITOR, SoftwareCategory.AI_GENERATION}
    ]
    if not creation_info.software_observations:
        editing_values = [
            value
            for value in creation_info.software
            if any(marker in value.casefold() for marker in _EDITING_SOFTWARE_MARKERS)
        ]
    if editing_values:
        return [
            _finding(
                code="compression.editing_software_metadata",
                title="Editing or generation software appears in metadata",
                severity=FindingSeverity.INFO,
                explanation="Embedded metadata names software associated with editing or generation workflows.",
                evidence={
                    "software": editing_values,
                    "source_tags": creation_info.source_tags.get("software", []),
                },
                method="sanitized-software-tag-match",
                limitations=[
                    "Software metadata can reflect an ordinary export, crop, color correction, or legitimate generation-assisted workflow.",
                    "Its presence does not prove malicious editing or that the media is fake.",
                ],
            )
        ]
    return [
        _finding(
            code="compression.encoder_metadata",
            title="Software or encoder metadata is present",
            severity=FindingSeverity.INFO,
            explanation="Embedded metadata identifies software, an encoder, or a writing library involved in the media workflow.",
            evidence={
                "software": creation_info.software,
                "source_tags": creation_info.source_tags.get("software", []),
            },
            method="sanitized-software-tag-observation",
            limitations=[
                "Encoding and transcoding are routine, including on cameras and social-media services.",
                "This observation does not prove content editing or fakery.",
            ],
        )
    ]


def _image_indicators(
    path: Path,
    detected_mime_type: str,
    creation_info: CreationInfo,
) -> List[ForensicFinding]:
    max_file_bytes = _env_int(
        "FORENSIC_COMPRESSION_MAX_FILE_BYTES",
        DEFAULT_MAX_FILE_BYTES,
        1_048_576,
        500 * 1024 * 1024,
    )
    max_decode_pixels = _env_int(
        "FORENSIC_COMPRESSION_MAX_DECODE_PIXELS",
        DEFAULT_MAX_DECODE_PIXELS,
        65_536,
        250_000_000,
    )
    max_analysis_pixels = _env_int(
        "FORENSIC_COMPRESSION_MAX_ANALYSIS_PIXELS",
        DEFAULT_MAX_ANALYSIS_PIXELS,
        4_096,
        4_194_304,
    )
    block_threshold = _env_float(
        "FORENSIC_JPEG_BLOCK_SCORE_THRESHOLD",
        DEFAULT_BLOCK_SCORE_THRESHOLD,
        0.0,
        1.0,
    )
    ela_enabled = _env_bool("FORENSIC_ELA_ENABLED", False)
    ela_quality = _env_int(
        "FORENSIC_ELA_JPEG_QUALITY",
        DEFAULT_ELA_QUALITY,
        1,
        100,
    )
    if path.stat().st_size > max_file_bytes:
        raise ValueError("Image exceeds the configured compression-analysis file-size limit.")

    with python_warnings.catch_warnings():
        python_warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(path) as image:
            width, height = image.size
            if width <= 0 or height <= 0 or width * height > max_decode_pixels:
                raise ValueError("Image dimensions exceed the configured compression-analysis pixel limit.")
            image.load()
            actual_format = (image.format or "unknown").upper()
            mode = image.mode
            alpha_present = "A" in image.getbands() or "transparency" in image.info
            icc_profile_present = bool(image.info.get("icc_profile"))
            quantization = getattr(image, "quantization", None)
            quantization_tables: Dict[int, Sequence[int]] = (
                quantization if isinstance(quantization, dict) else {}
            )
            quality_estimate = (
                estimate_jpeg_quality(quantization_tables)
                if detected_mime_type == "image/jpeg" and quantization_tables
                else None
            )
            crop = _analysis_crop(image, max_analysis_pixels)

    characteristics: Dict[str, Any] = {
        "format": actual_format,
        "detected_mime_type": detected_mime_type,
        "width": width,
        "height": height,
        "color_mode": mode,
        "bit_depth_per_channel": _bit_depth(mode),
        "alpha_present": alpha_present,
        "icc_profile_present": icc_profile_present,
        "jpeg_quantization_tables_available": bool(quantization_tables),
        "jpeg_quantization_table_count": len(quantization_tables),
    }
    if quality_estimate:
        characteristics["jpeg_quality_estimate"] = quality_estimate[0]
        characteristics["jpeg_quality_estimate_mean_table_error"] = quality_estimate[1]

    block_indicator: Optional[ForensicFinding] = None
    if detected_mime_type == "image/jpeg":
        block = calculate_block_discontinuity(crop)
        if block is not None:
            score = float(block["score"])
            block["review_threshold"] = block_threshold
            block_indicator = _finding(
                code="compression.jpeg_block_discontinuity",
                title="JPEG 8x8 block-boundary discontinuity",
                severity=(
                    FindingSeverity.LOW if score >= block_threshold else FindingSeverity.INFO
                ),
                explanation=(
                    "The normalized score measures excess luminance discontinuity at source-aligned 8x8 JPEG block boundaries."
                ),
                evidence=block,
                method="normalized-luma-8x8-boundary-discontinuity",
                limitations=[
                    "High scores can result from normal JPEG compression, repeated social-media recompression, or content aligned to the block grid.",
                    "Low scores do not establish originality, and high scores do not prove editing or fakery.",
                    "For large images, a bounded top-left region is analyzed without resizing to preserve block alignment.",
                ],
            )
        else:
            characteristics["block_score_available"] = False
            characteristics["block_score_unavailable_reason"] = (
                "Image is too small for stable adjacent 8x8 boundary comparison."
            )

    indicators = [
        _finding(
            code="compression.image_characteristics",
            title="Image encoding characteristics",
            severity=FindingSeverity.INFO,
            explanation="These are factual image encoding and color characteristics observed by the local decoder.",
            evidence=characteristics,
            method="pillow-image-header-and-tables",
            limitations=[
                "Encoding characteristics describe the current file, not its full editing history.",
                "Missing metadata, profiles, alpha, or JPEG tables is not evidence of manipulation.",
                "The JPEG quality value is an estimate against common IJG tables and may be inaccurate for custom encoders.",
            ],
        )
    ]
    if block_indicator is not None:
        indicators.append(block_indicator)

    if ela_enabled:
        summary = calculate_ela_summary(crop, ela_quality)
        indicators.append(
            _finding(
                code="compression.ela_summary",
                title="Bounded error-level analysis summary",
                severity=FindingSeverity.INFO,
                explanation="The summary measures pixel differences after a controlled in-memory JPEG re-encoding.",
                evidence={
                    **summary,
                    "recompression_quality": ela_quality,
                    "analyzed_width": crop.width,
                    "analyzed_height": crop.height,
                    "visualization_stored": False,
                },
                method="bounded-in-memory-jpeg-error-summary",
                limitations=[
                    "ELA is highly sensitive to source format, prior compression, image content, and the selected re-encoding quality.",
                    "It cannot prove localization, editing, or fakery; no visualization is retained.",
                ],
            )
        )
    crop.close()
    indicators.extend(_software_indicators(creation_info))
    return indicators


def _walk_items(value: Any, prefix: str = "") -> Iterable[Tuple[str, Any]]:
    if isinstance(value, dict):
        for key in sorted(value, key=lambda item: str(item)):
            child = value[key]
            qualified = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(child, (dict, list)):
                yield from _walk_items(child, qualified)
            else:
                yield qualified[:512], child
    elif isinstance(value, list):
        for index, child in enumerate(value):
            qualified = f"{prefix}[{index}]"
            if isinstance(child, (dict, list)):
                yield from _walk_items(child, qualified)
            else:
                yield qualified[:512], child


def _leaf_key(source_tag: str) -> str:
    leaf = source_tag.rsplit(".", 1)[-1].rsplit(":", 1)[-1]
    return "".join(character for character in leaf.lower() if character.isalnum())


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).strip()[:128]
        if "/" in text:
            numerator, denominator = text.split("/", 1)
            try:
                denominator_number = float(denominator)
                number = float(numerator) / denominator_number if denominator_number else math.nan
            except ValueError:
                return None
        else:
            matched = re.match(r"^-?\d+(?:\.\d+)?", text)
            if not matched:
                return None
            number = float(matched.group(0))
    return number if math.isfinite(number) else None


def _ffprobe_streams(raw: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    ffprobe = raw.get("ffprobe")
    if not isinstance(ffprobe, dict):
        return None
    streams = ffprobe.get("streams")
    if not isinstance(streams, list):
        return []
    return [stream for stream in streams if isinstance(stream, dict)]


def _duration_indicator(raw: Dict[str, Any]) -> List[ForensicFinding]:
    absolute_tolerance = _env_float(
        "FORENSIC_DURATION_TOLERANCE_SECONDS",
        DEFAULT_DURATION_TOLERANCE_SECONDS,
        0.0,
        3600.0,
    )
    ratio_tolerance = _env_float(
        "FORENSIC_DURATION_TOLERANCE_RATIO",
        DEFAULT_DURATION_TOLERANCE_RATIO,
        0.0,
        1.0,
    )
    observations: List[Dict[str, Any]] = []
    for source_tag, value in _walk_items(raw):
        if _leaf_key(source_tag) != "duration":
            continue
        duration = _number(value)
        if duration is not None and duration >= 0:
            observations.append(
                {"duration_seconds": round(duration, 6), "source_tag": source_tag}
            )
    if len(observations) < 2:
        return []
    minimum = min(observations, key=lambda item: (item["duration_seconds"], item["source_tag"]))
    maximum = max(observations, key=lambda item: (item["duration_seconds"], item["source_tag"]))
    difference = maximum["duration_seconds"] - minimum["duration_seconds"]
    tolerance = max(absolute_tolerance, maximum["duration_seconds"] * ratio_tolerance)
    if difference <= tolerance:
        return []
    return [
        _finding(
            code="compression.duration_disagreement",
            title="Container and stream durations differ",
            severity=FindingSeverity.LOW,
            explanation="Container and stream duration values differ beyond the configured tolerance.",
            evidence={
                "observations": observations[:16],
                "difference_seconds": round(difference, 6),
                "effective_tolerance_seconds": round(tolerance, 6),
            },
            method="normalized-ffprobe-duration-comparison",
            limitations=[
                "Time bases, encoder delay, stream padding, and ordinary remuxing can produce duration differences.",
                "This observation does not prove editing or fakery.",
            ],
        )
    ]


def _rate_indicators(raw: Dict[str, Any], media_type: str) -> List[ForensicFinding]:
    findings: List[ForensicFinding] = []
    rate_tolerance = _env_float(
        "FORENSIC_RATE_DIFFERENCE_RATIO",
        DEFAULT_RATE_DIFFERENCE_RATIO,
        0.0,
        1.0,
    )
    streams = _ffprobe_streams(raw) or []
    if media_type == "video":
        for index, stream in enumerate(streams):
            if stream.get("codec_type") != "video":
                continue
            average = _number(stream.get("avg_frame_rate"))
            nominal = _number(stream.get("r_frame_rate"))
            if average is None or nominal is None or max(average, nominal) <= 0:
                continue
            difference_ratio = abs(average - nominal) / max(average, nominal)
            if difference_ratio > rate_tolerance:
                findings.append(
                    _finding(
                        code="compression.variable_frame_rate_indicator",
                        title="Average and nominal frame rates differ",
                        severity=FindingSeverity.INFO,
                        explanation="The reported average and nominal frame rates differ enough to indicate a potentially variable-rate timeline.",
                        evidence={
                            "stream_index": index,
                            "average_frame_rate": round(average, 6),
                            "nominal_frame_rate": round(nominal, 6),
                            "difference_ratio": round(difference_ratio, 6),
                            "review_threshold": rate_tolerance,
                            "source_tags": [
                                f"ffprobe.streams[{index}].avg_frame_rate",
                                f"ffprobe.streams[{index}].r_frame_rate",
                            ],
                        },
                        method="ffprobe-average-vs-nominal-rate",
                        limitations=[
                            "Frame-rate fields alone do not conclusively establish variable frame timing.",
                            "Variable frame rate is common in phones, screen recordings, and social-media exports.",
                        ],
                    )
                )
    explicit_vbr: List[Dict[str, Any]] = []
    for source_tag, value in _walk_items(raw):
        if _leaf_key(source_tag) not in {"bitratemode", "ratecontrolmode"}:
            continue
        text = str(value).strip()[:128]
        if text.casefold() in {"vbr", "variable", "variable bitrate"}:
            explicit_vbr.append({"value": text, "source_tag": source_tag})
    if explicit_vbr:
        findings.append(
            _finding(
                code="compression.variable_bitrate_metadata",
                title="Variable-bitrate encoding is explicitly reported",
                severity=FindingSeverity.INFO,
                explanation="Embedded metadata explicitly describes a variable-bitrate encoding mode.",
                evidence={"observations": explicit_vbr[:16]},
                method="explicit-rate-mode-tag",
                limitations=[
                    "Variable bitrate is a normal efficiency feature and does not indicate manipulation.",
                    "The finding relies on self-reported metadata rather than packet-level measurement.",
                ],
            )
        )
    return findings


def _container_codec_indicators(
    detected_mime_type: str,
    streams: Sequence[Dict[str, Any]],
) -> List[ForensicFinding]:
    incompatible: List[Dict[str, Any]] = []
    for index, stream in enumerate(streams):
        codec_type = str(stream.get("codec_type") or "").lower()
        codec = str(stream.get("codec_name") or "").lower()
        if not codec:
            continue
        mismatch = False
        if detected_mime_type == "video/webm" and codec_type == "video":
            mismatch = codec not in {"vp8", "vp9", "av1"}
        elif detected_mime_type == "video/webm" and codec_type == "audio":
            mismatch = codec not in {"vorbis", "opus"}
        elif detected_mime_type == "audio/mpeg" and codec_type == "audio":
            mismatch = codec not in {"mp1", "mp2", "mp3"}
        if mismatch:
            incompatible.append(
                {"stream_index": index, "stream_type": codec_type, "codec": codec}
            )
    if not incompatible:
        return []
    return [
        _finding(
            code="compression.container_codec_mismatch",
            title="Codec is unusual for the detected container",
            severity=FindingSeverity.MEDIUM,
            explanation="A stream codec is incompatible with the narrow codec set defined for the detected container type.",
            evidence={
                "detected_mime_type": detected_mime_type,
                "observations": incompatible,
            },
            method="conservative-container-codec-compatibility-table",
            limitations=[
                "Non-standard files and parser labeling differences can produce this result.",
                "A container mismatch does not establish malicious editing or fake content.",
            ],
        )
    ]


def _stream_indicators(
    detected_mime_type: str,
    raw: Dict[str, Any],
) -> List[ForensicFinding]:
    streams = _ffprobe_streams(raw)
    if streams is None:
        return []
    expected_type = "video" if detected_mime_type.startswith("video/") else "audio"
    if any(stream.get("codec_type") == expected_type for stream in streams):
        return _container_codec_indicators(detected_mime_type, streams)
    return [
        _finding(
            code="compression.expected_stream_missing",
            title=f"Expected {expected_type} stream is missing",
            severity=FindingSeverity.MEDIUM,
            explanation=f"ffprobe returned a container without an expected {expected_type} stream.",
            evidence={
                "expected_stream_type": expected_type,
                "reported_stream_types": [
                    str(stream.get("codec_type"))[:32]
                    for stream in streams[:16]
                    if stream.get("codec_type") is not None
                ],
            },
            method="ffprobe-stream-inventory",
            limitations=[
                "A damaged, incomplete, unusual, or partially parsed container can lack an expected stream.",
                "This finding does not prove editing or fakery.",
            ],
        )
    ]


def _media_characteristics(
    detected_mime_type: str,
    metadata: MetadataEvidence,
    creation_info: CreationInfo,
) -> List[ForensicFinding]:
    normalized = metadata.normalized
    media_type = "video" if detected_mime_type.startswith("video/") else "audio"
    facts = normalized.get(media_type)
    file_facts = normalized.get("file")
    if not isinstance(facts, dict):
        return []
    file_values = file_facts if isinstance(file_facts, dict) else {}
    wanted = (
        ("codec", "container", "bit_rate", "duration_seconds", "stream_count", "frame_rate", "width", "height")
        if media_type == "video"
        else ("codec", "container", "bit_rate", "duration_seconds", "stream_count", "sample_rate", "channels")
    )
    measured: Dict[str, Any] = {
        "detected_mime_type": detected_mime_type,
        "container": file_values.get("format"),
        **{key: facts.get(key) for key in wanted if key != "container"},
        "software_or_encoder": creation_info.software,
    }
    measured = {key: value for key, value in measured.items() if value not in (None, [])}
    return [
        _finding(
            code=f"compression.{media_type}_characteristics",
            title=f"{media_type.title()} encoding characteristics",
            severity=FindingSeverity.INFO,
            explanation=f"These are normalized {media_type} container, stream, and encoding facts reported by local metadata parsers.",
            evidence=measured,
            method="sanitized-normalized-ffprobe-facts",
            limitations=[
                "These values describe the current encoding and do not reconstruct the media's full history.",
                "Transcoding and social-media recompression are common benign explanations for changed encoding facts.",
            ],
        )
    ]


def extract_compression_evidence(
    file_path: PathLike,
    *,
    detected_mime_type: str,
    metadata: MetadataEvidence,
    creation_info: CreationInfo,
    allowed_root: Optional[PathLike] = None,
) -> CompressionExtractionResult:
    """Collect bounded compression observations with independent error status."""
    started_at = perf_counter()

    def elapsed_ms() -> int:
        return max(0, round((perf_counter() - started_at) * 1000))

    supported = (
        detected_mime_type in _SUPPORTED_IMAGE_MIME_TYPES
        or detected_mime_type in _SUPPORTED_VIDEO_MIME_TYPES
        or detected_mime_type in _SUPPORTED_AUDIO_MIME_TYPES
    )
    if not supported:
        return CompressionExtractionResult(
            status="unsupported",
            warnings=["Compression analysis does not support this media type."],
            processing_time_ms=elapsed_ms(),
        )

    try:
        path = resolve_workspace_file(file_path, allowed_root)
        if detected_mime_type in _SUPPORTED_IMAGE_MIME_TYPES:
            indicators = _image_indicators(path, detected_mime_type, creation_info)
        else:
            if metadata.status != ExtractorStatus.AVAILABLE:
                return CompressionExtractionResult(
                    status="unavailable",
                    warnings=[
                        "Compression observations require available normalized media metadata."
                    ],
                    processing_time_ms=elapsed_ms(),
                )
            indicators = _media_characteristics(
                detected_mime_type, metadata, creation_info
            )
            if not indicators:
                return CompressionExtractionResult(
                    status="unavailable",
                    warnings=["Normalized stream facts were unavailable."],
                    processing_time_ms=elapsed_ms(),
                )
            raw = metadata.raw
            media_type = "video" if detected_mime_type.startswith("video/") else "audio"
            indicators.extend(_stream_indicators(detected_mime_type, raw))
            indicators.extend(_duration_indicator(raw))
            indicators.extend(_rate_indicators(raw, media_type))
            indicators.extend(_software_indicators(creation_info))
        return CompressionExtractionResult(
            status="available",
            indicators=deduplicate_findings(indicators),
            processing_time_ms=elapsed_ms(),
        )
    except ValueError as exc:
        return CompressionExtractionResult(
            status="error",
            warnings=[str(exc)[:512] or "Compression analysis failed."],
            processing_time_ms=elapsed_ms(),
        )
    except (Image.DecompressionBombError, Image.DecompressionBombWarning, UnidentifiedImageError, OSError):
        return CompressionExtractionResult(
            status="error",
            warnings=["Image decoding failed during compression analysis."],
            processing_time_ms=elapsed_ms(),
        )
    except Exception:
        return CompressionExtractionResult(
            status="error",
            warnings=["Compression analysis failed unexpectedly."],
            processing_time_ms=elapsed_ms(),
        )

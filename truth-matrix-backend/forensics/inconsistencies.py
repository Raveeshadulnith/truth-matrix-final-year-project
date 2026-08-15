from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field

from schemas.forensic_schema import (
    CreationInfo,
    ExtractorStatus,
    FindingSeverity,
    ForensicFinding,
    SoftwareCategory,
    SoftwareObservation,
)


METHOD = "embedded-metadata-consistency"
METHOD_VERSION = "1"

DEFAULT_TIMESTAMP_ORDER_TOLERANCE_SECONDS = 2.0
DEFAULT_TIMESTAMP_CONFLICT_TOLERANCE_SECONDS = 300.0
DEFAULT_DURATION_TOLERANCE_SECONDS = 0.5
DEFAULT_DURATION_TOLERANCE_RATIO = 0.02

_FILESYSTEM_DATE_TAGS = {
    "fileaccessdate",
    "filecreatedate",
    "fileinodechangedate",
    "filemodifydate",
}
_CREATED_TAGS = (
    "datetimeoriginal",
    "createdate",
    "creationtime",
    "mediacreatedate",
    "trackcreatedate",
    "datecreated",
    "contentcreatedate",
)
_MODIFIED_TAGS = (
    "datetime",
    "modifydate",
    "metadatadate",
    "modificationtime",
    "mediamodifydate",
    "trackmodifydate",
)
_DIGITIZED_TAGS = ("datetimedigitized", "digitizeddate")
_OFFSET_TAGS = ("offsettimeoriginal", "offsettimedigitized", "offsettime", "timezone")
_SUBSECOND_TAGS = (
    "subsectimeoriginal",
    "subsectimedigitized",
    "subsectime",
)
_SOFTWARE_TAGS = (
    "software",
    "creatortool",
    "historysoftwareagent",
    "encoder",
    "encodedby",
    "writingapplication",
    "writinglibrary",
    "handlername",
    "application",
    "producer",
    "generator",
)
_DEVICE_MAKE_TAGS = ("make", "cameramake", "devicemanufacturer")
_DEVICE_MODEL_TAGS = ("model", "cameramodelname", "devicemodelname", "cameramodel")
_CREATOR_TAGS = ("creator", "artist", "author", "byline", "copyrightowner")
_AI_GENERATION_SOFTWARE_MARKERS = (
    "stable diffusion",
    "midjourney",
    "dall-e",
    "dall·e",
    "adobe firefly",
    "generative ai",
    "ai generator",
)
_CAPTURE_PROCESSING_SOFTWARE_MARKERS = (
    "hdr+",
    "google camera",
    "pixel camera",
    "night sight",
    "apple camera",
    "iphone camera",
    "samsung camera",
    "camera firmware",
    "computational photography",
)
_EDITOR_SOFTWARE_MARKERS = (
    "adobe photoshop",
    "photoshop",
    "lightroom",
    "gimp",
    "premiere",
    "after effects",
    "davinci resolve",
    "final cut",
    "capcut",
    "canva",
)
_ENCODER_SOFTWARE_MARKERS = (
    "ffmpeg",
    "lavf",
    "lavc",
    "libx264",
    "x264",
    "libx265",
    "x265",
    "handbrake",
)
_SOCIAL_PLATFORM_MARKERS = (
    "instagram",
    "facebook",
    "whatsapp",
    "tiktok",
    "youtube",
    "snapchat",
)
_METADATA_TOOL_MARKERS = ("exiftool", "metadata editor")
_SOFTWARE_DESCRIPTIONS = {
    SoftwareCategory.CAPTURE_PROCESSING: (
        "Software used by a camera or phone while capturing and processing media. "
        "Its presence is not evidence of manual editing."
    ),
    SoftwareCategory.EDITOR: (
        "Software commonly used for editing or post-processing. Ordinary edits and exports are common benign explanations."
    ),
    SoftwareCategory.ENCODER: (
        "Software used to encode, transcode, or export media. Encoding does not by itself imply deceptive editing."
    ),
    SoftwareCategory.AI_GENERATION: (
        "The metadata explicitly names software associated with generative media. The tag can still be stale or copied."
    ),
    SoftwareCategory.SOCIAL_PLATFORM: (
        "A social or sharing platform appears in the media workflow and may have recompressed or rewritten metadata."
    ),
    SoftwareCategory.METADATA_TOOL: (
        "A metadata-management tool appears in the workflow. This does not establish that the media content changed."
    ),
    SoftwareCategory.UNKNOWN: (
        "The software name is preserved, but its role cannot be classified safely from the embedded value alone."
    ),
}
_EXTENSION_MIME_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "jpe": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "mp4": "video/mp4",
    "mov": "video/quicktime",
    "avi": "video/x-msvideo",
    "mkv": "video/x-matroska",
    "webm": "video/webm",
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "m4a": "audio/mp4",
}
_FORMAT_MIME_TYPES = {
    "jpeg": {"image/jpeg"},
    "jpg": {"image/jpeg"},
    "png": {"image/png"},
    "webp": {"image/webp"},
    "wav": {"audio/wav"},
    "wave": {"audio/wav"},
    "mp3": {"audio/mpeg"},
    "avi": {"video/x-msvideo"},
    "matroska": {"video/x-matroska"},
    "webm": {"video/webm", "audio/webm"},
    "mov": {"video/quicktime", "video/mp4", "audio/mp4"},
    "mp4": {"video/mp4", "audio/mp4"},
    "m4a": {"audio/mp4"},
    "quicktime": {"video/quicktime"},
}
_MIME_ALIASES = {
    "image/jpg": "image/jpeg",
    "image/pjpeg": "image/jpeg",
    "audio/x-wav": "audio/wav",
    "audio/wave": "audio/wav",
    "audio/vnd.wave": "audio/wav",
    "audio/mp3": "audio/mpeg",
    "audio/x-mp3": "audio/mpeg",
    "audio/x-m4a": "audio/mp4",
    "video/avi": "video/x-msvideo",
    "video/msvideo": "video/x-msvideo",
    "video/x-ms-video": "video/x-msvideo",
}
_GENERIC_MIME_TYPES = {"", "application/octet-stream", "binary/octet-stream"}


class MetadataConsistencyResult(BaseModel):
    """Result of creation normalization and embedded-metadata checks."""

    model_config = ConfigDict(extra="forbid")

    status: ExtractorStatus
    creation_info: CreationInfo = Field(default_factory=CreationInfo)
    findings: List[ForensicFinding] = Field(default_factory=list)


@dataclass(frozen=True)
class TimestampObservation:
    """One parsed or rejected embedded timestamp and its provenance."""

    category: str
    source_tag: str
    raw_value: str
    source_group: str
    parsed: Optional[datetime]
    offset_source_tag: Optional[str] = None
    subsecond_source_tag: Optional[str] = None

    @property
    def timezone_aware(self) -> bool:
        """Return whether the parsed timestamp contains a UTC offset."""
        return self.parsed is not None and self.parsed.utcoffset() is not None


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


def _source_group(source_tag: str) -> str:
    root = source_tag.split(".", 1)[0].split("[", 1)[0]
    if root == "ffprobe":
        if source_tag.startswith("ffprobe.format"):
            return "ffprobe:format"
        stream_match = re.match(r"ffprobe\.streams\[(\d+)\]", source_tag)
        if stream_match:
            return f"ffprobe:stream[{stream_match.group(1)}]"
    leaf_segment = source_tag.rsplit(".", 1)[-1]
    metadata_group = leaf_segment.split(":", 1)[0] if ":" in leaf_segment else ""
    return f"{root}:{metadata_group}" if metadata_group else root


def _timestamp_family(source_tag: str) -> Tuple[str, str]:
    """Group timestamp companion tags without conflating EXIF and XMP."""
    if "." in source_tag:
        extractor, leaf_segment = source_tag.split(".", 1)
        leaf_segment = leaf_segment.rsplit(".", 1)[-1]
    else:
        extractor, leaf_segment = "direct", source_tag
    metadata_group = leaf_segment.split(":", 1)[0].casefold()
    if metadata_group in {"ifd0", "exif", "exififd"}:
        family = "exif"
    elif metadata_group in {"xmp", "xmp-exif", "photoshop"}:
        family = "xmp"
    else:
        family = _source_group(source_tag)
    return extractor, family


def _bounded_text(value: Any, maximum: int = 1024) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text[:maximum] if text else None


def _matches(sources: Any, names: Sequence[str]) -> List[Tuple[str, Any]]:
    wanted = set(names)
    return [
        (source_tag, value)
        for source_tag, value in _walk_items(sources)
        if _leaf_key(source_tag) in wanted
    ]


def _unique_values(
    matches: Iterable[Tuple[str, Any]], maximum: int = 16
) -> List[Tuple[str, str]]:
    output: List[Tuple[str, str]] = []
    seen: set[str] = set()
    for source_tag, value in matches:
        text = _bounded_text(value)
        if text is None:
            continue
        normalized = " ".join(text.casefold().split())
        if normalized not in seen:
            seen.add(normalized)
            output.append((source_tag[:256], text))
        if len(output) >= maximum:
            break
    return output


def classify_software_name(name: str) -> SoftwareCategory:
    """Classify an explicit software name without inferring AI from generic tags."""
    normalized = " ".join(name.casefold().split())

    def contains_marker(marker: str) -> bool:
        left_boundary = r"(?<!\w)" if marker[0].isalnum() else ""
        right_boundary = r"(?!\w)" if marker[-1].isalnum() else ""
        return re.search(
            f"{left_boundary}{re.escape(marker)}{right_boundary}",
            normalized,
        ) is not None

    marker_groups = (
        (SoftwareCategory.AI_GENERATION, _AI_GENERATION_SOFTWARE_MARKERS),
        (SoftwareCategory.CAPTURE_PROCESSING, _CAPTURE_PROCESSING_SOFTWARE_MARKERS),
        (SoftwareCategory.EDITOR, _EDITOR_SOFTWARE_MARKERS),
        (SoftwareCategory.ENCODER, _ENCODER_SOFTWARE_MARKERS),
        (SoftwareCategory.SOCIAL_PLATFORM, _SOCIAL_PLATFORM_MARKERS),
        (SoftwareCategory.METADATA_TOOL, _METADATA_TOOL_MARKERS),
    )
    for category, markers in marker_groups:
        if any(contains_marker(marker) for marker in markers):
            return category
    return SoftwareCategory.UNKNOWN


def _software_observations(sources: Any) -> List[SoftwareObservation]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for source_tag, value in _matches(sources, _SOFTWARE_TAGS):
        name = _bounded_text(value)
        if not name:
            continue
        key = " ".join(name.casefold().split())
        if key not in grouped and len(grouped) >= 16:
            continue
        item = grouped.setdefault(
            key,
            {"name": name, "source_tags": []},
        )
        safe_tag = source_tag[:256]
        if safe_tag not in item["source_tags"] and len(item["source_tags"]) < 16:
            item["source_tags"].append(safe_tag)

    observations: List[SoftwareObservation] = []
    for item in grouped.values():
        category = classify_software_name(item["name"])
        observations.append(
            SoftwareObservation(
                name=item["name"],
                category=category,
                source_tags=item["source_tags"],
                user_description=_SOFTWARE_DESCRIPTIONS[category],
            )
        )
    return observations


def _normalize_offset(value: Any) -> Optional[str]:
    text = _bounded_text(value, 32)
    if not text:
        return None
    if text.upper() == "Z":
        return "+00:00"
    matched = re.fullmatch(r"([+-])(\d{2}):?(\d{2})", text)
    if not matched:
        return None
    hours, minutes = int(matched.group(2)), int(matched.group(3))
    if hours > 14 or minutes > 59 or (hours == 14 and minutes != 0):
        return None
    return f"{matched.group(1)}{hours:02d}:{minutes:02d}"


def _normalize_subsecond(value: Any) -> Optional[str]:
    text = _bounded_text(value, 32)
    if not text:
        return None
    digits = text.strip().lstrip(".")
    if not digits.isdigit():
        return None
    return digits[:6]


def parse_embedded_timestamp(
    value: Any,
    offset: Optional[str] = None,
    subsecond: Optional[str] = None,
) -> Optional[datetime]:
    """Parse an unambiguous embedded timestamp, preserving naive/aware state."""
    text = _bounded_text(value, 128)
    if not text or re.search(r"(?:^|\D)0{4}[:/-]0{2}[:/-]0{2}(?:\D|$)", text):
        return None
    normalized = text
    if re.match(r"^\d{4}:\d{2}:\d{2}(?: |T)", normalized):
        normalized = normalized[:4] + "-" + normalized[5:7] + "-" + normalized[8:]
    if normalized.endswith(("Z", "z")):
        normalized = normalized[:-1] + "+00:00"
    if re.search(r"[+-]\d{4}$", normalized):
        normalized = normalized[:-5] + normalized[-5:-2] + ":" + normalized[-2:]
    fractional = _normalize_subsecond(subsecond)
    if fractional and not re.search(r"\d{2}:\d{2}:\d{2}\.\d+", normalized):
        normalized = re.sub(
            r"(\d{2}:\d{2}:\d{2})(?=(?:Z|[+-]\d{2}:?\d{2})?$)",
            rf"\1.{fractional}",
            normalized,
        )
    if offset and not re.search(r"(?:Z|[+-]\d{2}:?\d{2})$", normalized, re.IGNORECASE):
        normalized = f"{normalized}{offset}"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.year < 1601 or parsed.year > 9999:
        return None
    return parsed


def _offset_for(
    source_tag: str,
    category: str,
    offset_matches: Sequence[Tuple[str, Any]],
) -> Tuple[Optional[str], Optional[str]]:
    preferred = {
        "created": ("offsettimeoriginal", "offsettime", "timezone"),
        "digitized": ("offsettimedigitized", "offsettime", "timezone"),
        "modified": ("offsettime", "timezone"),
    }[category]
    family = _timestamp_family(source_tag)
    for wanted in preferred:
        for offset_tag, value in offset_matches:
            if _leaf_key(offset_tag) == wanted and _timestamp_family(offset_tag) == family:
                normalized = _normalize_offset(value)
                if normalized:
                    return normalized, offset_tag[:256]
    return None, None


def _subsecond_for(
    source_tag: str,
    category: str,
    subsecond_matches: Sequence[Tuple[str, Any]],
) -> Tuple[Optional[str], Optional[str]]:
    preferred = {
        "created": ("subsectimeoriginal", "subsectime"),
        "digitized": ("subsectimedigitized", "subsectime"),
        "modified": ("subsectime",),
    }[category]
    family = _timestamp_family(source_tag)
    for wanted in preferred:
        for subsecond_tag, value in subsecond_matches:
            if (
                _leaf_key(subsecond_tag) == wanted
                and _timestamp_family(subsecond_tag) == family
            ):
                normalized = _normalize_subsecond(value)
                if normalized:
                    return normalized, subsecond_tag[:256]
    return None, None


def _timestamp_observations(sources: Any) -> List[TimestampObservation]:
    category_names = {
        "created": _CREATED_TAGS,
        "modified": _MODIFIED_TAGS,
        "digitized": _DIGITIZED_TAGS,
    }
    offset_matches = _matches(sources, _OFFSET_TAGS)
    subsecond_matches = _matches(sources, _SUBSECOND_TAGS)
    observations: List[TimestampObservation] = []
    for category, names in category_names.items():
        for source_tag, value in _matches(sources, names):
            if _leaf_key(source_tag) in _FILESYSTEM_DATE_TAGS:
                continue
            raw = _bounded_text(value, 128) or ""
            offset, offset_source = _offset_for(
                source_tag, category, offset_matches
            )
            subsecond, subsecond_source = _subsecond_for(
                source_tag, category, subsecond_matches
            )
            observations.append(
                TimestampObservation(
                    category=category,
                    source_tag=source_tag[:256],
                    raw_value=raw,
                    source_group=_source_group(source_tag),
                    parsed=parse_embedded_timestamp(raw, offset, subsecond),
                    offset_source_tag=offset_source,
                    subsecond_source_tag=subsecond_source,
                )
            )
    return observations


def _timestamp_priority(observation: TimestampObservation) -> Tuple[int, str]:
    priorities = {
        name: index
        for index, name in enumerate(
            (*_CREATED_TAGS, *_MODIFIED_TAGS, *_DIGITIZED_TAGS)
        )
    }
    return priorities.get(_leaf_key(observation.source_tag), 999), observation.source_tag


def normalize_creation_info(
    sources: Any,
    *,
    location_present: bool = False,
    location_source_tags: Sequence[str] = (),
) -> CreationInfo:
    """Map vendor-specific tags into privacy-safe creation information."""
    source_tags: Dict[str, List[str]] = {}

    software_observations = _software_observations(sources)
    software = [observation.name for observation in software_observations]
    if software_observations:
        source_tags["software"] = list(
            dict.fromkeys(
                tag
                for observation in software_observations
                for tag in observation.source_tags
            )
        )[:16]

    def choose(field: str, names: Sequence[str]) -> Optional[str]:
        values = _unique_values(_matches(sources, names))
        if not values:
            return None
        source_tags[field] = [values[0][0]]
        return values[0][1]

    device_make = choose("device_make", _DEVICE_MAKE_TAGS)
    device_model = choose("device_model", _DEVICE_MODEL_TAGS)
    creator = choose("creator", _CREATOR_TAGS)

    timestamps = _timestamp_observations(sources)
    selected: Dict[str, Optional[str]] = {
        "created_at": None,
        "modified_at": None,
        "digitized_at": None,
    }
    timezone_sources: List[str] = []
    for category, field in (
        ("created", "created_at"),
        ("modified", "modified_at"),
        ("digitized", "digitized_at"),
    ):
        candidates = sorted(
            (item for item in timestamps if item.category == category and item.parsed),
            key=_timestamp_priority,
        )
        if not candidates:
            continue
        chosen = candidates[0]
        assert chosen.parsed is not None
        selected[field] = chosen.parsed.isoformat()
        tags = [chosen.source_tag]
        if chosen.offset_source_tag:
            tags.append(chosen.offset_source_tag)
        if chosen.subsecond_source_tag:
            tags.append(chosen.subsecond_source_tag)
        source_tags[field] = list(dict.fromkeys(tags))
        if chosen.timezone_aware:
            timezone_sources.extend(tags)

    for timezone_tag, value in _matches(sources, _OFFSET_TAGS):
        text = (_bounded_text(value, 32) or "").upper()
        if _normalize_offset(value) or text in {"UTC", "GMT"}:
            timezone_sources.append(timezone_tag[:256])

    if timezone_sources:
        source_tags["timezone_present"] = list(dict.fromkeys(timezone_sources))[:16]
    if location_present:
        safe_location_tags = sorted({str(tag)[:256] for tag in location_source_tags})[:16]
        if safe_location_tags:
            source_tags["location_present"] = safe_location_tags

    return CreationInfo(
        software=software,
        software_observations=software_observations,
        device_make=device_make,
        device_model=device_model,
        creator=creator,
        created_at=selected["created_at"],
        modified_at=selected["modified_at"],
        digitized_at=selected["digitized_at"],
        timezone_present=bool(timezone_sources),
        location_present=location_present,
        source_tags=source_tags,
    )


def _finding(
    code: str,
    title: str,
    explanation: str,
    evidence: Dict[str, Any],
    severity: FindingSeverity,
    limitations: Sequence[str],
) -> ForensicFinding:
    return ForensicFinding(
        code=code,
        title=title,
        explanation=explanation,
        evidence=evidence,
        severity=severity,
        method=METHOD,
        method_version=METHOD_VERSION,
        limitations=list(limitations),
    )


def _timestamp_findings(
    observations: Sequence[TimestampObservation],
    order_tolerance: float,
    conflict_tolerance: float,
) -> List[ForensicFinding]:
    findings: List[ForensicFinding] = []
    for observation in observations:
        if observation.parsed is None:
            findings.append(
                _finding(
                    "metadata.timestamp_unparseable",
                    "Embedded timestamp could not be parsed",
                    "An embedded date is impossible or uses an ambiguous or unsupported format.",
                    {
                        "observed_value": observation.raw_value,
                        "source_tags": [observation.source_tag],
                        "timestamp_role": observation.category,
                    },
                    FindingSeverity.LOW,
                    [
                        "Malformed metadata may result from an exporter or damaged file and is not proof of manipulation.",
                        "Filesystem timestamps are intentionally excluded from this check.",
                    ],
                )
            )

    valid_created = [item for item in observations if item.category == "created" and item.parsed]
    valid_modified = [item for item in observations if item.category == "modified" and item.parsed]
    conflicts: List[Tuple[float, TimestampObservation, TimestampObservation]] = []
    for created in valid_created:
        for modified in valid_modified:
            if created.timezone_aware != modified.timezone_aware:
                continue
            assert created.parsed is not None and modified.parsed is not None
            difference = (created.parsed - modified.parsed).total_seconds()
            if difference > order_tolerance:
                conflicts.append((difference, created, modified))
    if conflicts:
        difference, created, modified = max(conflicts, key=lambda item: (item[0], item[1].source_tag, item[2].source_tag))
        findings.append(
            _finding(
                "metadata.timestamp_order_conflict",
                "Embedded modification time precedes creation time",
                "Comparable embedded timestamps place modification before creation beyond the configured tolerance.",
                {
                    "creation": {"value": created.parsed.isoformat(), "source_tag": created.source_tag},
                    "modification": {"value": modified.parsed.isoformat(), "source_tag": modified.source_tag},
                    "difference_seconds": round(difference, 6),
                    "tolerance_seconds": order_tolerance,
                },
                FindingSeverity.MEDIUM,
                [
                    "Clock errors, timezone loss, and exporter behavior can reorder embedded dates.",
                    "Naive timestamps are compared only with other naive timestamps; aware timestamps only with aware timestamps.",
                ],
            )
        )

    for category in ("created", "modified", "digitized"):
        candidates = [item for item in observations if item.category == category and item.parsed]
        for aware in (False, True):
            comparable = [item for item in candidates if item.timezone_aware == aware]
            if len({item.source_group for item in comparable}) < 2:
                continue
            valued: List[Tuple[datetime, TimestampObservation]] = []
            for item in comparable:
                assert item.parsed is not None
                comparison_value = (
                    item.parsed.astimezone(timezone.utc).replace(tzinfo=None)
                    if aware
                    else item.parsed
                )
                valued.append((comparison_value, item))
            earliest_value, earliest = min(valued, key=lambda item: (item[0], item[1].source_tag))
            latest_value, latest = max(valued, key=lambda item: (item[0], item[1].source_tag))
            difference = (latest_value - earliest_value).total_seconds()
            if difference <= conflict_tolerance:
                continue
            findings.append(
                _finding(
                    "metadata.timestamp_group_conflict",
                    "Embedded metadata groups report conflicting times",
                    "Different embedded metadata groups report materially different times for the same timestamp role.",
                    {
                        "timestamp_role": category,
                        "earliest": {"value": earliest.parsed.isoformat(), "source_tag": earliest.source_tag},
                        "latest": {"value": latest.parsed.isoformat(), "source_tag": latest.source_tag},
                        "difference_seconds": round(difference, 6),
                        "tolerance_seconds": conflict_tolerance,
                        "timezone_aware": aware,
                    },
                    FindingSeverity.LOW,
                    [
                        "Metadata groups can describe different workflow stages even when their tag names appear equivalent.",
                        "Timezone-aware and naive timestamps are never compared with each other.",
                    ],
                )
            )
    return findings


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = _bounded_text(value, 128)
        if not text:
            return None
        matched = re.match(r"^\s*(-?\d+(?:\.\d+)?)", text)
        if not matched:
            return None
        number = float(matched.group(1))
    return number if math.isfinite(number) else None


def _gps_findings(gps_observations: Sequence[Tuple[str, Any]]) -> List[ForensicFinding]:
    invalid: List[Dict[str, Any]] = []
    for source_tag, value in gps_observations[:32]:
        leaf = _leaf_key(source_tag)
        components: List[Tuple[str, Any]] = []
        if leaf in {"gpslatitude", "latitude"}:
            components = [("latitude", value)]
        elif leaf in {"gpslongitude", "longitude"}:
            components = [("longitude", value)]
        elif leaf in {"gpsposition", "coordinates"}:
            if isinstance(value, (list, tuple)) and len(value) >= 2:
                components = [("latitude", value[0]), ("longitude", value[1])]
            elif isinstance(value, str):
                parts = re.findall(r"-?\d+(?:\.\d+)?", value)
                if len(parts) >= 2:
                    components = [("latitude", parts[0]), ("longitude", parts[1])]
        for coordinate_kind, coordinate_value in components:
            number = _number(coordinate_value)
            legal_min, legal_max = (-90.0, 90.0) if coordinate_kind == "latitude" else (-180.0, 180.0)
            if number is None or legal_min <= number <= legal_max:
                continue
            invalid.append(
                {
                    "coordinate_kind": coordinate_kind,
                    "observed_category": "below_minimum" if number < legal_min else "above_maximum",
                    "legal_range": [legal_min, legal_max],
                    "source_tag": str(source_tag)[:256],
                }
            )
    if not invalid:
        return []
    return [
        _finding(
            "metadata.gps_out_of_range",
            "Embedded GPS coordinate is outside its legal range",
            "A coordinate was validated before privacy redaction and falls outside the legal latitude or longitude range.",
            {"observations": invalid},
            FindingSeverity.MEDIUM,
            [
                "Exact coordinates are intentionally omitted from this finding.",
                "Malformed GPS metadata can result from parser or exporter errors and is not proof of manipulation.",
            ],
        )
    ]


def _parent_tag(source_tag: str) -> str:
    return source_tag.rsplit(".", 1)[0] if "." in source_tag else _source_group(source_tag)


def _orientation(value: Any) -> Optional[int]:
    number = _number(value)
    if number is not None and int(number) in range(1, 9):
        return int(number)
    text = (_bounded_text(value, 128) or "").casefold()
    if "90" in text or "270" in text:
        return 6
    if text in {"horizontal", "normal", "top-left"}:
        return 1
    return None


def _dimension_findings(sources: Any) -> List[ForensicFinding]:
    facts: Dict[str, Dict[str, Tuple[str, Any]]] = {}
    orientations: List[Tuple[str, int]] = []
    for source_tag, value in _walk_items(sources):
        leaf = _leaf_key(source_tag)
        parent = _parent_tag(source_tag)
        if leaf in {"imagewidth", "exifimagewidth", "width"}:
            facts.setdefault(parent, {})["width"] = (source_tag, value)
        elif leaf in {"imageheight", "exifimageheight", "height"}:
            facts.setdefault(parent, {})["height"] = (source_tag, value)
        elif leaf == "orientation":
            normalized = _orientation(value)
            if normalized is not None:
                orientations.append((source_tag, normalized))

    dimensions: List[Dict[str, Any]] = []
    for group, values in sorted(facts.items()):
        if "width" not in values or "height" not in values:
            continue
        width = _number(values["width"][1])
        height = _number(values["height"][1])
        if width is None or height is None or width <= 0 or height <= 0:
            continue
        dimensions.append(
            {
                "group": group,
                "width": int(width) if width.is_integer() else width,
                "height": int(height) if height.is_integer() else height,
                "source_tags": [values["width"][0], values["height"][0]],
            }
        )

    findings: List[ForensicFinding] = []
    pairs = {(item["width"], item["height"]) for item in dimensions}
    rotated = any(value in {5, 6, 7, 8} for _, value in orientations)
    compatible_by_rotation = (
        len(pairs) == 2
        and rotated
        and any((height, width) in pairs for width, height in pairs)
    )
    if len(pairs) > 1 and not compatible_by_rotation:
        findings.append(
            _finding(
                "metadata.dimension_conflict",
                "Parsers report incompatible media dimensions",
                "Independent metadata locations report width and height values that cannot be reconciled by embedded rotation.",
                {"observations": dimensions[:16], "rotation_considered": rotated},
                FindingSeverity.MEDIUM,
                [
                    "Some containers store coded and displayed dimensions separately.",
                    "This discrepancy is a review signal, not proof of manipulation.",
                ],
            )
        )

    distinct_orientations = sorted({value for _, value in orientations})
    if len(distinct_orientations) > 1:
        findings.append(
            _finding(
                "metadata.orientation_conflict",
                "Parsers report conflicting orientations",
                "Embedded orientation values disagree across metadata locations.",
                {
                    "observations": [
                        {"orientation": value, "source_tag": source_tag}
                        for source_tag, value in orientations[:16]
                    ]
                },
                FindingSeverity.LOW,
                [
                    "Orientation can be rewritten or normalized by ordinary software.",
                    "The finding does not establish that image content was manipulated.",
                ],
            )
        )
    return findings


def _normalized_mime(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value[:255].split(";", 1)[0].strip().lower()
    return _MIME_ALIASES.get(cleaned, cleaned) or None


def _type_findings(
    sources: Any,
    detected_mime_type: str,
    original_filename: Optional[str],
    declared_mime_type: Optional[str],
) -> List[ForensicFinding]:
    findings: List[ForensicFinding] = []
    detected = _normalized_mime(detected_mime_type) or detected_mime_type
    extension = Path(original_filename or "").suffix.lower().lstrip(".")
    expected = _EXTENSION_MIME_TYPES.get(extension)
    if expected and expected != detected:
        findings.append(
            _finding(
                "file_type.extension_mismatch",
                "Filename extension differs from detected media type",
                "The filename extension and byte-detected media type do not agree.",
                {"detected_mime_type": detected, "extension_mime_type": expected},
                FindingSeverity.LOW,
                ["Renaming a valid file can cause this warning; it is not evidence that the content is fake."],
            )
        )
    declared = _normalized_mime(declared_mime_type)
    if declared and declared not in _GENERIC_MIME_TYPES and declared != detected:
        findings.append(
            _finding(
                "file_type.declared_mime_mismatch",
                "Declared media type differs from detected media type",
                "The client-declared MIME type and byte-detected media type do not agree.",
                {"detected_mime_type": detected, "declared_mime_type": declared},
                FindingSeverity.LOW,
                ["Client MIME declarations are often missing or inaccurate; this is not evidence that the content is fake."],
            )
        )

    format_matches = _matches(sources, ("filetype", "formatname", "format"))
    incompatible: List[Dict[str, Any]] = []
    for source_tag, value in format_matches:
        text = (_bounded_text(value, 256) or "").lower()
        tokens = [token.strip() for token in re.split(r"[,/]", text) if token.strip()]
        compatible: set[str] = set()
        for token in tokens:
            compatible.update(_FORMAT_MIME_TYPES.get(token, set()))
        if compatible and detected not in compatible:
            incompatible.append(
                {
                    "container_format": text,
                    "compatible_mime_types": sorted(compatible),
                    "source_tag": source_tag,
                }
            )
    if incompatible:
        findings.append(
            _finding(
                "file_type.container_mismatch",
                "Container metadata conflicts with detected media type",
                "A recognized embedded container or format name is incompatible with the byte-detected media type.",
                {"detected_mime_type": detected, "observations": incompatible[:16]},
                FindingSeverity.MEDIUM,
                [
                    "Only recognized, incompatible format names trigger this finding.",
                    "Parser errors or malformed containers can produce conflicting descriptions.",
                ],
            )
        )
    return findings


def _device_findings(sources: Any, creation_info: CreationInfo) -> List[ForensicFinding]:
    findings: List[ForensicFinding] = []
    for label, names in (("make", _DEVICE_MAKE_TAGS), ("model", _DEVICE_MODEL_TAGS)):
        values = _unique_values(_matches(sources, names))
        if len(values) <= 1:
            continue
        findings.append(
            _finding(
                "metadata.device_conflict",
                "Embedded capture-device values conflict",
                f"Different embedded metadata tags report mutually conflicting device {label} values.",
                {
                    "field": label,
                    "observations": [
                        {"value": value, "source_tag": source_tag}
                        for source_tag, value in values
                    ],
                },
                FindingSeverity.LOW,
                [
                    "Transcoding and metadata-copy workflows can preserve values from multiple devices.",
                    "This inconsistency is not proof that media content was manipulated.",
                ],
            )
        )

    editing_software = [
        observation.name
        for observation in creation_info.software_observations
        if observation.category
        in {SoftwareCategory.EDITOR, SoftwareCategory.AI_GENERATION}
    ]
    if (creation_info.device_make or creation_info.device_model) and editing_software:
        findings.append(
            _finding(
                "metadata.capture_edit_workflow",
                "Capture-device and editing-software metadata coexist",
                "The metadata describes both a capture device and software commonly used for editing or generation.",
                {
                    "device_make": creation_info.device_make,
                    "device_model": creation_info.device_model,
                    "software": editing_software,
                    "source_tags": sorted(
                        set(
                            creation_info.source_tags.get("device_make", [])
                            + creation_info.source_tags.get("device_model", [])
                            + creation_info.source_tags.get("software", [])
                        )
                    ),
                },
                FindingSeverity.INFO,
                [
                    "This is an informational workflow indicator only.",
                    "Legitimate cropping, color correction, export, and generation-assisted workflows can produce this combination.",
                ],
            )
        )
    return findings


def _duration_findings(
    sources: Any, absolute_tolerance: float, ratio_tolerance: float
) -> List[ForensicFinding]:
    observations: List[Dict[str, Any]] = []
    for source_tag, value in _matches(sources, ("duration",)):
        number = _number(value)
        if number is not None and number >= 0:
            observations.append({"duration_seconds": number, "source_tag": source_tag})
    if len(observations) < 2:
        return []
    earliest = min(observations, key=lambda item: (item["duration_seconds"], item["source_tag"]))
    latest = max(observations, key=lambda item: (item["duration_seconds"], item["source_tag"]))
    difference = latest["duration_seconds"] - earliest["duration_seconds"]
    tolerance = max(absolute_tolerance, latest["duration_seconds"] * ratio_tolerance)
    if difference <= tolerance:
        return []
    return [
        _finding(
            "metadata.duration_conflict",
            "Container and stream durations differ materially",
            "Embedded duration values differ by more than the configured absolute or proportional tolerance.",
            {
                "observations": observations[:16],
                "difference_seconds": round(difference, 6),
                "effective_tolerance_seconds": round(tolerance, 6),
            },
            FindingSeverity.LOW,
            [
                "Containers and streams may use different time bases or include padding.",
                "Duration disagreement is a review signal and not proof of manipulation.",
            ],
        )
    ]


def deduplicate_findings(findings: Iterable[ForensicFinding]) -> List[ForensicFinding]:
    """Return findings in a stable order with equivalent evidence removed."""
    unique: Dict[Tuple[str, str], ForensicFinding] = {}
    for finding in findings:
        evidence_key = json.dumps(
            finding.evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        unique.setdefault((finding.code, evidence_key), finding)
    return [unique[key] for key in sorted(unique)]


def analyze_metadata_consistency(
    sources: Any,
    *,
    detected_mime_type: str,
    original_filename: Optional[str] = None,
    declared_mime_type: Optional[str] = None,
    location_present: bool = False,
    location_source_tags: Sequence[str] = (),
    gps_observations: Sequence[Tuple[str, Any]] = (),
) -> MetadataConsistencyResult:
    """Normalize creation fields and run bounded deterministic consistency checks."""
    order_tolerance = _env_float(
        "FORENSIC_TIMESTAMP_ORDER_TOLERANCE_SECONDS",
        DEFAULT_TIMESTAMP_ORDER_TOLERANCE_SECONDS,
        0.0,
        86_400.0,
    )
    conflict_tolerance = _env_float(
        "FORENSIC_TIMESTAMP_CONFLICT_TOLERANCE_SECONDS",
        DEFAULT_TIMESTAMP_CONFLICT_TOLERANCE_SECONDS,
        0.0,
        31_536_000.0,
    )
    duration_tolerance = _env_float(
        "FORENSIC_DURATION_TOLERANCE_SECONDS",
        DEFAULT_DURATION_TOLERANCE_SECONDS,
        0.0,
        3600.0,
    )
    duration_ratio = _env_float(
        "FORENSIC_DURATION_TOLERANCE_RATIO",
        DEFAULT_DURATION_TOLERANCE_RATIO,
        0.0,
        1.0,
    )
    creation_info = normalize_creation_info(
        sources,
        location_present=location_present,
        location_source_tags=location_source_tags,
    )
    timestamps = _timestamp_observations(sources)
    findings: List[ForensicFinding] = []
    findings.extend(_timestamp_findings(timestamps, order_tolerance, conflict_tolerance))
    findings.extend(_gps_findings(gps_observations))
    findings.extend(_dimension_findings(sources))
    findings.extend(
        _type_findings(sources, detected_mime_type, original_filename, declared_mime_type)
    )
    findings.extend(_device_findings(sources, creation_info))
    findings.extend(_duration_findings(sources, duration_tolerance, duration_ratio))
    return MetadataConsistencyResult(
        status=ExtractorStatus.AVAILABLE,
        creation_info=creation_info,
        findings=deduplicate_findings(findings),
    )

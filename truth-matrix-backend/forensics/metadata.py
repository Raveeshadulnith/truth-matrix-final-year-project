from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import threading
import warnings as python_warnings
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union
from xml.etree.ElementTree import ParseError

from defusedxml.ElementTree import fromstring as safe_xml_fromstring
from defusedxml.common import DefusedXmlException
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from forensics.hashing import resolve_workspace_file
from forensics.inconsistencies import (
    MetadataConsistencyResult,
    analyze_metadata_consistency,
)
from forensics.precise_location import PreciseLocation, extract_precise_location
from schemas.forensic_schema import (
    CreationInfo,
    ExtractorStatus,
    ForensicFinding,
    MetadataEvidence,
)


PathLike = Union[str, Path]
JsonObject = Dict[str, JsonValue]
EXTRACTOR_VERSION = "metadata-v2"

DEFAULT_TOOL_TIMEOUT_SECONDS = 10.0
MIN_TOOL_TIMEOUT_SECONDS = 0.1
MAX_TOOL_TIMEOUT_SECONDS = 60.0
DEFAULT_TOOL_OUTPUT_BYTES = 1024 * 1024
MIN_TOOL_OUTPUT_BYTES = 16 * 1024
MAX_TOOL_OUTPUT_BYTES = 8 * 1024 * 1024
DEFAULT_MAX_TAGS = 256
MIN_MAX_TAGS = 16
MAX_MAX_TAGS = 2048
DEFAULT_MAX_DEPTH = 4
MIN_MAX_DEPTH = 1
MAX_MAX_DEPTH = 8
DEFAULT_MAX_KEY_CHARS = 128
MIN_MAX_KEY_CHARS = 16
MAX_MAX_KEY_CHARS = 512
DEFAULT_MAX_STRING_CHARS = 1024
MIN_MAX_STRING_CHARS = 64
MAX_MAX_STRING_CHARS = 8192
DEFAULT_MAX_SERIALIZED_BYTES = 64 * 1024
MIN_MAX_SERIALIZED_BYTES = 4096
MAX_MAX_SERIALIZED_BYTES = 1024 * 1024
DEFAULT_PILLOW_MAX_PIXELS = 100_000_000
MIN_PILLOW_MAX_PIXELS = 1_000_000
MAX_PILLOW_MAX_PIXELS = 500_000_000
DEFAULT_PILLOW_MAX_FILE_BYTES = 25 * 1024 * 1024
MIN_PILLOW_MAX_FILE_BYTES = 1024 * 1024
MAX_PILLOW_MAX_FILE_BYTES = 100 * 1024 * 1024
DEFAULT_FFPROBE_PROBESIZE_BYTES = 5_000_000
DEFAULT_FFPROBE_ANALYZE_DURATION_US = 5_000_000
DEFAULT_XMP_MAX_BYTES = 128 * 1024
MIN_XMP_MAX_BYTES = 1024
MAX_XMP_MAX_BYTES = 1024 * 1024
DEFAULT_XMP_MAX_DEPTH = 8
MIN_XMP_MAX_DEPTH = 2
MAX_XMP_MAX_DEPTH = 16
DEFAULT_XMP_MAX_FIELDS = 512
MIN_XMP_MAX_FIELDS = 16
MAX_XMP_MAX_FIELDS = 4096
DEFAULT_XMP_MAX_STRING_CHARS = 1024
MIN_XMP_MAX_STRING_CHARS = 64
MAX_XMP_MAX_STRING_CHARS = 8192

_SUPPORTED_MIME_PREFIXES = ("image/", "video/", "audio/")
_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
_SENSITIVE_KEY_PARTS = (
    "gps",
    "latitude",
    "longitude",
    "geolocation",
    "location",
    "serial",
    "password",
    "passwd",
    "secret",
    "token",
    "apikey",
    "accesskey",
)
_BINARY_KEY_PARTS = (
    "thumbnail",
    "previewimage",
    "jpgfromraw",
    "makernote",
    "binary",
    "rawdata",
    "profiledata",
    "photoshopsettings",
    "imagedata",
    "certificate",
)
_PRIVATE_TRANSPORT_KEYS = {
    "sourcefile",
    "directory",
    "filename",
    "filepath",
    "url",
    "uri",
    "filemodifydate",
    "fileaccessdate",
    "filecreatedate",
    "fileinodechangedate",
    "filepermissions",
}
_LOCATION_KEY_PARTS = ("gps", "latitude", "longitude", "geolocation", "location")
_XMP_FIELDS = {
    ("http://ns.adobe.com/xap/1.0/", "CreateDate"): "XMP:CreateDate",
    ("http://ns.adobe.com/xap/1.0/", "ModifyDate"): "XMP:ModifyDate",
    ("http://ns.adobe.com/xap/1.0/", "MetadataDate"): "XMP:MetadataDate",
    ("http://ns.adobe.com/xap/1.0/", "CreatorTool"): "XMP:CreatorTool",
    ("http://ns.adobe.com/photoshop/1.0/", "DateCreated"): "Photoshop:DateCreated",
    ("http://ns.adobe.com/exif/1.0/", "DateTimeOriginal"): "XMP-exif:DateTimeOriginal",
    ("http://ns.adobe.com/exif/1.0/", "GPSLatitude"): "XMP-exif:GPSLatitude",
    ("http://ns.adobe.com/exif/1.0/", "GPSLongitude"): "XMP-exif:GPSLongitude",
    ("http://ns.adobe.com/exif/1.0/", "GPSLatitudeRef"): "XMP-exif:GPSLatitudeRef",
    ("http://ns.adobe.com/exif/1.0/", "GPSLongitudeRef"): "XMP-exif:GPSLongitudeRef",
    ("http://ns.adobe.com/exif/1.0/", "GPSAltitude"): "XMP-exif:GPSAltitude",
    ("http://ns.adobe.com/exif/1.0/", "GPSAltitudeRef"): "XMP-exif:GPSAltitudeRef",
}


class MetadataExtractionResult(BaseModel):
    """Metadata evidence, normalized creation details, and extractor timing."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    evidence: MetadataEvidence
    creation_info: CreationInfo
    inconsistency_status: ExtractorStatus = ExtractorStatus.UNAVAILABLE
    findings: List[ForensicFinding] = Field(default_factory=list)
    processing_time_ms: int = Field(..., ge=0)
    precise_location: Optional[PreciseLocation] = Field(default=None, exclude=True)


@dataclass(frozen=True)
class ProcessOutput:
    """Bounded subprocess result without exposing captured output to callers."""

    returncode: int
    stdout: bytes
    stderr: bytes
    stdout_truncated: bool
    stderr_truncated: bool
    timed_out: bool


@dataclass(frozen=True)
class PillowExtraction:
    """Bounded Pillow metadata plus non-sensitive fallback warnings."""

    metadata: Dict[str, Any]
    warnings: Tuple[str, ...] = ()


@dataclass(frozen=True)
class MetadataLimits:
    """Configured bounds applied while sanitizing metadata."""

    max_tags: int
    max_depth: int
    max_key_chars: int
    max_string_chars: int
    max_serialized_bytes: int


@dataclass(frozen=True)
class SanitizedMetadata:
    """Bounded metadata plus presence flags captured before redaction."""

    raw: JsonObject
    warnings: List[str]
    location_present: bool
    xmp_present: bool
    c2pa_metadata_present: bool
    icc_profile_present: bool
    location_source_tags: Tuple[str, ...]
    gps_observations: Tuple[Tuple[str, Any], ...]


@dataclass
class _SanitizeState:
    limits: MetadataLimits
    tags_seen: int = 0
    redacted_fields: int = 0
    truncated_values: int = 0
    depth_omissions: int = 0
    location_present: bool = False
    xmp_present: bool = False
    c2pa_metadata_present: bool = False
    icc_profile_present: bool = False
    location_source_tags: List[str] = field(default_factory=list)
    gps_observations: List[Tuple[str, Any]] = field(default_factory=list)


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


def _metadata_limits() -> MetadataLimits:
    return MetadataLimits(
        max_tags=_env_int(
            "FORENSIC_METADATA_MAX_TAGS",
            DEFAULT_MAX_TAGS,
            MIN_MAX_TAGS,
            MAX_MAX_TAGS,
        ),
        max_depth=_env_int(
            "FORENSIC_METADATA_MAX_DEPTH",
            DEFAULT_MAX_DEPTH,
            MIN_MAX_DEPTH,
            MAX_MAX_DEPTH,
        ),
        max_key_chars=_env_int(
            "FORENSIC_METADATA_MAX_KEY_CHARS",
            DEFAULT_MAX_KEY_CHARS,
            MIN_MAX_KEY_CHARS,
            MAX_MAX_KEY_CHARS,
        ),
        max_string_chars=_env_int(
            "FORENSIC_METADATA_MAX_STRING_CHARS",
            DEFAULT_MAX_STRING_CHARS,
            MIN_MAX_STRING_CHARS,
            MAX_MAX_STRING_CHARS,
        ),
        max_serialized_bytes=_env_int(
            "FORENSIC_METADATA_MAX_JSON_BYTES",
            DEFAULT_MAX_SERIALIZED_BYTES,
            MIN_MAX_SERIALIZED_BYTES,
            MAX_MAX_SERIALIZED_BYTES,
        ),
    )


def discover_executable(env_name: str, executable_names: Sequence[str]) -> Optional[str]:
    """Find an explicit executable first, then search PATH by fixed names."""
    configured = (os.getenv(env_name) or "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file():
            return str(candidate.resolve())
        discovered = shutil.which(configured)
        return str(Path(discovered).resolve()) if discovered else None

    for name in executable_names:
        discovered = shutil.which(name)
        if discovered:
            return str(Path(discovered).resolve())
    return None


def _drain_bounded_pipe(
    stream: Any,
    destination: bytearray,
    limit: int,
    truncated: List[bool],
) -> None:
    try:
        while True:
            chunk = stream.read(8192)
            if not chunk:
                break
            remaining = limit - len(destination)
            if remaining > 0:
                destination.extend(chunk[:remaining])
            if len(chunk) > remaining:
                truncated[0] = True
    finally:
        stream.close()


def _run_bounded_process(
    arguments: Sequence[str],
    *,
    timeout_seconds: float,
    output_limit_bytes: int,
) -> ProcessOutput:
    """Run a fixed argument array with a timeout and bounded retained output."""
    process = subprocess.Popen(
        list(arguments),
        shell=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.stdout is None or process.stderr is None:
        process.kill()
        raise RuntimeError("Metadata tool output pipes were not created")

    stdout = bytearray()
    stderr = bytearray()
    stdout_truncated = [False]
    stderr_truncated = [False]
    readers = [
        threading.Thread(
            target=_drain_bounded_pipe,
            args=(process.stdout, stdout, output_limit_bytes, stdout_truncated),
            daemon=True,
        ),
        threading.Thread(
            target=_drain_bounded_pipe,
            args=(process.stderr, stderr, output_limit_bytes, stderr_truncated),
            daemon=True,
        ),
    ]
    for reader in readers:
        reader.start()

    timed_out = False
    try:
        returncode = process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        returncode = process.wait(timeout=2)
    finally:
        for reader in readers:
            reader.join(timeout=2)

    return ProcessOutput(
        returncode=returncode,
        stdout=bytes(stdout),
        stderr=bytes(stderr),
        stdout_truncated=stdout_truncated[0],
        stderr_truncated=stderr_truncated[0],
        timed_out=timed_out,
    )


def _leaf_key(key: object) -> str:
    text = str(key).rsplit(":", 1)[-1].rsplit(".", 1)[-1]
    return "".join(character for character in text.lower() if character.isalnum())


def _is_sensitive_key(key: object) -> bool:
    leaf = _leaf_key(key)
    return (
        leaf in _PRIVATE_TRANSPORT_KEYS
        or any(part in leaf for part in _SENSITIVE_KEY_PARTS)
        or any(part in leaf for part in _BINARY_KEY_PARTS)
    )


def _is_location_key(key: object) -> bool:
    leaf = _leaf_key(key)
    return any(part in leaf for part in _LOCATION_KEY_PARTS)


def _record_presence(state: _SanitizeState, key: object, value: Any) -> None:
    if value in (None, False, "", [], {}):
        return
    lowered_key = str(key).lower()
    if _is_location_key(key):
        state.location_present = True
        source_tag = str(key)[:256]
        if source_tag not in state.location_source_tags and len(state.location_source_tags) < 16:
            state.location_source_tags.append(source_tag)
        if len(state.gps_observations) < 32:
            state.gps_observations.append((source_tag, value))
    if "xmp" in lowered_key:
        state.xmp_present = True
    if any(
        marker in lowered_key
        for marker in ("c2pa", "jumbf", "manifeststore", "contentcredential")
    ):
        state.c2pa_metadata_present = True
    if "icc_profile" in lowered_key or "iccprofile" in lowered_key:
        state.icc_profile_present = True


def _sanitize_value(
    value: Any,
    state: _SanitizeState,
    *,
    depth: int,
) -> Optional[JsonValue]:
    if value is None or isinstance(value, bool) or isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        state.truncated_values += 1
        return None
    if isinstance(value, str):
        lowered_value = value.lower()
        if (
            "http://" in lowered_value
            or "https://" in lowered_value
            or lowered_value.startswith("(binary data")
        ):
            state.redacted_fields += 1
            return None
        if len(value) > state.limits.max_string_chars:
            state.truncated_values += 1
            return value[: state.limits.max_string_chars]
        return value
    if isinstance(value, bytes):
        state.redacted_fields += 1
        return None
    if depth > state.limits.max_depth:
        state.depth_omissions += 1
        return None
    if isinstance(value, dict):
        output: JsonObject = {}
        for raw_key, child in value.items():
            _record_presence(state, raw_key, child)
            if state.tags_seen >= state.limits.max_tags:
                state.truncated_values += 1
                continue
            state.tags_seen += 1
            if _is_sensitive_key(raw_key):
                if _is_location_key(raw_key) and child not in (None, "", [], {}):
                    state.location_present = True
                state.redacted_fields += 1
                continue
            key = str(raw_key)[: state.limits.max_key_chars]
            if not key or key in output:
                continue
            sanitized = _sanitize_value(child, state, depth=depth + 1)
            if sanitized is not None:
                output[key] = sanitized
        return output
    if isinstance(value, (list, tuple)):
        output_list: List[JsonValue] = []
        for child in value:
            if state.tags_seen >= state.limits.max_tags:
                state.truncated_values += 1
                break
            sanitized = _sanitize_value(child, state, depth=depth + 1)
            if sanitized is not None:
                output_list.append(sanitized)
        return output_list

    text = str(value)
    if len(text) > state.limits.max_string_chars:
        state.truncated_values += 1
        text = text[: state.limits.max_string_chars]
    return text


def _serialized_size(value: JsonObject) -> int:
    return len(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )


def _remove_last_leaf(value: Any) -> bool:
    if isinstance(value, dict) and value:
        last_key = next(reversed(value))
        child = value[last_key]
        if _remove_last_leaf(child):
            if child in ({}, []):
                value.pop(last_key, None)
            return True
        value.pop(last_key, None)
        return True
    if isinstance(value, list) and value:
        child = value[-1]
        if _remove_last_leaf(child):
            if child in ({}, []):
                value.pop()
            return True
        value.pop()
        return True
    return False


def sanitize_raw_metadata(
    sources: Dict[str, Any],
    limits: MetadataLimits,
) -> SanitizedMetadata:
    """Redact sensitive fields and enforce depth, tag, value, and JSON bounds."""
    state = _SanitizeState(limits=limits)
    sanitized = _sanitize_value(sources, state, depth=0)
    output = sanitized if isinstance(sanitized, dict) else {}
    size_trimmed = False
    while _serialized_size(output) > limits.max_serialized_bytes:
        if not _remove_last_leaf(output):
            output = {}
            break
        size_trimmed = True

    warnings: List[str] = []
    if state.redacted_fields:
        warnings.append(
            f"Redacted {state.redacted_fields} sensitive or binary metadata fields."
        )
    if state.truncated_values or state.depth_omissions or size_trimmed:
        warnings.append("Raw metadata was truncated to configured safety limits.")
    return SanitizedMetadata(
        raw=output,
        warnings=warnings,
        location_present=state.location_present,
        xmp_present=state.xmp_present,
        c2pa_metadata_present=state.c2pa_metadata_present,
        icc_profile_present=state.icc_profile_present,
        location_source_tags=tuple(state.location_source_tags),
        gps_observations=tuple(state.gps_observations),
    )


def _parse_json_output(output: ProcessOutput, tool_name: str) -> Any:
    if output.timed_out:
        raise TimeoutError(f"{tool_name} exceeded the metadata extraction timeout.")
    if output.stdout_truncated or output.stderr_truncated:
        raise ValueError(f"{tool_name} output exceeded the configured byte limit.")
    if output.returncode != 0:
        raise RuntimeError(f"{tool_name} failed with exit code {output.returncode}.")
    try:
        return json.loads(output.stdout.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(f"{tool_name} returned malformed JSON.") from exc


def _run_exiftool(
    executable: str,
    path: Path,
    *,
    timeout_seconds: float,
    output_limit_bytes: int,
) -> Dict[str, Any]:
    arguments = [
        executable,
        "-json",
        "-G1",
        "-struct",
        "-n",
        "-charset",
        "filename=UTF8",
        "-x",
        "ThumbnailImage",
        "-x",
        "PreviewImage",
        "-x",
        "JpgFromRaw",
        "-x",
        "MakerNotes",
        str(path),
    ]
    parsed = _parse_json_output(
        _run_bounded_process(
            arguments,
            timeout_seconds=timeout_seconds,
            output_limit_bytes=output_limit_bytes,
        ),
        "ExifTool",
    )
    if not isinstance(parsed, list) or len(parsed) != 1 or not isinstance(parsed[0], dict):
        raise ValueError("ExifTool returned an unexpected JSON structure.")
    return parsed[0]


def _run_ffprobe(
    executable: str,
    path: Path,
    *,
    timeout_seconds: float,
    output_limit_bytes: int,
) -> Dict[str, Any]:
    probe_size = _env_int(
        "FORENSIC_FFPROBE_PROBESIZE_BYTES",
        DEFAULT_FFPROBE_PROBESIZE_BYTES,
        32_768,
        100_000_000,
    )
    analyze_duration = _env_int(
        "FORENSIC_FFPROBE_ANALYZE_DURATION_US",
        DEFAULT_FFPROBE_ANALYZE_DURATION_US,
        0,
        60_000_000,
    )
    arguments = [
        executable,
        "-v",
        "error",
        "-hide_banner",
        "-nostdin",
        "-protocol_whitelist",
        "file",
        "-probesize",
        str(probe_size),
        "-analyzeduration",
        str(analyze_duration),
        "-show_error",
        "-show_format",
        "-show_streams",
        "-of",
        "json",
        str(path),
    ]
    parsed = _parse_json_output(
        _run_bounded_process(
            arguments,
            timeout_seconds=timeout_seconds,
            output_limit_bytes=output_limit_bytes,
        ),
        "ffprobe",
    )
    if not isinstance(parsed, dict):
        raise ValueError("ffprobe returned an unexpected JSON structure.")
    return parsed


def _bounded_pillow_value(
    value: Any,
    *,
    maximum_string_chars: int,
    depth: int = 0,
) -> Optional[Any]:
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, bytes):
        return None
    if isinstance(value, str):
        return value[:maximum_string_chars]
    if depth >= 2:
        return None
    if isinstance(value, (tuple, list)):
        bounded = [
            _bounded_pillow_value(
                item,
                maximum_string_chars=maximum_string_chars,
                depth=depth + 1,
            )
            for item in value[:16]
        ]
        return [item for item in bounded if item is not None]
    text = str(value)
    return text[:maximum_string_chars] if text else None


def _ifd_metadata(
    values: Any,
    *,
    prefix: str,
    tag_names: Dict[int, str],
    limits: MetadataLimits,
    remaining_tags: List[int],
) -> Dict[str, Any]:
    output: Dict[str, Any] = {}
    if not hasattr(values, "items"):
        return output
    for tag_id, value in sorted(values.items(), key=lambda item: str(item[0])):
        if remaining_tags[0] <= 0:
            break
        tag_name = tag_names.get(tag_id, f"Tag{tag_id}")
        if tag_name in {"ExifOffset", "GPSInfo", "InteroperabilityOffset"}:
            continue
        bounded = _bounded_pillow_value(
            value,
            maximum_string_chars=limits.max_string_chars,
        )
        if bounded is None:
            continue
        output[f"{prefix}:{tag_name}"] = bounded
        remaining_tags[0] -= 1
    return output


def _xml_name(value: str) -> Tuple[str, str]:
    if value.startswith("{") and "}" in value:
        namespace, local_name = value[1:].split("}", 1)
        return namespace, local_name
    return "", value


def _validate_xmp_tree(root: Any, *, maximum_depth: int, maximum_fields: int) -> None:
    fields_seen = 0

    def visit(element: Any, depth: int) -> None:
        nonlocal fields_seen
        if depth > maximum_depth:
            raise ValueError("Embedded XMP exceeds the configured depth limit.")
        fields_seen += 1 + len(getattr(element, "attrib", {}))
        if fields_seen > maximum_fields:
            raise ValueError("Embedded XMP exceeds the configured field-count limit.")
        for child in list(element):
            visit(child, depth + 1)

    visit(root, 1)


def _parse_xmp_fields(
    packet: bytes,
    *,
    maximum_bytes: int,
    maximum_depth: int,
    maximum_fields: int,
    maximum_string_chars: int,
) -> Dict[str, str]:
    if len(packet) > maximum_bytes:
        raise ValueError("Embedded XMP exceeds the configured byte limit.")
    try:
        root = safe_xml_fromstring(
            packet,
            forbid_dtd=True,
            forbid_entities=True,
            forbid_external=True,
        )
    except (DefusedXmlException, ParseError, SyntaxError, ValueError) as exc:
        raise ValueError("Embedded XMP could not be parsed safely.") from exc
    _validate_xmp_tree(
        root,
        maximum_depth=maximum_depth,
        maximum_fields=maximum_fields,
    )

    output: Dict[str, str] = {}
    for element in root.iter():
        for attribute, raw_value in sorted(element.attrib.items()):
            output_name = _XMP_FIELDS.get(_xml_name(attribute))
            value = str(raw_value).strip()
            if output_name and value and output_name not in output:
                output[output_name] = value[:maximum_string_chars]
        output_name = _XMP_FIELDS.get(_xml_name(str(element.tag)))
        if output_name and output_name not in output:
            value = "".join(element.itertext()).strip()
            if value:
                output[output_name] = value[:maximum_string_chars]
    return output


def _xmp_packet(image: Any) -> Optional[bytes]:
    for key in ("xmp", "XML:com.adobe.xmp"):
        value = image.info.get(key)
        if isinstance(value, str) and value:
            return value.encode("utf-8")
        if isinstance(value, (bytes, bytearray, memoryview)) and value:
            return bytes(value)
    return None


def _extract_with_pillow(
    path: Path,
    max_pixels: int,
    max_file_bytes: int,
    limits: MetadataLimits,
) -> PillowExtraction:
    from PIL import ExifTags, Image

    if path.stat().st_size > max_file_bytes:
        raise ValueError("Image exceeds the configured Pillow file-size limit.")

    warnings: List[str] = []
    try:
        with python_warnings.catch_warnings():
            python_warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                width, height = image.size
                if width <= 0 or height <= 0 or width * height > max_pixels:
                    raise ValueError(
                        "Image dimensions exceed the configured Pillow pixel limit."
                    )

                raw_exif: Dict[str, Any] = {}
                remaining_tags = [limits.max_tags]
                try:
                    exif = image.getexif()
                    raw_exif.update(
                        _ifd_metadata(
                            exif,
                            prefix="IFD0",
                            tag_names=ExifTags.TAGS,
                            limits=limits,
                            remaining_tags=remaining_tags,
                        )
                    )
                except (KeyError, OSError, TypeError, ValueError):
                    exif = None
                    warnings.append("The image's IFD0 metadata could not be parsed safely.")

                nested_ifds: Dict[str, Any] = {}
                if exif is not None:
                    for prefix, ifd_id, tag_names in (
                        ("ExifIFD", ExifTags.IFD.Exif, ExifTags.TAGS),
                        ("GPS", ExifTags.IFD.GPSInfo, ExifTags.GPSTAGS),
                    ):
                        try:
                            nested_ifds[prefix] = exif.get_ifd(ifd_id)
                            raw_exif.update(
                                _ifd_metadata(
                                    nested_ifds[prefix],
                                    prefix=prefix,
                                    tag_names=tag_names,
                                    limits=limits,
                                    remaining_tags=remaining_tags,
                                )
                            )
                        except (KeyError, OSError, TypeError, ValueError):
                            warnings.append(
                                f"The image's {prefix} metadata could not be parsed safely."
                            )

                    exif_ifd = nested_ifds.get("ExifIFD")
                    if hasattr(exif_ifd, "__contains__") and 40965 in exif_ifd:
                        try:
                            raw_exif.update(
                                _ifd_metadata(
                                    exif.get_ifd(ExifTags.IFD.Interop),
                                    prefix="InteropIFD",
                                    tag_names=ExifTags.TAGS,
                                    limits=limits,
                                    remaining_tags=remaining_tags,
                                )
                            )
                        except (KeyError, OSError, TypeError, ValueError):
                            warnings.append(
                                "The image's InteropIFD metadata could not be parsed safely."
                            )

                packet = _xmp_packet(image)
                xmp_metadata: Dict[str, str] = {}
                if packet is not None:
                    try:
                        xmp_metadata = _parse_xmp_fields(
                            packet,
                            maximum_bytes=_env_int(
                                "FORENSIC_XMP_MAX_BYTES",
                                DEFAULT_XMP_MAX_BYTES,
                                MIN_XMP_MAX_BYTES,
                                MAX_XMP_MAX_BYTES,
                            ),
                            maximum_depth=_env_int(
                                "FORENSIC_XMP_MAX_DEPTH",
                                DEFAULT_XMP_MAX_DEPTH,
                                MIN_XMP_MAX_DEPTH,
                                MAX_XMP_MAX_DEPTH,
                            ),
                            maximum_fields=_env_int(
                                "FORENSIC_XMP_MAX_FIELDS",
                                DEFAULT_XMP_MAX_FIELDS,
                                MIN_XMP_MAX_FIELDS,
                                MAX_XMP_MAX_FIELDS,
                            ),
                            maximum_string_chars=_env_int(
                                "FORENSIC_XMP_MAX_STRING_CHARS",
                                DEFAULT_XMP_MAX_STRING_CHARS,
                                MIN_XMP_MAX_STRING_CHARS,
                                MAX_XMP_MAX_STRING_CHARS,
                            ),
                        )
                    except ValueError as exc:
                        warnings.append(str(exc))

                return PillowExtraction(
                    metadata={
                        "Pillow:Format": image.format,
                        "Pillow:MIMEType": Image.MIME.get(image.format or ""),
                        "Pillow:ImageWidth": width,
                        "Pillow:ImageHeight": height,
                        "Pillow:ColorMode": image.mode,
                        "Pillow:BitDepth": _pillow_bit_depth(image.mode),
                        "Pillow:ICCProfilePresent": bool(image.info.get("icc_profile")),
                        "Pillow:XMPPresent": packet is not None,
                        **raw_exif,
                        **xmp_metadata,
                    },
                    warnings=tuple(warnings),
                )
    except Image.DecompressionBombWarning as exc:
        raise ValueError("Image dimensions exceed Pillow's safe pixel limit.") from exc


def _pillow_bit_depth(mode: str) -> Optional[int]:
    if mode in {"1"}:
        return 1
    if mode in {"L", "P", "RGB", "RGBA", "CMYK", "YCbCr", "LAB", "HSV"}:
        return 8
    if mode.startswith("I;16"):
        return 16
    if mode in {"I", "F"}:
        return 32
    return None


def _walk_items(value: Any, prefix: str = "") -> Iterable[Tuple[str, Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            qualified = f"{prefix}.{key}" if prefix else str(key)
            yield qualified, child
            yield from _walk_items(child, qualified)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_items(child, f"{prefix}[{index}]")


def _values_for(source: Any, *names: str) -> List[Tuple[str, Any]]:
    wanted = {"".join(character for character in name.lower() if character.isalnum()) for name in names}
    matches: List[Tuple[str, Any]] = []
    for key, value in _walk_items(source):
        if _leaf_key(key) in wanted and not isinstance(value, (dict, list)):
            matches.append((key, value))
    return matches


def _first_value(source: Any, *names: str) -> Optional[Any]:
    values = _values_for(source, *names)
    return values[0][1] if values else None


def _as_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text[:1024] if text else None


def _as_number(value: Any) -> Optional[Union[int, float]]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return value
    text = str(value).strip()
    if "/" in text:
        numerator, denominator = text.split("/", 1)
        try:
            denominator_number = float(denominator)
            if denominator_number:
                return round(float(numerator) / denominator_number, 6)
        except ValueError:
            return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    if not math.isfinite(parsed):
        return None
    return int(parsed) if parsed.is_integer() else parsed


def _normalize_metadata(
    sources: Dict[str, Any],
    detected_mime_type: str,
    presence: SanitizedMetadata,
    creation_info: CreationInfo,
) -> JsonObject:
    exif = sources.get("exiftool", {})
    ffprobe = sources.get("ffprobe", {})
    pillow = sources.get("pillow", {})
    combined = {**pillow, **exif}
    format_data = ffprobe.get("format", {}) if isinstance(ffprobe, dict) else {}
    streams = ffprobe.get("streams", []) if isinstance(ffprobe, dict) else []
    streams = streams if isinstance(streams, list) else []
    video_stream = next(
        (item for item in streams if isinstance(item, dict) and item.get("codec_type") == "video"),
        {},
    )
    audio_stream = next(
        (item for item in streams if isinstance(item, dict) and item.get("codec_type") == "audio"),
        {},
    )

    file_facts: JsonObject = {
        "format": _as_string(
            _first_value(combined, "FileType", "Format")
            or (format_data.get("format_name") if isinstance(format_data, dict) else None)
        ),
        "format_long_name": _as_string(
            format_data.get("format_long_name") if isinstance(format_data, dict) else None
        ),
        "mime_type": _as_string(_first_value(combined, "MIMEType") or detected_mime_type),
    }
    normalized: JsonObject = {
        "extractor_version": EXTRACTOR_VERSION,
        "file": {key: value for key, value in file_facts.items() if value is not None},
        "presence": {
            "location_present": presence.location_present,
            "xmp_present": presence.xmp_present,
            "c2pa_metadata_present": presence.c2pa_metadata_present,
        },
    }

    if detected_mime_type.startswith("image/"):
        image_facts: JsonObject = {
            "width": _as_number(_first_value(combined, "ImageWidth", "ExifImageWidth")),
            "height": _as_number(_first_value(combined, "ImageHeight", "ExifImageHeight")),
            "orientation": _as_string(_first_value(combined, "Orientation")),
            "color_space": _as_string(_first_value(combined, "ColorSpace", "ColorMode")),
            "bit_depth": _as_number(_first_value(combined, "BitDepth", "BitsPerSample")),
            "icc_profile_present": bool(_first_value(combined, "ICCProfilePresent"))
            or presence.icc_profile_present,
        }
        normalized["image"] = {
            key: value for key, value in image_facts.items() if value is not None
        }

    if detected_mime_type.startswith("video/"):
        video_facts: JsonObject = {
            "duration_seconds": _as_number(
                video_stream.get("duration")
                or (format_data.get("duration") if isinstance(format_data, dict) else None)
                or _first_value(combined, "Duration")
            ),
            "codec": _as_string(video_stream.get("codec_name") or _first_value(combined, "VideoCodec")),
            "profile": _as_string(video_stream.get("profile") or _first_value(combined, "VideoProfile")),
            "frame_rate": _as_number(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")),
            "width": _as_number(video_stream.get("width") or _first_value(combined, "ImageWidth")),
            "height": _as_number(video_stream.get("height") or _first_value(combined, "ImageHeight")),
            "bit_rate": _as_number(video_stream.get("bit_rate") or format_data.get("bit_rate")),
            "stream_count": len(streams),
            "pixel_format": _as_string(video_stream.get("pix_fmt")),
            "bit_depth": _as_number(video_stream.get("bits_per_raw_sample")),
        }
        normalized["video"] = {
            key: value for key, value in video_facts.items() if value is not None
        }

    if detected_mime_type.startswith("audio/"):
        audio_facts: JsonObject = {
            "duration_seconds": _as_number(
                audio_stream.get("duration")
                or (format_data.get("duration") if isinstance(format_data, dict) else None)
                or _first_value(combined, "Duration")
            ),
            "codec": _as_string(audio_stream.get("codec_name") or _first_value(combined, "AudioCodec")),
            "profile": _as_string(audio_stream.get("profile")),
            "sample_rate": _as_number(audio_stream.get("sample_rate") or _first_value(combined, "SampleRate")),
            "channels": _as_number(audio_stream.get("channels") or _first_value(combined, "Channels")),
            "channel_layout": _as_string(audio_stream.get("channel_layout")),
            "bit_rate": _as_number(audio_stream.get("bit_rate") or format_data.get("bit_rate")),
            "stream_count": len(streams),
        }
        normalized["audio"] = {
            key: value for key, value in audio_facts.items() if value is not None
        }

    lens = _as_string(_first_value(sources, "Lens", "LensModel"))
    copyright_value = _as_string(_first_value(sources, "Copyright"))
    normalized_creation: JsonObject = creation_info.model_dump(mode="json")
    if lens is not None:
        normalized_creation["lens"] = lens
    if copyright_value is not None:
        normalized_creation["copyright"] = copyright_value
    normalized["creation"] = normalized_creation
    return normalized


def extract_metadata(
    file_path: PathLike,
    *,
    detected_mime_type: str,
    original_filename: Optional[str] = None,
    declared_mime_type: Optional[str] = None,
    allowed_root: Optional[PathLike] = None,
) -> MetadataExtractionResult:
    """Extract bounded metadata without allowing one tool failure to escape."""
    started_at = perf_counter()

    def elapsed_ms() -> int:
        return max(0, round((perf_counter() - started_at) * 1000))

    if not detected_mime_type.startswith(_SUPPORTED_MIME_PREFIXES):
        return MetadataExtractionResult(
            evidence={
                "status": "unsupported",
                "source_version": EXTRACTOR_VERSION,
                "warnings": ["Metadata extraction does not support this media type."],
            },
            creation_info={},
            processing_time_ms=elapsed_ms(),
        )

    try:
        path = resolve_workspace_file(file_path, allowed_root)
        limits = _metadata_limits()
        timeout_seconds = _env_float(
            "FORENSIC_METADATA_TOOL_TIMEOUT_SECONDS",
            DEFAULT_TOOL_TIMEOUT_SECONDS,
            MIN_TOOL_TIMEOUT_SECONDS,
            MAX_TOOL_TIMEOUT_SECONDS,
        )
        output_limit_bytes = _env_int(
            "FORENSIC_TOOL_OUTPUT_MAX_BYTES",
            DEFAULT_TOOL_OUTPUT_BYTES,
            MIN_TOOL_OUTPUT_BYTES,
            MAX_TOOL_OUTPUT_BYTES,
        )
    except (FileNotFoundError, PermissionError, OSError, ValueError) as exc:
        return MetadataExtractionResult(
            evidence={
                "status": "error",
                "source_version": EXTRACTOR_VERSION,
                "warnings": [str(exc)],
            },
            creation_info={},
            processing_time_ms=elapsed_ms(),
        )

    sources: Dict[str, Any] = {}
    source_names: List[str] = []
    warnings: List[str] = []
    attempted_tools = 0
    failed_tools = 0

    exiftool = discover_executable("EXIFTOOL_PATH", ("exiftool", "exiftool.exe"))
    if exiftool:
        attempted_tools += 1
        try:
            sources["exiftool"] = _run_exiftool(
                exiftool,
                path,
                timeout_seconds=timeout_seconds,
                output_limit_bytes=output_limit_bytes,
            )
            source_names.append("exiftool")
        except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
            failed_tools += 1
            warnings.append(str(exc))
    else:
        warnings.append("ExifTool is unavailable.")

    if detected_mime_type.startswith(("video/", "audio/")):
        ffprobe = discover_executable("FFPROBE_PATH", ("ffprobe", "ffprobe.exe"))
        if ffprobe:
            attempted_tools += 1
            try:
                sources["ffprobe"] = _run_ffprobe(
                    ffprobe,
                    path,
                    timeout_seconds=timeout_seconds,
                    output_limit_bytes=output_limit_bytes,
                )
                source_names.append("ffprobe")
            except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
                failed_tools += 1
                warnings.append(str(exc))
        else:
            warnings.append("ffprobe is unavailable.")

    if detected_mime_type in _IMAGE_MIME_TYPES and "exiftool" not in sources:
        attempted_tools += 1
        try:
            max_pixels = _env_int(
                "FORENSIC_PILLOW_MAX_PIXELS",
                DEFAULT_PILLOW_MAX_PIXELS,
                MIN_PILLOW_MAX_PIXELS,
                MAX_PILLOW_MAX_PIXELS,
            )
            max_file_bytes = _env_int(
                "FORENSIC_PILLOW_MAX_FILE_BYTES",
                DEFAULT_PILLOW_MAX_FILE_BYTES,
                MIN_PILLOW_MAX_FILE_BYTES,
                MAX_PILLOW_MAX_FILE_BYTES,
            )
            pillow_result = _extract_with_pillow(
                path,
                max_pixels,
                max_file_bytes,
                limits,
            )
            sources["pillow"] = pillow_result.metadata
            warnings.extend(pillow_result.warnings)
            source_names.append("pillow")
        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            failed_tools += 1
            warnings.append("Pillow metadata fallback failed.")

    if not sources:
        status = "error" if attempted_tools and failed_tools == attempted_tools else "unavailable"
        return MetadataExtractionResult(
            evidence={
                "status": status,
                "source_version": EXTRACTOR_VERSION,
                "warnings": warnings,
            },
            creation_info={},
            processing_time_ms=elapsed_ms(),
        )

    sanitized = sanitize_raw_metadata(
        sources,
        limits,
    )
    precise_location = extract_precise_location(
        sanitized.gps_observations,
        detected_mime_type=detected_mime_type,
    )
    try:
        consistency = analyze_metadata_consistency(
            sanitized.raw,
            detected_mime_type=detected_mime_type,
            original_filename=original_filename,
            declared_mime_type=declared_mime_type,
            location_present=sanitized.location_present,
            location_source_tags=sanitized.location_source_tags,
            gps_observations=sanitized.gps_observations,
        )
    except Exception:
        consistency = MetadataConsistencyResult(status="error")
        warnings.append("Metadata consistency checks failed safely.")
    normalized = _normalize_metadata(
        sanitized.raw,
        detected_mime_type,
        sanitized,
        consistency.creation_info,
    )
    warnings.extend(sanitized.warnings)
    return MetadataExtractionResult(
        evidence={
            "status": "available",
            "source": ",".join(source_names),
            "source_version": EXTRACTOR_VERSION,
            "normalized": normalized,
            "raw": sanitized.raw,
            "warnings": warnings,
        },
        creation_info=consistency.creation_info,
        inconsistency_status=consistency.status,
        findings=consistency.findings,
        processing_time_ms=elapsed_ms(),
        precise_location=precise_location,
    )

from __future__ import annotations

import hashlib
import os
import struct
from pathlib import Path
from time import perf_counter
from typing import Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field

from schemas.forensic_schema import ExtractorStatus, ForensicFinding


PathLike = Union[str, Path]

DEFAULT_HASH_CHUNK_BYTES = 1024 * 1024
MIN_HASH_CHUNK_BYTES = 4096
MAX_HASH_CHUNK_BYTES = 8 * 1024 * 1024
DEFAULT_SIGNATURE_BYTES = 4096
MIN_SIGNATURE_BYTES = 64
MAX_SIGNATURE_BYTES = 64 * 1024
DEFAULT_UPLOAD_ROOT = Path(__file__).resolve().parents[1] / "uploads"

_SUPPORTED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "video/mp4",
    "video/quicktime",
    "video/x-msvideo",
    "video/x-matroska",
    "video/webm",
    "audio/wav",
    "audio/mpeg",
    "audio/mp4",
}

_EXTENSION_MIME_TYPES: Dict[str, str] = {
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
    "pdf": "application/pdf",
    "gif": "image/gif",
    "zip": "application/zip",
    "exe": "application/vnd.microsoft.portable-executable",
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
    "video/x-msvideo": "video/x-msvideo",
}

_GENERIC_DECLARED_MIME_TYPES = {"", "application/octet-stream", "binary/octet-stream"}
_QUICKTIME_BRANDS = {b"qt  "}
_MP4_AUDIO_BRANDS = {b"M4A ", b"M4B ", b"M4P ", b"F4A ", b"F4B "}
_HEIF_BRANDS = {b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1"}
_AVIF_BRANDS = {b"avif", b"avis"}
_THREE_GP_BRANDS = {b"3gp4", b"3gp5", b"3gp6", b"3ge6", b"3gg6"}
_MP4_VIDEO_BRANDS = {
    b"isom",
    b"iso2",
    b"iso3",
    b"iso4",
    b"iso5",
    b"iso6",
    b"avc1",
    b"dash",
    b"mp41",
    b"mp42",
    b"M4V ",
    b"MSNV",
}


class FileIdentityEvidence(BaseModel):
    """Structured result from the independent file identity extractor."""

    model_config = ConfigDict(extra="forbid")

    status: ExtractorStatus
    sha256: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    file_size_bytes: Optional[int] = Field(default=None, ge=0)
    detected_mime_type: Optional[str] = None
    normalized_extension: Optional[str] = None
    normalized_declared_mime_type: Optional[str] = None
    findings: List[ForensicFinding] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    processing_time_ms: int = Field(..., ge=0)


def normalize_mime_type(value: Optional[str]) -> Optional[str]:
    """Normalize a bounded MIME value and common aliases for comparison."""
    if value is None:
        return None
    cleaned = str(value)[:255].split(";", 1)[0].strip().lower()
    if not cleaned:
        return None
    return _MIME_ALIASES.get(cleaned, cleaned)


def _configured_int(
    name: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _resolve_upload_root(allowed_root: Optional[PathLike]) -> Path:
    configured_root = allowed_root or os.getenv("FORENSIC_UPLOAD_ROOT") or DEFAULT_UPLOAD_ROOT
    return Path(configured_root).expanduser().resolve(strict=False)


def resolve_workspace_file(
    file_path: PathLike,
    allowed_root: Optional[PathLike] = None,
) -> Path:
    """Resolve a regular file contained by the configured upload workspace."""
    root = _resolve_upload_root(allowed_root)
    candidate = Path(file_path).expanduser().resolve(strict=False)
    if not candidate.is_relative_to(root):
        raise PermissionError("File is outside the configured forensic upload workspace.")
    if not candidate.exists():
        raise FileNotFoundError("File does not exist in the forensic upload workspace.")
    if not candidate.is_file():
        raise ValueError("Forensic input must be a regular file.")
    return candidate


def _iso_bmff_brands(header: bytes) -> Optional[Tuple[bytes, set[bytes]]]:
    offset = 0
    header_length = len(header)

    while offset + 8 <= header_length:
        box_size = struct.unpack(">I", header[offset : offset + 4])[0]
        box_type = header[offset + 4 : offset + 8]
        header_size = 8

        if box_size == 1:
            if offset + 16 > header_length:
                return None
            box_size = struct.unpack(">Q", header[offset + 8 : offset + 16])[0]
            header_size = 16
        elif box_size == 0:
            box_size = header_length - offset

        if box_size < header_size:
            return None

        if box_type == b"ftyp":
            payload_start = offset + header_size
            payload_end = min(offset + box_size, header_length)
            payload = header[payload_start:payload_end]
            if len(payload) < 8:
                return None
            major_brand = payload[:4]
            compatible_brands = {
                payload[index : index + 4]
                for index in range(8, len(payload) - 3, 4)
            }
            return major_brand, compatible_brands | {major_brand}

        next_offset = offset + box_size
        if next_offset <= offset or next_offset > header_length:
            return None
        offset = next_offset

    return None


def _looks_like_mpeg_audio_frame(header: bytes, offset: int = 0) -> bool:
    if len(header) < offset + 4:
        return False
    frame = header[offset : offset + 4]
    if frame[0] != 0xFF or frame[1] & 0xE0 != 0xE0:
        return False
    version_bits = (frame[1] >> 3) & 0x03
    layer_bits = (frame[1] >> 1) & 0x03
    bitrate_index = (frame[2] >> 4) & 0x0F
    sample_rate_index = (frame[2] >> 2) & 0x03
    return (
        version_bits != 0x01
        and layer_bits != 0x00
        and bitrate_index not in {0x00, 0x0F}
        and sample_rate_index != 0x03
    )


def _looks_like_mp3(header: bytes) -> bool:
    if _looks_like_mpeg_audio_frame(header):
        return True
    if len(header) < 10 or not header.startswith(b"ID3"):
        return False
    if header[3] == 0xFF or header[4] == 0xFF or any(byte & 0x80 for byte in header[6:10]):
        return False
    tag_size = (
        (header[6] << 21)
        | (header[7] << 14)
        | (header[8] << 7)
        | header[9]
    )
    frame_offset = 10 + tag_size
    return frame_offset + 4 > len(header) or _looks_like_mpeg_audio_frame(
        header, frame_offset
    )


def detect_mime_type(header: bytes) -> Optional[str]:
    """Detect supported and common dangerous media types from bounded bytes."""
    if header.startswith(b"\xFF\xD8\xFF"):
        return "image/jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(header) >= 12 and header[:4] == b"RIFF":
        riff_type = header[8:12]
        if riff_type == b"WEBP":
            return "image/webp"
        if riff_type == b"WAVE":
            return "audio/wav"
        if riff_type == b"AVI ":
            return "video/x-msvideo"
    if _looks_like_mp3(header):
        return "audio/mpeg"
    if header.startswith(b"\x1a\x45\xdf\xa3"):
        lowered = header[:MAX_SIGNATURE_BYTES].lower()
        if b"webm" in lowered:
            return "video/webm"
        return "video/x-matroska"

    brands = _iso_bmff_brands(header)
    if brands:
        _, all_brands = brands
        if all_brands & _QUICKTIME_BRANDS:
            return "video/quicktime"
        if all_brands & _MP4_AUDIO_BRANDS:
            return "audio/mp4"
        if all_brands & _HEIF_BRANDS:
            return "image/heic"
        if all_brands & _AVIF_BRANDS:
            return "image/avif"
        if all_brands & _THREE_GP_BRANDS:
            return "video/3gpp"
        if all_brands & _MP4_VIDEO_BRANDS:
            return "video/mp4"
        return "application/mp4"

    if header.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if header.startswith(b"%PDF-"):
        return "application/pdf"
    if header.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        return "application/zip"
    if header.startswith(b"MZ"):
        return "application/vnd.microsoft.portable-executable"
    if header.startswith(b"Rar!\x1a\x07"):
        return "application/vnd.rar"
    if header.startswith(b"7z\xbc\xaf\x27\x1c"):
        return "application/x-7z-compressed"
    return None


def _mismatch_finding(
    *,
    code: str,
    title: str,
    compared_field: str,
    observed_value: str,
    detected_mime_type: str,
) -> ForensicFinding:
    return ForensicFinding(
        code=code,
        title=title,
        explanation=(
            "The byte-detected media type differs from a file declaration. "
            "Renaming, export workflows, or incorrect client metadata are common "
            "benign causes; this is not proof of manipulation."
        ),
        evidence={
            "detected_mime_type": detected_mime_type,
            compared_field: observed_value,
        },
        severity="low",
        method="magic-byte-signature",
        method_version="1.0",
        limitations=[
            "Signature detection identifies a container family but does not fully decode the file."
        ],
    )


def _type_findings(
    *,
    detected_mime_type: str,
    extension: Optional[str],
    declared_mime_type: Optional[str],
) -> List[ForensicFinding]:
    findings: List[ForensicFinding] = []
    expected_from_extension = _EXTENSION_MIME_TYPES.get(extension or "")
    if expected_from_extension and expected_from_extension != detected_mime_type:
        findings.append(
            _mismatch_finding(
                code="file_type.extension_mismatch",
                title="Filename extension differs from detected type",
                compared_field="extension_mime_type",
                observed_value=expected_from_extension,
                detected_mime_type=detected_mime_type,
            )
        )

    if (
        declared_mime_type is not None
        and declared_mime_type not in _GENERIC_DECLARED_MIME_TYPES
        and declared_mime_type != detected_mime_type
    ):
        findings.append(
            _mismatch_finding(
                code="file_type.declared_mime_mismatch",
                title="Declared MIME type differs from detected type",
                compared_field="declared_mime_type",
                observed_value=declared_mime_type or "",
                detected_mime_type=detected_mime_type,
            )
        )
    return findings


def extract_file_identity(
    file_path: PathLike,
    *,
    original_filename: Optional[str] = None,
    declared_mime_type: Optional[str] = None,
    allowed_root: Optional[PathLike] = None,
    chunk_size: Optional[int] = None,
    signature_bytes: Optional[int] = None,
) -> FileIdentityEvidence:
    """Hash one workspace file incrementally and detect its type from bytes.

    Errors are returned as structured extractor results so callers can keep
    forensic failures independent from ML inference.
    """
    started_at = perf_counter()
    extension = (
        Path(original_filename or str(file_path)).suffix.lower().lstrip(".")[:32]
        or None
    )
    normalized_declared = normalize_mime_type(declared_mime_type)

    def elapsed_ms() -> int:
        return max(0, round((perf_counter() - started_at) * 1000))

    try:
        safe_path = resolve_workspace_file(file_path, allowed_root)
        effective_chunk_size = (
            chunk_size
            if chunk_size is not None
            else _configured_int(
                "FORENSIC_HASH_CHUNK_BYTES",
                DEFAULT_HASH_CHUNK_BYTES,
                minimum=MIN_HASH_CHUNK_BYTES,
                maximum=MAX_HASH_CHUNK_BYTES,
            )
        )
        effective_signature_bytes = (
            signature_bytes
            if signature_bytes is not None
            else _configured_int(
                "FORENSIC_SIGNATURE_BYTES",
                DEFAULT_SIGNATURE_BYTES,
                minimum=MIN_SIGNATURE_BYTES,
                maximum=MAX_SIGNATURE_BYTES,
            )
        )
        if not MIN_HASH_CHUNK_BYTES <= effective_chunk_size <= MAX_HASH_CHUNK_BYTES:
            raise ValueError(
                f"chunk_size must be between {MIN_HASH_CHUNK_BYTES} and {MAX_HASH_CHUNK_BYTES}"
            )
        if not MIN_SIGNATURE_BYTES <= effective_signature_bytes <= MAX_SIGNATURE_BYTES:
            raise ValueError(
                f"signature_bytes must be between {MIN_SIGNATURE_BYTES} and {MAX_SIGNATURE_BYTES}"
            )

        digest = hashlib.sha256()
        total_bytes = 0
        header = bytearray()
        with safe_path.open("rb") as source:
            while True:
                chunk = source.read(effective_chunk_size)
                if not chunk:
                    break
                digest.update(chunk)
                total_bytes += len(chunk)
                remaining_header_bytes = effective_signature_bytes - len(header)
                if remaining_header_bytes > 0:
                    header.extend(chunk[:remaining_header_bytes])

        if total_bytes == 0:
            return FileIdentityEvidence(
                status="error",
                normalized_extension=extension,
                normalized_declared_mime_type=normalized_declared,
                error_code="empty_file",
                error_message="The forensic input file is empty.",
                processing_time_ms=elapsed_ms(),
            )

        detected_mime_type = detect_mime_type(bytes(header))
        sha256 = digest.hexdigest()
        if detected_mime_type is None:
            return FileIdentityEvidence(
                status="unsupported",
                sha256=sha256,
                file_size_bytes=total_bytes,
                normalized_extension=extension,
                normalized_declared_mime_type=normalized_declared,
                error_code="unknown_media_type",
                error_message="The file type could not be identified safely from its bytes.",
                processing_time_ms=elapsed_ms(),
            )

        findings = _type_findings(
            detected_mime_type=detected_mime_type,
            extension=extension,
            declared_mime_type=normalized_declared,
        )
        if detected_mime_type not in _SUPPORTED_MIME_TYPES:
            return FileIdentityEvidence(
                status="unsupported",
                sha256=sha256,
                file_size_bytes=total_bytes,
                detected_mime_type=detected_mime_type,
                normalized_extension=extension,
                normalized_declared_mime_type=normalized_declared,
                findings=findings,
                error_code="unsupported_media_type",
                error_message=(
                    f"Detected media type {detected_mime_type} is not supported for analysis."
                ),
                processing_time_ms=elapsed_ms(),
            )

        return FileIdentityEvidence(
            status="available",
            sha256=sha256,
            file_size_bytes=total_bytes,
            detected_mime_type=detected_mime_type,
            normalized_extension=extension,
            normalized_declared_mime_type=normalized_declared,
            findings=findings,
            processing_time_ms=elapsed_ms(),
        )
    except FileNotFoundError as exc:
        error_code = "missing_file"
        error_message = str(exc)
    except PermissionError as exc:
        error_code = "unsafe_path"
        error_message = str(exc)
    except (OSError, ValueError) as exc:
        error_code = "file_identity_error"
        error_message = str(exc)

    return FileIdentityEvidence(
        status="error",
        normalized_extension=extension,
        normalized_declared_mime_type=normalized_declared,
        error_code=error_code,
        error_message=error_message,
        processing_time_ms=elapsed_ms(),
    )

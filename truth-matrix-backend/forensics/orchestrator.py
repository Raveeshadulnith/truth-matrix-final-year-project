from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, List, Optional, TypeVar, Union

from forensics.assessment import attach_forensic_assessment
from forensics.compression import (
    CompressionExtractionResult,
    extract_compression_evidence,
)
from forensics.c2pa_verify import C2paExtractionResult, verify_c2pa
from forensics.c2pa_provenance import classify_c2pa_provenance
from forensics.fingerprints import (
    FingerprintExtractionResult,
    extract_perceptual_fingerprint,
)
from forensics.hashing import FileIdentityEvidence, extract_file_identity
from forensics.inconsistencies import deduplicate_findings
from forensics.metadata import MetadataExtractionResult, extract_metadata
from forensics.precise_location import PreciseLocation
from schemas.forensic_schema import C2paEvidence, ForensicEvidence


logger = logging.getLogger(__name__)
PathLike = Union[str, Path]
T = TypeVar("T")

DEFAULT_TOTAL_BUDGET_SECONDS = 45.0
DEFAULT_IDENTITY_BUDGET_SECONDS = 10.0
DEFAULT_METADATA_BUDGET_SECONDS = 15.0
DEFAULT_COMPRESSION_BUDGET_SECONDS = 12.0
DEFAULT_C2PA_BUDGET_SECONDS = 20.0
DEFAULT_FINGERPRINT_BUDGET_SECONDS = 20.0
MAX_BUDGET_SECONDS = 300.0
MAX_WARNINGS = 64


@dataclass(frozen=True)
class ForensicFileFacts:
    """File facts computed once and shared with every later extractor."""

    path: Path
    sha256: str
    size_bytes: int
    detected_mime_type: str


@dataclass(frozen=True)
class ForensicOrchestratorConfig:
    """Bounded extractor controls loaded once for a collection run."""

    enabled: bool
    metadata_enabled: bool
    compression_enabled: bool
    c2pa_enabled: bool
    fingerprints_enabled: bool
    total_budget_seconds: float
    identity_budget_seconds: float
    metadata_budget_seconds: float
    compression_budget_seconds: float
    c2pa_budget_seconds: float
    fingerprint_budget_seconds: float


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


def _env_budget(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not 0.01 <= value <= MAX_BUDGET_SECONDS:
        raise ValueError(f"{name} must be between 0.01 and {MAX_BUDGET_SECONDS:g}")
    return value


def load_orchestrator_config() -> ForensicOrchestratorConfig:
    """Load validated forensic controls from environment variables."""
    return ForensicOrchestratorConfig(
        enabled=_env_bool("FORENSIC_ENABLED", True),
        metadata_enabled=_env_bool("FORENSIC_METADATA_ENABLED", True),
        compression_enabled=_env_bool("FORENSIC_COMPRESSION_ENABLED", True),
        c2pa_enabled=_env_bool("FORENSIC_C2PA_ENABLED", True),
        fingerprints_enabled=_env_bool("FORENSIC_FINGERPRINTS_ENABLED", True),
        total_budget_seconds=_env_budget(
            "FORENSIC_TOTAL_BUDGET_SECONDS", DEFAULT_TOTAL_BUDGET_SECONDS
        ),
        identity_budget_seconds=_env_budget(
            "FORENSIC_IDENTITY_BUDGET_SECONDS", DEFAULT_IDENTITY_BUDGET_SECONDS
        ),
        metadata_budget_seconds=_env_budget(
            "FORENSIC_METADATA_BUDGET_SECONDS", DEFAULT_METADATA_BUDGET_SECONDS
        ),
        compression_budget_seconds=_env_budget(
            "FORENSIC_COMPRESSION_BUDGET_SECONDS",
            DEFAULT_COMPRESSION_BUDGET_SECONDS,
        ),
        c2pa_budget_seconds=_env_budget(
            "FORENSIC_C2PA_BUDGET_SECONDS", DEFAULT_C2PA_BUDGET_SECONDS
        ),
        fingerprint_budget_seconds=_env_budget(
            "FORENSIC_FINGERPRINT_BUDGET_SECONDS",
            DEFAULT_FINGERPRINT_BUDGET_SECONDS,
        ),
    )


def _log_timing(
    analysis_id: Optional[str],
    extractor: str,
    status: str,
    duration_ms: int,
) -> None:
    logger.info(
        "forensic_extractor_timing",
        extra={
            "analysis_id": analysis_id or "unassigned",
            "extractor": extractor,
            "status": status,
            "duration_ms": max(0, duration_ms),
        },
    )


def _status_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _metadata_unavailable(reason: str) -> MetadataExtractionResult:
    return MetadataExtractionResult(
        evidence={
            "status": "unavailable",
            "source_version": "metadata-v2",
            "warnings": [reason],
        },
        creation_info={},
        inconsistency_status="unavailable",
        processing_time_ms=0,
    )


def _metadata_error(reason: str) -> MetadataExtractionResult:
    result = _metadata_unavailable(reason)
    return result.model_copy(
        update={"evidence": result.evidence.model_copy(update={"status": "error"})}
    )


def _compression_unavailable(reason: str) -> CompressionExtractionResult:
    return CompressionExtractionResult(
        status="unavailable",
        warnings=[reason],
        processing_time_ms=0,
    )


def _compression_error(reason: str) -> CompressionExtractionResult:
    return CompressionExtractionResult(
        status="error", warnings=[reason], processing_time_ms=0
    )


def _fingerprint_unavailable(reason: str) -> FingerprintExtractionResult:
    return FingerprintExtractionResult(
        fingerprint={"status": "unavailable", "warnings": [reason]},
        processing_time_ms=0,
    )


def _fingerprint_error(reason: str) -> FingerprintExtractionResult:
    return FingerprintExtractionResult(
        fingerprint={"status": "error", "warnings": [reason]},
        processing_time_ms=0,
    )


def _c2pa_unavailable(reason: str) -> C2paExtractionResult:
    evidence = C2paEvidence.model_validate(
        {
            "status": "unavailable",
            "manifest_present": False,
            "validation_state": "unknown",
            "signature_state": "unknown",
            "trust_state": "not_checked",
            "warnings": [reason],
        }
    )
    evidence = evidence.model_copy(
        update={"provenance": classify_c2pa_provenance(evidence)}
    )
    return C2paExtractionResult(
        evidence=evidence,
        processing_time_ms=0,
    )


def _c2pa_error(reason: str) -> C2paExtractionResult:
    result = _c2pa_unavailable(reason)
    return result.model_copy(
        update={"evidence": result.evidence.model_copy(update={"status": "error"})}
    )


def _error_evidence(reason: str, elapsed_ms: int = 0) -> ForensicEvidence:
    evidence = ForensicEvidence(
        schema_version="1.2",
        status="error",
        file_identity_status="unavailable",
        metadata={"status": "unavailable", "warnings": [reason]},
        creation_info={},
        metadata_inconsistency_status="unavailable",
        compression_status="unavailable",
        c2pa={
            "status": "unavailable",
            "manifest_present": False,
            "validation_state": "unknown",
            "signature_state": "unknown",
            "trust_state": "not_checked",
            "warnings": [reason],
        },
        perceptual_fingerprint={"status": "unavailable", "warnings": [reason]},
        similarity_status="unavailable",
        warnings=[reason],
        processing_time_ms=max(0, elapsed_ms),
    )
    return attach_forensic_assessment(evidence)


def _run_stage(
    *,
    name: str,
    analysis_id: Optional[str],
    started_at: float,
    total_budget_seconds: float,
    stage_budget_seconds: float,
    operation: Callable[[], T],
    unavailable: Callable[[str], T],
    failed: Callable[[str], T],
    status_of: Callable[[T], str],
) -> T:
    elapsed = perf_counter() - started_at
    remaining = total_budget_seconds - elapsed
    if remaining <= 0:
        result = unavailable("The overall forensic time budget was exhausted.")
        _log_timing(analysis_id, name, status_of(result), 0)
        return result

    stage_started = perf_counter()
    try:
        result = operation()
    except Exception:
        result = failed(f"The {name} extractor failed unexpectedly.")
    duration = perf_counter() - stage_started
    duration_ms = max(0, round(duration * 1000))
    effective_budget = min(stage_budget_seconds, remaining)
    if duration > effective_budget:
        result = unavailable(f"The {name} extractor exceeded its time budget.")
    _log_timing(analysis_id, name, status_of(result), duration_ms)
    return result


def _overall_status(
    identity: FileIdentityEvidence,
    enabled_statuses: List[str],
) -> str:
    success_statuses = {"available", "not_present", "unsupported"}
    identity_has_evidence = identity.status == "available" or identity.sha256 is not None
    if not identity_has_evidence and not any(
        status in success_statuses for status in enabled_statuses
    ):
        return "unavailable"
    if identity.status == "available" and all(
        status in success_statuses for status in enabled_statuses
    ):
        return "complete"
    return "partial"


def collect_forensic_evidence(
    file_path: PathLike,
    *,
    original_filename: Optional[str] = None,
    declared_mime_type: Optional[str] = None,
    allowed_root: Optional[PathLike] = None,
    analysis_id: Optional[str] = None,
    config: Optional[ForensicOrchestratorConfig] = None,
    private_location_sink: Optional[Callable[[PreciseLocation], None]] = None,
) -> ForensicEvidence:
    """Collect versioned evidence without modifying ML labels or probabilities.

    SHA-256 and actual media type are computed exactly once. Those immutable
    file facts feed every later stage; metadata is also passed directly into
    compression analysis so ExifTool and ffprobe are not invoked twice.

    The total deadline prevents new stages from starting after exhaustion.
    Individual extractors additionally enforce their own I/O, decode, process,
    and subprocess limits; a completed stage that overruns its orchestration
    allocation is discarded as unavailable rather than reported as timely.
    """
    orchestration_started = perf_counter()
    try:
        settings = config or load_orchestrator_config()
        metadata_enabled = settings.enabled and settings.metadata_enabled
        compression_enabled = settings.enabled and settings.compression_enabled
        c2pa_enabled = settings.enabled and settings.c2pa_enabled
        fingerprints_enabled = settings.enabled and settings.fingerprints_enabled

        identity_started = perf_counter()
        identity = extract_file_identity(
            file_path,
            original_filename=original_filename,
            declared_mime_type=declared_mime_type,
            allowed_root=allowed_root,
        )
        identity_duration = perf_counter() - identity_started
        if identity_duration > min(
            settings.identity_budget_seconds,
            settings.total_budget_seconds,
        ):
            identity = identity.model_copy(
                update={
                    "status": "unavailable",
                    "warnings": [*identity.warnings, "File identity exceeded its time budget."],
                }
            )
        _log_timing(
            analysis_id,
            "identity",
            _status_value(identity.status),
            round(identity_duration * 1000),
        )

        identity_available = (
            identity.status == "available" and identity.detected_mime_type is not None
        )
        if identity_available:
            facts = ForensicFileFacts(
                path=Path(file_path),
                sha256=identity.sha256 or "",
                size_bytes=identity.file_size_bytes or 0,
                detected_mime_type=identity.detected_mime_type or "",
            )
        else:
            facts = None

        enabled_statuses: List[str] = []
        if metadata_enabled and facts:
            metadata = _run_stage(
                name="metadata",
                analysis_id=analysis_id,
                started_at=orchestration_started,
                total_budget_seconds=settings.total_budget_seconds,
                stage_budget_seconds=settings.metadata_budget_seconds,
                operation=lambda: extract_metadata(
                    facts.path,
                    detected_mime_type=facts.detected_mime_type,
                    original_filename=original_filename,
                    declared_mime_type=declared_mime_type,
                    allowed_root=allowed_root,
                ),
                unavailable=_metadata_unavailable,
                failed=_metadata_error,
                status_of=lambda item: _status_value(item.evidence.status),
            )
            enabled_statuses.append(_status_value(metadata.evidence.status))
        else:
            reason = (
                "Metadata extraction is disabled by configuration."
                if not metadata_enabled
                else "Metadata extraction was skipped because file identity was unavailable."
            )
            metadata = _metadata_unavailable(reason)

        if metadata.precise_location is not None and private_location_sink is not None:
            private_location_sink(metadata.precise_location)

        if compression_enabled and facts:
            compression = _run_stage(
                name="compression",
                analysis_id=analysis_id,
                started_at=orchestration_started,
                total_budget_seconds=settings.total_budget_seconds,
                stage_budget_seconds=settings.compression_budget_seconds,
                operation=lambda: extract_compression_evidence(
                    facts.path,
                    detected_mime_type=facts.detected_mime_type,
                    metadata=metadata.evidence,
                    creation_info=metadata.creation_info,
                    allowed_root=allowed_root,
                ),
                unavailable=_compression_unavailable,
                failed=_compression_error,
                status_of=lambda item: _status_value(item.status),
            )
            enabled_statuses.append(_status_value(compression.status))
        else:
            reason = (
                "Compression extraction is disabled by configuration."
                if not compression_enabled
                else "Compression extraction was skipped because file identity was unavailable."
            )
            compression = _compression_unavailable(reason)

        if fingerprints_enabled and facts:
            fingerprint = _run_stage(
                name="fingerprint",
                analysis_id=analysis_id,
                started_at=orchestration_started,
                total_budget_seconds=settings.total_budget_seconds,
                stage_budget_seconds=settings.fingerprint_budget_seconds,
                operation=lambda: extract_perceptual_fingerprint(
                    facts.path,
                    detected_mime_type=facts.detected_mime_type,
                    allowed_root=allowed_root,
                ),
                unavailable=_fingerprint_unavailable,
                failed=_fingerprint_error,
                status_of=lambda item: _status_value(item.fingerprint.status),
            )
            enabled_statuses.append(_status_value(fingerprint.fingerprint.status))
        else:
            reason = (
                "Perceptual fingerprinting is disabled by configuration."
                if not fingerprints_enabled
                else "Perceptual fingerprinting was skipped because file identity was unavailable."
            )
            fingerprint = _fingerprint_unavailable(reason)

        if c2pa_enabled and facts:
            c2pa = _run_stage(
                name="c2pa",
                analysis_id=analysis_id,
                started_at=orchestration_started,
                total_budget_seconds=settings.total_budget_seconds,
                stage_budget_seconds=settings.c2pa_budget_seconds,
                operation=lambda: verify_c2pa(
                    facts.path,
                    detected_mime_type=facts.detected_mime_type,
                    allowed_root=allowed_root,
                ),
                unavailable=_c2pa_unavailable,
                failed=_c2pa_error,
                status_of=lambda item: _status_value(item.evidence.status),
            )
            enabled_statuses.append(_status_value(c2pa.evidence.status))
        else:
            reason = (
                "C2PA verification is disabled by configuration."
                if not c2pa_enabled
                else "C2PA verification was skipped because file identity was unavailable."
            )
            c2pa = _c2pa_unavailable(reason)

        warnings: List[str] = list(identity.warnings)
        if identity.error_message:
            warnings.append(identity.error_message)
        warnings.extend(metadata.evidence.warnings)
        warnings.extend(compression.warnings)
        warnings.extend(fingerprint.fingerprint.warnings)
        warnings.extend(c2pa.evidence.warnings)
        warnings = list(dict.fromkeys(warnings))[:MAX_WARNINGS]

        evidence = ForensicEvidence(
            schema_version="1.2",
            status=_overall_status(identity, enabled_statuses),
            file_identity_status=identity.status,
            original_filename=Path(original_filename).name if original_filename else None,
            sha256=identity.sha256,
            file_size_bytes=identity.file_size_bytes,
            detected_mime_type=identity.detected_mime_type,
            metadata=metadata.evidence,
            creation_info=metadata.creation_info,
            metadata_inconsistency_status=(
                metadata.inconsistency_status if identity_available else identity.status
            ),
            metadata_inconsistencies=deduplicate_findings(
                [*identity.findings, *metadata.findings]
            ),
            compression_status=compression.status,
            compression_indicators=compression.indicators,
            c2pa=c2pa.evidence,
            perceptual_fingerprint=fingerprint.fingerprint,
            similarity_status="unavailable",
            warnings=warnings,
            processing_time_ms=max(
                0, round((perf_counter() - orchestration_started) * 1000)
            ),
        )
        return attach_forensic_assessment(evidence)
    except Exception:
        duration_ms = max(0, round((perf_counter() - orchestration_started) * 1000))
        _log_timing(analysis_id, "orchestrator", "error", duration_ms)
        return _error_evidence(
            "Forensic evidence orchestration failed unexpectedly.", duration_ms
        )

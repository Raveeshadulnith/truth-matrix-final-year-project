from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Any, Dict, List, Literal, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field

from forensics.assessment import attach_forensic_assessment
from forensics.fingerprints import (
    AUDIO_ALGORITHM,
    AUDIO_VERSION,
    PHASH_ALGORITHM,
    PHASH_VERSION,
    VIDEO_ALGORITHM,
    VIDEO_VERSION,
    FingerprintSimilarityResult,
    compare_audio_fingerprints,
    compare_image_phash,
    compare_video_fingerprints,
)
from schemas.forensic_schema import (
    ExtractorStatus,
    ForensicEvidence,
    OverallForensicStatus,
    PerceptualFingerprint,
    SimilarityMatch,
)


DEFAULT_CANDIDATE_LIMIT = 100
DEFAULT_EXACT_CANDIDATE_LIMIT = 25
DEFAULT_MATCH_LIMIT = 5
DEFAULT_WINDOW_DAYS = 3650
MAX_CANDIDATE_LIMIT = 500
MAX_MATCH_LIMIT = 25
MAX_WARNINGS = 64
_SUPPORTED_MEDIA = {"image", "video", "audio"}
_SUPPORTED_FINGERPRINTS = {
    "image": (PHASH_ALGORITHM, PHASH_VERSION),
    "video": (VIDEO_ALGORITHM, VIDEO_VERSION),
    "audio": (AUDIO_ALGORITHM, AUDIO_VERSION),
}
_HISTORY_ONLY_WARNING = "Stored-history similarity extraction is not enabled yet."


class SimilaritySearchResult(BaseModel):
    """Internal outcome for one authenticated, bounded history search."""

    model_config = ConfigDict(extra="forbid")

    status: ExtractorStatus
    matches: List[SimilarityMatch] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    processing_time_ms: int = Field(default=0, ge=0)
    affects_overall_status: bool = False


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


def _algorithm_key(fingerprint: PerceptualFingerprint) -> Optional[str]:
    if not fingerprint.algorithm or not fingerprint.algorithm_version:
        return None
    return f"{fingerprint.algorithm}@{fingerprint.algorithm_version}"


def _candidate_identity(
    candidate: Dict[str, Any],
    *,
    user_id: str,
    media_type: str,
    current_analysis_id: str,
) -> Optional[tuple[str, str, str]]:
    """Return safe public identity fields after redundant ownership checks."""
    analysis_id = candidate.get("id")
    created_at = candidate.get("created_at")
    if (
        candidate.get("user_id") != user_id
        or candidate.get("media_type") != media_type
        or not isinstance(analysis_id, str)
        or not analysis_id
        or analysis_id == current_analysis_id
        or not isinstance(created_at, str)
        or not created_at
    ):
        return None
    filename = candidate.get("original_filename")
    safe_filename = filename if isinstance(filename, str) and filename else "Unnamed media"
    return analysis_id, safe_filename, created_at


def _candidate_fingerprint(candidate: Dict[str, Any]) -> Optional[PerceptualFingerprint]:
    evidence = candidate.get("forensic_evidence")
    if not isinstance(evidence, dict):
        return None
    raw_fingerprint = evidence.get("perceptual_fingerprint")
    if not isinstance(raw_fingerprint, dict):
        return None
    try:
        fingerprint = PerceptualFingerprint.model_validate(raw_fingerprint)
    except (TypeError, ValueError):
        return None
    if fingerprint.status != ExtractorStatus.AVAILABLE:
        return None
    return fingerprint


def _compare_fingerprints(
    media_type: Literal["image", "video", "audio"],
    current: PerceptualFingerprint,
    candidate: PerceptualFingerprint,
) -> Optional[FingerprintSimilarityResult]:
    expected = _SUPPORTED_FINGERPRINTS[media_type]
    if (
        (current.algorithm, current.algorithm_version) != expected
        or (candidate.algorithm, candidate.algorithm_version) != expected
    ):
        return None
    if media_type == "image":
        if not current.value or not candidate.value:
            return None
        return compare_image_phash(current.value, candidate.value)
    if media_type == "video":
        return compare_video_fingerprints(current, candidate)
    return compare_audio_fingerprints(current, candidate)


def _near_match_details(result: FingerprintSimilarityResult) -> Dict[str, Any]:
    details: Dict[str, Any] = {
        "method": result.method,
        "threshold": result.threshold,
        "limitations": result.limitations,
    }
    if result.matched_components is not None:
        details["matched_components"] = result.matched_components
    if result.overlap_ratio is not None:
        details["overlap_ratio"] = result.overlap_ratio
    return details


def match_similarity_candidates(
    *,
    user_id: str,
    current_analysis_id: str,
    media_type: Literal["image", "video", "audio"],
    sha256: Optional[str],
    fingerprint: PerceptualFingerprint,
    exact_candidates: Sequence[Dict[str, Any]],
    near_candidates: Sequence[Dict[str, Any]],
    max_matches: int = DEFAULT_MATCH_LIMIT,
) -> List[SimilarityMatch]:
    """Rank safe exact and compatible near matches from bounded candidates.

    The current analysis is always excluded, even when a caller accidentally
    returns it. Exact matches take precedence and suppress a duplicate near
    match for the same historical analysis.
    """
    if media_type not in _SUPPORTED_MEDIA:
        raise ValueError("media_type must be image, video, or audio")
    bounded_match_count = min(max(max_matches, 1), MAX_MATCH_LIMIT)
    matches: List[SimilarityMatch] = []
    matched_ids: set[str] = set()

    if sha256:
        for candidate in exact_candidates[:MAX_CANDIDATE_LIMIT]:
            identity = _candidate_identity(
                candidate,
                user_id=user_id,
                media_type=media_type,
                current_analysis_id=current_analysis_id,
            )
            if identity is None or candidate.get("sha256") != sha256:
                continue
            analysis_id, filename, created_at = identity
            if analysis_id in matched_ids:
                continue
            matches.append(
                SimilarityMatch(
                    analysis_id=analysis_id,
                    filename=filename,
                    created_at=created_at,
                    match_type="exact",
                    similarity_score=1.0,
                    distance=0.0,
                    details={
                        "method": "sha256-equality",
                        "limitations": [
                            "An exact byte match does not establish authorship or ownership."
                        ],
                    },
                    algorithm="sha256",
                )
            )
            matched_ids.add(analysis_id)

    current_key = _algorithm_key(fingerprint)
    if fingerprint.status == ExtractorStatus.AVAILABLE and current_key:
        for candidate in near_candidates[:MAX_CANDIDATE_LIMIT]:
            identity = _candidate_identity(
                candidate,
                user_id=user_id,
                media_type=media_type,
                current_analysis_id=current_analysis_id,
            )
            if identity is None:
                continue
            analysis_id, filename, created_at = identity
            if analysis_id in matched_ids or candidate.get("fingerprint_algorithm") != current_key:
                continue
            candidate_fingerprint = _candidate_fingerprint(candidate)
            if candidate_fingerprint is None or _algorithm_key(candidate_fingerprint) != current_key:
                continue
            try:
                comparison = _compare_fingerprints(
                    media_type, fingerprint, candidate_fingerprint
                )
            except (TypeError, ValueError):
                continue
            if comparison is None or not comparison.is_similar:
                continue
            matches.append(
                SimilarityMatch(
                    analysis_id=analysis_id,
                    filename=filename,
                    created_at=created_at,
                    match_type="near",
                    similarity_score=comparison.similarity_score,
                    distance=comparison.distance,
                    details=_near_match_details(comparison),
                    algorithm=fingerprint.algorithm or "unknown",
                    algorithm_version=fingerprint.algorithm_version,
                )
            )
            matched_ids.add(analysis_id)

    matches.sort(
        key=lambda match: (
            0 if match.match_type.value == "exact" else 1,
            -match.similarity_score,
        )
    )
    return matches[:bounded_match_count]


def search_user_similarity_matches(
    *,
    user_id: str,
    current_analysis_id: str,
    media_type: Literal["image", "video", "audio"],
    evidence: ForensicEvidence,
) -> SimilaritySearchResult:
    """Query one user's bounded history and run compatible local comparators."""
    started_at = perf_counter()

    def elapsed_ms() -> int:
        return max(0, round((perf_counter() - started_at) * 1000))

    try:
        if not _env_bool("FORENSIC_SIMILARITY_ENABLED", True):
            return SimilaritySearchResult(
                status="unavailable",
                warnings=["Authenticated history similarity search is disabled."],
                processing_time_ms=elapsed_ms(),
            )
        candidate_limit = _env_int(
            "FORENSIC_SIMILARITY_MAX_CANDIDATES",
            DEFAULT_CANDIDATE_LIMIT,
            1,
            MAX_CANDIDATE_LIMIT,
        )
        exact_limit = _env_int(
            "FORENSIC_SIMILARITY_MAX_EXACT_CANDIDATES",
            DEFAULT_EXACT_CANDIDATE_LIMIT,
            1,
            100,
        )
        match_limit = _env_int(
            "FORENSIC_SIMILARITY_MAX_MATCHES",
            DEFAULT_MATCH_LIMIT,
            1,
            MAX_MATCH_LIMIT,
        )
        window_days = _env_int(
            "FORENSIC_SIMILARITY_WINDOW_DAYS",
            DEFAULT_WINDOW_DAYS,
            1,
            36_500,
        )
        created_after = (
            datetime.now(timezone.utc) - timedelta(days=window_days)
        ).isoformat()

        from services.supabase_service import (
            get_user_analysis_results_by_sha256,
            get_user_similarity_candidates,
        )

        exact_candidates: List[Dict[str, Any]] = []
        near_candidates: List[Dict[str, Any]] = []
        warnings: List[str] = []
        attempted_queries = 0
        successful_queries = 0

        if evidence.sha256:
            attempted_queries += 1
            try:
                exact_candidates = get_user_analysis_results_by_sha256(
                    user_id,
                    evidence.sha256,
                    exact_limit,
                    media_type=media_type,
                    created_after=created_after,
                    exclude_analysis_id=current_analysis_id,
                )
                successful_queries += 1
            except Exception:
                warnings.append("Exact duplicate history lookup was unavailable.")

        fingerprint_key = _algorithm_key(evidence.perceptual_fingerprint)
        if (
            evidence.perceptual_fingerprint.status == ExtractorStatus.AVAILABLE
            and fingerprint_key
        ):
            attempted_queries += 1
            try:
                near_candidates = get_user_similarity_candidates(
                    user_id,
                    media_type,
                    fingerprint_key,
                    created_after,
                    candidate_limit,
                    exclude_analysis_id=current_analysis_id,
                )
                successful_queries += 1
            except Exception:
                warnings.append("Near-duplicate history lookup was unavailable.")

        if attempted_queries == 0:
            return SimilaritySearchResult(
                status="unavailable",
                warnings=["No integrity hash or compatible perceptual fingerprint was available."],
                processing_time_ms=elapsed_ms(),
            )
        if successful_queries == 0:
            return SimilaritySearchResult(
                status="error",
                warnings=warnings,
                processing_time_ms=elapsed_ms(),
                affects_overall_status=True,
            )

        matches = match_similarity_candidates(
            user_id=user_id,
            current_analysis_id=current_analysis_id,
            media_type=media_type,
            sha256=evidence.sha256,
            fingerprint=evidence.perceptual_fingerprint,
            exact_candidates=exact_candidates,
            near_candidates=near_candidates,
            max_matches=match_limit,
        )
        return SimilaritySearchResult(
            status="available",
            matches=matches,
            warnings=warnings,
            processing_time_ms=elapsed_ms(),
            affects_overall_status=bool(warnings),
        )
    except Exception:
        return SimilaritySearchResult(
            status="error",
            warnings=["Authenticated history similarity search failed."],
            processing_time_ms=elapsed_ms(),
            affects_overall_status=True,
        )


def attach_similarity_result(
    evidence: ForensicEvidence,
    result: SimilaritySearchResult,
) -> ForensicEvidence:
    """Attach history matches without changing any ML prediction fields."""
    warnings = [warning for warning in evidence.warnings if warning != _HISTORY_ONLY_WARNING]
    warnings.extend(result.warnings)
    warnings = list(dict.fromkeys(warnings))[:MAX_WARNINGS]
    overall_status = evidence.status
    if result.affects_overall_status and overall_status == OverallForensicStatus.COMPLETE:
        overall_status = OverallForensicStatus.PARTIAL
    updated_evidence = evidence.model_copy(
        update={
            "status": overall_status,
            "similarity_status": result.status,
            "similarity_matches": result.matches,
            "warnings": warnings,
            "processing_time_ms": evidence.processing_time_ms
            + result.processing_time_ms,
        }
    )
    return attach_forensic_assessment(updated_evidence)

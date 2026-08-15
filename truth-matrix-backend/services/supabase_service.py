import os
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

_service_client: Optional[Client] = None
_auth_client: Optional[Client] = None

_FORENSIC_RESULT_COLUMNS = (
    "sha256",
    "perceptual_fingerprint",
    "fingerprint_algorithm",
    "forensic_evidence",
    "forensic_schema_version",
)
_MODEL_RESULT_COLUMNS = (
    "fake_probability",
    "authentic_probability",
    "model_version",
)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_MEDIA_TYPES = {"image", "video", "audio"}
_SIMILARITY_SELECT_COLUMNS = (
    "id,user_id,media_type,original_filename,created_at,sha256,"
    "perceptual_fingerprint,fingerprint_algorithm,forensic_evidence"
)


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is missing in backend .env")
    return value


def get_supabase_service_client() -> Client:
    """Service role client for trusted backend database operations only."""
    global _service_client
    if _service_client is None:
        _service_client = create_client(
            _require_env("SUPABASE_URL"),
            _require_env("SUPABASE_SERVICE_ROLE_KEY"),
        )
    return _service_client


def get_supabase_auth_client() -> Client:
    """Anon client for normal Supabase Auth signup/login calls."""
    global _auth_client
    if _auth_client is None:
        _auth_client = create_client(
            _require_env("SUPABASE_URL"),
            _require_env("SUPABASE_ANON_KEY"),
        )
    return _auth_client


def _single_response_data(response: Any) -> Optional[Dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, list):
        return data[0] if data else None
    return data


def _map_analysis_result(record: Dict[str, Any]) -> Dict[str, Any]:
    """Copy a Supabase row and supply null additive fields for legacy rows."""
    mapped = dict(record)
    for column in (*_FORENSIC_RESULT_COLUMNS, *_MODEL_RESULT_COLUMNS):
        mapped.setdefault(column, None)
    forensic_evidence = mapped.get("forensic_evidence")
    alignment = None
    if isinstance(forensic_evidence, dict):
        assessment = forensic_evidence.get("assessment")
        if isinstance(assessment, dict):
            candidate = assessment.get("model_alignment")
            if isinstance(candidate, dict):
                alignment = candidate
    mapped["model_forensic_alignment"] = alignment
    return mapped


def _map_analysis_results(records: Any) -> List[Dict[str, Any]]:
    """Map a possibly empty Supabase result list without changing nested JSON."""
    if not isinstance(records, list):
        return []
    return [_map_analysis_result(record) for record in records if isinstance(record, dict)]


def _bounded_analysis_limit(limit: int) -> int:
    """Keep every analysis-results query within the API's documented bound."""
    return min(max(limit, 1), 100)


def _bounded_similarity_candidate_limit(limit: int) -> int:
    """Keep application-level perceptual comparison candidate sets bounded."""
    return min(max(limit, 1), 500)


def _validate_media_type(media_type: str) -> str:
    """Validate the fixed media category used by similarity queries."""
    if media_type not in _MEDIA_TYPES:
        raise ValueError("media_type must be image, video, or audio")
    return media_type


def _validate_fingerprint_algorithm(fingerprint_algorithm: str) -> str:
    """Validate the backend-derived algorithm/version comparison key."""
    if not fingerprint_algorithm or len(fingerprint_algorithm) > 128:
        raise ValueError("fingerprint_algorithm must contain 1 to 128 characters")
    return fingerprint_algorithm


def _validate_sha256(sha256: str) -> str:
    """Validate the canonical lowercase SHA-256 representation used in storage."""
    if not _SHA256_PATTERN.fullmatch(sha256):
        raise ValueError("sha256 must contain 64 lowercase hexadecimal characters")
    return sha256


def get_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
    response = (
        get_supabase_service_client()
        .table("user_profiles")
        .select("*")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    return _single_response_data(response)


def upsert_user_profile(
    *,
    user_id: str,
    email: Optional[str],
    full_name: Optional[str] = None,
    avatar_url: Optional[str] = None,
) -> Dict[str, Any]:
    data = {
        "id": user_id,
        "email": email,
    }

    if full_name is not None:
        data["full_name"] = full_name
    if avatar_url is not None:
        data["avatar_url"] = avatar_url

    response = (
        get_supabase_service_client()
        .table("user_profiles")
        .upsert(data, on_conflict="id")
        .execute()
    )
    saved = _single_response_data(response)
    if not saved:
        raise RuntimeError("Supabase did not return the saved user profile")
    return saved


def update_user_profile(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = {key: value for key, value in data.items() if value is not None}
    if not cleaned:
        profile = get_user_profile(user_id)
        if not profile:
            raise RuntimeError("User profile was not found")
        return profile

    response = (
        get_supabase_service_client()
        .table("user_profiles")
        .update(cleaned)
        .eq("id", user_id)
        .execute()
    )
    updated = _single_response_data(response)
    if not updated:
        raise RuntimeError("Supabase did not return the updated user profile")
    return updated


def save_analysis_result(data: Dict[str, Any]) -> Dict[str, Any]:
    """Insert one backend-derived analysis record and map forensic nulls."""
    response = (
        get_supabase_service_client()
        .table("analysis_results")
        .insert(data)
        .execute()
    )
    saved = _single_response_data(response)
    if not saved:
        raise RuntimeError("Supabase did not return the saved analysis result")
    return _map_analysis_result(saved)


def save_sensitive_location(
    *,
    analysis_id: str,
    user_id: str,
    encrypted_payload: str,
    encryption_version: str,
) -> None:
    """Upsert coordinates encrypted and derived by the trusted backend."""
    if not encrypted_payload or len(encrypted_payload) > 8192:
        raise ValueError("encrypted location payload has an invalid size")
    get_supabase_service_client().table("analysis_sensitive_location").upsert(
        {
            "analysis_id": analysis_id,
            "user_id": user_id,
            "encrypted_payload": encrypted_payload,
            "encryption_version": encryption_version,
        },
        on_conflict="analysis_id",
    ).execute()


def get_owned_sensitive_location(
    analysis_id: str,
    user_id: str,
) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Return an owner-verified analysis and its private location row, if any."""
    analysis = get_analysis_result_by_id(analysis_id, user_id)
    if not analysis:
        return None, None
    response = (
        get_supabase_service_client()
        .table("analysis_sensitive_location")
        .select("analysis_id,user_id,encrypted_payload,encryption_version")
        .eq("analysis_id", analysis_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return analysis, _single_response_data(response)


def get_sensitive_location_record(
    analysis_id: str,
    user_id: str,
) -> Optional[Dict[str, Any]]:
    """Read one private row using both its analysis ID and authenticated owner."""
    response = (
        get_supabase_service_client()
        .table("analysis_sensitive_location")
        .select("analysis_id,user_id,encrypted_payload,encryption_version")
        .eq("analysis_id", analysis_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return _single_response_data(response)


def get_user_analysis_results(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Return a bounded newest-first history for one authenticated user."""
    response = (
        get_supabase_service_client()
        .table("analysis_results")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(_bounded_analysis_limit(limit))
        .execute()
    )
    return _map_analysis_results(getattr(response, "data", None))


def get_user_analysis_results_by_sha256(
    user_id: str,
    sha256: str,
    limit: int = 25,
    *,
    media_type: Optional[str] = None,
    created_after: Optional[str] = None,
    exclude_analysis_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Find exact hashes in one user's bounded, optionally filtered history."""
    canonical_sha256 = _validate_sha256(sha256)
    query = (
        get_supabase_service_client()
        .table("analysis_results")
        .select(_SIMILARITY_SELECT_COLUMNS)
        .eq("user_id", user_id)
        .eq("sha256", canonical_sha256)
    )
    if media_type is not None:
        query = query.eq("media_type", _validate_media_type(media_type))
    if created_after is not None:
        query = query.gte("created_at", created_after)
    if exclude_analysis_id is not None:
        query = query.neq("id", exclude_analysis_id)
    response = (
        query.order("created_at", desc=True)
        .limit(_bounded_analysis_limit(limit))
        .execute()
    )
    return _map_analysis_results(getattr(response, "data", None))


def get_user_similarity_candidates(
    user_id: str,
    media_type: str,
    fingerprint_algorithm: str,
    created_after: str,
    limit: int = 100,
    *,
    exclude_analysis_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return bounded compatible candidates for application-level comparison.

    The database query performs no perceptual-distance calculation. It only
    narrows by owner, media category, exact algorithm/version key, time window,
    and count before the documented media-specific comparator runs.
    """
    query = (
        get_supabase_service_client()
        .table("analysis_results")
        .select(_SIMILARITY_SELECT_COLUMNS)
        .eq("user_id", user_id)
        .eq("media_type", _validate_media_type(media_type))
        .eq(
            "fingerprint_algorithm",
            _validate_fingerprint_algorithm(fingerprint_algorithm),
        )
        .gte("created_at", created_after)
    )
    if exclude_analysis_id is not None:
        query = query.neq("id", exclude_analysis_id)
    response = (
        query.order("created_at", desc=True)
        .limit(_bounded_similarity_candidate_limit(limit))
        .execute()
    )
    return _map_analysis_results(getattr(response, "data", None))


def get_analysis_result_by_id(result_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """Return one analysis only when it belongs to the authenticated user."""
    response = (
        get_supabase_service_client()
        .table("analysis_results")
        .select("*")
        .eq("id", result_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    result = _single_response_data(response)
    return _map_analysis_result(result) if result else None


def delete_analysis_result(result_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """Delete one user-owned analysis and return its mapped previous value."""
    existing = get_analysis_result_by_id(result_id, user_id)
    if not existing:
        return None

    get_supabase_service_client().table("analysis_results").delete().eq(
        "id", result_id
    ).eq("user_id", user_id).execute()
    return existing

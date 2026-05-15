import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

_service_client: Optional[Client] = None
_auth_client: Optional[Client] = None


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
    response = (
        get_supabase_service_client()
        .table("analysis_results")
        .insert(data)
        .execute()
    )
    saved = _single_response_data(response)
    if not saved:
        raise RuntimeError("Supabase did not return the saved analysis result")
    return saved


def get_user_analysis_results(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    response = (
        get_supabase_service_client()
        .table("analysis_results")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return getattr(response, "data", []) or []


def get_analysis_result_by_id(result_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    response = (
        get_supabase_service_client()
        .table("analysis_results")
        .select("*")
        .eq("id", result_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return _single_response_data(response)


def delete_analysis_result(result_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    existing = get_analysis_result_by_id(result_id, user_id)
    if not existing:
        return None

    get_supabase_service_client().table("analysis_results").delete().eq(
        "id", result_id
    ).eq("user_id", user_id).execute()
    return existing

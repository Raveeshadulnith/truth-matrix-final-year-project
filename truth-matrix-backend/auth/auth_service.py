import os
from typing import Any, Dict, Optional

from services.supabase_service import (
    get_supabase_auth_client,
    get_user_profile,
    upsert_user_profile,
)


def _user_to_dict(user: Any) -> Dict[str, Any]:
    if user is None:
        return {}
    if hasattr(user, "model_dump"):
        return user.model_dump()
    if hasattr(user, "dict"):
        return user.dict()
    if isinstance(user, dict):
        return user
    return {
        "id": getattr(user, "id", None),
        "email": getattr(user, "email", None),
        "user_metadata": getattr(user, "user_metadata", None),
    }


def _session_tokens(session: Any) -> Dict[str, Optional[str]]:
    if session is None:
        return {"access_token": None, "refresh_token": None}
    return {
        "access_token": getattr(session, "access_token", None),
        "refresh_token": getattr(session, "refresh_token", None),
    }


def _metadata_full_name(user: Dict[str, Any]) -> Optional[str]:
    metadata = user.get("user_metadata") or {}
    if isinstance(metadata, dict):
        full_name = metadata.get("full_name")
        if isinstance(full_name, str) and full_name.strip():
            return full_name.strip()
    return None


def _attach_profile(user: Dict[str, Any], full_name: Optional[str] = None) -> Dict[str, Any]:
    user_id = user.get("id")
    if not user_id:
        return user

    email = user.get("email")
    profile = get_user_profile(user_id)

    if not profile:
        profile = upsert_user_profile(
            user_id=user_id,
            email=email,
            full_name=full_name or _metadata_full_name(user),
        )

    user["profile"] = profile
    return user


def _auth_response(response: Any, full_name: Optional[str] = None) -> Dict[str, Any]:
    tokens = _session_tokens(getattr(response, "session", None))
    user = _user_to_dict(getattr(response, "user", None))
    return {
        **tokens,
        "user": _attach_profile(user, full_name),
    }


def signup_user(full_name: str, email: str, password: str) -> Dict[str, Any]:
    response = get_supabase_auth_client().auth.sign_up(
        {
            "email": email,
            "password": password,
            "options": {
                "data": {
                    "full_name": full_name,
                }
            },
        }
    )

    return _auth_response(response, full_name)


def login_user(email: str, password: str) -> Dict[str, Any]:
    response = get_supabase_auth_client().auth.sign_in_with_password(
        {
            "email": email,
            "password": password,
        }
    )

    return _auth_response(response)


def refresh_user_session(refresh_token: str) -> Dict[str, Any]:
    response = get_supabase_auth_client().auth.refresh_session(refresh_token)
    return _auth_response(response)


def send_password_reset(email: str) -> None:
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    get_supabase_auth_client().auth.reset_password_for_email(
        email,
        {
            "redirect_to": f"{frontend_url}/reset-password",
        },
    )


def get_user_from_token(token: str) -> Dict[str, Any]:
    response = get_supabase_auth_client().auth.get_user(token)
    return _user_to_dict(getattr(response, "user", None))

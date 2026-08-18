import os
from typing import Any, Dict, Optional

import requests

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
    """Create the confirmed Supabase identity only after application OTP proof."""
    from services.supabase_service import get_supabase_service_client

    response = get_supabase_service_client().auth.admin.create_user(
        {
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {"full_name": full_name},
        }
    )
    return {"user": _attach_profile(_user_to_dict(getattr(response, "user", None)), full_name)}


def login_user(email: str, password: str) -> Dict[str, Any]:
    response = get_supabase_auth_client().auth.sign_in_with_password(
        {
            "email": email,
            "password": password,
        }
    )

    return _auth_response(response)


def confirm_user_email(user_id: str) -> Dict[str, Any]:
    from services.supabase_service import get_supabase_service_client

    response = get_supabase_service_client().auth.admin.update_user_by_id(
        user_id, {"email_confirm": True}
    )
    return _user_to_dict(getattr(response, "user", None))


def get_admin_user(user_id: str) -> Dict[str, Any]:
    from services.supabase_service import get_supabase_service_client

    response = get_supabase_service_client().auth.admin.get_user_by_id(user_id)
    return _user_to_dict(getattr(response, "user", None))


def delete_admin_user(user_id: str) -> None:
    from services.supabase_service import get_supabase_service_client

    get_supabase_service_client().auth.admin.delete_user(user_id)


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


def sign_out_user(access_token: str) -> None:
    """Revoke the Supabase refresh session; app registry handles JWT replay."""
    from services.supabase_service import _require_env

    response = requests.post(
        f"{_require_env('SUPABASE_URL').rstrip('/')}/auth/v1/logout?scope=local",
        headers={
            "apikey": _require_env("SUPABASE_ANON_KEY"),
            "Authorization": f"Bearer {access_token}",
        },
        timeout=5,
    )
    response.raise_for_status()

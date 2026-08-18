import hmac
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

from services.supabase_service import get_supabase_service_client


def _data(response: Any) -> Any:
    return getattr(response, "data", None)


def _one(response: Any) -> Optional[Dict[str, Any]]:
    data = _data(response)
    if isinstance(data, list):
        return data[0] if data else None
    return data if isinstance(data, dict) else None


def create_challenge(payload: Dict[str, Any]) -> Dict[str, Any]:
    row = _one(get_supabase_service_client().rpc("create_auth_challenge", payload).execute())
    if not row:
        raise RuntimeError("Could not create authentication challenge")
    return row


def replace_challenge(payload: Dict[str, Any]) -> Dict[str, Any]:
    row = _one(get_supabase_service_client().rpc("replace_auth_challenge", payload).execute())
    if not row:
        raise RuntimeError("Challenge resend is unavailable")
    return row


def consume_challenge(challenge_id: str, digest: str) -> Dict[str, Any]:
    current = _one(
        get_supabase_service_client()
        .table("auth_challenges")
        .select("otp_digest")
        .eq("id", challenge_id)
        .maybe_single()
        .execute()
    )
    expected_digest = str((current or {}).get("otp_digest") or "")
    digest_valid = bool(expected_digest) and hmac.compare_digest(expected_digest, digest)
    row = _one(
        get_supabase_service_client().rpc(
            "consume_auth_challenge",
            {
                "p_challenge_id": challenge_id,
                "p_expected_digest": expected_digest,
                "p_digest_valid": digest_valid,
            },
        ).execute()
    )
    return row or {"status": "invalid"}


def get_challenge(challenge_id: str) -> Optional[Dict[str, Any]]:
    return _one(
        get_supabase_service_client()
        .table("auth_challenges")
        .select("id,user_id,purpose,email_hash,expires_at,resend_count,last_sent_at,consumed_at,revoked_at")
        .eq("id", challenge_id)
        .maybe_single()
        .execute()
    )


def revoke_challenge(challenge_id: str) -> None:
    (
        get_supabase_service_client()
        .table("auth_challenges")
        .update({"revoked_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", challenge_id)
        .is_("consumed_at", "null")
        .is_("revoked_at", "null")
        .execute()
    )


def register_session(payload: Dict[str, Any]) -> None:
    get_supabase_service_client().rpc("register_app_session", payload).execute()


def validate_and_touch_session(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _one(get_supabase_service_client().rpc("validate_and_touch_app_session", payload).execute()) or {
        "status": "invalid"
    }


def validate_refresh_session(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _one(get_supabase_service_client().rpc("validate_app_refresh_session", payload).execute()) or {
        "status": "invalid"
    }


def rotate_refresh_session(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _one(get_supabase_service_client().rpc("rotate_app_refresh_session", payload).execute()) or {
        "status": "invalid"
    }


def revoke_session_by_refresh(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _one(get_supabase_service_client().rpc("revoke_app_session_by_refresh", payload).execute()) or {
        "status": "invalid"
    }


def revoke_session(session_digest: str, user_id: str, reason: str) -> None:
    (
        get_supabase_service_client()
        .table("app_sessions")
        .update({"revoked_at": datetime.now(timezone.utc).isoformat(), "revocation_reason": reason[:64]})
        .eq("session_digest", session_digest)
        .eq("user_id", user_id)
        .is_("revoked_at", "null")
        .execute()
    )


def revoke_other_sessions(user_id: str, current_session_digest: str, reason: str) -> None:
    (
        get_supabase_service_client()
        .table("app_sessions")
        .update({"revoked_at": datetime.now(timezone.utc).isoformat(), "revocation_reason": reason[:64]})
        .eq("user_id", user_id)
        .neq("session_digest", current_session_digest)
        .is_("revoked_at", "null")
        .execute()
    )


def downgrade_session_assurance(session_digest: str, user_id: str) -> None:
    (
        get_supabase_service_client()
        .table("app_sessions")
        .update({"mfa_verified_at": None})
        .eq("session_digest", session_digest)
        .eq("user_id", user_id)
        .is_("revoked_at", "null")
        .execute()
    )


def risk_status(risk_keys: Iterable[str], window_seconds: int) -> Dict[str, Any]:
    result = _one(
        get_supabase_service_client().rpc(
            "get_auth_risk_status", {"p_risk_keys": list(risk_keys), "p_window_seconds": window_seconds}
        ).execute()
    )
    return result or {"failure_count": 0, "captcha_required": False, "blocked": False}


def record_login_failure(risk_keys: Iterable[str], window_seconds: int, captcha_threshold: int, rate_limit: int) -> Dict[str, Any]:
    result = _one(
        get_supabase_service_client().rpc(
            "record_auth_failure",
            {
                "p_risk_keys": list(risk_keys),
                "p_window_seconds": window_seconds,
                "p_captcha_threshold": captcha_threshold,
                "p_rate_limit": rate_limit,
            },
        ).execute()
    )
    return result or {"failure_count": 1, "captcha_required": False, "blocked": False}


def clear_login_failures(risk_keys: Iterable[str]) -> None:
    get_supabase_service_client().table("auth_risk_state").delete().in_("risk_key", list(risk_keys)).execute()


def get_security_settings(user_id: str) -> Dict[str, Any]:
    row = _one(
        get_supabase_service_client().table("user_security_settings").select("*").eq("user_id", user_id).maybe_single().execute()
    )
    if row:
        return row
    payload = {"user_id": user_id, "mfa_enabled": True}
    return _one(get_supabase_service_client().table("user_security_settings").insert(payload).execute()) or payload


def set_mfa_verified(user_id: str, enabled: bool = True) -> None:
    values = {"mfa_enabled": enabled, "updated_at": datetime.now(timezone.utc).isoformat()}
    if enabled:
        values["mfa_enrolled_at"] = datetime.now(timezone.utc).isoformat()
    get_supabase_service_client().table("user_security_settings").upsert({"user_id": user_id, **values}).execute()


def create_step_up_authorization(payload: Dict[str, Any]) -> None:
    get_supabase_service_client().table("step_up_authorizations").insert(payload).execute()


def consume_step_up(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _one(get_supabase_service_client().rpc("consume_step_up_authorization", payload).execute()) or {
        "status": "invalid"
    }


def apply_mfa_disable(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _one(get_supabase_service_client().rpc("apply_mfa_disable", payload).execute()) or {
        "status": "invalid"
    }


def insert_audit_event(payload: Dict[str, Any]) -> None:
    get_supabase_service_client().table("security_audit_events").insert(payload).execute()

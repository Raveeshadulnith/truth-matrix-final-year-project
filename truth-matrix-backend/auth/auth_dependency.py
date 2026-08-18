from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from services.supabase_service import get_supabase_auth_client
from auth.security_config import get_security_config
from auth.security_store import validate_and_touch_session
from auth.security_utils import keyed_digest, session_id_from_verified_token

load_dotenv()

security = HTTPBearer(auto_error=False)


def _credentials_exception(
    message: str = "Invalid or missing authentication token",
    code: str = "AUTHENTICATION_REQUIRED",
) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": code, "message": message},
        headers={"WWW-Authenticate": "Bearer"},
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
        "role": getattr(user, "role", None),
        "app_metadata": getattr(user, "app_metadata", None),
        "user_metadata": getattr(user, "user_metadata", None),
    }


def verify_supabase_jwt(token: str) -> Dict[str, Any]:
    try:
        response = get_supabase_auth_client().auth.get_user(token)
    except Exception as exc:
        if "expired" in str(exc).lower():
            raise _credentials_exception("Authentication token has expired", "SESSION_EXPIRED") from exc
        raise _credentials_exception() from exc

    user = _user_to_dict(getattr(response, "user", None))
    user_id = user.get("id")
    if not user_id:
        raise _credentials_exception("Authentication token does not contain a user id")

    app_metadata = user.get("app_metadata") or {}
    if not isinstance(app_metadata, dict):
        app_metadata = {}

    return {
        "sub": user_id,
        "email": user.get("email"),
        "role": user.get("role") or app_metadata.get("role"),
        "user": user,
    }


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _credentials_exception("Authorization header must be Bearer token")

    token = credentials.credentials
    payload = verify_supabase_jwt(token)
    try:
        session_id = session_id_from_verified_token(token)
        session_digest = keyed_digest(session_id, purpose="app-session", audit=True)
        config = get_security_config()
        session_state = validate_and_touch_session(
            {
                "p_session_digest": session_digest,
                "p_user_id": payload.get("sub"),
                "p_idle_seconds": config.session_idle_timeout_seconds,
                "p_touch_interval_seconds": config.session_touch_interval_seconds,
            }
        )
    except Exception as exc:
        raise _credentials_exception("Authentication session is invalid or expired", "SESSION_EXPIRED") from exc
    if session_state.get("status") != "active":
        if session_state.get("status") in {"idle_expired", "expired"}:
            from auth.security_service import audit

            event_type = "session_idle_expired" if session_state.get("status") == "idle_expired" else "session_expired"
            audit(request, event_type, "revoked", user_id=payload.get("sub"), session_id=session_id)
        raise _credentials_exception("Authentication session is invalid or expired", "SESSION_EXPIRED")
    if config.mfa_required_for_all and not session_state.get("mfa_verified"):
        from auth.security_service import audit

        audit(request, "mfa_required", "session_rejected", user_id=payload.get("sub"), session_id=session_id)
        raise _credentials_exception("Multi-factor authentication is required", "MFA_REQUIRED")
    return {
        "id": payload.get("sub"),
        "email": payload.get("email"),
        "role": payload.get("role"),
        "token": token,
        "session_id": session_id,
        "session_digest": session_digest,
        "claims": payload,
    }

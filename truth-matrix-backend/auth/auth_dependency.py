from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from services.supabase_service import get_supabase_auth_client

load_dotenv()

security = HTTPBearer(auto_error=False)


def _credentials_exception(detail: str = "Invalid or missing authentication token") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
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
            raise _credentials_exception("Authentication token has expired") from exc
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

    payload = verify_supabase_jwt(credentials.credentials)
    return {
        "id": payload.get("sub"),
        "email": payload.get("email"),
        "role": payload.get("role"),
        "token": credentials.credentials,
        "claims": payload,
    }

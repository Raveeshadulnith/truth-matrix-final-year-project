import hashlib
import hmac
import json
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import jwt
from fastapi import Request

from auth.security_config import get_security_config

logger = logging.getLogger("truth_matrix.security")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def keyed_digest(value: str, *, purpose: str, audit: bool = False) -> str:
    config = get_security_config()
    key = (config.audit_hmac_pepper if audit else config.otp_hmac_pepper).encode("utf-8")
    return hmac.new(key, f"{purpose}:{value}".encode("utf-8"), hashlib.sha256).hexdigest()


def otp_digest(challenge_id: str, code: str) -> str:
    return keyed_digest(f"{challenge_id}:{code}", purpose="otp")


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def mask_email(email: str) -> str:
    local, _, domain = normalize_email(email).partition("@")
    if not domain:
        return "***"
    shown = local[:1]
    return f"{shown}{'*' * max(2, min(len(local) - 1, 8))}@{domain}"


def verified_jwt_claims(token: str) -> Dict[str, Any]:
    """Read claims only after the exact token has been verified by Supabase."""
    claims = jwt.decode(token, options={"verify_signature": False, "verify_exp": False})
    if not isinstance(claims, dict):
        raise ValueError("Invalid authentication token claims")
    return claims


def session_id_from_verified_token(token: str) -> str:
    session_id = verified_jwt_claims(token).get("session_id")
    if not isinstance(session_id, str) or not session_id:
        raise ValueError("Authentication token does not contain a session id")
    return session_id


def token_expiry_from_verified_token(token: str) -> Optional[datetime]:
    exp = verified_jwt_claims(token).get("exp")
    if not isinstance(exp, (int, float)):
        return None
    return datetime.fromtimestamp(exp, tz=timezone.utc)


def client_ip(request: Request) -> str:
    config = get_security_config()
    if config.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
        if forwarded:
            return forwarded
    return request.client.host if request.client else "unknown"


def request_context(request: Request, session_id: Optional[str] = None) -> Dict[str, Any]:
    ip = client_ip(request)
    context: Dict[str, Any] = {
        "request_id": getattr(request.state, "request_id", None),
        "ip_hash": keyed_digest(ip, purpose="ip", audit=True),
        "user_agent": request.headers.get("user-agent", "")[:256],
    }
    if session_id:
        context["session_hash"] = keyed_digest(session_id, purpose="session", audit=True)
    return context


_FORBIDDEN_METADATA_KEYS = {
    "password", "otp", "code", "captcha", "captcha_token", "access_token",
    "refresh_token", "authorization", "api_key", "secret", "session_id", "ip",
}


def sanitize_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    clean: Dict[str, Any] = {}
    for key, value in (metadata or {}).items():
        normalized = str(key).casefold()
        if (
            normalized in _FORBIDDEN_METADATA_KEYS
            or normalized.endswith("_ip")
            or any(word in normalized for word in ("password", "token", "secret", "otp"))
        ):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            clean[str(key)[:64]] = value[:256] if isinstance(value, str) else value
    return clean


def log_audit_event(event: Dict[str, Any]) -> None:
    logger.info(json.dumps(event, default=str, separators=(",", ":"), sort_keys=True))

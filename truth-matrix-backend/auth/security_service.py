import logging
import hmac
from datetime import timedelta
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import Request

from auth.auth_service import (
    login_user,
    refresh_user_session,
    send_password_reset,
    sign_out_user,
    signup_user,
)
from auth.providers import CaptchaVerificationError, EmailDeliveryError, captcha_verifier, email_provider
from auth.security_config import get_security_config
from auth.security_store import (
    clear_login_failures,
    consume_challenge,
    apply_mfa_disable,
    create_challenge,
    create_step_up_authorization,
    get_challenge,
    get_security_settings,
    insert_audit_event,
    record_login_failure,
    register_session,
    replace_challenge,
    revoke_challenge,
    revoke_session,
    revoke_session_by_refresh,
    risk_status,
    set_mfa_verified,
    rotate_refresh_session,
    validate_refresh_session,
    validate_and_touch_session,
)
from auth.security_utils import (
    client_ip,
    generate_otp,
    generate_token,
    keyed_digest,
    log_audit_event,
    mask_email,
    normalize_email,
    otp_digest,
    request_context,
    sanitize_metadata,
    session_id_from_verified_token,
    utc_now,
)

logger = logging.getLogger(__name__)


class AuthFlowError(Exception):
    def __init__(self, status_code: int, code: str, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retry_after = retry_after


def audit(
    request: Request,
    event_type: str,
    outcome: str,
    *,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    context = request_context(request, session_id)
    event = {
        "event_type": event_type[:64],
        "outcome": outcome[:32],
        "user_id": user_id,
        "request_id": context.get("request_id"),
        "ip_hash": context.get("ip_hash"),
        "session_hash": context.get("session_hash"),
        "user_agent": context.get("user_agent"),
        "metadata": sanitize_metadata(metadata),
    }
    log_audit_event(event)
    try:
        insert_audit_event(event)
    except Exception:
        logger.exception("security audit persistence failed", extra={"event_type": event_type})


def _risk_keys(request: Request, email: str) -> list[str]:
    return [
        keyed_digest(normalize_email(email), purpose="risk-email", audit=True),
        keyed_digest(client_ip(request), purpose="risk-ip", audit=True),
    ]


def _verify_captcha(request: Request, token: Optional[str], action: str) -> None:
    try:
        captcha_verifier.verify(token, client_ip(request), action)
    except CaptchaVerificationError as exc:
        audit(request, "captcha_verification", "failed", metadata={"reason": str(exc)})
        raise AuthFlowError(403, "CAPTCHA_INVALID", "Bot verification failed. Refresh the page and try again.") from exc
    audit(request, "captcha_verification", "success")


def _challenge_response(row: Dict[str, Any], email: str, purpose: str) -> Dict[str, Any]:
    return {
        "status": "mfa_required",
        "challenge_id": str(row["id"]),
        "purpose": purpose,
        "expires_in": get_security_config().otp_expiry_seconds,
        "masked_destination": mask_email(email),
    }


def _new_challenge(
    request: Request,
    *,
    user_id: Optional[str],
    email: str,
    purpose: str,
    bound_session_digest: Optional[str] = None,
) -> Dict[str, Any]:
    config = get_security_config()
    challenge_id = str(uuid4())
    code = generate_otp()
    row = create_challenge(
        {
            "p_id": challenge_id,
            "p_user_id": user_id,
            "p_purpose": purpose,
            "p_email_hash": keyed_digest(normalize_email(email), purpose="challenge-email", audit=True),
            "p_otp_digest": otp_digest(challenge_id, code),
            "p_expires_at": (utc_now() + timedelta(seconds=config.otp_expiry_seconds)).isoformat(),
            "p_max_attempts": config.otp_max_attempts,
            "p_ip_hash": request_context(request)["ip_hash"],
            "p_bound_session_digest": bound_session_digest,
        }
    )
    try:
        email_provider.send_otp(
            email=email,
            code=code,
            purpose=purpose,
            idempotency_key=f"auth-{purpose}-{challenge_id}-0",
        )
    except EmailDeliveryError as exc:
        try:
            revoke_challenge(challenge_id)
        except Exception:
            logger.exception("failed to revoke undelivered authentication challenge")
        audit(request, "mfa_challenge_sent", "provider_error", user_id=user_id, metadata={"purpose": purpose})
        raise AuthFlowError(503, "EMAIL_DELIVERY_FAILED", "Verification email is temporarily unavailable.") from exc
    audit(request, "mfa_challenge_sent", "success", user_id=user_id, metadata={"purpose": purpose})
    if purpose == "signup":
        audit(request, "signup_challenge_sent", "success")
    return _challenge_response(row, email, purpose)


def begin_signup(request: Request, full_name: str, email: str, password: str, captcha_token: Optional[str]) -> Dict[str, Any]:
    _verify_captcha(request, captcha_token, "signup")
    email = normalize_email(email)
    audit(request, "signup_started", "attempt")
    # The password and profile stay only in browser component memory. Creating
    # the Supabase identity is deferred until the email challenge is consumed.
    return _new_challenge(request, user_id=None, email=email, purpose="signup")


def begin_login(request: Request, email: str, password: str, captcha_token: Optional[str]) -> Dict[str, Any]:
    config = get_security_config()
    captcha_verified = False
    if config.login_captcha_always:
        _verify_captcha(request, captcha_token, "login")
        captcha_verified = True
    email = normalize_email(email)
    keys = _risk_keys(request, email)
    risk = risk_status(keys, config.login_failure_window_seconds)
    if risk.get("blocked"):
        audit(request, "login_failed", "rate_limited", metadata={"reason": "rate_limit"})
        raise AuthFlowError(429, "RATE_LIMITED", "Too many attempts. Please wait and try again.", 60)
    if risk.get("captcha_required"):
        if not captcha_token:
            audit(request, "login_captcha_required", "required")
            raise AuthFlowError(403, "CAPTCHA_REQUIRED", "Complete the CAPTCHA and try again.")
        if not captcha_verified:
            _verify_captcha(request, captcha_token, "login")
    try:
        auth = login_user(email, password)
        user = auth.get("user") or {}
        user_id = str(user.get("id") or "")
        if not user_id or not auth.get("access_token"):
            raise ValueError("Authentication did not return a user session")
        try:
            sign_out_user(auth["access_token"])
        except Exception:
            logger.warning("transient password-check session could not be revoked")
    except Exception as exc:
        state = record_login_failure(
            keys,
            config.login_failure_window_seconds,
            config.login_captcha_threshold,
            config.login_rate_limit,
        )
        audit(request, "login_failed", "rejected", metadata={"reason": "invalid_credentials"})
        if state.get("blocked"):
            raise AuthFlowError(429, "RATE_LIMITED", "Too many attempts. Please wait and try again.", 60) from exc
        raise AuthFlowError(401, "INVALID_CREDENTIALS", "Invalid email or password.") from exc

    settings = get_security_settings(user_id)
    if config.mfa_required_for_all or settings.get("mfa_enabled", True):
        return _new_challenge(request, user_id=user_id, email=email, purpose="login")
    clear_login_failures(keys)
    return _finish_session(request, auth, user_id, email, event_type="login_succeeded", assurance_level="aal1")


def _finish_session(
    request: Request,
    auth: Dict[str, Any],
    user_id: str,
    email: str,
    event_type: str,
    assurance_level: str = "aal2",
) -> Dict[str, Any]:
    config = get_security_config()
    access_token = auth.get("access_token")
    refresh_token = auth.get("refresh_token")
    if not access_token or not refresh_token:
        raise AuthFlowError(401, "SESSION_NOT_CREATED", "Authentication could not be completed.")
    session_id = session_id_from_verified_token(access_token)
    absolute = utc_now() + timedelta(seconds=config.session_absolute_timeout_seconds)
    try:
        register_session(
            {
                "p_session_digest": keyed_digest(session_id, purpose="app-session", audit=True),
                "p_refresh_token_digest": keyed_digest(refresh_token, purpose="refresh-token", audit=True),
                "p_user_id": user_id,
                "p_absolute_expires_at": absolute.isoformat(),
                "p_mfa_verified_at": utc_now().isoformat() if assurance_level == "aal2" else None,
            }
        )
    except Exception as exc:
        try:
            sign_out_user(access_token)
        except Exception:
            logger.warning("provider session cleanup failed after registry error")
        audit(request, "session_creation_failed", "registry_error", user_id=user_id, session_id=session_id)
        raise AuthFlowError(503, "SESSION_NOT_CREATED", "Authentication could not be completed.") from exc
    clear_login_failures(_risk_keys(request, email))
    if assurance_level == "aal2":
        set_mfa_verified(user_id, True)
    audit(request, event_type, "success", user_id=user_id, session_id=session_id)
    return {
        **auth,
        "assurance_level": assurance_level,
        "idle_timeout_seconds": config.session_idle_timeout_seconds,
    }


def verify_mfa(
    request: Request,
    challenge_id: str,
    code: str,
    password: str,
    email: str,
    full_name: Optional[str] = None,
) -> Dict[str, Any]:
    result = consume_challenge(challenge_id, otp_digest(challenge_id, code))
    if result.get("status") != "verified":
        audit(request, "mfa_failed", str(result.get("status", "invalid")), metadata={"purpose": result.get("purpose")})
        status_code = 429 if result.get("status") == "attempts_exhausted" else 400
        raise AuthFlowError(status_code, "MFA_INVALID", "The verification code is invalid or expired.")
    user_id = str(result.get("user_id") or "")
    purpose = str(result.get("purpose") or "")
    email = normalize_email(email)
    expected_email_hash = keyed_digest(email, purpose="challenge-email", audit=True)
    email_bound = hmac.compare_digest(str(result.get("email_hash") or ""), expected_email_hash)
    if purpose not in {"signup", "login"} or not email_bound or (purpose == "login" and not user_id):
        audit(request, "mfa_failed", "invalid_binding", metadata={"purpose": purpose})
        raise AuthFlowError(400, "MFA_INVALID", "The verification code is invalid or expired.")
    try:
        if purpose == "signup":
            if not full_name or not full_name.strip():
                raise ValueError("Signup profile is missing")
            created = signup_user(full_name.strip(), email, password)
            user_id = str((created.get("user") or {}).get("id") or "")
            if not user_id:
                raise ValueError("Signup did not create a user")
        auth = login_user(email, password)
        authenticated_user_id = str((auth.get("user") or {}).get("id") or "")
        if authenticated_user_id != user_id:
            raise ValueError("Authentication challenge user binding changed")
    except Exception as exc:
        audit(request, "mfa_failed", "credential_recheck_failed", user_id=user_id, metadata={"purpose": purpose})
        if purpose == "signup":
            audit(request, "signup_failed", "rejected", user_id=user_id or None, metadata={"reason": "account_unavailable"})
        raise AuthFlowError(401, "AUTHENTICATION_RESTART_REQUIRED", "Authentication expired. Please start again.") from exc
    audit(request, f"{purpose}_verified", "success", user_id=user_id)
    audit(request, "mfa_verified", "success", user_id=user_id, metadata={"purpose": purpose})
    return _finish_session(request, auth, user_id, email, event_type="login_succeeded")


def resend_mfa(request: Request, challenge_id: str, email: str, captcha_token: Optional[str]) -> Dict[str, Any]:
    _verify_captcha(request, captcha_token, "mfa_resend")
    config = get_security_config()
    challenge = get_challenge(challenge_id)
    email = normalize_email(email)
    if (
        not challenge
        or not hmac.compare_digest(
            str(challenge.get("email_hash") or ""),
            keyed_digest(email, purpose="challenge-email", audit=True),
        )
    ):
        audit(request, "mfa_resend_limited", "unknown_challenge")
        return {
            "message": "If the challenge is active, a new code has been sent.",
            "expires_in": config.otp_expiry_seconds,
        }
    user_id = str(challenge.get("user_id") or "") or None
    code = generate_otp()
    try:
        row = replace_challenge(
            {
                "p_challenge_id": challenge_id,
                "p_otp_digest": otp_digest(challenge_id, code),
                "p_expires_at": (utc_now() + timedelta(seconds=config.otp_expiry_seconds)).isoformat(),
                "p_cooldown_seconds": config.otp_resend_cooldown_seconds,
                "p_max_resends": config.otp_max_resends,
            }
        )
        resend_count = int(row.get("resend_count", 0))
    except Exception as exc:
        audit(request, "mfa_resend_limited", "limited", user_id=user_id)
        raise AuthFlowError(429, "RESEND_LIMITED", "Please wait before requesting another code.", config.otp_resend_cooldown_seconds) from exc
    try:
        email_provider.send_otp(
            email=email,
            code=code,
            purpose=str(challenge.get("purpose")),
            idempotency_key=f"auth-{challenge.get('purpose')}-{challenge_id}-{resend_count}",
        )
    except EmailDeliveryError as exc:
        audit(request, "mfa_challenge_sent", "provider_error", user_id=user_id, metadata={"purpose": challenge.get("purpose")})
        raise AuthFlowError(503, "EMAIL_DELIVERY_FAILED", "Verification email is temporarily unavailable.") from exc
    audit(request, "mfa_challenge_sent", "resent", user_id=user_id, metadata={"purpose": challenge.get("purpose")})
    return {
        "message": "If the challenge is active, a new code has been sent.",
        "expires_in": config.otp_expiry_seconds,
    }


def refresh_session(request: Request, refresh_token: str) -> Dict[str, Any]:
    old_refresh_digest = keyed_digest(refresh_token, purpose="refresh-token", audit=True)
    try:
        state = validate_refresh_session(
            {
                "p_refresh_token_digest": old_refresh_digest,
                "p_idle_seconds": get_security_config().session_idle_timeout_seconds,
            }
        )
    except Exception as exc:
        audit(request, "session_refresh_failed", "registry_error")
        raise AuthFlowError(503, "SESSION_CHECK_UNAVAILABLE", "Session validation is temporarily unavailable.") from exc
    if state.get("status") != "active" or (
        get_security_config().mfa_required_for_all and not state.get("mfa_verified")
    ):
        audit(request, "session_refresh_failed", str(state.get("status", "invalid")))
        raise AuthFlowError(401, "SESSION_EXPIRED", "Your session has expired. Please sign in again.")
    access_token: Optional[str] = None
    try:
        auth = refresh_user_session(refresh_token)
        access_token = auth.get("access_token")
        new_refresh_token = auth.get("refresh_token")
        user_id = str((auth.get("user") or {}).get("id") or "")
        session_id = session_id_from_verified_token(access_token)
        session_digest = keyed_digest(session_id, purpose="app-session", audit=True)
        if user_id != str(state.get("user_id") or "") or session_digest != str(state.get("session_digest") or ""):
            raise ValueError("Refreshed provider session binding changed")
        rotated = rotate_refresh_session(
            {
                "p_old_refresh_token_digest": old_refresh_digest,
                "p_new_refresh_token_digest": keyed_digest(new_refresh_token, purpose="refresh-token", audit=True),
                "p_session_digest": session_digest,
                "p_user_id": user_id,
                "p_idle_seconds": get_security_config().session_idle_timeout_seconds,
            }
        )
        if rotated.get("status") != "rotated":
            raise ValueError("Application session was revoked during refresh")
    except Exception as exc:
        if access_token:
            try:
                sign_out_user(access_token)
            except Exception:
                logger.warning("refreshed provider session cleanup failed")
        audit(request, "session_refresh_failed", "rejected", user_id=str(state.get("user_id") or "") or None)
        raise AuthFlowError(401, "SESSION_EXPIRED", "Your session has expired. Please sign in again.") from exc
    audit(request, "session_refreshed", "success", user_id=user_id, session_id=session_id)
    return {
        **auth,
        "assurance_level": "aal2" if state.get("mfa_verified") else "aal1",
        "idle_timeout_seconds": get_security_config().session_idle_timeout_seconds,
    }


def logout(request: Request, token: str, user_id: str, session_id: str) -> None:
    session_digest = keyed_digest(session_id, purpose="app-session", audit=True)
    revocation_error: Optional[Exception] = None
    try:
        revoke_session(session_digest, user_id, "logout")
    except Exception as exc:
        revocation_error = exc
        audit(request, "session_revocation_failed", "registry_error", user_id=user_id, session_id=session_id)
    finally:
        try:
            sign_out_user(token)
        except Exception:
            logger.warning("Supabase logout failed after local revocation")
            audit(request, "provider_logout_failed", "provider_error", user_id=user_id, session_id=session_id)
    if revocation_error is not None:
        raise revocation_error
    audit(request, "logout", "success", user_id=user_id, session_id=session_id)
    audit(request, "session_revoked", "success", user_id=user_id, session_id=session_id, metadata={"reason": "logout"})


def logout_with_refresh_token(request: Request, refresh_token: str) -> None:
    """Revoke an app session when the bearer JWT is already expired."""
    try:
        result = revoke_session_by_refresh(
            {
                "p_refresh_token_digest": keyed_digest(
                    refresh_token, purpose="refresh-token", audit=True
                ),
                "p_reason": "logout",
            }
        )
    except Exception as exc:
        audit(request, "session_revocation_failed", "registry_error")
        raise AuthFlowError(503, "LOGOUT_INCOMPLETE", "Server logout could not be completed.") from exc
    outcome = "success" if result.get("status") in {"revoked", "already_revoked", "invalid"} else "failed"
    audit(request, "logout", outcome, user_id=str(result.get("user_id") or "") or None)
    audit(
        request,
        "session_revoked",
        outcome,
        user_id=str(result.get("user_id") or "") or None,
        metadata={"reason": "logout", "credential": "refresh_digest"},
    )


def request_password_reset(request: Request, email: str, captcha_token: Optional[str]) -> None:
    _verify_captcha(request, captcha_token, "password_reset")
    try:
        send_password_reset(normalize_email(email))
        outcome = "accepted"
    except Exception:
        outcome = "accepted_unknown"
    audit(request, "password_reset_requested", outcome)


def start_step_up(request: Request, current_user: Dict[str, Any], password: str, captcha_token: Optional[str]) -> Dict[str, Any]:
    if captcha_token:
        _verify_captcha(request, captcha_token, "step_up")
    email = normalize_email(str(current_user.get("email") or ""))
    try:
        transient = login_user(email, password)
        if not transient.get("access_token"):
            raise ValueError("No transient session")
        try:
            sign_out_user(transient["access_token"])
        except Exception:
            logger.warning("step-up password-check session could not be revoked")
    except Exception as exc:
        audit(request, "step_up_failed", "invalid_password", user_id=current_user["id"])
        raise AuthFlowError(401, "STEP_UP_FAILED", "Verification failed.") from exc
    audit(request, "step_up_started", "password_verified", user_id=current_user["id"], session_id=current_user["session_id"])
    return _new_challenge(
        request,
        user_id=current_user["id"],
        email=email,
        purpose="step_up_disable_mfa",
        bound_session_digest=current_user["session_digest"],
    )


def verify_step_up(request: Request, current_user: Dict[str, Any], challenge_id: str, code: str) -> Dict[str, str]:
    result = consume_challenge(challenge_id, otp_digest(challenge_id, code))
    if (
        result.get("status") != "verified"
        or result.get("purpose") != "step_up_disable_mfa"
        or result.get("user_id") != current_user["id"]
        or result.get("bound_session_digest") != current_user["session_digest"]
    ):
        audit(request, "step_up_failed", "invalid", user_id=current_user["id"], session_id=current_user["session_id"])
        raise AuthFlowError(400, "STEP_UP_FAILED", "Verification failed or expired.")
    raw_token = generate_token()
    token_digest = keyed_digest(raw_token, purpose="step-up", audit=True)
    create_step_up_authorization(
        {
            "token_digest": token_digest,
            "user_id": current_user["id"],
            "session_digest": current_user["session_digest"],
            "action": "disable_mfa",
            "expires_at": (utc_now() + timedelta(seconds=get_security_config().step_up_max_age_seconds)).isoformat(),
        }
    )
    audit(request, "step_up_succeeded", "success", user_id=current_user["id"], session_id=current_user["session_id"])
    return {"step_up_token": raw_token}


def disable_mfa(request: Request, current_user: Dict[str, Any], raw_step_up_token: str) -> None:
    config = get_security_config()
    if config.mfa_required_for_all or not config.allow_mfa_disable:
        audit(request, "mfa_disable_rejected", "policy", user_id=current_user["id"], session_id=current_user["session_id"])
        raise AuthFlowError(403, "MFA_REQUIRED_BY_POLICY", "MFA is required by security policy.")
    result = apply_mfa_disable(
        {
            "p_token_digest": keyed_digest(raw_step_up_token, purpose="step-up", audit=True),
            "p_user_id": current_user["id"],
            "p_session_digest": current_user["session_digest"],
            "p_action": "disable_mfa",
        }
    )
    if result.get("status") != "consumed":
        audit(request, "mfa_disable_rejected", "step_up_invalid", user_id=current_user["id"], session_id=current_user["session_id"])
        raise AuthFlowError(403, "RECENT_VERIFICATION_REQUIRED", "Recent password and MFA verification is required.")
    audit(request, "session_revoked", "other_sessions", user_id=current_user["id"], session_id=current_user["session_id"], metadata={"reason": "mfa_disabled"})
    audit(request, "mfa_disabled", "success", user_id=current_user["id"], session_id=current_user["session_id"])


def mfa_status(user_id: str) -> Dict[str, Any]:
    settings = get_security_settings(user_id)
    config = get_security_config()
    return {
        "mfa_enabled": bool(settings.get("mfa_enabled", True)),
        "required_by_policy": config.mfa_required_for_all,
        "disable_allowed": config.allow_mfa_disable and not config.mfa_required_for_all,
    }

from typing import Any, Dict, Union

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from auth.auth_dependency import get_current_user, security, verify_supabase_jwt
from auth.security_service import (
    AuthFlowError, begin_login, begin_signup, disable_mfa, logout, logout_with_refresh_token, mfa_status,
    refresh_session, request_password_reset, resend_mfa, start_step_up,
    verify_mfa, verify_step_up,
)
from auth.security_utils import session_id_from_verified_token
from schemas.auth_schema import (
    ApiMessage, AuthResponse, ChallengeResponse, LoginRequest, LogoutRequest,
    MfaDisableRequest, MfaResendRequest, MfaVerifyRequest, ProfileUpdateRequest,
    RefreshRequest, ResendResponse, ResetPasswordRequest, SignupRequest, StepUpStartRequest,
    StepUpVerifyRequest,
)
from services.supabase_service import get_user_profile, update_user_profile

router = APIRouter(prefix="/api/auth", tags=["authentication"])


def _raise_auth_error(exc: AuthFlowError) -> None:
    headers = {"Cache-Control": "no-store"}
    if exc.retry_after is not None:
        headers["Retry-After"] = str(exc.retry_after)
    raise HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.message},
        headers=headers,
    ) from exc


def _current_user_profile(current_user: Dict[str, Any]) -> Dict[str, Any]:
    profile = get_user_profile(current_user["id"]) or {}
    return {
        "id": current_user["id"],
        "email": profile.get("email") or current_user.get("email"),
        "full_name": profile.get("full_name") or "",
        "avatar_url": profile.get("avatar_url"),
        "role": profile.get("role") or "user",
        "created_at": profile.get("created_at"),
        "updated_at": profile.get("updated_at"),
    }


@router.post("/signup", response_model=ChallengeResponse, status_code=status.HTTP_202_ACCEPTED)
def signup_route(payload: SignupRequest, request: Request) -> Dict[str, Any]:
    try:
        return begin_signup(request, payload.full_name, str(payload.email), payload.password, payload.captcha_token)
    except AuthFlowError as exc:
        _raise_auth_error(exc)


@router.post("/login", response_model=Union[ChallengeResponse, AuthResponse])
def login_route(payload: LoginRequest, request: Request) -> Dict[str, Any]:
    try:
        return begin_login(request, str(payload.email), payload.password, payload.captcha_token)
    except AuthFlowError as exc:
        _raise_auth_error(exc)


@router.post("/mfa/verify", response_model=AuthResponse)
def verify_mfa_route(payload: MfaVerifyRequest, request: Request) -> Dict[str, Any]:
    try:
        return verify_mfa(
            request,
            payload.challenge_id,
            payload.code,
            payload.password,
            str(payload.email),
            payload.full_name,
        )
    except AuthFlowError as exc:
        _raise_auth_error(exc)


@router.post("/mfa/resend", response_model=ResendResponse, status_code=status.HTTP_202_ACCEPTED)
def resend_mfa_route(payload: MfaResendRequest, request: Request) -> Dict[str, Any]:
    try:
        return resend_mfa(request, payload.challenge_id, str(payload.email), payload.captcha_token)
    except AuthFlowError as exc:
        _raise_auth_error(exc)


@router.post("/refresh", response_model=AuthResponse)
def refresh_route(payload: RefreshRequest, request: Request) -> Dict[str, Any]:
    try:
        return refresh_session(request, payload.refresh_token)
    except AuthFlowError as exc:
        _raise_auth_error(exc)


@router.post("/logout", response_model=ApiMessage)
def logout_route(
    payload: LogoutRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, str]:
    if credentials is not None and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
        try:
            verified = verify_supabase_jwt(token)
        except Exception:
            if payload.refresh_token:
                try:
                    logout_with_refresh_token(request, payload.refresh_token)
                except AuthFlowError as exc:
                    _raise_auth_error(exc)
            return {"message": "Signed out."}
        try:
            logout(request, token, str(verified["sub"]), session_id_from_verified_token(token))
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "LOGOUT_INCOMPLETE", "message": "Server logout could not be completed."},
            ) from exc
    elif payload.refresh_token:
        try:
            logout_with_refresh_token(request, payload.refresh_token)
        except AuthFlowError as exc:
            _raise_auth_error(exc)
    return {"message": "Signed out."}


@router.post("/reset-password", response_model=ApiMessage, status_code=status.HTTP_202_ACCEPTED)
def reset_password_route(payload: ResetPasswordRequest, request: Request) -> Dict[str, str]:
    try:
        request_password_reset(request, str(payload.email), payload.captcha_token)
    except AuthFlowError as exc:
        _raise_auth_error(exc)
    return {"message": "If an account exists, password reset instructions will be sent."}


@router.get("/me")
def read_me(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return _current_user_profile(current_user)


@router.put("/profile")
def update_profile_route(
    payload: ProfileUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        update_user_profile(
            current_user["id"],
            {"full_name": payload.full_name, "avatar_url": payload.avatar_url},
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Profile update failed.") from exc
    return _current_user_profile(current_user)


@router.get("/mfa/status")
def mfa_status_route(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return mfa_status(current_user["id"])


@router.post("/step-up/start", response_model=ChallengeResponse)
def step_up_start_route(
    payload: StepUpStartRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        return start_step_up(request, current_user, payload.password, payload.captcha_token)
    except AuthFlowError as exc:
        _raise_auth_error(exc)


@router.post("/step-up/verify")
def step_up_verify_route(
    payload: StepUpVerifyRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, str]:
    try:
        return verify_step_up(request, current_user, payload.challenge_id, payload.code)
    except AuthFlowError as exc:
        _raise_auth_error(exc)


@router.post("/mfa/disable", response_model=ApiMessage)
def mfa_disable_route(
    payload: MfaDisableRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, str]:
    try:
        disable_mfa(request, current_user, payload.step_up_token)
    except AuthFlowError as exc:
        _raise_auth_error(exc)
    return {"message": "MFA disabled."}

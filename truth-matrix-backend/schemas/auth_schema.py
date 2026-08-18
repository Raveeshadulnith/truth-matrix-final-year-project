from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class SignupRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    captcha_token: Optional[str] = Field(None, max_length=4096)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        if not any(ch.isupper() for ch in value) or not any(ch.islower() for ch in value) or not any(ch.isdigit() for ch in value):
            raise ValueError("Password must include uppercase, lowercase, and numeric characters")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)
    captcha_token: Optional[str] = Field(None, max_length=4096)


class ChallengeResponse(BaseModel):
    status: Literal["mfa_required"] = "mfa_required"
    challenge_id: str
    purpose: str
    expires_in: int
    masked_destination: str


class MfaVerifyRequest(BaseModel):
    challenge_id: str
    code: str = Field(..., pattern=r"^\d{6}$")
    password: str = Field(..., min_length=1, max_length=128)
    email: EmailStr
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)


class MfaResendRequest(BaseModel):
    challenge_id: str
    email: EmailStr
    captcha_token: Optional[str] = Field(None, max_length=4096)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1, max_length=4096)


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = Field(None, max_length=4096)


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    captcha_token: Optional[str] = Field(None, max_length=4096)


class StepUpStartRequest(BaseModel):
    password: str = Field(..., min_length=1, max_length=128)
    captcha_token: Optional[str] = Field(None, max_length=4096)


class StepUpVerifyRequest(BaseModel):
    challenge_id: str
    code: str = Field(..., pattern=r"^\d{6}$")


class MfaDisableRequest(BaseModel):
    step_up_token: str = Field(..., min_length=20, max_length=512)


class ProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    avatar_url: Optional[str] = None


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: Dict[str, Any]
    assurance_level: Literal["aal1", "aal2"] = "aal2"
    idle_timeout_seconds: int


class ApiMessage(BaseModel):
    message: str
    code: Optional[str] = None


class ResendResponse(ApiMessage):
    expires_in: int

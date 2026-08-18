import os
from dataclasses import dataclass
from functools import lru_cache
from typing import FrozenSet


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be a boolean")


def _int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise RuntimeError(f"{name} must be between {minimum} and {maximum}")
    return value


def _float(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = os.getenv(name, str(default))
    try:
        value = float(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a number") from exc
    if not minimum <= value <= maximum:
        raise RuntimeError(f"{name} must be between {minimum} and {maximum}")
    return value


@dataclass(frozen=True)
class SecurityConfig:
    environment: str
    https_enabled: bool
    captcha_enabled: bool
    recaptcha_version: str
    recaptcha_secret_key: str
    recaptcha_allowed_hostnames: FrozenSet[str]
    recaptcha_min_score: float
    resend_api_key: str
    resend_from_email: str
    resend_reply_to: str
    otp_hmac_pepper: str
    audit_hmac_pepper: str
    otp_expiry_seconds: int
    otp_max_attempts: int
    otp_resend_cooldown_seconds: int
    otp_max_resends: int
    login_failure_window_seconds: int
    login_captcha_always: bool
    login_captcha_threshold: int
    login_rate_limit: int
    session_idle_timeout_seconds: int
    session_absolute_timeout_seconds: int
    session_touch_interval_seconds: int
    step_up_max_age_seconds: int
    mfa_required_for_all: bool
    allow_mfa_disable: bool
    trust_proxy_headers: bool

    @property
    def production(self) -> bool:
        return self.environment in {"production", "prod"}

    def validate(self) -> None:
        if self.recaptcha_version not in {"v2", "v3"}:
            raise RuntimeError("RECAPTCHA_VERSION must be v2 or v3")
        if not self.production:
            return
        if not self.captcha_enabled:
            raise RuntimeError("CAPTCHA_ENABLED must be true in production")
        required = {
            "SUPABASE_URL": os.getenv("SUPABASE_URL", "").strip(),
            "SUPABASE_ANON_KEY": os.getenv("SUPABASE_ANON_KEY", "").strip(),
            "SUPABASE_SERVICE_ROLE_KEY": os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip(),
            "RESEND_API_KEY": self.resend_api_key,
            "RESEND_FROM_EMAIL": self.resend_from_email,
            "OTP_HMAC_PEPPER": self.otp_hmac_pepper,
            "AUDIT_HMAC_PEPPER": self.audit_hmac_pepper,
        }
        if self.captcha_enabled:
            required["RECAPTCHA_SECRET_KEY"] = self.recaptcha_secret_key
            if not self.recaptcha_allowed_hostnames:
                raise RuntimeError("RECAPTCHA_ALLOWED_HOSTNAMES is required in production")
        missing = [name for name, value in required.items() if not value]
        placeholders = [
            name
            for name, value in required.items()
            if value and any(marker in value.lower() for marker in ("change-me", "placeholder", "example"))
        ]
        if missing or placeholders:
            names = sorted(set(missing + placeholders))
            raise RuntimeError(f"Missing or placeholder security configuration: {', '.join(names)}")
        if self.captcha_enabled and self.recaptcha_allowed_hostnames <= {"localhost", "127.0.0.1", "::1"}:
            raise RuntimeError("RECAPTCHA_ALLOWED_HOSTNAMES must include a production hostname")
        if len(self.otp_hmac_pepper) < 32 or len(self.audit_hmac_pepper) < 32:
            raise RuntimeError("OTP_HMAC_PEPPER and AUDIT_HMAC_PEPPER must be at least 32 characters")


@lru_cache(maxsize=1)
def get_security_config() -> SecurityConfig:
    environment = os.getenv("APP_ENV", "development").strip().lower()
    config = SecurityConfig(
        environment=environment,
        https_enabled=_bool("HTTPS_ENABLED", False),
        captcha_enabled=_bool("CAPTCHA_ENABLED", environment != "test"),
        recaptcha_version=os.getenv("RECAPTCHA_VERSION", "v3").strip().lower(),
        recaptcha_secret_key=os.getenv("RECAPTCHA_SECRET_KEY", "").strip(),
        recaptcha_allowed_hostnames=frozenset(
            item.strip().lower()
            for item in os.getenv("RECAPTCHA_ALLOWED_HOSTNAMES", "localhost,127.0.0.1").split(",")
            if item.strip()
        ),
        recaptcha_min_score=_float("RECAPTCHA_MIN_SCORE", 0.5, 0.0, 1.0),
        resend_api_key=os.getenv("RESEND_API_KEY", "").strip(),
        resend_from_email=os.getenv("RESEND_FROM_EMAIL", "").strip(),
        resend_reply_to=os.getenv("RESEND_REPLY_TO", "").strip(),
        otp_hmac_pepper=os.getenv("OTP_HMAC_PEPPER", "development-only-change-me-otp-pepper"),
        audit_hmac_pepper=os.getenv("AUDIT_HMAC_PEPPER", "development-only-change-me-audit-pepper"),
        otp_expiry_seconds=_int("OTP_EXPIRY_SECONDS", 600, 60, 600),
        otp_max_attempts=_int("OTP_MAX_ATTEMPTS", 5, 1, 10),
        otp_resend_cooldown_seconds=_int("OTP_RESEND_COOLDOWN_SECONDS", 60, 10, 600),
        otp_max_resends=_int("OTP_MAX_RESENDS", 3, 0, 10),
        login_failure_window_seconds=_int("LOGIN_FAILURE_WINDOW_SECONDS", 900, 60, 86400),
        login_captcha_always=_bool("LOGIN_CAPTCHA_ALWAYS", False),
        login_captcha_threshold=_int("LOGIN_CAPTCHA_THRESHOLD", 3, 1, 20),
        login_rate_limit=_int("LOGIN_RATE_LIMIT", 10, 3, 100),
        session_idle_timeout_seconds=_int("SESSION_IDLE_TIMEOUT_SECONDS", 900, 60, 86400),
        session_absolute_timeout_seconds=_int("SESSION_ABSOLUTE_TIMEOUT_SECONDS", 28800, 300, 604800),
        session_touch_interval_seconds=_int("SESSION_TOUCH_INTERVAL_SECONDS", 60, 1, 600),
        step_up_max_age_seconds=_int("STEP_UP_MAX_AGE_SECONDS", 300, 30, 900),
        mfa_required_for_all=_bool("MFA_REQUIRED_FOR_ALL", True),
        allow_mfa_disable=_bool("ALLOW_MFA_DISABLE", False),
        trust_proxy_headers=_bool("TRUST_PROXY_HEADERS", False),
    )
    config.validate()
    return config

import html
import logging
from datetime import datetime, timezone
from typing import Optional

import requests

from auth.security_config import get_security_config


logger = logging.getLogger(__name__)


class CaptchaVerificationError(Exception):
    pass


class CaptchaVerifier:
    endpoint = "https://www.google.com/recaptcha/api/siteverify"
    max_age_seconds = 120

    def verify(self, token: Optional[str], remote_ip: Optional[str], expected_action: Optional[str] = None) -> None:
        config = get_security_config()
        if not config.captcha_enabled:
            return
        if not token or not config.recaptcha_secret_key:
            raise CaptchaVerificationError("CAPTCHA verification is required")
        try:
            response = requests.post(
                self.endpoint,
                data={"secret": config.recaptcha_secret_key, "response": token, "remoteip": remote_ip},
                timeout=5,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise CaptchaVerificationError("CAPTCHA provider unavailable") from exc
        hostname = str(payload.get("hostname", "")).lower()
        recaptcha_version = getattr(config, "recaptcha_version", "v3")
        action = str(payload.get("action", ""))
        try:
            score = float(payload.get("score"))
        except (TypeError, ValueError):
            score = -1.0
        try:
            challenge_time = datetime.fromisoformat(str(payload.get("challenge_ts", "")).replace("Z", "+00:00"))
            if challenge_time.tzinfo is None:
                challenge_time = challenge_time.replace(tzinfo=timezone.utc)
            age_seconds = (datetime.now(timezone.utc) - challenge_time.astimezone(timezone.utc)).total_seconds()
        except (TypeError, ValueError):
            age_seconds = self.max_age_seconds + 1
        rejection_reasons = []
        if not payload.get("success"):
            rejection_reasons.append("provider_rejected")
        if hostname not in config.recaptcha_allowed_hostnames:
            rejection_reasons.append("hostname_mismatch")
        if recaptcha_version == "v3" and expected_action is not None and action != expected_action:
            rejection_reasons.append("action_mismatch")
        if recaptcha_version == "v3" and score < config.recaptcha_min_score:
            rejection_reasons.append("score_below_threshold")
        if age_seconds < -30 or age_seconds > self.max_age_seconds:
            rejection_reasons.append("token_stale")
        if rejection_reasons:
            logger.warning(
                "reCAPTCHA v3 verification rejected reasons=%s hostname=%s action=%s score=%s error_codes=%s",
                rejection_reasons,
                hostname,
                action,
                score,
                payload.get("error-codes", []),
            )
            raise CaptchaVerificationError(",".join(rejection_reasons))


class EmailDeliveryError(Exception):
    pass


class ResendEmailProvider:
    def send_otp(self, *, email: str, code: str, purpose: str, idempotency_key: str) -> str:
        config = get_security_config()
        if not config.resend_api_key or not config.resend_from_email:
            raise EmailDeliveryError("Email provider is not configured")
        try:
            import resend

            resend.api_key = config.resend_api_key
            safe_code = html.escape(code)
            safe_purpose = html.escape("account setup" if purpose == "signup" else purpose.replace("_", " "))
            params = {
                "from": config.resend_from_email,
                "to": [email],
                "subject": "Your Truth Matrix verification code",
                "text": (
                    f"Your Truth Matrix code is {code}. It expires in "
                    f"{config.otp_expiry_seconds // 60} minutes. Do not share this code."
                ),
                "html": (
                    "<p>Use this code to complete your Truth Matrix " + safe_purpose + ":</p>"
                    f"<p style=\"font-size:28px;font-weight:700;letter-spacing:6px\">{safe_code}</p>"
                    f"<p>It expires in {config.otp_expiry_seconds // 60} minutes. "
                    "Do not share this code with anyone.</p>"
                ),
            }
            if config.resend_reply_to:
                params["reply_to"] = config.resend_reply_to
            result = resend.Emails.send(params, {"idempotency_key": idempotency_key})
            return str(result.get("id", ""))
        except Exception as exc:
            raise EmailDeliveryError("Could not deliver verification email") from exc


captcha_verifier = CaptchaVerifier()
email_provider = ResendEmailProvider()

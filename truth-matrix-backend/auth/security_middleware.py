import logging
from typing import Dict
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from auth.security_config import get_security_config

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = dict(scope.get("headers", [])).get(b"x-request-id", b"").decode("ascii", "ignore")[:64]
        if not request_id:
            request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id

        response_started = False

        async def send_with_headers(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                headers = list(message.get("headers", []))
                existing = {name.lower() for name, _ in headers}
                values: Dict[bytes, bytes] = {
                    b"x-content-type-options": b"nosniff",
                    b"referrer-policy": b"no-referrer",
                    b"x-frame-options": b"DENY",
                    b"content-security-policy": b"default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
                    b"permissions-policy": b"camera=(), microphone=(), geolocation=()",
                    b"x-request-id": request_id.encode("ascii"),
                }
                path = str(scope.get("path", ""))
                if path.startswith("/api/auth"):
                    values[b"cache-control"] = b"no-store"
                    values[b"pragma"] = b"no-cache"
                config = get_security_config()
                if config.production and config.https_enabled:
                    values[b"strict-transport-security"] = b"max-age=31536000; includeSubDomains"
                headers.extend((name, value) for name, value in values.items() if name not in existing)
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        except Exception:
            logger.exception("Unhandled application error", extra={"request_id": request_id})
            if response_started:
                raise
            await send_with_headers(
                {"type": "http.response.start", "status": 500, "headers": [(b"content-type", b"application/json")]}
            )
            await send_with_headers(
                {"type": "http.response.body", "body": b'{"detail":"Internal server error"}'}
            )

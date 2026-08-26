"""SoAI - OpenAI anonymous owner token response decorator middleware [backend/features/api/middleware/openai_anonymous_owner_token.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from core.auth.cookies import determine_secure_cookie
from core.openai.anonymous_owner_tokens import normalize_anonymous_owner_token
from core.runtime.proxy_headers import resolve_request_scheme
from core.system_api.request_paths import get_scope_path
from core.system_api.route_paths import (
    OPENAI_ANONYMOUS_COOKIE_PATH,
    OPENAI_COMPAT_PREFIX_WITH_SLASH,
)

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol

__all__ = ("OpenAIAnonymousOwnerTokenMiddleware",)

_ANON_TOKEN_COOKIE = "soai-anon-token"
_ANON_TOKEN_RESPONSE_HEADER = "X-SoAI-Anon-Token"


def _build_set_cookie_header(
    token: str,
    *,
    secure: bool,
) -> str:
    parts = [
        f"{_ANON_TOKEN_COOKIE}={token}",
        f"Path={OPENAI_ANONYMOUS_COOKIE_PATH}",
        "SameSite=Lax",
        "HttpOnly",
    ]
    if secure:
        parts.append("Secure")
    return "; ".join(parts)


def _response_already_sets_owner_cookie(headers: list[tuple[bytes, bytes]]) -> bool:
    for key, value in headers:
        if key.lower() != b"set-cookie":
            continue
        try:
            text = value.decode("latin-1")
        except UnicodeDecodeError:
            continue
        if text.startswith(f"{_ANON_TOKEN_COOKIE}="):
            return True
    return False


class OpenAIAnonymousOwnerTokenMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive)
        path = get_scope_path(request.scope)
        if not path.startswith(OPENAI_COMPAT_PREFIX_WITH_SLASH):
            await self.app(scope, receive, send)
            return
        try:
            config_value = request.app.state.api_dependencies.config
        except AttributeError:
            config_value = None
        config: ConfigProtocol | None = config_value if config_value is not None else None

        async def send_wrapper(message: Message) -> None:
            if message.get("type") != "http.response.start":
                await send(message)
                return
            try:
                issued = request.state.issued_anonymous_owner_token
            except AttributeError:
                issued = None
            headers = list(message.get("headers") or [])
            token = normalize_anonymous_owner_token(issued) if isinstance(issued, str) else None
            if token is None:
                await send(message)
                return
            header_key = _ANON_TOKEN_RESPONSE_HEADER.lower().encode("latin-1")
            if not any(key.lower() == header_key for key, _value in headers):
                headers.append(
                    (_ANON_TOKEN_RESPONSE_HEADER.encode("latin-1"), token.encode("latin-1")),
                )
            if config is not None and (not _response_already_sets_owner_cookie(headers)):
                scheme = resolve_request_scheme(request)
                secure_cookie = determine_secure_cookie(config, request_scheme=scheme)
                headers.append(
                    (
                        b"set-cookie",
                        _build_set_cookie_header(token, secure=secure_cookie).encode("latin-1"),
                    ),
                )
            message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)

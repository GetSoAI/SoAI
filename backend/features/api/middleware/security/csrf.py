"""SoAI - Cookie-auth CSRF request hardening helpers [backend/features/api/middleware/security/csrf.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request, Response, status
from starlette.datastructures import MutableHeaders
from starlette.types import Message, Send

from core.auth.cookie_authentication import resolve_cookie_token_candidates
from core.auth.cookies import determine_secure_cookie, resolve_webui_cookie_names, set_csrf_cookie
from core.auth.csrf_tokens import (
    SOAI_CSRF_HEADER_NAME,
    csrf_cookie_is_valid,
    csrf_header_matches_cookie,
)
from core.config.protocols import ConfigProtocol
from core.errors.exceptions import StateError
from core.runtime.proxy_headers import resolve_request_scheme
from features.api.runtime.boundary_error_responses import (
    build_boundary_error_json_response_for_request,
)
from features.api.runtime.context import get_request_trace_id

__all__ = (
    "build_csrf_block_response",
    "build_csrf_cookie_send_wrapper",
    "is_unsafe_browser_method",
    "should_block_cookie_csrf_request",
)

CSRF_BLOCK_MESSAGE = (
    "Cookie-auth browser request was blocked because the CSRF token was missing or invalid."
)
_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_COOKIE_AUTH_METHODS = frozenset({"jwt_cookie", "jwt_cookie_rotation_recovery"})


@dataclass(frozen=True, slots=True)
class _CsrfResponseHeaders:
    cookie_header: str | None
    token_header: str


def is_unsafe_browser_method(method: str) -> bool:
    return str(method or "").upper() in _UNSAFE_METHODS


def _request_auth_method(request: Request) -> str | None:
    try:
        auth_method_value = request.state.auth_method
    except AttributeError:
        auth_method_value = None
    return auth_method_value if isinstance(auth_method_value, str) else None


def should_block_cookie_csrf_request(
    request: Request,
    auth_method: str | None,
    verification_secrets: tuple[str, ...],
) -> bool:
    if auth_method not in _COOKIE_AUTH_METHODS:
        return False
    if not is_unsafe_browser_method(request.method):
        return False
    cookie_names = resolve_webui_cookie_names(resolve_request_scheme(request))
    candidates = resolve_cookie_token_candidates(
        request,
        cookie_name=cookie_names.csrf,
    )
    if len(candidates) != 1:
        return True
    return not csrf_header_matches_cookie(
        candidates[0],
        request.headers.get(SOAI_CSRF_HEADER_NAME),
        secret_keys=verification_secrets,
    )


def build_csrf_block_response(
    request: Request,
    verification_secrets: tuple[str, ...],
) -> Response | None:
    if not should_block_cookie_csrf_request(
        request,
        _request_auth_method(request),
        verification_secrets,
    ):
        return None
    trace_id = get_request_trace_id(request)
    return build_boundary_error_json_response_for_request(
        request,
        status_code=status.HTTP_403_FORBIDDEN,
        message=CSRF_BLOCK_MESSAGE,
        soai_code="csrf_token_missing_or_invalid",
        openai_code="csrf_token_missing_or_invalid",
        trace_id=trace_id,
    )


def _csrf_response_headers(
    request: Request,
    config: ConfigProtocol,
    primary_signing_secret: str,
    verification_secrets: tuple[str, ...],
) -> _CsrfResponseHeaders | None:
    auth_method = _request_auth_method(request)
    if auth_method not in _COOKIE_AUTH_METHODS:
        return None
    cookie_names = resolve_webui_cookie_names(resolve_request_scheme(request))
    candidates = resolve_cookie_token_candidates(
        request,
        cookie_name=cookie_names.csrf,
    )
    csrf_cookie_text = candidates[0] if len(candidates) == 1 else ""
    if csrf_cookie_is_valid(csrf_cookie_text, secret_keys=verification_secrets):
        return _CsrfResponseHeaders(cookie_header=None, token_header=csrf_cookie_text)
    response = Response()
    secure_cookie = determine_secure_cookie(config, request_scheme=resolve_request_scheme(request))
    token = set_csrf_cookie(
        response,
        config,
        cookie_names=cookie_names,
        secret_key=primary_signing_secret,
        secure_cookie=secure_cookie,
    )
    header_value = response.headers.get("set-cookie")
    if header_value is None:
        raise StateError("CSRF cookie header was not generated.")
    return _CsrfResponseHeaders(cookie_header=header_value, token_header=token)


def build_csrf_cookie_send_wrapper(
    send: Send,
    request: Request,
    config: ConfigProtocol,
    primary_signing_secret: str,
    verification_secrets: tuple[str, ...],
) -> Send:
    csrf_headers = _csrf_response_headers(
        request,
        config,
        primary_signing_secret,
        verification_secrets,
    )
    if csrf_headers is None:
        return send

    async def send_wrapper(message: Message) -> None:
        if message.get("type") == "http.response.start":
            if "headers" not in message:
                message["headers"] = []
            headers = MutableHeaders(scope=message)
            if csrf_headers.cookie_header is not None:
                headers.append("set-cookie", csrf_headers.cookie_header)
            headers[SOAI_CSRF_HEADER_NAME] = csrf_headers.token_header
        await send(message)

    return send_wrapper

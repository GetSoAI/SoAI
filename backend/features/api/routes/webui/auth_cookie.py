"""SoAI - Auth cookie setup helper for WebUI routes [backend/features/api/routes/webui/auth_cookie.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request, Response

from core.auth.cookies import (
    determine_secure_cookie,
    resolve_webui_cookie_names,
    set_auth_cookie_record,
)
from core.auth.webui_sessions import (
    ANDROID_DEVICE_COOKIE_NAME,
    WebuiSessionJtiCollisionError,
    WebuiSessionRegistrationResult,
    build_webui_session_descriptor,
)
from core.runtime.proxy_headers import resolve_request_scheme
from features.api.routes.webui.session_successor_credentials import SessionSuccessorAllocator
from features.api.runtime.context import ApiContext
from features.api.runtime.errors import raise_conflict, raise_service_unavailable

__all__ = ("apply_session_cookie",)


async def apply_session_cookie(
    request: Request,
    response: Response,
    api_context: ApiContext,
    user_id: int,
    username: str,
    password_revision: int,
) -> WebuiSessionRegistrationResult:
    scheme = resolve_request_scheme(request)
    cookie_names = resolve_webui_cookie_names(scheme)
    secure_cookie = determine_secure_cookie(api_context.dependencies.config, request_scheme=scheme)
    auth_config = api_context.dependencies.auth_config
    primary_signing_secret = auth_config.primary_signing_secret
    if primary_signing_secret is None:
        raise_service_unavailable(request, "Authentication secret key is not configured.")
    descriptor = build_webui_session_descriptor(
        android_cookie=request.cookies.get(ANDROID_DEVICE_COOKIE_NAME),
        user_agent=request.headers.get("user-agent"),
    )
    successor_allocator = SessionSuccessorAllocator(api_context, None)
    while True:
        token_record = await successor_allocator.create(
            user_id=user_id,
            username=username,
            password_revision=password_revision,
        )
        try:
            registration = (
                await api_context.dependencies.webui_manager.database_tokens.register_session(
                    jti=token_record.jti,
                    expected_user_id=user_id,
                    username=username,
                    expected_password_revision=password_revision,
                    descriptor=descriptor,
                    issued_at_ms=token_record.issued_at_ms,
                    expires_at_ms=token_record.expires_at_ms,
                )
            )
            break
        except WebuiSessionJtiCollisionError:
            continue
    if registration is None:
        raise_conflict(request, "Credentials changed before login completed. Please try again.")
    set_auth_cookie_record(
        response,
        api_context.dependencies.config,
        token_record,
        cookie_names=cookie_names,
        secret_key=primary_signing_secret,
        secure_cookie=secure_cookie,
    )
    return registration

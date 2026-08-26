"""SoAI - WebUI auth guard failure handling helpers [backend/webui/manager/auth_guard_failure_handling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import status

from core.auth.auth_decisions import AuthenticationDecision
from core.auth.auth_guard_throttling import register_auth_guard_failure
from core.runtime.protocols import RequestProtocol
from core.wallpaper.protocols import AuthGuardProtocol
from webui.manager.internal_protocols import AuthFailureLoggerProtocol

__all__ = ("register_failure_and_build_decision",)


async def register_failure_and_build_decision(
    *,
    request: RequestProtocol,
    guard: AuthGuardProtocol,
    log_failure: AuthFailureLoggerProtocol,
    trace_id: str | None,
    auth_method: str,
    message: str,
    reason: str,
    client_ip: str | None,
    bucket_identifiers: tuple[str, ...],
    fingerprint: str | None,
    failure_category: str | None,
) -> AuthenticationDecision:
    throttled, retry_at = await register_auth_guard_failure(guard, bucket_identifiers)
    await log_failure(
        request,
        reason,
        client_ip,
        fingerprint=fingerprint,
        throttled=throttled,
        retry_at=retry_at,
    )
    status_code = status.HTTP_429_TOO_MANY_REQUESTS if throttled else status.HTTP_401_UNAUTHORIZED
    error_message = "Too many authentication failures. Retry later." if throttled else message
    return AuthenticationDecision(
        continue_request=False,
        auth_method=auth_method,
        status_code=status_code,
        error_type="authentication_error",
        error_message=error_message,
        failure_category=failure_category,
        rate_limit_reset=retry_at if throttled else None,
        trace_id=trace_id,
    )

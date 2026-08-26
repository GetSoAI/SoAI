"""SoAI - WebUI login throttling route helpers [backend/features/api/routes/webui/login_throttling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request

from core.auth.auth_failure_buckets import build_webui_login_failure_buckets
from core.auth.auth_guard_throttling import (
    register_auth_guard_failure,
    reset_auth_guard_failures,
    resolve_auth_guard_throttle,
)
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError
from core.logging.trace import get_logger
from core.timing.durations import ms_to_seconds_ceil
from core.timing.epoch import epoch_ms
from core.wallpaper.protocols import AuthGuardProtocol
from features.api.runtime.errors import raise_rate_limit

if TYPE_CHECKING:
    from core.notifications.protocols_database import DatabaseNotificationsProtocol

__all__ = (
    "create_login_throttle_admin_alert_noncritical",
    "enforce_login_throttle",
    "raise_login_rate_limit",
    "record_login_failure",
    "register_login_failure",
    "reset_login_failures",
)

LOGGER_NAME = "SoAI.features.api.login_throttling"
OPERATION_CREATE_LOGIN_THROTTLE_ALERT = "webui.login_throttling.admin_alert"


def raise_login_rate_limit(request: Request, retry_at: int | None) -> None:
    retry_after_ms = max(retry_at - epoch_ms(), 0) if retry_at else 0
    retry_after = ms_to_seconds_ceil(retry_after_ms)
    headers = {"Retry-After": str(retry_after)}
    raise_rate_limit(
        request,
        "Too many login attempts. Please try again later.",
        error_type="rate_limit_exceeded",
        extra={"retry_after_seconds": retry_after},
        headers=headers,
    )


async def enforce_login_throttle(
    request: Request,
    guard: AuthGuardProtocol,
    bucket_identifiers: tuple[str, ...],
) -> None:
    throttled, retry_at = await resolve_auth_guard_throttle(guard, bucket_identifiers)
    if throttled:
        raise_login_rate_limit(request, retry_at)


async def record_login_failure(
    guard: AuthGuardProtocol,
    bucket_identifiers: tuple[str, ...],
) -> tuple[bool, int | None]:
    return await register_auth_guard_failure(guard, bucket_identifiers)


async def create_login_throttle_admin_alert_noncritical(
    database_notifications: DatabaseNotificationsProtocol,
) -> None:
    try:
        await database_notifications.create_login_throttle_admin_alert_if_due()
    except (SoAIError, RuntimeError) as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_CREATE_LOGIN_THROTTLE_ALERT,
        )
        log_exception(
            get_logger(LOGGER_NAME),
            coerced,
            message="Failed to create login throttle admin alert (non-critical).",
            operation=OPERATION_CREATE_LOGIN_THROTTLE_ALERT,
            level="warning",
        )


async def register_login_failure(
    request: Request,
    guard: AuthGuardProtocol,
    bucket_identifiers: tuple[str, ...],
) -> None:
    throttled, retry_at = await record_login_failure(guard, bucket_identifiers)
    if throttled:
        raise_login_rate_limit(request, retry_at)


async def reset_login_failures(
    guard: AuthGuardProtocol,
    client_ip: str,
    username: str | None,
) -> None:
    await reset_auth_guard_failures(
        guard,
        build_webui_login_failure_buckets(client_ip, username),
    )

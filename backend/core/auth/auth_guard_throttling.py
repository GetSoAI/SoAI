"""SoAI - Auth guard throttling helpers [backend/core/auth/auth_guard_throttling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.wallpaper.protocols import AuthGuardProtocol

__all__ = (
    "register_auth_guard_failure",
    "reset_auth_guard_failures",
    "resolve_auth_guard_throttle",
)


async def resolve_auth_guard_throttle(
    guard: AuthGuardProtocol,
    bucket_identifiers: tuple[str, ...],
) -> tuple[bool, int | None]:
    retry_at_values: list[int] = []
    for bucket_identifier in bucket_identifiers:
        throttled, retry_at = await guard.is_throttled(bucket_identifier)
        if not throttled:
            continue
        if retry_at is not None:
            retry_at_values.append(retry_at)
    if not retry_at_values:
        return (False, None)
    return (True, max(retry_at_values))


async def register_auth_guard_failure(
    guard: AuthGuardProtocol,
    bucket_identifiers: tuple[str, ...],
) -> tuple[bool, int | None]:
    throttled = False
    retry_at_values: list[int] = []
    for bucket_identifier in bucket_identifiers:
        bucket_throttled, retry_at = await guard.register_failure(bucket_identifier)
        throttled = throttled or bucket_throttled
        if retry_at is not None:
            retry_at_values.append(retry_at)
    if not throttled:
        return (False, None)
    if not retry_at_values:
        return (True, None)
    return (True, max(retry_at_values))


async def reset_auth_guard_failures(
    guard: AuthGuardProtocol,
    bucket_identifiers: tuple[str, ...],
) -> None:
    for bucket_identifier in bucket_identifiers:
        await guard.reset(bucket_identifier)

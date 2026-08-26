"""SoAI - Bounded identity mutation, status, and recovery attempt throttling [backend/features/api/routes/webui/identity_mutation_throttling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request

from core.wallpaper.protocols import AuthGuardProtocol
from features.api.routes.webui.login_throttling import raise_login_rate_limit
from features.api.runtime.client_host import resolve_client_host
from features.api.runtime.context import ApiContext


def _identity_attempt_buckets(request: Request, actor_or_source: str) -> tuple[str, str]:
    client_ip = resolve_client_host(request, default="") or "unknown"
    return (
        f"identity_mutation_ip:{client_ip}",
        f"identity_mutation_actor:{actor_or_source}",
    )


async def enforce_identity_mutation_attempt_limit(
    request: Request,
    api_context: ApiContext,
    *,
    actor_or_source: str,
) -> None:
    guard: AuthGuardProtocol = api_context.dependencies.webui_manager.identity_mutation_guard
    for bucket in _identity_attempt_buckets(request, actor_or_source):
        throttled, retry_at = await guard.is_throttled(bucket)
        if throttled:
            raise_login_rate_limit(request, retry_at)
    for bucket in _identity_attempt_buckets(request, actor_or_source):
        throttled, retry_at = await guard.register_failure(bucket)
        if throttled:
            raise_login_rate_limit(request, retry_at)


__all__ = ("enforce_identity_mutation_attempt_limit",)

"""SoAI - Ordered WebUI authentication resource locking [backend/features/api/routes/webui/webui_auth_resource_locking.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, asynccontextmanager

from core.concurrency.protocols import AsyncLockRegistryProtocol
from core.users.username import require_canonical_username


def username_auth_resource(username: str) -> str:
    return f"webui_username_auth:{require_canonical_username(username)}"


def session_mutation_resource(jti: str) -> str:
    if not isinstance(jti, str) or not jti:
        raise ValueError("Session mutation resource requires a JTI.")
    return f"webui_session_mutation:{jti}"


def setup_ceremony_resource() -> str:
    return "webui_setup_ceremony"


def licensing_mutation_resource() -> str:
    return "webui_licensing_mutation"


def build_login_auth_resources(
    throttle_buckets: tuple[str, ...],
    username: str,
) -> tuple[str, ...]:
    return (*throttle_buckets, username_auth_resource(username))


@asynccontextmanager
async def lock_webui_auth_resources(
    locks: AsyncLockRegistryProtocol[str],
    resources: tuple[str, ...],
) -> AsyncGenerator[None]:
    ordered_resources = tuple(sorted(set(resources)))
    async with AsyncExitStack() as exit_stack:
        for resource in ordered_resources:
            await exit_stack.enter_async_context(locks.lock(resource))
        yield


__all__ = (
    "build_login_auth_resources",
    "lock_webui_auth_resources",
    "licensing_mutation_resource",
    "session_mutation_resource",
    "setup_ceremony_resource",
    "username_auth_resource",
)

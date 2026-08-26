"""SoAI - Bounded actor password proof for identity mutations [backend/features/api/routes/webui/identity_mutation_password_proof.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time

from fastapi import Request

from core.users.identity_mutation_records import IdentityMutationBinding
from core.users.username_rename import UserIdentitySnapshot
from features.api.routes.webui.login_throttling import (
    create_login_throttle_admin_alert_noncritical,
    enforce_login_throttle,
    raise_login_rate_limit,
    record_login_failure,
    reset_login_failures,
)
from features.api.routes.webui.user_mutation_responses import (
    record_identity_mutation_failure,
)
from features.api.runtime.context import ApiContext


async def verify_identity_mutation_actor_password(
    *,
    request: Request,
    api_context: ApiContext,
    binding: IdentityMutationBinding,
    actor: UserIdentitySnapshot,
    current_password: str,
    deadline_monotonic: float,
    throttle_buckets: tuple[str, ...],
    client_ip: str,
) -> bool:
    guard = api_context.dependencies.webui_manager.webui_login_guard
    await enforce_login_throttle(request, guard, throttle_buckets)
    remaining_seconds = deadline_monotonic - time.monotonic()
    if remaining_seconds <= 0:
        return await record_identity_mutation_failure(
            api_context.dependencies.database_user_mutations,
            binding,
            "identity_mutation_deadline_exceeded",
        )
    password_valid = await api_context.dependencies.login_password_service.verify_password(
        current_password,
        actor.hashed_password,
        timeout_sec=remaining_seconds,
    )
    if not password_valid:
        throttled, retry_at = await record_login_failure(guard, throttle_buckets)
        if throttled:
            await create_login_throttle_admin_alert_noncritical(
                api_context.dependencies.database_notifications
            )
            raise_login_rate_limit(request, retry_at)
        return await record_identity_mutation_failure(
            api_context.dependencies.database_user_mutations,
            binding,
            "incorrect_current_password",
        )
    await reset_login_failures(guard, client_ip, actor.username)
    return False


__all__ = ("verify_identity_mutation_actor_password",)

"""SoAI - Messaging account runtime start failure containment [backend/app/background/messaging_runtime_failure.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from features.messaging.account_runtime_health import (
    record_messaging_account_runtime_health,
)

if TYPE_CHECKING:
    from app.background.messaging_runtime_task_set import (
        MessagingRuntimeSignature,
        MessagingRuntimeTaskSet,
    )
    from core.conversations.conversation_source import MessagingPlatform
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("contain_messaging_runtime_start_failure",)


async def contain_messaging_runtime_start_failure(
    *,
    task_set: MessagingRuntimeTaskSet,
    api_dependencies: ApiDependencies,
    account_id: str,
    platform: MessagingPlatform,
    signature: MessagingRuntimeSignature,
    exception: Exception,
) -> None:
    error = coerce_to_soai_error(
        exception,
        operation="messaging.account.runtime_start",
    )
    await record_messaging_account_runtime_health(
        api_dependencies,
        platform=platform,
        account_id=account_id,
        expected_revision=signature.revision,
        lifecycle_generation=signature.lifecycle_generation,
        healthy=False,
        health_code=str(error.code)[:120],
    )
    task_set.defer_failure(
        account_id=account_id,
        platform=platform,
        signature=signature,
        failure_code=str(error.code),
    )

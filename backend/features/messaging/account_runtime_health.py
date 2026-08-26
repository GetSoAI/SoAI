"""SoAI - Messaging account runtime health projection [backend/features/messaging/account_runtime_health.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.messaging.account_validation import require_messaging_account_fence
from core.validation.record_fields import require_int
from core.validation.strings import coerce_optional_trimmed_str
from features.messaging.account_transition_reporting import (
    read_messaging_ownership_state,
    report_messaging_account_transition,
)

if TYPE_CHECKING:
    from core.conversations.conversation_source import MessagingPlatform
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("record_messaging_account_runtime_health",)

OPERATION_RUNTIME_HEALTH = "messaging.account.runtime_health"


async def record_messaging_account_runtime_health(
    api_dependencies: ApiDependencies,
    *,
    platform: MessagingPlatform,
    account_id: str,
    expected_revision: int,
    lifecycle_generation: int,
    healthy: bool,
    health_code: str | None,
) -> None:
    repository = api_dependencies.database_messaging_accounts
    account = await repository.get_transport_account(account_id, platform)
    if account is None or account.get("lifecycle_state") in ("disabled", "deleting"):
        return
    fence = require_messaging_account_fence(account)
    result = await repository.record_reconciliation(
        user_id=fence.user_id,
        account_id=account_id,
        expected_revision=require_int(
            expected_revision,
            label="Expected Messaging account revision",
            build_error=StateError,
            minimum=1,
        ),
        lifecycle_generation=require_int(
            lifecycle_generation,
            label="Expected Messaging account lifecycle generation",
            build_error=StateError,
            minimum=0,
        ),
        healthy=healthy,
        callback_fingerprint=coerce_optional_trimmed_str(
            account.get("installed_callback_fingerprint"),
        ),
        ownership_state=read_messaging_ownership_state(account),
        health_code=health_code,
    )
    report_messaging_account_transition(
        operation=OPERATION_RUNTIME_HEALTH,
        platform=platform,
        account_id=account_id,
        before=result.before if result is not None else account,
        after=result.after if result is not None else None,
    )

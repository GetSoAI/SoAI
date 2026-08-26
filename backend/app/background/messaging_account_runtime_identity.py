"""SoAI - Messaging account runtime identity validation [backend/app/background/messaging_account_runtime_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.background.messaging_runtime_task_set import MessagingRuntimeSignature
from core.errors.exceptions import StateError
from core.messaging.account_validation import require_messaging_account_fence

if TYPE_CHECKING:
    from core.conversations.conversation_source import MessagingPlatform
    from core.types.json import JSONDict

__all__ = (
    "MessagingAccountRuntimeIdentity",
    "require_messaging_runtime_identity",
)


@dataclass(frozen=True, slots=True)
class MessagingAccountRuntimeIdentity:
    account_id: str
    user_id: int
    signature: MessagingRuntimeSignature


def require_messaging_runtime_identity(
    account: JSONDict,
    platform: MessagingPlatform,
) -> MessagingAccountRuntimeIdentity:
    fence = require_messaging_account_fence(account)
    if fence.platform != platform:
        raise StateError("Messaging account runtime identity is invalid.")
    return MessagingAccountRuntimeIdentity(
        account_id=fence.account_id,
        user_id=fence.user_id,
        signature=MessagingRuntimeSignature(
            revision=fence.revision,
            lifecycle_generation=fence.lifecycle_generation,
            configuration_fingerprint="",
        ),
    )

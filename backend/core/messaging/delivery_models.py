"""SoAI - Messaging provider delivery contracts [backend/core/messaging/delivery_models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Literal

    from core.conversations.conversation_source import MessagingPlatform

    type MessagingProviderSendState = Literal[
        "sent",
        "retryable",
        "failed",
        "delivery_unknown",
    ]

__all__ = (
    "MESSAGING_DELIVERY_CLAIM_OWNER",
    "MessagingDeliveryAttempt",
    "MessagingProviderSendOutcome",
)

MESSAGING_DELIVERY_CLAIM_OWNER = "delivery-worker"


@dataclass(frozen=True, slots=True)
class MessagingDeliveryAttempt:
    delivery_id: str
    claim_generation: int
    ordinal: int
    content_text: str
    chunk_attempt_count: int
    account_id: str
    account_generation: int
    user_id: int
    platform: MessagingPlatform
    remote_thread_type: str
    remote_thread_key: str
    binding_generation: int
    originating_sender_id: str


@dataclass(frozen=True, slots=True)
class MessagingProviderSendOutcome:
    state: MessagingProviderSendState
    provider_message_id: str | None
    failure_code: str | None
    retry_after_ms: int | None
    next_request_delay_ms: int | None

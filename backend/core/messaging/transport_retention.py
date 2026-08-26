"""SoAI - Messaging transport retention policy [backend/core/messaging/transport_retention.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.conversations.conversation_source import MessagingPlatform
    from core.messaging.ingress_models import NormalizedMessagingEvent

__all__ = (
    "messaging_event_exceeds_accepted_age",
    "messaging_transport_retention_cutoff_ms",
)

MILLISECONDS_PER_DAY = 24 * 60 * 60 * 1000


def _transport_retention_ms(platform: MessagingPlatform) -> int:
    if platform == "telegram":
        return 2 * MILLISECONDS_PER_DAY
    if platform == "whatsapp":
        return 8 * MILLISECONDS_PER_DAY
    return MILLISECONDS_PER_DAY


def messaging_transport_retention_cutoff_ms(
    platform: MessagingPlatform,
    now_ms: int,
) -> int:
    return max(0, now_ms - _transport_retention_ms(platform))


def messaging_event_exceeds_accepted_age(
    event: NormalizedMessagingEvent,
    now_ms: int,
) -> bool:
    timestamp_ms = event.provider_timestamp_ms
    if timestamp_ms is None:
        return False
    return timestamp_ms < messaging_transport_retention_cutoff_ms(event.platform, now_ms)

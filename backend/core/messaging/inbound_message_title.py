"""SoAI - Inbound messaging thread title formatting [backend/core/messaging/inbound_message_title.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.messaging.ingress_models import NormalizedMessagingEvent

__all__ = ("build_inbound_message_title",)


def build_inbound_message_title(message: NormalizedMessagingEvent) -> str:
    sender_name = message.sender_display_name or message.sender_id
    return f"{message.platform.title()} {sender_name}"

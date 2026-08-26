"""SoAI - Typed Messaging ingress contracts [backend/core/messaging/ingress_models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.types.json import JSONDict, JSONValue

if TYPE_CHECKING:
    from typing import Literal

    from core.conversations.conversation_source import MessagingPlatform

    type MessagingIngressClassification = Literal[
        "prompt",
        "control",
        "interaction",
        "protocol",
        "unsupported",
    ]
    type RemoteThreadType = Literal["private", "group", "channel"]
    type MessagingReceiptStatus = Literal["sent", "delivered", "read", "failed"]

__all__ = (
    "MessagingMediaDescriptor",
    "NormalizedMessagingEvent",
    "normalize_messaging_receipt_status",
)


def normalize_messaging_receipt_status(value: JSONValue) -> MessagingReceiptStatus | None:
    if value == "sent":
        return "sent"
    if value == "delivered":
        return "delivered"
    if value == "read":
        return "read"
    if value == "failed":
        return "failed"
    return None


@dataclass(frozen=True, slots=True)
class MessagingMediaDescriptor:
    provider_media_id: str
    media_type: str
    filename: str | None
    mime_type: str | None
    size_bytes: int | None

    def to_payload(self) -> JSONDict:
        return {
            "provider_media_id": self.provider_media_id,
            "media_type": self.media_type,
            "filename": self.filename,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True, slots=True)
class NormalizedMessagingEvent:
    platform: MessagingPlatform
    provider_event_id: str
    provider_principal_id: str | None
    remote_thread_type: RemoteThreadType
    remote_thread_key: str
    classification: MessagingIngressClassification
    sender_id: str | None
    sender_display_name: str | None
    text: str
    provider_message_id: str | None
    reply_to_provider_message_id: str | None
    media: tuple[MessagingMediaDescriptor, ...] = field(default_factory=tuple)
    discord_dispatch_sequence: int | None = None
    provider_timestamp_ms: int | None = None
    receipt_status: MessagingReceiptStatus | None = None

    def source_metadata(self) -> JSONDict:
        return {
            "platform": self.platform,
            "sender_id": self.sender_id,
            "sender_display_name": self.sender_display_name,
            "provider_message_id": self.provider_message_id,
            "reply_to_provider_message_id": self.reply_to_provider_message_id,
            "remote_thread_type": self.remote_thread_type,
            "remote_thread_key": self.remote_thread_key,
        }

    def fingerprint_payload(self) -> JSONDict:
        return {
            "platform": self.platform,
            "provider_event_id": self.provider_event_id,
            "provider_principal_id": self.provider_principal_id,
            "remote_thread_type": self.remote_thread_type,
            "remote_thread_key": self.remote_thread_key,
            "classification": self.classification,
            "sender_id": self.sender_id,
            "text": self.text,
            "provider_message_id": self.provider_message_id,
            "reply_to_provider_message_id": self.reply_to_provider_message_id,
            "provider_timestamp_ms": self.provider_timestamp_ms,
            "receipt_status": self.receipt_status,
            "media": [descriptor.to_payload() for descriptor in self.media],
        }

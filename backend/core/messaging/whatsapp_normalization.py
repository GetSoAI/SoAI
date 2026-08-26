"""SoAI - WhatsApp webhook normalization [backend/core/messaging/whatsapp_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.messaging.inbound_content import (
    bounded_trimmed_text,
    provider_epoch_seconds_ms,
    trimmed_text,
)
from core.messaging.ingress_models import (
    MessagingMediaDescriptor,
    NormalizedMessagingEvent,
    normalize_messaging_receipt_status,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("normalize_whatsapp_webhook_payload",)

WHATSAPP_MAX_TEXT_LENGTH = 4_096
WHATSAPP_MAX_CAPTION_LENGTH = 1_024
WHATSAPP_MAX_BATCH_EVENTS = 101


def _contact_name(value_payload: JSONDict) -> str | None:
    contacts = value_payload.get("contacts")
    if not isinstance(contacts, list) or not contacts or not isinstance(contacts[0], dict):
        return None
    profile = contacts[0].get("profile")
    return bounded_trimmed_text(profile.get("name"), 255) if isinstance(profile, dict) else None


def _principal_id(value_payload: JSONDict) -> str | None:
    metadata = value_payload.get("metadata")
    if not isinstance(metadata, dict):
        return None
    return bounded_trimmed_text(metadata.get("phone_number_id"), 255)


def _message_text(message: JSONDict) -> str:
    message_type = trimmed_text(message.get("type"))
    typed_payload = message.get(message_type or "")
    if message_type == "text" and isinstance(typed_payload, dict):
        return bounded_trimmed_text(typed_payload.get("body"), WHATSAPP_MAX_TEXT_LENGTH) or ""
    if isinstance(typed_payload, dict):
        return (
            bounded_trimmed_text(
                typed_payload.get("caption"),
                WHATSAPP_MAX_CAPTION_LENGTH,
            )
            or ""
        )
    return ""


def _message_media(message: JSONDict) -> tuple[MessagingMediaDescriptor, ...]:
    message_type = trimmed_text(message.get("type"))
    if message_type not in {"image", "document", "audio", "video", "sticker"}:
        return ()
    typed_payload = message.get(message_type)
    if not isinstance(typed_payload, dict):
        return ()
    media_id = bounded_trimmed_text(typed_payload.get("id"), 255)
    if media_id is None:
        return ()
    filename = bounded_trimmed_text(typed_payload.get("filename"), 512)
    return (
        MessagingMediaDescriptor(
            provider_media_id=media_id,
            media_type="image" if message_type == "sticker" else message_type,
            filename=filename,
            mime_type=bounded_trimmed_text(typed_payload.get("mime_type"), 255),
            size_bytes=None,
        ),
    )


def _message_event(
    value_payload: JSONDict,
    message: JSONDict,
    *,
    principal_id: str,
) -> NormalizedMessagingEvent | None:
    message_id = bounded_trimmed_text(message.get("id"), 512)
    sender_id = bounded_trimmed_text(message.get("from"), 255)
    if message_id is None or sender_id is None:
        return None
    media = _message_media(message)
    text = _message_text(message)
    supported = bool(text or media)
    context = message.get("context")
    reply_id = bounded_trimmed_text(context.get("id"), 512) if isinstance(context, dict) else None
    return NormalizedMessagingEvent(
        platform="whatsapp",
        provider_event_id=message_id,
        provider_principal_id=principal_id,
        remote_thread_type="private",
        remote_thread_key=sender_id,
        classification="prompt" if supported else "unsupported",
        sender_id=sender_id,
        sender_display_name=_contact_name(value_payload),
        text=text,
        provider_message_id=message_id,
        reply_to_provider_message_id=reply_id,
        media=media,
        provider_timestamp_ms=provider_epoch_seconds_ms(message.get("timestamp")),
    )


def _status_event(
    status_payload: JSONDict,
    *,
    principal_id: str,
) -> NormalizedMessagingEvent | None:
    status_id = bounded_trimmed_text(status_payload.get("id"), 512)
    recipient_id = bounded_trimmed_text(status_payload.get("recipient_id"), 255)
    status = bounded_trimmed_text(status_payload.get("status"), 64)
    if status_id is None or recipient_id is None or status is None:
        return None
    receipt_status = normalize_messaging_receipt_status(status)
    return NormalizedMessagingEvent(
        platform="whatsapp",
        provider_event_id=f"status:{status_id}:{status}",
        provider_principal_id=principal_id,
        remote_thread_type="private",
        remote_thread_key=recipient_id,
        classification="protocol" if receipt_status is not None else "unsupported",
        sender_id=None,
        sender_display_name=None,
        text="",
        provider_message_id=status_id,
        reply_to_provider_message_id=None,
        provider_timestamp_ms=provider_epoch_seconds_ms(status_payload.get("timestamp")),
        receipt_status=receipt_status,
    )


def _normalize_value(value_payload: JSONDict) -> list[NormalizedMessagingEvent]:
    principal_id = _principal_id(value_payload)
    if principal_id is None:
        return []
    events: list[NormalizedMessagingEvent] = []
    messages = value_payload.get("messages")
    if isinstance(messages, list):
        for message in messages:
            if isinstance(message, dict):
                event = _message_event(value_payload, message, principal_id=principal_id)
                if event is not None:
                    events.append(event)
                    if len(events) >= WHATSAPP_MAX_BATCH_EVENTS:
                        return events
    statuses = value_payload.get("statuses")
    if isinstance(statuses, list):
        for status_payload in statuses:
            if isinstance(status_payload, dict):
                event = _status_event(status_payload, principal_id=principal_id)
                if event is not None:
                    events.append(event)
                    if len(events) >= WHATSAPP_MAX_BATCH_EVENTS:
                        return events
    return events


def normalize_whatsapp_webhook_payload(payload: JSONDict) -> tuple[NormalizedMessagingEvent, ...]:
    entries = payload.get("entry")
    if not isinstance(entries, list):
        return ()
    events: list[NormalizedMessagingEvent] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        changes = entry.get("changes")
        if not isinstance(changes, list):
            continue
        for change in changes:
            value = change.get("value") if isinstance(change, dict) else None
            if isinstance(value, dict):
                events.extend(_normalize_value(value))
                if len(events) >= WHATSAPP_MAX_BATCH_EVENTS:
                    return tuple(events[:WHATSAPP_MAX_BATCH_EVENTS])
    return tuple(events)

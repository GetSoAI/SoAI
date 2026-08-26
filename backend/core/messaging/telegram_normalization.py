"""SoAI - Telegram webhook normalization [backend/core/messaging/telegram_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.messaging.inbound_content import (
    bounded_trimmed_text,
    identifier_text,
    provider_epoch_seconds_ms,
    trimmed_text,
)
from core.messaging.ingress_models import (
    MessagingMediaDescriptor,
    NormalizedMessagingEvent,
)

if TYPE_CHECKING:
    from core.messaging.ingress_models import MessagingIngressClassification, RemoteThreadType
    from core.types.json import JSONDict, JSONValue

__all__ = ("normalize_telegram_update",)

TELEGRAM_MAX_TEXT_LENGTH = 4_096
TELEGRAM_MAX_CAPTION_LENGTH = 1_024
TELEGRAM_MAX_PHOTO_SIZES = 20


def _bounded_identifier(value: JSONValue, maximum_length: int) -> str | None:
    normalized = identifier_text(value)
    if normalized is None or len(normalized) > maximum_length:
        return None
    return normalized


def _thread_type(chat_payload: JSONDict) -> RemoteThreadType:
    chat_type = trimmed_text(chat_payload.get("type"))
    if chat_type == "private":
        return "private"
    if chat_type in {"group", "supergroup"}:
        return "group"
    return "channel"


def _reply_id(message_payload: JSONDict) -> str | None:
    reply_payload = message_payload.get("reply_to_message")
    if not isinstance(reply_payload, dict):
        return None
    return _bounded_identifier(reply_payload.get("message_id"), 512)


def _file_descriptor(
    payload: JSONDict,
    *,
    media_type: str,
    fallback_filename: str | None,
) -> MessagingMediaDescriptor | None:
    file_id = bounded_trimmed_text(payload.get("file_id"), 255)
    if file_id is None:
        return None
    size_value = payload.get("file_size")
    size_bytes = (
        size_value if isinstance(size_value, int) and not isinstance(size_value, bool) else None
    )
    return MessagingMediaDescriptor(
        provider_media_id=file_id,
        media_type=media_type,
        filename=bounded_trimmed_text(payload.get("file_name"), 512) or fallback_filename,
        mime_type=bounded_trimmed_text(payload.get("mime_type"), 255),
        size_bytes=size_bytes,
    )


def _media(message_payload: JSONDict) -> tuple[MessagingMediaDescriptor, ...]:
    photo_payload = message_payload.get("photo")
    if isinstance(photo_payload, list) and len(photo_payload) <= TELEGRAM_MAX_PHOTO_SIZES:
        photos = [entry for entry in photo_payload if isinstance(entry, dict)]
        if photos:
            descriptor = _file_descriptor(
                photos[-1],
                media_type="image",
                fallback_filename="telegram-photo.jpg",
            )
            return (descriptor,) if descriptor is not None else ()
    descriptors: list[MessagingMediaDescriptor] = []
    for field_name, media_type, fallback_filename in (
        ("document", "document", None),
        ("audio", "audio", "telegram-audio"),
        ("voice", "audio", "telegram-voice.ogg"),
        ("video", "video", "telegram-video"),
    ):
        value = message_payload.get(field_name)
        if not isinstance(value, dict):
            continue
        descriptor = _file_descriptor(
            value,
            media_type=media_type,
            fallback_filename=fallback_filename,
        )
        if descriptor is not None:
            descriptors.append(descriptor)
    return tuple(descriptors)


def _sender_name(sender_payload: JSONDict) -> str | None:
    username = bounded_trimmed_text(sender_payload.get("username"), 255)
    if username is not None:
        return username
    names = tuple(
        value
        for value in (
            bounded_trimmed_text(sender_payload.get("first_name"), 128),
            bounded_trimmed_text(sender_payload.get("last_name"), 128),
        )
        if value is not None
    )
    return " ".join(names) or None


def _message_event(
    *,
    update_id: str,
    message_payload: JSONDict,
    edited: bool,
) -> NormalizedMessagingEvent | None:
    chat_payload = message_payload.get("chat")
    sender_payload = message_payload.get("from")
    if not isinstance(chat_payload, dict) or not isinstance(sender_payload, dict):
        return None
    thread_key = _bounded_identifier(chat_payload.get("id"), 512)
    sender_id = _bounded_identifier(sender_payload.get("id"), 255)
    message_id = _bounded_identifier(message_payload.get("message_id"), 512)
    if thread_key is None or sender_id is None or message_id is None:
        return None
    media = _media(message_payload)
    text = (
        bounded_trimmed_text(
            message_payload.get("text"),
            TELEGRAM_MAX_TEXT_LENGTH,
        )
        or bounded_trimmed_text(
            message_payload.get("caption"),
            TELEGRAM_MAX_CAPTION_LENGTH,
        )
        or ""
    )
    classification: MessagingIngressClassification = (
        "unsupported" if edited or (not text and not media) else "prompt"
    )
    if sender_payload.get("is_bot") is True:
        classification = "protocol"
    return NormalizedMessagingEvent(
        platform="telegram",
        provider_event_id=update_id,
        provider_principal_id=None,
        remote_thread_type=_thread_type(chat_payload),
        remote_thread_key=thread_key,
        classification=classification,
        sender_id=sender_id,
        sender_display_name=_sender_name(sender_payload),
        text=text,
        provider_message_id=message_id,
        reply_to_provider_message_id=_reply_id(message_payload),
        media=media,
        provider_timestamp_ms=provider_epoch_seconds_ms(message_payload.get("date")),
    )


def _unsupported_update(update_id: str) -> NormalizedMessagingEvent:
    return NormalizedMessagingEvent(
        platform="telegram",
        provider_event_id=update_id,
        provider_principal_id=None,
        remote_thread_type="private",
        remote_thread_key="unknown",
        classification="unsupported",
        sender_id=None,
        sender_display_name=None,
        text="",
        provider_message_id=None,
        reply_to_provider_message_id=None,
    )


def normalize_telegram_update(payload: JSONDict) -> tuple[NormalizedMessagingEvent, ...]:
    update_id = _bounded_identifier(payload.get("update_id"), 512)
    if update_id is None:
        return ()
    message_payload_value: JSONValue = payload.get("message")
    if isinstance(message_payload_value, dict):
        event = _message_event(
            update_id=update_id,
            message_payload=message_payload_value,
            edited=False,
        )
        return (event if event is not None else _unsupported_update(update_id),)
    edited_payload = payload.get("edited_message")
    if isinstance(edited_payload, dict):
        event = _message_event(
            update_id=update_id,
            message_payload=edited_payload,
            edited=True,
        )
        return (event if event is not None else _unsupported_update(update_id),)
    return (_unsupported_update(update_id),)

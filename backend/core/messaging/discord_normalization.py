"""SoAI - Discord Gateway Dispatch normalization [backend/core/messaging/discord_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from core.messaging.inbound_content import bounded_trimmed_text, trimmed_text
from core.messaging.ingress_models import MessagingMediaDescriptor, NormalizedMessagingEvent

if TYPE_CHECKING:
    from core.messaging.ingress_models import MessagingIngressClassification
    from core.types.json import JSONDict

__all__ = ("normalize_discord_gateway_dispatch",)

DISCORD_MAX_TEXT_LENGTH = 2_000
DISCORD_MAX_ATTACHMENTS = 10
DISCORD_EPOCH_MS = 1_420_070_400_000


def _dispatch_sequence(payload: JSONDict) -> int | None:
    value = payload.get("s")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _snowflake_timestamp_ms(value: str) -> int | None:
    if not value.isdigit():
        return None
    timestamp_ms = (int(value) >> 22) + DISCORD_EPOCH_MS
    return timestamp_ms if timestamp_ms >= DISCORD_EPOCH_MS else None


def _mentioned_bot_ids(data: JSONDict) -> frozenset[str]:
    mentions = data.get("mentions")
    if not isinstance(mentions, list):
        return frozenset()
    bot_ids: set[str] = set()
    for mention in mentions:
        if not isinstance(mention, dict) or mention.get("bot") is not True:
            continue
        bot_id = bounded_trimmed_text(mention.get("id"), 255)
        if bot_id is not None:
            bot_ids.add(bot_id)
    return frozenset(bot_ids)


def _strip_leading_address_mentions(text: str, data: JSONDict) -> str:
    normalized = text
    bot_ids = _mentioned_bot_ids(data)
    while normalized:
        role_match = re.match(r"^<@&[0-9]{1,32}>(?:\s+|$)", normalized)
        if role_match is not None:
            normalized = normalized[role_match.end() :].lstrip()
            continue
        user_match = re.match(r"^<@!?([0-9]{1,32})>(?:\s+|$)", normalized)
        if user_match is not None and user_match.group(1) in bot_ids:
            normalized = normalized[user_match.end() :].lstrip()
            continue
        break
    return normalized


def _media(data: JSONDict) -> tuple[MessagingMediaDescriptor, ...]:
    attachments = data.get("attachments")
    if not isinstance(attachments, list) or len(attachments) > DISCORD_MAX_ATTACHMENTS:
        return ()
    descriptors: list[MessagingMediaDescriptor] = []
    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue
        attachment_id = bounded_trimmed_text(attachment.get("id"), 255)
        if attachment_id is None:
            continue
        size_value = attachment.get("size")
        size_bytes = (
            size_value if isinstance(size_value, int) and not isinstance(size_value, bool) else None
        )
        mime_type = bounded_trimmed_text(attachment.get("content_type"), 255)
        descriptors.append(
            MessagingMediaDescriptor(
                provider_media_id=attachment_id,
                media_type=(mime_type.split("/", maxsplit=1)[0] if mime_type else "document"),
                filename=bounded_trimmed_text(attachment.get("filename"), 255),
                mime_type=mime_type,
                size_bytes=size_bytes,
            ),
        )
    return tuple(descriptors)


def _unsupported_dispatch(
    *,
    sequence: int,
    thread_key: str,
) -> tuple[NormalizedMessagingEvent, ...]:
    return (
        NormalizedMessagingEvent(
            platform="discord",
            provider_event_id=f"dispatch:{sequence}",
            provider_principal_id=None,
            remote_thread_type="channel",
            remote_thread_key=thread_key,
            classification="unsupported",
            sender_id=None,
            sender_display_name=None,
            text="",
            provider_message_id=None,
            reply_to_provider_message_id=None,
            discord_dispatch_sequence=sequence,
        ),
    )


def normalize_discord_gateway_dispatch(
    payload: JSONDict,
) -> tuple[NormalizedMessagingEvent, ...]:
    sequence = _dispatch_sequence(payload)
    event_type = trimmed_text(payload.get("t"))
    if sequence is None or event_type is None:
        return ()
    data = payload.get("d")
    if not isinstance(data, dict):
        return _unsupported_dispatch(sequence=sequence, thread_key="unknown")
    thread_key = bounded_trimmed_text(data.get("channel_id"), 512) or "unknown"
    if event_type != "MESSAGE_CREATE":
        return (
            NormalizedMessagingEvent(
                platform="discord",
                provider_event_id=f"dispatch:{sequence}",
                provider_principal_id=None,
                remote_thread_type="channel",
                remote_thread_key=thread_key,
                classification=(
                    "protocol" if event_type in {"READY", "RESUMED"} else "unsupported"
                ),
                sender_id=None,
                sender_display_name=None,
                text="",
                provider_message_id=None,
                reply_to_provider_message_id=None,
                discord_dispatch_sequence=sequence,
            ),
        )
    author = data.get("author")
    if not isinstance(author, dict):
        return _unsupported_dispatch(sequence=sequence, thread_key=thread_key)
    message_id = bounded_trimmed_text(data.get("id"), 512)
    sender_id = bounded_trimmed_text(author.get("id"), 255)
    if message_id is None or sender_id is None:
        return _unsupported_dispatch(sequence=sequence, thread_key=thread_key)
    media = _media(data)
    raw_text = data.get("content")
    bounded_text = bounded_trimmed_text(raw_text, DISCORD_MAX_TEXT_LENGTH) or ""
    text = _strip_leading_address_mentions(bounded_text, data)
    reference = data.get("message_reference")
    reply_id = (
        bounded_trimmed_text(reference.get("message_id"), 512)
        if isinstance(reference, dict)
        else None
    )
    classification: MessagingIngressClassification = "prompt" if text or media else "unsupported"
    if isinstance(raw_text, str) and len(raw_text.strip()) > DISCORD_MAX_TEXT_LENGTH:
        classification = "unsupported"
    attachments = data.get("attachments")
    if isinstance(attachments, list) and len(attachments) > DISCORD_MAX_ATTACHMENTS:
        classification = "unsupported"
    if author.get("bot") is True:
        classification = "protocol"
    return (
        NormalizedMessagingEvent(
            platform="discord",
            provider_event_id=message_id,
            provider_principal_id=None,
            remote_thread_type="private" if data.get("guild_id") is None else "channel",
            remote_thread_key=thread_key,
            classification=classification,
            sender_id=sender_id,
            sender_display_name=(
                bounded_trimmed_text(author.get("global_name"), 255)
                or bounded_trimmed_text(author.get("username"), 255)
            ),
            text=text,
            provider_message_id=message_id,
            reply_to_provider_message_id=reply_id,
            media=media,
            discord_dispatch_sequence=sequence,
            provider_timestamp_ms=_snowflake_timestamp_ms(message_id),
        ),
    )

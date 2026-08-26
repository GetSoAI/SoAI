"""SoAI - Provider media metadata resolution [backend/features/messaging/provider_media_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import quote

import httpx2

from core.errors.exceptions import ValidationError
from core.messaging.credential_fields import (
    require_messaging_credential,
    require_whatsapp_access_token,
    require_whatsapp_api_version,
)
from core.validation.strings import coerce_optional_trimmed_str
from features.messaging.provider_json_request import request_messaging_provider_json
from features.messaging.provider_media_stream import (
    ProviderMediaStream,
    open_provider_media_stream,
)

if TYPE_CHECKING:
    from core.conversations.conversation_source import MessagingPlatform
    from core.runtime.protocols import RuntimeFlagsViewProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "ResolvedProviderMedia",
    "resolve_discord_media",
    "resolve_telegram_media",
    "resolve_whatsapp_media",
)

OPERATION_MEDIA_METADATA = "messaging.provider.media_metadata"


@dataclass(slots=True)
class ResolvedProviderMedia:
    stream: ProviderMediaStream
    filename: str
    mime_type: str | None
    declared_size: int | None

    async def close(self) -> None:
        await self.stream.close()


def _require_text(value: JSONValue, label: str, maximum_length: int = 512) -> str:
    normalized = coerce_optional_trimmed_str(value)
    if normalized is None or len(normalized) > maximum_length:
        raise ValidationError(f"{label} is invalid.")
    return normalized


def _optional_size(value: JSONValue, label: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError(f"{label} is invalid.")
    return value


def _resolve_declared_size(
    descriptor_size: int | None,
    provider_size: int | None,
) -> int | None:
    if (
        descriptor_size is not None
        and provider_size is not None
        and descriptor_size != provider_size
    ):
        raise ValidationError("Messaging provider media size changed after admission.")
    return provider_size if provider_size is not None else descriptor_size


async def _get_provider_json(
    http_client: httpx2.AsyncClient,
    url: str,
    *,
    platform: MessagingPlatform,
    headers: dict[str, str] | None = None,
) -> JSONDict:
    return await request_messaging_provider_json(
        http_client,
        method="GET",
        url=url,
        operation_label="Messaging provider media metadata",
        operation=OPERATION_MEDIA_METADATA,
        platform=platform,
        headers=headers,
    )


async def resolve_telegram_media(
    *,
    http_client: httpx2.AsyncClient,
    runtime_flags: RuntimeFlagsViewProtocol,
    credentials: JSONDict,
    descriptor: JSONDict,
    max_bytes: int,
) -> ResolvedProviderMedia:
    bot_token = require_messaging_credential(
        credentials,
        "bot_token",
        "Telegram bot token",
        maximum_length=512,
    )
    media_id = _require_text(descriptor.get("provider_media_id"), "Telegram media id", 255)
    payload = await _get_provider_json(
        http_client,
        f"https://api.telegram.org/bot{quote(bot_token, safe=':')}/getFile?file_id={quote(media_id, safe='')}",
        platform="telegram",
    )
    if payload.get("ok") is not True:
        raise ValidationError("Telegram rejected media metadata access.")
    result = payload.get("result")
    if not isinstance(result, dict):
        raise ValidationError("Telegram media metadata is invalid.")
    file_path = _require_text(result.get("file_path"), "Telegram media path", 1024)
    if file_path.startswith("/") or ".." in file_path.split("/"):
        raise ValidationError("Telegram media path is invalid.")
    provider_size = _optional_size(result.get("file_size"), "Telegram media size")
    stream = await open_provider_media_stream(
        http_client=http_client,
        runtime_flags=runtime_flags,
        url=f"https://api.telegram.org/file/bot{quote(bot_token, safe=':')}/{file_path}",
        allowed_host_suffixes=("api.telegram.org",),
        headers=None,
        max_bytes=max_bytes,
    )
    return ResolvedProviderMedia(
        stream=stream,
        filename=_require_text(
            descriptor.get("filename") or file_path.rsplit("/", maxsplit=1)[-1],
            "Telegram media filename",
        ),
        mime_type=coerce_optional_trimmed_str(descriptor.get("mime_type")) or stream.content_type,
        declared_size=_resolve_declared_size(
            _optional_size(descriptor.get("size_bytes"), "Telegram admitted media size"),
            provider_size if provider_size is not None else stream.declared_size,
        ),
    )


async def resolve_whatsapp_media(
    *,
    http_client: httpx2.AsyncClient,
    runtime_flags: RuntimeFlagsViewProtocol,
    credentials: JSONDict,
    descriptor: JSONDict,
    max_bytes: int,
) -> ResolvedProviderMedia:
    access_token = require_whatsapp_access_token(credentials)
    api_version = require_whatsapp_api_version(credentials)
    media_id = _require_text(descriptor.get("provider_media_id"), "WhatsApp media id", 255)
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = await _get_provider_json(
        http_client,
        f"https://graph.facebook.com/{api_version}/{quote(media_id, safe='')}",
        platform="whatsapp",
        headers=headers,
    )
    media_url = _require_text(payload.get("url"), "WhatsApp media URL", 2048)
    provider_size = _optional_size(payload.get("file_size"), "WhatsApp media size")
    stream = await open_provider_media_stream(
        http_client=http_client,
        runtime_flags=runtime_flags,
        url=media_url,
        allowed_host_suffixes=("facebook.com", "fbsbx.com"),
        headers=headers,
        max_bytes=max_bytes,
    )
    return ResolvedProviderMedia(
        stream=stream,
        filename=_require_text(
            descriptor.get("filename") or media_id,
            "WhatsApp media filename",
        ),
        mime_type=(
            coerce_optional_trimmed_str(payload.get("mime_type"))
            or coerce_optional_trimmed_str(descriptor.get("mime_type"))
            or stream.content_type
        ),
        declared_size=_resolve_declared_size(
            _optional_size(descriptor.get("size_bytes"), "WhatsApp admitted media size"),
            provider_size if provider_size is not None else stream.declared_size,
        ),
    )


async def resolve_discord_media(
    *,
    http_client: httpx2.AsyncClient,
    runtime_flags: RuntimeFlagsViewProtocol,
    credentials: JSONDict,
    descriptor: JSONDict,
    source_metadata: JSONDict,
    max_bytes: int,
) -> ResolvedProviderMedia:
    bot_token = require_messaging_credential(
        credentials,
        "bot_token",
        "Discord bot token",
        maximum_length=2048,
    )
    channel_id = _require_text(source_metadata.get("remote_thread_key"), "Discord channel id")
    message_id = _require_text(source_metadata.get("provider_message_id"), "Discord message id")
    media_id = _require_text(descriptor.get("provider_media_id"), "Discord attachment id", 255)
    headers = {"Authorization": f"Bot {bot_token}"}
    payload = await _get_provider_json(
        http_client,
        f"https://discord.com/api/v10/channels/{quote(channel_id, safe='')}/messages/{quote(message_id, safe='')}",
        platform="discord",
        headers=headers,
    )
    attachments = payload.get("attachments")
    if not isinstance(attachments, list) or len(attachments) > 10:
        raise ValidationError("Discord attachment metadata is invalid.")
    matching = next(
        (
            attachment
            for attachment in attachments
            if isinstance(attachment, dict) and str(attachment.get("id") or "") == media_id
        ),
        None,
    )
    if not isinstance(matching, dict):
        raise ValidationError("Discord attachment is no longer available.")
    provider_size = _optional_size(matching.get("size"), "Discord media size")
    stream = await open_provider_media_stream(
        http_client=http_client,
        runtime_flags=runtime_flags,
        url=_require_text(matching.get("url"), "Discord media URL", 2048),
        allowed_host_suffixes=("cdn.discordapp.com", "media.discordapp.net"),
        headers=None,
        max_bytes=max_bytes,
    )
    return ResolvedProviderMedia(
        stream=stream,
        filename=_require_text(
            matching.get("filename") or descriptor.get("filename") or media_id,
            "Discord media filename",
        ),
        mime_type=(
            coerce_optional_trimmed_str(matching.get("content_type"))
            or coerce_optional_trimmed_str(descriptor.get("mime_type"))
            or stream.content_type
        ),
        declared_size=_resolve_declared_size(
            _optional_size(descriptor.get("size_bytes"), "Discord admitted media size"),
            provider_size or stream.declared_size,
        ),
    )

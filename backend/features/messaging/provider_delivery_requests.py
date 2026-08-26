"""SoAI - Provider-specific Messaging outbound request contracts [backend/features/messaging/provider_delivery_requests.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import quote

import httpx2

from core.messaging.credential_fields import (
    require_messaging_credential,
    require_whatsapp_access_token,
    require_whatsapp_api_version,
)

if TYPE_CHECKING:
    from typing import Literal

    from core.conversations.conversation_source import MessagingPlatform
    from core.types.json import JSONDict

__all__ = (
    "MessagingProviderRequest",
    "MessagingProviderRequestFailure",
    "MessagingProviderRequestSuccess",
    "build_messaging_progress_request",
    "build_messaging_text_request",
    "execute_messaging_provider_request",
)


@dataclass(frozen=True, slots=True)
class MessagingProviderRequest:
    url: str
    headers: dict[str, str] | None
    body: JSONDict


@dataclass(frozen=True, slots=True)
class MessagingProviderRequestFailure:
    classification: Literal["connection_unavailable", "ambiguous"]


@dataclass(frozen=True, slots=True)
class MessagingProviderRequestSuccess:
    response: httpx2.Response


async def execute_messaging_provider_request(
    http_client: httpx2.AsyncClient,
    request: MessagingProviderRequest,
    *,
    timeout_seconds: float,
) -> MessagingProviderRequestFailure | MessagingProviderRequestSuccess:
    try:
        response = await http_client.post(
            request.url,
            headers=request.headers,
            json=request.body,
            follow_redirects=False,
            timeout=timeout_seconds,
        )
    except (httpx2.ConnectError, httpx2.ConnectTimeout, httpx2.PoolTimeout):
        return MessagingProviderRequestFailure(classification="connection_unavailable")
    except (httpx2.TimeoutException, httpx2.RequestError):
        return MessagingProviderRequestFailure(classification="ambiguous")
    return MessagingProviderRequestSuccess(response=response)


def _telegram_bot_url(credentials: JSONDict, operation: str) -> str:
    token = require_messaging_credential(
        credentials,
        "bot_token",
        "Telegram bot token",
        maximum_length=512,
    )
    return f"https://api.telegram.org/bot{quote(token, safe=':')}/{operation}"


def _discord_channel_request(
    credentials: JSONDict,
    remote_thread_key: str,
    operation: str,
) -> tuple[str, dict[str, str]]:
    bot_token = require_messaging_credential(
        credentials,
        "bot_token",
        "Discord bot token",
        maximum_length=2048,
    )
    channel = quote(remote_thread_key, safe="")
    return (
        f"https://discord.com/api/v10/channels/{channel}/{operation}",
        {"Authorization": f"Bot {bot_token}"},
    )


def build_messaging_progress_request(
    *,
    platform: MessagingPlatform,
    credentials: JSONDict,
    remote_thread_key: str,
) -> MessagingProviderRequest | None:
    if platform == "whatsapp":
        return None
    if platform == "telegram":
        return MessagingProviderRequest(
            url=_telegram_bot_url(credentials, "sendChatAction"),
            headers=None,
            body={"chat_id": remote_thread_key, "action": "typing"},
        )
    url, headers = _discord_channel_request(credentials, remote_thread_key, "typing")
    return MessagingProviderRequest(url=url, headers=headers, body={})


def build_messaging_text_request(
    *,
    platform: MessagingPlatform,
    credentials: JSONDict,
    remote_thread_key: str,
    content_text: str,
    delivery_id: str,
    ordinal: int,
) -> MessagingProviderRequest:
    if platform == "telegram":
        return MessagingProviderRequest(
            url=_telegram_bot_url(credentials, "sendMessage"),
            headers=None,
            body={"chat_id": remote_thread_key, "text": content_text},
        )
    if platform == "whatsapp":
        access_token = require_whatsapp_access_token(credentials)
        api_version = require_whatsapp_api_version(credentials)
        phone_number_id = require_messaging_credential(
            credentials,
            "phone_number_id",
            "WhatsApp phone number id",
            maximum_length=255,
        )
        return MessagingProviderRequest(
            url=(
                f"https://graph.facebook.com/{api_version}/"
                f"{quote(phone_number_id, safe='')}/messages"
            ),
            headers={"Authorization": f"Bearer {access_token}"},
            body={
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": remote_thread_key,
                "type": "text",
                "text": {"preview_url": False, "body": content_text},
            },
        )
    url, headers = _discord_channel_request(credentials, remote_thread_key, "messages")
    nonce_source = f"{delivery_id}:{ordinal}".encode()
    nonce = hashlib.sha256(nonce_source).hexdigest()[:24]
    return MessagingProviderRequest(
        url=url,
        headers=headers,
        body={"content": content_text, "nonce": nonce, "enforce_nonce": True},
    )

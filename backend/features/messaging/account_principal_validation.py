"""SoAI - Provider-backed Messaging account identity validation [backend/features/messaging/account_principal_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx2

from core.errors.exceptions import ApiError, ValidationError
from core.messaging.account_models import ResolvedMessagingPrincipal
from core.messaging.credential_fields import (
    require_messaging_credential,
    require_telegram_bot_token,
)
from core.messaging.provider_identity import require_messaging_provider_response_id
from core.types.json_value import coerce_json_dict
from core.validation.strings import coerce_optional_trimmed_str
from features.messaging.provider_json_request import request_messaging_provider_json
from features.messaging.whatsapp_principal_validation import (
    resolve_whatsapp_provider_principal,
)

if TYPE_CHECKING:
    from core.conversations.conversation_source import MessagingPlatform
    from core.types.json import JSONDict

__all__ = ("resolve_messaging_provider_principal",)

DISCORD_MESSAGE_CONTENT_FLAGS = 786432
OPERATION_TELEGRAM_IDENTITY = "messaging.telegram.identity_validate"
OPERATION_DISCORD_BOT_IDENTITY = "messaging.discord.bot_identity_validate"
OPERATION_DISCORD_APPLICATION_IDENTITY = "messaging.discord.application_identity_validate"


async def resolve_messaging_provider_principal(
    *,
    http_client: httpx2.AsyncClient,
    platform: MessagingPlatform,
    credentials: JSONDict,
) -> ResolvedMessagingPrincipal:
    if platform == "telegram":
        return await _resolve_telegram_principal(http_client, credentials)
    if platform == "whatsapp":
        return await resolve_whatsapp_provider_principal(http_client, credentials)
    return await _resolve_discord_principal(http_client, credentials)


async def _resolve_telegram_principal(
    http_client: httpx2.AsyncClient,
    credentials: JSONDict,
) -> ResolvedMessagingPrincipal:
    bot_token = require_telegram_bot_token(credentials)
    payload = await request_messaging_provider_json(
        http_client,
        method="GET",
        url=f"https://api.telegram.org/bot{bot_token}/getMe",
        operation_label="Telegram identity validation",
        operation=OPERATION_TELEGRAM_IDENTITY,
        platform="telegram",
    )
    if payload.get("ok") is not True:
        raise ValidationError("Telegram rejected the supplied bot credentials.")
    result = coerce_json_dict(payload.get("result"))
    if result is None:
        raise ValidationError("Telegram returned an invalid bot identity.")
    principal_id = require_messaging_provider_response_id(
        result.get("id"),
        "Telegram bot identity",
    )
    username = coerce_optional_trimmed_str(result.get("username"))
    return ResolvedMessagingPrincipal(
        platform="telegram",
        principal_id=principal_id,
        principal_label=username,
        parent_principal_id=None,
        application_principal_id=None,
    )


async def _resolve_discord_principal(
    http_client: httpx2.AsyncClient,
    credentials: JSONDict,
) -> ResolvedMessagingPrincipal:
    bot_token = require_messaging_credential(
        credentials,
        "bot_token",
        "Discord bot token",
        maximum_length=2048,
    )
    expected_application_id = require_messaging_credential(
        credentials,
        "application_id",
        "Discord application id",
        maximum_length=255,
    )
    headers = {"Authorization": f"Bot {bot_token}"}
    bot_payload = await request_messaging_provider_json(
        http_client,
        method="GET",
        url="https://discord.com/api/v10/users/@me",
        operation_label="Discord bot identity validation",
        operation=OPERATION_DISCORD_BOT_IDENTITY,
        platform="discord",
        headers=headers,
        validation_error_code="messaging_discord_bot_token_rejected",
    )
    if bot_payload.get("bot") is not True:
        raise ApiError(
            "Discord credentials do not identify a bot user.",
            code="messaging_discord_not_bot",
            http_status=422,
        )
    application_payload = await request_messaging_provider_json(
        http_client,
        method="GET",
        url="https://discord.com/api/v10/oauth2/applications/@me",
        operation_label="Discord application identity validation",
        operation=OPERATION_DISCORD_APPLICATION_IDENTITY,
        platform="discord",
        headers=headers,
        validation_error_code="messaging_discord_application_rejected",
    )
    application_id = require_messaging_provider_response_id(
        application_payload.get("id"),
        "Discord application identity",
    )
    if application_id != expected_application_id:
        raise ApiError(
            "Discord bot token does not belong to the selected application.",
            code="messaging_discord_application_mismatch",
            http_status=422,
        )
    application_flags = application_payload.get("flags")
    if (
        isinstance(application_flags, bool)
        or not isinstance(application_flags, int)
        or application_flags & DISCORD_MESSAGE_CONTENT_FLAGS == 0
    ):
        raise ApiError(
            "Discord Message Content intent access is not enabled.",
            code="messaging_discord_message_content_required",
            http_status=422,
        )
    return ResolvedMessagingPrincipal(
        platform="discord",
        principal_id=require_messaging_provider_response_id(
            bot_payload.get("id"),
            "Discord bot identity",
        ),
        principal_label=coerce_optional_trimmed_str(
            bot_payload.get("global_name") or bot_payload.get("username"),
        ),
        parent_principal_id=application_id,
        application_principal_id=application_id,
    )

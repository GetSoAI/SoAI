"""SoAI - Telegram webhook ownership lifecycle [backend/features/messaging/telegram_callback.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx2

from core.errors.exceptions import ValidationError
from core.messaging.callback_contracts import (
    MessagingCallbackInspection,
    MessagingCallbackMutation,
    resolve_callback_install_precondition,
    resolve_callback_removal_precondition,
)
from core.messaging.callback_urls import fingerprint_messaging_callback_url
from core.messaging.credential_fields import (
    require_messaging_credential,
    require_telegram_bot_token,
)
from core.types.json_value import coerce_json_dict
from core.validation.strings import coerce_optional_trimmed_str
from features.messaging.callback_observability import (
    log_messaging_callback_inspection,
    log_messaging_callback_mutation,
)
from features.messaging.provider_json_request import request_messaging_provider_json

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "inspect_telegram_callback",
    "install_telegram_callback",
    "remove_owned_telegram_callback",
)

OPERATION_INSPECT = "messaging.telegram.callback_inspect"
OPERATION_INSTALL = "messaging.telegram.callback_install"
OPERATION_REMOVE = "messaging.telegram.callback_remove"


async def inspect_telegram_callback(
    http_client: httpx2.AsyncClient,
    *,
    account_id: str,
    credentials: JSONDict,
    desired_url: str,
) -> MessagingCallbackInspection:
    token = require_telegram_bot_token(credentials)
    payload = await request_messaging_provider_json(
        http_client,
        method="GET",
        url=f"https://api.telegram.org/bot{token}/getWebhookInfo",
        operation_label="Telegram webhook inspection",
        operation=OPERATION_INSPECT,
        platform="telegram",
        account_id=account_id,
    )
    if payload.get("ok") is not True:
        raise ValidationError("Telegram webhook inspection failed.")
    result = coerce_json_dict(payload.get("result"))
    if result is None:
        raise ValidationError("Telegram webhook inspection response is invalid.")
    current_url = coerce_optional_trimmed_str(result.get("url"))
    inspection = MessagingCallbackInspection(
        current_url=current_url,
        desired_url=desired_url,
        state=(
            "vacant"
            if current_url is None
            else "owned" if current_url == desired_url else "external"
        ),
    )
    log_messaging_callback_inspection(
        operation=OPERATION_INSPECT,
        platform="telegram",
        account_id=account_id,
        inspection=inspection,
    )
    return inspection


async def install_telegram_callback(
    http_client: httpx2.AsyncClient,
    *,
    account_id: str,
    credentials: JSONDict,
    callback_url: str,
    replace_existing_callback: bool,
    refresh_owned_callback: bool,
) -> MessagingCallbackMutation:
    precondition = resolve_callback_install_precondition(
        await inspect_telegram_callback(
            http_client,
            account_id=account_id,
            credentials=credentials,
            desired_url=callback_url,
        ),
        replace_existing_callback=replace_existing_callback,
        refresh_owned_callback=refresh_owned_callback,
    )
    if precondition is not None:
        return precondition
    token = require_telegram_bot_token(credentials)
    secret = require_messaging_credential(
        credentials,
        "webhook_secret",
        "Telegram webhook secret",
        maximum_length=256,
    )
    payload = await request_messaging_provider_json(
        http_client,
        method="POST",
        url=f"https://api.telegram.org/bot{token}/setWebhook",
        operation_label="Telegram webhook installation",
        operation=OPERATION_INSTALL,
        platform="telegram",
        account_id=account_id,
        json_body={
            "url": callback_url,
            "secret_token": secret,
            "allowed_updates": ["message"],
            "drop_pending_updates": False,
        },
    )
    if payload.get("ok") is not True or payload.get("result") is not True:
        raise ValidationError("Telegram webhook installation failed.")
    mutation = MessagingCallbackMutation(
        callback_fingerprint=fingerprint_messaging_callback_url(callback_url),
        ownership_state="owned",
    )
    log_messaging_callback_mutation(
        operation=OPERATION_INSTALL,
        platform="telegram",
        account_id=account_id,
        mutation=mutation,
    )
    return mutation


async def remove_owned_telegram_callback(
    http_client: httpx2.AsyncClient,
    *,
    account_id: str,
    credentials: JSONDict,
    installed_callback_fingerprint: str | None,
    desired_url: str,
) -> MessagingCallbackMutation:
    precondition = resolve_callback_removal_precondition(
        await inspect_telegram_callback(
            http_client,
            account_id=account_id,
            credentials=credentials,
            desired_url=desired_url,
        ),
        installed_callback_fingerprint=installed_callback_fingerprint,
    )
    if precondition is not None:
        return precondition
    token = require_telegram_bot_token(credentials)
    payload = await request_messaging_provider_json(
        http_client,
        method="POST",
        url=f"https://api.telegram.org/bot{token}/deleteWebhook",
        operation_label="Telegram webhook removal",
        operation=OPERATION_REMOVE,
        platform="telegram",
        account_id=account_id,
        json_body={"drop_pending_updates": False},
    )
    if payload.get("ok") is not True or payload.get("result") is not True:
        raise ValidationError("Telegram webhook removal failed.")
    mutation = MessagingCallbackMutation(callback_fingerprint=None, ownership_state="unknown")
    log_messaging_callback_mutation(
        operation=OPERATION_REMOVE,
        platform="telegram",
        account_id=account_id,
        mutation=mutation,
    )
    return mutation

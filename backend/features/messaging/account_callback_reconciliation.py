"""SoAI - Messaging account callback reconciliation [backend/features/messaging/account_callback_reconciliation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx2

from core.errors.exceptions import ApiError, StateError
from core.messaging.account_validation import (
    require_messaging_account_id,
    require_messaging_platform,
)
from core.messaging.callback_contracts import MessagingCallbackMutation
from core.messaging.callback_urls import build_messaging_callback_url
from core.types.json import is_json_dict
from core.validation.strings import coerce_optional_trimmed_str
from features.messaging.telegram_callback import (
    inspect_telegram_callback,
    install_telegram_callback,
    remove_owned_telegram_callback,
)
from features.messaging.whatsapp_callback import (
    inspect_whatsapp_callback,
    install_whatsapp_callback,
    remove_owned_whatsapp_callback,
)

if TYPE_CHECKING:
    from core.conversations.conversation_source import MessagingPlatform
    from core.types.json import JSONDict

__all__ = (
    "preflight_messaging_callback_ownership",
    "reconcile_messaging_account_callback",
    "remove_messaging_account_callback",
)


def _require_credentials(account: JSONDict) -> JSONDict:
    credentials = account.get("credentials")
    if not is_json_dict(credentials):
        raise StateError("Messaging account credentials are unavailable.")
    return credentials


def _callback_identity(
    account: JSONDict,
    public_origin: str,
) -> tuple[MessagingPlatform, str, str, JSONDict]:
    platform = require_messaging_platform(str(account.get("platform") or ""))
    account_id = require_messaging_account_id(str(account.get("account_id") or ""))
    return (
        platform,
        account_id,
        build_messaging_callback_url(
            public_origin=public_origin,
            platform=platform,
            account_id=account_id,
        ),
        _require_credentials(account),
    )


async def preflight_messaging_callback_ownership(
    http_client: httpx2.AsyncClient,
    *,
    account: JSONDict,
    public_origin: str,
    replace_existing_callback: bool,
) -> None:
    platform = require_messaging_platform(str(account.get("platform") or ""))
    if platform == "discord":
        return
    platform, account_id, callback_url, credentials = _callback_identity(
        account,
        public_origin,
    )
    if platform == "telegram":
        inspection = await inspect_telegram_callback(
            http_client,
            account_id=account_id,
            credentials=credentials,
            desired_url=callback_url,
        )
    else:
        inspection = await inspect_whatsapp_callback(
            http_client,
            account_id=account_id,
            credentials=credentials,
            desired_url=callback_url,
        )
    if inspection.state == "external" and not replace_existing_callback:
        raise ApiError(
            "The provider already routes this account to a different callback. Explicit replacement confirmation is required.",
            code="messaging_callback_conflict",
            http_status=409,
        )


async def reconcile_messaging_account_callback(
    http_client: httpx2.AsyncClient,
    *,
    account: JSONDict,
    public_origin: str,
    replace_existing_callback: bool,
    refresh_owned_callback: bool,
) -> MessagingCallbackMutation:
    platform = require_messaging_platform(str(account.get("platform") or ""))
    if platform == "discord":
        return MessagingCallbackMutation(
            callback_fingerprint=None,
            ownership_state="not_applicable",
        )
    platform, account_id, callback_url, credentials = _callback_identity(
        account,
        public_origin,
    )
    if platform == "telegram":
        return await install_telegram_callback(
            http_client,
            account_id=account_id,
            credentials=credentials,
            callback_url=callback_url,
            replace_existing_callback=replace_existing_callback,
            refresh_owned_callback=refresh_owned_callback,
        )
    return await install_whatsapp_callback(
        http_client,
        account_id=account_id,
        credentials=credentials,
        callback_url=callback_url,
        replace_existing_callback=replace_existing_callback,
        refresh_owned_callback=refresh_owned_callback,
    )


async def remove_messaging_account_callback(
    http_client: httpx2.AsyncClient,
    *,
    account: JSONDict,
    public_origin: str,
) -> MessagingCallbackMutation:
    platform = require_messaging_platform(str(account.get("platform") or ""))
    if platform == "discord":
        return MessagingCallbackMutation(
            callback_fingerprint=None,
            ownership_state="not_applicable",
        )
    platform, account_id, callback_url, credentials = _callback_identity(
        account,
        public_origin,
    )
    installed_fingerprint = coerce_optional_trimmed_str(
        account.get("installed_callback_fingerprint"),
    )
    if platform == "telegram":
        return await remove_owned_telegram_callback(
            http_client,
            account_id=account_id,
            credentials=credentials,
            installed_callback_fingerprint=installed_fingerprint,
            desired_url=callback_url,
        )
    return await remove_owned_whatsapp_callback(
        http_client,
        account_id=account_id,
        credentials=credentials,
        installed_callback_fingerprint=installed_fingerprint,
        desired_url=callback_url,
    )

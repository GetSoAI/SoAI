"""SoAI - WhatsApp WABA callback ownership lifecycle [backend/features/messaging/whatsapp_callback.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import httpx2

from core.errors.exceptions import ServiceUnavailableError, ValidationError
from core.messaging.callback_contracts import (
    MessagingCallbackInspection,
    MessagingCallbackMutation,
    resolve_callback_install_precondition,
    resolve_callback_removal_precondition,
)
from core.messaging.callback_urls import fingerprint_messaging_callback_url
from core.messaging.credential_fields import (
    require_messaging_credential,
    require_whatsapp_access_token,
    require_whatsapp_api_version,
)
from core.messaging.graph_pagination import read_graph_next_cursor
from core.types.json_value import coerce_json_dict
from core.validation.strings import coerce_optional_trimmed_str
from features.messaging.callback_observability import (
    log_messaging_callback_inspection,
    log_messaging_callback_mutation,
)
from features.messaging.provider_json_request import request_messaging_provider_json

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "inspect_whatsapp_callback",
    "install_whatsapp_callback",
    "remove_owned_whatsapp_callback",
)

WHATSAPP_SUBSCRIPTION_PAGE_LIMIT = 100
WHATSAPP_SUBSCRIPTION_MAX_PAGES = 20
OPERATION_INSPECT = "messaging.whatsapp.callback_inspect"
OPERATION_SUBSCRIBE = "messaging.whatsapp.application_subscribe"
OPERATION_INSTALL = "messaging.whatsapp.callback_install"
OPERATION_REMOVE = "messaging.whatsapp.callback_remove"


def _subscription_url(credentials: JSONDict) -> str:
    api_version = require_whatsapp_api_version(credentials)
    business_account_id = require_messaging_credential(
        credentials,
        "business_account_id",
        "WhatsApp Business Account id",
        maximum_length=255,
    )
    account_url = f"https://graph.facebook.com/{api_version}/{business_account_id}"
    return f"{account_url}/subscribed_apps"


def _authorization_headers(credentials: JSONDict) -> dict[str, str]:
    access_token = require_whatsapp_access_token(credentials)
    return {"Authorization": f"Bearer {access_token}"}


def _find_application_subscription(
    value: JSONValue,
    application_id: str,
) -> JSONDict | None:
    if not isinstance(value, list) or len(value) > WHATSAPP_SUBSCRIPTION_PAGE_LIMIT:
        raise ValidationError("WhatsApp subscription inspection response is invalid.")
    for entry in value:
        record = coerce_json_dict(entry)
        if record is None:
            raise ValidationError("WhatsApp subscription record is invalid.")
        record_id = coerce_optional_trimmed_str(record.get("id"))
        application_data = coerce_json_dict(record.get("whatsapp_business_api_data"))
        nested_id = (
            coerce_optional_trimmed_str(application_data.get("id"))
            if application_data is not None
            else None
        )
        if application_id in (record_id, nested_id):
            return record
    return None


def _subscription_callback_url(subscription: JSONDict) -> str | None:
    direct = coerce_optional_trimmed_str(subscription.get("override_callback_uri"))
    if direct is not None:
        return direct
    application_data = coerce_json_dict(subscription.get("whatsapp_business_api_data"))
    if application_data is None:
        return None
    return coerce_optional_trimmed_str(application_data.get("override_callback_uri"))


def _inspected(
    *,
    current_url: str | None,
    desired_url: str,
    state: Literal["vacant", "owned", "external"],
    page_count: int,
    account_id: str,
) -> MessagingCallbackInspection:
    inspection = MessagingCallbackInspection(
        current_url=current_url,
        desired_url=desired_url,
        state=state,
    )
    log_messaging_callback_inspection(
        operation=OPERATION_INSPECT,
        platform="whatsapp",
        account_id=account_id,
        inspection=inspection,
        page_count=page_count,
    )
    return inspection


async def inspect_whatsapp_callback(
    http_client: httpx2.AsyncClient,
    *,
    account_id: str,
    credentials: JSONDict,
    desired_url: str,
) -> MessagingCallbackInspection:
    application_id = require_messaging_credential(
        credentials,
        "application_id",
        "WhatsApp application id",
        maximum_length=255,
    )
    after: str | None = None
    for page_number in range(WHATSAPP_SUBSCRIPTION_MAX_PAGES):
        params = {"limit": str(WHATSAPP_SUBSCRIPTION_PAGE_LIMIT)}
        if after is not None:
            params["after"] = after
        payload = await request_messaging_provider_json(
            http_client,
            method="GET",
            url=_subscription_url(credentials),
            operation_label="WhatsApp callback inspection",
            operation=OPERATION_INSPECT,
            platform="whatsapp",
            account_id=account_id,
            headers=_authorization_headers(credentials),
            params=params,
        )
        subscription = _find_application_subscription(payload.get("data"), application_id)
        if subscription is not None:
            current_url = _subscription_callback_url(subscription)
            return _inspected(
                current_url=current_url,
                desired_url=desired_url,
                state="owned" if current_url == desired_url else "external",
                page_count=page_number + 1,
                account_id=account_id,
            )
        after = read_graph_next_cursor(
            payload,
            response_label="WhatsApp subscription response",
        )
        if after is None:
            return _inspected(
                current_url=None,
                desired_url=desired_url,
                state="vacant",
                page_count=page_number + 1,
                account_id=account_id,
            )
    raise ServiceUnavailableError(
        "WhatsApp callback inspection exceeded its bounded page limit.",
    )


async def install_whatsapp_callback(
    http_client: httpx2.AsyncClient,
    *,
    account_id: str,
    credentials: JSONDict,
    callback_url: str,
    replace_existing_callback: bool,
    refresh_owned_callback: bool,
) -> MessagingCallbackMutation:
    inspection = await inspect_whatsapp_callback(
        http_client,
        account_id=account_id,
        credentials=credentials,
        desired_url=callback_url,
    )
    precondition = resolve_callback_install_precondition(
        inspection,
        replace_existing_callback=replace_existing_callback,
        refresh_owned_callback=refresh_owned_callback,
    )
    if precondition is not None:
        return precondition
    headers = _authorization_headers(credentials)
    url = _subscription_url(credentials)
    if inspection.state == "vacant":
        subscribed = await request_messaging_provider_json(
            http_client,
            method="POST",
            url=url,
            operation_label="WhatsApp application subscription",
            operation=OPERATION_SUBSCRIBE,
            platform="whatsapp",
            account_id=account_id,
            headers=headers,
            json_body={"subscribed_fields": ["messages"]},
        )
        if subscribed.get("success") is not True:
            raise ValidationError("WhatsApp application subscription failed.")
    verify_token = require_messaging_credential(
        credentials,
        "verify_token",
        "WhatsApp verify token",
        maximum_length=256,
    )
    installed = await request_messaging_provider_json(
        http_client,
        method="POST",
        url=url,
        operation_label="WhatsApp callback installation",
        operation=OPERATION_INSTALL,
        platform="whatsapp",
        account_id=account_id,
        headers=headers,
        json_body={
            "override_callback_uri": callback_url,
            "verify_token": verify_token,
        },
    )
    application_id = require_messaging_credential(
        credentials,
        "application_id",
        "WhatsApp application id",
        maximum_length=255,
    )
    subscription = _find_application_subscription(
        installed.get("data"),
        application_id,
    )
    if subscription is None or _subscription_callback_url(subscription) != callback_url:
        raise ValidationError("WhatsApp callback installation failed.")
    mutation = MessagingCallbackMutation(
        callback_fingerprint=fingerprint_messaging_callback_url(callback_url),
        ownership_state="owned",
    )
    log_messaging_callback_mutation(
        operation=OPERATION_INSTALL,
        platform="whatsapp",
        account_id=account_id,
        mutation=mutation,
    )
    return mutation


async def remove_owned_whatsapp_callback(
    http_client: httpx2.AsyncClient,
    *,
    account_id: str,
    credentials: JSONDict,
    installed_callback_fingerprint: str | None,
    desired_url: str,
) -> MessagingCallbackMutation:
    inspection = await inspect_whatsapp_callback(
        http_client,
        account_id=account_id,
        credentials=credentials,
        desired_url=desired_url,
    )
    precondition = resolve_callback_removal_precondition(
        inspection,
        installed_callback_fingerprint=installed_callback_fingerprint,
    )
    if precondition is not None:
        return precondition
    reverted = await request_messaging_provider_json(
        http_client,
        method="POST",
        url=_subscription_url(credentials),
        operation_label="WhatsApp callback removal",
        operation=OPERATION_REMOVE,
        platform="whatsapp",
        account_id=account_id,
        headers=_authorization_headers(credentials),
        json_body={"subscribed_fields": ["messages"]},
    )
    if reverted.get("success") is not True:
        raise ValidationError("WhatsApp callback removal failed.")
    mutation = MessagingCallbackMutation(callback_fingerprint=None, ownership_state="unknown")
    log_messaging_callback_mutation(
        operation=OPERATION_REMOVE,
        platform="whatsapp",
        account_id=account_id,
        mutation=mutation,
    )
    return mutation

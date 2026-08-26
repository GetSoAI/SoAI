"""SoAI - WhatsApp account identity validation [backend/features/messaging/whatsapp_principal_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx2

from core.errors.exceptions import ApiError, ServiceUnavailableError, ValidationError
from core.messaging.account_models import ResolvedMessagingPrincipal
from core.messaging.credential_fields import (
    require_messaging_credential,
    require_whatsapp_access_token,
    require_whatsapp_api_version,
)
from core.messaging.graph_pagination import read_graph_next_cursor
from core.messaging.provider_identity import require_messaging_provider_response_id
from core.types.json_value import coerce_json_dict
from core.validation.strings import coerce_optional_trimmed_str
from features.messaging.provider_json_request import request_messaging_provider_json

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("resolve_whatsapp_provider_principal",)

WHATSAPP_PHONE_PAGE_LIMIT = 100
WHATSAPP_PHONE_MAX_PAGES = 20
WHATSAPP_REQUIRED_TOKEN_SCOPES = frozenset(
    {"whatsapp_business_management", "whatsapp_business_messaging"},
)
OPERATION_PHONE_IDENTITY = "messaging.whatsapp.phone_identity_validate"
OPERATION_APPLICATION_CREDENTIAL = "messaging.whatsapp.application_credential_validate"
OPERATION_BUSINESS_ACCOUNT_IDENTITY = "messaging.whatsapp.business_account_identity_validate"


async def resolve_whatsapp_provider_principal(
    http_client: httpx2.AsyncClient,
    credentials: JSONDict,
) -> ResolvedMessagingPrincipal:
    access_token = require_whatsapp_access_token(credentials)
    phone_number_id = require_messaging_credential(
        credentials,
        "phone_number_id",
        "WhatsApp phone number id",
        maximum_length=255,
    )
    business_account_id = require_messaging_credential(
        credentials,
        "business_account_id",
        "WhatsApp Business Account id",
        maximum_length=255,
    )
    application_id = require_messaging_credential(
        credentials,
        "application_id",
        "WhatsApp application id",
        maximum_length=255,
    )
    app_secret = require_messaging_credential(
        credentials,
        "app_secret",
        "WhatsApp application secret",
        maximum_length=512,
    )
    api_version = require_whatsapp_api_version(credentials)
    await _validate_application_token(
        http_client=http_client,
        api_version=api_version,
        application_id=application_id,
        app_secret=app_secret,
        access_token=access_token,
    )
    headers = {"Authorization": f"Bearer {access_token}"}
    phone_payload = await request_messaging_provider_json(
        http_client,
        method="GET",
        url=f"https://graph.facebook.com/{api_version}/{phone_number_id}",
        operation_label="WhatsApp phone identity validation",
        operation=OPERATION_PHONE_IDENTITY,
        platform="whatsapp",
        headers=headers,
        params={"fields": "id,display_phone_number,verified_name"},
        validation_error_code="messaging_whatsapp_phone_rejected",
    )
    resolved_phone_id = require_messaging_provider_response_id(
        phone_payload.get("id"),
        "WhatsApp phone identity",
    )
    if resolved_phone_id != phone_number_id:
        raise ApiError(
            "WhatsApp returned a different phone number identity.",
            code="messaging_whatsapp_phone_mismatch",
            http_status=422,
        )
    if not await _business_account_contains_phone(
        http_client=http_client,
        api_version=api_version,
        business_account_id=business_account_id,
        phone_number_id=phone_number_id,
        headers=headers,
    ):
        raise ApiError(
            "WhatsApp credentials cannot access the selected phone number through the selected Business Account.",
            code="messaging_whatsapp_business_account_mismatch",
            http_status=422,
        )
    return ResolvedMessagingPrincipal(
        platform="whatsapp",
        principal_id=phone_number_id,
        principal_label=coerce_optional_trimmed_str(
            phone_payload.get("verified_name") or phone_payload.get("display_phone_number"),
        ),
        parent_principal_id=business_account_id,
        application_principal_id=application_id,
    )


async def _validate_application_token(
    *,
    http_client: httpx2.AsyncClient,
    api_version: str,
    application_id: str,
    app_secret: str,
    access_token: str,
) -> None:
    payload = await request_messaging_provider_json(
        http_client,
        method="GET",
        url=f"https://graph.facebook.com/{api_version}/debug_token",
        operation_label="WhatsApp application credential validation",
        operation=OPERATION_APPLICATION_CREDENTIAL,
        platform="whatsapp",
        headers={"Authorization": f"Bearer {application_id}|{app_secret}"},
        params={"input_token": access_token},
        validation_error_code="messaging_whatsapp_application_credentials_rejected",
    )
    token_data = coerce_json_dict(payload.get("data"))
    if token_data is None or token_data.get("is_valid") is not True:
        raise ApiError(
            "WhatsApp access token is invalid.",
            code="messaging_whatsapp_access_token_rejected",
            http_status=422,
        )
    resolved_application_id = require_messaging_provider_response_id(
        token_data.get("app_id"),
        "WhatsApp access token application identity",
    )
    if resolved_application_id != application_id:
        raise ApiError(
            "WhatsApp access token belongs to a different Meta application.",
            code="messaging_whatsapp_application_mismatch",
            http_status=422,
        )
    scopes = token_data.get("scopes")
    if not isinstance(scopes, list) or any(not isinstance(scope, str) for scope in scopes):
        raise ValidationError("WhatsApp access token permissions response is invalid.")
    if not WHATSAPP_REQUIRED_TOKEN_SCOPES.issubset(set(scopes)):
        raise ApiError(
            "WhatsApp access token lacks required permissions.",
            code="messaging_whatsapp_permissions_required",
            http_status=422,
        )


async def _business_account_contains_phone(
    *,
    http_client: httpx2.AsyncClient,
    api_version: str,
    business_account_id: str,
    phone_number_id: str,
    headers: dict[str, str],
) -> bool:
    url = f"https://graph.facebook.com/{api_version}/{business_account_id}/phone_numbers"
    after: str | None = None
    for _page_number in range(WHATSAPP_PHONE_MAX_PAGES):
        params = {"fields": "id", "limit": str(WHATSAPP_PHONE_PAGE_LIMIT)}
        if after is not None:
            params["after"] = after
        payload = await request_messaging_provider_json(
            http_client,
            method="GET",
            url=url,
            operation_label="WhatsApp Business Account identity validation",
            operation=OPERATION_BUSINESS_ACCOUNT_IDENTITY,
            platform="whatsapp",
            headers=headers,
            params=params,
            validation_error_code="messaging_whatsapp_business_account_rejected",
        )
        if _response_collection_contains_id(payload.get("data"), phone_number_id):
            return True
        after = read_graph_next_cursor(
            payload,
            response_label="WhatsApp Business Account response",
        )
        if after is None:
            return False
    raise ServiceUnavailableError(
        "WhatsApp Business Account identity validation exceeded its bounded page limit.",
    )


def _response_collection_contains_id(value: JSONValue, expected_id: str) -> bool:
    if not isinstance(value, list):
        raise ValidationError("WhatsApp Business Account response is invalid.")
    for entry in value:
        record = coerce_json_dict(entry)
        if (
            record is not None
            and require_messaging_provider_response_id(
                record.get("id"),
                "WhatsApp Business Account phone identity",
            )
            == expected_id
        ):
            return True
    return False

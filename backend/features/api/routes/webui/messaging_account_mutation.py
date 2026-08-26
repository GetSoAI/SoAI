"""SoAI - Messaging account mutation input preparation [backend/features/api/routes/webui/messaging_account_mutation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request

from core.errors.exceptions import StateError
from core.messaging.account_models import (
    MessagingAuthorizedSender,
    ResolvedMessagingPrincipal,
)
from core.messaging.account_validation import require_messaging_account_id
from core.types.json_value import coerce_json_dict
from core.validation.record_fields import require_int
from core.validation.strings import coerce_optional_trimmed_str
from features.api.runtime.errors import raise_invalid_request
from features.api.schemas.messaging_accounts import (
    MessagingAuthorizedSenderRequest,
    validate_messaging_credentials_platform,
)
from features.messaging.account_principal_validation import (
    resolve_messaging_provider_principal,
)

if TYPE_CHECKING:
    from core.conversations.conversation_source import MessagingPlatform
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext
    from features.api.schemas.messaging_accounts import MessagingCredentialsRequest

__all__ = (
    "build_messaging_authorized_senders",
    "resolve_messaging_update_credentials",
    "serialize_messaging_credentials",
)


def serialize_messaging_credentials(
    credentials: MessagingCredentialsRequest,
) -> JSONDict:
    payload = coerce_json_dict(credentials.model_dump(mode="json"))
    if payload is None:
        raise StateError("Messaging credentials could not be serialized.")
    return payload


def build_messaging_authorized_senders(
    senders: list[MessagingAuthorizedSenderRequest],
) -> tuple[MessagingAuthorizedSender, ...]:
    return tuple(
        MessagingAuthorizedSender(
            sender_id=sender.sender_id,
            display_label=sender.display_label,
        )
        for sender in senders
    )


async def resolve_messaging_update_credentials(
    *,
    request: Request,
    api_context: ApiContext,
    platform: MessagingPlatform,
    existing: JSONDict,
    credentials_payload: MessagingCredentialsRequest | None,
) -> tuple[JSONDict | None, JSONDict, ResolvedMessagingPrincipal]:
    existing_principal = _existing_principal(platform, existing)
    if credentials_payload is None:
        credentials = await api_context.dependencies.database_messaging_accounts.get_credentials(
            require_int(
                existing.get("user_id"),
                label="Messaging account owner",
                build_error=StateError,
                minimum=1,
            ),
            require_messaging_account_id(str(existing.get("account_id") or "")),
        )
        if credentials is None:
            raise StateError("Messaging account credentials are unavailable.")
        return (None, credentials, existing_principal)
    try:
        validate_messaging_credentials_platform(platform, credentials_payload)
    except ValueError as exception:
        raise_invalid_request(request, str(exception))
    credentials = serialize_messaging_credentials(credentials_payload)
    resolved = await resolve_messaging_provider_principal(
        http_client=api_context.dependencies.http_client,
        platform=platform,
        credentials=credentials,
    )
    if (
        resolved.principal_id != existing_principal.principal_id
        or resolved.parent_principal_id != existing_principal.parent_principal_id
        or resolved.application_principal_id != existing_principal.application_principal_id
    ):
        raise_invalid_request(
            request,
            "Messaging credentials resolve to a different provider account.",
        )
    return (
        credentials,
        credentials,
        ResolvedMessagingPrincipal(
            platform=resolved.platform,
            principal_id=resolved.principal_id,
            principal_label=resolved.principal_label or existing_principal.principal_label,
            parent_principal_id=resolved.parent_principal_id,
            application_principal_id=resolved.application_principal_id,
        ),
    )


def _existing_principal(
    platform: MessagingPlatform,
    existing: JSONDict,
) -> ResolvedMessagingPrincipal:
    principal_id = coerce_optional_trimmed_str(existing.get("principal_id"))
    if principal_id is None:
        raise StateError("Stored Messaging principal identity is invalid.")
    return ResolvedMessagingPrincipal(
        platform=platform,
        principal_id=principal_id,
        principal_label=coerce_optional_trimmed_str(existing.get("principal_label")),
        parent_principal_id=coerce_optional_trimmed_str(existing.get("parent_principal_id")),
        application_principal_id=coerce_optional_trimmed_str(
            existing.get("application_principal_id"),
        ),
    )

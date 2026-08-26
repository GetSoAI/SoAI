"""SoAI - Authenticated Messaging webhook boundary [backend/features/api/routes/messaging/webhook_requests.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request

from core.errors.exceptions import ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.messaging.platform_verification import (
    verify_telegram_secret,
    verify_whatsapp_signature,
)
from core.serialization.json import normalize_to_json_dict
from core.serialization.json_parsing import parse_json_value
from core.types.json import is_json_dict
from core.validation.strings import coerce_optional_trimmed_str
from features.api.routes.messaging.webhook_observability import (
    MessagingWebhookTrace,
    log_messaging_webhook_authentication,
    log_messaging_webhook_body,
    log_messaging_webhook_complete,
)
from features.api.runtime.errors import (
    raise_forbidden,
    raise_invalid_request,
    raise_not_found,
)
from features.api.runtime.request_payloads import read_bounded_body_bytes_or_raise

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext

__all__ = (
    "load_webhook_account",
    "parse_messaging_webhook_body",
    "read_messaging_webhook_body_bytes",
    "require_telegram_webhook_secret",
    "require_whatsapp_webhook_signature",
)

MESSAGING_WEBHOOK_MAX_BODY_BYTES = 1_048_576


async def load_webhook_account(
    request: Request,
    api_context: ApiContext,
    *,
    account_id: str,
    platform: str,
    trace: MessagingWebhookTrace,
) -> JSONDict:
    account = await api_context.dependencies.messaging_gateway.get_webhook_account(
        account_id=account_id,
        platform=platform,
    )
    if account is None:
        log_messaging_webhook_authentication(
            trace,
            accepted=False,
            failure_code="messaging_webhook_account_unavailable",
        )
        raise_not_found(request, "Messaging account not found.")
    return account


def require_account_credentials(account: JSONDict) -> JSONDict:
    credentials = account.get("credentials")
    if not is_json_dict(credentials):
        raise ValidationError("Messaging account credentials are unavailable.")
    return credentials


async def read_messaging_webhook_body_bytes(
    request: Request,
    trace: MessagingWebhookTrace,
) -> bytes:
    try:
        body = await read_bounded_body_bytes_or_raise(
            request,
            max_body_bytes=MESSAGING_WEBHOOK_MAX_BODY_BYTES,
            invalid_body_message="Messaging webhook body could not be read.",
            payload_too_large_message="Messaging webhook body is too large.",
        )
    except HANDLED_RUNTIME_EXCEPTIONS:
        log_messaging_webhook_complete(
            trace,
            outcome="rejected",
            failure_code="messaging_webhook_body_rejected",
        )
        raise
    log_messaging_webhook_body(trace, body_bytes=len(body))
    return body


def parse_messaging_webhook_body(
    request: Request,
    raw_body: bytes,
    trace: MessagingWebhookTrace,
) -> JSONDict:
    try:
        parsed = parse_json_value(raw_body, field="Messaging webhook body", max_depth=32)
        if not isinstance(parsed, dict):
            raise ValidationError("Messaging webhook body must be a JSON object.")
        return normalize_to_json_dict(
            parsed,
            message="Messaging webhook body is invalid.",
        )
    except ValidationError as exception:
        log_messaging_webhook_complete(
            trace,
            outcome="rejected",
            failure_code="messaging_webhook_json_invalid",
        )
        raise_invalid_request(request, str(exception))


def require_telegram_webhook_secret(
    request: Request,
    *,
    account: JSONDict,
    provided_token: str | None,
    trace: MessagingWebhookTrace,
) -> None:
    credentials = require_account_credentials(account)
    expected = coerce_optional_trimmed_str(credentials.get("webhook_secret"))
    if not verify_telegram_secret(expected, provided_token):
        log_messaging_webhook_authentication(
            trace,
            accepted=False,
            failure_code="telegram_webhook_secret_invalid",
        )
        raise_forbidden(request, "Telegram webhook secret token is invalid.")
    log_messaging_webhook_authentication(trace, accepted=True)


def require_whatsapp_webhook_signature(
    request: Request,
    *,
    account: JSONDict,
    signature_header: str | None,
    raw_body: bytes,
    trace: MessagingWebhookTrace,
) -> None:
    credentials = require_account_credentials(account)
    app_secret = coerce_optional_trimmed_str(credentials.get("app_secret"))
    if not verify_whatsapp_signature(
        app_secret=app_secret,
        signature_header=signature_header,
        raw_body=raw_body,
    ):
        log_messaging_webhook_authentication(
            trace,
            accepted=False,
            failure_code="whatsapp_webhook_signature_invalid",
        )
        raise_forbidden(request, "WhatsApp webhook signature is invalid.")
    log_messaging_webhook_authentication(trace, accepted=True)

"""SoAI - Provider-specific outbound Messaging execution [backend/features/messaging/provider_delivery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import httpx2

from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.messaging.delivery_models import MessagingProviderSendOutcome
from core.messaging.inbound_content import bounded_trimmed_text
from core.messaging.observability_emission import log_messaging_diagnostic
from core.messaging.observability_fields import MessagingLogFields
from core.network.http_json import read_http_json_dict
from core.timing.monotonic import monotonic_ms
from core.timing.retry_backoff import parse_retry_after_milliseconds
from core.types.json_value import coerce_json_dict
from features.messaging.provider_delivery_requests import (
    MessagingProviderRequest,
    MessagingProviderRequestFailure,
    execute_messaging_provider_request,
)
from features.messaging.provider_error_codes import read_messaging_provider_error_code

if TYPE_CHECKING:
    from core.conversations.conversation_source import MessagingPlatform
    from core.messaging.delivery_models import MessagingProviderSendState
    from core.messaging.observability_fields import MessagingLogOutcome
    from core.types.json import JSONDict, JSONValue

__all__ = ("execute_messaging_provider_text_request",)

PROVIDER_DELIVERY_TIMEOUT_SECONDS = 15.0
DEFAULT_RETRY_AFTER_MS = 1_000
MAX_RETRY_AFTER_MS = 300_000
LOGGER_NAME = "SoAI.features.messaging.provider_delivery"
OPERATION_DELIVERY = "messaging.provider.delivery"


def _is_ambiguous_provider_status(status_code: int) -> bool:
    return status_code == 408 or 500 <= status_code <= 599


def _response_payload(response: httpx2.Response) -> JSONDict | None:
    try:
        return read_http_json_dict(response, field="Messaging provider delivery response")
    except ValidationError:
        return None


def _retry_value(
    platform: MessagingPlatform,
    payload: JSONDict | None,
) -> JSONValue:
    if payload is None:
        return None
    if platform == "discord":
        return payload.get("retry_after")
    if platform == "telegram":
        parameters = coerce_json_dict(payload.get("parameters"))
        return parameters.get("retry_after") if parameters is not None else None
    return None


def _retry_after_ms(
    platform: MessagingPlatform,
    response: httpx2.Response,
    payload: JSONDict | None,
) -> int:
    provider_value = _retry_value(platform, payload)
    value = provider_value if provider_value is not None else response.headers.get("retry-after")
    return parse_retry_after_milliseconds(
        value,
        default_milliseconds=DEFAULT_RETRY_AFTER_MS,
        maximum_milliseconds=MAX_RETRY_AFTER_MS,
    )


def _success_cooldown_ms(
    platform: MessagingPlatform,
    response: httpx2.Response,
) -> int:
    if platform != "discord" or response.headers.get("x-ratelimit-remaining") != "0":
        return 0
    return parse_retry_after_milliseconds(
        response.headers.get("x-ratelimit-reset-after"),
        default_milliseconds=0,
        maximum_milliseconds=MAX_RETRY_AFTER_MS,
    )


def _coerce_provider_id(value: JSONValue) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        value = str(value)
    return bounded_trimmed_text(value, 512)


def _response_message_id(
    platform: MessagingPlatform,
    payload: JSONDict,
) -> str | None:
    if platform == "telegram":
        if payload.get("ok") is not True:
            return None
        result = coerce_json_dict(payload.get("result"))
        return _coerce_provider_id(result.get("message_id") if result is not None else None)
    if platform == "whatsapp":
        messages = payload.get("messages")
        if not isinstance(messages, list) or len(messages) != 1:
            return None
        message = coerce_json_dict(messages[0])
        return _coerce_provider_id(message.get("id") if message is not None else None)
    return _coerce_provider_id(payload.get("id"))


def _outcome(
    *,
    state: MessagingProviderSendState,
    provider_message_id: str | None = None,
    failure_code: str | None = None,
    retry_after_ms: int | None = None,
    next_request_delay_ms: int | None = None,
) -> MessagingProviderSendOutcome:
    return MessagingProviderSendOutcome(
        state=state,
        provider_message_id=provider_message_id,
        failure_code=failure_code,
        retry_after_ms=retry_after_ms,
        next_request_delay_ms=next_request_delay_ms,
    )


def _log_delivery_outcome(
    log_fields: MessagingLogFields,
    started_ms: int,
    outcome: MessagingProviderSendOutcome,
    *,
    response: httpx2.Response | None = None,
) -> MessagingProviderSendOutcome:
    if outcome.state == "sent":
        log_outcome: MessagingLogOutcome = "success"
    elif outcome.state == "retryable":
        log_outcome = "retryable"
    elif outcome.state == "delivery_unknown":
        log_outcome = "unknown"
    else:
        log_outcome = "failure"
    log_messaging_diagnostic(
        get_logger(LOGGER_NAME),
        message="Messaging provider delivery reached a terminal request outcome.",
        log_fields=replace(
            log_fields,
            phase="complete",
            outcome=log_outcome,
            elapsed_ms=monotonic_ms() - started_ms,
            failure_code=outcome.failure_code,
            provider_status=response.status_code if response is not None else None,
            provider_error_code=(
                read_messaging_provider_error_code(response)
                if response is not None and outcome.failure_code is not None
                else None
            ),
            retry_after_ms=outcome.retry_after_ms,
        ),
    )
    return outcome


def _log_provider_response(
    log_fields: MessagingLogFields,
    started_ms: int,
    platform: MessagingPlatform,
    response: httpx2.Response,
    payload: JSONDict | None,
) -> None:
    retry_after_ms = None
    if response.status_code == 429 or _is_ambiguous_provider_status(response.status_code):
        retry_after_ms = _retry_after_ms(platform, response, payload)
    log_messaging_diagnostic(
        get_logger(LOGGER_NAME),
        message="Messaging provider delivery response received.",
        log_fields=replace(
            log_fields,
            phase="progress",
            outcome="success" if 200 <= response.status_code < 300 else "failure",
            elapsed_ms=monotonic_ms() - started_ms,
            provider_status=response.status_code,
            provider_error_code=(
                None
                if 200 <= response.status_code < 300
                else read_messaging_provider_error_code(response)
            ),
            retry_after_ms=retry_after_ms,
        ),
    )


async def execute_messaging_provider_text_request(
    *,
    http_client: httpx2.AsyncClient,
    platform: MessagingPlatform,
    request: MessagingProviderRequest,
    delivery_id: str,
    ordinal: int,
) -> MessagingProviderSendOutcome:
    log_fields = MessagingLogFields(
        operation=OPERATION_DELIVERY,
        platform=platform,
        phase="start",
        delivery_id=delivery_id,
        chunk_ordinal=ordinal,
    )
    started_ms = monotonic_ms()
    log_messaging_diagnostic(
        get_logger(LOGGER_NAME),
        message="Messaging provider delivery request started.",
        log_fields=log_fields,
    )
    request_result = await execute_messaging_provider_request(
        http_client,
        request,
        timeout_seconds=PROVIDER_DELIVERY_TIMEOUT_SECONDS,
    )
    if isinstance(request_result, MessagingProviderRequestFailure):
        retryable = (
            request_result.classification == "connection_unavailable" or platform == "discord"
        )
        outcome = _outcome(
            state="retryable" if retryable else "delivery_unknown",
            failure_code=(
                "provider_connection_unavailable"
                if request_result.classification == "connection_unavailable"
                else "provider_delivery_ambiguous"
            ),
            retry_after_ms=DEFAULT_RETRY_AFTER_MS if retryable else None,
        )
        return _log_delivery_outcome(log_fields, started_ms, outcome)
    response = request_result.response
    payload = _response_payload(response)
    _log_provider_response(log_fields, started_ms, platform, response, payload)
    if response.status_code == 429:
        outcome = _outcome(
            state="retryable",
            failure_code="provider_http_429",
            retry_after_ms=_retry_after_ms(platform, response, payload),
        )
        return _log_delivery_outcome(log_fields, started_ms, outcome, response=response)
    if _is_ambiguous_provider_status(response.status_code):
        retryable = platform == "discord"
        outcome = _outcome(
            state="retryable" if retryable else "delivery_unknown",
            failure_code=f"provider_http_{response.status_code}",
            retry_after_ms=(_retry_after_ms(platform, response, payload) if retryable else None),
        )
        return _log_delivery_outcome(log_fields, started_ms, outcome, response=response)
    if response.status_code < 200 or response.status_code >= 300:
        outcome = _outcome(
            state="failed",
            failure_code=f"provider_http_{response.status_code}",
        )
        return _log_delivery_outcome(log_fields, started_ms, outcome, response=response)
    if platform == "telegram" and payload is not None and payload.get("ok") is False:
        outcome = _outcome(state="failed", failure_code="provider_success_rejected")
        return _log_delivery_outcome(log_fields, started_ms, outcome, response=response)
    provider_message_id = _response_message_id(platform, payload) if payload is not None else None
    if provider_message_id is None:
        outcome = _outcome(
            state="delivery_unknown",
            failure_code="provider_success_receipt_invalid",
        )
        return _log_delivery_outcome(log_fields, started_ms, outcome, response=response)
    outcome = _outcome(
        state="sent",
        provider_message_id=provider_message_id,
        next_request_delay_ms=_success_cooldown_ms(platform, response),
    )
    return _log_delivery_outcome(log_fields, started_ms, outcome, response=response)

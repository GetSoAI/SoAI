"""SoAI - Messaging provider JSON request policy [backend/features/messaging/provider_json_request.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import httpx2

from core.errors.exceptions import ApiError, ServiceUnavailableError, ValidationError
from core.logging.trace import get_logger
from core.messaging.observability_emission import log_messaging_diagnostic
from core.messaging.observability_fields import MessagingLogFields
from core.network.http_json import read_http_json_dict
from core.timing.monotonic import monotonic_ms
from features.messaging.provider_error_codes import read_messaging_provider_error_code

if TYPE_CHECKING:
    from core.conversations.conversation_source import MessagingPlatform
    from core.types.json import JSONDict

__all__ = ("request_messaging_provider_json",)

PROVIDER_JSON_TIMEOUT_SECONDS = 15.0
LOGGER_NAME = "SoAI.features.messaging.provider_json_request"
RETRYABLE_PROVIDER_STATUS_CODES = (429, 500, 502, 503, 504)


def _log_transport_failure(
    *,
    platform: MessagingPlatform | None,
    operation: str,
    account_id: str | None,
    started_ms: int,
    failure_code: str,
) -> None:
    log_messaging_diagnostic(
        get_logger(LOGGER_NAME),
        message="Messaging provider request did not reach the provider.",
        log_fields=MessagingLogFields(
            operation=operation,
            platform=platform,
            phase="complete",
            outcome="retryable",
            account_id=account_id,
            elapsed_ms=monotonic_ms() - started_ms,
            failure_code=failure_code,
        ),
    )


def _log_response(
    *,
    platform: MessagingPlatform | None,
    operation: str,
    account_id: str | None,
    started_ms: int,
    response: httpx2.Response,
) -> None:
    logger = get_logger(LOGGER_NAME)
    status_code = response.status_code
    if status_code in RETRYABLE_PROVIDER_STATUS_CODES:
        outcome: Literal["success", "failure", "retryable"] = "retryable"
    elif 200 <= status_code < 300:
        outcome = "success"
    else:
        outcome = "failure"
    log_messaging_diagnostic(
        logger,
        message="Messaging provider request completed.",
        log_fields=MessagingLogFields(
            operation=operation,
            platform=platform,
            phase="complete",
            outcome=outcome,
            account_id=account_id,
            elapsed_ms=monotonic_ms() - started_ms,
            provider_status=status_code,
            provider_error_code=(
                None if outcome == "success" else read_messaging_provider_error_code(response)
            ),
        ),
    )


async def request_messaging_provider_json(
    http_client: httpx2.AsyncClient,
    *,
    method: Literal["GET", "POST", "DELETE"],
    url: str,
    operation_label: str,
    operation: str,
    platform: MessagingPlatform | None = None,
    account_id: str | None = None,
    headers: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
    json_body: JSONDict | None = None,
    validation_error_code: str | None = None,
) -> JSONDict:
    started_ms = monotonic_ms()
    log_messaging_diagnostic(
        get_logger(LOGGER_NAME),
        message="Messaging provider request started.",
        log_fields=MessagingLogFields(
            operation=operation,
            platform=platform,
            phase="start",
            account_id=account_id,
        ),
    )
    try:
        response = await http_client.request(
            method,
            url,
            headers=headers,
            params=params,
            json=json_body,
            follow_redirects=False,
            timeout=PROVIDER_JSON_TIMEOUT_SECONDS,
        )
    except httpx2.TimeoutException as exception:
        _log_transport_failure(
            platform=platform,
            operation=operation,
            account_id=account_id,
            started_ms=started_ms,
            failure_code="provider_request_timeout",
        )
        raise ServiceUnavailableError(f"{operation_label} timed out.") from exception
    except httpx2.RequestError as exception:
        _log_transport_failure(
            platform=platform,
            operation=operation,
            account_id=account_id,
            started_ms=started_ms,
            failure_code="provider_request_unreachable",
        )
        raise ServiceUnavailableError(
            f"{operation_label} could not reach the provider."
        ) from exception
    _log_response(
        platform=platform,
        operation=operation,
        account_id=account_id,
        started_ms=started_ms,
        response=response,
    )
    if response.status_code in RETRYABLE_PROVIDER_STATUS_CODES:
        raise ServiceUnavailableError(f"{operation_label} is temporarily unavailable.")
    if response.status_code < 200 or response.status_code >= 300:
        if validation_error_code is not None:
            raise ApiError(
                f"{operation_label} was rejected by the provider.",
                code=validation_error_code,
                http_status=422,
            )
        raise ValidationError(f"{operation_label} was rejected by the provider.")
    return read_http_json_dict(response, field=f"{operation_label} response")

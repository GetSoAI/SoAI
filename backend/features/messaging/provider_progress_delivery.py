"""SoAI - Provider-specific Messaging progress delivery [backend/features/messaging/provider_progress_delivery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Literal

import httpx2

from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.messaging.observability_emission import log_messaging_diagnostic
from core.messaging.observability_fields import MessagingLogFields
from core.network.http_json import read_http_json_dict
from core.timing.monotonic import monotonic_ms
from features.messaging.provider_delivery_requests import (
    MessagingProviderRequestFailure,
    build_messaging_progress_request,
    execute_messaging_provider_request,
)

if TYPE_CHECKING:
    from core.conversations.conversation_source import MessagingPlatform
    from core.types.json import JSONDict

__all__ = ("send_messaging_provider_progress",)

LOGGER_NAME = "SoAI.features.messaging.provider_progress_delivery"
OPERATION_PROGRESS = "messaging.provider.progress"
PROVIDER_PROGRESS_TIMEOUT_SECONDS = 5.0


async def send_messaging_provider_progress(
    *,
    http_client: httpx2.AsyncClient,
    platform: MessagingPlatform,
    credentials: JSONDict,
    remote_thread_key: str,
) -> Literal["sent", "failed", "unsupported"]:
    log_fields = MessagingLogFields(
        operation=OPERATION_PROGRESS,
        platform=platform,
        phase="start",
    )
    request = build_messaging_progress_request(
        platform=platform,
        credentials=credentials,
        remote_thread_key=remote_thread_key,
    )
    if request is None:
        log_messaging_diagnostic(
            get_logger(LOGGER_NAME),
            message="Messaging provider progress is unsupported.",
            log_fields=replace(log_fields, phase="complete", outcome="skipped"),
        )
        return "unsupported"
    started_ms = monotonic_ms()
    log_messaging_diagnostic(
        get_logger(LOGGER_NAME),
        message="Messaging provider progress request started.",
        log_fields=log_fields,
    )
    request_result = await execute_messaging_provider_request(
        http_client,
        request,
        timeout_seconds=PROVIDER_PROGRESS_TIMEOUT_SECONDS,
    )
    if isinstance(request_result, MessagingProviderRequestFailure):
        log_messaging_diagnostic(
            get_logger(LOGGER_NAME),
            message="Messaging provider progress request failed.",
            log_fields=replace(
                log_fields,
                phase="complete",
                outcome="retryable",
                elapsed_ms=monotonic_ms() - started_ms,
                failure_code="provider_progress_unavailable",
            ),
        )
        return "failed"
    response = request_result.response
    sent = response.status_code == 204 if platform == "discord" else False
    if platform == "telegram" and 200 <= response.status_code < 300:
        try:
            payload = read_http_json_dict(response, field="Telegram progress response")
        except ValidationError:
            payload = {}
        sent = payload.get("ok") is True
    log_messaging_diagnostic(
        get_logger(LOGGER_NAME),
        message="Messaging provider progress request completed.",
        log_fields=replace(
            log_fields,
            phase="complete",
            outcome="success" if sent else "failure",
            elapsed_ms=monotonic_ms() - started_ms,
            provider_status=response.status_code,
            failure_code=None if sent else "provider_progress_rejected",
        ),
    )
    return "sent" if sent else "failed"

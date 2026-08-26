"""SoAI - Messaging webhook request diagnostics [backend/features/api/routes/messaging/webhook_observability.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from core.messaging.observability_emission import log_messaging_diagnostic
from core.messaging.observability_fields import (
    MessagingLogFields,
    resolve_messaging_log_outcome,
)
from core.runtime.request_trace_id import get_request_trace_id
from core.timing.monotonic import monotonic_ms

if TYPE_CHECKING:
    from fastapi import Request

    from core.conversations.conversation_source import MessagingPlatform
    from core.messaging.ingress_models import NormalizedMessagingEvent

__all__ = (
    "MessagingWebhookTrace",
    "begin_messaging_webhook_trace",
    "log_messaging_webhook_admission",
    "log_messaging_webhook_authentication",
    "log_messaging_webhook_body",
    "log_messaging_webhook_complete",
    "log_messaging_webhook_normalization",
    "log_messaging_webhook_rate",
)

LOGGER_NAME = "SoAI.features.api.webhook_observability"


@dataclass(frozen=True, slots=True)
class MessagingWebhookTrace:
    platform: MessagingPlatform
    account_id: str
    operation: str
    trace_id: str | None
    started_ms: int


def begin_messaging_webhook_trace(
    request: Request,
    *,
    platform: MessagingPlatform,
    account_id: str,
    operation: str,
) -> MessagingWebhookTrace:
    trace = MessagingWebhookTrace(
        platform=platform,
        account_id=account_id,
        operation=operation,
        trace_id=get_request_trace_id(request),
        started_ms=monotonic_ms(),
    )
    log_messaging_diagnostic(
        get_logger(LOGGER_NAME),
        message="Messaging webhook request started.",
        log_fields=_trace_fields(trace),
    )
    return trace


def _trace_fields(trace: MessagingWebhookTrace) -> MessagingLogFields:
    return MessagingLogFields(
        operation=trace.operation,
        platform=trace.platform,
        phase="start",
        account_id=trace.account_id,
        trace_id=trace.trace_id,
    )


def log_messaging_webhook_authentication(
    trace: MessagingWebhookTrace,
    *,
    accepted: bool,
    failure_code: str | None = None,
) -> None:
    log_messaging_diagnostic(
        get_logger(LOGGER_NAME),
        message="Messaging webhook authentication evaluated.",
        log_fields=replace(
            _trace_fields(trace),
            phase="progress",
            outcome="success" if accepted else "rejected",
            failure_code=failure_code,
        ),
    )


def log_messaging_webhook_rate(
    trace: MessagingWebhookTrace,
    *,
    accepted: bool,
    classification: str | None = None,
    retry_after_ms: int | None = None,
) -> None:
    log_messaging_diagnostic(
        get_logger(LOGGER_NAME),
        message="Messaging webhook rate decision evaluated.",
        log_fields=replace(
            _trace_fields(trace),
            phase="progress",
            outcome="success" if accepted else "rejected",
            classification=classification,
            failure_code=None if accepted else "messaging_webhook_rate_limited",
            retry_after_ms=retry_after_ms,
        ),
    )


def log_messaging_webhook_body(
    trace: MessagingWebhookTrace,
    *,
    body_bytes: int,
) -> None:
    log_messaging_diagnostic(
        get_logger(LOGGER_NAME),
        message="Messaging webhook body was read.",
        log_fields=replace(
            _trace_fields(trace),
            phase="progress",
            outcome="success",
            body_bytes=body_bytes,
        ),
    )


def log_messaging_webhook_normalization(
    trace: MessagingWebhookTrace,
    events: tuple[NormalizedMessagingEvent, ...],
) -> None:
    counts: dict[tuple[str, str], int] = {}
    for event in events:
        key = (event.classification, event.remote_thread_type)
        counts[key] = counts.get(key, 0) + 1
    if not counts:
        counts[("none", "none")] = 0
    for (classification, remote_thread_type), event_count in counts.items():
        log_messaging_diagnostic(
            get_logger(LOGGER_NAME),
            message="Messaging webhook events normalized.",
            log_fields=replace(
                _trace_fields(trace),
                phase="progress",
                outcome="success",
                classification=classification,
                remote_thread_type=remote_thread_type,
                event_count=event_count,
            ),
        )


def log_messaging_webhook_admission(
    trace: MessagingWebhookTrace,
    event: NormalizedMessagingEvent,
    *,
    admission_status: str,
) -> None:
    log_messaging_diagnostic(
        get_logger(LOGGER_NAME),
        message="Messaging webhook event admission completed.",
        log_fields=replace(
            _trace_fields(trace),
            phase="progress",
            outcome="success",
            classification=event.classification,
            remote_thread_type=event.remote_thread_type,
            admission_status=admission_status,
        ),
    )


def log_messaging_webhook_complete(
    trace: MessagingWebhookTrace,
    *,
    outcome: str,
    event_count: int | None = None,
    failure_code: str | None = None,
) -> None:
    log_messaging_diagnostic(
        get_logger(LOGGER_NAME),
        message="Messaging webhook request completed.",
        log_fields=replace(
            _trace_fields(trace),
            phase="complete",
            outcome=resolve_messaging_log_outcome(outcome),
            elapsed_ms=monotonic_ms() - trace.started_ms,
            failure_code=failure_code,
            event_count=event_count,
        ),
    )

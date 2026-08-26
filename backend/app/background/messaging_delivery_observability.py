"""SoAI - Durable Messaging delivery lifecycle reporting [backend/app/background/messaging_delivery_observability.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from core.messaging.observability_emission import (
    log_messaging_diagnostic,
    log_messaging_lifecycle,
)
from core.messaging.observability_fields import (
    MessagingLogFields,
    resolve_messaging_log_outcome,
)

if TYPE_CHECKING:
    from core.messaging.delivery_models import MessagingDeliveryAttempt

__all__ = (
    "report_delivery_chunk_state",
    "report_delivery_claimed",
    "report_delivery_worker_backoff",
    "report_delivery_worker_transition",
)

LOGGER_NAME = "SoAI.app.background.messaging_delivery_observability"
OPERATION_CHUNK = "messaging.delivery.chunk"
OPERATION_CLAIM = "messaging.delivery.claim"
OPERATION_WORKER = "messaging.delivery.worker"


def report_delivery_worker_transition(
    *,
    outcome: str,
    outcome_detail: str,
    event_count: int | None = None,
    failure_code: str | None = None,
) -> None:
    log_messaging_lifecycle(
        get_logger(LOGGER_NAME),
        message="Messaging delivery worker state changed.",
        log_fields=MessagingLogFields(
            operation=OPERATION_WORKER,
            phase="complete",
            outcome=resolve_messaging_log_outcome(outcome),
            outcome_detail=outcome_detail,
            failure_code=failure_code,
            event_count=event_count,
        ),
    )


def report_delivery_claimed(attempt: MessagingDeliveryAttempt) -> None:
    log_messaging_diagnostic(
        get_logger(LOGGER_NAME),
        message="Messaging delivery claim acquired.",
        log_fields=MessagingLogFields(
            operation=OPERATION_CLAIM,
            platform=attempt.platform,
            phase="complete",
            outcome="success",
            account_id=attempt.account_id,
            attempt=attempt.chunk_attempt_count,
            delivery_id=attempt.delivery_id,
            chunk_ordinal=attempt.ordinal,
        ),
    )


def report_delivery_worker_backoff(
    *,
    operation: str,
    attempt: int,
    retry_after_ms: int,
    delivery_id: str | None = None,
) -> None:
    log_messaging_diagnostic(
        get_logger(LOGGER_NAME),
        message="Messaging delivery worker is waiting before retry.",
        log_fields=MessagingLogFields(
            operation=operation,
            phase="progress",
            outcome="retryable",
            attempt=attempt,
            retry_after_ms=retry_after_ms,
            delivery_id=delivery_id,
        ),
    )


def report_delivery_chunk_state(
    attempt: MessagingDeliveryAttempt,
    *,
    outcome: str,
    outcome_detail: str,
    failure_code: str | None = None,
    retry_after_ms: int | None = None,
) -> None:
    log_messaging_diagnostic(
        get_logger(LOGGER_NAME),
        message="Messaging delivery chunk state changed.",
        log_fields=MessagingLogFields(
            operation=OPERATION_CHUNK,
            platform=attempt.platform,
            phase="progress",
            outcome=resolve_messaging_log_outcome(outcome),
            account_id=attempt.account_id,
            attempt=attempt.chunk_attempt_count,
            failure_code=failure_code,
            retry_after_ms=retry_after_ms,
            delivery_id=attempt.delivery_id,
            chunk_ordinal=attempt.ordinal,
            outcome_detail=outcome_detail,
        ),
    )

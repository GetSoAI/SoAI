"""SoAI - Messaging Gateway lifecycle and reconciliation reporting [backend/app/background/messaging_gateway_observability.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.logging.rate_limited_logger import RateLimitedLogger
from core.logging.trace import get_logger
from core.messaging.observability_emission import (
    log_messaging_bounded_failure,
    log_messaging_lifecycle,
    log_messaging_trace,
)
from core.messaging.observability_fields import MessagingLogFields

if TYPE_CHECKING:
    from app.background.messaging_account_runtime_supervisor import (
        MessagingAccountRuntimeSummary,
    )

__all__ = ("MessagingGatewayReporter",)

LOGGER_NAME = "SoAI.app.background.messaging_gateway_observability"
OPERATION_GATEWAY = "messaging.gateway.lifecycle"
OPERATION_RECONCILE = "messaging.gateway.reconcile"
FAILURE_SUMMARY_INTERVAL_SECONDS = 60.0


class MessagingGatewayReporter:
    def __init__(self) -> None:
        self._admission_state = "closed"
        self._failure_limiter = RateLimitedLogger(
            interval_seconds=FAILURE_SUMMARY_INTERVAL_SECONDS,
        )

    def report_started(self) -> None:
        log_messaging_lifecycle(
            get_logger(LOGGER_NAME),
            message="Messaging Gateway started.",
            log_fields=MessagingLogFields(
                operation=OPERATION_GATEWAY,
                phase="complete",
                outcome="success",
            ),
        )

    def report_reconciled(
        self,
        summary: MessagingAccountRuntimeSummary,
        *,
        elapsed_ms: int,
    ) -> None:
        fields = MessagingLogFields(
            operation=OPERATION_RECONCILE,
            phase="complete",
            outcome="success",
            elapsed_ms=elapsed_ms,
            account_count=summary.account_count,
            skipped_count=summary.skipped_count,
        )
        log_messaging_trace(
            get_logger(LOGGER_NAME),
            message="Messaging Gateway reconciliation completed.",
            log_fields=fields,
        )
        if self._admission_state == "open":
            return
        recovered = self._admission_state == "degraded"
        self._admission_state = "open"
        log_messaging_lifecycle(
            get_logger(LOGGER_NAME),
            message=(
                "Messaging Gateway recovered and admission reopened."
                if recovered
                else "Messaging Gateway admission opened."
            ),
            log_fields=replace(fields, operation=OPERATION_GATEWAY),
        )

    def report_failure(
        self,
        exception: Exception,
        *,
        attempt: int,
        elapsed_ms: int,
        retry_after_ms: int,
    ) -> None:
        error = coerce_to_soai_error(exception, operation=OPERATION_RECONCILE)
        fields = MessagingLogFields(
            operation=OPERATION_RECONCILE,
            phase="complete",
            outcome="retryable",
            attempt=attempt,
            elapsed_ms=elapsed_ms,
            failure_code=str(error.code),
            retry_after_ms=retry_after_ms,
        )
        log_messaging_bounded_failure(
            get_logger(LOGGER_NAME),
            self._failure_limiter,
            message="Messaging Gateway reconciliation keeps failing.",
            log_fields=fields,
        )
        if self._admission_state == "degraded":
            return
        self._admission_state = "degraded"
        log_messaging_lifecycle(
            get_logger(LOGGER_NAME),
            message="Messaging Gateway became degraded and admission closed.",
            log_fields=replace(fields, operation=OPERATION_GATEWAY, outcome="failure"),
        )

    def report_stopped(self) -> None:
        self._admission_state = "closed"
        log_messaging_lifecycle(
            get_logger(LOGGER_NAME),
            message="Messaging Gateway stopped.",
            log_fields=MessagingLogFields(
                operation=OPERATION_GATEWAY,
                phase="complete",
                outcome="success",
            ),
        )

"""SoAI - Messaging delivery worker retry and uncertain-outcome settlement [backend/app/background/messaging_delivery_recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from app.background.messaging_delivery_observability import (
    report_delivery_worker_backoff,
)
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.messaging.delivery_models import MESSAGING_DELIVERY_CLAIM_OWNER
from core.timing.retry_backoff import compute_exponential_backoff_seconds

if TYPE_CHECKING:
    from core.messaging.delivery_models import MessagingDeliveryAttempt
    from core.messaging.protocols import DatabaseMessagingDeliveriesProtocol

__all__ = (
    "settle_messaging_delivery_worker_failure",
    "wait_for_messaging_delivery_recovery",
)

LOGGER_NAME = "SoAI.app.background.messaging_delivery_recovery"
FAILURE_BACKOFF_MAX_SECONDS = 30.0
OPERATION_SETTLEMENT = "messaging.delivery.settle_worker_failure"


async def wait_for_messaging_delivery_recovery(
    shutdown_event: asyncio.Event,
    attempt: int,
    *,
    operation: str,
    delivery_id: str | None = None,
) -> None:
    delay = compute_exponential_backoff_seconds(
        attempt,
        base_seconds=1.0,
        maximum_seconds=FAILURE_BACKOFF_MAX_SECONDS,
        jitter_ratio=0.2,
    )
    report_delivery_worker_backoff(
        operation=operation,
        attempt=attempt,
        retry_after_ms=int(delay * 1000),
        delivery_id=delivery_id,
    )
    try:
        await asyncio.wait_for(shutdown_event.wait(), timeout=delay)
    except TimeoutError:
        return


async def settle_messaging_delivery_worker_failure(
    *,
    database_deliveries: DatabaseMessagingDeliveriesProtocol,
    attempt: MessagingDeliveryAttempt,
    server_boot_id: str,
    shutdown_event: asyncio.Event,
) -> None:
    settlement_attempt = 0
    while not shutdown_event.is_set():
        try:
            await database_deliveries.settle_worker_failure(
                delivery_id=attempt.delivery_id,
                claim_generation=attempt.claim_generation,
                claim_owner=MESSAGING_DELIVERY_CLAIM_OWNER,
                server_boot_id=server_boot_id,
            )
            return
        except RECOVERABLE_EXCEPTIONS as exception:
            if settlement_attempt == 0:
                log_handled_exception(
                    get_logger(LOGGER_NAME),
                    exception,
                    message="Messaging delivery failure settlement will be retried.",
                    operation=OPERATION_SETTLEMENT,
                    level="warning",
                    details={"delivery_id": attempt.delivery_id},
                )
            await wait_for_messaging_delivery_recovery(
                shutdown_event,
                settlement_attempt,
                operation=OPERATION_SETTLEMENT,
                delivery_id=attempt.delivery_id,
            )
            settlement_attempt += 1

"""SoAI - Messaging account recovery backoff policy [backend/features/messaging/account_recovery_backoff.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import TYPE_CHECKING

from core.concurrency.shutdown_waits import wait_for_shutdown_or_schedule_change
from core.logging.trace import get_logger
from core.messaging.observability_emission import log_messaging_diagnostic
from core.timing.retry_backoff import compute_exponential_backoff_seconds

if TYPE_CHECKING:
    from core.messaging.observability_fields import MessagingLogFields

__all__ = ("wait_for_messaging_account_recovery",)

ACCOUNT_RECOVERY_BASE_SECONDS = 1.0
ACCOUNT_RECOVERY_MAXIMUM_SECONDS = 60.0
LOGGER_NAME = "SoAI.features.messaging.account_recovery_backoff"


async def wait_for_messaging_account_recovery(
    shutdown_event: asyncio.Event,
    attempt: int,
    *,
    log_fields: MessagingLogFields,
) -> bool:
    delay = compute_exponential_backoff_seconds(
        attempt,
        base_seconds=ACCOUNT_RECOVERY_BASE_SECONDS,
        maximum_seconds=ACCOUNT_RECOVERY_MAXIMUM_SECONDS,
    )
    log_messaging_diagnostic(
        get_logger(LOGGER_NAME),
        message="Messaging account runtime is waiting before its next recovery attempt.",
        log_fields=replace(
            log_fields,
            phase="progress",
            outcome="retryable",
            attempt=attempt,
            retry_after_ms=int(delay * 1000),
        ),
    )
    outcome = await wait_for_shutdown_or_schedule_change(
        shutdown_event,
        None,
        delay,
    )
    return outcome == "timeout"

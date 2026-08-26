"""SoAI - Messaging provider progress projection [backend/app/background/messaging_progress_worker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import httpx2

from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.licensing.admission import LicensingOperationClass
from core.logging.rate_limited_logger import RateLimitedLogger
from core.logging.trace import get_logger
from core.runtime.network_policy import is_offline_mode_enabled
from core.timing.epoch import epoch_ms
from features.messaging.provider_progress_delivery import (
    send_messaging_provider_progress,
)

if TYPE_CHECKING:
    from core.licensing.protocols import LicensingStatusProtocol
    from core.messaging.account_models import MessagingProgressTarget
    from core.messaging.protocols import DatabaseMessagingAccountsProtocol
    from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = ("run_messaging_progress_worker",)

LOGGER_NAME = "SoAI.app.background.messaging_progress_worker"
PROGRESS_ACTIVE_DELAY_MS = 3_000
PROGRESS_BATCH_SIZE = 100
PROGRESS_REFRESH_SECONDS = 4.0
PROGRESS_WARNING_INTERVAL_SECONDS = 60.0


def _log_progress_failure(
    failure_logger: RateLimitedLogger,
    *,
    account_id: str,
    input_id: str,
) -> None:
    should_emit, suppressed_count = failure_logger.should_emit()
    if not should_emit:
        return
    get_logger(LOGGER_NAME).warning(
        "".join(
            (
                "Messaging progress indication failed; the canonical turn continues. ",
                "account_id=%s input_id=%s suppressed=%d",
            ),
        ),
        account_id,
        input_id,
        suppressed_count,
    )


async def _refresh_progress_target(
    *,
    http_client: httpx2.AsyncClient,
    target: MessagingProgressTarget,
    failure_logger: RateLimitedLogger,
) -> None:
    try:
        outcome = await send_messaging_provider_progress(
            http_client=http_client,
            platform=target.platform,
            credentials=target.credentials,
            remote_thread_key=target.remote_thread_key,
        )
    except HANDLED_RUNTIME_EXCEPTIONS:
        _log_progress_failure(
            failure_logger,
            account_id=target.account_id,
            input_id=target.input_id,
        )
        return
    if outcome == "failed":
        _log_progress_failure(
            failure_logger,
            account_id=target.account_id,
            input_id=target.input_id,
        )


async def run_messaging_progress_worker(
    *,
    database_accounts: DatabaseMessagingAccountsProtocol,
    http_client: httpx2.AsyncClient,
    runtime_flags: RuntimeFlagsViewProtocol,
    shutdown_event: asyncio.Event,
    licensing_status: LicensingStatusProtocol,
) -> None:
    failure_logger = RateLimitedLogger(
        interval_seconds=PROGRESS_WARNING_INTERVAL_SECONDS,
    )
    while not shutdown_event.is_set():
        try:
            await asyncio.wait_for(
                shutdown_event.wait(),
                timeout=PROGRESS_REFRESH_SECONDS,
            )
        except TimeoutError:
            await _refresh_progress_batch(
                database_accounts=database_accounts,
                http_client=http_client,
                runtime_flags=runtime_flags,
                shutdown_event=shutdown_event,
                failure_logger=failure_logger,
                licensing_status=licensing_status,
            )
            continue
        return


async def _refresh_progress_batch(
    *,
    database_accounts: DatabaseMessagingAccountsProtocol,
    http_client: httpx2.AsyncClient,
    runtime_flags: RuntimeFlagsViewProtocol,
    shutdown_event: asyncio.Event,
    failure_logger: RateLimitedLogger,
    licensing_status: LicensingStatusProtocol,
) -> None:
    if shutdown_event.is_set() or is_offline_mode_enabled(runtime_flags):
        return
    licensing_admission = await licensing_status.admission(LicensingOperationClass.ORDINARY)
    if not licensing_admission.allowed:
        return
    try:
        targets = await database_accounts.list_progress_targets(
            active_before_ms=epoch_ms() - PROGRESS_ACTIVE_DELAY_MS,
            limit=PROGRESS_BATCH_SIZE,
        )
    except HANDLED_RUNTIME_EXCEPTIONS:
        _log_progress_failure(
            failure_logger,
            account_id="unavailable",
            input_id="unavailable",
        )
        return
    async with asyncio.TaskGroup() as task_group:
        for target in targets:
            _ = task_group.create_task(
                _refresh_progress_target(
                    http_client=http_client,
                    target=target,
                    failure_logger=failure_logger,
                ),
            )

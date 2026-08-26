"""SoAI - Periodic reconciliation for API key quota reservations [backend/app/background/api_key_quota_reservation_reconciler.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.runtime.soai_identifiers import create_system_id
from core.tasks.progress import (
    await_background_task_shutdown,
    run_background_periodic_task,
)
from core.timing.epoch import epoch_ms

if TYPE_CHECKING:
    from core.auth.protocols_database_api_keys import DatabaseAPIKeysProtocol
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
    )

__all__ = (
    "ApiKeyQuotaReservationReconciler",
    "ApiKeyQuotaReservationReconcilerDependencies",
)

LOGGER_NAME = "SoAI.app.background.api_key_quota_reservation_reconciler"
OPERATION = "app.background.api_key_quota_reservation_reconciler.reconcile"


@dataclass(frozen=True, slots=True)
class ApiKeyQuotaReservationReconcilerDependencies:
    config: ConfigProtocol
    database_api_keys: DatabaseAPIKeysProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ApiKeyQuotaReservationReconcilerDependencies",
            cancellation_binder=self.cancellation_binder,
            config=self.config,
            database_api_keys=self.database_api_keys,
            finalizer_tracker=self.finalizer_tracker,
        )


class ApiKeyQuotaReservationReconciler:
    def __init__(self, deps: ApiKeyQuotaReservationReconcilerDependencies) -> None:
        self._deps = deps
        self._logger = get_logger(LOGGER_NAME)
        self._shutdown_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is not None and (not self._task.done()):
            return
        self._reset_task_state()
        interval_raw = self._deps.config.get_int("API.OPENAI.KEY_QUOTAS.RECONCILE_INTERVAL_SEC")
        interval_sec = max(1.0, float(int(interval_raw)))
        batch_raw = self._deps.config.get_int("API.OPENAI.KEY_QUOTAS.RECONCILE_BATCH_LIMIT")
        batch_limit = max(1, int(batch_raw))
        self._task = await self._create_reconcile_task(
            interval_sec=interval_sec,
            batch_limit=batch_limit,
        )

    def _reset_task_state(self) -> None:
        self._shutdown_event = asyncio.Event()
        self._task = None

    async def _create_reconcile_task(
        self,
        *,
        interval_sec: float,
        batch_limit: int,
    ) -> asyncio.Task[None]:
        async def _run_once() -> None:
            try:
                await self._deps.database_api_keys.reconcile_quota_reservations(
                    epoch_ms(),
                    batch_limit=batch_limit,
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    self._logger,
                    exception,
                    message="API key quota reservation reconciliation failed.",
                    operation=OPERATION,
                    level="warning",
                )

        def _build_task() -> asyncio.Task[None]:
            return run_background_periodic_task(
                shutdown_event=self._shutdown_event,
                interval_seconds=interval_sec,
                task=_run_once,
                cancellation_binder=self._deps.cancellation_binder,
                finalizer_tracker=self._deps.finalizer_tracker,
                cancellation_id=create_system_id(
                    subsystem="api_key_quota",
                    owner="reservation_reconcile",
                    include_random_suffix=False,
                ),
                owner="api_key_quota_reservations",
                name="api-key-quota-reservation-reconciler",
                logger=self._logger,
                metadata={
                    "interval_ms": int(interval_sec * 1000.0),
                    "batch_limit": int(batch_limit),
                },
                task_name="api_key_quota_reservation_reconcile",
                run_immediately=False,
            )

        return _build_task()

    async def shutdown(self) -> None:
        self._shutdown_event.set()
        task = self._task
        self._task = None
        await await_background_task_shutdown(
            task,
            logger=self._logger,
            operation="app.background.api_key_quota_reservation_reconciler.shutdown",
            message="API key quota reconciler task failed during shutdown (non-critical).",
            level="debug",
        )

"""SoAI - Durable outbound Messaging delivery worker [backend/app/background/messaging_delivery_worker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx2

from app.background.messaging_delivery_attempt import execute_messaging_delivery_attempt
from app.background.messaging_delivery_event_projection import (
    MessagingDeliveryEventProjection,
    MessagingDeliveryEventProjectionDependencies,
)
from app.background.messaging_delivery_observability import (
    report_delivery_claimed,
    report_delivery_worker_transition,
)
from app.background.messaging_delivery_recovery import (
    settle_messaging_delivery_worker_failure,
    wait_for_messaging_delivery_recovery,
)
from app.background.messaging_progress_worker import run_messaging_progress_worker
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.licensing.admission import LicensingOperationClass
from core.logging.trace import get_logger
from core.messaging.delivery_models import MESSAGING_DELIVERY_CLAIM_OWNER
from core.runtime.network_policy import is_offline_mode_enabled
from core.runtime.soai_identifiers import build_soai_id, create_system_id
from core.tasks.progress import await_background_task_shutdown
from core.tasks.supervised_task_spawner import spawn_supervised_tracked_task

if TYPE_CHECKING:
    from core.events.protocols import DurableEventDeliveryProtocol
    from core.licensing.protocols import LicensingStatusProtocol
    from core.messaging.protocols import (
        DatabaseMessagingAccountsProtocol,
        DatabaseMessagingDeliveriesProtocol,
    )
    from core.runtime.protocols import RuntimeFlagsViewProtocol
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
    )

__all__ = ("MessagingDeliveryWorker", "MessagingDeliveryWorkerDependencies")

LOGGER_NAME = "SoAI.app.background.messaging_delivery_worker"
IDLE_WAIT_SECONDS = 0.25
OPERATION_CLAIM = "messaging.delivery.claim"
OPERATION_WORKER = "messaging.delivery.worker"
OPERATION_SHUTDOWN = "messaging.delivery.shutdown"


@dataclass(frozen=True, slots=True)
class MessagingDeliveryWorkerDependencies:
    durable_delivery: DurableEventDeliveryProtocol
    database_deliveries: DatabaseMessagingDeliveriesProtocol
    database_accounts: DatabaseMessagingAccountsProtocol
    http_client: httpx2.AsyncClient
    runtime_flags: RuntimeFlagsViewProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    licensing_status: LicensingStatusProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MessagingDeliveryWorkerDependencies",
            durable_delivery=self.durable_delivery,
            database_deliveries=self.database_deliveries,
            database_accounts=self.database_accounts,
            http_client=self.http_client,
            runtime_flags=self.runtime_flags,
            cancellation_binder=self.cancellation_binder,
            finalizer_tracker=self.finalizer_tracker,
            licensing_status=self.licensing_status,
        )


class MessagingDeliveryWorker:
    def __init__(self, deps: MessagingDeliveryWorkerDependencies) -> None:
        self._deps = deps
        self._shutdown_event = asyncio.Event()
        self._wake_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._progress_task: asyncio.Task[None] | None = None
        self._event_projection: MessagingDeliveryEventProjection | None = None
        self._server_boot_id = ""

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._shutdown_event = asyncio.Event()
        self._wake_event = asyncio.Event()
        self._server_boot_id = create_system_id(
            subsystem="messaging_delivery",
            owner="server_boot",
            include_random_suffix=True,
        )
        recovered_count = await self._deps.database_deliveries.reconcile_prior_boot_deliveries(
            current_server_boot_id=self._server_boot_id,
        )
        report_delivery_worker_transition(
            outcome="success",
            outcome_detail="recovered_prior_boot" if recovered_count else "started",
            event_count=recovered_count,
        )
        self._event_projection = MessagingDeliveryEventProjection(
            MessagingDeliveryEventProjectionDependencies(
                durable_delivery=self._deps.durable_delivery,
                database_deliveries=self._deps.database_deliveries,
                wake_event=self._wake_event,
            ),
        )
        self._event_projection.subscribe()
        self._task = spawn_supervised_tracked_task(
            self._run,
            cancellation_binder=self._deps.cancellation_binder,
            finalizer_tracker=self._deps.finalizer_tracker,
            cancellation_id=build_soai_id(("sys", "messaging", "delivery")),
            owner="messaging_gateway",
            name="messaging-delivery-worker",
            logger=get_logger(LOGGER_NAME),
        )
        self._progress_task = spawn_supervised_tracked_task(
            lambda: run_messaging_progress_worker(
                database_accounts=self._deps.database_accounts,
                http_client=self._deps.http_client,
                runtime_flags=self._deps.runtime_flags,
                shutdown_event=self._shutdown_event,
                licensing_status=self._deps.licensing_status,
            ),
            cancellation_binder=self._deps.cancellation_binder,
            finalizer_tracker=self._deps.finalizer_tracker,
            cancellation_id=build_soai_id(("sys", "messaging", "progress")),
            owner="messaging_gateway",
            name="messaging-progress-worker",
            logger=get_logger(LOGGER_NAME),
        )

    async def _wait_for_work(self) -> None:
        try:
            await asyncio.wait_for(self._wake_event.wait(), timeout=IDLE_WAIT_SECONDS)
        except TimeoutError:
            return
        finally:
            self._wake_event.clear()

    async def _run(self) -> None:
        claim_failure_attempt = 0
        offline_active = False
        while not self._shutdown_event.is_set():
            if is_offline_mode_enabled(self._deps.runtime_flags):
                if not offline_active:
                    report_delivery_worker_transition(
                        outcome="retryable",
                        outcome_detail="offline",
                        failure_code="offline_mode_enabled",
                    )
                    offline_active = True
                await self._wait_for_work()
                continue
            if offline_active:
                report_delivery_worker_transition(
                    outcome="success",
                    outcome_detail="online",
                )
                offline_active = False
            try:
                licensing_admission = await self._deps.licensing_status.admission(
                    LicensingOperationClass.ORDINARY
                )
                if not licensing_admission.allowed:
                    await self._wait_for_work()
                    continue
                attempt = await self._deps.database_deliveries.claim_next_delivery_attempt(
                    claim_owner=MESSAGING_DELIVERY_CLAIM_OWNER,
                    server_boot_id=self._server_boot_id,
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                if claim_failure_attempt == 0:
                    log_handled_exception(
                        get_logger(LOGGER_NAME),
                        exception,
                        message="Messaging delivery claim failed; retrying with bounded backoff.",
                        operation=OPERATION_CLAIM,
                        level="warning",
                    )
                    report_delivery_worker_transition(
                        outcome="failure",
                        outcome_detail="claim_degraded",
                        failure_code="messaging_delivery_claim_failed",
                    )
                await wait_for_messaging_delivery_recovery(
                    self._shutdown_event,
                    claim_failure_attempt,
                    operation=OPERATION_CLAIM,
                )
                claim_failure_attempt += 1
                continue
            if claim_failure_attempt:
                report_delivery_worker_transition(
                    outcome="success",
                    outcome_detail="claim_recovered",
                )
            claim_failure_attempt = 0
            if attempt is None:
                await self._wait_for_work()
                continue
            report_delivery_claimed(attempt)
            try:
                await execute_messaging_delivery_attempt(
                    deliveries=self._deps.database_deliveries,
                    accounts=self._deps.database_accounts,
                    http_client=self._deps.http_client,
                    attempt=attempt,
                    server_boot_id=self._server_boot_id,
                )
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                log_exception(
                    get_logger(LOGGER_NAME),
                    exception,
                    message="Messaging delivery worker failed; recording uncertain outcome.",
                    operation=OPERATION_WORKER,
                    level="error",
                    details={"delivery_id": attempt.delivery_id},
                )
                await settle_messaging_delivery_worker_failure(
                    database_deliveries=self._deps.database_deliveries,
                    attempt=attempt,
                    server_boot_id=self._server_boot_id,
                    shutdown_event=self._shutdown_event,
                )
            finally:
                self._wake_event.set()

    async def shutdown(self) -> None:
        self._shutdown_event.set()
        self._wake_event.set()
        await await_background_task_shutdown(
            self._task,
            logger=get_logger(LOGGER_NAME),
            operation=OPERATION_SHUTDOWN,
            message="Messaging delivery worker shutdown failed.",
            level="warning",
        )
        self._task = None
        await await_background_task_shutdown(
            self._progress_task,
            logger=get_logger(LOGGER_NAME),
            operation="messaging.progress.shutdown",
            message="Messaging progress worker shutdown failed.",
            level="warning",
        )
        self._progress_task = None
        event_projection = self._event_projection
        self._event_projection = None
        if event_projection is not None:
            event_projection.unsubscribe()
        report_delivery_worker_transition(
            outcome="cancelled",
            outcome_detail="stopped",
        )

"""SoAI - User-owned Messaging transport runtime [backend/app/background/messaging_gateway.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, override

from app.background.messaging_account_deletion_recovery import (
    resume_messaging_account_deletions,
)
from app.background.messaging_account_runtime_supervisor import (
    MessagingAccountRuntimeSupervisor,
    MessagingAccountRuntimeSupervisorDependencies,
)
from app.background.messaging_delivery_worker import (
    MessagingDeliveryWorker,
    MessagingDeliveryWorkerDependencies,
)
from app.background.messaging_gateway_dependencies import MessagingGatewayDependencies
from app.background.messaging_gateway_observability import MessagingGatewayReporter
from app.background.messaging_interaction_resolution_worker import (
    MessagingInteractionResolutionWorker,
    MessagingInteractionResolutionWorkerDependencies,
)
from app.background.runtime_api_dependencies import (
    resolve_api_dependencies_from_runtime,
)
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.licensing.admission import LicensingOperationClass
from core.licensing.enforcement import require_ordinary_licensing
from core.logging.trace import get_logger
from core.messaging.account_validation import require_messaging_account_id
from core.messaging.protocols import MessagingGatewayProtocol
from core.runtime.soai_identifiers import create_system_id
from core.tasks.progress import await_background_task_shutdown
from core.tasks.supervised_task_spawner import spawn_supervised_tracked_task
from core.timing.constants import RESPONSIVE_TIMEOUT_SEC
from core.timing.monotonic import monotonic_ms
from core.timing.retry_backoff import compute_exponential_backoff_seconds
from features.api.runtime.container.types import ApiDependencies
from features.messaging.ingress_publication import publish_messaging_admission

if TYPE_CHECKING:
    from core.messaging.ingress_models import NormalizedMessagingEvent
    from core.types.json import JSONDict

__all__ = ("MessagingGateway",)

LOGGER_NAME = "SoAI.app.background.messaging_gateway"
OPERATION_RECONCILE = "messaging_gateway.reconcile"

RETENTION_CLEANUP_INTERVAL_SECONDS = 15 * 60.0


class MessagingGateway(MessagingGatewayProtocol):
    def __init__(self, deps: MessagingGatewayDependencies) -> None:
        self._deps = deps
        self._admission_open = False
        self._shutdown_event = asyncio.Event()
        self._supervisor_task: asyncio.Task[None] | None = None
        self._account_supervisor: MessagingAccountRuntimeSupervisor | None = None
        self._delivery_worker: MessagingDeliveryWorker | None = None
        self._interaction_worker: MessagingInteractionResolutionWorker | None = None
        self._reconcile_event = asyncio.Event()
        self._initial_reconciliation_event = asyncio.Event()
        self._next_retention_cleanup_at = 0.0
        self._reporter = MessagingGatewayReporter()

    @override
    def request_reconcile(self) -> None:
        self._reconcile_event.set()

    async def _api_dependencies(self) -> ApiDependencies:
        return await resolve_api_dependencies_from_runtime(self._deps.runtime_state)

    @override
    async def get_webhook_account(
        self,
        *,
        account_id: str,
        platform: str,
    ) -> JSONDict | None:
        account = await self._deps.database_messaging_accounts.get_transport_account(
            require_messaging_account_id(account_id),
            platform,
        )
        if account is None or account.get("lifecycle_state") not in (
            "enabled",
            "degraded",
        ):
            return None
        return account

    @override
    async def admit_event(
        self,
        *,
        account_id: str,
        event: NormalizedMessagingEvent,
    ) -> JSONDict:
        if not self._admission_open:
            raise StateError("Messaging admission is closed.")
        await require_ordinary_licensing(self._deps.licensing_status)
        result = await self._deps.database_messaging_ingress.admit_event(
            account_id=require_messaging_account_id(account_id),
            event=event,
        )
        await publish_messaging_admission(await self._api_dependencies(), result)
        self.request_reconcile()
        return result

    async def _run(self) -> None:
        failure_attempt = 0
        while not self._shutdown_event.is_set():
            self._reconcile_event.clear()
            retry_delay: float | None = None
            started_ms = monotonic_ms()
            try:
                api_dependencies = await self._api_dependencies()
                if self._interaction_worker is None:
                    self._interaction_worker = MessagingInteractionResolutionWorker(
                        MessagingInteractionResolutionWorkerDependencies(
                            api_dependencies=api_dependencies,
                            database_ingress=self._deps.database_messaging_ingress,
                        ),
                    )
                await resume_messaging_account_deletions(
                    database_accounts=self._deps.database_messaging_accounts,
                    api_dependencies=api_dependencies,
                    http_client=self._deps.http_client,
                    event_bus=self._deps.event_bus,
                )
                cancellation_results = (
                    await self._deps.database_messaging_ingress.reconcile_pending_cancellations()
                )
                for cancellation_result in cancellation_results:
                    await publish_messaging_admission(api_dependencies, cancellation_result)
                reset_results = (
                    await self._deps.database_messaging_ingress.complete_pending_resets()
                )
                for reset_result in reset_results:
                    await publish_messaging_admission(api_dependencies, reset_result)
                interaction_worker = self._interaction_worker
                if interaction_worker is None:
                    raise StateError("Messaging interaction worker is unavailable.")
                licensing_admission = await self._deps.licensing_status.admission(
                    LicensingOperationClass.ORDINARY
                )
                if licensing_admission.allowed:
                    await interaction_worker.reconcile()
                loop_time = asyncio.get_running_loop().time()
                if loop_time >= self._next_retention_cleanup_at:
                    self._next_retention_cleanup_at = loop_time + RETENTION_CLEANUP_INTERVAL_SECONDS
                    await self._deps.database_messaging_ingress.cleanup_transport_records()
                self._admission_open = True
                account_supervisor = self._account_supervisor
                if account_supervisor is None:
                    raise StateError("Messaging account runtime supervisor is unavailable.")
                summary = await account_supervisor.reconcile()
                failure_attempt = 0
                self._reporter.report_reconciled(
                    summary,
                    elapsed_ms=monotonic_ms() - started_ms,
                )
                self._initial_reconciliation_event.set()
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                self._admission_open = False
                if failure_attempt == 0:
                    log_exception(
                        get_logger(LOGGER_NAME),
                        exception,
                        message="Messaging Gateway reconciliation cycle failed.",
                        operation=OPERATION_RECONCILE,
                        level="warning",
                    )
                retry_delay = compute_exponential_backoff_seconds(
                    failure_attempt,
                    base_seconds=1.0,
                    maximum_seconds=60.0,
                    jitter_ratio=0.2,
                )
                self._reporter.report_failure(
                    exception,
                    attempt=failure_attempt,
                    elapsed_ms=monotonic_ms() - started_ms,
                    retry_after_ms=int(retry_delay * 1000),
                )
                self._initial_reconciliation_event.set()
                failure_attempt += 1
            try:
                wait_event = (
                    self._shutdown_event if retry_delay is not None else self._reconcile_event
                )
                await asyncio.wait_for(
                    wait_event.wait(),
                    timeout=retry_delay or RESPONSIVE_TIMEOUT_SEC,
                )
            except TimeoutError:
                continue

    @override
    async def start(self) -> None:
        if self._supervisor_task is not None and not self._supervisor_task.done():
            return
        self._shutdown_event = asyncio.Event()
        self._reconcile_event = asyncio.Event()
        self._initial_reconciliation_event = asyncio.Event()
        self._admission_open = False
        self._next_retention_cleanup_at = 0.0
        self._reporter = MessagingGatewayReporter()
        self._delivery_worker = MessagingDeliveryWorker(
            MessagingDeliveryWorkerDependencies(
                durable_delivery=self._deps.durable_delivery,
                database_deliveries=self._deps.database_messaging_deliveries,
                database_accounts=self._deps.database_messaging_accounts,
                http_client=self._deps.http_client,
                runtime_flags=self._deps.runtime_flags,
                cancellation_binder=self._deps.cancellation_binder,
                finalizer_tracker=self._deps.finalizer_tracker,
                licensing_status=self._deps.licensing_status,
            ),
        )
        await self._delivery_worker.start()
        self._interaction_worker = None
        self._account_supervisor = MessagingAccountRuntimeSupervisor(
            MessagingAccountRuntimeSupervisorDependencies(
                runtime_state=self._deps.runtime_state,
                runtime_flags=self._deps.runtime_flags,
                http_client=self._deps.http_client,
                database_accounts=self._deps.database_messaging_accounts,
                database_ingress=self._deps.database_messaging_ingress,
                cancellation_binder=self._deps.cancellation_binder,
                finalizer_tracker=self._deps.finalizer_tracker,
                shutdown_event=self._shutdown_event,
            ),
        )
        self._supervisor_task = spawn_supervised_tracked_task(
            self._run,
            name="messaging-gateway-supervisor",
            logger=get_logger(LOGGER_NAME),
            cancellation_binder=self._deps.cancellation_binder,
            cancellation_id=create_system_id(
                subsystem="messaging_gateway",
                owner="supervisor",
                include_random_suffix=False,
            ),
            owner="messaging_gateway",
            finalizer_tracker=self._deps.finalizer_tracker,
        )
        self._reporter.report_started()

    @override
    async def wait_for_initial_reconciliation(self, timeout: float) -> bool:
        try:
            await asyncio.wait_for(
                self._initial_reconciliation_event.wait(),
                timeout=timeout,
            )
        except TimeoutError:
            return False
        return True

    @override
    async def shutdown(self) -> None:
        self._admission_open = False
        self._shutdown_event.set()
        self._reconcile_event.set()
        self._initial_reconciliation_event.set()
        supervisor_task = self._supervisor_task
        self._supervisor_task = None
        await await_background_task_shutdown(
            supervisor_task,
            logger=get_logger(LOGGER_NAME),
            operation="messaging_gateway.shutdown",
            message="Messaging Gateway supervisor shutdown failed.",
            level="warning",
        )
        account_supervisor = self._account_supervisor
        self._account_supervisor = None
        if account_supervisor is not None:
            await account_supervisor.shutdown()
        delivery_worker = self._delivery_worker
        self._delivery_worker = None
        if delivery_worker is not None:
            await delivery_worker.shutdown()
        self._interaction_worker = None
        self._reporter.report_stopped()

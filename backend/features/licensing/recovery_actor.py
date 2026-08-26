"""SoAI - Licensing restart recovery and reconciliation actor [backend/features/licensing/recovery_actor.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.errors.exceptions import ApiError, SecurityError, StateError, ValidationError
from core.licensing.errors import LicensingIntegrityError
from core.licensing.protocols import (
    LicensingRepairPlaneCoordinatorProtocol,
    LicensingRepositoryProtocol,
    LicensingStatusProtocol,
    LicensingWizardRepositoryProtocol,
)
from core.licensing.storage_records import RecoverableLicensingOperation
from core.licensing.trust_material import ReleaseTrustMaterial
from core.licensing.types import Edition
from core.logging.trace import get_logger
from core.runtime.soai_identifiers import create_system_id
from core.tasks.progress import await_background_task_shutdown, run_background_periodic_task
from core.tasks.protocols import TaskCancellationBinderProtocol, TaskFinalizerTrackerProtocol
from core.timing.epoch import epoch_ms
from core.timing.retry_backoff import compute_exponential_backoff_seconds
from core.users.bootstrap_state import BootstrapState
from core.users.protocols_database import DatabaseUsersProtocol
from features.licensing.wizard_operations import WizardLicensingOperations

LOGGER_NAME = "SoAI.features.licensing.recovery_actor"
_MAXIMUM_BACKOFF_MS = 3_600_000
_LOOP_MAXIMUM_WAIT_SECONDS = 60.0


@dataclass(frozen=True, slots=True)
class LicensingRecoveryDependencies:
    edition: Edition
    repository: LicensingRepositoryProtocol
    wizard_repository: LicensingWizardRepositoryProtocol
    wizard_pending: WizardLicensingOperations
    authenticated_operations: WizardLicensingOperations
    runtime: LicensingStatusProtocol
    trust_material: ReleaseTrustMaterial
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    database_users: DatabaseUsersProtocol
    repair_plane_coordinator: LicensingRepairPlaneCoordinatorProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="LicensingRecoveryDependencies",
            authenticated_operations=self.authenticated_operations,
            cancellation_binder=self.cancellation_binder,
            database_users=self.database_users,
            edition=self.edition,
            finalizer_tracker=self.finalizer_tracker,
            repair_plane_coordinator=self.repair_plane_coordinator,
            repository=self.repository,
            runtime=self.runtime,
            trust_material=self.trust_material,
            wizard_pending=self.wizard_pending,
            wizard_repository=self.wizard_repository,
        )


class LicensingRecoveryActor:
    def __init__(self, dependencies: LicensingRecoveryDependencies) -> None:
        self._deps = dependencies
        self._shutdown_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._logger = get_logger(LOGGER_NAME)

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        if self.running:
            return
        self._shutdown_event.clear()
        await self._deps.runtime.resolved_status()
        await self.reconcile_local_startup(epoch_ms())
        await self._reconcile_repair_plane()
        self._task = run_background_periodic_task(
            shutdown_event=self._shutdown_event,
            interval_seconds=_LOOP_MAXIMUM_WAIT_SECONDS,
            task=self._run_iteration,
            cancellation_binder=self._deps.cancellation_binder,
            finalizer_tracker=self._deps.finalizer_tracker,
            cancellation_id=create_system_id(
                subsystem="licensing", owner="recovery", include_random_suffix=False
            ),
            owner="licensing_recovery",
            name="Licensing recovery actor",
            logger=self._logger,
            task_name="licensing_recovery_actor",
            run_immediately=True,
        )

    async def shutdown(self) -> None:
        self._shutdown_event.set()
        task = self._task
        if task is None:
            return
        await await_background_task_shutdown(
            task,
            logger=self._logger,
            operation="licensing_recovery_actor.shutdown",
            message="Licensing recovery actor failed during shutdown.",
        )
        self._task = None

    async def reconcile_local_startup(self, now_ms: int) -> None:
        for operation in await self._deps.repository.recoverable_operations():
            if operation.state == "prepared":
                await self._deps.repository.transition_operation(
                    operation.operation_id,
                    expected_state="prepared",
                    target_state="cancelled",
                    updated_at_ms=now_ms,
                )
            elif operation.state in {"sending", "reconciling"}:
                await self._mark_outcome_unknown(operation, now_ms)

    async def reconcile_startup(self, now_ms: int) -> None:
        operations = await self._deps.repository.recoverable_operations()
        for operation in operations:
            try:
                await self._reconcile_operation(operation, now_ms)
            except (ApiError, SecurityError):
                continue
            except (LicensingIntegrityError, StateError, ValidationError):
                await self._fail_if_current(operation, now_ms)

    async def _run_iteration(self) -> None:
        try:
            await self.reconcile_startup(epoch_ms())
            await self._reconcile_repair_plane()
        except (LicensingIntegrityError, StateError, ValidationError) as exception:
            self._logger.warning(
                "Licensing recovery iteration rejected local state: %s",
                type(exception).__name__,
            )

    async def _reconcile_repair_plane(self) -> None:
        status = await self._deps.runtime.dynamic_status()
        await self._deps.repair_plane_coordinator.reconcile(status.requires_repair_plane)

    async def _reconcile_operation(
        self, operation: RecoverableLicensingOperation, now_ms: int
    ) -> None:
        if operation.state == "prepared":
            await self._deps.repository.transition_operation(
                operation.operation_id,
                expected_state="prepared",
                target_state="cancelled",
                updated_at_ms=now_ms,
            )
            return
        if operation.state in {"sending", "reconciling"}:
            await self._mark_outcome_unknown(operation, now_ms)
            return
        if operation.state not in {"outcome_unknown", "retry_wait"}:
            raise StateError("Recoverable licensing operation state is invalid.")
        if operation.next_retry_at_ms is None or operation.next_retry_at_ms > now_ms:
            return
        if self._deps.trust_material.catalog is None:
            return
        if operation.state == "retry_wait":
            transitioned = await self._deps.repository.transition_operation(
                operation.operation_id,
                expected_state="retry_wait",
                target_state="outcome_unknown",
                next_retry_at_ms=now_ms,
                updated_at_ms=now_ms,
            )
            if not transitioned:
                return
        owner = await self._operation_owner()
        await owner.reconcile_operation(
            draft_revision=await self._draft_revision(),
            now_ms=now_ms,
        )

    async def _mark_outcome_unknown(
        self, operation: RecoverableLicensingOperation, now_ms: int
    ) -> None:
        await self._deps.repository.transition_operation(
            operation.operation_id,
            expected_state=operation.state,
            target_state="outcome_unknown",
            updated_at_ms=now_ms,
            next_retry_at_ms=now_ms + _retry_delay(operation),
        )

    async def _fail_if_current(self, operation: RecoverableLicensingOperation, now_ms: int) -> None:
        current = await self._deps.repository.latest_operation()
        if current is None or current.get("operation_id") != operation.operation_id:
            return
        state = current.get("state")
        if state not in {"prepared", "sending", "outcome_unknown", "reconciling", "retry_wait"}:
            return
        await self._deps.repository.transition_operation(
            operation.operation_id,
            expected_state=str(state),
            target_state="failed",
            terminal_code="invalid_contract",
            updated_at_ms=now_ms,
        )

    async def _draft_revision(self) -> int:
        draft = await self._deps.wizard_repository.read_wizard_draft(self._deps.edition)
        return int(draft["revision"])

    async def _operation_owner(self) -> WizardLicensingOperations:
        state = await self._deps.database_users.get_bootstrap_state()
        if state is BootstrapState.COMPLETE:
            return self._deps.authenticated_operations
        if state is BootstrapState.UNINITIALIZED:
            return self._deps.wizard_pending
        raise StateError("Licensing operation owner cannot be resolved.")


def _retry_delay(operation: RecoverableLicensingOperation) -> int:
    return int(
        compute_exponential_backoff_seconds(
            max(0, operation.attempt_count - 1),
            base_seconds=5.0,
            maximum_seconds=_MAXIMUM_BACKOFF_MS / 1_000,
            jitter_ratio=0.2,
        )
        * 1_000
    )


__all__ = ("LicensingRecoveryActor", "LicensingRecoveryDependencies")

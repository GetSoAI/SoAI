"""SoAI - Application update service [backend/app/application_update_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application_dependencies import ApplicationLogging, ApplicationPaths
from app.backup.restore_journal import require_no_pending_restore
from app.edition_composition import UpdaterComposition
from app.internal_protocols import ApplicationRuntimeCoordinatorViewProtocol
from app.types_services import ApplicationServices
from app.updater.software_update.admission import (
    UPDATE_IN_PROGRESS_MESSAGE,
    UPDATE_PLATFORM_UNAVAILABLE_MESSAGE,
    UPDATE_RESTORE_PENDING_MESSAGE,
    UPDATE_UNAVAILABLE_MESSAGE,
    is_update_platform_supported,
    resolve_update_rejection_message,
)
from app.updater.software_update.handoff import (
    UPDATE_HANDOFF_EXCEPTIONS,
    abort_unaccepted_updater,
    accept_prepared_updater,
    wait_for_prepared_updater,
)
from app.updater.software_update.notice_store import SoftwareUpdateNoticeStore
from app.updater.software_update.preparation_progress import (
    write_preparation_progress,
)
from app.updater.software_update.preparation_status import UpdatePreparationStatus
from app.updater.software_update.updater_launch import (
    build_updater_command,
    spawn_detached_updater,
)
from core.concurrency.cancellation_cleanup import (
    cancellation_cleanup,
    current_task_has_pending_cancellation,
)
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ConflictError, StateError
from core.files.path_policy import safe_join_relative_under_base_lexical
from core.filesystem.async_queries import async_path_exists
from core.runtime.protocols import RuntimeStateStoreProtocol
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.software_update_result import (
    create_software_update_task,
    create_software_update_task_id,
)
from core.tasks.status_transitions import update_status

if TYPE_CHECKING:
    from core.app.protocols import ApplicationUpdateOutcome
    from core.types.json import JSONDict

__all__ = ("ApplicationUpdateService", "ApplicationUpdateServiceDependencies")

OPERATION = "application_update_service.update"
UPDATE_LAUNCH_FAILED_MESSAGE = "Failed to launch the software updater."


@dataclass(frozen=True, slots=True)
class ApplicationUpdateServiceDependencies:
    logging: ApplicationLogging
    paths: ApplicationPaths
    runtime: RuntimeStateStoreProtocol
    services: ApplicationServices
    runtime_coordinator: ApplicationRuntimeCoordinatorViewProtocol
    updater: UpdaterComposition

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ApplicationUpdateServiceDependencies",
            logging=self.logging,
            paths=self.paths,
            runtime=self.runtime,
            runtime_coordinator=self.runtime_coordinator,
            services=self.services,
            updater=self.updater,
        )


class ApplicationUpdateService:
    def __init__(self, deps: ApplicationUpdateServiceDependencies) -> None:
        self._deps = deps
        self._update_lock = asyncio.Lock()
        self._preparation_status = UpdatePreparationStatus(deps.paths.base_dir, deps.logging.logger)
        self._notice_store = SoftwareUpdateNoticeStore(deps.paths.base_dir, deps.logging.logger)

    async def get_preparation_status(self) -> JSONDict:
        return await self._preparation_status.get_status()

    async def get_update_notice(self, user_id: int) -> JSONDict | None:
        return await self._notice_store.get_pending_notice(user_id)

    async def acknowledge_update_notice(self, *, user_id: int, task_id: str) -> bool:
        return await self._notice_store.acknowledge(user_id=user_id, task_id=task_id)

    async def update(self) -> tuple[ApplicationUpdateOutcome, str]:
        self._deps.logging.logger.info("API request to initiate self-update received.")
        if self._deps.services.infrastructure.metrics_manager is not None:
            self._deps.services.infrastructure.metrics_manager.increment_counter(
                "global",
                "updates_triggered",
            )
        async with self._update_lock:
            prior_task_id = self._preparation_status.active_task_id
            accepted = False
            try:
                outcome, message = await self._launch_updater()
                accepted = outcome == "accepted"
                return (outcome, message)
            finally:
                if not accepted and self._preparation_status.active_task_id != prior_task_id:
                    self._preparation_status.finish()

    async def _launch_updater(self) -> tuple[ApplicationUpdateOutcome, str]:
        runtime_flags = self._deps.services.configuration.runtime_flags
        if not is_update_platform_supported(self._deps.updater.edition):
            self._deps.logging.logger.warning(UPDATE_PLATFORM_UNAVAILABLE_MESSAGE)
            return ("unavailable", UPDATE_PLATFORM_UNAVAILABLE_MESSAGE)
        rejection_message = resolve_update_rejection_message(self._deps.runtime, runtime_flags)
        if rejection_message is not None:
            self._deps.logging.logger.warning(rejection_message)
            outcome: ApplicationUpdateOutcome = (
                "conflict" if rejection_message == UPDATE_IN_PROGRESS_MESSAGE else "unavailable"
            )
            return (outcome, rejection_message)
        updater_path = safe_join_relative_under_base_lexical(
            base_path=self._deps.paths.base_dir,
            relative_path=self._deps.updater.cli_relative_path,
            description="Updater entrypoint",
        )
        task_id: str | None = None
        process_handle = None
        handoff_accepted = False
        try:
            try:
                await asyncio.to_thread(require_no_pending_restore, self._deps.paths.base_dir)
            except ConflictError:
                return ("conflict", UPDATE_RESTORE_PENDING_MESSAGE)
            if not await async_path_exists(updater_path):
                self._deps.logging.logger.error(
                    "Updater entrypoint is missing: %s",
                    updater_path,
                )
                return ("unavailable", UPDATE_UNAVAILABLE_MESSAGE)
            rejection_message = resolve_update_rejection_message(
                self._deps.runtime,
                runtime_flags,
            )
            if rejection_message is not None:
                self._deps.logging.logger.warning(rejection_message)
                outcome = (
                    "conflict" if rejection_message == UPDATE_IN_PROGRESS_MESSAGE else "unavailable"
                )
                return (outcome, rejection_message)
            pending_task_id = create_software_update_task_id()
            await cancellation_cleanup(
                create_software_update_task(
                    self._deps.services.tasks.task_registry,
                    task_id=pending_task_id,
                    metadata={"edition": self._deps.updater.edition, "phase": "preparing"},
                )
            )
            task_id = pending_task_id
            self._preparation_status.begin(task_id)
            await asyncio.to_thread(
                write_preparation_progress,
                self._deps.paths.base_dir,
                task_id,
                "preparing",
            )
            if current_task_has_pending_cancellation():
                raise asyncio.CancelledError()
            rejection_message = resolve_update_rejection_message(self._deps.runtime, runtime_flags)
            if rejection_message is not None:
                terminal_task = await finalize(
                    self._deps.services.tasks.task_registry,
                    task_id,
                    TaskStatus.CANCELLED,
                    status_message=rejection_message,
                )
                if terminal_task is None or terminal_task.status != TaskStatus.CANCELLED:
                    raise StateError("Superseded update could not finalize its durable task.")
                outcome = (
                    "conflict" if rejection_message == UPDATE_IN_PROGRESS_MESSAGE else "unavailable"
                )
                return (outcome, rejection_message)
            command = build_updater_command(
                cli_module=self._deps.updater.cli_module,
                config_path=self._deps.paths.config_path,
                task_id=task_id,
                wait_for_pid=os.getpid(),
            )
            banner_system = self._deps.runtime_coordinator.ensure_banner_system()
            banner_system.emit("update")
            self._deps.logging.logger.info(
                "Launching detached updater process: %s",
                " ".join(command),
            )
            process_handle = spawn_detached_updater(
                base_dir=self._deps.paths.base_dir,
                config=self._deps.services.configuration.config,
                command=command,
            )
            prepared = await wait_for_prepared_updater(
                base_path=self._deps.paths.base_dir,
                task_id=task_id,
                edition=self._deps.updater.edition,
                process_handle=process_handle,
            )
            if not prepared:
                await cancellation_cleanup(
                    asyncio.to_thread(
                        abort_unaccepted_updater,
                        process_handle,
                        self._deps.paths.base_dir,
                        task_id,
                        self._deps.logging.logger,
                    )
                )
                terminal_task = await finalize(
                    self._deps.services.tasks.task_registry,
                    task_id,
                    TaskStatus.CANCELLED,
                    status_message="The installation is already up-to-date.",
                )
                if terminal_task is None or terminal_task.status != TaskStatus.CANCELLED:
                    raise StateError("No-update operation could not finalize its durable task.")
                return ("unavailable", "The installation is already up-to-date.")
            rejection_message = resolve_update_rejection_message(self._deps.runtime, runtime_flags)
            if rejection_message is not None:
                raise StateError(rejection_message)
            working_task = await update_status(
                self._deps.services.tasks.task_registry,
                task_id,
                TaskStatus.WORKING,
                status_message="Updater preparation acknowledged.",
            )
            if working_task is None or working_task.status != TaskStatus.WORKING:
                raise StateError("Updater preparation could not persist its durable task.")
            rejection_message = resolve_update_rejection_message(self._deps.runtime, runtime_flags)
            if rejection_message is not None or process_handle.poll() is not None:
                raise StateError("Updater handoff was superseded before acknowledgement.")
            accept_prepared_updater(self._deps.paths.base_dir, task_id)
            handoff_accepted = True
            self._deps.services.tasks.task_registry.transfer_task_ownership(task_id)
            self._deps.runtime.transfer_process_ownership(process_handle)
            message = (
                "Updater process launched. The application will now shut down to allow "
                "the update to proceed."
            )
            self._deps.logging.logger.info(message)
            self._deps.runtime.set_system_stop()
            return ("accepted", message)
        except UPDATE_HANDOFF_EXCEPTIONS as exception:
            failure = exception
            if process_handle is not None and not handoff_accepted:
                try:
                    await cancellation_cleanup(
                        asyncio.to_thread(
                            abort_unaccepted_updater,
                            process_handle,
                            self._deps.paths.base_dir,
                            task_id,
                            self._deps.logging.logger,
                        )
                    )
                except UPDATE_HANDOFF_EXCEPTIONS as cleanup_exception:
                    failure = cleanup_exception
            if task_id is not None and not handoff_accepted:
                terminal_status = (
                    TaskStatus.CANCELLED
                    if isinstance(failure, asyncio.CancelledError)
                    else TaskStatus.FAILED
                )
                terminal_task = await cancellation_cleanup(
                    finalize(
                        self._deps.services.tasks.task_registry,
                        task_id,
                        terminal_status,
                        error_code=500 if terminal_status == TaskStatus.FAILED else None,
                        error_message=(
                            UPDATE_LAUNCH_FAILED_MESSAGE
                            if terminal_status == TaskStatus.FAILED
                            else None
                        ),
                    )
                )
                if terminal_task is None or terminal_task.status != terminal_status:
                    raise StateError(
                        "Updater launch failure could not finalize its durable task."
                    ) from failure
            if isinstance(failure, asyncio.CancelledError):
                raise
            log_exception(
                self._deps.logging.logger,
                failure,
                message="Failed to launch updater process",
                operation=OPERATION,
            )
            return ("failed", UPDATE_LAUNCH_FAILED_MESSAGE)

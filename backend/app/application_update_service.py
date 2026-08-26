"""SoAI - Application update service [backend/app/application_update_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import platform
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application_dependencies import ApplicationLogging, ApplicationPaths
from app.cli.windows_console_service import (
    WindowsConsoleService,
    WindowsConsoleServiceDependencies,
)
from app.edition_composition import UpdaterComposition
from app.internal_protocols import ApplicationRuntimeCoordinatorViewProtocol
from app.types_services import ApplicationServices
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.path_policy import safe_join_relative_under_base_lexical
from core.filesystem.async_queries import async_path_exists
from core.runtime.protocols import RuntimeFlagsViewProtocol, RuntimeStateStoreProtocol
from core.system.process_launcher import (
    DEVNULL_STREAM,
    SUBPROCESS_RECOVERABLE_EXCEPTIONS,
    spawn_handoff_process,
)

if TYPE_CHECKING:
    from core.app.protocols import ApplicationUpdateOutcome

__all__ = ("ApplicationUpdateService", "ApplicationUpdateServiceDependencies")

OPERATION = "application_update_service.update"
SELF_UPDATE_DISABLED_MESSAGE = "Self-update is disabled because host system actions are disabled."
UPDATE_IN_PROGRESS_MESSAGE = "Application shutdown or software update is already in progress."
UPDATE_LAUNCH_FAILED_MESSAGE = "Failed to launch the software updater."
UPDATE_OFFLINE_MESSAGE = (
    "SYSTEM.RUNTIME.STAY_OFFLINE is enabled. Software updates are disabled in offline mode."
)
UPDATE_UNAVAILABLE_MESSAGE = "The software updater is unavailable."
UPDATE_LAUNCH_EXCEPTIONS: tuple[type[Exception], ...] = (
    RECOVERABLE_EXCEPTIONS + SUBPROCESS_RECOVERABLE_EXCEPTIONS
)


def _resolve_update_rejection_message(
    runtime: RuntimeStateStoreProtocol,
    runtime_flags: RuntimeFlagsViewProtocol | None,
) -> str | None:
    if runtime.is_shutting_down or runtime.restart_requested or runtime.system_stop_event.is_set():
        return UPDATE_IN_PROGRESS_MESSAGE
    if runtime_flags is not None and runtime_flags.offline_mode:
        return UPDATE_OFFLINE_MESSAGE
    if runtime_flags is not None and runtime_flags.host_system_actions_disabled:
        return SELF_UPDATE_DISABLED_MESSAGE
    return None


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

    async def update(self) -> tuple[ApplicationUpdateOutcome, str]:
        self._deps.logging.logger.info("API request to initiate self-update received.")
        if self._deps.services.infrastructure.metrics_manager is not None:
            self._deps.services.infrastructure.metrics_manager.increment_counter(
                "global",
                "updates_triggered",
            )
        async with self._update_lock:
            return await self._launch_updater()

    async def _launch_updater(self) -> tuple[ApplicationUpdateOutcome, str]:
        runtime_flags = self._deps.services.configuration.runtime_flags
        rejection_message = _resolve_update_rejection_message(self._deps.runtime, runtime_flags)
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
        try:
            if not await async_path_exists(updater_path):
                self._deps.logging.logger.error(
                    "Updater entrypoint is missing: %s",
                    updater_path,
                )
                return ("unavailable", UPDATE_UNAVAILABLE_MESSAGE)
            rejection_message = _resolve_update_rejection_message(
                self._deps.runtime,
                runtime_flags,
            )
            if rejection_message is not None:
                self._deps.logging.logger.warning(rejection_message)
                outcome = (
                    "conflict" if rejection_message == UPDATE_IN_PROGRESS_MESSAGE else "unavailable"
                )
                return (outcome, rejection_message)
            command = [
                sys.executable,
                "-m",
                self._deps.updater.cli_module,
                "--update-software",
                "--silent",
                "--wait-for-pid",
                str(os.getpid()),
            ]
            banner_system = self._deps.runtime_coordinator.ensure_banner_system()
            banner_system.emit("update")
            self._deps.logging.logger.info(
                "Launching detached updater process: %s",
                " ".join(command),
            )
            creationflags = 0
            start_new_session = False
            if platform.system() == "Windows":
                creationflags = WindowsConsoleService(
                    WindowsConsoleServiceDependencies(logger=self._deps.logging.logger),
                ).get_subprocess_flags()
            else:
                start_new_session = True
            env = os.environ.copy()
            backend_root = os.path.join(self._deps.paths.base_dir, "backend")
            existing_pythonpath = env.get("PYTHONPATH")
            if existing_pythonpath:
                env["PYTHONPATH"] = os.pathsep.join([backend_root, existing_pythonpath])
            else:
                env["PYTHONPATH"] = backend_root
            process_handle = spawn_handoff_process(
                command,
                cwd=backend_root,
                env=env,
                creationflags=creationflags,
                start_new_session=start_new_session,
                stdin=DEVNULL_STREAM,
                stdout=DEVNULL_STREAM,
                stderr=DEVNULL_STREAM,
            )
            self._deps.runtime.transfer_process_ownership(process_handle)
            message = (
                "Updater process launched. The application will now shut down to allow "
                "the update to proceed."
            )
            self._deps.logging.logger.info(message)
            self._deps.runtime.set_system_stop()
            return ("accepted", message)
        except UPDATE_LAUNCH_EXCEPTIONS as exception:
            log_exception(
                self._deps.logging.logger,
                exception,
                message="Failed to launch updater process",
                operation=OPERATION,
            )
            return ("failed", UPDATE_LAUNCH_FAILED_MESSAGE)

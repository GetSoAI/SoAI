"""SoAI - Hardware subsystem terminal and command execution assembly [backend/app/composition/hardware_terminal_composition.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.lifecycle.coordinator import LifecycleCoordinator
from core.logging.protocols import TraceLogger
from core.logging.trace import get_logger
from core.system.command_executor import CommandExecutor, CommandExecutorDependencies
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from core.terminal.protocols import TerminalServiceProtocol
from terminal.dependencies import (
    PTYSessionManagerDependencies,
    TerminalServiceDependencies,
)
from terminal.pty_session_manager import PTYSessionManager
from terminal.service import Terminal

if TYPE_CHECKING:
    from core.runtime.flags_service import RuntimeFlagsService

__all__ = (
    "build_command_executor",
    "build_terminal_service",
)

LOGGER_NAME = "SoAI.app.composition.hardware_terminal_composition"


def build_command_executor() -> CommandExecutor:
    return CommandExecutor(CommandExecutorDependencies(executor_logger=get_logger(LOGGER_NAME)))


def build_terminal_service(
    *,
    terminal_enabled: bool,
    base_dir: str,
    hardware_logger: TraceLogger,
    command_executor: CommandExecutor,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    runtime_flags: RuntimeFlagsService,
    lifecycle_coordinator: LifecycleCoordinator,
) -> TerminalServiceProtocol:
    pty_session_manager = PTYSessionManager(
        PTYSessionManagerDependencies(
            base_dir=base_dir,
            logger=hardware_logger,
            cancellation_binder=cancellation_binder,
            finalizer_tracker=finalizer_tracker,
        ),
    )
    terminal_service = Terminal(
        TerminalServiceDependencies(
            terminal_enabled=terminal_enabled,
            base_dir=base_dir,
            logger=hardware_logger,
            command_executor=command_executor,
            runtime_flags=runtime_flags,
            pty_session_manager=pty_session_manager,
        ),
    )
    lifecycle_coordinator.register_actor(terminal_service)
    return terminal_service

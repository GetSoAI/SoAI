"""SoAI - Terminal subsystem dependency bundles [backend/terminal/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.logging.trace import TraceLogger
from core.runtime.protocols import RuntimeFlagsViewProtocol
from core.system.protocols import CommandExecutorProtocol
from terminal.internal_protocols import PTYSessionManagerProtocol

if TYPE_CHECKING:
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
    )

__all__ = (
    "PTYIOHandlerDependencies",
    "PTYSessionManagerDependencies",
    "PTYSpawnerDependencies",
    "TerminalServiceDependencies",
)


@dataclass(frozen=True, slots=True)
class PTYSpawnerDependencies:
    base_dir: str
    logger: TraceLogger

    def __post_init__(self) -> None:
        require_dependencies(
            owner="PTYSpawnerDependencies",
            base_dir=self.base_dir,
            logger=self.logger,
        )


@dataclass(frozen=True, slots=True)
class PTYIOHandlerDependencies:
    logger: TraceLogger

    def __post_init__(self) -> None:
        require_dependencies(
            owner="PTYIOHandlerDependencies",
            logger=self.logger,
        )


@dataclass(frozen=True, slots=True)
class PTYSessionManagerDependencies:
    base_dir: str
    logger: TraceLogger
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="PTYSessionManagerDependencies",
            base_dir=self.base_dir,
            cancellation_binder=self.cancellation_binder,
            finalizer_tracker=self.finalizer_tracker,
            logger=self.logger,
        )


@dataclass(frozen=True, slots=True)
class TerminalServiceDependencies:
    terminal_enabled: bool
    base_dir: str
    logger: TraceLogger
    command_executor: CommandExecutorProtocol
    runtime_flags: RuntimeFlagsViewProtocol
    pty_session_manager: PTYSessionManagerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="TerminalServiceDependencies",
            base_dir=self.base_dir,
            command_executor=self.command_executor,
            logger=self.logger,
            pty_session_manager=self.pty_session_manager,
            runtime_flags=self.runtime_flags,
            terminal_enabled=self.terminal_enabled,
        )

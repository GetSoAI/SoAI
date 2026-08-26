"""SoAI - Runtime mutation actor dependency models [backend/orchestrator/lifecycle/runtime_mutation_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.events.types_plugins import (
    ClearQuarantineCommand,
    RequestPluginDisableCommand,
    RequestPluginEnableCommand,
    RequestPluginStopAndWaitCommand,
)
from core.events.types_system import ConfigReloadedEvent
from core.orchestrator.scheduler_work import SchedulerWorkItem
from core.orchestrator.stop_outcome import PluginStopOutcome
from orchestrator.lifecycle.config_reload_result import PluginConfigReloadResult
from orchestrator.lifecycle.runtime_mutation_commands import RuntimeMutationStopRequest
from orchestrator.types import OrchestratorDependencies

__all__ = ("OrchestratorLifecycleRuntimeMutationsDependencies",)


@dataclass(frozen=True, slots=True)
class OrchestratorLifecycleRuntimeMutationsDependencies:
    orchestrator: OrchestratorDependencies
    config_reload_handler: Callable[[ConfigReloadedEvent], Awaitable[PluginConfigReloadResult]]
    config_reload_failure_publisher: Callable[[ConfigReloadedEvent, str], Awaitable[None]]
    stop_handler: Callable[[RuntimeMutationStopRequest], Awaitable[PluginStopOutcome]]
    stop_command_handler: Callable[[RequestPluginStopAndWaitCommand], Awaitable[None]]
    disable_handler: Callable[[RequestPluginDisableCommand], Awaitable[None]]
    enable_handler: Callable[[RequestPluginEnableCommand], Awaitable[list[SchedulerWorkItem]]]
    clear_quarantine_handler: Callable[[ClearQuarantineCommand], Awaitable[list[SchedulerWorkItem]]]
    recovery_handler: Callable[[str, str], Awaitable[None]]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="OrchestratorLifecycleRuntimeMutationsDependencies",
            clear_quarantine_handler=self.clear_quarantine_handler,
            config_reload_failure_publisher=self.config_reload_failure_publisher,
            config_reload_handler=self.config_reload_handler,
            disable_handler=self.disable_handler,
            enable_handler=self.enable_handler,
            orchestrator=self.orchestrator,
            recovery_handler=self.recovery_handler,
            stop_command_handler=self.stop_command_handler,
            stop_handler=self.stop_handler,
        )

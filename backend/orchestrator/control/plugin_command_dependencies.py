"""SoAI - Orchestrator plugin command dependency bundle [backend/orchestrator/control/plugin_command_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import override

from core.di.validation import require_dependencies
from core.tasks.protocols import (
    SpawnTrackedBackgroundTaskCallable,
    TaskRegistryProtocol,
)
from orchestrator.control.queue_scheduler_dependencies import (
    ControlQueueSchedulerDependencies,
)
from orchestrator.internal_protocols import GuardianRefProtocol
from orchestrator.lifecycle.service_interfaces.internal_protocols import (
    OrchestratorLifecycleCoordinatorProtocol,
)

__all__ = ("OrchestratorPluginCommandDependencies",)


@dataclass(frozen=True, slots=True)
class OrchestratorPluginCommandDependencies(ControlQueueSchedulerDependencies):
    lifecycle: OrchestratorLifecycleCoordinatorProtocol
    task_registry: TaskRegistryProtocol
    guardian_ref: GuardianRefProtocol
    spawn_background_task: SpawnTrackedBackgroundTaskCallable
    shutdown_stop_all_plugins_timeout_sec: float

    @override
    def __post_init__(self) -> None:
        ControlQueueSchedulerDependencies.__post_init__(self)
        require_dependencies(
            owner="OrchestratorPluginCommandDependencies",
            guardian_ref=self.guardian_ref,
            lifecycle=self.lifecycle,
            shutdown_stop_all_plugins_timeout_sec=self.shutdown_stop_all_plugins_timeout_sec,
            spawn_background_task=self.spawn_background_task,
            task_registry=self.task_registry,
        )

"""SoAI - User commands for plugin lifecycle management [backend/orchestrator/lifecycle/user_commands/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError
from core.events.types_plugins import (
    ClearQuarantineCommand,
    RequestPluginDisableCommand,
    RequestPluginEnableCommand,
    RequestPluginStopAndWaitCommand,
)
from core.orchestrator.scheduler_work import SchedulerWorkItem
from orchestrator.lifecycle.service_interfaces.internal_protocols import (
    OrchestratorLifecycleRuntimeMutationsProtocol,
)
from orchestrator.lifecycle.state_access.internal_protocols import (
    PluginWorkPurgeProtocol,
)
from orchestrator.lifecycle.user_commands.clear_quarantine import (
    handle_clear_quarantine,
)
from orchestrator.lifecycle.user_commands.dependencies import (
    OrchestratorLifecycleUserCommandsDependencies,
)
from orchestrator.lifecycle.user_commands.plugin_enable import (
    handle_plugin_enable_command,
)
from orchestrator.lifecycle.user_commands.plugin_stop_disable import (
    handle_plugin_disable_command,
    handle_plugin_stop_command,
)

__all__ = ("OrchestratorLifecycleUserCommands",)


class OrchestratorLifecycleUserCommands:
    def __init__(self, deps: OrchestratorLifecycleUserCommandsDependencies) -> None:
        self._deps = deps
        self._runtime_mutations: OrchestratorLifecycleRuntimeMutationsProtocol | None = None
        self._purge_plugin_requests: PluginWorkPurgeProtocol | None = None

    def bind_runtime_mutations(
        self,
        runtime_mutations: OrchestratorLifecycleRuntimeMutationsProtocol,
    ) -> None:
        self._runtime_mutations = runtime_mutations

    def bind_plugin_work_purge(
        self,
        purge_plugin_requests: PluginWorkPurgeProtocol,
    ) -> None:
        self._purge_plugin_requests = purge_plugin_requests

    async def handle_clear_quarantine(
        self,
        event: ClearQuarantineCommand,
    ) -> list[SchedulerWorkItem]:
        runtime_mutations = self._runtime_mutations
        if runtime_mutations is None:
            raise StateError(
                "Runtime mutations must be bound before use.",
                operation="orchestrator.lifecycle.user_commands.handle_clear_quarantine",
            )
        return await runtime_mutations.submit_clear_quarantine_command(event)

    async def handle_plugin_stop_command(self, command: RequestPluginStopAndWaitCommand) -> None:
        runtime_mutations = self._runtime_mutations
        if runtime_mutations is None:
            raise StateError(
                "Runtime mutations must be bound before use.",
                operation="orchestrator.lifecycle.user_commands.handle_plugin_stop_command",
            )
        await runtime_mutations.submit_stop_command(command)

    async def handle_plugin_disable_command(self, command: RequestPluginDisableCommand) -> None:
        runtime_mutations = self._runtime_mutations
        if runtime_mutations is None:
            raise StateError(
                "Runtime mutations must be bound before use.",
                operation="orchestrator.lifecycle.user_commands.handle_plugin_disable_command",
            )
        await runtime_mutations.submit_disable_command(command)

    async def handle_plugin_enable_command(
        self,
        command: RequestPluginEnableCommand,
    ) -> list[SchedulerWorkItem]:
        runtime_mutations = self._runtime_mutations
        if runtime_mutations is None:
            raise StateError(
                "Runtime mutations must be bound before use.",
                operation="orchestrator.lifecycle.user_commands.handle_plugin_enable_command",
            )
        return await runtime_mutations.submit_enable_command(command)

    async def execute_clear_quarantine(
        self,
        event: ClearQuarantineCommand,
    ) -> list[SchedulerWorkItem]:
        return await handle_clear_quarantine(self._deps, event=event)

    async def execute_plugin_stop_command(self, command: RequestPluginStopAndWaitCommand) -> None:
        purge_plugin_requests = self._require_purge_plugin_requests(
            "orchestrator.lifecycle.user_commands.execute_plugin_stop_command",
        )
        await handle_plugin_stop_command(
            self._deps,
            command=command,
            purge_plugin_requests=purge_plugin_requests,
        )

    async def execute_plugin_disable_command(self, command: RequestPluginDisableCommand) -> None:
        purge_plugin_requests = self._require_purge_plugin_requests(
            "orchestrator.lifecycle.user_commands.execute_plugin_disable_command",
        )
        await handle_plugin_disable_command(
            self._deps,
            command=command,
            purge_plugin_requests=purge_plugin_requests,
        )

    async def execute_plugin_enable_command(
        self,
        command: RequestPluginEnableCommand,
    ) -> list[SchedulerWorkItem]:
        return await handle_plugin_enable_command(self._deps, command=command)

    def _require_purge_plugin_requests(
        self,
        operation: str,
    ) -> PluginWorkPurgeProtocol:
        purge_plugin_requests = self._purge_plugin_requests
        if purge_plugin_requests is None:
            raise StateError(
                "Plugin work purge callback must be bound before use.",
                operation=operation,
            )
        return purge_plugin_requests

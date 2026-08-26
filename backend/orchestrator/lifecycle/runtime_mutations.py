"""SoAI - Per-plugin runtime mutation actor [backend/orchestrator/lifecycle/runtime_mutations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.context import create_system_cancellation_id
from core.errors.exceptions import StateError
from core.events.types_plugins import (
    ClearQuarantineCommand,
    RequestPluginDisableCommand,
    RequestPluginEnableCommand,
    RequestPluginStopAndWaitCommand,
)
from core.events.types_system import ConfigReloadedEvent
from core.logging.trace import get_logger
from core.orchestrator.scheduler_work import SchedulerWorkItem
from core.orchestrator.stop_outcome import PluginStopOutcome
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from orchestrator.lifecycle.config_reload_result import (
    PluginConfigReloadResult,
)
from orchestrator.lifecycle.runtime_mutation_commands import RuntimeMutationStopRequest
from orchestrator.lifecycle.runtime_mutation_dependencies import (
    OrchestratorLifecycleRuntimeMutationsDependencies,
)
from orchestrator.lifecycle.runtime_mutation_shutdown import shutdown_runtime_mutations
from orchestrator.lifecycle.runtime_mutation_state import (
    STOP_PRIORITY_COMMAND_NAMES,
    ClearQuarantineRuntimeMutationCommand,
    ConfigReloadRuntimeMutationCommand,
    DisableRuntimeMutationCommand,
    EnableRuntimeMutationCommand,
    PluginRuntimeMutationEntry,
    PluginStopCommandRuntimeMutation,
    QueuedRuntimeMutation,
    RecoveryRuntimeMutationCommand,
    StopRuntimeMutationCommand,
    drain_pending_reloads,
    insert_stop_priority_command,
    resolve_runtime_mutation_name,
)
from orchestrator.lifecycle.runtime_mutation_worker import (
    publish_dropped_reload_events,
    run_runtime_mutation_worker,
)
from orchestrator.lifecycle.runtime_mutations_config_reload import (
    submit_runtime_config_reload,
)

if TYPE_CHECKING:
    from orchestrator.lifecycle.runtime_mutation_types import (
        DroppedReloadRuntimeMutation,
        RuntimeMutationFuture,
        RuntimeMutationResult,
    )

__all__ = (
    "OrchestratorLifecycleRuntimeMutations",
    "OrchestratorLifecycleRuntimeMutationsDependencies",
)

LOGGER_NAME = "SoAI.orchestrator.lifecycle.runtime_mutations"


class OrchestratorLifecycleRuntimeMutations:
    def __init__(self, deps: OrchestratorLifecycleRuntimeMutationsDependencies) -> None:
        self._deps = deps
        self._entries: dict[str, PluginRuntimeMutationEntry] = {}
        self._entries_lock = asyncio.Lock()
        self._accepting_commands = True

    async def start(self) -> None:
        async with self._entries_lock:
            if self._entries:
                raise StateError(
                    "Runtime mutation actor cannot start with stale queued entries.",
                    operation="orchestrator.lifecycle.runtime_mutations.start",
                )
            self._accepting_commands = True

    async def submit_config_reload(self, event: ConfigReloadedEvent) -> PluginConfigReloadResult:
        return await submit_runtime_config_reload(
            deps=self._deps,
            entries=self._entries,
            entries_lock=self._entries_lock,
            accepting_commands=self._is_accepting_commands,
            event=event,
            start_worker_locked=self._start_worker_locked,
        )

    async def submit_stop_plugin(self, request: RuntimeMutationStopRequest) -> PluginStopOutcome:
        lifecycle = self._deps.orchestrator.plugin_manager.lifecycle
        if lifecycle.is_plugin_lock_owned_by_current_task(request.plugin_name):
            return await self._deps.stop_handler(request)
        result = await self._submit_command(
            request.plugin_name,
            StopRuntimeMutationCommand(request=request),
        )
        if isinstance(result, PluginStopOutcome):
            return result
        raise StateError(
            "Stop mutation returned an invalid result type.",
            operation="orchestrator.lifecycle.runtime_mutations.submit_stop_plugin",
            details={"plugin_name": request.plugin_name},
        )

    async def submit_stop_command(self, command: RequestPluginStopAndWaitCommand) -> None:
        await self._submit_command(
            command.plugin_name,
            PluginStopCommandRuntimeMutation(command=command),
        )

    async def submit_disable_command(self, command: RequestPluginDisableCommand) -> None:
        await self._submit_command(
            command.plugin_name,
            DisableRuntimeMutationCommand(command=command),
        )

    async def submit_enable_command(
        self,
        command: RequestPluginEnableCommand,
    ) -> list[SchedulerWorkItem]:
        result = await self._submit_command(
            command.plugin_name,
            EnableRuntimeMutationCommand(command=command),
        )
        if isinstance(result, list):
            return result
        raise StateError(
            "Enable mutation returned an invalid result type.",
            operation="orchestrator.lifecycle.runtime_mutations.submit_enable_command",
            details={"plugin_name": command.plugin_name},
        )

    async def submit_clear_quarantine_command(
        self,
        command: ClearQuarantineCommand,
    ) -> list[SchedulerWorkItem]:
        result = await self._submit_command(
            command.plugin_name,
            ClearQuarantineRuntimeMutationCommand(command=command),
        )
        if isinstance(result, list):
            return result
        raise StateError(
            "Clear quarantine mutation returned an invalid result type.",
            operation="orchestrator.lifecycle.runtime_mutations.submit_clear_quarantine_command",
            details={"plugin_name": command.plugin_name},
        )

    async def submit_recovery(self, plugin_name: str, reason: str) -> None:
        await self._submit_command(
            plugin_name,
            RecoveryRuntimeMutationCommand(plugin_name=plugin_name, reason=reason),
        )

    async def shutdown(self, timeout_seconds: float) -> None:
        async with self._entries_lock:
            self._accepting_commands = False
        await shutdown_runtime_mutations(
            deps=self._deps,
            entries=self._entries,
            entries_lock=self._entries_lock,
            timeout_seconds=timeout_seconds,
        )

    def _is_accepting_commands(self) -> bool:
        return self._accepting_commands

    async def discard_plugin(self, plugin_name: str) -> None:
        dropped_reloads: list[DroppedReloadRuntimeMutation] = []
        pending_to_fail: list[RuntimeMutationFuture] = []
        purge_reason = "Plugin was purged before the queued runtime mutation could execute."
        purge_error = StateError(
            purge_reason,
            operation="orchestrator.lifecycle.runtime_mutations.discard_plugin",
            details={"plugin_name": plugin_name},
        )
        async with self._entries_lock:
            entry = self._entries.get(plugin_name)
            if entry is None:
                return
            entry.discard_reason = purge_reason
            for queued_command in entry.pending:
                if isinstance(queued_command.command, ConfigReloadRuntimeMutationCommand):
                    dropped_reloads.append(
                        (
                            queued_command.command.event,
                            queued_command.future,
                            "discarded because the plugin was purged",
                        ),
                    )
                    continue
                pending_to_fail.append(queued_command.future)
            entry.pending.clear()
            worker_task = entry.worker_task
            if worker_task is None or worker_task.done():
                self._entries.pop(plugin_name, None)
        await publish_dropped_reload_events(
            dropped_reloads=dropped_reloads,
            deps=self._deps,
        )
        for future in pending_to_fail:
            if not future.done():
                future.set_exception(purge_error)

    async def _submit_command(
        self,
        plugin_name: str,
        command: (
            ConfigReloadRuntimeMutationCommand
            | StopRuntimeMutationCommand
            | PluginStopCommandRuntimeMutation
            | DisableRuntimeMutationCommand
            | EnableRuntimeMutationCommand
            | ClearQuarantineRuntimeMutationCommand
            | RecoveryRuntimeMutationCommand
        ),
    ) -> PluginStopOutcome | list[SchedulerWorkItem] | PluginConfigReloadResult | None:
        loop = asyncio.get_running_loop()
        future: RuntimeMutationFuture = loop.create_future()
        dropped_reloads: list[DroppedReloadRuntimeMutation] = []
        discard_reason: str | None = None
        async with self._entries_lock:
            if not self._accepting_commands:
                raise StateError(
                    "Runtime mutation rejected because orchestrator shutdown is in progress.",
                    operation="orchestrator.lifecycle.runtime_mutations.submit_command",
                    details={"plugin_name": plugin_name},
                )
            entry = self._entries.get(plugin_name)
            if entry is None:
                entry = PluginRuntimeMutationEntry()
                self._entries[plugin_name] = entry
            discard_reason = entry.discard_reason
            if discard_reason is None:
                command_name = resolve_runtime_mutation_name(command)
                if command_name in STOP_PRIORITY_COMMAND_NAMES:
                    dropped_reloads = drain_pending_reloads(
                        entry,
                        reason=f"discarded by queued {command_name} command",
                    )
                    insert_stop_priority_command(
                        entry,
                        QueuedRuntimeMutation(command=command, future=future),
                    )
                else:
                    entry.pending.append(QueuedRuntimeMutation(command=command, future=future))
                self._start_worker_locked(plugin_name, entry)
        if discard_reason is not None:
            raise StateError(
                discard_reason,
                operation="orchestrator.lifecycle.runtime_mutations.submit_command",
                details={"plugin_name": plugin_name},
            )
        await publish_dropped_reload_events(
            dropped_reloads=dropped_reloads,
            deps=self._deps,
        )
        result: RuntimeMutationResult = await future
        return result

    def _start_worker_locked(
        self,
        plugin_name: str,
        entry: PluginRuntimeMutationEntry,
    ) -> None:
        worker_task = entry.worker_task
        if worker_task is not None and (not worker_task.done()):
            return
        logger = get_logger(LOGGER_NAME)
        entry.worker_task = spawn_tracked_task(
            run_runtime_mutation_worker(
                plugin_name=plugin_name,
                deps=self._deps,
                entries=self._entries,
                entries_lock=self._entries_lock,
            ),
            name=f"orchestrator-runtime-mutation-{plugin_name}",
            logger=logger,
            cancellation_binder=self._deps.orchestrator.task_cancellation_binder,
            cancellation_id=create_system_cancellation_id(
                f"orchestrator_runtime_mutation:{plugin_name}",
            ),
            owner="orchestrator_runtime_mutation",
            metadata={"plugin_name": plugin_name},
            finalizer_tracker=self._deps.orchestrator.task_finalizer_tracker,
        )

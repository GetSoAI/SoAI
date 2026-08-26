"""SoAI - Runtime mutation worker behavior [backend/orchestrator/lifecycle/runtime_mutation_worker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from orchestrator.lifecycle.config_reload_result import (
    PluginConfigReloadOutcome,
    PluginConfigReloadResult,
)
from orchestrator.lifecycle.runtime_mutation_dependencies import (
    OrchestratorLifecycleRuntimeMutationsDependencies,
)
from orchestrator.lifecycle.runtime_mutation_state import (
    ClearQuarantineRuntimeMutationCommand,
    ConfigReloadRuntimeMutationCommand,
    DisableRuntimeMutationCommand,
    EnableRuntimeMutationCommand,
    PluginRuntimeMutationEntry,
    PluginStopCommandRuntimeMutation,
    RecoveryRuntimeMutationCommand,
    StopRuntimeMutationCommand,
    resolve_runtime_mutation_name,
)

if TYPE_CHECKING:
    from orchestrator.lifecycle.runtime_mutation_types import (
        DroppedReloadRuntimeMutation,
        RuntimeMutationFuture,
        RuntimeMutationResult,
    )

__all__ = (
    "discard_pending_after_worker_cancellation",
    "execute_runtime_mutation_command",
    "publish_dropped_reload_events",
    "run_runtime_mutation_worker",
)

LOGGER_NAME = "SoAI.orchestrator.lifecycle.runtime_mutation_worker"
OPERATION = "orchestrator.lifecycle.runtime_mutations.run_worker"


async def run_runtime_mutation_worker(
    *,
    plugin_name: str,
    deps: OrchestratorLifecycleRuntimeMutationsDependencies,
    entries: dict[str, PluginRuntimeMutationEntry],
    entries_lock: asyncio.Lock,
) -> None:
    logger = get_logger(LOGGER_NAME)
    while True:
        async with entries_lock:
            entry = entries.get(plugin_name)
            if entry is None:
                return
            if not entry.pending:
                entry.worker_task = None
                entries.pop(plugin_name, None)
                return
            queued_command = entry.pending.popleft()
            entry.active_command_name = resolve_runtime_mutation_name(queued_command.command)
            entry.active_future = queued_command.future
        try:
            result = await execute_runtime_mutation_command(
                command=queued_command.command,
                deps=deps,
            )
            if not queued_command.future.done():
                queued_command.future.set_result(result)
        except asyncio.CancelledError as exception:
            if not queued_command.future.done():
                queued_command.future.set_exception(exception)
            await discard_pending_after_worker_cancellation(
                plugin_name=plugin_name,
                exception=exception,
                deps=deps,
                entries=entries,
                entries_lock=entries_lock,
            )
            raise
        except RECOVERABLE_EXCEPTIONS as exception:
            coerced_exception = coerce_to_soai_error(
                exception,
                operation="orchestrator.lifecycle.runtime_mutations.run_worker",
            )
            log_exception(
                logger,
                coerced_exception,
                message="Runtime mutation worker command failed.",
                operation=OPERATION,
                details={
                    "plugin_name": plugin_name,
                    "command_name": resolve_runtime_mutation_name(queued_command.command),
                },
            )
            if not queued_command.future.done():
                queued_command.future.set_exception(coerced_exception)
        finally:
            async with entries_lock:
                entry = entries.get(plugin_name)
                if entry is not None:
                    entry.active_command_name = None
                    entry.active_future = None


async def discard_pending_after_worker_cancellation(
    *,
    plugin_name: str,
    exception: asyncio.CancelledError,
    deps: OrchestratorLifecycleRuntimeMutationsDependencies,
    entries: dict[str, PluginRuntimeMutationEntry],
    entries_lock: asyncio.Lock,
) -> None:
    dropped_reloads: list[DroppedReloadRuntimeMutation] = []
    pending_to_fail: list[RuntimeMutationFuture] = []
    async with entries_lock:
        entry = entries.pop(plugin_name, None)
        if entry is None:
            return
        for queued_command in entry.pending:
            if isinstance(queued_command.command, ConfigReloadRuntimeMutationCommand):
                dropped_reloads.append(
                    (
                        queued_command.command.event,
                        queued_command.future,
                        "discarded because the runtime mutation worker was cancelled",
                    ),
                )
                continue
            pending_to_fail.append(queued_command.future)
    await publish_dropped_reload_events(
        dropped_reloads=dropped_reloads,
        deps=deps,
    )
    for future in pending_to_fail:
        if not future.done():
            future.set_exception(exception)


async def publish_dropped_reload_events(
    *,
    dropped_reloads: list[DroppedReloadRuntimeMutation],
    deps: OrchestratorLifecycleRuntimeMutationsDependencies,
) -> None:
    for event, future, reason in dropped_reloads:
        await deps.config_reload_failure_publisher(event, reason)
        if not future.done():
            future.set_result(
                PluginConfigReloadResult(
                    PluginConfigReloadOutcome.FAILED_TERMINAL,
                    error=reason,
                ),
            )


async def execute_runtime_mutation_command(
    *,
    command: (
        ConfigReloadRuntimeMutationCommand
        | StopRuntimeMutationCommand
        | PluginStopCommandRuntimeMutation
        | DisableRuntimeMutationCommand
        | EnableRuntimeMutationCommand
        | ClearQuarantineRuntimeMutationCommand
        | RecoveryRuntimeMutationCommand
    ),
    deps: OrchestratorLifecycleRuntimeMutationsDependencies,
) -> RuntimeMutationResult:
    if isinstance(command, ConfigReloadRuntimeMutationCommand):
        return await deps.config_reload_handler(command.event)
    if isinstance(command, StopRuntimeMutationCommand):
        return await deps.stop_handler(command.request)
    if isinstance(command, PluginStopCommandRuntimeMutation):
        await deps.stop_command_handler(command.command)
        return None
    if isinstance(command, DisableRuntimeMutationCommand):
        await deps.disable_handler(command.command)
        return None
    if isinstance(command, EnableRuntimeMutationCommand):
        return await deps.enable_handler(command.command)
    if isinstance(command, ClearQuarantineRuntimeMutationCommand):
        return await deps.clear_quarantine_handler(command.command)
    if isinstance(command, RecoveryRuntimeMutationCommand):
        await deps.recovery_handler(command.plugin_name, command.reason)
        return None
    raise StateError(
        "Unsupported runtime mutation command.",
        operation="orchestrator.lifecycle.runtime_mutations.execute_command",
    )

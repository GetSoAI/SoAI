"""SoAI - Orchestrator runtime mutation: config reload submission [backend/orchestrator/lifecycle/runtime_mutations_config_reload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.events.types_system import ConfigReloadedEvent
from orchestrator.lifecycle.config_reload_result import (
    PluginConfigReloadOutcome,
    PluginConfigReloadResult,
)
from orchestrator.lifecycle.runtime_mutation_state import (
    ConfigReloadRuntimeMutationCommand,
    PluginRuntimeMutationEntry,
    QueuedRuntimeMutation,
    build_reload_block_reason,
    entry_has_stop_priority,
    replace_pending_reload,
)
from orchestrator.lifecycle.runtime_mutation_worker import (
    publish_dropped_reload_events,
)

if TYPE_CHECKING:
    from orchestrator.lifecycle.runtime_mutation_dependencies import (
        OrchestratorLifecycleRuntimeMutationsDependencies,
    )
    from orchestrator.lifecycle.runtime_mutation_types import (
        DroppedReloadRuntimeMutation,
        RuntimeMutationFuture,
    )

__all__ = ("submit_runtime_config_reload",)


async def submit_runtime_config_reload(
    *,
    deps: OrchestratorLifecycleRuntimeMutationsDependencies,
    entries: dict[str, PluginRuntimeMutationEntry],
    entries_lock: asyncio.Lock,
    accepting_commands: Callable[[], bool],
    event: ConfigReloadedEvent,
    start_worker_locked: Callable[[str, PluginRuntimeMutationEntry], None],
) -> PluginConfigReloadResult:
    loop = asyncio.get_running_loop()
    entry: PluginRuntimeMutationEntry | None = None
    future: RuntimeMutationFuture | None = None
    dropped_reloads: list[DroppedReloadRuntimeMutation] = []
    discard_reason: str | None = None
    async with entries_lock:
        if not accepting_commands():
            discard_reason = "Runtime mutations are shutting down."
        else:
            entry = entries.get(event.config_name)
            if entry is None:
                entry = PluginRuntimeMutationEntry()
                entries[event.config_name] = entry
            discard_reason = _resolve_reload_discard_reason(entry)
        if discard_reason is None:
            if entry is None:
                raise StateError(
                    "Config reload mutation entry was not initialized.",
                    operation="orchestrator.lifecycle.runtime_mutations.submit_config_reload",
                    details={"plugin_name": event.config_name},
                )
            future = loop.create_future()
            replaced_reload = replace_pending_reload(
                entry,
                QueuedRuntimeMutation(
                    command=ConfigReloadRuntimeMutationCommand(event=event),
                    future=future,
                ),
            )
            if replaced_reload is not None:
                if not isinstance(
                    replaced_reload.command,
                    ConfigReloadRuntimeMutationCommand,
                ):
                    raise StateError(
                        "Replaced runtime mutation must be a config reload command.",
                        operation="orchestrator.lifecycle.runtime_mutations.submit_config_reload",
                        details={"plugin_name": event.config_name},
                    )
                dropped_reloads.append(
                    (
                        replaced_reload.command.event,
                        replaced_reload.future,
                        f"superseded by newer config reload revision {event.revision}",
                    ),
                )
            else:
                entry.pending.append(
                    QueuedRuntimeMutation(
                        command=ConfigReloadRuntimeMutationCommand(event=event),
                        future=future,
                    ),
                )
            start_worker_locked(event.config_name, entry)
    await publish_dropped_reload_events(
        dropped_reloads=dropped_reloads,
        deps=deps,
    )
    if discard_reason is not None:
        await deps.config_reload_failure_publisher(event, discard_reason)
        return PluginConfigReloadResult(
            outcome=PluginConfigReloadOutcome.FAILED_TERMINAL,
            error=discard_reason,
        )
    if future is None:
        raise StateError(
            "Config reload mutation is missing a future.",
            operation="orchestrator.lifecycle.runtime_mutations.submit_config_reload",
            details={"plugin_name": event.config_name, "revision": event.revision},
        )
    result = await future
    if isinstance(result, PluginConfigReloadResult):
        return result
    raise StateError(
        "Config reload mutation returned an invalid result type.",
        operation="orchestrator.lifecycle.runtime_mutations.submit_config_reload",
        details={"plugin_name": event.config_name, "revision": event.revision},
    )


def _resolve_reload_discard_reason(entry: PluginRuntimeMutationEntry) -> str | None:
    if entry.discard_reason is not None:
        return entry.discard_reason
    if entry_has_stop_priority(entry):
        return build_reload_block_reason(entry)
    return None

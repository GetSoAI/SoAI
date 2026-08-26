"""SoAI - Runtime mutation queue state and policy [backend/orchestrator/lifecycle/runtime_mutation_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.events.types_plugins import (
    ClearQuarantineCommand,
    RequestPluginDisableCommand,
    RequestPluginEnableCommand,
    RequestPluginStopAndWaitCommand,
)
from core.events.types_system import ConfigReloadedEvent
from orchestrator.lifecycle.runtime_mutation_commands import RuntimeMutationStopRequest

if TYPE_CHECKING:
    from orchestrator.lifecycle.runtime_mutation_types import (
        DroppedReloadRuntimeMutation,
        RuntimeMutationFuture,
    )

__all__ = (
    "DISABLE_COMMAND_NAME",
    "STOP_PRIORITY_COMMAND_NAMES",
    "ClearQuarantineRuntimeMutationCommand",
    "ConfigReloadRuntimeMutationCommand",
    "DisableRuntimeMutationCommand",
    "EnableRuntimeMutationCommand",
    "PluginRuntimeMutationEntry",
    "PluginStopCommandRuntimeMutation",
    "QueuedRuntimeMutation",
    "RecoveryRuntimeMutationCommand",
    "StopRuntimeMutationCommand",
    "build_reload_block_reason",
    "drain_pending_reloads",
    "entry_has_stop_priority",
    "insert_stop_priority_command",
    "replace_pending_reload",
    "resolve_runtime_mutation_name",
)

STOP_COMMAND_NAME = "stop"
DISABLE_COMMAND_NAME = "disable"
ENABLE_COMMAND_NAME = "enable"
CLEAR_QUARANTINE_COMMAND_NAME = "clear_quarantine"
RECOVERY_COMMAND_NAME = "recovery"
CONFIG_RELOAD_COMMAND_NAME = "config_reload"
STOP_PRIORITY_COMMAND_NAMES = frozenset(
    {STOP_COMMAND_NAME, DISABLE_COMMAND_NAME, RECOVERY_COMMAND_NAME},
)


@dataclass(frozen=True, slots=True)
class ConfigReloadRuntimeMutationCommand:
    event: ConfigReloadedEvent


@dataclass(frozen=True, slots=True)
class StopRuntimeMutationCommand:
    request: RuntimeMutationStopRequest


@dataclass(frozen=True, slots=True)
class PluginStopCommandRuntimeMutation:
    command: RequestPluginStopAndWaitCommand


@dataclass(frozen=True, slots=True)
class DisableRuntimeMutationCommand:
    command: RequestPluginDisableCommand


@dataclass(frozen=True, slots=True)
class EnableRuntimeMutationCommand:
    command: RequestPluginEnableCommand


@dataclass(frozen=True, slots=True)
class ClearQuarantineRuntimeMutationCommand:
    command: ClearQuarantineCommand


@dataclass(frozen=True, slots=True)
class RecoveryRuntimeMutationCommand:
    plugin_name: str
    reason: str


@dataclass(slots=True)
class QueuedRuntimeMutation:
    command: (
        ConfigReloadRuntimeMutationCommand
        | StopRuntimeMutationCommand
        | PluginStopCommandRuntimeMutation
        | DisableRuntimeMutationCommand
        | EnableRuntimeMutationCommand
        | ClearQuarantineRuntimeMutationCommand
        | RecoveryRuntimeMutationCommand
    )
    future: RuntimeMutationFuture


@dataclass(slots=True)
class PluginRuntimeMutationEntry:
    pending: deque[QueuedRuntimeMutation] = field(default_factory=deque[QueuedRuntimeMutation])
    worker_task: asyncio.Task[None] | None = None
    active_command_name: str | None = None
    active_future: RuntimeMutationFuture | None = None
    discard_reason: str | None = None


def resolve_runtime_mutation_name(
    command: (
        ConfigReloadRuntimeMutationCommand
        | StopRuntimeMutationCommand
        | PluginStopCommandRuntimeMutation
        | DisableRuntimeMutationCommand
        | EnableRuntimeMutationCommand
        | ClearQuarantineRuntimeMutationCommand
        | RecoveryRuntimeMutationCommand
    ),
) -> str:
    if isinstance(command, ConfigReloadRuntimeMutationCommand):
        return CONFIG_RELOAD_COMMAND_NAME
    if isinstance(command, StopRuntimeMutationCommand):
        return STOP_COMMAND_NAME
    if isinstance(command, PluginStopCommandRuntimeMutation):
        return STOP_COMMAND_NAME
    if isinstance(command, DisableRuntimeMutationCommand):
        return DISABLE_COMMAND_NAME
    if isinstance(command, EnableRuntimeMutationCommand):
        return ENABLE_COMMAND_NAME
    if isinstance(command, ClearQuarantineRuntimeMutationCommand):
        return CLEAR_QUARANTINE_COMMAND_NAME
    return RECOVERY_COMMAND_NAME


def entry_has_stop_priority(entry: PluginRuntimeMutationEntry) -> bool:
    if entry.active_command_name in STOP_PRIORITY_COMMAND_NAMES:
        return True
    for queued_command in entry.pending:
        if resolve_runtime_mutation_name(queued_command.command) in STOP_PRIORITY_COMMAND_NAMES:
            return True
    return False


def replace_pending_reload(
    entry: PluginRuntimeMutationEntry,
    replacement: QueuedRuntimeMutation,
) -> QueuedRuntimeMutation | None:
    for index, queued_command in enumerate(entry.pending):
        if isinstance(queued_command.command, ConfigReloadRuntimeMutationCommand):
            entry.pending[index] = replacement
            return queued_command
    return None


def drain_pending_reloads(
    entry: PluginRuntimeMutationEntry,
    *,
    reason: str,
) -> list[DroppedReloadRuntimeMutation]:
    retained_commands: deque[QueuedRuntimeMutation] = deque()
    dropped_reloads: list[DroppedReloadRuntimeMutation] = []
    while entry.pending:
        queued_command = entry.pending.popleft()
        if isinstance(queued_command.command, ConfigReloadRuntimeMutationCommand):
            dropped_reloads.append((queued_command.command.event, queued_command.future, reason))
            continue
        retained_commands.append(queued_command)
    entry.pending = retained_commands
    return dropped_reloads


def insert_stop_priority_command(
    entry: PluginRuntimeMutationEntry,
    queued_command: QueuedRuntimeMutation,
) -> None:
    reordered_commands = deque[QueuedRuntimeMutation]()
    inserted = False
    while entry.pending:
        current_command = entry.pending.popleft()
        if (not inserted) and (
            resolve_runtime_mutation_name(current_command.command)
            not in STOP_PRIORITY_COMMAND_NAMES
        ):
            reordered_commands.append(queued_command)
            inserted = True
        reordered_commands.append(current_command)
    if not inserted:
        reordered_commands.append(queued_command)
    entry.pending = reordered_commands


def build_reload_block_reason(entry: PluginRuntimeMutationEntry) -> str:
    active_command_name = entry.active_command_name
    if active_command_name in STOP_PRIORITY_COMMAND_NAMES:
        return f"discarded because {active_command_name} is in progress"
    for queued_command in entry.pending:
        queued_command_name = resolve_runtime_mutation_name(queued_command.command)
        if queued_command_name in STOP_PRIORITY_COMMAND_NAMES:
            return f"discarded by queued {queued_command_name} command"
    return "discarded because a stop-priority lifecycle command is pending"

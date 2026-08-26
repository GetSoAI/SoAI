"""SoAI - Orchestrator plugin command rejection rules [backend/orchestrator/control/plugin_command_rejection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.error_types import ErrorType
from core.events.types_base import ReplyableCommand
from core.tasks.failure_events import send_error_event_and_finalize
from core.tasks.protocols import TaskRegistryProtocol
from orchestrator.internal_protocols import GuardianRefProtocol
from orchestrator.types import OrchestratorDependencies

__all__ = ("reject_user_command_if_invalid_state",)


async def reject_user_command_if_invalid_state(
    *,
    orchestrator: OrchestratorDependencies,
    guardian_ref: GuardianRefProtocol,
    task_registry: TaskRegistryProtocol,
    plugin_name: str,
    command: ReplyableCommand,
    action_name: str,
    requires_plugin_lock: bool = False,
) -> bool:
    plugin_locked = orchestrator.plugin_manager.lifecycle.is_plugin_locked(plugin_name)
    if requires_plugin_lock:
        if plugin_locked:
            return False
        error_message = (
            f"Cannot {action_name} '{plugin_name}': the owning lifecycle operation"
            " no longer holds the plugin lock."
        )
        await send_error_event_and_finalize(
            command.reply_channel,
            error_message,
            ErrorType.CONFLICT,
            registry=task_registry,
        )
        return True
    if plugin_locked:
        error_message = (
            f"Cannot {action_name} '{plugin_name}': plugin is locked for a critical"
            " lifecycle operation (e.g., deletion)."
        )
        await send_error_event_and_finalize(
            command.reply_channel,
            error_message,
            ErrorType.CONFLICT,
            registry=task_registry,
        )
        return True
    guardian = guardian_ref.value
    if guardian and await guardian.is_plugin_recovering(plugin_name):
        error_message = (
            f"Cannot {action_name} '{plugin_name}': plugin is undergoing automated" " recovery."
        )
        await send_error_event_and_finalize(
            command.reply_channel,
            error_message,
            ErrorType.CONFLICT,
            registry=task_registry,
        )
        return True
    return False

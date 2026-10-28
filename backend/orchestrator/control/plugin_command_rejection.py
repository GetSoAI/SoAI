"""SoAI - Orchestrator plugin command rejection rules [backend/orchestrator/control/plugin_command_rejection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from functools import cache

from core.errors.error_types import ErrorType
from core.events.types_base import ReplyableCommand
from core.logging.rate_limited_logger import RateLimitedLogger
from core.logging.trace import get_logger
from core.tasks.failure_events import send_error_event_and_finalize
from core.tasks.protocols import TaskRegistryProtocol
from orchestrator.internal_protocols import GuardianRefProtocol
from orchestrator.types import OrchestratorDependencies

__all__ = ("reject_user_command_if_invalid_state",)

LOGGER_NAME = "SoAI.orchestrator.control.plugin_command_rejection"
LOCKED_REJECTION_DIAGNOSTIC_INTERVAL_SECONDS = 10.0


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
    lifecycle = orchestrator.plugin_manager.lifecycle
    plugin_locked = lifecycle.is_plugin_locked(plugin_name)
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
    if plugin_locked and not lifecycle.discovery_ownership.is_plugin_locked_by_discovery(
        plugin_name
    ):
        _record_locked_rejection(orchestrator, plugin_name=plugin_name, action_name=action_name)
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


@cache
def _locked_rejection_diagnostics() -> RateLimitedLogger:
    return RateLimitedLogger(interval_seconds=LOCKED_REJECTION_DIAGNOSTIC_INTERVAL_SECONDS)


def _record_locked_rejection(
    orchestrator: OrchestratorDependencies,
    *,
    plugin_name: str,
    action_name: str,
) -> None:
    emit, suppressed = _locked_rejection_diagnostics().should_emit()
    if not emit:
        return
    plugin_manager = orchestrator.plugin_manager
    lifecycle = plugin_manager.lifecycle
    holder = lifecycle.describe_plugin_lock_holder(plugin_name)
    get_logger(LOGGER_NAME).warning(
        (
            "Rejected '%s' for plugin '%s' while its lifecycle lock is held: holder_task=%s "
            "held_ms=%s ownership=%s workers=%s suppressed=%s"
        ),
        action_name,
        plugin_name,
        holder.task_name if holder is not None else None,
        int(holder.held_seconds * 1000) if holder is not None else None,
        lifecycle.discovery_ownership.describe_ownership(plugin_name),
        plugin_manager.describe_worker_ownership(plugin_name),
        suppressed,
    )

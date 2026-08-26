"""SoAI - Durable clone replay reconciliation [backend/plugins/clone/clone_replay.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.database.clone_requests import CloneTransactionRecord
from core.errors.exceptions import StateError
from core.events.types_plugins import ClonePluginCommand
from plugins.actions.progress import send_completion_with_task
from plugins.identity import normalize_plugin_target_name
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

__all__ = (
    "reconcile_committed_clone_after_cancellation",
    "reconcile_replayed_clone",
)


def _validate_replayed_clone_input(
    transaction: CloneTransactionRecord,
    command: ClonePluginCommand,
) -> None:
    requested_target = normalize_plugin_target_name(command.target_name)
    if (
        transaction.source_plugin_name != command.plugin_name
        or transaction.clone_models != command.clone_models
        or (requested_target is not None and requested_target != transaction.target_plugin_name)
    ):
        raise StateError("Clone task identity was reused with different input.")


async def _send_failed_clone_completion(
    plugin_manager: PluginManagerRuntimeProtocol,
    command: ClonePluginCommand,
    task_id: str,
    message: str,
) -> None:
    await send_completion_with_task(
        command.reply_channel,
        task_id,
        success=False,
        message=message,
        error_code=500,
        error_message=message,
        mutation_fencing_token=(
            command.context.mutation_fencing_token if command.context is not None else None
        ),
        task_registry=plugin_manager.dependencies.infrastructure.task_registry,
        send_task_complete_event_callable=plugin_manager.dependencies.infrastructure.task_helpers.send_task_complete_event,
    )


async def reconcile_replayed_clone(
    plugin_manager: PluginManagerRuntimeProtocol,
    command: ClonePluginCommand,
    task_id: str,
    *,
    execute_admitted: bool = False,
) -> CloneTransactionRecord | None:
    transaction = await plugin_manager.dependencies.databases.plugins.clone_transactions.get(
        task_id
    )
    if transaction is None:
        return None
    _validate_replayed_clone_input(transaction, command)
    if transaction.committed or transaction.phase == "committed":
        return transaction
    if transaction.phase == "rolled_back":
        await _send_failed_clone_completion(
            plugin_manager,
            command,
            task_id,
            "Plugin clone was rolled back during recovery.",
        )
        return transaction
    if transaction.phase == "recovery_required":
        await _send_failed_clone_completion(
            plugin_manager,
            command,
            task_id,
            "Plugin clone requires startup recovery.",
        )
        return transaction
    if transaction.phase == "admitted" and execute_admitted:
        return transaction
    if command.reply_channel is not None:
        attached = (
            await plugin_manager.dependencies.infrastructure.task_registry.attach_reply_queue(
                task_id,
                command.reply_channel,
            )
        )
        if attached is None:
            raise StateError("Active clone transaction task is unavailable.")
    return transaction


async def reconcile_committed_clone_after_cancellation(
    plugin_manager: PluginManagerRuntimeProtocol,
    command: ClonePluginCommand,
    task_id: str,
) -> bool:
    transaction = await plugin_manager.dependencies.databases.plugins.clone_transactions.get(
        task_id
    )
    if transaction is None or not (transaction.committed or transaction.phase == "committed"):
        return False
    _validate_replayed_clone_input(transaction, command)
    return True

"""SoAI - Interrupted clone startup recovery [backend/plugins/clone/clone_startup_recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from plugins.clone.clone_committed_integrity import verify_committed_clone_transactions
from plugins.clone.clone_rollback import rollback_clone_transaction
from plugins.clone.operation_locks import clone_operation_locks
from plugins.protocols_internal.runtime.internal_protocols import PluginManagerRuntimeProtocol

__all__ = ("recover_interrupted_clone_transactions",)


async def recover_interrupted_clone_transactions(
    manager: PluginManagerRuntimeProtocol,
) -> int:
    repository = manager.dependencies.databases.plugins.clone_transactions
    await verify_committed_clone_transactions(manager)
    transactions = await repository.list_recoverable()
    for transaction in transactions:
        async with clone_operation_locks(manager, (transaction.target_plugin_name,)):
            await rollback_clone_transaction(manager, task_id=transaction.task_id)
            await finalize(
                manager.dependencies.infrastructure.task_registry,
                transaction.task_id,
                TaskStatus.FAILED,
                error_code=500,
                error_message="Plugin clone was rolled back during startup recovery.",
                status_message="Plugin clone recovery completed with rollback.",
            )
    return len(transactions)

"""SoAI - Clone transaction repository service [backend/database/repositories/plugins/clone_transaction_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.database.clone_requests import (
    CloneArtifactRecord,
    CloneCommitRequest,
    CloneTransactionRecord,
)
from core.database.protocols import DatabaseCoreProtocol
from database.repositories.plugins.clone_commit import sync_commit_clone_transaction
from database.repositories.plugins.clone_committed_transactions import (
    sync_get_committed_clone_for_target,
    sync_list_committed_clone_transactions,
    sync_mark_committed_clone_integrity_failure,
)
from database.repositories.plugins.clone_reservations import (
    sync_get_clone_target_owner,
    sync_list_reserved_clone_targets,
)
from database.repositories.plugins.clone_transactions import (
    sync_get_clone_transaction,
    sync_list_clone_artifacts,
    sync_list_recoverable_clone_transactions,
    sync_mark_clone_rollback_recovery_required,
    sync_record_clone_artifact,
    sync_transition_clone_artifact,
    sync_transition_clone_transaction,
)

__all__ = ("DatabasePluginCloneTransactions",)


class DatabasePluginCloneTransactions:
    def __init__(self, core: DatabaseCoreProtocol) -> None:
        self._core = core

    async def commit(self, request: CloneCommitRequest) -> int | None:
        return await self._core.writer.queue_write_operation(
            sync_commit_clone_transaction,
            request,
        )

    async def get(self, task_id: str) -> CloneTransactionRecord | None:
        return await self._core.writer.queue_write_operation(
            sync_get_clone_transaction,
            task_id,
        )

    async def get_committed_for_target(
        self,
        target_plugin_name: str,
    ) -> CloneTransactionRecord | None:
        return await self._core.writer.queue_write_operation(
            sync_get_committed_clone_for_target,
            target_plugin_name,
        )

    async def get_target_owner(self, target_plugin_name: str) -> str | None:
        return await self._core.writer.queue_write_operation(
            sync_get_clone_target_owner,
            target_plugin_name,
        )

    async def list_artifacts(self, task_id: str) -> tuple[CloneArtifactRecord, ...]:
        return await self._core.writer.queue_write_operation(
            sync_list_clone_artifacts,
            task_id,
        )

    async def list_recoverable(self) -> tuple[CloneTransactionRecord, ...]:
        return await self._core.writer.queue_write_operation(
            sync_list_recoverable_clone_transactions,
        )

    async def list_committed(self) -> tuple[CloneTransactionRecord, ...]:
        return await self._core.writer.queue_write_operation(
            sync_list_committed_clone_transactions,
        )

    async def mark_integrity_failure(
        self,
        task_id: str,
        target_plugin_name: str,
        recovery_error: str,
    ) -> bool:
        return await self._core.writer.queue_write_operation(
            sync_mark_committed_clone_integrity_failure,
            task_id,
            target_plugin_name,
            recovery_error,
        )

    async def list_reserved_targets(self) -> tuple[str, ...]:
        return await self._core.writer.queue_write_operation(
            sync_list_reserved_clone_targets,
        )

    async def record_artifact(
        self,
        task_id: str,
        artifact_type: str,
        staging_path: str,
        final_path: str,
    ) -> int:
        return await self._core.writer.queue_write_operation(
            sync_record_clone_artifact,
            task_id,
            artifact_type,
            staging_path,
            final_path,
        )

    async def transition_artifact(
        self,
        task_id: str,
        artifact_id: int,
        current_state: str,
        following_state: str,
    ) -> bool:
        return await self._core.writer.queue_write_operation(
            sync_transition_clone_artifact,
            task_id,
            artifact_id,
            current_state,
            following_state,
        )

    async def mark_rollback_recovery_required(
        self,
        task_id: str,
        recovery_error: str,
    ) -> bool:
        return await self._core.writer.queue_write_operation(
            sync_mark_clone_rollback_recovery_required,
            task_id,
            recovery_error,
        )

    async def transition(
        self,
        task_id: str,
        current_phase: str,
        following_phase: str,
    ) -> bool:
        return await self._core.writer.queue_write_operation(
            sync_transition_clone_transaction,
            task_id,
            current_phase,
            following_phase,
        )

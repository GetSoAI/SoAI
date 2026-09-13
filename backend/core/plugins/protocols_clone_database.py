"""SoAI - Clone transaction database protocol [backend/core/plugins/protocols_clone_database.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

from core.database.clone_requests import (
    CloneArtifactRecord,
    CloneCommitRequest,
    CloneTransactionRecord,
)

__all__ = ("DatabasePluginCloneTransactionsProtocol",)


class DatabasePluginCloneTransactionsProtocol(Protocol):
    async def commit(self, request: CloneCommitRequest) -> int | None: ...

    async def get(self, task_id: str) -> CloneTransactionRecord | None: ...

    async def get_committed_for_target(
        self,
        target_plugin_name: str,
    ) -> CloneTransactionRecord | None: ...

    async def get_target_owner(self, target_plugin_name: str) -> str | None: ...

    async def list_artifacts(self, task_id: str) -> tuple[CloneArtifactRecord, ...]: ...

    async def list_recoverable(self) -> tuple[CloneTransactionRecord, ...]: ...

    async def list_committed(self) -> tuple[CloneTransactionRecord, ...]: ...

    async def mark_integrity_failure(
        self,
        task_id: str,
        target_plugin_name: str,
        recovery_error: str,
    ) -> bool: ...

    async def list_reserved_targets(self) -> tuple[str, ...]: ...

    async def record_artifact(
        self,
        task_id: str,
        artifact_type: str,
        staging_path: str,
        final_path: str,
    ) -> int: ...

    async def transition_artifact(
        self,
        task_id: str,
        artifact_id: int,
        current_state: str,
        following_state: str,
    ) -> bool: ...

    async def mark_rollback_recovery_required(
        self,
        task_id: str,
        recovery_error: str,
    ) -> bool: ...

    async def transition(
        self,
        task_id: str,
        current_phase: str,
        following_phase: str,
    ) -> bool: ...

"""SoAI - Committed clone startup integrity verification [backend/plugins/clone/clone_committed_integrity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import stat

from core.concurrency.cancellation_cleanup import uncancel_and_wait
from core.errors.exceptions import StateError
from core.state.state_names import PLUGIN_STATE_DELETING
from plugins.clone.clone_committed_cleanup import (
    COMMITTED_CLONE_FILESYSTEM_ARTIFACT_TYPES,
    release_committed_clone_artifact_markers,
)
from plugins.clone.ownership_marker import artifact_ownership_marker_path
from plugins.protocols_internal.runtime.internal_protocols import PluginManagerRuntimeProtocol

__all__ = (
    "is_clone_integrity_quarantined",
    "verify_committed_clone_transactions",
)

_REQUIRED_ARTIFACT_TYPES = frozenset(
    {
        "configuration",
        "database_record",
        "environment",
        "package_cache",
        "plugin_package",
        "runtime",
    }
)


async def is_clone_integrity_quarantined(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> bool:
    transaction = (
        await manager.dependencies.databases.plugins.clone_transactions.get_committed_for_target(
            plugin_name
        )
    )
    return bool(
        transaction is not None
        and transaction.committed
        and transaction.phase == "recovery_required"
    )


async def _verify_artifacts(
    manager: PluginManagerRuntimeProtocol,
    task_id: str,
    target_plugin_name: str,
) -> None:
    repository = manager.dependencies.databases.plugins.clone_transactions
    artifacts = await repository.list_artifacts(task_id)
    artifact_types = {artifact.artifact_type for artifact in artifacts}
    if not _REQUIRED_ARTIFACT_TYPES.issubset(artifact_types):
        raise StateError("Clone artifact journal is incomplete.")
    for artifact in artifacts:
        if artifact.artifact_type in {"plugin_package", "configuration"}:
            try:
                artifact_stat = await asyncio.to_thread(os.lstat, artifact.final_path)
            except OSError as exception:
                raise StateError("Committed clone filesystem artifact is missing.") from exception
            if artifact.state != "published" or not stat.S_ISREG(artifact_stat.st_mode):
                raise StateError("Committed clone filesystem artifact is invalid.")
            continue
        if artifact.artifact_type == "models":
            if artifact.state != "published":
                raise StateError("Committed clone filesystem artifact is invalid.")
            try:
                artifact_stat = await asyncio.to_thread(os.lstat, artifact.final_path)
            except FileNotFoundError as exception:
                marker_exists = await asyncio.to_thread(
                    os.path.lexists,
                    artifact_ownership_marker_path(artifact.final_path),
                )
                if not marker_exists:
                    continue
                raise StateError("Committed clone filesystem artifact is missing.") from exception
            except OSError as exception:
                raise StateError(
                    "Committed clone filesystem artifact is unavailable."
                ) from exception
            if not stat.S_ISDIR(artifact_stat.st_mode):
                raise StateError("Committed clone filesystem artifact is invalid.")
            continue
        if artifact.state != "materialized":
            raise StateError("Clone artifact journal is incomplete.")
    record = await manager.dependencies.databases.plugins.get_plugin_by_name(target_plugin_name)
    if record is None:
        raise StateError("Committed clone database record is missing.")
    await uncancel_and_wait(
        asyncio.to_thread(
            release_committed_clone_artifact_markers,
            artifacts,
            task_id,
            artifact_types=COMMITTED_CLONE_FILESYSTEM_ARTIFACT_TYPES,
        )
    )


async def verify_committed_clone_transactions(
    manager: PluginManagerRuntimeProtocol,
) -> int:
    repository = manager.dependencies.databases.plugins.clone_transactions
    transactions = await repository.list_committed()
    for transaction in transactions:
        record = await manager.dependencies.databases.plugins.get_plugin_by_name(
            transaction.target_plugin_name
        )
        if record is not None and record.get("state") == PLUGIN_STATE_DELETING:
            continue
        try:
            await _verify_artifacts(
                manager,
                transaction.task_id,
                transaction.target_plugin_name,
            )
        except StateError as exception:
            reason = str(exception)
            if "ownership" in reason:
                reason = "Clone artifact ownership mismatch."
            marked = await repository.mark_integrity_failure(
                transaction.task_id,
                transaction.target_plugin_name,
                reason,
            )
            if not marked:
                raise StateError(
                    "Committed clone integrity failure could not be quarantined."
                ) from exception
    return len(transactions)

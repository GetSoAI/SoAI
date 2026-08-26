"""SoAI - Transaction-owned clone rollback [backend/plugins/clone/clone_rollback.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os

from core.concurrency.cancellation_cleanup import uncancel_and_wait
from core.database.clone_requests import CloneArtifactRecord
from core.errors.exceptions import StateError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from plugins.clone.artifact_cleanup import (
    remove_owned_directory,
    remove_owned_file,
)
from plugins.clone.artifact_ownership import is_owned_file
from plugins.clone.directory_identity_release import (
    directory_identity_release_path,
    read_staged_directory_identity_removal,
)
from plugins.clone.file_artifact_removal import (
    read_published_file_removal_marker,
    remove_file_artifact_atomically,
)
from plugins.clone.ownership_marker import (
    artifact_ownership_marker_path,
    require_ownership_marker,
)
from plugins.clone.staging_artifact_ownership import remove_owned_staging_artifact
from plugins.filesystem.runtime_artifacts import (
    remove_plugin_validation_cache_artifacts,
)
from plugins.manager.artifacts import purge_plugin_from_memory
from plugins.package_cache_gc import remove_plugin_package_cache
from plugins.protocols_internal.runtime.internal_protocols import PluginManagerRuntimeProtocol

__all__ = ("rollback_clone_transaction",)


async def _remove_staging_path(artifact: CloneArtifactRecord, task_id: str) -> None:
    path = artifact.staging_path
    if path.startswith(("database_record://", "environment://", "package_cache://", "runtime://")):
        return
    if not os.path.basename(path).endswith(f".clone-{task_id}.staging"):
        raise StateError("Clone staging artifact does not contain its transaction identity.")
    if artifact.artifact_type in {"plugin_package", "configuration"}:
        staging_type = "file"
    elif artifact.artifact_type == "models":
        staging_type = "directory"
    else:
        raise StateError("Clone staging artifact type is invalid.")
    await uncancel_and_wait(
        asyncio.to_thread(
            remove_owned_staging_artifact,
            path,
            task_id,
            staging_type,
        )
    )


async def _remove_artifact(
    manager: PluginManagerRuntimeProtocol,
    artifact: CloneArtifactRecord,
    task_id: str,
    target_plugin_name: str,
) -> None:
    if artifact.artifact_type in {"plugin_package", "configuration"}:
        marker_path = artifact_ownership_marker_path(artifact.final_path)
        if os.path.lexists(artifact.final_path) and not os.path.lexists(marker_path):
            raise StateError("Clone public file ownership marker is missing.")
        staging_removal_marker = read_published_file_removal_marker(
            artifact.staging_path,
            task_id,
        )
        if staging_removal_marker is not None:
            await uncancel_and_wait(
                asyncio.to_thread(
                    remove_file_artifact_atomically,
                    artifact.staging_path,
                    staging_removal_marker,
                    None,
                )
            )
        if os.path.lexists(marker_path):
            await uncancel_and_wait(
                asyncio.to_thread(
                    remove_owned_file,
                    artifact.final_path,
                    task_id,
                    artifact.staging_path,
                )
            )
        await _remove_staging_path(artifact, task_id)
        return
    if artifact.artifact_type == "models":
        marker_path = artifact_ownership_marker_path(artifact.final_path)
        if os.path.lexists(artifact.final_path) and not os.path.lexists(marker_path):
            raise StateError("Clone public directory ownership marker is missing.")
        release_path = directory_identity_release_path(marker_path, task_id)
        release_removal = read_staged_directory_identity_removal(marker_path, task_id)
        if (
            os.path.lexists(marker_path)
            or os.path.lexists(release_path)
            or release_removal is not None
        ):
            await uncancel_and_wait(
                asyncio.to_thread(
                    remove_owned_directory,
                    artifact.final_path,
                    task_id,
                    artifact.staging_path,
                )
            )
        await _remove_staging_path(artifact, task_id)
        return
    await _remove_staging_path(artifact, task_id)
    if artifact.state == "intended":
        package_path = os.path.join(
            manager.paths.plugin_directory,
            f"{target_plugin_name}.soaiplugin",
        )
        package_marker_path = artifact_ownership_marker_path(package_path)
        if not os.path.lexists(package_path) and not os.path.lexists(package_marker_path):
            return
        if os.path.lexists(package_marker_path):
            package_marker = require_ownership_marker(
                package_marker_path,
                task_id,
                "file",
                require_published=False,
            )
            if package_marker.state == "claim":
                return
    package_path = os.path.join(
        manager.paths.plugin_directory,
        f"{target_plugin_name}.soaiplugin",
    )
    if not is_owned_file(package_path, task_id):
        raise StateError("Clone activation ownership anchor is missing.")
    if artifact.artifact_type == "runtime":
        if await manager.get_plugin_instance(target_plugin_name) is not None:
            await purge_plugin_from_memory(manager, target_plugin_name)
        return
    if artifact.artifact_type == "database_record":
        deleted = await manager.dependencies.databases.plugins.permanently_delete_plugin_record(
            target_plugin_name
        )
        if (
            not deleted
            and await manager.dependencies.databases.plugins.get_plugin_by_name(target_plugin_name)
            is not None
        ):
            raise StateError("Clone database record could not be removed during rollback.")
        return
    if artifact.artifact_type == "environment":
        await manager.worker_controller.delete_plugin_environment(target_plugin_name)
        return
    if artifact.artifact_type == "package_cache":
        await remove_plugin_package_cache(manager, target_plugin_name)
        await remove_plugin_validation_cache_artifacts(manager, target_plugin_name)
        await manager.dependencies.infrastructure.config_manager.delete_from_cache(
            target_plugin_name
        )
        return
    raise StateError(f"Unsupported clone artifact type: {artifact.artifact_type}")


async def rollback_clone_transaction(
    manager: PluginManagerRuntimeProtocol,
    *,
    task_id: str,
) -> None:
    repository = manager.dependencies.databases.plugins.clone_transactions
    transaction = await repository.get(task_id)
    if transaction is None or transaction.phase == "rolled_back":
        return
    if transaction.committed or transaction.phase == "committed":
        return
    current_phase = transaction.phase
    if current_phase == "recovery_required":
        if not await repository.transition(task_id, "recovery_required", "rollback_pending"):
            raise StateError("Clone recovery could not resume rollback.")
    elif current_phase != "rollback_pending":
        if not await repository.transition(task_id, current_phase, "rollback_pending"):
            raise StateError("Clone transaction could not enter rollback.")
    failures: list[str] = []
    for artifact in await repository.list_artifacts(task_id):
        if artifact.state == "removed":
            continue
        try:
            await _remove_artifact(
                manager,
                artifact,
                task_id,
                transaction.target_plugin_name,
            )
            if not await repository.transition_artifact(
                task_id,
                artifact.artifact_id,
                artifact.state,
                "removed",
            ):
                raise StateError("Clone artifact rollback transition was rejected.")
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            failures.append(f"{artifact.artifact_type}:{type(exception).__name__}")
            break
    if failures:
        recovery_error = ", ".join(failures)
        if not await repository.mark_rollback_recovery_required(task_id, recovery_error):
            raise StateError("Clone rollback failure could not enter recovery-required state.")
        raise StateError(f"Clone rollback requires recovery: {recovery_error}")
    if not await repository.transition(task_id, "rollback_pending", "rolled_back"):
        raise StateError("Clone transaction could not complete rollback.")

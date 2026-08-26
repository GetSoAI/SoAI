"""SoAI - Committed clone ownership cleanup [backend/plugins/clone/clone_committed_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_and_wait
from core.database.clone_requests import CloneArtifactRecord
from core.errors.exceptions import StateError
from core.filesystem.atomic_write_primitives import fsync_directory
from plugins.clone.directory_artifact_identity import read_directory_identity_entry
from plugins.clone.directory_identity_release import (
    directory_identity_release_path,
    read_staged_directory_identity_removal,
    remove_staged_directory_identity,
    require_directory_identity_entry,
    require_directory_identity_release_state,
    stage_directory_identity_release,
)
from plugins.clone.file_artifact_identity import (
    file_artifact_identity_matches,
    read_file_artifact_identity,
)
from plugins.clone.file_artifact_removal import remove_file_artifact_atomically
from plugins.clone.ownership_marker import (
    DIRECTORY_IDENTITY,
    OwnershipEntry,
    OwnershipMarker,
    artifact_ownership_marker_path,
    ownership_marker_staging_path,
    require_ownership_marker,
)
from plugins.clone.ownership_marker_builders import build_published_file_marker
from plugins.protocols_internal.runtime.internal_protocols import PluginManagerRuntimeProtocol

__all__ = (
    "COMMITTED_CLONE_FILESYSTEM_ARTIFACT_TYPES",
    "COMMITTED_CLONE_MODEL_ARTIFACT_TYPES",
    "release_committed_clone_artifact_markers",
    "release_committed_clone_markers",
)

COMMITTED_CLONE_FILESYSTEM_ARTIFACT_TYPES = frozenset(("configuration", "models", "plugin_package"))
COMMITTED_CLONE_MODEL_ARTIFACT_TYPES = frozenset(("models",))

if TYPE_CHECKING:
    from typing import Literal

    from plugins.clone.directory_identity_release import DirectoryIdentityReleaseState

    type DirectoryReleaseState = DirectoryIdentityReleaseState | Literal["orphaned"]


@dataclass(frozen=True, slots=True)
class _MarkerReleaseOperation:
    artifact: CloneArtifactRecord
    marker: OwnershipMarker | None
    directory_release_state: DirectoryReleaseState | None
    release_identity: OwnershipEntry | None


def _validate_artifact_types(artifact_types: frozenset[str]) -> None:
    if not artifact_types or not artifact_types.issubset(COMMITTED_CLONE_FILESYSTEM_ARTIFACT_TYPES):
        raise StateError("Committed clone marker release artifact types are invalid.")


def _build_release_operation(
    artifact: CloneArtifactRecord,
    task_id: str,
    *,
    allow_missing_models: bool,
) -> _MarkerReleaseOperation | None:
    marker_path = artifact_ownership_marker_path(artifact.final_path)
    if not os.path.lexists(marker_path):
        if artifact.artifact_type == "models":
            release_path = directory_identity_release_path(marker_path, task_id)
            release_identity = (
                read_directory_identity_entry(release_path, task_id)
                if os.path.lexists(release_path)
                else read_staged_directory_identity_removal(
                    marker_path,
                    task_id,
                )
            )
            if release_identity is None:
                return None
            return _MarkerReleaseOperation(
                artifact,
                None,
                "orphaned",
                release_identity,
            )
        return None
    artifact_type = "directory" if artifact.artifact_type == "models" else "file"
    marker = require_ownership_marker(
        marker_path,
        task_id,
        artifact_type,
        require_published=True,
    )
    if artifact_type == "directory":
        release_state = require_directory_identity_release_state(
            artifact.final_path,
            marker_path,
            task_id,
            marker,
            allow_missing_root=allow_missing_models,
        )
        return _MarkerReleaseOperation(
            artifact,
            marker,
            release_state,
            require_directory_identity_entry(marker),
        )
    identity = read_file_artifact_identity(artifact.final_path)
    if artifact.artifact_type == "plugin_package" and not file_artifact_identity_matches(
        identity,
        device=marker.device,
        inode=marker.inode,
        size_bytes=marker.size_bytes,
        sha256_hex=marker.sha256_hex,
    ):
        raise StateError("Clone artifact ownership identity mismatch.")
    return _MarkerReleaseOperation(artifact, marker, None, None)


def _remove_marker_staging(marker_path: str, task_id: str, artifact_type: str) -> None:
    staging_path = ownership_marker_staging_path(marker_path, task_id)
    if not os.path.lexists(staging_path):
        return
    require_ownership_marker(
        staging_path,
        task_id,
        artifact_type,
        require_published=False,
    )
    os.unlink(staging_path)


def _release_directory_operation(operation: _MarkerReleaseOperation, task_id: str) -> None:
    artifact = operation.artifact
    marker_path = artifact_ownership_marker_path(artifact.final_path)
    release_state = operation.directory_release_state
    if release_state is None:
        raise StateError("Clone directory identity release state is missing.")
    if operation.release_identity is None:
        raise StateError("Clone directory release identity is missing.")
    if release_state != "orphaned":
        if operation.marker is None:
            raise StateError("Clone directory ownership marker is missing.")
        release_state = stage_directory_identity_release(
            artifact.final_path,
            marker_path,
            task_id,
            operation.marker,
            release_state,
        )
        for entry in operation.marker.entries:
            if not entry.relative_path.endswith(f"/{DIRECTORY_IDENTITY}"):
                continue
            identity_path = os.path.join(
                artifact.final_path,
                *entry.relative_path.split("/"),
            )
            remove_file_artifact_atomically(
                identity_path,
                build_published_file_marker(
                    task_id,
                    device=entry.device,
                    inode=entry.inode,
                    size_bytes=entry.size_bytes,
                    sha256_hex=entry.sha256_hex,
                ),
                None,
            )
    if operation.marker is not None:
        os.unlink(marker_path)
        fsync_directory(os.path.dirname(artifact.final_path), strict=True)
    remove_staged_directory_identity(
        marker_path,
        task_id,
        "staged" if release_state == "orphaned" else release_state,
        operation.release_identity,
    )


def release_committed_clone_artifact_markers(
    artifacts: tuple[CloneArtifactRecord, ...],
    task_id: str,
    *,
    artifact_types: frozenset[str],
    allow_missing_models: bool = False,
) -> None:
    _validate_artifact_types(artifact_types)
    operations: list[_MarkerReleaseOperation] = []
    for artifact in artifacts:
        if artifact.state != "published" or artifact.artifact_type not in artifact_types:
            continue
        operation = _build_release_operation(
            artifact,
            task_id,
            allow_missing_models=allow_missing_models,
        )
        if operation is not None:
            operations.append(operation)
    for operation in operations:
        artifact = operation.artifact
        marker_path = artifact_ownership_marker_path(artifact.final_path)
        if operation.marker is not None:
            _remove_marker_staging(marker_path, task_id, operation.marker.artifact_type)
        if artifact.artifact_type == "models":
            _release_directory_operation(operation, task_id)
            continue
        os.unlink(marker_path)
        fsync_directory(os.path.dirname(artifact.final_path), strict=True)


async def release_committed_clone_markers(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    *,
    artifact_types: frozenset[str],
    allow_missing_models: bool = False,
) -> None:
    _validate_artifact_types(artifact_types)
    repository = manager.dependencies.databases.plugins.clone_transactions
    transaction = await repository.get_committed_for_target(plugin_name)
    if transaction is None:
        return
    artifacts = await repository.list_artifacts(transaction.task_id)
    await uncancel_and_wait(
        asyncio.to_thread(
            release_committed_clone_artifact_markers,
            artifacts,
            transaction.task_id,
            artifact_types=artifact_types,
            allow_missing_models=allow_missing_models,
        ),
    )

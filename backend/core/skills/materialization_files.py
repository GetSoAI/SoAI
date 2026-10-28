"""SoAI - Verified skill staging and anchored publication [backend/core/skills/materialization_files.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import os
from collections.abc import Generator
from contextlib import ExitStack, contextmanager

from core.concurrency.deadlines import MonotonicDeadline
from core.concurrency.protocols import CancellationTokenProtocol
from core.errors.exceptions import StateError
from core.files.anchored_directory import open_anchored_workspace
from core.files.protocols_anchored import AnchoredDirectoryProtocol
from core.filesystem.windows_sharing_conflicts import sharing_conflict_deadline
from core.skills.packages import calculate_skill_package_digest, validate_skill_resource_inventory
from core.skills.records import SkillMember, SkillResource

__all__ = (
    "validate_materialization_inventory",
    "create_skill_staging",
    "populate_skill_staging",
    "verify_skill_materialization",
    "publish_skill_staging",
    "remove_skill_staging",
    "read_skill_directory_identity",
)


def validate_materialization_inventory(
    members: tuple[SkillMember, ...],
    package_digest: str,
    manifest_path: str = "SKILL.md",
    executable_paths: tuple[str, ...] | None = None,
) -> None:
    _validate_materialization_resources(
        tuple(member.resource for member in members), manifest_path, executable_paths
    )
    for member in members:
        if hashlib.sha256(member.content).hexdigest() != member.digest:
            raise StateError("Retained skill member integrity verification failed.")
    if calculate_skill_package_digest(members, executable_paths=executable_paths) != package_digest:
        raise StateError("Retained skill package integrity verification failed.")


def _validate_materialization_resources(
    resources: tuple[SkillResource, ...],
    manifest_path: str,
    executable_paths: tuple[str, ...] | None,
) -> None:
    validate_skill_resource_inventory(resources, manifest_path=manifest_path)
    if executable_paths is not None and (
        executable_paths != tuple(sorted(set(executable_paths)))
        or not set(executable_paths).issubset(
            resource.path for resource in resources if not resource.is_directory
        )
    ):
        raise StateError("Materialization executable bindings are not canonical regular files.")


@contextmanager
def _member_parent(
    directory: AnchoredDirectoryProtocol, path: str
) -> Generator[AnchoredDirectoryProtocol]:
    with ExitStack() as resources:
        parent = directory
        for part in path.split("/")[:-1]:
            parent = parent.open_directory(part)
            resources.callback(parent.close)
        yield parent


def _require_identity(directory: AnchoredDirectoryProtocol, expected: tuple[int, int]) -> None:
    if directory.identity != expected:
        raise StateError("Materialization directory identity changed.")


def read_skill_directory_identity(
    root: str, identity: tuple[int, int], name: str | None
) -> tuple[int, int] | None:
    with open_anchored_workspace(root) as workspace:
        _require_identity(workspace, identity)
        if name is None:
            return workspace.identity
        try:
            directory = workspace.open_directory(name)
        except FileNotFoundError:
            return None
        try:
            return directory.identity
        finally:
            directory.close()


def create_skill_staging(
    workspace_root: str,
    workspace_identity: tuple[int, int],
    staging_name: str,
    deadline: MonotonicDeadline | None = None,
    cancellation: CancellationTokenProtocol | None = None,
) -> tuple[int, int]:
    with open_anchored_workspace(
        workspace_root, deadline=deadline, cancellation=cancellation
    ) as workspace:
        _require_identity(workspace, workspace_identity)
        staging = workspace.create_directory(staging_name)
        try:
            identity = staging.identity
            staging.flush()
            workspace.flush()
            return identity
        finally:
            staging.close()


def populate_skill_staging(
    workspace_root: str,
    workspace_identity: tuple[int, int],
    staging_name: str,
    staging_identity: tuple[int, int],
    members: tuple[SkillMember, ...],
    package_digest: str,
    cancellation: CancellationTokenProtocol,
    deadline: MonotonicDeadline | None = None,
    manifest_path: str = "SKILL.md",
    executable_paths: tuple[str, ...] | None = None,
) -> None:
    validate_materialization_inventory(members, package_digest, manifest_path, executable_paths)
    operation_deadline = deadline or sharing_conflict_deadline(
        os.path.join(workspace_root, staging_name),
        planned_paths=(
            os.path.join(workspace_root, staging_name, member.path)
            for member in members
            if not member.is_directory
        ),
    )
    with open_anchored_workspace(
        workspace_root, deadline=operation_deadline, cancellation=cancellation
    ) as workspace:
        _require_identity(workspace, workspace_identity)
        staging = workspace.open_directory(staging_name)
        try:
            _require_identity(staging, staging_identity)
            for member in members:
                cancellation.raise_if_cancelled()
                with _member_parent(staging, member.path) as parent:
                    name = member.path.split("/")[-1]
                    if member.is_directory:
                        directory = parent.create_directory(name)
                        directory.close()
                    else:
                        if executable_paths is not None and member.path in executable_paths:
                            parent.write_file(name, member.content, posix_executable=True)
                        else:
                            parent.write_file(name, member.content)
            _verify_inventory(
                staging, tuple(member.resource for member in members), executable_paths
            )
            for member in reversed(members):
                cancellation.raise_if_cancelled()
                if member.is_directory:
                    with _member_parent(staging, member.path) as parent:
                        directory = parent.open_directory(member.path.split("/")[-1])
                        try:
                            directory.flush()
                        finally:
                            directory.close()
            staging.flush()
            workspace.flush()
        finally:
            staging.close()


def _verify_inventory(
    directory: AnchoredDirectoryProtocol,
    resources: tuple[SkillResource, ...],
    executable_paths: tuple[str, ...] | None = None,
) -> None:
    expected_children: dict[str, set[str]] = {"": set()}
    for resource in resources:
        parent_path, _separator, name = resource.path.rpartition("/")
        expected_children[parent_path].add(name)
        if resource.is_directory:
            expected_children[resource.path] = set()
    if set(directory.names()) != expected_children[""]:
        raise StateError("Materialized directory inventory changed.")
    for resource in resources:
        with _member_parent(directory, resource.path) as parent:
            name = resource.path.split("/")[-1]
            if resource.is_directory:
                child = parent.open_directory(name)
                try:
                    if set(child.names()) != expected_children[resource.path]:
                        raise StateError("Materialized directory inventory changed.")
                finally:
                    child.close()
            else:
                content = (
                    parent.read_file(name, resource.size_bytes)
                    if executable_paths is None
                    else parent.read_file(
                        name,
                        resource.size_bytes,
                        posix_executable=resource.path in executable_paths,
                    )
                )
                if (
                    len(content) != resource.size_bytes
                    or hashlib.sha256(content).hexdigest() != resource.digest
                ):
                    raise StateError("Materialized skill member content changed.")


def verify_skill_materialization(
    workspace_root: str,
    workspace_identity: tuple[int, int],
    directory_name: str,
    directory_identity: tuple[int, int],
    resources: tuple[SkillResource, ...],
    manifest_path: str = "SKILL.md",
    executable_paths: tuple[str, ...] | None = None,
    deadline: MonotonicDeadline | None = None,
) -> None:
    _validate_materialization_resources(resources, manifest_path, executable_paths)
    operation_deadline = deadline or sharing_conflict_deadline(
        os.path.join(workspace_root, directory_name)
    )
    with open_anchored_workspace(workspace_root, deadline=operation_deadline) as workspace:
        _require_identity(workspace, workspace_identity)
        directory = workspace.open_directory(directory_name)
        try:
            _require_identity(directory, directory_identity)
            _verify_inventory(directory, resources, executable_paths)
            directory.flush()
            workspace.flush()
        finally:
            directory.close()
    with open_anchored_workspace(workspace_root, deadline=operation_deadline) as current_workspace:
        _require_identity(current_workspace, workspace_identity)
        current_directory = current_workspace.open_directory(directory_name)
        try:
            _require_identity(current_directory, directory_identity)
        finally:
            current_directory.close()


def publish_skill_staging(
    workspace_root: str,
    workspace_identity: tuple[int, int],
    staging_name: str,
    staging_identity: tuple[int, int],
    final_name: str,
    resources: tuple[SkillResource, ...],
    deadline: MonotonicDeadline | None = None,
    manifest_path: str = "SKILL.md",
    executable_paths: tuple[str, ...] | None = None,
) -> None:
    _validate_materialization_resources(resources, manifest_path, executable_paths)
    operation_deadline = deadline or sharing_conflict_deadline(
        os.path.join(workspace_root, staging_name)
    )
    with open_anchored_workspace(workspace_root, deadline=operation_deadline) as workspace:
        _require_identity(workspace, workspace_identity)
        directory = workspace.open_directory(staging_name)
        try:
            _require_identity(directory, staging_identity)
            _verify_inventory(directory, resources, executable_paths)
        finally:
            directory.close()
        workspace.publish_directory(staging_name, final_name)
        workspace.flush()
        published = workspace.open_directory(final_name)
        try:
            _require_identity(published, staging_identity)
            _verify_inventory(published, resources, executable_paths)
        finally:
            published.close()


def remove_skill_staging(
    workspace_root: str,
    workspace_identity: tuple[int, int],
    staging_name: str,
    staging_identity: tuple[int, int],
    resources: tuple[SkillResource, ...],
    deadline: MonotonicDeadline | None = None,
    manifest_path: str = "SKILL.md",
) -> None:
    validate_skill_resource_inventory(resources, manifest_path=manifest_path)
    operation_deadline = deadline or sharing_conflict_deadline(
        os.path.join(workspace_root, staging_name)
    )
    with open_anchored_workspace(workspace_root, deadline=operation_deadline) as workspace:
        _require_identity(workspace, workspace_identity)
        try:
            directory = workspace.open_directory(staging_name)
        except FileNotFoundError:
            workspace.flush()
            return
        try:
            _require_identity(directory, staging_identity)
            for member in reversed(resources):
                try:
                    with _member_parent(directory, member.path) as parent:
                        name = member.path.split("/")[-1]
                        if member.is_directory:
                            parent.remove_directory(name)
                        else:
                            parent.remove_file(name)
                except FileNotFoundError:
                    continue
        finally:
            directory.close()
        workspace.remove_directory(staging_name, expected_identity=staging_identity)
        workspace.flush()

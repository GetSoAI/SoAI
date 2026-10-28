"""SoAI - Private file-backed skill collection preparation and ownership [backend/core/skills/collection_staging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import os
import tempfile

from core.concurrency.protocols import CancellationTokenProtocol
from core.errors.exceptions import StateError
from core.files.anchored_directory import open_anchored_workspace
from core.files.content_hashing import hash_seekable_binary_stream_content
from core.files.file_identity import FileIdentity
from core.filesystem.open_files import create_binary_owner_only, open_regular_binary_no_symlink
from core.skills.collection_discovery import iter_skill_collection_packages
from core.skills.errors import build_skill_error
from core.skills.limits import MAX_UPLOAD_BYTES
from core.skills.packages import (
    calculate_skill_package_digest,
    validate_skill_package,
    validate_skill_resource_inventory,
)
from core.skills.records import (
    SkillMember,
    SkillPackage,
    StagedSkillCollection,
    StagedSkillPackage,
)

__all__ = (
    "prepare_skill_collection",
    "read_staged_skill_package",
    "remove_skill_collection_staging",
)


def prepare_skill_collection(
    upload_path: str,
    filename: str,
    expected_size: int,
    expected_digest: str,
    cancellation: CancellationTokenProtocol,
) -> StagedSkillCollection:
    if expected_size > MAX_UPLOAD_BYTES:
        raise build_skill_error(
            "skill_invalid_package",
            reason="resource_limit",
            field="upload_bytes",
            measured=expected_size,
            limit=MAX_UPLOAD_BYTES,
        )
    directory = tempfile.mkdtemp(prefix="skills-import-", dir=os.path.dirname(upload_path))
    with open_anchored_workspace(directory) as staging:
        identity = staging.identity
    packages: list[StagedSkillPackage] = []
    content_names: list[str] = []
    prepared = False
    try:
        with open_regular_binary_no_symlink(upload_path) as source:
            source_identity = FileIdentity.from_stat(os.fstat(source.fileno()))
            if source_identity.size != expected_size:
                raise StateError("Skill upload size changed before collection validation.")
            hashed = hash_seekable_binary_stream_content(source)
            if hashed.sha256_hex != expected_digest or hashed.size_bytes != expected_size:
                raise StateError("Skill upload identity changed before collection validation.")
            source.seek(0)
            if filename == "SKILL.md":
                package = validate_skill_package(
                    source.read(MAX_UPLOAD_BYTES + 1), filename=filename
                )
                packages.append(_stage_package(directory, "", package, content_names, cancellation))
            elif filename.lower().endswith(".zip"):
                for root, package in iter_skill_collection_packages(
                    source, upload_digest=expected_digest, cancellation=cancellation
                ):
                    packages.append(
                        _stage_package(directory, root, package, content_names, cancellation)
                    )
            else:
                raise build_skill_error("skill_invalid_package", reason="invalid_filename")
            after = FileIdentity.from_stat(os.fstat(source.fileno()))
            if not source_identity.matches_descriptor_snapshot(after):
                raise StateError("Skill upload changed during collection validation.")
        cancellation.raise_if_cancelled()
        prepared = True
        return StagedSkillCollection(directory, identity, expected_digest, tuple(packages))
    finally:
        if not prepared:
            _remove_owned_staging(directory, identity, tuple(content_names))


def _stage_package(
    directory: str,
    source_root: str,
    package: SkillPackage,
    content_names: list[str],
    cancellation: CancellationTokenProtocol,
) -> StagedSkillPackage:
    name = f"package-{len(content_names)}"
    with create_binary_owner_only(os.path.join(directory, name)) as output:
        content_names.append(name)
        for member in (*package.members, *package.supporting_members):
            cancellation.raise_if_cancelled()
            output.write(member.content)
        output.flush()
        identity = FileIdentity.from_stat(os.fstat(output.fileno()))
    return StagedSkillPackage(
        source_root,
        package.manifest,
        tuple(member.resource for member in package.members),
        package.digest,
        package.size_bytes,
        name,
        identity,
        package.profile,
        tuple(member.resource for member in package.supporting_members),
    )


def read_staged_skill_package(
    collection: StagedSkillCollection, package: StagedSkillPackage
) -> SkillPackage:
    members: list[SkillMember] = []
    validate_skill_resource_inventory(package.resources)
    with open_anchored_workspace(collection.directory) as directory:
        if directory.identity != collection.directory_identity:
            raise StateError("Skill import staging directory identity changed.")
        path = os.path.join(collection.directory, package.content_name)
        with open_regular_binary_no_symlink(path) as source:
            before = FileIdentity.from_stat(os.fstat(source.fileno()))
            expected_size = package.size_bytes + sum(
                resource.size_bytes for resource in package.supporting_resources
            )
            if before != package.content_identity or before.size != expected_size:
                raise StateError("Skill import staging file was replaced.")
            for resource in (*package.resources, *package.supporting_resources):
                content = source.read(resource.size_bytes)
                if (
                    len(content) != resource.size_bytes
                    or hashlib.sha256(content).hexdigest() != resource.digest
                ):
                    raise StateError("Skill import staging content integrity verification failed.")
                members.append(
                    SkillMember(resource.path, resource.is_directory, content, resource.digest)
                )
            after = FileIdentity.from_stat(os.fstat(source.fileno()))
            if source.read(1) or not before.matches_descriptor_snapshot(after):
                raise StateError("Skill import staging file changed during installation.")
    inventory = tuple(members[: len(package.resources)])
    if calculate_skill_package_digest(inventory) != package.digest:
        raise StateError("Skill import staging package integrity verification failed.")
    return SkillPackage(
        package.manifest,
        inventory,
        package.digest,
        collection.upload_digest,
        package.size_bytes,
        package.profile,
        tuple(members[len(package.resources) :]),
    )


def remove_skill_collection_staging(collection: StagedSkillCollection) -> None:
    content_names = tuple(package.content_name for package in collection.packages)
    _remove_owned_staging(collection.directory, collection.directory_identity, content_names)


def _remove_owned_staging(
    directory: str, identity: tuple[int, int], content_names: tuple[str, ...]
) -> None:
    with open_anchored_workspace(os.path.dirname(directory)) as parent:
        name = os.path.basename(directory)
        try:
            staging = parent.open_directory(name)
        except FileNotFoundError:
            return
        try:
            if staging.identity != identity:
                raise StateError("Skill import cleanup refused a replaced staging directory.")
            present = set(staging.names())
            if not present.issubset(content_names):
                raise StateError("Skill import cleanup found files outside its owned inventory.")
            for content_name in content_names:
                if content_name in present:
                    staging.remove_file(content_name)
        finally:
            staging.close()
        parent.remove_directory(name, expected_identity=identity)

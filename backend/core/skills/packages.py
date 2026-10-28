"""SoAI - Portable skill package validation and identity [backend/core/skills/packages.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import io
import zipfile
import zlib

from core.archives.errors import ArchivePathTraversalError
from core.archives.resource_limits import ArchivePlanningBudget
from core.archives.zip_bounded_read import read_bounded_zip_member
from core.archives.zip_creation import PortableZipPathIndex
from core.archives.zip_directory_budget import validate_zip_directory_budget
from core.archives.zip_plan import ValidatedZipMember, ZipPlanPolicy, build_validated_zip_plan
from core.errors.exceptions import StateError, ValidationError
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_dict
from core.serialization.sha256_hexdigest import require_canonical_sha256_hexdigest
from core.skills.compatibility_profiles import (
    compile_skill_compatibility_profile,
    load_skill_compatibility_catalog,
)
from core.skills.errors import build_skill_error
from core.skills.limits import (
    MAX_DECODER_MEMORY_BYTES,
    MAX_ENTRIES,
    MAX_FILES,
    MAX_MANIFEST_BYTES,
    MAX_PACKAGE_BYTES,
    MAX_PATH_BYTES,
    MAX_PATH_DEPTH,
    MAX_UPLOAD_BYTES,
    skill_archive_limits,
)
from core.skills.manifest import parse_skill_manifest
from core.skills.records import SkillMember, SkillPackage, SkillResource

__all__ = (
    "calculate_skill_package_digest",
    "validate_skill_package",
    "validate_skill_resource_inventory",
    "complete_skill_inventory",
    "create_skill_member",
    "read_skill_archive_member",
    "skill_package_execution_binding",
    "require_skill_file_capacity",
)


def validate_skill_resource_inventory(
    resources: tuple[SkillResource, ...], *, manifest_path: str = "SKILL.md"
) -> None:
    if not resources or len(resources) > MAX_ENTRIES:
        raise StateError("Skill resource inventory has an invalid entry count.")
    if sum(not resource.is_directory for resource in resources) > MAX_FILES:
        raise StateError("Skill resource inventory exceeds its file count limit.")
    if sum(resource.size_bytes for resource in resources) > MAX_PACKAGE_BYTES:
        raise StateError("Skill resource inventory exceeds its byte limit.")
    if tuple(resource.path for resource in resources) != tuple(
        sorted(resource.path for resource in resources)
    ):
        raise StateError("Skill resource inventory is not canonical.")
    index = PortableZipPathIndex()
    directories: set[str] = set()
    for resource in resources:
        try:
            index.add(resource.path, is_directory=resource.is_directory)
            path_bytes = resource.path.encode("utf-8")
            require_canonical_sha256_hexdigest(resource.digest, label="Skill resource digest")
        except (ArchivePathTraversalError, ValidationError, UnicodeEncodeError) as exception:
            raise StateError(
                "Skill resource inventory contains an invalid path or digest."
            ) from exception
        parts = resource.path.split("/")
        if len(parts) > MAX_PATH_DEPTH or len(path_bytes) > MAX_PATH_BYTES:
            raise StateError("Skill resource inventory exceeds its path limits.")
        if resource.size_bytes < 0:
            raise StateError("Skill resource size must not be negative.")
        if any("/".join(parts[:depth]) not in directories for depth in range(1, len(parts))):
            raise StateError("Skill resource inventory omits a parent directory.")
        if resource.is_directory:
            if resource.size_bytes or resource.digest != hashlib.sha256(b"").hexdigest():
                raise StateError("Skill directory contains unexpected bytes or digest.")
            directories.add(resource.path)
    if not any(
        resource.path == manifest_path and not resource.is_directory for resource in resources
    ):
        raise StateError("Skill resource inventory omits its manifest.")


def validate_skill_package(upload: bytes, *, filename: str) -> SkillPackage:
    members: tuple[SkillMember, ...]
    if len(upload) > MAX_UPLOAD_BYTES:
        raise build_skill_error(
            "skill_invalid_package",
            reason="resource_limit",
            field="upload_bytes",
            measured=len(upload),
            limit=MAX_UPLOAD_BYTES,
        )
    if filename == "SKILL.md":
        members = (create_skill_member("SKILL.md", False, upload),)
        wrapper = None
    elif filename.lower().endswith(".zip"):
        members, wrapper = _read_archive(upload)
    else:
        raise build_skill_error("skill_invalid_package", reason="invalid_filename")
    manifest_member = next(member for member in members if member.path == "SKILL.md")
    manifest = parse_skill_manifest(manifest_member.content)
    if wrapper is not None and wrapper != manifest.name:
        raise build_skill_error("skill_invalid_package", reason="wrapper_name_mismatch")
    return SkillPackage(
        manifest=manifest,
        members=members,
        digest=calculate_skill_package_digest(members),
        upload_digest=hashlib.sha256(upload).hexdigest(),
        size_bytes=sum(len(member.content) for member in members),
        profile=compile_skill_compatibility_profile(
            manifest, "", load_skill_compatibility_catalog(), members=members
        ),
    )


def calculate_skill_package_digest(
    members: tuple[SkillMember, ...], *, executable_paths: tuple[str, ...] | None = None
) -> str:
    digest = hashlib.sha256()
    for member in members:
        for part in (
            b"directory" if member.is_directory else b"file",
            member.path.encode("utf-8"),
            member.content,
        ):
            digest.update(len(part).to_bytes(8, "big"))
            digest.update(part)
    if executable_paths is not None:
        for part in (
            b"executable_paths",
            serialize_json_compact_stable_strict(list(executable_paths)).encode("utf-8"),
        ):
            digest.update(len(part).to_bytes(8, "big"))
            digest.update(part)
    return digest.hexdigest()


def require_skill_file_capacity(file_count: int) -> None:
    if file_count > MAX_FILES:
        raise build_skill_error(
            "skill_invalid_package",
            reason="resource_limit",
            field="regular_files",
            measured=file_count,
            limit=MAX_FILES,
        )


def skill_package_execution_binding(package: SkillPackage, source_root: str) -> str:
    profile = parse_json_dict(package.profile.content_json) if package.profile is not None else {}
    profile.pop("source_root", None)
    publication = profile.pop("publication", None)
    if isinstance(publication, dict):
        executable_paths = publication.get("executable_paths")
        if isinstance(executable_paths, list):
            profile["executable_paths"] = [
                path.removeprefix(f"{source_root}/") if source_root else path
                for path in executable_paths
                if isinstance(path, str)
            ]
    profile["supporting_digests"] = {
        member.path: member.digest for member in package.supporting_members
    }
    return serialize_json_compact_stable_strict(profile)


def _read_archive(upload: bytes) -> tuple[tuple[SkillMember, ...], str | None]:
    try:
        with io.BytesIO(upload) as source:
            limits = skill_archive_limits()
            validate_zip_directory_budget(source, limits)
            with zipfile.ZipFile(source) as archive:
                plan = build_validated_zip_plan(
                    archive,
                    policy=ZipPlanPolicy.strict_portable_paths(resource_limits=limits),
                )
                wrapper = _package_wrapper(plan.members)
                metadata_budget = ArchivePlanningBudget(limits)
                archive_index = PortableZipPathIndex()
                output: dict[str, SkillMember] = {}
                expanded_bytes = 0
                file_count = 0
                for member in plan.members:
                    archive_index.add(member.archive_path, is_directory=member.is_directory)
                    if member.zip_info.external_attr & 0x400:
                        raise ValidationError("Skill ZIP entries must not be reparse points.")
                    content = read_skill_archive_member(
                        source, archive, member, MAX_PACKAGE_BYTES - expanded_bytes, metadata_budget
                    )
                    expanded_bytes += len(content)
                    path = member.archive_path.rstrip("/")
                    if wrapper is not None:
                        if path == wrapper:
                            continue
                        path = path[len(wrapper) + 1 :]
                    if not member.is_directory:
                        file_count += 1
                        require_skill_file_capacity(file_count)
                    output[path] = create_skill_member(path, member.is_directory, content)
                return complete_skill_inventory(output), wrapper
    except ArchivePathTraversalError as exception:
        raise build_skill_error("skill_invalid_package", reason="archive_unsafe") from exception
    except (zipfile.BadZipFile, EOFError, zlib.error, UnicodeDecodeError) as exception:
        raise build_skill_error("skill_invalid_package", reason="archive_integrity") from exception


def _package_wrapper(members: tuple[ValidatedZipMember, ...]) -> str | None:
    manifests = [
        member.archive_path
        for member in members
        if member.archive_path.rstrip("/").split("/")[-1].casefold() == "skill.md"
    ]
    if len(manifests) != 1:
        raise ValidationError("A skill ZIP must contain exactly one SKILL.md manifest.")
    manifest_path = manifests[0]
    if manifest_path == "SKILL.md":
        return None
    parts = manifest_path.split("/")
    if len(parts) != 2 or parts[1] != "SKILL.md":
        raise ValidationError("SKILL.md must be at the ZIP root or in one enclosing directory.")
    wrapper = parts[0]
    if any(
        member.archive_path != f"{wrapper}/" and not member.archive_path.startswith(f"{wrapper}/")
        for member in members
    ):
        raise ValidationError("Every ZIP entry must belong to the same skill directory.")
    return wrapper


def read_skill_archive_member(
    source: io.BufferedIOBase | io.RawIOBase,
    archive: zipfile.ZipFile,
    member: ValidatedZipMember,
    remaining: int,
    metadata_budget: ArchivePlanningBudget,
    aggregate_metadata_budget: ArchivePlanningBudget | None = None,
) -> bytes:
    maximum = remaining
    if member.is_directory:
        maximum = 0
    elif member.archive_path.split("/")[-1] == "SKILL.md":
        maximum = min(maximum, MAX_MANIFEST_BYTES)
    if member.file_size > maximum:
        field = (
            "manifest_bytes"
            if member.archive_path.split("/")[-1] == "SKILL.md"
            else "expanded_bytes"
        )
        raise build_skill_error(
            "skill_invalid_package",
            reason="resource_limit",
            field=field,
            measured=member.file_size,
            limit=maximum,
        )
    return read_bounded_zip_member(
        source,
        archive,
        member.zip_info,
        metadata_budget=metadata_budget,
        maximum_bytes=maximum,
        maximum_decoder_memory_bytes=MAX_DECODER_MEMORY_BYTES,
        aggregate_metadata_budget=aggregate_metadata_budget,
    )


def complete_skill_inventory(members: dict[str, SkillMember]) -> tuple[SkillMember, ...]:
    for path in tuple(members):
        segments = path.split("/")
        if len(segments) > MAX_PATH_DEPTH or len(path.encode("utf-8")) > MAX_PATH_BYTES:
            field = "path_depth" if len(segments) > MAX_PATH_DEPTH else "path_bytes"
            measured, limit = (
                (len(segments), MAX_PATH_DEPTH)
                if field == "path_depth"
                else (len(path.encode("utf-8")), MAX_PATH_BYTES)
            )
            raise build_skill_error(
                "skill_invalid_package",
                reason="resource_limit",
                field=field,
                measured=measured,
                limit=limit,
            )
        for depth in range(1, len(segments)):
            parent = "/".join(segments[:depth])
            if parent not in members:
                members[parent] = create_skill_member(parent, True, b"")
    if len(members) > MAX_ENTRIES:
        raise build_skill_error(
            "skill_invalid_package",
            reason="resource_limit",
            field="materialized_entries",
            measured=len(members),
            limit=MAX_ENTRIES,
        )
    index = PortableZipPathIndex()
    result = tuple(members[path] for path in sorted(members))
    for member in result:
        index.add(member.path, is_directory=member.is_directory)
    return result


def create_skill_member(path: str, is_directory: bool, content: bytes) -> SkillMember:
    return SkillMember(
        path=path,
        is_directory=is_directory,
        content=content,
        digest=hashlib.sha256(content).hexdigest(),
    )

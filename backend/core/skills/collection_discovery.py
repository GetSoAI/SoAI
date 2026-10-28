"""SoAI - Bounded indexed collection discovery on seekable uploads [backend/core/skills/collection_discovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io
import re
import stat
import zipfile
import zlib
from collections.abc import Iterator

from core.archives.errors import ArchivePathTraversalError
from core.archives.resource_limits import ArchivePlanningBudget, encoded_metadata_size
from core.archives.zip_bounded_read import read_bounded_zip_member
from core.archives.zip_creation import PortableZipPathIndex
from core.archives.zip_directory_budget import validate_zip_directory_budget
from core.archives.zip_plan import (
    ValidatedZipMember,
    ZipPlanPolicy,
    add_zip_materialized_outputs,
    validate_zip_member,
)
from core.concurrency.protocols import CancellationTokenProtocol
from core.errors.exceptions import ValidationError
from core.serialization.json_parsing import parse_json_dict
from core.skills.collection_resources import read_collection_supporting_members
from core.skills.collection_roots import (
    SKILL_PLUGIN_MANIFEST_PATHS,
    collection_plugin_manifest_paths,
    collection_skill_source_binding,
    group_skill_members,
    resolve_collection_skill_roots,
)
from core.skills.compatibility_profiles import (
    SkillCompatibilityTool,
    compile_skill_compatibility_profile,
    load_skill_compatibility_catalog,
)
from core.skills.errors import build_skill_error
from core.skills.limits import (
    MAX_DECODER_MEMORY_BYTES,
    MAX_INSTALLED_SKILLS,
    MAX_MANIFEST_BYTES,
    MAX_NAME_CHARACTERS,
    MAX_PACKAGE_BYTES,
    MAX_RETAINED_BYTES,
    skill_archive_limits,
    skill_repository_limits,
)
from core.skills.manifest import SKILL_NAME_PATTERN_TEXT, parse_skill_manifest
from core.skills.packages import (
    calculate_skill_package_digest,
    complete_skill_inventory,
    create_skill_member,
    read_skill_archive_member,
    require_skill_file_capacity,
    skill_package_execution_binding,
)
from core.skills.publication_layout import map_skill_publication, skill_publication_payload
from core.skills.records import SkillMember, SkillPackage, SkillPublicationLayout
from core.types.json import JSONDict

__all__ = ("iter_skill_collection_packages",)


def iter_skill_collection_packages(
    source: io.BufferedIOBase | io.RawIOBase,
    *,
    upload_digest: str,
    cancellation: CancellationTokenProtocol,
) -> Iterator[tuple[str, SkillPackage]]:
    try:
        limits = skill_repository_limits()
        validate_zip_directory_budget(source, limits)
        with zipfile.ZipFile(source) as archive:
            metadata_budget = ArchivePlanningBudget(limits)
            indexed, wrapper = _index_repository(archive, cancellation, metadata_budget)
            declaration_budget = ArchivePlanningBudget(limits)
            declarations: dict[str, JSONDict] = {}
            manifest_paths: list[str] = list(SKILL_PLUGIN_MANIFEST_PATHS)
            for path in manifest_paths:
                member = indexed.get(path)
                if member is not None:
                    _require_retained_member(member)
                    content = read_bounded_zip_member(
                        source,
                        archive,
                        member.zip_info,
                        metadata_budget=declaration_budget,
                        aggregate_metadata_budget=metadata_budget,
                        maximum_bytes=MAX_MANIFEST_BYTES,
                        maximum_decoder_memory_bytes=MAX_DECODER_MEMORY_BYTES,
                    )
                    declarations[path] = parse_json_dict(
                        content, field="skill plugin manifest", reject_duplicate_keys=True
                    )
                    if path.endswith("marketplace.json"):
                        manifest_paths.extend(
                            candidate
                            for candidate in collection_plugin_manifest_paths(declarations)
                            if candidate not in manifest_paths
                        )
            roots = resolve_collection_skill_roots(indexed, declarations)
            grouped = group_skill_members(indexed, roots)
            catalog = load_skill_compatibility_catalog()
            names: dict[str, tuple[str, str, str]] = {}
            retained_bytes = 0
            retained_support: set[str] = set()
            for root in roots:
                cancellation.raise_if_cancelled()
                plugin_root, owners = collection_skill_source_binding(root, declarations)
                parts = root.split("/")
                for depth in range(1, len(parts) + 1):
                    ancestor = indexed.get("/".join(parts[:depth]))
                    if ancestor is not None:
                        _require_retained_member(ancestor)
                package = _read_package(
                    source,
                    archive,
                    root,
                    grouped[root],
                    upload_digest,
                    cancellation,
                    catalog,
                    metadata_budget,
                    indexed,
                    tuple(
                        sorted(
                            {
                                str(payload["name"])
                                for payload in owners
                                if isinstance(payload.get("name"), str)
                                and len(str(payload["name"])) <= MAX_NAME_CHARACTERS
                                and re.fullmatch(SKILL_NAME_PATTERN_TEXT, str(payload["name"]))
                            }
                        )
                    ),
                    wrapper,
                    plugin_root,
                )
                previous = names.get(package.manifest.name)
                bindings = skill_package_execution_binding(package, root)
                if previous is not None:
                    if (
                        previous[1:] == (package.digest, bindings)
                        and not package.supporting_members
                        and "CLAUDE_PLUGIN_ROOT" not in package.manifest.source
                    ):
                        continue
                    raise build_skill_error(
                        "skill_invalid_package",
                        reason="source_conflict",
                        locations=(previous[0], root),
                    )
                names[package.manifest.name] = (root, package.digest, bindings)
                if len(names) > MAX_INSTALLED_SKILLS:
                    raise build_skill_error(
                        "skill_invalid_package",
                        reason="resource_limit",
                        field="installed_skills",
                        measured=len(names),
                        limit=MAX_INSTALLED_SKILLS,
                    )
                retained_bytes += package.size_bytes + sum(
                    len(member.content)
                    for member in package.supporting_members
                    if member.path not in retained_support
                )
                retained_support.update(member.path for member in package.supporting_members)
                if retained_bytes > MAX_RETAINED_BYTES:
                    raise build_skill_error(
                        "skill_invalid_package",
                        reason="resource_limit",
                        field="retained_bytes",
                        measured=retained_bytes,
                        limit=MAX_RETAINED_BYTES,
                    )
                yield root, package
    except ArchivePathTraversalError as exception:
        raise build_skill_error("skill_invalid_package", reason="archive_unsafe") from exception
    except (zipfile.BadZipFile, EOFError, zlib.error, UnicodeDecodeError) as exception:
        raise build_skill_error("skill_invalid_package", reason="archive_integrity") from exception


def _index_repository(
    archive: zipfile.ZipFile, cancellation: CancellationTokenProtocol, budget: ArchivePlanningBudget
) -> tuple[dict[str, ValidatedZipMember], str | None]:
    limits = skill_repository_limits()
    policy = ZipPlanPolicy.strict_portable_paths(resource_limits=limits)
    index = PortableZipPathIndex()
    directories: set[str] = set()
    members: list[ValidatedZipMember] = []
    for info in archive.infolist():
        cancellation.raise_if_cancelled()
        budget.add_member(
            metadata_bytes=encoded_metadata_size(info.orig_filename, info.extra, info.comment),
            name=info.orig_filename,
        )
        member = validate_zip_member(info, policy, allow_symbolic_links=True)
        index.add(member.archive_path, is_directory=member.is_directory)
        add_zip_materialized_outputs(member, directories, budget)
        budget.add_expanded_bytes(member.file_size, member.archive_path)
        members.append(member)
    roots = {member.archive_path.rstrip("/").split("/", 1)[0] for member in members}
    wrapper = next(iter(roots)) if len(roots) == 1 else None
    if wrapper is not None and any(
        member.archive_path.rstrip("/") == wrapper and not member.is_directory for member in members
    ):
        wrapper = None
    if wrapper is not None:
        relative_paths = {member.archive_path[len(wrapper) + 1 :].rstrip("/") for member in members}
        if "SKILL.md" not in relative_paths and not any(
            path in SKILL_PLUGIN_MANIFEST_PATHS
            or path.startswith(("skills/", ".agents/skills/", ".claude/skills/", ".codex/skills/"))
            for path in relative_paths
        ):
            wrapper = None
    output: dict[str, ValidatedZipMember] = {}
    for member in members:
        path = member.archive_path.rstrip("/")
        if wrapper is not None:
            path = path[len(wrapper) :].lstrip("/")
        if path:
            output[path] = member
    return output, wrapper


def _require_retained_member(member: ValidatedZipMember) -> None:
    if stat.S_ISLNK(member.unix_mode) or member.zip_info.external_attr & 0x400:
        raise build_skill_error("skill_invalid_package", reason="archive_unsafe")


def _read_package(
    source: io.BufferedIOBase | io.RawIOBase,
    archive: zipfile.ZipFile,
    root: str,
    members: tuple[tuple[str, ValidatedZipMember], ...],
    upload_digest: str,
    cancellation: CancellationTokenProtocol,
    catalog: tuple[SkillCompatibilityTool, ...],
    metadata_budget: ArchivePlanningBudget,
    indexed: dict[str, ValidatedZipMember],
    namespaces: tuple[str, ...],
    wrapper: str | None,
    plugin_root: str,
) -> SkillPackage:
    limits = skill_archive_limits()
    budget = ArchivePlanningBudget(limits)
    output: dict[str, SkillMember] = {}
    size_bytes = 0
    file_count = 0
    for logical_path, member in members:
        cancellation.raise_if_cancelled()
        _require_retained_member(member)
        content = read_skill_archive_member(
            source, archive, member, MAX_PACKAGE_BYTES - size_bytes, budget, metadata_budget
        )
        size_bytes += len(content)
        file_count += not member.is_directory
        require_skill_file_capacity(file_count)
        path = logical_path[len(root) + 1 :] if root else logical_path
        output[path] = create_skill_member(path, member.is_directory, content)
    inventory = complete_skill_inventory(output)
    manifest_source = output.get("SKILL.md")
    if manifest_source is None:
        raise ValidationError(f"Skill manifest is missing from its source root: {root}")
    manifest = parse_skill_manifest(
        manifest_source.content, directory_name=root.rsplit("/", 1)[-1] or wrapper
    )

    def read_support(path: str) -> SkillMember:
        parts = path.split("/")
        for depth in range(1, len(parts) + 1):
            ancestor = indexed.get("/".join(parts[:depth]))
            if ancestor is not None:
                _require_retained_member(ancestor)
        member = indexed[path]
        content = read_skill_archive_member(
            source, archive, member, MAX_PACKAGE_BYTES, budget, metadata_budget
        )
        return create_skill_member(path, False, content)

    supporting = read_collection_supporting_members(
        root, inventory, indexed, read_support, plugin_root=plugin_root
    )
    publication = map_skill_publication(root, inventory, supporting)
    executable_paths = tuple(
        member.path
        for member in publication
        if not member.is_directory and indexed[member.path].unix_mode & 0o111
    )
    layout = SkillPublicationLayout(
        f"{root}/SKILL.md" if root else "SKILL.md",
        calculate_skill_package_digest(publication, executable_paths=executable_paths),
        tuple((member.path, member.digest) for member in supporting),
        executable_paths,
        plugin_root,
    )
    return SkillPackage(
        manifest,
        inventory,
        calculate_skill_package_digest(inventory),
        upload_digest,
        size_bytes,
        compile_skill_compatibility_profile(
            manifest,
            root,
            catalog,
            members=inventory,
            publication=skill_publication_payload(layout),
            aliases=tuple(f"{namespace}:{manifest.name}" for namespace in namespaces),
        ),
        supporting,
    )

"""SoAI - Tar archive extraction validation plan [backend/core/archives/tar_plan.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import tarfile
from collections.abc import Iterable

from core.archives.constants import validate_member_name
from core.archives.errors import ArchivePathTraversalError
from core.archives.resource_limits import (
    ArchivePlanningBudget,
    ArchiveResourceLimits,
    default_archive_resource_limits,
    encoded_metadata_size,
)
from core.archives.tar_link_plan import build_tar_link_copy_operations
from core.archives.tar_plan_types import TarExtractionPlan, TarLinkMember
from core.errors.exceptions import ValidationError

__all__ = ("TarExtractionPlan", "build_tar_extraction_plan")


def build_tar_extraction_plan(
    members: Iterable[tarfile.TarInfo],
    *,
    limits: ArchiveResourceLimits | None = None,
    budget: ArchivePlanningBudget | None = None,
) -> TarExtractionPlan:
    if limits is not None and budget is not None:
        raise ValidationError("TAR planning accepts either limits or an existing budget, not both.")
    resolved_limits = limits if limits is not None else default_archive_resource_limits()
    planning_budget = budget if budget is not None else ArchivePlanningBudget(resolved_limits)
    validated_destinations: set[str] = set()
    directories: list[str] = []
    directory_set: set[str] = set()
    regular_members: list[tarfile.TarInfo] = []
    links: list[TarLinkMember] = []
    file_sizes: dict[str, int] = {}
    for member in members:
        _add_member_metadata(planning_budget, member)
        validated = validate_member_name(member.name)
        if validated in validated_destinations:
            raise ArchivePathTraversalError(
                f"Archive contains duplicate destination: {member.name} -> '{validated}'",
            )
        validated_destinations.add(validated)
        if member.isdir():
            _add_directory(
                validated,
                directories,
                directory_set,
                file_sizes,
                planning_budget,
                generated=False,
            )
            continue
        if member.issym():
            _add_parent_directories(
                validated,
                directories,
                directory_set,
                file_sizes,
                planning_budget,
            )
            links.append(
                TarLinkMember(
                    destination_path=validated,
                    raw_target=member.linkname,
                    resolved_target=_validate_symlink_target(validated, member.linkname),
                    is_symbolic=True,
                ),
            )
            continue
        if member.islnk():
            _add_parent_directories(
                validated,
                directories,
                directory_set,
                file_sizes,
                planning_budget,
            )
            links.append(
                TarLinkMember(
                    destination_path=validated,
                    raw_target=member.linkname,
                    resolved_target=validate_member_name(member.linkname),
                    is_symbolic=False,
                ),
            )
            continue
        if member.isfile():
            _add_parent_directories(
                validated,
                directories,
                directory_set,
                file_sizes,
                planning_budget,
            )
            if validated in directory_set:
                raise ArchivePathTraversalError(
                    f"Archive destination is both file and directory: {validated}",
                )
            planning_budget.add_materialized_entry(generated_metadata_bytes=0, name=validated)
            planning_budget.add_expanded_bytes(member.size, member.name)
            regular_members.append(member)
            file_sizes[validated] = member.size
    copy_operations = build_tar_link_copy_operations(
        links=tuple(links),
        directories=directories,
        directory_set=directory_set,
        file_sizes=file_sizes,
        budget=planning_budget,
    )
    return TarExtractionPlan(
        directories=tuple(directories),
        regular_members=tuple(regular_members),
        copy_operations=copy_operations,
        total_size=planning_budget.expanded_bytes,
    )


def _add_member_metadata(budget: ArchivePlanningBudget, member: tarfile.TarInfo) -> None:
    pax_values: list[str] = []
    for key, value in member.pax_headers.items():
        pax_values.extend((key, value))
    budget.add_member(
        metadata_bytes=encoded_metadata_size(
            member.name,
            member.linkname,
            member.uname,
            member.gname,
            *pax_values,
        ),
        name=member.name,
    )


def _validate_symlink_target(link_name: str, link_target: str) -> str:
    if os.path.isabs(link_target):
        raise ArchivePathTraversalError(f"Symlink '{link_name}' has absolute target: {link_target}")
    link_dir = os.path.dirname(link_name)
    resolved = os.path.normpath(os.path.join(link_dir, link_target))
    if resolved == ".." or resolved.startswith(f"..{os.sep}"):
        raise ArchivePathTraversalError(
            f"Symlink '{link_name}' target escapes archive: {link_target}",
        )
    return resolved


def _add_parent_directories(
    path: str,
    directories: list[str],
    directory_set: set[str],
    file_sizes: dict[str, int],
    budget: ArchivePlanningBudget,
) -> None:
    directory = os.path.dirname(path)
    pending: list[str] = []
    while directory:
        pending.append(directory)
        directory = os.path.dirname(directory)
    for parent in reversed(pending):
        _add_directory(
            parent,
            directories,
            directory_set,
            file_sizes,
            budget,
            generated=True,
        )


def _add_directory(
    path: str,
    directories: list[str],
    directory_set: set[str],
    file_sizes: dict[str, int],
    budget: ArchivePlanningBudget,
    *,
    generated: bool,
) -> None:
    if path in directory_set:
        return
    if path in file_sizes:
        raise ArchivePathTraversalError(
            f"Archive destination is both file and directory: {path}",
        )
    budget.add_materialized_entry(
        generated_metadata_bytes=encoded_metadata_size(path) if generated else 0,
        name=path,
    )
    directories.append(path)
    directory_set.add(path)

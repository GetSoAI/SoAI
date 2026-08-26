"""SoAI - TAR link materialization planning [backend/core/archives/tar_link_plan.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from bisect import bisect_left

from core.archives.constants import MAX_SYMLINK_CHAIN_DEPTH
from core.archives.errors import (
    ArchiveLinkTargetNotFoundError,
    ArchivePathTraversalError,
)
from core.archives.resource_limits import ArchivePlanningBudget, encoded_metadata_size
from core.archives.tar_plan_types import TarCopyOperation, TarLinkMember

__all__ = ("build_tar_link_copy_operations",)


def build_tar_link_copy_operations(
    *,
    links: tuple[TarLinkMember, ...],
    directories: list[str],
    directory_set: set[str],
    file_sizes: dict[str, int],
    budget: ArchivePlanningBudget,
) -> tuple[TarCopyOperation, ...]:
    copy_operations: list[TarCopyOperation] = []
    symbolic_links: list[TarLinkMember] = []
    for link in links:
        if link.is_symbolic:
            symbolic_links.append(link)
            continue
        _plan_file_copy(
            link,
            file_sizes,
            directory_set,
            budget,
            copy_operations,
        )
    _plan_symbolic_links(
        symbolic_links,
        directories,
        directory_set,
        file_sizes,
        budget,
        copy_operations,
    )
    return tuple(copy_operations)


def _plan_symbolic_links(
    pending_links: list[TarLinkMember],
    directories: list[str],
    directory_set: set[str],
    file_sizes: dict[str, int],
    budget: ArchivePlanningBudget,
    copy_operations: list[TarCopyOperation],
) -> None:
    pending = list(pending_links)
    for _iteration in range(MAX_SYMLINK_CHAIN_DEPTH):
        if not pending:
            return
        sorted_files = sorted(file_sizes)
        sorted_directories = sorted(directory_set)
        available_files = set(sorted_files)
        available_directories = set(sorted_directories)
        made_progress = False
        unresolved: list[TarLinkMember] = []
        for link in pending:
            if link.resolved_target in available_files:
                _plan_file_copy(
                    link,
                    file_sizes,
                    directory_set,
                    budget,
                    copy_operations,
                )
                made_progress = True
                continue
            if link.resolved_target in available_directories:
                _plan_directory_copy(
                    link,
                    sorted_files,
                    sorted_directories,
                    directories,
                    directory_set,
                    file_sizes,
                    budget,
                    copy_operations,
                )
                made_progress = True
                continue
            unresolved.append(link)
        if not made_progress and unresolved:
            names = ", ".join(link.destination_path for link in unresolved)
            raise ArchivePathTraversalError(
                f"Cannot resolve symlinks (circular or missing): {names}",
            )
        pending = unresolved
    if pending:
        raise ArchivePathTraversalError(
            f"Symlink chain depth exceeds {MAX_SYMLINK_CHAIN_DEPTH}",
        )


def _plan_file_copy(
    link: TarLinkMember,
    file_sizes: dict[str, int],
    directory_set: set[str],
    budget: ArchivePlanningBudget,
    copy_operations: list[TarCopyOperation],
) -> None:
    if link.resolved_target not in file_sizes:
        raise ArchiveLinkTargetNotFoundError(
            f"Archive link '{link.destination_path}' references non-existent target '{link.raw_target}'",
        )
    _require_available_destination(link.destination_path, file_sizes, directory_set)
    target_size = file_sizes[link.resolved_target]
    budget.add_materialized_entry(
        generated_metadata_bytes=0,
        name=link.destination_path,
    )
    budget.add_expanded_bytes(target_size, link.destination_path)
    file_sizes[link.destination_path] = target_size
    copy_operations.append(
        TarCopyOperation(
            source_path=link.resolved_target,
            destination_path=link.destination_path,
            file_size=target_size,
        ),
    )


def _plan_directory_copy(
    link: TarLinkMember,
    sorted_files: list[str],
    sorted_directories: list[str],
    directories: list[str],
    directory_set: set[str],
    file_sizes: dict[str, int],
    budget: ArchivePlanningBudget,
    copy_operations: list[TarCopyOperation],
) -> None:
    _require_available_destination(link.destination_path, file_sizes, directory_set)
    _add_generated_directory(link.destination_path, directories, directory_set, budget, False)
    for source_directory in _prefixed_paths(sorted_directories, link.resolved_target):
        relative = source_directory[len(link.resolved_target) :].lstrip(os.sep)
        destination = os.path.join(link.destination_path, relative)
        _require_available_destination(destination, file_sizes, directory_set)
        _add_generated_directory(destination, directories, directory_set, budget, True)
    for source_file in _prefixed_paths(sorted_files, link.resolved_target):
        relative = source_file[len(link.resolved_target) :].lstrip(os.sep)
        destination = os.path.join(link.destination_path, relative)
        _require_available_destination(destination, file_sizes, directory_set)
        file_size = file_sizes[source_file]
        budget.add_materialized_entry(
            generated_metadata_bytes=encoded_metadata_size(destination),
            name=destination,
        )
        budget.add_expanded_bytes(file_size, destination)
        file_sizes[destination] = file_size
        copy_operations.append(
            TarCopyOperation(
                source_path=source_file,
                destination_path=destination,
                file_size=file_size,
            ),
        )


def _prefixed_paths(paths: list[str], root: str) -> tuple[str, ...]:
    prefix = f"{root.rstrip(os.sep)}{os.sep}"
    start = bisect_left(paths, prefix)
    matches: list[str] = []
    for index in range(start, len(paths)):
        path = paths[index]
        if not path.startswith(prefix):
            break
        matches.append(path)
    return tuple(matches)


def _add_generated_directory(
    path: str,
    directories: list[str],
    directory_set: set[str],
    budget: ArchivePlanningBudget,
    count_metadata: bool,
) -> None:
    budget.add_materialized_entry(
        generated_metadata_bytes=encoded_metadata_size(path) if count_metadata else 0,
        name=path,
    )
    directories.append(path)
    directory_set.add(path)


def _require_available_destination(
    destination: str,
    file_sizes: dict[str, int],
    directory_set: set[str],
) -> None:
    if destination in file_sizes or destination in directory_set:
        raise ArchivePathTraversalError(
            f"Archive link expansion collides with existing destination: {destination}",
        )

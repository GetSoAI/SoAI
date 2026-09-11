"""SoAI - Canonical validated ZIP archive plans [backend/core/archives/zip_plan.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat
import unicodedata
import zipfile
from dataclasses import dataclass, field, replace

from core.archives.constants import validate_member_name
from core.archives.errors import ArchivePathTraversalError
from core.archives.resource_limits import (
    ArchivePlanningBudget,
    ArchiveResourceLimits,
    default_archive_resource_limits,
    encoded_metadata_size,
)
from core.errors.exceptions import ValidationError

__all__ = (
    "ValidatedZipMember",
    "ValidatedZipPlan",
    "ZipPlanPolicy",
    "build_validated_zip_plan",
)

SUPPORTED_ZIP_COMPRESSION_TYPES = frozenset(
    {
        zipfile.ZIP_STORED,
        zipfile.ZIP_DEFLATED,
        zipfile.ZIP_BZIP2,
        zipfile.ZIP_LZMA,
    }
)


@dataclass(frozen=True, slots=True)
class ZipPlanPolicy:
    reject_backslashes: bool = False
    reject_colons: bool = False
    reject_empty_segments: bool = False
    reject_case_collisions: bool = False
    reject_unicode_collisions: bool = False
    reject_prefix_conflicts: bool = True
    resource_limits: ArchiveResourceLimits = field(
        default_factory=default_archive_resource_limits,
    )

    @classmethod
    def strict_portable_paths(cls, *, resource_limits: ArchiveResourceLimits) -> ZipPlanPolicy:
        return cls(
            reject_backslashes=True,
            reject_colons=True,
            reject_empty_segments=True,
            reject_case_collisions=True,
            reject_unicode_collisions=True,
            resource_limits=resource_limits,
        )

    @classmethod
    def plugin_package(cls) -> ZipPlanPolicy:
        return replace(
            cls.strict_portable_paths(
                resource_limits=replace(
                    default_archive_resource_limits(),
                    max_members=10_000,
                    max_materialized_entries=10_000,
                ),
            ),
            reject_prefix_conflicts=True,
        )


@dataclass(frozen=True, slots=True)
class ValidatedZipMember:
    zip_info: zipfile.ZipInfo
    archive_path: str
    destination_path: str
    is_directory: bool
    file_size: int
    unix_mode: int


@dataclass(frozen=True, slots=True)
class ValidatedZipPlan:
    members: tuple[ValidatedZipMember, ...]
    total_uncompressed_size: int


def build_validated_zip_plan(
    zip_file: zipfile.ZipFile,
    *,
    policy: ZipPlanPolicy | None = None,
) -> ValidatedZipPlan:
    resolved_policy = policy or ZipPlanPolicy()
    info_list = zip_file.infolist()
    if len(info_list) > resolved_policy.resource_limits.max_members:
        raise ValidationError(
            f"ZIP archive exceeds the member limit of {resolved_policy.resource_limits.max_members}.",
        )
    budget = ArchivePlanningBudget(resolved_policy.resource_limits)
    members: list[ValidatedZipMember] = []
    exact_destinations: set[str] = set()
    folded_destinations: dict[str, str] = {}
    unicode_destinations: dict[str, str] = {}
    file_destinations: set[str] = set()
    canonical_file_destinations: set[str] = set()
    materialized_directories: set[str] = set()
    for zip_info in info_list:
        budget.add_member(
            metadata_bytes=encoded_metadata_size(
                zip_info.orig_filename,
                zip_info.extra,
                zip_info.comment,
            ),
            name=zip_info.orig_filename,
        )
        member = _validate_member(zip_info, resolved_policy)
        _validate_destination_collisions(
            member,
            resolved_policy,
            exact_destinations,
            folded_destinations,
            unicode_destinations,
            file_destinations,
            canonical_file_destinations,
        )
        exact_destinations.add(member.destination_path)
        _add_materialized_outputs(
            member,
            materialized_directories,
            budget,
        )
        if not member.is_directory:
            budget.add_expanded_bytes(member.file_size, member.archive_path)
        if not member.is_directory:
            file_destinations.add(member.destination_path)
            canonical_file_destinations.add(_canonical_destination(member.destination_path))
        members.append(member)
    return ValidatedZipPlan(
        members=tuple(members),
        total_uncompressed_size=budget.expanded_bytes,
    )


def _add_materialized_outputs(
    member: ValidatedZipMember,
    materialized_directories: set[str],
    budget: ArchivePlanningBudget,
) -> None:
    path_parts = member.destination_path.split(os.sep)
    for index in range(1, len(path_parts)):
        parent = os.sep.join(path_parts[:index])
        if parent in materialized_directories:
            continue
        budget.add_materialized_entry(
            generated_metadata_bytes=encoded_metadata_size(parent),
            name=parent,
        )
        materialized_directories.add(parent)
    if member.is_directory and member.destination_path in materialized_directories:
        return
    budget.add_materialized_entry(
        generated_metadata_bytes=0,
        name=member.archive_path,
    )
    if member.is_directory:
        materialized_directories.add(member.destination_path)


def _validate_member(zip_info: zipfile.ZipInfo, policy: ZipPlanPolicy) -> ValidatedZipMember:
    archive_path = zip_info.orig_filename
    if not archive_path or "\x00" in archive_path:
        raise ArchivePathTraversalError("ZIP archive contains an empty or NUL-valued member path.")
    if policy.reject_backslashes and "\\" in archive_path:
        raise ArchivePathTraversalError(
            f"ZIP archive member contains a backslash: {archive_path}",
        )
    if policy.reject_colons and ":" in archive_path:
        raise ArchivePathTraversalError(
            f"ZIP archive member contains a colon: {archive_path}",
        )
    if policy.reject_empty_segments and "" in archive_path.split("/")[:-1]:
        raise ArchivePathTraversalError(
            f"ZIP archive member contains an empty path segment: {archive_path}",
        )
    destination_path = validate_member_name(archive_path)
    if zip_info.flag_bits & 0x1:
        raise ValidationError(f"ZIP archive member is encrypted: {archive_path}")
    if zip_info.compress_type not in SUPPORTED_ZIP_COMPRESSION_TYPES:
        raise ValidationError(
            f"ZIP archive member uses unsupported compression: {archive_path}",
        )
    unix_mode = (zip_info.external_attr >> 16) & 0xFFFF
    file_type = stat.S_IFMT(unix_mode)
    if file_type == stat.S_IFLNK:
        raise ArchivePathTraversalError(f"ZIP archive contains a symbolic link: {archive_path}")
    if file_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
        raise ArchivePathTraversalError(
            f"ZIP archive contains a redirected or special member: {archive_path}",
        )
    filename_is_directory = zip_info.is_dir()
    if file_type in {stat.S_IFREG, stat.S_IFDIR} and (
        filename_is_directory != (file_type == stat.S_IFDIR)
    ):
        raise ArchivePathTraversalError(
            f"ZIP archive member filename and Unix file type disagree: {archive_path}",
        )
    return ValidatedZipMember(
        zip_info=zip_info,
        archive_path=archive_path,
        destination_path=destination_path,
        is_directory=filename_is_directory,
        file_size=zip_info.file_size,
        unix_mode=unix_mode,
    )


def _validate_destination_collisions(
    member: ValidatedZipMember,
    policy: ZipPlanPolicy,
    exact_destinations: set[str],
    folded_destinations: dict[str, str],
    unicode_destinations: dict[str, str],
    file_destinations: set[str],
    canonical_file_destinations: set[str],
) -> None:
    destination = member.destination_path
    if destination in exact_destinations:
        raise ArchivePathTraversalError(
            f"ZIP archive contains duplicate destination: {destination}"
        )
    if policy.reject_case_collisions:
        folded = unicodedata.normalize("NFC", destination).casefold()
        previous = folded_destinations.get(folded)
        if previous is not None and previous != destination:
            raise ArchivePathTraversalError(
                f"ZIP archive contains case-conflicting destinations: {previous}, {destination}",
            )
        folded_destinations[folded] = destination
    if policy.reject_unicode_collisions:
        unicode_key = unicodedata.normalize("NFC", destination)
        previous = unicode_destinations.get(unicode_key)
        if previous is not None and previous != destination:
            raise ArchivePathTraversalError(
                f"ZIP archive contains Unicode-conflicting destinations: {previous}, {destination}",
            )
        unicode_destinations[unicode_key] = destination
    if not policy.reject_prefix_conflicts:
        return
    path_parts = destination.split(os.sep)
    prefixes = {os.sep.join(path_parts[:index]) for index in range(1, len(path_parts))}
    canonical_prefixes = {_canonical_destination(prefix) for prefix in prefixes}
    conflicting_files = prefixes.intersection(file_destinations)
    canonical_conflicting_files: set[str] = (
        canonical_prefixes.intersection(canonical_file_destinations)
        if policy.reject_case_collisions or policy.reject_unicode_collisions
        else set()
    )
    if conflicting_files or canonical_conflicting_files:
        conflict = sorted(conflicting_files or canonical_conflicting_files)[0]
        raise ArchivePathTraversalError(
            f"ZIP archive destination is nested beneath a file: {conflict}, {destination}",
        )
    canonical_destination = _canonical_destination(destination)
    if not member.is_directory:
        nested_prefix = f"{destination}{os.sep}"
        canonical_nested_prefix = f"{canonical_destination}{os.sep}"
        nested = sorted(
            existing
            for existing in exact_destinations
            if existing.startswith(nested_prefix)
            or (
                (policy.reject_case_collisions or policy.reject_unicode_collisions)
                and _canonical_destination(existing).startswith(canonical_nested_prefix)
            )
        )
        if nested:
            raise ArchivePathTraversalError(
                f"ZIP archive file conflicts with nested destination: {destination}, {nested[0]}",
            )


def _canonical_destination(destination: str) -> str:
    return unicodedata.normalize("NFC", destination).casefold()

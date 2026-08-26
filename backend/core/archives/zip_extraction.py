"""SoAI - Zip archive extraction helpers [backend/core/archives/zip_extraction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io
import os
import shutil
import zipfile
from collections.abc import Callable, Sequence
from contextlib import ExitStack
from dataclasses import dataclass, field, replace
from functools import partial

from core.archives.constants import (
    CHUNK_READ_SIZE,
    UNIX_MODE_MASK,
    UNIX_MODE_SYMLINK,
    UNIX_MODE_TYPE_MASK,
)
from core.archives.errors import ArchivePathTraversalError
from core.archives.extraction_move import move_extracted_items
from core.archives.reservations import (
    DiskReservationRequest,
    open_disk_reservation,
    open_write_claim,
)
from core.archives.resource_limits import default_archive_resource_limits
from core.archives.zip_directory_budget import validate_zip_directory_budget
from core.archives.zip_members import (
    detect_root_prefix,
    normalize_zip_member_path,
    should_skip_member,
    should_skip_top_level_member,
    validate_zip_member_symlink,
)
from core.archives.zip_plan import ValidatedZipMember, build_validated_zip_plan
from core.archives.zip_plan_extraction import (
    extract_validated_zip_members,
    extract_validated_zip_plan,
)
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.files.path_policy import ensure_path_within_base_lexical
from core.files.temp_files import create_persistent_staging_directory
from core.filesystem.open_files import open_binary
from core.hardware.protocols_storage import DiskSpaceReservationProviderProtocol

__all__ = (
    "CHUNK_READ_SIZE",
    "UNIX_MODE_MASK",
    "UNIX_MODE_SYMLINK",
    "UNIX_MODE_TYPE_MASK",
    "ZipExtractionOptions",
    "ZipExtractionResult",
    "async_safe_zip_extractall",
    "safe_zip_extract_with_options",
    "safe_zip_extractall",
)


@dataclass(frozen=True, slots=True)
class ZipExtractionOptions:
    ignore_patterns: Sequence[str] = field(default_factory=tuple)
    top_level_ignore_patterns: Sequence[str] = field(default_factory=tuple)
    strip_root_prefix: bool = True
    on_member_skipped: Callable[[str, str], None] | None = None


@dataclass(frozen=True, slots=True)
class ZipExtractionResult:
    extracted_files: list[str]
    root_prefix: str | None


def safe_zip_extractall(
    archive_path: str | io.BufferedIOBase | io.RawIOBase,
    destination: str,
    *,
    reservation_provider: DiskSpaceReservationProviderProtocol,
) -> list[str]:
    real_destination = os.path.realpath(destination)
    destination_parent = os.path.dirname(real_destination) or real_destination
    archive_label = archive_path if isinstance(archive_path, str) else "<binary-stream>"

    with ExitStack() as source_stack:
        archive_source = (
            source_stack.enter_context(open_binary(archive_path, mode="rb"))
            if isinstance(archive_path, str)
            else archive_path
        )
        validate_zip_directory_budget(archive_source, default_archive_resource_limits())
        zip_file = source_stack.enter_context(zipfile.ZipFile(archive_source, "r"))
        plan = build_validated_zip_plan(zip_file)
        total_size = plan.total_uncompressed_size

        with open_disk_reservation(
            reservation_provider,
            requests=(DiskReservationRequest(path=destination_parent, required_bytes=total_size),),
            operation="core.archives.zip_extraction.extract",
            details={"archive_path": archive_label, "destination": real_destination},
        ) as reservation:
            with open_write_claim(reservation, size_bytes=total_size) as claim:
                os.makedirs(destination, exist_ok=True)
                temp_dir = create_persistent_staging_directory(
                    prefix=".soai_zip_extract.",
                    directory=destination_parent,
                )
                try:
                    extracted = extract_validated_zip_plan(zip_file, plan, temp_dir)
                    move_extracted_items(temp_dir=temp_dir, destination=real_destination)
                finally:
                    if os.path.lexists(temp_dir):
                        shutil.rmtree(temp_dir)
                if claim is not None:
                    claim.commit()

                return extracted


async def async_safe_zip_extractall(
    archive_path: str,
    destination: str,
    *,
    reservation_provider: DiskSpaceReservationProviderProtocol,
) -> list[str]:
    return await run_joined_thread_call(
        partial(
            safe_zip_extractall,
            archive_path,
            destination,
            reservation_provider=reservation_provider,
        ),
        task_name="safe-zip-extraction",
    )


def safe_zip_extract_with_options(
    zip_source: str | io.BufferedIOBase | io.RawIOBase,
    destination: str,
    options: ZipExtractionOptions | None = None,
    *,
    reservation_provider: DiskSpaceReservationProviderProtocol,
) -> ZipExtractionResult:
    resolved_options = options or ZipExtractionOptions()
    base_path_abs = os.path.abspath(destination)
    destination_parent = os.path.dirname(base_path_abs) or base_path_abs

    with ExitStack() as source_stack:
        archive_source = (
            source_stack.enter_context(open_binary(zip_source, mode="rb"))
            if isinstance(zip_source, str)
            else zip_source
        )
        validate_zip_directory_budget(archive_source, default_archive_resource_limits())
        zip_file = source_stack.enter_context(zipfile.ZipFile(archive_source, "r"))
        plan = build_validated_zip_plan(zip_file)
        members = [member.zip_info for member in plan.members]
        if not members:
            return ZipExtractionResult(extracted_files=[], root_prefix=None)

        root_prefix = detect_root_prefix(members) if resolved_options.strip_root_prefix else None
        extracted: list[str] = []
        validated_destinations: set[str] = set()
        extraction_members: list[ValidatedZipMember] = []

        for planned_member in plan.members:
            member = planned_member.zip_info
            relative_path = _resolve_extractable_zip_member(
                member,
                root_prefix,
                resolved_options,
                validated_destinations,
                base_path_abs,
                destination,
            )
            if relative_path is None:
                continue
            extraction_members.append(
                replace(planned_member, destination_path=relative_path),
            )
        total_size = sum(
            member.file_size for member in extraction_members if not member.is_directory
        )

        with open_disk_reservation(
            reservation_provider,
            requests=(DiskReservationRequest(path=destination_parent, required_bytes=total_size),),
            operation="core.archives.zip_extraction.extract_with_options",
            details={"destination": base_path_abs},
        ) as reservation:
            with open_write_claim(reservation, size_bytes=total_size) as claim:
                os.makedirs(destination, exist_ok=True)
                temp_dir = create_persistent_staging_directory(
                    prefix=".soai_zip_extract.",
                    directory=destination_parent,
                )
                try:
                    extract_validated_zip_members(
                        zip_file,
                        tuple(extraction_members),
                        temp_dir,
                    )
                    extracted.extend(
                        member.destination_path
                        for member in extraction_members
                        if not member.is_directory
                    )

                    move_extracted_items(temp_dir=temp_dir, destination=base_path_abs)
                finally:
                    if os.path.lexists(temp_dir):
                        shutil.rmtree(temp_dir)
                if claim is not None:
                    claim.commit()

    return ZipExtractionResult(extracted_files=extracted, root_prefix=root_prefix)


def _resolve_extractable_zip_member(
    member: zipfile.ZipInfo,
    root_prefix: str | None,
    options: ZipExtractionOptions,
    validated_destinations: set[str],
    base_path_abs: str,
    destination: str,
) -> str | None:
    posix_name = member.filename.replace("\\", "/")
    relative_path = normalize_zip_member_path(
        posix_name,
        root_prefix,
        strip_root=options.strip_root_prefix,
    )
    if not relative_path:
        return None
    if relative_path in validated_destinations:
        raise ArchivePathTraversalError(
            f"Archive contains duplicate destination: {member.filename} -> '{relative_path}'",
        )
    validated_destinations.add(relative_path)
    validate_zip_member_symlink(member)
    skip_component = should_skip_member(relative_path, options.ignore_patterns)
    skip_top_level = should_skip_top_level_member(relative_path, options.top_level_ignore_patterns)
    if skip_component or skip_top_level:
        if options.on_member_skipped:
            options.on_member_skipped(member.filename, "ignore_pattern")
        return None
    target_abs = os.path.abspath(os.path.join(destination, relative_path))
    try:
        ensure_path_within_base_lexical(
            base_path_abs,
            target_abs,
            description="Archive entry destination path",
            error_cls=ArchivePathTraversalError,
        )
    except ArchivePathTraversalError as exception:
        raise ArchivePathTraversalError(
            f"Archive entry escapes base directory: {member.filename}",
        ) from exception
    return relative_path

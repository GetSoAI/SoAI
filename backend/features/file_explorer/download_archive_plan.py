"""SoAI - Secure file explorer download archive planning [backend/features/file_explorer/download_archive_plan.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from threading import Event

from core.archives.zip_creation import (
    PortableZipPathIndex,
    calculate_zip_archive_upper_bound,
)
from core.errors.exceptions import (
    ConflictError,
    NotFoundError,
    PayloadTooLargeError,
    SecurityError,
    StateError,
    ValidationError,
)
from core.files.file_identity import FileIdentity
from core.files.managed_path_access import stat_managed_path
from core.files.managed_storage_errors import FileStorageSecurityError
from core.files.path_policy import ensure_path_within_base_lexical
from core.validation.strict_numbers import require_positive_int_strict
from features.file_explorer.download_archive_cancellation import (
    raise_if_download_archive_cancelled,
)
from features.file_explorer.download_archive_directory_access import (
    read_download_directory_entries,
)
from features.file_explorer.download_archive_models import (
    DownloadArchiveDirectory,
    DownloadArchiveEntry,
    DownloadArchivePlan,
)

__all__ = ("build_download_archive_plan",)


def build_download_archive_plan(
    *,
    root_path: str,
    selected_paths: tuple[str, ...],
    maximum_members: int,
    maximum_archive_bytes: int,
    cancellation_event: Event,
) -> DownloadArchivePlan:
    member_limit = require_positive_int_strict(
        maximum_members,
        error_message="maximum_members must be a positive integer",
    )
    if not selected_paths:
        raise ValidationError("At least one file explorer download path is required.")
    registry = PortableZipPathIndex()
    entries: list[DownloadArchiveEntry] = []
    directories: list[DownloadArchiveDirectory] = []
    first_source_identity: FileIdentity | None = None
    first_archive_name = ""
    for source_path in selected_paths:
        raise_if_download_archive_cancelled(cancellation_event)
        validated_source = ensure_path_within_base_lexical(
            root_path,
            source_path,
            description="File explorer download source",
            error_cls=SecurityError,
        )
        archive_name = os.path.basename(validated_source.rstrip(os.sep)) or "file-explorer"
        source_identity = _read_source_identity(root_path, validated_source)
        if first_source_identity is None:
            first_source_identity = source_identity
            first_archive_name = archive_name
        archive_path = registry.add_unique_root(
            archive_name,
            is_directory=source_identity.is_directory,
        )
        entries.append(
            DownloadArchiveEntry(
                source_path=validated_source,
                archive_path=archive_path,
                identity=source_identity,
            ),
        )
        _require_member_limit(entries, member_limit)
        if source_identity.is_directory:
            _scan_directory(
                source_path=validated_source,
                archive_path=archive_path,
                source_identity=source_identity,
                root_path=root_path,
                registry=registry,
                entries=entries,
                directories=directories,
                maximum_members=member_limit,
                cancellation_event=cancellation_event,
            )
    members = [(entry.archive_path, entry.identity.size, entry.is_directory) for entry in entries]
    required_bytes = calculate_zip_archive_upper_bound(
        members,
        maximum_bytes=maximum_archive_bytes,
    )
    filename = (
        f"{first_archive_name}.zip"
        if len(selected_paths) == 1
        and first_source_identity is not None
        and first_source_identity.is_directory
        else "file-explorer-selection.zip"
    )
    return DownloadArchivePlan(
        entries=tuple(entries),
        directories=tuple(directories),
        required_bytes=required_bytes,
        download_filename=filename,
    )


def _scan_directory(
    *,
    source_path: str,
    archive_path: str,
    source_identity: FileIdentity,
    root_path: str,
    registry: PortableZipPathIndex,
    entries: list[DownloadArchiveEntry],
    directories: list[DownloadArchiveDirectory],
    maximum_members: int,
    cancellation_event: Event,
) -> None:
    pending: list[tuple[str, str, FileIdentity]] = [
        (source_path, archive_path, source_identity),
    ]
    while pending:
        raise_if_download_archive_cancelled(cancellation_event)
        current_source, current_archive, planned_identity = pending.pop()
        current_identity = _read_source_identity(root_path, current_source)
        if current_identity != planned_identity or not current_identity.is_directory:
            raise ConflictError(
                "File explorer download source changed while the archive was being planned.",
                operation="file_explorer.download_archive.plan",
            )
        child_entries = read_download_directory_entries(
            root_path,
            current_source,
            expected_identity=current_identity,
        )
        directories.append(
            DownloadArchiveDirectory(
                source_path=current_source,
                identity=current_identity,
                child_names=tuple(name for name, _identity in child_entries),
            ),
        )
        child_directories: list[tuple[str, str, FileIdentity]] = []
        for child_name, identity in child_entries:
            raise_if_download_archive_cancelled(cancellation_event)
            child_path = ensure_path_within_base_lexical(
                root_path,
                os.path.join(current_source, child_name),
                description="File explorer download entry",
                error_cls=SecurityError,
            )
            child_archive = registry.add(
                f"{current_archive.rstrip('/')}/{child_name}",
                is_directory=identity.is_directory,
            )
            entries.append(
                DownloadArchiveEntry(
                    source_path=child_path,
                    archive_path=child_archive,
                    identity=identity,
                ),
            )
            _require_member_limit(entries, maximum_members)
            if identity.is_directory:
                child_directories.append((child_path, child_archive, identity))
        pending.extend(reversed(child_directories))


def _read_source_identity(root_path: str, source_path: str) -> FileIdentity:
    try:
        identity = FileIdentity.from_stat(stat_managed_path(root_path, source_path))
    except FileStorageSecurityError as exception:
        if isinstance(exception.__cause__, FileNotFoundError):
            raise NotFoundError(
                "File explorer download source was not found.",
                operation="file_explorer.download_archive.plan",
            ) from exception
        raise SecurityError(
            "File explorer download source failed secure traversal.",
            operation="file_explorer.download_archive.plan",
        ) from exception
    except OSError as exception:
        raise StateError(
            "File explorer download source could not be inspected.",
            operation="file_explorer.download_archive.plan",
            cause=exception,
        ) from exception
    if not identity.is_directory and not identity.is_regular_file:
        raise ValidationError(
            "Download archives support only regular files and directories.",
            operation="file_explorer.download_archive.plan",
        )
    return identity


def _require_member_limit(entries: list[DownloadArchiveEntry], maximum_members: int) -> None:
    if len(entries) <= maximum_members:
        return
    raise PayloadTooLargeError(
        "File explorer download archive exceeds the configured member limit.",
        details={"maximum_members": maximum_members, "member_count": len(entries)},
        operation="file_explorer.download_archive.plan",
    )

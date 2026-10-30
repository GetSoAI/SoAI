"""SoAI - Bounded live logs inventory and capture [backend/app/backup/logs_export_capture.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass
from socket import gethostname
from threading import Event

from app.backup.copy_no_symlinks.file_copy import (
    BoundedFileCapture,
    sync_copy_file_and_hash_no_symlinks,
)
from app.backup.logs_export_selection import (
    has_logs_export_text_content,
    is_compressed_logs_file,
    is_logs_export_file,
)
from core.archives.resource_limits import ArchivePlanningBudget, encoded_metadata_size
from core.archives.zip_creation import PortableZipPathIndex, calculate_zip_archive_upper_bound
from core.archives.zip_creation_models import ZipArchiveDirectory, ZipArchiveEntry, ZipArchivePlan
from core.backup.paths import get_backup_relative_logs_path
from core.concurrency.cancellation import check_cancellation_deadline
from core.concurrency.deadlines import MonotonicDeadline
from core.errors.exceptions import ConflictError, SecurityError
from core.files.directory_snapshot import read_directory_entries
from core.files.file_identity import FileIdentity
from core.files.managed_path_access import stat_managed_path
from core.files.path_policy import safe_join_relative_under_base_lexical
from core.filesystem.atomic_writes import atomic_write_text_content
from core.hardware.protocols_storage import StorageManagerProtocol
from core.hardware.reservation_claims import claim_reserved_write
from core.meta.version import __version__
from core.runtime.platform import get_runtime_platform
from core.serialization.json import serialize_json_compact_stable_strict
from core.timing.formatting import datetime_to_utc_iso, utc_now
from core.types.json import JSONDict, JSONValue

__all__ = ("LogsInventory", "inventory_logs", "capture_logs")


@dataclass(frozen=True, slots=True)
class LogsInventory:
    entries: tuple[ZipArchiveEntry, ...]
    directories: tuple[ZipArchiveDirectory, ...]
    payload_bytes: int


def inventory_logs(
    source_path: str,
    *,
    source_root: str,
    root_identity: FileIdentity,
    configured_log_paths: tuple[str, ...] = (),
    budget: ArchivePlanningBudget,
    cancellation_event: Event,
    deadline: MonotonicDeadline,
) -> LogsInventory:
    registry = PortableZipPathIndex()
    archive_root = registry.add(
        get_backup_relative_logs_path().replace(os.sep, "/"), is_directory=True
    )
    registry.add("diagnostics.json", is_directory=False)
    budget.add_member(
        metadata_bytes=encoded_metadata_size("diagnostics.json"), name="diagnostics.json"
    )
    entries: list[ZipArchiveEntry] = [ZipArchiveEntry(source_path, archive_root, root_identity)]
    budget.add_member(metadata_bytes=encoded_metadata_size(archive_root), name=archive_root)
    budget.add_materialized_entry(generated_metadata_bytes=0, name=archive_root)
    directories: list[ZipArchiveDirectory] = []
    pending = [entries[0]]
    while pending:
        check_cancellation_deadline(cancellation_event, deadline, operation="logs.export.inventory")
        directory = pending.pop()

        def admit_entry(
            name: str,
            identity: FileIdentity,
            archive_directory: str = directory.archive_path,
            source_directory: str = directory.source_path,
        ) -> None:
            archive_name = f"{archive_directory}{name}"
            metadata: JSONDict = {"path": archive_name, "size": identity.size, "sha256": "0" * 64}
            budget.add_member(metadata_bytes=encoded_metadata_size(archive_name), name=archive_name)
            budget.add_materialized_entry(
                generated_metadata_bytes=encoded_metadata_size(
                    serialize_json_compact_stable_strict(metadata)
                )
                + 1,
                name=archive_name,
            )
            if identity.is_regular_file and is_logs_export_file(
                os.path.join(source_directory, name), configured_log_paths
            ):
                budget.add_expanded_bytes(identity.size, archive_name)

        children = read_directory_entries(
            source_root,
            directory.source_path,
            expected_identity=directory.identity,
            admit_entry=admit_entry,
            cancellation_event=cancellation_event,
            deadline=deadline,
            stable_object_only=True,
            concurrent_leaf_read=True,
            operation="logs.export.inventory",
        )
        directories.append(
            ZipArchiveDirectory(
                directory.source_path,
                directory.identity,
                tuple(
                    name
                    for name, identity in children
                    if identity.is_directory
                    or is_logs_export_file(
                        os.path.join(directory.source_path, name), configured_log_paths
                    )
                ),
            )
        )
        child_directories: list[ZipArchiveEntry] = []
        for name, identity in children:
            check_cancellation_deadline(
                cancellation_event, deadline, operation="logs.export.inventory"
            )
            if identity.is_regular_file and not is_logs_export_file(
                os.path.join(directory.source_path, name), configured_log_paths
            ):
                continue
            relative = os.path.relpath(os.path.join(directory.source_path, name), source_path)
            child_path = safe_join_relative_under_base_lexical(
                base_path=source_path,
                relative_path=relative,
                description="Log capture source",
                error_cls=SecurityError,
            )
            archive_name = registry.add(
                f"{directory.archive_path}{name}", is_directory=identity.is_directory
            )
            entry = ZipArchiveEntry(child_path, archive_name, identity)
            entries.append(entry)
            if entry.is_directory:
                child_directories.append(entry)
        pending.extend(reversed(child_directories))
    return LogsInventory(tuple(entries), tuple(directories), budget.expanded_bytes)


def capture_logs(
    inventory: LogsInventory,
    *,
    source_root: str,
    snapshot_path: str,
    storage_manager: StorageManagerProtocol,
    budget: ArchivePlanningBudget,
    maximum_archive_bytes: int,
    cancellation_event: Event,
    deadline: MonotonicDeadline,
    capture_started: str,
    download_filename: str,
) -> ZipArchivePlan:
    entries: list[ZipArchiveEntry] = []
    records: list[JSONValue] = []
    excluded_paths: set[str] = set()
    with storage_manager.reserve_disk_space(
        path=snapshot_path,
        required_bytes=inventory.payload_bytes,
        operation="logs.export.capture",
        details={"required_bytes": inventory.payload_bytes},
    ) as reservation:
        _verify_source_directories(inventory, source_root, cancellation_event, deadline)
        for entry in sorted(inventory.entries, key=lambda entry: entry.archive_path):
            check_cancellation_deadline(
                cancellation_event, deadline, operation="logs.export.capture"
            )
            staged_path = safe_join_relative_under_base_lexical(
                base_path=snapshot_path,
                relative_path=entry.archive_path.rstrip("/"),
                description="Log capture staging",
                error_cls=SecurityError,
            )
            if entry.is_directory:
                os.makedirs(staged_path, mode=0o700, exist_ok=True)
                continue
            size, digest = sync_copy_file_and_hash_no_symlinks(
                entry.source_path,
                staged_path,
                deadline_monotonic=deadline.deadline_monotonic,
                write_reservation=reservation,
                capture=BoundedFileCapture(
                    source_root,
                    entry.identity,
                    entry.identity.size,
                    not is_compressed_logs_file(entry.source_path),
                    cancellation_event,
                ),
            )
            if not is_compressed_logs_file(entry.source_path) and not has_logs_export_text_content(
                snapshot_path, staged_path
            ):
                excluded_paths.add(entry.source_path)
                os.remove(staged_path)
                continue
            records.append({"path": entry.archive_path, "size": size, "sha256": digest})
            entries.append(
                ZipArchiveEntry(
                    staged_path,
                    entry.archive_path,
                    FileIdentity.from_stat(
                        stat_managed_path(snapshot_path, staged_path, file_descriptor_snapshot=True)
                    ),
                )
            )
        _verify_source_directories(inventory, source_root, cancellation_event, deadline)
        check_cancellation_deadline(
            cancellation_event, deadline, operation="logs.export.diagnostics"
        )
        platform = get_runtime_platform()
        diagnostics: JSONDict = {
            "soai_version": __version__,
            "machine_name": gethostname(),
            "platform": platform.os_name,
            "architecture": platform.architecture,
            "capture_started": capture_started,
            "capture_finished": datetime_to_utc_iso(utc_now()),
            "directory_capture": "Fixed membership observed once per directory; later entries are excluded. Only log filenames and configured main/audit logs, with their numeric/date rotations or compressed forms, are included. Plain files must have text content; unrelated files are excluded.",
            "file_capture": "Planned byte prefixes read while logging continues; compressed files must remain unchanged. Hashes describe captured bytes, not a simultaneous filesystem snapshot.",
            "files": [],
        }
        budget.add_local_metadata(
            encoded_metadata_size(serialize_json_compact_stable_strict(diagnostics)),
            "diagnostics.json",
        )
        diagnostics["files"] = records
        content = serialize_json_compact_stable_strict(diagnostics)
        check_cancellation_deadline(
            cancellation_event, deadline, operation="logs.export.diagnostics"
        )
        metadata_size = encoded_metadata_size(content)
        budget.add_expanded_bytes(metadata_size, "diagnostics.json")
        metadata_path = os.path.join(snapshot_path, "diagnostics.json")
        with storage_manager.reserve_disk_space(
            path=snapshot_path,
            required_bytes=metadata_size,
            operation="logs.export.diagnostics",
            details={"required_bytes": metadata_size},
        ) as metadata_reservation:
            with claim_reserved_write(metadata_reservation, size_bytes=metadata_size):
                atomic_write_text_content(
                    metadata_path,
                    content,
                    encoding="utf-8",
                    errors="strict",
                    file_mode=0o600,
                    fsync=True,
                )
        entries.append(
            ZipArchiveEntry(
                metadata_path,
                "diagnostics.json",
                FileIdentity.from_stat(
                    stat_managed_path(snapshot_path, metadata_path, file_descriptor_snapshot=True)
                ),
            )
        )
        directories: list[ZipArchiveDirectory] = []
        archive_root = get_backup_relative_logs_path().replace(os.sep, "/").rstrip("/")
        for directory in inventory.directories:
            relative = os.path.relpath(directory.source_path, inventory.entries[0].source_path)
            archive_name = (
                archive_root
                if relative == "."
                else f"{archive_root}/{relative.replace(os.sep, '/')}"
            )
            staged_path = safe_join_relative_under_base_lexical(
                base_path=snapshot_path,
                relative_path=archive_name,
                description="Log staging directory",
                error_cls=SecurityError,
            )
            identity = FileIdentity.from_stat(stat_managed_path(snapshot_path, staged_path))
            entries.append(ZipArchiveEntry(staged_path, f"{archive_name}/", identity))
            directories.append(
                ZipArchiveDirectory(
                    staged_path,
                    identity,
                    tuple(
                        name
                        for name in directory.child_names
                        if os.path.join(directory.source_path, name) not in excluded_paths
                    ),
                )
            )
        parent = os.path.dirname(archive_root)
        while parent:
            parent_path = os.path.join(snapshot_path, parent)
            child = archive_root[len(parent) + 1 :].split("/")[0]
            identity = FileIdentity.from_stat(stat_managed_path(snapshot_path, parent_path))
            directories.append(ZipArchiveDirectory(parent_path, identity, (child,)))
            parent = os.path.dirname(parent)
        directories.append(
            ZipArchiveDirectory(
                snapshot_path,
                FileIdentity.from_stat(stat_managed_path(snapshot_path, snapshot_path)),
                ("data", "diagnostics.json"),
            )
        )
        check_cancellation_deadline(cancellation_event, deadline, operation="logs.export.plan")
        required_bytes = calculate_zip_archive_upper_bound(
            [(entry.archive_path, entry.identity.size, entry.is_directory) for entry in entries],
            maximum_bytes=maximum_archive_bytes,
        )
        return ZipArchivePlan(
            tuple(sorted(entries, key=lambda entry: entry.archive_path)),
            tuple(directories),
            required_bytes,
            download_filename,
        )


def _verify_source_directories(
    inventory: LogsInventory,
    source_root: str,
    cancellation_event: Event,
    deadline: MonotonicDeadline,
) -> None:
    for directory in inventory.directories:
        check_cancellation_deadline(cancellation_event, deadline, operation="logs.export.capture")
        actual = FileIdentity.from_stat(stat_managed_path(source_root, directory.source_path))
        if not directory.identity.matches_file_object(actual):
            raise ConflictError("Log directory changed during capture.")

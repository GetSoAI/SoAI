"""SoAI - Atomic file operations for backup manifests and markers [backend/app/backup/archive_io.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, TypedDict

from app.backup.task_registry_reporting import update_progress_noncritical
from core.backup.types import BackupManifest
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.async_queries import async_path_exists
from core.filesystem.atomic_writes import atomic_write_text_content
from core.filesystem.open_files import open_text
from core.logging.protocols import LoggerProtocol
from core.logging.trace import get_logger
from core.progress.formatting import format_transfer_details
from core.serialization.json import normalize_for_json, serialize_json_pretty_sorted
from core.serialization.json_parsing import parse_json_dict, parse_json_value
from core.tasks.protocols import TaskRegistryProtocol
from core.timing.epoch import epoch_ms
from core.types.json_value import filter_json_mapping_strict

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "coerce_manifest_timestamp_ms",
    "emit_backup_progress",
    "get_soai_version",
    "read_first_backup_marker",
    "read_manifest_file",
    "serialize_manifest",
    "write_manifest",
    "write_manifest_content",
    "write_marker_file",
)

LOGGER_NAME = "SoAI.app.backup.archive_io"
OPERATION = "utils_backup.get_soai_version"
OPERATION_EMIT_PROGRESS = "app.backup.archive_io.emit_backup_progress"


class _BackupMarkerFields(TypedDict):
    timestamp_ms: int
    targets_completed: dict[str, bool]


def serialize_manifest(manifest: BackupManifest) -> str:
    return serialize_json_pretty_sorted(normalize_for_json(manifest))


def write_manifest_content(path: str, manifest_content: str) -> None:
    atomic_write_text_content(
        path,
        manifest_content,
        encoding="utf-8",
        errors="strict",
        parent_mode=0o700,
        fsync=True,
        file_mode=0o600,
        fsync_parent_directory=True,
    )


def write_manifest(path: str, manifest: BackupManifest) -> None:
    write_manifest_content(path, serialize_manifest(manifest))


def write_marker_file(
    path: str,
    *,
    targets_completed: dict[str, bool] | None = None,
) -> None:
    marker_data: _BackupMarkerFields = {
        "timestamp_ms": epoch_ms(),
        "targets_completed": targets_completed or {},
    }
    marker_value = serialize_json_pretty_sorted(
        filter_json_mapping_strict(
            marker_data,
            error_message="Backup marker must be JSON-compatible.",
        ),
    )
    atomic_write_text_content(
        path,
        marker_value,
        encoding="utf-8",
        errors="strict",
        parent_mode=0o700,
        fsync=True,
        file_mode=0o600,
        fsync_parent_directory=True,
    )


def read_first_backup_marker(path: str) -> JSONDict | None:
    if not os.path.isfile(path):
        return None
    try:
        with open_text(path, encoding="utf-8") as file_handle:
            content = file_handle.read().strip()
        parsed = parse_json_value(content)
        return parsed if isinstance(parsed, dict) else None
    except (OSError, ValidationError):
        return None


def _read_file_text(path: str) -> str:
    with open_text(path, encoding="utf-8") as file_handle:
        return file_handle.read()


async def get_soai_version(*, base_path: str, log: LoggerProtocol) -> str:
    version_file = os.path.join(base_path, "VERSION")
    if not await async_path_exists(version_file):
        return "unknown"
    try:
        content = await asyncio.to_thread(_read_file_text, version_file)
        return content.strip()
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            log,
            exception,
            message="Failed to read SoAI version file for backup manifest (non-critical).",
            operation=OPERATION,
            details={"version_file": version_file},
            level="debug",
        )
        return "unknown"


def read_manifest_file(manifest_path: str) -> JSONDict:
    with open_text(manifest_path, encoding="utf-8") as file_handle:
        return parse_json_dict(file_handle.read(), field="backup manifest")


def coerce_manifest_timestamp_ms(manifest: JSONDict, backup_path: str) -> int:
    if not isinstance(backup_path, str) or not backup_path.strip():
        raise ValidationError("backup_path is required.")
    timestamp_value = manifest.get("timestamp_ms")
    if isinstance(timestamp_value, int | float) and not isinstance(timestamp_value, bool):
        candidate = int(timestamp_value)
        now_ms = epoch_ms()
        if 0 < candidate <= now_ms + 86_400_000:
            return candidate
    stat_info = os.lstat(backup_path)
    return int(stat_info.st_mtime_ns // 1_000_000)


async def emit_backup_progress(
    *,
    task_registry: TaskRegistryProtocol,
    task_id: str | None,
    completed_count: int,
    total_count: int,
    target_name: str,
    bytes_processed: int = 0,
    total_bytes: int = 0,
    speed: float = 0.0,
    eta_seconds: float = 0.0,
) -> None:
    if task_id is None:
        return
    if total_count <= 0:
        return
    percent = min(99, max(1, int(completed_count / total_count * 99)))
    details = ""
    if bytes_processed > 0 or speed > 0:
        details = format_transfer_details(
            bytes_processed,
            total_bytes if total_bytes > 0 else None,
            speed=speed,
            eta_seconds=eta_seconds,
        )
    await update_progress_noncritical(
        registry=task_registry,
        task_id=task_id,
        progress_current=percent,
        log=get_logger(LOGGER_NAME),
        operation=OPERATION_EMIT_PROGRESS,
        message="Failed to update backup target progress.",
        status_message=f"Backed up {target_name}",
        details=details,
        level="debug",
    )

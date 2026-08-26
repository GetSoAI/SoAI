"""SoAI - Backup target execution helpers [backend/app/backup/backup_target_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.backup.archive_io import emit_backup_progress
from app.backup.size_format import format_size
from core.backup.types import BackupManifest
from core.errors.exceptions import ValidationError
from core.logging.protocols import StandardLogger
from core.logging.trace import get_logger
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from app.backup.internal_protocols import BackupServiceContext, BackupTargetParams
    from core.backup.types import BackupManifestEntry, BackupManifestFiles
    from core.types.json import JSONValue

__all__ = (
    "ManifestSections",
    "add_manifest_size",
    "coerce_size",
    "emit_target_progress",
    "extract_manifest_sections",
    "process_multi_file_results",
    "process_single_file_result",
    "record_backed_up_file",
)

LOGGER_NAME = "SoAI.app.backup.backup_target_execution"


@dataclass(slots=True)
class ManifestSections:
    files_section: BackupManifestFiles
    targets_enabled: dict[str, bool]
    targets_completed: dict[str, bool]


def extract_manifest_sections(manifest: BackupManifest) -> ManifestSections:
    files_section = manifest.get("files")
    targets_enabled = manifest.get("targets_enabled")
    targets_completed = manifest.get("targets_completed")
    if not isinstance(files_section, dict):
        raise ValidationError("Backup manifest missing files section.")
    if not isinstance(targets_enabled, dict):
        raise ValidationError("Backup manifest missing targets_enabled section.")
    if not isinstance(targets_completed, dict):
        raise ValidationError("Backup manifest missing targets_completed section.")
    return ManifestSections(
        files_section=files_section,
        targets_enabled=targets_enabled,
        targets_completed=targets_completed,
    )


def coerce_size(value: JSONValue) -> int:
    if not is_strict_int(value) or value < 0:
        raise ValidationError("size must be a non-negative integer.")
    return value


def add_manifest_size(manifest: BackupManifest, size_value: int) -> None:
    total_size = coerce_size(manifest.get("total_size_bytes"))
    manifest["total_size_bytes"] = total_size + size_value


def record_backed_up_file(
    backed_up_targets: dict[str, list[tuple[str, int]]],
    target_name: str,
    file_path: str,
    size_value: int,
) -> None:
    entries = backed_up_targets.get(target_name)
    if entries is None:
        entries = []
        backed_up_targets[target_name] = entries
    entries.append((file_path, size_value))


async def emit_target_progress(
    context: BackupServiceContext,
    params: BackupTargetParams,
    target_name: str,
    completed_count: int,
) -> None:
    await emit_backup_progress(
        task_registry=context.runtime_dependencies.task_registry,
        task_id=params.task_id,
        completed_count=completed_count,
        total_count=params.total_enabled_targets,
        target_name=target_name,
    )


def process_single_file_result(
    sections: ManifestSections,
    manifest: BackupManifest,
    backed_up_targets: dict[str, list[tuple[str, int]]],
    target_name: str,
    file_key: str,
    result: BackupManifestEntry | None,
    display_path: str | None = None,
    log: StandardLogger | None = None,
) -> bool:
    logger = get_logger(LOGGER_NAME)
    effective_log = log or logger
    if result is None:
        sections.targets_completed[target_name] = False
        effective_log.warning("%s: backup failed", target_name)
        return False
    sections.files_section[file_key] = result
    size_value = coerce_size(result.get("size"))
    add_manifest_size(manifest, size_value)
    record_backed_up_file(
        backed_up_targets,
        target_name,
        display_path or file_key,
        size_value,
    )
    sections.targets_completed[target_name] = True
    effective_log.debug(
        "%s: backed up %s (%s)",
        target_name,
        file_key,
        format_size(size_value),
    )
    return True


def process_multi_file_results(
    sections: ManifestSections,
    manifest: BackupManifest,
    backed_up_targets: dict[str, list[tuple[str, int]]],
    target_name: str,
    results: BackupManifestFiles,
    success: bool,
    empty_message: str,
    log: StandardLogger | None = None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    effective_log = log or logger
    for rel_path, result in results.items():
        sections.files_section[rel_path] = result
        size_value = coerce_size(result.get("size"))
        add_manifest_size(manifest, size_value)
        record_backed_up_file(backed_up_targets, target_name, rel_path, size_value)
        effective_log.debug(
            "%s: backed up %s (%s)",
            target_name,
            rel_path,
            format_size(size_value),
        )
    sections.targets_completed[target_name] = success
    if not results:
        effective_log.debug("%s: %s", target_name, empty_message)

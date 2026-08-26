"""SoAI - Backup creation workflow with retention and cleanup [backend/app/backup/backup_creation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import time

from app.backup.archive_io import get_soai_version
from app.backup.backup_completion_logging import log_backup_completion_summary
from app.backup.backup_manifest_write import write_manifest_with_disk_reservation
from app.backup.backup_removal import safe_cleanup_path
from app.backup.backup_retention import apply_retention_policy
from app.backup.backup_size_estimation import estimate_backup_required_bytes
from app.backup.backup_slots import create_backup_slot
from app.backup.backup_stale_cleanup import cleanup_stale_partial_backups
from app.backup.backup_target_execution import coerce_size
from app.backup.backup_target_paths import (
    all_enabled_targets_completed,
    get_base_path,
    get_enabled_backup_targets,
)
from app.backup.backup_targets import (
    backup_config_target,
    backup_database_target,
    backup_encryption_key_target,
    backup_gpu_settings_target,
    backup_plugin_configs_target,
)
from app.backup.backup_targets_user import backup_logs_target, backup_user_data_target
from app.backup.backup_timeout_settings import get_stale_part_threshold_seconds
from app.backup.copy_no_symlinks.permissions import ensure_backup_directory_permissions
from app.backup.internal_protocols import BackupServiceContext, BackupTargetParams
from app.backup.licensing_recovery import build_licensing_recovery_summary
from app.backup.size_format import format_size
from core.backup.types import BackupCreateResult, BackupManifest, BackupManifestFiles
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.async_queries import async_isdir
from core.hardware.protocols_storage import DiskSpaceReservationLeaseProtocol
from core.logging.protocols import LoggerProtocol
from core.logging.trace import get_logger
from core.runtime.platform import get_runtime_platform
from core.timing.epoch import epoch_ms
from core.timing.formatting import utc_now_iso

__all__ = (
    "cleanup_stale_parts",
    "create_backup_internal",
)

LOGGER_NAME = "SoAI.app.backup.backup_creation"
OPERATION = "application_backup.create_backup_internal"


async def _reserve_backup_disk_space(
    self: BackupServiceContext,
    *,
    enabled_targets_map: dict[str, bool],
    logger: LoggerProtocol,
) -> tuple[DiskSpaceReservationLeaseProtocol, int]:
    estimated_required_bytes = await estimate_backup_required_bytes(
        self.config,
        self.files,
        enabled_targets_map,
    )
    storage_manager = self.runtime_dependencies.storage_manager
    reservation = storage_manager.reserve_disk_space(
        path=self.backups_path,
        required_bytes=estimated_required_bytes,
        operation="application_backup.create_backup",
        details={
            "purpose": "backup_destination",
            "backup_path": self.backups_path,
            "estimated_required_bytes": estimated_required_bytes,
            "enabled_targets": [name for name, enabled in enabled_targets_map.items() if enabled],
        },
    )
    logger.debug(
        "Estimated backup requirements: %s",
        format_size(estimated_required_bytes),
    )
    return reservation, estimated_required_bytes


async def _build_backup_manifest(
    self: BackupServiceContext,
    *,
    backup_id: str,
    files_section: BackupManifestFiles,
    targets_enabled: dict[str, bool],
    targets_completed: dict[str, bool],
    logger: LoggerProtocol,
) -> BackupManifest:
    return {
        "backup_id": backup_id,
        "timestamp_ms": epoch_ms(),
        "timestamp_iso": utc_now_iso(),
        "soai_version": await get_soai_version(
            base_path=get_base_path(self.config),
            log=logger,
        ),
        "files": files_section,
        "total_size_bytes": 0,
        "sqlite_integrity_ok": False,
        "targets_enabled": targets_enabled,
        "targets_completed": targets_completed,
        "licensing_recovery": {
            "state": "incomplete",
            "database": {"present": False, "sha256": None},
            "encryption_key": {"present": False, "sha256": None},
        },
    }


async def _run_backup_targets(self: BackupServiceContext, params: BackupTargetParams) -> None:
    completed_target_count = 0
    completed_target_count = await backup_database_target(self, params, completed_target_count)
    completed_target_count = await backup_config_target(self, params, completed_target_count)
    completed_target_count = await backup_encryption_key_target(
        self,
        params,
        completed_target_count,
    )
    completed_target_count = await backup_plugin_configs_target(
        self,
        params,
        completed_target_count,
    )
    completed_target_count = await backup_gpu_settings_target(self, params, completed_target_count)
    completed_target_count = await backup_user_data_target(self, params, completed_target_count)
    completed_target_count = await backup_logs_target(self, params, completed_target_count)


async def _apply_retention_policy_noncritical(
    self: BackupServiceContext,
    *,
    logger: LoggerProtocol,
) -> None:
    try:
        await apply_retention_policy(
            backups_path=self.backups_path,
            config=self.config,
            log=logger,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Retention policy failed (backup still created)",
            operation=OPERATION,
        )


async def cleanup_stale_parts(self: BackupServiceContext, *, backups_path: str) -> None:
    logger = get_logger(LOGGER_NAME)
    if not backups_path or not await async_isdir(backups_path):
        return
    async with self.backup_lock:
        stale_threshold_seconds = get_stale_part_threshold_seconds(self.config)
        cleaned = await asyncio.to_thread(
            cleanup_stale_partial_backups,
            backups_path=backups_path,
            stale_threshold_seconds=stale_threshold_seconds,
        )
        if cleaned:
            logger.info("Cleaned up %s stale partial backup(s).", cleaned)


async def create_backup_internal(
    self: BackupServiceContext,
    *,
    task_id: str | None = None,
) -> BackupCreateResult:
    logger = get_logger(LOGGER_NAME)
    if not self.backups_path:
        raise StateError("Backups path is not configured.")
    enabled_targets_map = get_enabled_backup_targets(self.config)
    if not any(enabled_targets_map.values()):
        raise ValidationError("No backup targets are enabled.")
    backup_reservation, _estimated_backup_bytes = await _reserve_backup_disk_space(
        self,
        enabled_targets_map=enabled_targets_map,
        logger=logger,
    )
    final_path_target, part_path = await asyncio.to_thread(create_backup_slot, self.backups_path)
    backup_id = os.path.basename(final_path_target)
    start_time = time.monotonic()
    logger.info("Creating backup: %s", backup_id)
    final_path: str | None = None
    backup_success = False
    try:
        logger.debug("Created staging directory: %s", part_path)
        files_section: BackupManifestFiles = {}
        targets_enabled: dict[str, bool] = {}
        targets_completed: dict[str, bool] = {}
        manifest = await _build_backup_manifest(
            self,
            backup_id=backup_id,
            files_section=files_section,
            targets_enabled=targets_enabled,
            targets_completed=targets_completed,
            logger=logger,
        )
        enabled_targets = [name for name, enabled in enabled_targets_map.items() if enabled]
        disabled_targets = [name for name, enabled in enabled_targets_map.items() if not enabled]
        logger.debug("Enabled targets: %s", enabled_targets)
        if disabled_targets:
            logger.debug("Disabled targets: %s", disabled_targets)
        backed_up_targets: dict[str, list[tuple[str, int]]] = {}
        params = BackupTargetParams(
            backup_dir=part_path,
            manifest=manifest,
            backed_up_targets=backed_up_targets,
            enabled_targets_map=enabled_targets_map,
            disk_reservation=backup_reservation,
            total_enabled_targets=len(enabled_targets),
            task_id=task_id,
        )
        await _run_backup_targets(self, params)
        manifest["licensing_recovery"] = await asyncio.to_thread(
            build_licensing_recovery_summary,
            part_path,
            files_section,
            database_target_completed=(
                not enabled_targets_map.get("DATABASE", False)
                or targets_completed.get("DATABASE", False)
            ),
        )
        if not files_section:
            raise StateError(
                "Backup produced no restorable files.",
                details={
                    "backup_id": backup_id,
                    "enabled_targets": enabled_targets,
                },
                operation="application_backup.create_backup",
            )
        manifest_path = os.path.join(part_path, "manifest.json")
        await write_manifest_with_disk_reservation(
            storage_manager=self.runtime_dependencies.storage_manager,
            manifest_path=manifest_path,
            manifest=manifest,
            backup_id=backup_id,
        )
        logger.debug("Wrote manifest to %s", manifest_path)
        await asyncio.to_thread(os.rename, part_path, final_path_target)
        final_path = final_path_target
        elapsed = time.monotonic() - start_time
        total_size = coerce_size(manifest.get("total_size_bytes"))
        file_count = len(files_section)
        log_backup_completion_summary(
            logger=logger,
            backup_id=backup_id,
            elapsed_seconds=elapsed,
            total_size_bytes=total_size,
            file_count=file_count,
            backed_up_targets=backed_up_targets,
        )
        backup_success = (
            all_enabled_targets_completed(
                targets_enabled,
                targets_completed,
            )
            and manifest["licensing_recovery"]["state"] != "incomplete"
        )
        if backup_success:
            timestamp_value = manifest.get("timestamp_ms")
            if isinstance(timestamp_value, int | float) and not isinstance(timestamp_value, bool):
                self.record_backup_timestamp_ms(int(timestamp_value))
    except asyncio.CancelledError:
        await safe_cleanup_path(
            part_path,
            operation="application_backup.create_backup_internal",
            is_directory=True,
            log=logger,
        )
        logger.info("Backup was cancelled.")
        raise
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation="application_backup.create_backup_internal",
        )
        await safe_cleanup_path(
            part_path,
            operation="application_backup.create_backup_internal",
            is_directory=True,
            log=logger,
        )
        raise coerced from exception
    finally:
        backup_reservation.release()
    await _apply_retention_policy_noncritical(self, logger=logger)
    if final_path is None:
        raise StateError("Backup path was not finalized.")
    runtime_platform = get_runtime_platform()
    await ensure_backup_directory_permissions(
        final_path,
        is_windows=runtime_platform.is_windows,
    )
    result: BackupCreateResult = {
        "backup_id": os.path.basename(final_path),
        "backup_path": final_path,
        "manifest": manifest,
        "success": backup_success,
        "targets_enabled": dict(targets_enabled),
        "targets_completed": dict(targets_completed),
    }
    return result

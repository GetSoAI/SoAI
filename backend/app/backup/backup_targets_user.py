"""SoAI - Backup target handlers for user data and logs [backend/app/backup/backup_targets_user.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from app.backup.backup_target_execution import (
    emit_target_progress,
    extract_manifest_sections,
    process_multi_file_results,
)
from app.backup.backup_target_paths import get_files_storage_path, get_wallpaper_path
from app.backup.backup_target_paths_extra import get_logs_path
from app.backup.internal_protocols import BackupServiceContext, BackupTargetParams
from app.backup.logs_backup import backup_logs
from app.backup.user_data_backup import backup_user_data
from core.logging.trace import get_logger

__all__ = (
    "backup_logs_target",
    "backup_user_data_target",
)

LOGGER_NAME = "SoAI.app.backup.backup_targets_user"


async def backup_user_data_target(
    context: BackupServiceContext,
    params: BackupTargetParams,
    completed_target_count: int,
) -> int:
    logger = get_logger(LOGGER_NAME)
    sections = extract_manifest_sections(params.manifest)

    if not params.enabled_targets_map.get("USER_DATA"):
        sections.targets_enabled["USER_DATA"] = False
        return completed_target_count

    sections.targets_enabled["USER_DATA"] = True
    logger.debug("Backing up USER_DATA target...")
    user_data_results, user_data_success = await backup_user_data(
        wallpaper_path=get_wallpaper_path(context.config, context.files),
        files_path=get_files_storage_path(context.config, context.files),
        dest_dir=params.backup_dir,
        log=logger,
        disk_reservation=params.disk_reservation,
    )
    process_multi_file_results(
        sections=sections,
        manifest=params.manifest,
        backed_up_targets=params.backed_up_targets,
        target_name="USER_DATA",
        results=user_data_results,
        success=user_data_success,
        empty_message="no user data directories found",
        log=logger,
    )

    completed_target_count += 1
    await emit_target_progress(context, params, "USER_DATA", completed_target_count)
    return completed_target_count


async def backup_logs_target(
    context: BackupServiceContext,
    params: BackupTargetParams,
    completed_target_count: int,
) -> int:
    logger = get_logger(LOGGER_NAME)
    sections = extract_manifest_sections(params.manifest)

    if not params.enabled_targets_map.get("LOGS"):
        sections.targets_enabled["LOGS"] = False
        return completed_target_count

    sections.targets_enabled["LOGS"] = True
    logger.debug("Backing up LOGS target...")
    logs_results, logs_success = await backup_logs(
        logs_path=get_logs_path(context.config, context.files),
        dest_dir=params.backup_dir,
        log=logger,
        disk_reservation=params.disk_reservation,
    )
    process_multi_file_results(
        sections=sections,
        manifest=params.manifest,
        backed_up_targets=params.backed_up_targets,
        target_name="LOGS",
        results=logs_results,
        success=logs_success,
        empty_message="no logs directory found",
        log=logger,
    )

    completed_target_count += 1
    await emit_target_progress(context, params, "LOGS", completed_target_count)
    return completed_target_count

"""SoAI - Backup target execution for database config and settings [backend/app/backup/backup_targets.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from app.backup.backup_target_execution import (
    add_manifest_size,
    coerce_size,
    emit_target_progress,
    extract_manifest_sections,
    process_multi_file_results,
    process_single_file_result,
)
from app.backup.backup_target_paths import (
    get_db_path,
    get_encryption_key_path,
    get_gpu_settings_path,
)
from app.backup.backup_target_paths_extra import (
    get_core_config_path,
    get_plugins_path,
)
from app.backup.backup_timeout_settings import (
    get_config_lock_timeout_seconds,
    get_plugin_lock_timeout_seconds,
    get_sqlite_backup_timeout_seconds,
    get_sqlite_backup_timeout_seconds_per_gib,
)
from app.backup.config_backup import backup_config_file
from app.backup.data_file_backup import backup_single_file_to_data_dir
from app.backup.internal_protocols import BackupServiceContext, BackupTargetParams
from app.backup.plugin_config_backup import backup_plugin_configs
from app.backup.size_format import format_size
from app.backup.sqlite_backup_execution import backup_sqlite_database
from app.backup.task_result_validation import require_backup_bool_field
from core.backup.paths import (
    get_backup_relative_config_path,
    get_backup_relative_database_path,
    get_backup_relative_encryption_key_path,
    get_backup_relative_gpu_settings_path,
)
from core.filesystem.async_queries import async_path_exists
from core.logging.trace import get_logger

__all__ = (
    "backup_config_target",
    "backup_database_target",
    "backup_encryption_key_target",
    "backup_gpu_settings_target",
    "backup_plugin_configs_target",
)

LOGGER_NAME = "SoAI.app.backup.backup_targets"


async def backup_database_target(
    context: BackupServiceContext,
    params: BackupTargetParams,
    completed_target_count: int,
) -> int:
    logger = get_logger(LOGGER_NAME)
    sections = extract_manifest_sections(params.manifest)

    if not params.enabled_targets_map.get("DATABASE"):
        sections.targets_enabled["DATABASE"] = False
        return completed_target_count

    sections.targets_enabled["DATABASE"] = True
    logger.debug("Backing up DATABASE target...")
    db_source_path = get_db_path(context.config, context.files)

    if not await async_path_exists(db_source_path):
        sections.targets_completed["DATABASE"] = True
        logger.debug("DATABASE: database file not present; skipping")
    else:
        db_result = await backup_sqlite_database(
            db_path=db_source_path,
            dest_dir=params.backup_dir,
            sqlite_backup_timeout_seconds=get_sqlite_backup_timeout_seconds(context.config),
            sqlite_backup_timeout_seconds_per_gib=get_sqlite_backup_timeout_seconds_per_gib(
                context.config,
            ),
            log=logger,
            disk_reservation=params.disk_reservation,
            task_registry=context.runtime_dependencies.task_registry,
            task_id=params.task_id,
        )
        if db_result:
            sections.files_section[get_backup_relative_database_path()] = db_result
            sqlite_integrity_ok = require_backup_bool_field(
                db_result,
                field_name="integrity_ok",
                error_message="DATABASE backup result integrity_ok must be a bool.",
            )
            params.manifest["sqlite_integrity_ok"] = sqlite_integrity_ok
            size_value = coerce_size(db_result.get("size"))
            add_manifest_size(params.manifest, size_value)
            integrity_status = "integrity=ok" if sqlite_integrity_ok else "integrity=failed"
            if not sqlite_integrity_ok:
                logger.warning(
                    "DATABASE: sqlite integrity_check failed; marking backup as incomplete",
                )
            database_entries = params.backed_up_targets.get("DATABASE")
            if database_entries is None:
                database_entries = []
                params.backed_up_targets["DATABASE"] = database_entries
            database_entries.append(
                (f"{get_backup_relative_database_path()} ({integrity_status})", size_value),
            )
            sections.targets_completed["DATABASE"] = sqlite_integrity_ok
            logger.debug(
                "DATABASE: backed up %s (%s)",
                get_backup_relative_database_path(),
                format_size(size_value),
            )
        else:
            sections.targets_completed["DATABASE"] = False
            logger.warning("DATABASE: backup failed")

    completed_target_count += 1
    await emit_target_progress(context, params, "DATABASE", completed_target_count)
    return completed_target_count


async def backup_config_target(
    context: BackupServiceContext,
    params: BackupTargetParams,
    completed_target_count: int,
) -> int:
    logger = get_logger(LOGGER_NAME)
    sections = extract_manifest_sections(params.manifest)

    if not params.enabled_targets_map.get("CONFIG"):
        sections.targets_enabled["CONFIG"] = False
        return completed_target_count

    sections.targets_enabled["CONFIG"] = True
    logger.debug("Backing up CONFIG target...")
    config_source_path = get_core_config_path(context.config, context.files)

    if not await async_path_exists(config_source_path):
        sections.targets_completed["CONFIG"] = True
        logger.debug("CONFIG: config.yaml not present; skipping")
    else:
        lock_path = context.config_manager.get_lock_path(config_source_path)
        config_result = await backup_config_file(
            config_path=config_source_path,
            dest_dir=params.backup_dir,
            lock_path=lock_path,
            lock_timeout_seconds=get_config_lock_timeout_seconds(context.config),
            disk_reservation=params.disk_reservation,
        )
        process_single_file_result(
            sections=sections,
            manifest=params.manifest,
            backed_up_targets=params.backed_up_targets,
            target_name="CONFIG",
            file_key=get_backup_relative_config_path(),
            result=config_result,
            log=logger,
        )

    completed_target_count += 1
    await emit_target_progress(context, params, "CONFIG", completed_target_count)
    return completed_target_count


async def backup_encryption_key_target(
    context: BackupServiceContext,
    params: BackupTargetParams,
    completed_target_count: int,
) -> int:
    logger = get_logger(LOGGER_NAME)
    sections = extract_manifest_sections(params.manifest)

    if not params.enabled_targets_map.get("ENCRYPTION_KEY"):
        sections.targets_enabled["ENCRYPTION_KEY"] = False
        return completed_target_count

    sections.targets_enabled["ENCRYPTION_KEY"] = True
    logger.debug("Backing up ENCRYPTION_KEY target...")
    encryption_key_source_path = get_encryption_key_path(context.config, context.files)

    if not await async_path_exists(encryption_key_source_path):
        sections.targets_completed["ENCRYPTION_KEY"] = True
        logger.debug("ENCRYPTION_KEY: key not present; skipping")
    else:
        key_result = await backup_single_file_to_data_dir(
            source_path=encryption_key_source_path,
            dest_dir=params.backup_dir,
            dest_filename="secret.key",
            disk_reservation=params.disk_reservation,
            log_missing=True,
            missing_log_message="Encryption key not found: %s",
        )
        process_single_file_result(
            sections=sections,
            manifest=params.manifest,
            backed_up_targets=params.backed_up_targets,
            target_name="ENCRYPTION_KEY",
            file_key=get_backup_relative_encryption_key_path(),
            result=key_result,
            log=logger,
        )

    completed_target_count += 1
    await emit_target_progress(context, params, "ENCRYPTION_KEY", completed_target_count)
    return completed_target_count


async def backup_plugin_configs_target(
    context: BackupServiceContext,
    params: BackupTargetParams,
    completed_target_count: int,
) -> int:
    logger = get_logger(LOGGER_NAME)
    sections = extract_manifest_sections(params.manifest)

    if not params.enabled_targets_map.get("PLUGIN_CONFIGS"):
        sections.targets_enabled["PLUGIN_CONFIGS"] = False
        return completed_target_count

    sections.targets_enabled["PLUGIN_CONFIGS"] = True
    logger.debug("Backing up PLUGIN_CONFIGS target...")
    plugin_results, plugin_success = await backup_plugin_configs(
        plugins_path=get_plugins_path(context.config, context.files),
        dest_dir=params.backup_dir,
        config_manager=context.config_manager,
        lock_timeout_seconds=get_plugin_lock_timeout_seconds(context.config),
        disk_reservation=params.disk_reservation,
    )
    process_multi_file_results(
        sections=sections,
        manifest=params.manifest,
        backed_up_targets=params.backed_up_targets,
        target_name="PLUGIN_CONFIGS",
        results=plugin_results,
        success=plugin_success,
        empty_message="no plugin config files found",
        log=logger,
    )

    completed_target_count += 1
    await emit_target_progress(context, params, "PLUGIN_CONFIGS", completed_target_count)
    return completed_target_count


async def backup_gpu_settings_target(
    context: BackupServiceContext,
    params: BackupTargetParams,
    completed_target_count: int,
) -> int:
    logger = get_logger(LOGGER_NAME)
    sections = extract_manifest_sections(params.manifest)

    if not params.enabled_targets_map.get("GPU_SETTINGS"):
        sections.targets_enabled["GPU_SETTINGS"] = False
        return completed_target_count

    sections.targets_enabled["GPU_SETTINGS"] = True
    logger.debug("Backing up GPU_SETTINGS target...")
    gpu_source_path = get_gpu_settings_path(context.config, context.files)

    if not await async_path_exists(gpu_source_path):
        sections.targets_completed["GPU_SETTINGS"] = True
        logger.debug("GPU_SETTINGS: no GPU settings file present; skipping")
    else:
        gpu_result = await backup_single_file_to_data_dir(
            source_path=gpu_source_path,
            dest_dir=params.backup_dir,
            dest_filename="gpu/gpu_settings_slots.json",
            disk_reservation=params.disk_reservation,
        )
        process_single_file_result(
            sections=sections,
            manifest=params.manifest,
            backed_up_targets=params.backed_up_targets,
            target_name="GPU_SETTINGS",
            file_key=get_backup_relative_gpu_settings_path(),
            result=gpu_result,
            log=logger,
        )

    completed_target_count += 1
    await emit_target_progress(context, params, "GPU_SETTINGS", completed_target_count)
    return completed_target_count

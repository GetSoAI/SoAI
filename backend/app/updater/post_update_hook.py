"""SoAI - Post-update upgrade hook (configuration and DB migrations) [backend/app/updater/post_update_hook.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
import os
import sqlite3

from app.cli.offline_mode import resolve_config_path
from app.config.schema_disk_reconciliation import reconcile_config_payload_on_disk
from app.updater.config_timeout_default_upgrade import upgrade_selected_timeout_defaults
from app.updater.config_timeout_default_upgrade_state import (
    begin_timeout_default_upgrade,
    mark_timeout_default_upgrade_completed,
    timeout_default_upgrade_completed,
)
from app.updater.software_update.activation_state import find_pending_update_activation
from app.updater.software_update.install_transaction_state import (
    SUCCESS_COMPLETE_MARKER,
    marker_path,
)
from core.config.file_permissions import (
    runtime_config_atomic_file_mode,
    secure_runtime_config_paths,
)
from core.config.runtime_config import Config
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError, StateError
from core.filesystem.atomic_writes import atomic_write_text_content
from core.filesystem.open_files import open_text
from core.logging.configuration_constants import DEFAULT_LOG_DATE_FORMAT
from core.logging.formatters import UnifiedFormatter
from core.logging.trace import get_logger
from core.tasks.type_catalog import TaskTypeCatalog, build_base_task_catalog
from database.migrations.runtime import upgrade_database_path

__all__ = ("main",)

OPERATION_POST_UPDATE_HOOK = "app.updater.post_update_hook"
OPERATION_POST_UPDATE_HOOK_RESTORE_CONFIG = "app.updater.post_update_hook.restore_config_backup"
LOGGER_NAME = "SoAI.app.updater.post_update_hook"


def _restore_config_backup(
    *,
    config_path: str,
    backup_path: str,
    logger: logging.Logger,
) -> None:
    if not os.path.isfile(backup_path):
        return
    secure_runtime_config_paths(config_path, backup_path)
    logger.warning("Restoring config.yaml after failed update hook: %s", config_path)
    with open_text(backup_path, encoding="utf-8", errors="strict") as handle:
        backup_content = handle.read()
    atomic_write_text_content(
        config_path,
        backup_content,
        encoding="utf-8",
        errors="strict",
        fsync=True,
        file_mode=runtime_config_atomic_file_mode(),
    )
    secure_runtime_config_paths(config_path, backup_path)


def _configure_logging() -> None:
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        UnifiedFormatter(
            "%(asctime)s - [SoAI/PostUpdateHook] - %(levelname)s - %(message)s",
            DEFAULT_LOG_DATE_FORMAT,
            use_colors=False,
        ),
    )
    logging.basicConfig(
        level=logging.INFO,
        handlers=[console_handler],
    )


def main(task_catalog: TaskTypeCatalog) -> int:
    _configure_logging()
    logger = get_logger(LOGGER_NAME)
    repo_root = os.path.abspath(os.getcwd())
    config_path = ""
    config_backup_path: str | None = None
    migrations_committed = False

    try:
        config_path = resolve_config_path(repo_root)
        prepared_update = find_pending_update_activation(repo_root, include_preparation=True)
        if prepared_update is not None and os.path.normcase(config_path) != os.path.normcase(
            prepared_update.config_path
        ):
            raise StateError("Update hook configuration does not match protected update state.")
        timeout_defaults_already_upgraded = timeout_default_upgrade_completed(config_path)
        if not timeout_defaults_already_upgraded:
            begin_timeout_default_upgrade(config_path)
        reconciliation = reconcile_config_payload_on_disk(
            config_path=config_path,
            logger=logger,
            create_missing=True,
            migration_message="Config migrations applied during update hook: %s",
            drift_message="Config schema drift detected during update hook; rewriting config.yaml.",
            changed_paths_message="Updated config paths: %s",
            payload_transform=(
                None if timeout_defaults_already_upgraded else upgrade_selected_timeout_defaults
            ),
        )
        config_dict = reconciliation.data
        config_backup_path = reconciliation.backup_path
        config_instance = Config(config_dict, main_app_base_dir=repo_root)
        db_path = config_instance.get_str("DATA.DATABASE.PATHS.SYSTEM_DB")
        if not db_path:
            raise ValueError("DATA.DATABASE.PATHS.SYSTEM_DB is required.")
        locks_dir = config_instance.get_str("SYSTEM.PATHS.LOCKS")
        if not locks_dir:
            raise ValueError("SYSTEM.PATHS.LOCKS is required.")
        lock_path = os.path.join(locks_dir, "soai.db_upgrade.lock")

        logger.info("Running database upgrade hook (db=%s)...", db_path)
        from_version, to_version = upgrade_database_path(
            db_path=db_path,
            lock_path=lock_path,
            logger=logger,
            task_catalog=task_catalog,
        )
        migrations_committed = True
        if from_version != to_version:
            logger.info("Database upgraded successfully: v%s -> v%s", from_version, to_version)
        else:
            logger.info("Database is already up-to-date (v%s).", to_version)
        if not timeout_defaults_already_upgraded and (
            prepared_update is None
            or os.path.isfile(
                marker_path(prepared_update.paths.transaction_path, SUCCESS_COMPLETE_MARKER)
            )
        ):
            mark_timeout_default_upgrade_completed(config_path)
        return 0
    except (OSError, ValueError, TypeError, RuntimeError, sqlite3.Error, SoAIError) as exception:
        try:
            if not migrations_committed and config_path and isinstance(config_backup_path, str):
                _restore_config_backup(
                    config_path=config_path,
                    backup_path=config_backup_path,
                    logger=logger,
                )
        except (
            OSError,
            ValueError,
            TypeError,
            RuntimeError,
            sqlite3.Error,
            SoAIError,
        ) as restore_exception:
            log_exception(
                logger,
                restore_exception,
                message="Failed to restore config.yaml after failed update hook.",
                operation=OPERATION_POST_UPDATE_HOOK_RESTORE_CONFIG,
                level="error",
            )
        log_exception(
            logger,
            exception,
            message="Post-update hook failed.",
            operation=OPERATION_POST_UPDATE_HOOK,
            level="error",
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main(build_base_task_catalog()))

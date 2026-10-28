"""SoAI - Post-update upgrade hook (configuration and DB migrations) [backend/app/updater/post_update_hook.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
import os
import sqlite3
from collections.abc import Callable
from contextlib import ExitStack
from functools import partial
from typing import TYPE_CHECKING

from app.cli.offline_mode import resolve_config_path
from app.config.schema_disk_reconciliation import (
    ConfigPayloadTransformResult,
    reconcile_config_payload_on_disk,
)
from app.updater.config_timeout_default_upgrade import upgrade_selected_timeout_defaults
from app.updater.config_upgrade_state import (
    SavedConfigUpgrade,
    begin_config_upgrade,
    config_upgrade_completed,
    mark_config_upgrade_completed,
)
from app.updater.plugin_backend_limit_upgrade import refresh_plugin_backend_limits
from app.updater.plugin_backend_limit_upgrade_ownership import (
    guard_plugin_upgrade_ownership,
    retained_plugin_sources,
)
from app.updater.software_update.activation_state import find_pending_update_activation
from app.updater.software_update.install_transaction_persisted_state import (
    resolve_update_plugins_path,
)
from app.updater.software_update.install_transaction_state import (
    SUCCESS_COMPLETE_MARKER,
    marker_path,
)
from app.updater.windows_service_upgrade import (
    migrate_windows_service_state,
    upgrade_windows_service_paths,
)
from core.bootstrap.disk_reservation_provider import create_bootstrap_disk_reservation_provider
from core.config.file_permissions import (
    runtime_config_atomic_file_mode,
    secure_runtime_config_paths,
)
from core.config.remote_storage import find_remote_storage_settings
from core.config.runtime_config import Config
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError, StateError
from core.filesystem.atomic_writes import atomic_write_text_content
from core.filesystem.open_files import open_text
from core.logging.configuration_constants import DEFAULT_LOG_DATE_FORMAT
from core.logging.formatters import UnifiedFormatter
from core.logging.trace import get_logger
from core.meta.version import __version__
from core.platform.os import is_windows
from core.tasks.type_catalog import TaskTypeCatalog, build_base_task_catalog
from database.migrations.runtime import upgrade_database_path

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict

    type ConfigUpgradeTransform = Callable[[ConfigDict], ConfigPayloadTransformResult]

__all__ = ("main",)

OPERATION_POST_UPDATE_HOOK = "app.updater.post_update_hook"
OPERATION_POST_UPDATE_HOOK_RESTORE_CONFIG = "app.updater.post_update_hook.restore_config_backup"
LOGGER_NAME = "SoAI.app.updater.post_update_hook"
_REMOTE_STORAGE_WARNING = "SoAI now runs as the Windows SYSTEM account. These storage settings point to network shares or mapped drives that it may not reach: %s. Move them to a local folder or to a share that the computer account can access."


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


def _begin_pending_config_upgrades(
    config_path: str, repo_root: str
) -> tuple[tuple[SavedConfigUpgrade, ...], tuple[ConfigUpgradeTransform, ...]]:
    upgrades: list[tuple[SavedConfigUpgrade, ConfigUpgradeTransform]] = [
        (SavedConfigUpgrade.TIMEOUT_DEFAULT, upgrade_selected_timeout_defaults),
    ]
    if is_windows():
        upgrades.append(
            (
                SavedConfigUpgrade.WINDOWS_SERVICE_PATHS,
                partial(upgrade_windows_service_paths, base_path=repo_root),
            )
        )
    pending = tuple(
        (upgrade, transform)
        for upgrade, transform in upgrades
        if not config_upgrade_completed(config_path, upgrade)
    )
    for upgrade, _transform in pending:
        begin_config_upgrade(config_path, upgrade)
    return (
        tuple(upgrade for upgrade, _transform in pending),
        tuple(transform for _upgrade, transform in pending),
    )


def _apply_config_upgrades(
    payload: ConfigDict, *, transforms: tuple[ConfigUpgradeTransform, ...]
) -> ConfigPayloadTransformResult:
    changed_paths: set[str] = set()
    for transform in transforms:
        result = transform(payload)
        payload = result.data
        changed_paths.update(result.changed_paths)
    return ConfigPayloadTransformResult(data=payload, changed_paths=tuple(sorted(changed_paths)))


def _report_remote_storage(config: Config, logger: logging.Logger) -> None:
    remote_settings = find_remote_storage_settings(config)
    if remote_settings:
        logger.warning(
            _REMOTE_STORAGE_WARNING,
            ", ".join(remote_settings),
        )


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


def main(task_catalog: TaskTypeCatalog, *, edition: str = "soai-core") -> int:
    _configure_logging()
    logger = get_logger(LOGGER_NAME)
    repo_root = os.path.abspath(os.getcwd())
    config_path = ""
    config_backup_path: str | None = None
    migrations_committed = False

    try:
        with ExitStack() as resources:
            resources.enter_context(
                guard_plugin_upgrade_ownership(repo_root, edition=edition, logger=logger)
            )
            config_path = resolve_config_path(repo_root)
            prepared_update = find_pending_update_activation(repo_root, include_preparation=True)
            if prepared_update is not None and os.path.normcase(config_path) != os.path.normcase(
                prepared_update.config_path
            ):
                raise StateError("Update hook configuration does not match protected update state.")
            pending_upgrades, upgrade_transforms = _begin_pending_config_upgrades(
                config_path, repo_root
            )
            reconciliation = reconcile_config_payload_on_disk(
                config_path=config_path,
                logger=logger,
                create_missing=True,
                migration_message="Config migrations applied during update hook: %s",
                drift_message="Config schema drift detected during update hook; rewriting config.yaml.",
                changed_paths_message="Updated config paths: %s",
                payload_transform=(
                    partial(_apply_config_upgrades, transforms=upgrade_transforms)
                    if upgrade_transforms
                    else None
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
            plugin_directories = tuple(
                dict.fromkeys(
                    (
                        resolve_update_plugins_path(config_instance),
                        os.path.join(repo_root, "plugins"),
                    )
                )
            )
            protected_plugins = retained_plugin_sources(
                prepared_update,
                base_path=repo_root,
                directories=plugin_directories,
                edition=edition,
            )
            resources.enter_context(
                refresh_plugin_backend_limits(
                    base_path=repo_root,
                    config_path=config_path,
                    directories=plugin_directories,
                    lock_directory=locks_dir,
                    target_version=__version__,
                    reservation_provider=create_bootstrap_disk_reservation_provider(repo_root),
                    logger=logger,
                    retained_packages=protected_plugins,
                )
            )

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
            if prepared_update is None or os.path.isfile(
                marker_path(prepared_update.paths.transaction_path, SUCCESS_COMPLETE_MARKER)
            ):
                for upgrade in pending_upgrades:
                    mark_config_upgrade_completed(config_path, upgrade)
            if is_windows():
                migrate_windows_service_state(repo_root, logger)
                _report_remote_storage(config_instance, logger)
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

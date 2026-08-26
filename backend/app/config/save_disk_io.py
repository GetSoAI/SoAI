"""SoAI - Config save disk I/O operations [backend/app/config/save_disk_io.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import copy
import os
from typing import TYPE_CHECKING

from ruamel.yaml.comments import CommentedMap

from app.config.save_outcome import ConfigSaveOutcome
from core.config.types import KnownFileState
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ConfigurationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol

if TYPE_CHECKING:
    from app.config.internal_protocols import (
        ConfigCacheProtocol,
        ConfigReconcilerProtocol,
    )
    from app.config.io import ConfigIO

__all__ = (
    "load_current_config_from_disk",
    "write_config_to_disk",
)

OPERATION = "config_manager.save_config"


async def load_current_config_from_disk(
    io: ConfigIO,
    *,
    config_name: str,
    config_path: str,
) -> CommentedMap | None:
    exists = await asyncio.to_thread(os.path.exists, config_path)
    if not exists:
        return None
    raw_contents, _ = await io.read_config_snapshot_unlocked(
        config_path=config_path,
        config_name=config_name,
    )
    return io.parse_config_contents(
        raw_contents,
        config_name=config_name,
        config_path=config_path,
    )


async def write_config_to_disk(
    *,
    io: ConfigIO,
    reconciler: ConfigReconcilerProtocol,
    cache: ConfigCacheProtocol,
    logger: LoggerProtocol,
    config_name: str,
    config_path: str,
    config_mapping: CommentedMap,
    previous_cached_snapshot: CommentedMap | None,
    lock_path: str,
    previous_state: KnownFileState | None,
) -> ConfigSaveOutcome:
    backup_path = f"{config_path}.backup"
    content_hash: str | None = None
    did_exist_before_save = False
    previous_revision: int | None = None
    revision = 0
    try:
        did_exist_before_save = os.path.exists(config_path)
        previous_revision = reconciler.file_revisions.get(config_path)
        await io.atomic_write_yaml_unlocked(
            config_path=config_path,
            config_mapping=config_mapping,
            backup_path=backup_path,
            encoding="utf-8",
        )
        stat = await asyncio.to_thread(os.stat, config_path)
        content_hash = await io.calculate_file_hash(config_path)
        reconciler.known_files_state[config_path] = KnownFileState(
            mtime=stat.st_mtime,
            size=stat.st_size,
            content_hash=content_hash,
        )
        revision = reconciler.bump_revision(config_path)
        async with cache.lock:
            cache.configs[config_name] = copy.deepcopy(config_mapping)
        logger.info(
            "Configuration for '%s' saved to %s and internal state updated.",
            config_name,
            config_path,
        )
    except PermissionError as exception:
        raise ConfigurationError(
            f"PERMISSION DENIED: Cannot write config file {config_path}. ({exception})",
        ) from exception
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Error saving config",
            operation=OPERATION,
            details={"config_name": config_name},
        )
        raise ConfigurationError(
            f"Unexpected error saving config '{config_name}': {exception}",
        ) from exception
    return ConfigSaveOutcome(
        config_name=config_name,
        config_path=config_path,
        lock_path=lock_path,
        backup_path=backup_path,
        did_exist_before_save=did_exist_before_save,
        previous_known_state=previous_state,
        previous_cached_snapshot=previous_cached_snapshot,
        previous_revision=previous_revision,
        content_hash=content_hash,
        revision=revision,
    )

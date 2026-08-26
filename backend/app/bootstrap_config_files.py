"""SoAI - Bootstrap configuration file mirroring helpers [backend/app/bootstrap_config_files.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import io
import logging
import shutil

from core.config.file_permissions import (
    runtime_config_atomic_file_mode,
    secure_runtime_config_paths,
)
from core.errors.exception_logging import log_exception
from core.filesystem.async_queries import async_path_exists
from core.filesystem.atomic_writes import atomic_write_text
from core.filesystem.open_files import open_text

__all__ = ("mirror_config_file",)

OPERATION_APP_BOOTSTRAP_CONFIG_FILES_MIRROR_CONFIG_FILE = (
    "app.bootstrap_config_files.mirror_config_file"
)


async def mirror_config_file(
    *,
    source_path: str,
    source_label: str,
    target_path: str,
    target_label: str,
    logger: logging.Logger,
    operation: str,
) -> bool:
    if not await async_path_exists(source_path):
        return False
    try:

        def _writer(handle: io.TextIOBase) -> None:
            with open_text(source_path, encoding="utf-8") as source_handle:
                shutil.copyfileobj(source_handle, handle)

        backup_path = f"{target_path}.backup" if await async_path_exists(target_path) else None
        await asyncio.to_thread(secure_runtime_config_paths, target_path, backup_path)
        await asyncio.to_thread(
            atomic_write_text,
            target_path,
            _writer,
            encoding="utf-8",
            backup_path=backup_path,
            file_mode=runtime_config_atomic_file_mode(),
        )
        await asyncio.to_thread(secure_runtime_config_paths, target_path, backup_path)
        logger.debug("Bootstrap: Created '%s' from '%s'.", target_label, source_label)
        return True
    except PermissionError as permission_error:
        logger.critical(
            "Bootstrap: PERMISSION DENIED while creating '%s' from '%s': %s",
            target_label,
            source_label,
            permission_error,
        )
        raise
    except OSError as exception:
        log_exception(
            logger,
            exception,
            message=f"Bootstrap: Failed to create '{target_label}' from '{source_label}'",
            operation=OPERATION_APP_BOOTSTRAP_CONFIG_FILES_MIRROR_CONFIG_FILE,
            details={"bootstrap_operation": operation},
        )
        return False

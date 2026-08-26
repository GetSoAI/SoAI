"""SoAI - Config path discovery for filesystem reconciliation [backend/app/config/reconciliation_discovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os

from app.config.io import ConfigIO
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ConfigurationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.plugins.file_suffixes import PLUGIN_CONFIG_FILE_SUFFIX

__all__ = (
    "build_candidate_paths_async",
    "filter_paths_to_existing_async",
    "list_manageable_configs_async",
)

OPERATION_CONFIG_MANAGER_GET_ALL_MANAGEABLE_PATHS = "config_manager.get_all_manageable_paths"
OPERATION_CONFIG_MANAGER_SCAN_FILESYSTEM_STATE = "config_manager.scan_filesystem_state"


async def list_manageable_configs_async(
    plugins_path: str | None,
    logger: LoggerProtocol,
) -> list[str]:
    configs = ["core"]
    if not plugins_path:
        return configs
    try:
        if await asyncio.to_thread(os.path.isdir, plugins_path):
            plugin_configs = [
                filename.removesuffix(PLUGIN_CONFIG_FILE_SUFFIX)
                for filename in await asyncio.to_thread(os.listdir, plugins_path)
                if filename.endswith(PLUGIN_CONFIG_FILE_SUFFIX)
            ]
            configs.extend(plugin_configs)
    except OSError as exception:
        log_exception(
            logger,
            exception,
            message="Could not list plugin configs.",
            operation=OPERATION_CONFIG_MANAGER_GET_ALL_MANAGEABLE_PATHS,
            details={"plugins_path": plugins_path},
        )
        raise ConfigurationError(f"Could not list plugin configs: {plugins_path}") from exception
    return sorted(configs)


async def build_candidate_paths_async(
    io_component: ConfigIO,
    config_name: str | None,
    logger: LoggerProtocol,
) -> set[str]:
    if config_name:
        return {io_component.get_config_path_sync(config_name)}

    candidate_paths: set[str] = {io_component.get_config_path_sync("core")}
    plugins_path = io_component.plugins_path
    if not plugins_path:
        return candidate_paths

    plugins_dir_is_dir = await asyncio.to_thread(os.path.isdir, plugins_path)
    if not plugins_dir_is_dir:
        return candidate_paths

    try:
        entries = await asyncio.to_thread(os.listdir, plugins_path)
        for entry in entries:
            if not entry.endswith(PLUGIN_CONFIG_FILE_SUFFIX):
                continue
            full_path = os.path.join(plugins_path, entry)
            if await asyncio.to_thread(os.path.isfile, full_path):
                candidate_paths.add(full_path)
    except OSError as exception:
        log_exception(
            logger,
            exception,
            message="Could not scan plugin directory for reconciliation",
            operation=OPERATION_CONFIG_MANAGER_GET_ALL_MANAGEABLE_PATHS,
            details={"plugins_path": plugins_path},
        )
        raise ConfigurationError(
            f"Could not scan plugin directory for reconciliation: {plugins_path}",
        ) from exception
    return candidate_paths


async def filter_paths_to_existing_async(
    candidate_paths: set[str],
    logger: LoggerProtocol,
) -> set[str]:
    current_paths_on_disk: set[str] = set()
    for path in candidate_paths:
        try:
            if await asyncio.to_thread(os.path.exists, path):
                current_paths_on_disk.add(path)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to check existence",
                operation=OPERATION_CONFIG_MANAGER_SCAN_FILESYSTEM_STATE,
                details={"path": path},
            )
            raise ConfigurationError(
                f"Failed to check existence for {path}: {exception}",
            ) from exception
    return current_paths_on_disk

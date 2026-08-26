"""SoAI - Plugin runtime filesystem lifecycle operations [backend/plugins/filesystem/runtime_artifacts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import stat
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_and_wait
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.managed_file_deletion import delete_managed_path
from core.files.managed_storage_errors import FileDeletionSecurityError
from core.files.operations import async_remove_if_exists
from core.filesystem.async_queries import async_makedirs, async_path_exists
from core.filesystem.open_files import open_text
from core.logging.trace import get_logger
from plugins.artifact_paths import (
    collect_plugin_artifact_paths,
    collect_plugin_validation_cache_paths,
)
from plugins.clone.clone_committed_cleanup import (
    COMMITTED_CLONE_FILESYSTEM_ARTIFACT_TYPES,
    release_committed_clone_markers,
)
from plugins.fs_permissions import (
    ensure_correct_permissions,
    ensure_single_path_permissions,
)
from plugins.identity import require_plugin_identifier
from plugins.package_cache_gc import remove_plugin_package_cache

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from plugins.manager.internal_protocols import PluginManagerLifecycleTarget
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = (
    "prepare_plugin_runtime_directories",
    "remove_plugin_artifacts",
    "remove_plugin_backend_installation",
    "remove_plugin_validation_cache_artifacts",
)

OPERATION_PLUGIN_MANAGER_INIT = "plugin_manager.init"
OPERATION_REMOVE_PLUGIN_ARTIFACTS = "plugins.manager.artifacts.remove_plugin_artifacts"
OPERATION_REMOVE_BACKEND_INSTALLATION = (
    "plugins.registry.force_cleanup_steps.remove_plugin_backend_installation"
)
LOGGER_NAME = "SoAI.plugins.filesystem.runtime_artifacts"


async def prepare_plugin_runtime_directories(
    manager: PluginManagerLifecycleTarget,
    logger: LoggerProtocol,
) -> None:
    for directory in [
        manager.paths.plugin_directory,
        manager.paths.backends_directory,
        manager.paths.temp_directory,
        manager.paths.plugin_venvs_root,
    ]:
        await async_makedirs(directory, exist_ok=True)
        await ensure_single_path_permissions(directory)
    init_py_path = os.path.join(manager.paths.plugin_directory, "__init__.py")
    if await async_path_exists(init_py_path):
        return
    logger.warning(
        "Plugins directory is missing '__init__.py'. Creating it now at: %s",
        init_py_path,
    )
    try:

        def create_init_file() -> None:
            with open_text(init_py_path, mode="a", encoding="utf-8") as file_handle:
                file_handle.write("")

        await uncancel_and_wait(asyncio.to_thread(create_init_file))
        await ensure_correct_permissions(init_py_path)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to automatically create '__init__.py' in plugins directory",
            operation=OPERATION_PLUGIN_MANAGER_INIT,
        )


async def _remove_plugin_paths(
    paths: list[str] | tuple[str, ...],
    *,
    plugin_name: str,
    require_success: bool,
) -> None:
    logger = get_logger(LOGGER_NAME)
    for path in paths:
        existed_before = await async_path_exists(path)
        removed = await async_remove_if_exists(path, logger=logger)
        if require_success and existed_before and (not removed) and await async_path_exists(path):
            raise StateError(
                "Failed to remove plugin artifact.",
                operation=OPERATION_REMOVE_PLUGIN_ARTIFACTS,
                details={"plugin_name": plugin_name, "path": path},
            )


async def remove_plugin_validation_cache_artifacts(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> None:
    await _remove_plugin_paths(
        collect_plugin_validation_cache_paths(manager, plugin_name),
        plugin_name=plugin_name,
        require_success=True,
    )


async def remove_plugin_artifacts(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    *,
    require_success: bool = True,
) -> None:
    await release_committed_clone_markers(
        manager,
        plugin_name,
        artifact_types=COMMITTED_CLONE_FILESYSTEM_ARTIFACT_TYPES,
    )
    await remove_plugin_package_cache(manager, plugin_name)
    await _remove_plugin_paths(
        collect_plugin_artifact_paths(manager, plugin_name),
        plugin_name=plugin_name,
        require_success=require_success,
    )


async def remove_plugin_backend_installation(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> None:
    try:
        require_plugin_identifier(
            plugin_name,
            invalid_message="Invalid plugin name for backend installation removal.",
        )
    except ValidationError as exception:
        raise StateError(
            "Invalid plugin name for backend installation removal.",
            operation=OPERATION_REMOVE_BACKEND_INSTALLATION,
            details={"plugin_name": plugin_name},
        ) from exception
    backends_directory = str(manager.paths.backends_directory or "").strip()
    if not backends_directory:
        raise StateError(
            "Plugin backends directory is not configured.",
            operation=OPERATION_REMOVE_BACKEND_INSTALLATION,
            details={"plugin_name": plugin_name},
        )
    backends_root = os.path.abspath(backends_directory)
    candidate_path = os.path.join(backends_root, plugin_name)
    try:
        candidate_status = os.lstat(candidate_path)
    except FileNotFoundError:
        return
    if not stat.S_ISDIR(candidate_status.st_mode) and not stat.S_ISLNK(candidate_status.st_mode):
        raise StateError(
            "Plugin backend installation path exists but is not a directory.",
            operation=OPERATION_REMOVE_BACKEND_INSTALLATION,
            details={"plugin_name": plugin_name, "path": candidate_path},
        )
    try:
        await delete_managed_path(backends_root, candidate_path)
    except (FileDeletionSecurityError, OSError) as exception:
        raise StateError(
            "Plugin backend installation could not be removed safely.",
            operation=OPERATION_REMOVE_BACKEND_INSTALLATION,
            details={"plugin_name": plugin_name},
            cause=exception,
        ) from exception
    if os.path.lexists(candidate_path):
        raise StateError(
            "Plugin backend installation removal did not remove the target path.",
            operation=OPERATION_REMOVE_BACKEND_INSTALLATION,
            details={"plugin_name": plugin_name},
        )

"""SoAI - Plugin upload rollback cleanup [backend/plugins/actions/upload_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from plugins.actions.upload_placeholder_cleanup import cleanup_uploading_placeholder
from plugins.actions.upload_validation import (
    safe_delete_upload_environment,
    safe_remove_upload_file,
)
from plugins.filesystem.runtime_artifacts import remove_plugin_artifacts
from plugins.manager.alias_map import update_alias_map
from plugins.manager.artifacts import purge_plugin_from_memory
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

__all__ = (
    "UploadExecutionState",
    "cleanup_created_upload_runtime",
    "rollback_plugin_upload",
)

OPERATION = "plugin_flow.process_upload_plugin_async"


@dataclass(slots=True)
class UploadExecutionState:
    placeholder_created: bool = False
    file_moved: bool = False


async def cleanup_created_upload_runtime(
    manager: PluginManagerRuntimeProtocol,
    *,
    plugin_name: str | None,
    logger: LoggerProtocol,
) -> None:
    if plugin_name:
        try:
            await purge_plugin_from_memory(manager, plugin_name)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to purge uploaded plugin runtime during upload cleanup.",
                operation=OPERATION,
                details={"plugin": plugin_name},
                level="warning",
            )
    if plugin_name:
        try:
            await remove_plugin_artifacts(manager, plugin_name, require_success=False)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to remove uploaded plugin artifacts during upload cleanup.",
                operation=OPERATION,
                details={"plugin": plugin_name},
                level="warning",
            )
    await safe_delete_upload_environment(manager, plugin_name, logger=logger)


async def rollback_plugin_upload(
    manager: PluginManagerRuntimeProtocol,
    *,
    state: UploadExecutionState,
    plugin_name: str | None,
    final_path: str | None,
    committed_path: str | None,
    logger: LoggerProtocol,
) -> None:
    if plugin_name and (state.placeholder_created or state.file_moved):
        await cleanup_created_upload_runtime(
            manager,
            plugin_name=plugin_name,
            logger=logger,
        )
    if committed_path is not None:
        await safe_remove_upload_file(committed_path, logger=logger)
    placeholder_deleted = await cleanup_uploading_placeholder(
        manager,
        placeholder_created=state.placeholder_created,
        plugin_name=plugin_name,
        final_path=final_path,
    )
    if placeholder_deleted:
        await update_alias_map(manager)

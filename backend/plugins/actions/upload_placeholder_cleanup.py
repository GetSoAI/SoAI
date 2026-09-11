"""SoAI - Plugin upload placeholder cleanup [backend/plugins/actions/upload_placeholder_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.async_queries import async_path_exists
from core.logging.trace import get_logger
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

__all__ = ("cleanup_uploading_placeholder",)

LOGGER_NAME = "SoAI.plugins.actions.upload_placeholder_cleanup"
OPERATION = "plugin_flow.process_upload_plugin_async"


async def cleanup_uploading_placeholder(
    manager: PluginManagerRuntimeProtocol,
    *,
    placeholder_created: bool,
    plugin_name: str | None,
    final_path: str | None,
) -> bool:
    logger = get_logger(LOGGER_NAME)
    if not placeholder_created or not plugin_name:
        return False
    try:
        record = await manager.dependencies.databases.plugins.get_plugin_by_name(plugin_name)
        if not record:
            return False
        if final_path and await async_path_exists(final_path):
            return False
        deleted = await manager.dependencies.databases.plugins.permanently_delete_plugin_record(
            plugin_name
        )
        return bool(deleted)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to cleanup plugin upload placeholder",
            operation=OPERATION,
            details={"plugin": plugin_name},
        )
        return False

"""SoAI - Plugin upload task collision recovery [backend/plugins/actions/upload_task_collision.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from core.files.operations import async_remove_if_exists
from core.logging.trace import get_logger
from core.tasks.errors import TaskIDCollisionError
from plugins.actions.upload_placeholder_cleanup import cleanup_uploading_placeholder
from plugins.state.task_collisions import handle_task_id_collision_error

if TYPE_CHECKING:
    from core.events.types_base import ReplyChannel
    from core.runtime.request_context import RequestContext
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = ("handle_upload_task_id_collision",)

LOGGER_NAME = "SoAI.plugins.actions.upload_task_collision"


async def handle_upload_task_id_collision(
    manager: PluginManagerRuntimeProtocol,
    exception: TaskIDCollisionError,
    *,
    reply_channel: ReplyChannel,
    context: RequestContext | None,
    temp_file_path: str | None,
    placeholder_created: bool,
    plugin_name: str | None,
    final_path: str | None,
) -> None:
    del context

    async def cleanup_temp_file() -> None:
        logger = get_logger(LOGGER_NAME)
        if temp_file_path:
            await async_remove_if_exists(temp_file_path, logger=logger, log_level=logging.DEBUG)
        await cleanup_uploading_placeholder(
            manager,
            placeholder_created=placeholder_created,
            plugin_name=plugin_name,
            final_path=final_path,
        )

    await handle_task_id_collision_error(
        exception,
        reply_channel,
        manager.dependencies.infrastructure.task_helpers.send_error_event,
        cleanup_callback=cleanup_temp_file,
    )

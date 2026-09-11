"""SoAI - Plugin upload task collision recovery [backend/plugins/actions/upload_task_collision.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.tasks.errors import TaskIDCollisionError
from plugins.actions.upload_placeholder_cleanup import cleanup_uploading_placeholder
from plugins.state.task_collisions import handle_task_id_collision_error

if TYPE_CHECKING:
    from core.events.types_base import ReplyChannel
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = ("handle_upload_task_id_collision",)


async def handle_upload_task_id_collision(
    manager: PluginManagerRuntimeProtocol,
    exception: TaskIDCollisionError,
    *,
    reply_channel: ReplyChannel,
    placeholder_created: bool,
    plugin_name: str | None,
    final_path: str | None,
) -> None:
    async def cleanup_placeholder() -> None:
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
        cleanup_callback=cleanup_placeholder,
    )

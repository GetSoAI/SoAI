"""SoAI - Plugin user-command backend process cleanup [backend/orchestrator/lifecycle/user_commands/plugin_backend_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.events.types_base import Event
from core.logging.trace import get_logger
from core.runtime.backend_process_tracking_db import (
    cleanup_tracked_backend_processes_from_database,
)
from core.tasks.api_events import send_task_complete_event
from orchestrator.lifecycle.user_commands.dependencies import (
    OrchestratorLifecycleUserCommandsDependencies,
)

__all__ = ("cleanup_tracked_backend_processes_if_needed",)

LOGGER_NAME = "SoAI.orchestrator.lifecycle.plugin_backend_cleanup"


async def cleanup_tracked_backend_processes_if_needed(
    deps: OrchestratorLifecycleUserCommandsDependencies,
    *,
    plugin_name: str,
    reply_channel: asyncio.Queue[Event],
    command_name: str,
) -> bool:
    logger = get_logger(LOGGER_NAME)
    record = await deps.orchestrator.database_plugins.get_plugin_by_name(plugin_name)
    if not (record and record.get("supports_backend_process_tracking")):
        return True
    cleanup_result = await cleanup_tracked_backend_processes_from_database(
        deps.orchestrator.database_plugins,
        plugin_name=plugin_name,
        logger=logger,
    )
    if cleanup_result is None or cleanup_result.succeeded:
        return True
    await send_task_complete_event(
        reply_channel,
        (
            f"Plugin '{plugin_name}' is marked as stopped/disabled, "
            f"but backend process cleanup failed during {command_name}."
        ),
        success=False,
        error_code=500,
        registry=deps.task_registry,
    )
    return False

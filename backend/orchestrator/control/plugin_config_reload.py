"""SoAI - Plugin config reload task submission [backend/orchestrator/control/plugin_config_reload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.events.types_system import ConfigReloadedEvent
from core.logging.trace import get_logger
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.task_cancellation_ops import generate_system_cancellation_id
from orchestrator.control.internal_protocols import (
    OrchestratorPluginConfigReloadDepsSurface,
)
from orchestrator.control.plugin_scheduler_work import schedule_work_items
from orchestrator.lifecycle.config_reload_result import PluginConfigReloadOutcome

__all__ = (
    "enqueue_plugin_config_reload",
    "run_plugin_config_reload",
)

LOGGER_NAME = "SoAI.orchestrator.control.plugin_config_reload"


CONFIG_RELOAD_RETRY_DELAY_SECONDS = 0.25


async def enqueue_plugin_config_reload(
    *,
    event: ConfigReloadedEvent,
    deps: OrchestratorPluginConfigReloadDepsSurface,
) -> None:
    logger = get_logger(LOGGER_NAME)
    _ = spawn_tracked_task(
        run_plugin_config_reload(event=event, deps=deps),
        owner="orchestrator_config_reload",
        logger=logger,
        metadata={"config_name": event.config_name, "revision": event.revision},
        cancellation_binder=deps.orchestrator.task_cancellation_binder,
        finalizer_tracker=deps.orchestrator.task_finalizer_tracker,
        cancellation_id=generate_system_cancellation_id("orchestrator-config-reload"),
        name=f"orchestrator-config-reload-{event.config_name}-{event.revision}",
    )


async def run_plugin_config_reload(
    *,
    event: ConfigReloadedEvent,
    deps: OrchestratorPluginConfigReloadDepsSurface,
) -> None:
    logger = get_logger(LOGGER_NAME)
    while True:
        reload_result = await deps.lifecycle.startup.handle_plugin_config_reloaded(event)
        if reload_result.should_retry:
            await asyncio.sleep(CONFIG_RELOAD_RETRY_DELAY_SECONDS)
            continue
        if reload_result.outcome == PluginConfigReloadOutcome.FAILED_TERMINAL:
            logger.warning(
                "Plugin config reload failed terminally for %s at revision %s: %s",
                event.config_name,
                event.revision,
                reload_result.error or "unknown error",
            )
        await schedule_work_items(
            scheduler=deps.scheduler,
            work_items=reload_result.work_items,
            operation="orchestrator_control.handle_plugin_config_reloaded",
        )
        return

"""SoAI - Plugin start_with_model execution for model loading [backend/orchestrator/lifecycle/model_loading_start.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.context import create_system_cancellation_id
from core.plugins.protocols_instance import PluginInstanceProtocol
from core.runtime.request_context import RequestContext
from core.runtime.request_context_cloning import clone_request_context
from core.tasks.task import Task
from orchestrator.lifecycle.model_start_timeouts import resolve_start_with_model_timeout
from orchestrator.lifecycle.task_tracking.model_context import (
    build_startup_model_context,
)
from orchestrator.lifecycle.tracked_backend_processes import (
    supports_backend_process_tracking,
)
from orchestrator.lifecycle.tracked_backend_start import (
    start_with_model_and_persist_backend_process_identities,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from core.logging.protocols import LoggerProtocol
    from core.plugins.protocols_database import DatabasePluginsProtocol
    from core.runtime.backend_process_tracking import BackendProcessIdentity
    from core.types.json import JSONValue

    type ModelInfo = Mapping[str, JSONValue]

__all__ = ("start_plugin_process_with_model",)


async def start_plugin_process_with_model(
    plugin_instance: PluginInstanceProtocol,
    *,
    plugin_name: str,
    task: Task,
    model_info: ModelInfo,
    request_context: RequestContext,
    database_plugins: DatabasePluginsProtocol,
    load_timeout: float,
    logger: LoggerProtocol,
) -> tuple[bool, bool, list[BackendProcessIdentity]]:
    supports_tracking = supports_backend_process_tracking(plugin_instance)
    start_timeout = resolve_start_with_model_timeout(load_timeout)
    start_context = clone_request_context(
        request_context,
        cancellation_id=create_system_cancellation_id(f"model_start:{plugin_name}"),
    )
    if supports_tracking:
        start_success, persisted_identities = (
            await start_with_model_and_persist_backend_process_identities(
                plugin_instance,
                plugin_name=plugin_name,
                database_plugins=database_plugins,
                model_context=build_startup_model_context(task, model_info),
                request_context=start_context,
                start_timeout=start_timeout,
                logger=logger,
            )
        )
        return (bool(start_success), supports_tracking, list(persisted_identities))
    start_success = await asyncio.wait_for(
        plugin_instance.start_with_model(
            build_startup_model_context(task, model_info),
            start_context,
        ),
        timeout=start_timeout,
    )
    return (bool(start_success), supports_tracking, [])

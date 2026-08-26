"""SoAI - Plugin force cleanup helper steps [backend/plugins/registry/force_cleanup_steps.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.timing.constants import SHORT_POLL_INTERVAL_SEC
from plugins.filesystem.runtime_artifacts import remove_plugin_artifacts

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )
    from plugins.protocols_internal.task_progress.internal_protocols import (
        TaskProgressSenderProtocol,
    )

__all__ = (
    "execute_force_cleanup_step",
    "perform_force_cleanup_file_removal",
)

OPERATION_PLUGINS_REGISTRY_FORCE_CLEANUP_STEPS_EXECUTE_FORCE_CLEANUP_STEP = (
    "plugins.registry.force_cleanup_steps.execute_force_cleanup_step"
)
FORCE_CLEANUP_STEP_EXCEPTIONS = RECOVERABLE_EXCEPTIONS + (StateError,)


LOGGER_NAME = "SoAI.plugins.registry.force_cleanup_steps"


async def execute_force_cleanup_step(
    progress_callback: TaskProgressSenderProtocol,
    cleanup_errors: list[str],
    *,
    progress_percent: int,
    progress_message: str,
    error_message: str,
    error_label: str,
    action_callable: Callable[[], Awaitable[None]] | None,
    operation_name: str = "plugin_registry.process_force_cleanup_plugin_async",
    abort_on_failure: bool = False,
) -> None:
    logger = get_logger(LOGGER_NAME)
    try:
        await progress_callback(progress_percent, progress_message)
        if action_callable is not None:
            await action_callable()
    except FORCE_CLEANUP_STEP_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message=error_message,
            operation=OPERATION_PLUGINS_REGISTRY_FORCE_CLEANUP_STEPS_EXECUTE_FORCE_CLEANUP_STEP,
            details={"operation_name": operation_name, "step": error_label},
        )
        cleanup_errors.append(f"{error_label} ({exception})")
        if abort_on_failure:
            raise


async def perform_force_cleanup_file_removal(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> None:
    await asyncio.sleep(SHORT_POLL_INTERVAL_SEC)
    await remove_plugin_artifacts(manager, plugin_name)
    await manager.dependencies.infrastructure.config_manager.delete_from_cache(plugin_name)

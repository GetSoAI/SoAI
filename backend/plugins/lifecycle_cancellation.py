"""SoAI - Plugin lifecycle cancellation registry cleanup [backend/plugins/lifecycle_cancellation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger

if TYPE_CHECKING:
    from plugins.lifecycle_dependencies import (
        ActiveCancellationRecord,
        PluginLifecycleDependencies,
    )

__all__ = ("deregister_active_cancellation",)

LOGGER_NAME = "SoAI.plugins.lifecycle_cancellation"
OPERATION = "plugin_lifecycle.deregister_active_cancellation.clear_registry"


async def deregister_active_cancellation(
    deps: PluginLifecycleDependencies,
    active_cancellation_lock: asyncio.Lock,
    active_cancellation_tasks: dict[str, dict[str, ActiveCancellationRecord]],
    cancellation_id: str,
    task_key: str,
) -> None:
    logger = get_logger(LOGGER_NAME)
    should_clear = False
    async with active_cancellation_lock:
        tasks = active_cancellation_tasks.get(cancellation_id)
        if not tasks:
            return
        tasks.pop(task_key, None)
        if not tasks:
            active_cancellation_tasks.pop(cancellation_id, None)
            should_clear = True
    if not should_clear:
        return
    try:
        active_tasks = await deps.task_registry_queries.query_active_filtered(
            cancellation_id=cancellation_id,
            limit=1,
        )
        token_set = await deps.token_collection.get_tokens_for_scope(cancellation_id)
        if (not active_tasks) and (not token_set):
            await deps.cancellation_coordinator.clear_scope(cancellation_id)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to clear cancellation registry for cancellation_id.",
            operation=OPERATION,
            details={"cancellation_id": cancellation_id},
            level="warning",
        )

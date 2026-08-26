"""SoAI - Plugin lifecycle task cancellation workflows [backend/plugins/lifecycle_shutdown_cancellation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.task_groups import cancel_and_await
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from plugins.lifecycle_dependencies import (
    ActiveCancellationRecord,
    PluginLifecycleDependencies,
)

__all__ = (
    "cancel_and_drain_registered_plugin_tasks",
    "cancel_registered_plugin_tasks",
)

LOGGER_NAME = "SoAI.plugins.lifecycle_shutdown_cancellation"
OPERATION = "plugins.lifecycle.cancel_registered_tasks"


async def _cancel_scopes(
    deps: PluginLifecycleDependencies,
    cancellation_ids: list[str],
    reason: str,
    *,
    plugin_name: str | None,
) -> int:
    logger = get_logger(LOGGER_NAME)
    cancelled_count = 0
    for cancellation_id in cancellation_ids:
        try:
            await deps.cancellation_coordinator.cancel_scope(cancellation_id, reason)
            cancelled_count += 1
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to cancel registered plugin lifecycle task.",
                operation=OPERATION,
                details={"cancellation_id": cancellation_id, "plugin": plugin_name or ""},
                level="warning",
            )
    return cancelled_count


async def cancel_registered_plugin_tasks(
    deps: PluginLifecycleDependencies,
    active_cancellation_lock: asyncio.Lock,
    active_cancellation_tasks: dict[str, dict[str, ActiveCancellationRecord]],
    *,
    plugin_name: str,
    reason: str,
    exclude_cancellation_ids: frozenset[str],
) -> int:
    cancellation_ids: list[str] = []
    async with active_cancellation_lock:
        for cancellation_id, records in active_cancellation_tasks.items():
            if cancellation_id in exclude_cancellation_ids:
                continue
            if any(record.plugin_name == plugin_name for record in records.values()):
                cancellation_ids.append(cancellation_id)
    return await _cancel_scopes(
        deps,
        cancellation_ids,
        reason,
        plugin_name=plugin_name,
    )


async def cancel_and_drain_registered_plugin_tasks(
    deps: PluginLifecycleDependencies,
    active_cancellation_lock: asyncio.Lock,
    active_cancellation_tasks: dict[str, dict[str, ActiveCancellationRecord]],
    *,
    reason: str,
    drain_timeout_sec: float,
) -> int:
    current_task = asyncio.current_task()
    cancellation_ids: list[str] = []
    records_to_drain: list[ActiveCancellationRecord] = []
    self_owned_records: list[ActiveCancellationRecord] = []
    async with active_cancellation_lock:
        for cancellation_id, records in active_cancellation_tasks.items():
            active_records = [record for record in records.values() if not record.task.done()]
            eligible_records = [
                record for record in active_records if record.task is not current_task
            ]
            if not eligible_records:
                continue
            records_to_drain.extend(eligible_records)
            if any(record.task is current_task for record in active_records):
                self_owned_records.extend(eligible_records)
            else:
                cancellation_ids.append(cancellation_id)
    await _cancel_scopes(deps, cancellation_ids, reason, plugin_name=None)
    for record in self_owned_records:
        record.token.cancel(reason)
    await cancel_and_await(
        [record.task for record in records_to_drain],
        timeout_sec=drain_timeout_sec,
    )
    logger = get_logger(LOGGER_NAME)
    for record in records_to_drain:
        if record.task.done():
            continue
        logger.warning(
            "Plugin lifecycle task remained active after shutdown cancellation: plugin=%s task_type=%s",
            record.plugin_name or "",
            record.task_type,
        )
    return len(records_to_drain)

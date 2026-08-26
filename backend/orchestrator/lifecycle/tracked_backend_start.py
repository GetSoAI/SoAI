"""SoAI - Tracked backend process start persistence [backend/orchestrator/lifecycle/tracked_backend_start.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_groups import cancel_and_await
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAITimeoutError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.runtime.backend_process_tracking import (
    BackendProcessIdentity,
    backend_process_identities_match,
    normalize_backend_process_pids,
    resolve_backend_process_identities,
)
from core.timing.constants import SHORT_POLL_INTERVAL_SEC, STANDARD_DELAY_SEC

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.plugins.protocols_database import DatabasePluginsProtocol
    from core.plugins.protocols_instance import (
        ModelContextProtocol,
        PluginInstanceProtocol,
    )
    from core.runtime.request_context import RequestContext

__all__ = ("start_with_model_and_persist_backend_process_identities",)

OPERATION = "orchestrator.tracked_backend_start"


async def start_with_model_and_persist_backend_process_identities(
    plugin_instance: PluginInstanceProtocol,
    *,
    plugin_name: str,
    database_plugins: DatabasePluginsProtocol,
    model_context: ModelContextProtocol,
    request_context: RequestContext,
    start_timeout: float,
    logger: LoggerProtocol,
) -> tuple[bool, list[BackendProcessIdentity]]:
    start_task: asyncio.Task[bool] | None = None
    start_task_started_at = time.monotonic()
    cleanup_start_task = False
    persisted_identities: list[BackendProcessIdentity] = []
    try:
        start_task = create_ephemeral_task(
            plugin_instance.start_with_model(model_context, request_context),
            name="orchestrator.lifecycle.tracked_backend_start.start_with_model",
        )
        cleanup_start_task = True
        persisted_identities = await _poll_and_persist_start_identities(
            plugin_instance=plugin_instance,
            plugin_name=plugin_name,
            database_plugins=database_plugins,
            start_task=start_task,
            start_task_started_at=start_task_started_at,
            start_timeout=start_timeout,
            logger=logger,
        )
        remaining_start_timeout = max(
            0.0,
            start_timeout - (time.monotonic() - start_task_started_at),
        )
        start_success = await asyncio.wait_for(start_task, timeout=remaining_start_timeout)
        if not start_success:
            cleanup_start_task = False
            return (False, persisted_identities)
        identities = await _persist_final_start_identities(
            plugin_instance=plugin_instance,
            plugin_name=plugin_name,
            database_plugins=database_plugins,
            persisted_identities=persisted_identities,
            logger=logger,
        )
        cleanup_start_task = False
        return (True, identities)
    except TimeoutError as exception:
        timeout_error = SoAITimeoutError(
            "The backend did not start before its configured deadline.",
            operation=OPERATION,
            cause=exception,
        )
        log_exception(
            logger,
            timeout_error,
            message="Backend startup reached its configured deadline.",
            operation=OPERATION,
        )
        raise timeout_error from exception
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced_exception = coerce_to_soai_error(exception, operation=OPERATION)
        log_exception(
            logger,
            coerced_exception,
            message="Failed to start plugin backend process.",
            operation=OPERATION,
        )
        if coerced_exception is exception:
            raise
        raise coerced_exception from exception
    finally:
        if cleanup_start_task:
            await _settle_start_task_after_failure(start_task)


async def _poll_and_persist_start_identities(
    *,
    plugin_instance: PluginInstanceProtocol,
    plugin_name: str,
    database_plugins: DatabasePluginsProtocol,
    start_task: asyncio.Task[bool],
    start_task_started_at: float,
    start_timeout: float,
    logger: LoggerProtocol,
) -> list[BackendProcessIdentity]:
    persisted_identities: list[BackendProcessIdentity] = []
    poll_deadline = start_task_started_at + min(start_timeout, 5.0)
    while time.monotonic() < poll_deadline:
        if start_task.done():
            break
        probe_timeout = min(
            STANDARD_DELAY_SEC,
            max(0.0, poll_deadline - time.monotonic()),
        )
        if probe_timeout == 0.0:
            break
        try:
            raw_pids = await asyncio.wait_for(
                plugin_instance.get_backend_process_pids(),
                timeout=probe_timeout,
            )
        except TimeoutError:
            continue
        pids = normalize_backend_process_pids(raw_pids)
        if pids:
            identities = resolve_backend_process_identities(
                pids,
                plugin_name=plugin_name,
                logger=logger,
            )
            if identities and not backend_process_identities_match(
                identities,
                persisted_identities,
            ):
                await database_plugins.set_runtime_processes(
                    plugin_name,
                    identities,
                )
                persisted_identities = identities
        await asyncio.sleep(SHORT_POLL_INTERVAL_SEC)
    return persisted_identities


async def _persist_final_start_identities(
    *,
    plugin_instance: PluginInstanceProtocol,
    plugin_name: str,
    database_plugins: DatabasePluginsProtocol,
    persisted_identities: list[BackendProcessIdentity],
    logger: LoggerProtocol,
) -> list[BackendProcessIdentity]:
    try:
        raw_pids = await asyncio.wait_for(
            plugin_instance.get_backend_process_pids(),
            timeout=STANDARD_DELAY_SEC,
        )
    except TimeoutError:
        logger.warning(
            "Backend process identity probe timed out after startup. plugin=%s",
            plugin_name,
        )
        return persisted_identities
    pids = normalize_backend_process_pids(raw_pids)
    if not pids:
        if persisted_identities:
            await database_plugins.clear_runtime_processes(plugin_name)
        return []
    identities = resolve_backend_process_identities(
        pids,
        plugin_name=plugin_name,
        logger=logger,
    )
    if not identities:
        if persisted_identities:
            await database_plugins.clear_runtime_processes(plugin_name)
        return []
    if not backend_process_identities_match(identities, persisted_identities):
        await database_plugins.set_runtime_processes(
            plugin_name,
            identities,
        )
    return identities


async def _settle_start_task_after_failure(
    start_task: asyncio.Task[bool] | None,
) -> None:
    if start_task is not None:
        await uncancel_then_cleanup(cancel_and_await((start_task,)))

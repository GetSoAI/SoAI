"""SoAI - Parallel plugin stop execution during shutdown [backend/orchestrator/control/shutdown_stop_all.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.deadlines import MonotonicDeadline
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_groups import (
    DEFAULT_CANCELLATION_TIMEOUT_SEC,
    cancel_and_await,
)
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.logging.trace import get_logger
from core.orchestrator.stop_outcome import PluginStopOutcome
from orchestrator.lifecycle.service_interfaces.internal_protocols import (
    OrchestratorLifecycleShutdownCoordinatorProtocol,
)

__all__ = ("execute_shutdown_stop_all",)

LOGGER_NAME = "SoAI.orchestrator.control.shutdown_stop_all"
OPERATION = "orchestrator.control.shutdown_stop_all"


async def execute_shutdown_stop_all(
    shutdown: OrchestratorLifecycleShutdownCoordinatorProtocol,
    plugin_names: list[str],
    *,
    reason: str,
    deadline: MonotonicDeadline,
) -> None:
    remaining_seconds = deadline.remaining_seconds()
    execution_budget_sec = remaining_seconds - DEFAULT_CANCELLATION_TIMEOUT_SEC
    if execution_budget_sec <= 0:
        raise StateError(
            f"Shutdown plugin stop deadline expired before stopping: {', '.join(plugin_names)}.",
        )
    task_plugins: dict[asyncio.Task[PluginStopOutcome], str] = {}
    for plugin_name in plugin_names:
        task = create_ephemeral_task(
            shutdown.stop_plugin_for_shutdown(
                plugin_name=plugin_name,
                reason=reason,
                stop_timeout_sec=execution_budget_sec,
            ),
            name=f"shutdown-stop-plugin-{plugin_name}",
            log_exceptions=False,
        )
        task_plugins[task] = plugin_name
    try:
        done, pending = await asyncio.wait(task_plugins, timeout=execution_budget_sec)
    except asyncio.CancelledError:
        await uncancel_then_cleanup(
            cancel_and_await(
                list(task_plugins),
                timeout_sec=DEFAULT_CANCELLATION_TIMEOUT_SEC,
            ),
        )
        raise
    failures: dict[str, str] = {}
    if pending:
        for task in pending:
            plugin_name = task_plugins[task]
            failures[plugin_name] = "stop operation exceeded the shutdown deadline"
        await cancel_and_await(
            list(pending),
            timeout_sec=deadline.remaining_seconds(),
        )
    logger = get_logger(LOGGER_NAME)
    for task in done:
        plugin_name = task_plugins[task]
        if task.cancelled():
            failures[plugin_name] = "stop operation was cancelled"
            continue
        exception = task.exception()
        if exception is not None:
            if not isinstance(exception, Exception):
                raise exception
            failures[plugin_name] = type(exception).__name__
            coerced = coerce_to_soai_error(exception, operation=OPERATION)
            log_exception(
                logger,
                coerced,
                message=f"Shutdown stop failed for plugin '{plugin_name}'.",
                operation=OPERATION,
                details={"plugin": plugin_name},
            )
            continue
        outcome = task.result()
        if not isinstance(outcome, PluginStopOutcome):
            failures[plugin_name] = "stop operation returned an invalid outcome"
            continue
        if not outcome.terminated:
            failures[plugin_name] = outcome.message or "plugin did not terminate"
    if failures:
        diagnostics = "; ".join(
            f"{plugin_name}: {failures[plugin_name]}" for plugin_name in sorted(failures)
        )
        raise StateError(f"Shutdown plugin stop failed: {diagnostics}")

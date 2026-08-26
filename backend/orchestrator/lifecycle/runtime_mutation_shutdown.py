"""SoAI - Runtime mutation actor shutdown [backend/orchestrator/lifecycle/runtime_mutation_shutdown.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.task_groups import cancel_and_await
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from orchestrator.lifecycle.runtime_mutation_dependencies import (
    OrchestratorLifecycleRuntimeMutationsDependencies,
)
from orchestrator.lifecycle.runtime_mutation_state import (
    ConfigReloadRuntimeMutationCommand,
    PluginRuntimeMutationEntry,
)
from orchestrator.lifecycle.runtime_mutation_worker import publish_dropped_reload_events

if TYPE_CHECKING:
    from orchestrator.lifecycle.runtime_mutation_types import (
        DroppedReloadRuntimeMutation,
        RuntimeMutationFuture,
    )

__all__ = ("shutdown_runtime_mutations",)

LOGGER_NAME = "SoAI.orchestrator.lifecycle.runtime_mutation_shutdown"
OPERATION_SHUTDOWN_RUNTIME_MUTATIONS = "orchestrator.lifecycle.runtime_mutations.shutdown"


async def shutdown_runtime_mutations(
    *,
    deps: OrchestratorLifecycleRuntimeMutationsDependencies,
    entries: dict[str, PluginRuntimeMutationEntry],
    entries_lock: asyncio.Lock,
    timeout_seconds: float,
) -> None:
    logger = get_logger(LOGGER_NAME)
    worker_tasks: list[asyncio.Task[None]] = []
    dropped_reloads: list[DroppedReloadRuntimeMutation] = []
    futures_to_fail: list[RuntimeMutationFuture] = []
    async with entries_lock:
        for plugin_name, entry in list(entries.items()):
            entry.discard_reason = "Runtime mutations are shutting down."
            worker_task = entry.worker_task
            if worker_task is not None:
                worker_tasks.append(worker_task)
            _collect_entry_shutdown_work(
                plugin_name=plugin_name,
                entry=entry,
                dropped_reloads=dropped_reloads,
                futures_to_fail=futures_to_fail,
            )
            entry.pending.clear()
        entries.clear()
    publication_error: Exception | None = None
    try:
        await publish_dropped_reload_events(dropped_reloads=dropped_reloads, deps=deps)
    except RECOVERABLE_EXCEPTIONS as exception:
        publication_error = coerce_to_soai_error(
            exception,
            operation=OPERATION_SHUTDOWN_RUNTIME_MUTATIONS,
        )
        log_exception(
            logger,
            publication_error,
            message="Runtime mutation shutdown failed while publishing dropped reload events.",
            operation=OPERATION_SHUTDOWN_RUNTIME_MUTATIONS,
        )
    finally:
        _fail_runtime_mutation_futures(futures_to_fail)
        await uncancel_then_cleanup(
            cancel_and_await(
                tasks=worker_tasks,
                logger=logger,
                task_label="runtime mutation workers",
                timeout_sec=timeout_seconds,
            ),
        )
    if publication_error is not None:
        raise publication_error


def _collect_entry_shutdown_work(
    *,
    plugin_name: str,
    entry: PluginRuntimeMutationEntry,
    dropped_reloads: list[DroppedReloadRuntimeMutation],
    futures_to_fail: list[RuntimeMutationFuture],
) -> None:
    if entry.active_future is not None:
        futures_to_fail.append(entry.active_future)
    for queued_command in entry.pending:
        if isinstance(queued_command.command, ConfigReloadRuntimeMutationCommand):
            dropped_reloads.append(
                (
                    queued_command.command.event,
                    queued_command.future,
                    f"discarded because orchestrator shutdown cancelled {plugin_name} mutations",
                ),
            )
            continue
        futures_to_fail.append(queued_command.future)


def _fail_runtime_mutation_futures(futures: list[RuntimeMutationFuture]) -> None:
    for future in futures:
        if not future.done():
            future.set_exception(
                StateError(
                    "Runtime mutation was cancelled because orchestrator shutdown is in progress.",
                    operation=OPERATION_SHUTDOWN_RUNTIME_MUTATIONS,
                ),
            )

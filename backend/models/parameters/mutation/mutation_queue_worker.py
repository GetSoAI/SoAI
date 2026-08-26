"""SoAI - Per-model mutation worker loop for parameter mutation service [backend/models/parameters/mutation/mutation_queue_worker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.concurrency.lock_registry import TTLAsyncLockRegistry
from core.concurrency.locks import (
    BoundedLockContext,
    bounded_lock_for_cleanup,
)
from core.concurrency.queue_ops import drain_queue_to_list
from core.concurrency.queue_race import (
    QueueRaceOutcome,
    race_queue_operation_against_signals,
)
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ServiceUnavailableError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import UNEXPECTED_RUNTIME_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.timing.constants import ASYNC_POLL_SLICE_SEC, YIELD_CONTROL_SEC
from models.parameters.mutation.types import MutationQueueItem
from models.parameters.mutation_ordering import MutationOrderTracker

if TYPE_CHECKING:
    from models.parameters.mutation_ordering import MutationCallable

__all__ = ("run_mutation_queue_worker",)

OPERATION = "models.parameters.mutation.mutation_queue_worker.process_mutation"


async def run_mutation_queue_worker(
    *,
    universal_id: str,
    queue: asyncio.PriorityQueue[MutationQueueItem],
    shutdown_event: asyncio.Event,
    mutation_queue_locks: TTLAsyncLockRegistry[str],
    mutation_queues: dict[str, asyncio.PriorityQueue[MutationQueueItem]],
    mutation_tasks: dict[str, asyncio.Task[None]],
    mutation_tasks_lock: asyncio.Lock,
    mutation_executor: Callable[[str, str, int | None, MutationCallable], Awaitable[None]],
    order_tracker: MutationOrderTracker,
    logger: LoggerProtocol,
    mutation_idle_timeout: float,
) -> None:
    task_removed_from_registry = False
    try:
        while True:
            race_result = await race_queue_operation_against_signals(
                queue.get(),
                (),
                timeout_seconds=mutation_idle_timeout,
            )
            if race_result.outcome is not QueueRaceOutcome.OPERATION_COMPLETED:
                async with mutation_queue_locks.lock(universal_id):
                    if not queue.empty():
                        continue
                    async with BoundedLockContext(mutation_tasks_lock) as exit_lock_result:
                        if exit_lock_result.acquired and queue.empty():
                            mutation_tasks.pop(universal_id, None)
                            task_removed_from_registry = True
                            break
                continue
            mutation_entry = race_result.value
            if mutation_entry is None:
                continue
            (
                order_key,
                strict_order,
                mutation_key,
                mutation_value,
                mutation_callable,
                future,
            ) = mutation_entry
            order_base = order_key[0] if isinstance(order_key, tuple) else order_key
            expected = order_tracker.get_expected_order(universal_id)
            if strict_order and expected is not None and (order_base != expected):
                async with mutation_queue_locks.lock(universal_id):
                    queue.put_nowait(mutation_entry)
                queue.task_done()
                if not await order_tracker.wait_for_order(
                    universal_id,
                    shutdown_event=shutdown_event,
                ):
                    break
                continue
            try:
                await mutation_executor(
                    universal_id,
                    mutation_key,
                    mutation_value,
                    mutation_callable,
                )
                if not future.done():
                    future.set_result(None)
            except asyncio.CancelledError as exception:
                if not future.done():
                    future.set_exception(exception)
                raise
            except RECOVERABLE_EXCEPTIONS as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message="Mutation execution failed; surfaced on mutation future (non-critical).",
                    operation=OPERATION,
                    details={
                        "universal_id": universal_id,
                        "mutation_key": str(mutation_key),
                    },
                    level="debug",
                )
                if not future.done():
                    future.set_exception(exception)
            except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
                coerced = coerce_to_soai_error(
                    exception,
                    operation="models.parameters.mutation.mutation_queue_worker.process_mutation",
                )
                log_exception(
                    logger,
                    coerced,
                    message="Mutation execution raised an unexpected exception; surfaced on mutation future.",
                    operation=OPERATION,
                    details={
                        "universal_id": universal_id,
                        "mutation_key": str(mutation_key),
                    },
                    level="error",
                )
                if not future.done():
                    future.set_exception(coerced)
            finally:
                order_tracker.advance_expected_order(
                    universal_id,
                    completed_base=order_base,
                    strict_order=strict_order,
                )
                queue.task_done()
                await asyncio.sleep(YIELD_CONTROL_SEC)
    finally:
        if not task_removed_from_registry:
            queue_detached = False
            async with mutation_queue_locks.bounded_lock_for_cleanup(
                universal_id,
                ASYNC_POLL_SLICE_SEC,
            ) as queue_lock_result:
                async with bounded_lock_for_cleanup(mutation_tasks_lock) as tasks_lock_result:
                    if tasks_lock_result.acquired:
                        mutation_tasks.pop(universal_id, None)
                if queue_lock_result.acquired and mutation_queues.get(universal_id) is queue:
                    mutation_queues.pop(universal_id, None)
                    queue_detached = True
            if queue_detached:
                drain_error = ServiceUnavailableError(
                    "Parameter mutation worker shut down before this mutation could be processed.",
                )
                remaining_entries = drain_queue_to_list(queue)
                for remaining_entry in remaining_entries:
                    remaining_future: asyncio.Future[None] = remaining_entry[5]
                    if not remaining_future.done():
                        remaining_future.set_exception(drain_error)
                if remaining_entries:
                    logger.debug(
                        "Drained %d pending mutation(s) for '%s' during worker shutdown.",
                        len(remaining_entries),
                        universal_id,
                    )
        order_tracker.clear_universal_id(universal_id)

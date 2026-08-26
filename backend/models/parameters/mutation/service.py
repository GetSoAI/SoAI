"""SoAI - Batched async parameter updates with ordering [backend/models/parameters/mutation/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.lock_registry import (
    TTLAsyncLockRegistry,
    TTLAsyncLockRegistryDependencies,
)
from core.concurrency.queue_ops import drain_queue_to_list
from core.errors.exceptions import ServiceUnavailableError
from core.runtime.soai_identifiers import build_soai_id, safe_or_hashed_segment
from models.parameters.mutation.dependencies import ParameterMutationServiceDependencies
from models.parameters.mutation.mutation_queue_worker import run_mutation_queue_worker
from models.parameters.mutation.types import MutationQueueItem, UpdateQueuePayload
from models.parameters.mutation.update_queue_submission import (
    enqueue_parameter_delete,
    enqueue_parameter_update,
)
from models.parameters.mutation.update_queue_worker import (
    run_parameter_update_queue_worker,
    signal_update_workers_shutdown,
)
from models.parameters.mutation_ordering import MutationOrderTracker

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.types.json import JSONDict
    from models.parameters.mutation_ordering import MutationCallable

__all__ = ("ParameterMutationService",)


class ParameterMutationService:

    def __init__(self, deps: ParameterMutationServiceDependencies) -> None:
        self._logger = deps.logger
        self._shutdown_event = deps.shutdown_event
        self._spawn_tracked_task = deps.spawn_tracked_task
        self._cancellation_binder = deps.cancellation_binder
        self._finalizer_tracker = deps.finalizer_tracker
        self._num_workers = deps.num_workers
        self._update_executor = deps.update_executor
        self._delete_executor = deps.delete_executor
        self._mutation_executor = deps.mutation_executor
        self._task_registry = deps.task_registry
        self._update_queue: asyncio.Queue[tuple[str, UpdateQueuePayload] | None] = asyncio.Queue(
            maxsize=max(1, int(deps.update_queue_max_size)),
        )
        self._workers: list[asyncio.Task[None]] = []
        self._lifecycle_lock = asyncio.Lock()
        self._accepting_mutations = True
        self._mutation_tasks: dict[str, asyncio.Task[None]] = {}
        self._mutation_tasks_lock = asyncio.Lock()
        self._mutation_queues: dict[str, asyncio.PriorityQueue[MutationQueueItem]] = {}
        self._mutation_queue_locks: TTLAsyncLockRegistry[str] = TTLAsyncLockRegistry(
            TTLAsyncLockRegistryDependencies(
                ttl_seconds=3600.0,
                max_size=2000,
                cleanup_interval_seconds=300.0,
            ),
        )
        self._mutation_idle_timeout = max(0.1, float(deps.mutation_idle_timeout))
        self._order_tracker = MutationOrderTracker()
        self._mutation_worker_semaphore = asyncio.Semaphore(deps.max_mutation_workers)

    async def start(self) -> None:
        async with self._lifecycle_lock:
            if self._workers:
                return
            self._accepting_mutations = True
            for worker_index in range(self._num_workers):
                self._workers.append(
                    self._spawn_tracked_task(
                        run_parameter_update_queue_worker(
                            update_queue=self._update_queue,
                            update_executor=self._update_executor,
                            delete_executor=self._delete_executor,
                            task_registry=self._task_registry,
                            logger=self._logger,
                            shutdown_event=self._shutdown_event,
                        ),
                        name=f"model-manager-param-worker-{worker_index}",
                        cancellation_binder=self._cancellation_binder,
                        cancellation_id=build_soai_id(
                            (
                                "sys",
                                "model_manager",
                                "param_worker",
                                safe_or_hashed_segment(str(worker_index)),
                            ),
                        ),
                        owner="model_parameter_worker",
                        metadata={"worker_id": worker_index},
                        finalizer_tracker=self._finalizer_tracker,
                    ),
                )

    async def shutdown(self) -> None:
        async with self._lifecycle_lock:
            self._accepting_mutations = False
            await signal_update_workers_shutdown(
                update_queue=self._update_queue,
                logger=self._logger,
                num_workers=len(self._workers),
            )
            if self._workers:
                cleanup_results = await asyncio.gather(*self._workers, return_exceptions=True)
                for cleanup_result in cleanup_results:
                    if isinstance(cleanup_result, asyncio.CancelledError):
                        continue
                    if isinstance(cleanup_result, BaseException):
                        self._logger.debug(
                            "Parameter update worker raised during shutdown cleanup (non-critical): %s",
                            str(cleanup_result),
                        )
            self._workers.clear()
            for task in list(self._mutation_tasks.values()):
                task.cancel()
            if self._mutation_tasks:
                cleanup_results = await asyncio.gather(
                    *self._mutation_tasks.values(),
                    return_exceptions=True,
                )
                for cleanup_result in cleanup_results:
                    if isinstance(cleanup_result, asyncio.CancelledError):
                        continue
                    if isinstance(cleanup_result, BaseException):
                        self._logger.debug(
                            "Parameter mutation worker raised during shutdown cleanup (non-critical): %s",
                            str(cleanup_result),
                        )
            self._mutation_tasks.clear()
            drain_error = ServiceUnavailableError(
                "Parameter mutation service shut down before this mutation could be processed.",
            )
            for mutation_queue in self._mutation_queues.values():
                for remaining_entry in drain_queue_to_list(mutation_queue):
                    remaining_future: asyncio.Future[None] = remaining_entry[5]
                    if not remaining_future.done():
                        remaining_future.set_exception(drain_error)
            self._mutation_queues.clear()
            await self._mutation_queue_locks.clear()

    async def enqueue_update(
        self,
        universal_id: str,
        parameters: JSONDict,
        reply_channel: asyncio.Queue[Event],
    ) -> None:
        async with self._lifecycle_lock:
            if not self._accepting_mutations:
                raise ServiceUnavailableError("Parameter mutation service is shut down.")
            await enqueue_parameter_update(
                update_queue=self._update_queue,
                order_tracker=self._order_tracker,
                universal_id=universal_id,
                parameters=parameters,
                reply_channel=reply_channel,
            )

    async def enqueue_delete(
        self,
        universal_id: str,
        keys: list[str],
        reply_channel: asyncio.Queue[Event],
    ) -> None:
        async with self._lifecycle_lock:
            if not self._accepting_mutations:
                raise ServiceUnavailableError("Parameter mutation service is shut down.")
            await enqueue_parameter_delete(
                update_queue=self._update_queue,
                order_tracker=self._order_tracker,
                universal_id=universal_id,
                keys=keys,
                reply_channel=reply_channel,
            )

    async def mutate(
        self,
        universal_id: str,
        *,
        metric_key: str,
        metric_value: int | None = None,
        mutation: MutationCallable,
        order: int | None = None,
    ) -> None:
        future: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        strict_order = order is not None
        normalized = self._order_tracker.normalize_mutation_callable(mutation)
        queue: asyncio.PriorityQueue[MutationQueueItem] | None = None
        should_start_worker = False
        async with self._lifecycle_lock:
            if not self._accepting_mutations:
                raise ServiceUnavailableError("Parameter mutation service is shut down.")
            async with self._mutation_queue_locks.lock(universal_id):
                queue = self._mutation_queues.get(universal_id)
                if queue is None:
                    queue = asyncio.PriorityQueue()
                    self._mutation_queues[universal_id] = queue
            async with self._mutation_tasks_lock:
                existing_task = self._mutation_tasks.get(universal_id)
                should_start_worker = existing_task is None or existing_task.done()
            if not should_start_worker:
                key = self._order_tracker.determine_order(universal_id, order)
                queue.put_nowait((key, strict_order, metric_key, metric_value, normalized, future))
                if strict_order and self._order_tracker.get_expected_order(universal_id) == key[0]:
                    self._order_tracker.notify_order_ready(universal_id)
        if should_start_worker:
            semaphore_acquired = False
            worker_started = False
            try:
                await self._mutation_worker_semaphore.acquire()
                semaphore_acquired = True
                async with self._lifecycle_lock:
                    if not self._accepting_mutations:
                        raise ServiceUnavailableError("Parameter mutation service is shut down.")
                    async with self._mutation_queue_locks.lock(universal_id):
                        queue = self._mutation_queues.get(universal_id)
                        if queue is None:
                            queue = asyncio.PriorityQueue()
                            self._mutation_queues[universal_id] = queue
                        key = self._order_tracker.determine_order(universal_id, order)
                        queue.put_nowait(
                            (key, strict_order, metric_key, metric_value, normalized, future),
                        )
                        if (
                            strict_order
                            and self._order_tracker.get_expected_order(universal_id) == key[0]
                        ):
                            self._order_tracker.notify_order_ready(universal_id)
                    async with self._mutation_tasks_lock:
                        existing_task = self._mutation_tasks.get(universal_id)
                        if existing_task is None or existing_task.done():
                            self._mutation_tasks[universal_id] = self._spawn_tracked_task(
                                self._bounded_mutation_worker(universal_id, queue),
                                name=f"model-manager-parameter-mutation-{universal_id}",
                                logger=self._logger,
                                cancellation_binder=self._cancellation_binder,
                                cancellation_id=build_soai_id(
                                    (
                                        "sys",
                                        "model_manager",
                                        "parameter_mutation",
                                        safe_or_hashed_segment(str(universal_id)),
                                    ),
                                ),
                                owner="model_parameter_mutation_worker",
                                metadata={"universal_id": universal_id},
                                finalizer_tracker=self._finalizer_tracker,
                            )
                            worker_started = True
            finally:
                if semaphore_acquired and not worker_started:
                    self._mutation_worker_semaphore.release()
        await future

    async def _bounded_mutation_worker(
        self,
        universal_id: str,
        queue: asyncio.PriorityQueue[MutationQueueItem],
    ) -> None:
        try:
            await run_mutation_queue_worker(
                universal_id=universal_id,
                queue=queue,
                shutdown_event=self._shutdown_event,
                mutation_queue_locks=self._mutation_queue_locks,
                mutation_queues=self._mutation_queues,
                mutation_tasks=self._mutation_tasks,
                mutation_tasks_lock=self._mutation_tasks_lock,
                mutation_executor=self._mutation_executor,
                order_tracker=self._order_tracker,
                logger=self._logger,
                mutation_idle_timeout=self._mutation_idle_timeout,
            )
        finally:
            self._mutation_worker_semaphore.release()

"""SoAI - Continuous durable RAG job lease heartbeat [backend/mcp/worker/processing/durable_job_heartbeat.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.task_groups import cancel_and_await
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.rag.job_operations import rag_job_lease_lost_details
from core.timing.epoch import epoch_ms
from mcp.worker.processing.durable_job_runtime import durable_processing_lease_ttl_seconds
from mcp.worker.processing.job_execution import execute_processing_job

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Coroutine

    from core.logging.protocols import LoggerProtocol
    from mcp.worker.internal_protocols import MCPWorkerProtocol
    from mcp.worker.processing.durable_job_runtime import DurableProcessingLease
    from mcp.worker.processing.job_parsing import ParsedProcessingJob

    type LeaseRenewal = Callable[[str, str], Awaitable[bool]]

__all__ = (
    "DurableJobLeaseHeartbeat",
    "execute_with_durable_lease",
    "run_with_durable_job_heartbeat",
)


class DurableJobLeaseHeartbeat:
    def __init__(
        self,
        *,
        job_id: str,
        lease_token: str,
        lease_ttl_seconds: float,
        renew: LeaseRenewal,
    ) -> None:
        self._job_id = job_id
        self._lease_token = lease_token
        self._lease_ttl_seconds = lease_ttl_seconds
        self._renew = renew
        self._stop_event = asyncio.Event()

    async def stop(self) -> None:
        self._stop_event.set()

    @property
    def wait_timeout_seconds(self) -> float:
        return max(0.001, self._lease_ttl_seconds / 3.0)

    async def run(self) -> None:
        interval = self.wait_timeout_seconds
        safe_margin = max(0.001, self._lease_ttl_seconds / 6.0)
        confirmed_expiry = time.monotonic() + self._lease_ttl_seconds
        while not self._stop_event.is_set():
            if await self._wait_for_stop(interval):
                return
            backoff = min(0.01, interval)
            while True:
                try:
                    renewal_started = time.monotonic()
                    renewal_timeout = confirmed_expiry - safe_margin - renewal_started
                    if renewal_timeout <= 0:
                        raise StateError(
                            "RAG job lease ownership became unprovable.",
                            details=rag_job_lease_lost_details(),
                        )
                    renewed = await asyncio.wait_for(
                        self._renew(self._job_id, self._lease_token),
                        timeout=renewal_timeout,
                    )
                except RECOVERABLE_EXCEPTIONS as exception:
                    if time.monotonic() + backoff >= confirmed_expiry - safe_margin:
                        raise StateError(
                            "RAG job lease ownership became unprovable.",
                            details=rag_job_lease_lost_details(),
                            cause=exception,
                        ) from exception
                    try:
                        await asyncio.wait_for(self._stop_event.wait(), timeout=backoff)
                        return
                    except TimeoutError:
                        backoff = min(1.0, interval, backoff * 2.0)
                        continue
                if not renewed:
                    raise StateError(
                        "RAG job lease is no longer current.",
                        details=rag_job_lease_lost_details(),
                    )
                confirmed_expiry = renewal_started + self._lease_ttl_seconds
                break

    async def _wait_for_stop(self, timeout_seconds: float) -> bool:
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=timeout_seconds)
        except TimeoutError:
            return False
        return True


async def run_with_durable_job_heartbeat[T](
    processing: Coroutine[None, None, T],
    heartbeat: DurableJobLeaseHeartbeat,
) -> T:
    processing_task = asyncio.create_task(processing, name="durable-rag-processing")
    heartbeat_task = asyncio.create_task(heartbeat.run(), name="durable-rag-lease-heartbeat")

    async def stop_and_join() -> None:
        await heartbeat.stop()
        if not heartbeat_task.done():
            heartbeat_task.cancel()
        if not processing_task.done():
            processing_task.cancel()
        await cancel_and_await(
            (processing_task, heartbeat_task),
            task_label="durable RAG processing and heartbeat tasks",
        )

    try:
        while True:
            done, _pending = await asyncio.wait(
                (processing_task, heartbeat_task),
                return_when=asyncio.FIRST_COMPLETED,
                timeout=heartbeat.wait_timeout_seconds,
            )
            if done:
                break
        if processing_task in done:
            return await processing_task
        if heartbeat_task in done:
            heartbeat_error = heartbeat_task.exception()
            if heartbeat_error is not None:
                await cancel_and_await(
                    (processing_task,),
                    task_label="durable RAG processing task",
                )
                raise heartbeat_error
        return await processing_task
    finally:
        await uncancel_then_cleanup(stop_and_join())


async def execute_with_durable_lease(
    worker: MCPWorkerProtocol,
    parsed: ParsedProcessingJob,
    lease: DurableProcessingLease,
    *,
    logger: LoggerProtocol,
) -> str | None:
    ttl_seconds = durable_processing_lease_ttl_seconds(worker)

    async def renew(job_id: str, lease_token: str) -> bool:
        return await worker.database_files.renew_rag_job_lease(
            job_id,
            lease_token,
            int(epoch_ms()) + ttl_seconds * 1000,
            int(epoch_ms()),
        )

    return await run_with_durable_job_heartbeat(
        execute_processing_job(worker, parsed, logger=logger),
        DurableJobLeaseHeartbeat(
            job_id=lease.job_id,
            lease_token=lease.lease_token,
            lease_ttl_seconds=ttl_seconds,
            renew=renew,
        ),
    )

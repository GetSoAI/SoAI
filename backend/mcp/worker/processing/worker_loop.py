"""SoAI - MCP document processing worker loop [backend/mcp/worker/processing/worker_loop.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from core.concurrency.cancellation import TaskCancelledError
from core.concurrency.queue_race import (
    QueueRaceOutcome,
    race_queue_operation_against_signals,
)
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import UNEXPECTED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.metrics.keyspace_paths_mcp_rag import MCP_RAG_GAUGE_PROCESSING_QUEUE_SIZE
from core.rag.job_operations import RAGJobStatus
from core.timing.constants import STANDARD_DELAY_SEC
from core.timing.epoch import epoch_ms
from mcp.worker.metrics_reporting import record_worker_metric_gauge
from mcp.worker.processing.durable_job_heartbeat import (
    execute_with_durable_lease,
)
from mcp.worker.processing.durable_job_runtime import (
    DurableProcessingLease,
    acquire_durable_processing_lease,
    finalize_durable_processing_job,
    is_durable_processing_lease_lost,
    release_durable_processing_lease,
)
from mcp.worker.processing.job_cancellation_postmortem import (
    finalize_worker_cancellation,
    handle_token_cancellation,
)
from mcp.worker.processing.job_execution import execute_processing_job
from mcp.worker.processing.job_parsing import parse_processing_job
from mcp.worker.processing.job_postmortem import handle_processing_failure

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = ("processing_worker",)

LOGGER_NAME = "SoAI.mcp.worker.worker_loop"
OPERATION = "mcp.worker.processing_worker"
_DURABLE_SCAN_EXCEPTIONS: tuple[type[Exception], ...] = (*RECOVERABLE_EXCEPTIONS, SoAIError)


async def processing_worker(self: MCPWorkerProtocol, worker_id: int) -> None:
    logger = get_logger(LOGGER_NAME)
    logger.debug("RAG worker %s started", worker_id)
    try:
        while not self.shutdown_event.is_set():
            try:
                race_result = await race_queue_operation_against_signals(
                    self.processing_queue.get(),
                    (self.shutdown_event,),
                    timeout_seconds=STANDARD_DELAY_SEC,
                )
            except asyncio.CancelledError:
                logger.debug("Worker %s received cancellation signal", worker_id)
                raise
            except RECOVERABLE_EXCEPTIONS as error:
                log_exception(
                    logger,
                    error,
                    message=f"Worker {worker_id} queue get error",
                    operation=OPERATION,
                )
                await asyncio.sleep(STANDARD_DELAY_SEC)
                continue
            queue_item_received = race_result.outcome is QueueRaceOutcome.OPERATION_COMPLETED
            if race_result.outcome is QueueRaceOutcome.SIGNAL_FIRED:
                break
            if queue_item_received:
                job = race_result.value
            else:
                try:
                    jobs = await self.database_files.list_claimable_rag_processing_jobs(
                        now_ms=int(epoch_ms()),
                        limit=1,
                    )
                except _DURABLE_SCAN_EXCEPTIONS as error:
                    log_exception(
                        logger,
                        error,
                        message=f"Worker {worker_id} durable RAG job scan failed",
                        operation=OPERATION,
                    )
                    await asyncio.sleep(STANDARD_DELAY_SEC)
                    continue
                if not jobs:
                    continue
                job_record = jobs[0]
                job = {
                    "job_id": job_record["job_id"],
                    "type": job_record["job_type"],
                    "task_id": job_record["task_id"],
                }
            temp_file: str | None = None
            job_type: str | None = None
            task_id_for_logs: str | None = None
            document_id_for_logs: str | None = None
            job_payload: JSONDict | None = None
            durable_lease: DurableProcessingLease | None = None
            remove_temp_file = True
            try:
                try:
                    parsed = parse_processing_job(job)
                except ValueError as exception:
                    raise ValidationError(str(exception), cause=exception) from exception
                if parsed is None:
                    logger.warning(
                        "Worker %s received non-dict job: %s",
                        worker_id,
                        type(job).__name__ if job is not None else "None",
                    )
                    continue
                durable_lease = await acquire_durable_processing_lease(
                    self,
                    parsed,
                    worker_id=worker_id,
                )
                if parsed.job_id is not None and durable_lease is None:
                    continue
                active_parsed = durable_lease.parsed if durable_lease is not None else parsed
                job_payload = active_parsed.payload
                temp_file = active_parsed.temp_file
                task_id_for_logs = active_parsed.task_id
                job_type = active_parsed.job_type
                try:
                    if durable_lease is None:
                        document_id_for_logs = await execute_processing_job(
                            self,
                            active_parsed,
                            logger=logger,
                        )
                    else:
                        document_id_for_logs = await execute_with_durable_lease(
                            self,
                            active_parsed,
                            durable_lease,
                            logger=logger,
                        )
                except ValueError as exception:
                    raise ValidationError(str(exception), cause=exception) from exception
                finalized = await finalize_durable_processing_job(
                    self,
                    durable_lease,
                    status=RAGJobStatus.COMPLETED,
                    error_message=None,
                )
                if not finalized:
                    remove_temp_file = False
            except asyncio.CancelledError:
                logger.debug(
                    "Worker %s cancelled for task %s",
                    worker_id,
                    task_id_for_logs or "unknown",
                )
                if durable_lease is not None:
                    remove_temp_file = False
                    await release_durable_processing_lease(self, durable_lease)
                else:
                    await finalize_worker_cancellation(
                        self,
                        worker_id=worker_id,
                        task_id=task_id_for_logs,
                        job_type=job_type,
                        document_id=document_id_for_logs,
                        job_payload=job_payload,
                        logger=logger,
                    )
                raise
            except TaskCancelledError as cancelled_error:
                postmortem_owned = await handle_token_cancellation(
                    self,
                    cancelled_error,
                    worker_id=worker_id,
                    task_id=task_id_for_logs,
                    job_type=job_type,
                    document_id=document_id_for_logs,
                    job_payload=job_payload,
                    logger=logger,
                )
                if not postmortem_owned:
                    remove_temp_file = False
                    continue
                finalized = await finalize_durable_processing_job(
                    self,
                    durable_lease,
                    status=RAGJobStatus.CANCELLED,
                    error_message=cancelled_error.reason,
                )
                if not finalized:
                    remove_temp_file = False
            except SoAIError as error:
                if durable_lease is not None and is_durable_processing_lease_lost(error):
                    remove_temp_file = False
                    continue
                log_exception(
                    logger,
                    error,
                    message=f"Error processing job {job_type}",
                    operation=OPERATION,
                    details={
                        "job_type": job_type,
                        "task_id": task_id_for_logs,
                        "worker_id": worker_id,
                    },
                )
                postmortem_owned = await handle_processing_failure(
                    self,
                    error,
                    worker_id=worker_id,
                    task_id=task_id_for_logs,
                    job_type=job_type,
                    document_id=document_id_for_logs,
                    job_payload=job_payload,
                    logger=logger,
                )
                if not postmortem_owned:
                    remove_temp_file = False
                    continue
                finalized = await finalize_durable_processing_job(
                    self,
                    durable_lease,
                    status=RAGJobStatus.FAILED,
                    error_message=error.message,
                )
                if not finalized:
                    remove_temp_file = False
            except UNEXPECTED_RUNTIME_EXCEPTIONS as error:
                coerced = coerce_to_soai_error(error, operation=OPERATION)
                log_exception(
                    logger,
                    coerced,
                    message=f"Unexpected error processing job {job_type}",
                    operation=OPERATION,
                    details={
                        "job_type": job_type,
                        "task_id": task_id_for_logs,
                        "worker_id": worker_id,
                    },
                )
                postmortem_owned = await handle_processing_failure(
                    self,
                    error,
                    worker_id=worker_id,
                    task_id=task_id_for_logs,
                    job_type=job_type,
                    document_id=document_id_for_logs,
                    job_payload=job_payload,
                    logger=logger,
                )
                if not postmortem_owned:
                    remove_temp_file = False
                    continue
                finalized = await finalize_durable_processing_job(
                    self,
                    durable_lease,
                    status=RAGJobStatus.FAILED,
                    error_message=coerced.message,
                )
                if not finalized:
                    remove_temp_file = False
            finally:
                if queue_item_received:
                    self.processing_queue.task_done()
                record_worker_metric_gauge(
                    self.metrics,
                    logger,
                    MCP_RAG_GAUGE_PROCESSING_QUEUE_SIZE,
                    operation=OPERATION,
                    details={"worker_id": worker_id},
                    value=self.processing_queue.qsize(),
                )
                if temp_file and remove_temp_file:
                    try:
                        os.remove(temp_file)
                    except OSError as error:
                        logger.debug(
                            "Failed to remove temp file %s: %s",
                            temp_file,
                            str(error),
                        )
    finally:
        logger.debug("RAG worker %s stopped", worker_id)

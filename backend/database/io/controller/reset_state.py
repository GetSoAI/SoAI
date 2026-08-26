"""SoAI - DB controller reset helpers [backend/database/io/controller/reset_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from queue import Empty, Queue

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.logging.protocols import LoggerProtocol
from core.logging.trace import get_logger
from database.io.internal_protocols import (
    DatabaseWriteJobProtocol,
    OperationStatus,
    ShutdownSentinel,
)
from database.io.operation_status_tracker import OperationStatusTracker

__all__ = (
    "cancel_active_jobs",
    "drain_pending_items",
    "mark_active_jobs_outcome_unknown",
)

LOGGER_NAME = "SoAI.database.io.reset_state"
OPERATION_DATABASE_IO_CONTROLLER_RESET_ACTIVE_JOB = "database.io.controller.reset.active_job"
OPERATION_DATABASE_IO_CONTROLLER_RESET_DRAIN_QUEUE = "database.io.controller.reset.drain_queue"


def drain_pending_items(
    queue: Queue[DatabaseWriteJobProtocol | type[ShutdownSentinel]],
    status_tracker: OperationStatusTracker,
) -> None:
    logger = get_logger(LOGGER_NAME)
    while True:
        try:
            item = queue.get_nowait()
        except Empty:
            break
        if isinstance(item, type):
            queue.task_done()
            continue
        job: DatabaseWriteJobProtocol = item
        try:
            if status_tracker.record_if_not_terminal(
                job.operation_id,
                OperationStatus.SKIPPED,
                error_type="WriterSessionReset",
            ):
                job.resolve_unavailable()
        except (OSError, RuntimeError) as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation="database.io.controller.reset.drain_queue",
            )
            log_exception(
                logger,
                coerced,
                message="Failed to mark queued database operation unavailable during reset.",
                operation=OPERATION_DATABASE_IO_CONTROLLER_RESET_DRAIN_QUEUE,
                level="warning",
            )
        finally:
            queue.task_done()


def cancel_active_jobs(
    status_tracker: OperationStatusTracker,
    logger: LoggerProtocol,
) -> None:
    active_jobs = status_tracker.pop_active_jobs()
    for operation_id, job in active_jobs:
        if job.cancelled is not None:
            job.cancelled.set()
        if not status_tracker.record_if_not_terminal(
            operation_id,
            OperationStatus.SKIPPED,
            error_type="WriterSessionReset",
        ):
            continue
        try:
            job.resolve_unavailable()
        except (OSError, RuntimeError) as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation="database.io.controller.reset.active_job",
            )
            log_handled_exception(
                logger,
                coerced,
                message="Failed to resolve active job while resetting database writer session (non-critical).",
                operation=OPERATION_DATABASE_IO_CONTROLLER_RESET_ACTIVE_JOB,
                level="debug",
            )


def mark_active_jobs_outcome_unknown(
    status_tracker: OperationStatusTracker,
    logger: LoggerProtocol,
) -> None:
    active_jobs = status_tracker.pop_active_jobs()
    for operation_id, job in active_jobs:
        if not status_tracker.record_if_not_terminal(
            operation_id,
            OperationStatus.OUTCOME_UNKNOWN,
            error_type="WriterShutdownTruthUnknown",
        ):
            continue
        try:
            job.resolve_unavailable()
        except (OSError, RuntimeError) as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation="database.io.controller.reset.active_job",
            )
            log_handled_exception(
                logger,
                coerced,
                message="Failed to resolve unknown-outcome job during database writer reset.",
                operation=OPERATION_DATABASE_IO_CONTROLLER_RESET_ACTIVE_JOB,
                level="debug",
            )

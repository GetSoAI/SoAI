"""SoAI - Durable mutation publication failure policy [backend/app/background/mutation_publication_failures.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError, StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_base import Event
from core.logging.trace import get_logger
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.protocols import TaskRegistryProtocol

__all__ = (
    "MUTATION_PUBLICATION_EXCEPTIONS",
    "drain_mutation_reply_queue",
    "finalize_failed_mutation_claim",
    "log_mutation_publication_failure",
)

LOGGER_NAME = "SoAI.app.background.mutation_publication_failures"
OPERATION = "mutation_command_execution.execute_claim"
MUTATION_PUBLICATION_EXCEPTIONS: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    SoAIError,
)


async def drain_mutation_reply_queue(
    reply_queue: asyncio.Queue[Event],
) -> None:
    while True:
        await reply_queue.get()


async def finalize_failed_mutation_claim(
    task_registry: TaskRegistryProtocol,
    *,
    request_id: str,
    task_id: str,
    fencing_token: int,
    exception: StateError,
    diagnostic_message: str,
    error_message: str,
    status_message: str,
) -> None:
    log_exception(
        get_logger(LOGGER_NAME),
        exception,
        message=diagnostic_message,
        operation=OPERATION,
        details={"request_id": request_id, "task_id": task_id},
        level="error",
    )
    await finalize(
        task_registry,
        task_id,
        TaskStatus.FAILED,
        error_message=error_message,
        status_message=status_message,
        mutation_fencing_token=fencing_token,
    )


def log_mutation_publication_failure(
    exception: Exception,
    *,
    attempt: int,
    task_id: str,
    was_enqueued: bool,
) -> None:
    log_exception(
        get_logger(LOGGER_NAME),
        exception,
        message=(
            "Durable mutation publication failed after enqueue; awaiting its outcome."
            if was_enqueued
            else "Durable mutation publication failed; retrying."
        ),
        operation=OPERATION,
        details={"attempt": attempt, "task_id": task_id},
        level="warning",
    )

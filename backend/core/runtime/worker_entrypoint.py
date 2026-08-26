"""SoAI - Worker entrypoint execution helpers [backend/core/runtime/worker_entrypoint.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.runtime.event_loop_runner import run_coroutine_in_new_event_loop

__all__ = ("run_worker_entrypoint",)

OPERATION_CORE_RUNTIME_WORKER_ENTRYPOINT_SOAI_ERROR = "core.runtime.worker_entrypoint.soai_error"


def run_worker_entrypoint[ResultT](
    awaitable: Awaitable[ResultT],
    *,
    logger: LoggerProtocol,
    unhandled_message: str,
    operation: str,
    unhandled_level: str = "critical",
    soai_error_message: str | None = None,
    soai_error_level: str = "critical",
) -> None:
    try:
        run_coroutine_in_new_event_loop(awaitable)
    except SoAIError as exception:
        if soai_error_message is not None:
            log_exception(
                logger,
                exception,
                message=soai_error_message,
                operation=OPERATION_CORE_RUNTIME_WORKER_ENTRYPOINT_SOAI_ERROR,
                level=soai_error_level,
            )
        raise
    except RECOVERABLE_EXCEPTIONS as exception:
        error = coerce_to_soai_error(exception, operation=operation)
        log_exception(
            logger,
            error,
            message=unhandled_message,
            operation=operation,
            level=unhandled_level,
        )
        raise error from exception

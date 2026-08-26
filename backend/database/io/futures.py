"""SoAI - Thread-safe asyncio.Future resolution helpers [backend/database/io/futures.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import StandardLogger

__all__ = (
    "resolve_future_exception_threadsafe",
    "resolve_future_result_threadsafe",
)

OPERATION = "database_core.resolve_future"


def resolve_future_result_threadsafe[T](
    future: asyncio.Future[T],
    *,
    logger: StandardLogger,
    result: T,
) -> None:
    if future.done():
        return
    loop = future.get_loop()

    def _finalize() -> None:
        if future.done():
            return
        try:
            future.set_result(result)
        except asyncio.InvalidStateError:
            logger.debug("Future already resolved, skipping duplicate resolution.")
        except RECOVERABLE_EXCEPTIONS as finalize_error:
            log_exception(
                logger,
                finalize_error,
                message="Failed to finalize database future",
                operation=OPERATION,
            )
            if not future.done():
                future.cancel()

    try:
        loop.call_soon_threadsafe(_finalize)
    except RuntimeError as loop_unavailable_error:
        logger.warning(
            "Event loop unavailable for future resolution: %s",
            str(loop_unavailable_error),
        )


def resolve_future_exception_threadsafe[T](
    future: asyncio.Future[T],
    *,
    logger: StandardLogger,
    exception: BaseException,
) -> None:
    if future.done():
        return
    loop = future.get_loop()

    def _finalize() -> None:
        if future.done():
            return
        try:
            future.set_exception(exception)
        except asyncio.InvalidStateError:
            logger.debug("Future already resolved, skipping duplicate resolution.")
        except RECOVERABLE_EXCEPTIONS as finalize_error:
            log_exception(
                logger,
                finalize_error,
                message="Failed to finalize database future",
                operation=OPERATION,
            )
            if not future.done():
                future.cancel()

    try:
        loop.call_soon_threadsafe(_finalize)
    except RuntimeError as loop_unavailable_error:
        logger.warning(
            "Event loop unavailable for future resolution: %s",
            str(loop_unavailable_error),
        )

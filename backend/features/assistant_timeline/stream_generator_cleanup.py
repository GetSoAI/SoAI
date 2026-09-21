"""SoAI - Assistant timeline stream generator cleanup [backend/features/assistant_timeline/stream_generator_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import (
    HANDLED_RUNTIME_EXCEPTIONS,
    UNEXPECTED_RUNTIME_EXCEPTIONS,
)
from core.logging.trace import get_logger

__all__ = (
    "cancel_assistant_stream_generator",
    "close_assistant_stream_generator",
    "transfer_assistant_stream_generator_cleanup",
)

LOGGER_NAME = "SoAI.features.assistant_timeline.stream_generator_cleanup"
OPERATION_STREAM_CLEANUP = "assistant_timeline.consume_stream.cleanup"
STREAM_CLEANUP_DEADLINE_SECONDS = 2.0


def transfer_assistant_stream_generator_cleanup(
    stream_generator: AsyncGenerator[bytes],
    *,
    active_read_task: asyncio.Task[bytes] | None,
    track_background_task: Callable[[asyncio.Task[None]], None],
) -> None:
    async def close_after_read() -> None:
        close_task = create_ephemeral_task(stream_generator.aclose())
        done, _pending = await asyncio.wait(
            {close_task},
            timeout=STREAM_CLEANUP_DEADLINE_SECONDS,
        )
        if not done:
            get_logger(LOGGER_NAME).warning(
                "Assistant stream generator close exceeded the cleanup deadline."
            )
            close_task.cancel()
            track_background_task(close_task)
            return
        results = await asyncio.gather(close_task, return_exceptions=True)
        for result in results:
            if isinstance(result, BaseException) and not isinstance(result, asyncio.CancelledError):
                _log_stream_cleanup_exception(result)

    async def cleanup() -> None:
        if active_read_task is not None:
            read_task = active_read_task
            if not read_task.done():
                read_task.cancel()
                done, _pending = await asyncio.wait(
                    {read_task},
                    timeout=STREAM_CLEANUP_DEADLINE_SECONDS,
                )
                if not done:
                    get_logger(LOGGER_NAME).warning(
                        "Assistant stream provider read exceeded the cleanup deadline."
                    )

                    async def finish_after_read() -> None:
                        results = await asyncio.gather(read_task, return_exceptions=True)
                        for result in results:
                            if isinstance(result, BaseException) and not isinstance(
                                result, asyncio.CancelledError
                            ):
                                _log_stream_cleanup_exception(result)
                        await close_after_read()

                    continuation = create_ephemeral_task(finish_after_read())
                    track_background_task(continuation)
                    return
            results = await asyncio.gather(read_task, return_exceptions=True)
            for result in results:
                if isinstance(result, BaseException) and not isinstance(
                    result, asyncio.CancelledError
                ):
                    _log_stream_cleanup_exception(result)
        await close_after_read()

    cleanup_task = create_ephemeral_task(cleanup())
    track_background_task(cleanup_task)


async def cancel_assistant_stream_generator(
    stream_generator: AsyncGenerator[bytes],
    *,
    stream_generator_closed: bool,
) -> bool:
    if stream_generator_closed:
        return True
    try:
        await uncancel_then_cleanup(stream_generator.athrow(asyncio.CancelledError()))
    except StopAsyncIteration:
        return True
    except asyncio.CancelledError:
        return True
    return await close_assistant_stream_generator(
        stream_generator,
        stream_generator_closed=False,
    )


async def close_assistant_stream_generator(
    stream_generator: AsyncGenerator[bytes],
    *,
    stream_generator_closed: bool,
) -> bool:
    if stream_generator_closed:
        return True
    try:
        await uncancel_then_cleanup(stream_generator.aclose())
    except asyncio.CancelledError:
        return True
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_STREAM_CLEANUP,
        )
        log_exception(
            get_logger(LOGGER_NAME),
            coerced,
            message="Assistant timeline stream generator cleanup failed (non-critical).",
            operation=OPERATION_STREAM_CLEANUP,
            level="debug",
        )
    except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
        _log_stream_cleanup_exception(exception)
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_STREAM_CLEANUP,
        )
        log_exception(
            get_logger(LOGGER_NAME),
            coerced,
            message="Assistant timeline stream generator cleanup failed with unclassified exception (non-critical).",
            operation=OPERATION_STREAM_CLEANUP,
            level="debug",
        )
    return True


def _log_stream_cleanup_exception(exception: BaseException) -> None:
    coerced = coerce_to_soai_error(
        exception,
        operation=OPERATION_STREAM_CLEANUP,
    )
    log_exception(
        get_logger(LOGGER_NAME),
        coerced,
        message="Assistant timeline stream generator cleanup failed (non-critical).",
        operation=OPERATION_STREAM_CLEANUP,
        level="debug",
    )

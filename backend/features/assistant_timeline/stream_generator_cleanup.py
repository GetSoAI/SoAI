"""SoAI - Assistant timeline stream generator cleanup [backend/features/assistant_timeline/stream_generator_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import (
    HANDLED_RUNTIME_EXCEPTIONS,
    UNEXPECTED_RUNTIME_EXCEPTIONS,
)
from core.logging.trace import get_logger

__all__ = ("cancel_assistant_stream_generator", "close_assistant_stream_generator")

LOGGER_NAME = "SoAI.features.assistant_timeline.stream_generator_cleanup"
OPERATION_STREAM_CLEANUP = "assistant_timeline.consume_stream.cleanup"


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

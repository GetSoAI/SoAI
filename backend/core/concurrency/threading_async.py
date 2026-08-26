"""SoAI - Async helpers for threading primitives [backend/core/concurrency/threading_async.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import functools
import threading
import weakref
from collections.abc import Callable
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import UNEXPECTED_RUNTIME_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.logging.rate_limited_logger import RateLimitedLogger
from core.timing.constants import TIGHT_POLL_INTERVAL_SEC

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "join_thread",
    "run_sync_in_daemon_thread",
    "wait_for_threading_event",
)

OPERATION_CORE_CONCURRENCY_THREADING_ASYNC_RUNNER = "core.concurrency.threading_async.runner"


_SYNC_DAEMON_THREAD_LIMIT: int = 8


@functools.cache
def _get_sync_daemon_thread_limiter_registry() -> (
    weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.BoundedSemaphore]
):
    return weakref.WeakKeyDictionary()


@functools.cache
def _get_sync_daemon_thread_limiter_registry_lock() -> threading.Lock:
    return threading.Lock()


def _get_sync_daemon_thread_limiter(loop: asyncio.AbstractEventLoop) -> asyncio.BoundedSemaphore:
    registry = _get_sync_daemon_thread_limiter_registry()
    registry_lock = _get_sync_daemon_thread_limiter_registry_lock()
    with registry_lock:
        existing_limiter = registry.get(loop)
        if existing_limiter is not None:
            return existing_limiter
        limiter = asyncio.BoundedSemaphore(_SYNC_DAEMON_THREAD_LIMIT)
        registry[loop] = limiter
        return limiter


@functools.cache
def _get_daemon_thread_limiter_shutdown_logger() -> RateLimitedLogger:
    return RateLimitedLogger(interval_seconds=10.0)


async def wait_for_threading_event(
    event: threading.Event,
    *,
    timeout: float | None = None,
    poll_interval: float = TIGHT_POLL_INTERVAL_SEC,
) -> bool:
    if event.is_set():
        return True
    if timeout is not None and timeout <= 0:
        return False
    loop = asyncio.get_running_loop()
    start = loop.time()
    while not event.is_set():
        if timeout is not None and (loop.time() - start) >= timeout:
            return event.is_set()
        await asyncio.sleep(poll_interval)
    return True


async def join_thread(
    thread: threading.Thread,
    *,
    timeout: float | None = None,
    poll_interval: float = TIGHT_POLL_INTERVAL_SEC,
) -> bool:
    if not thread.is_alive():
        return True
    if timeout is not None and timeout <= 0:
        return not thread.is_alive()
    loop = asyncio.get_running_loop()
    start = loop.time()
    while thread.is_alive():
        thread.join(timeout=0)
        if not thread.is_alive():
            return True
        if timeout is not None and (loop.time() - start) >= timeout:
            break
        await asyncio.sleep(poll_interval)
    return not thread.is_alive()


async def run_sync_in_daemon_thread(
    func: Callable[[], JSONDict],
    *,
    timeout: float | None = None,
    thread_name: str | None = None,
    logger: LoggerProtocol,
    operation: str,
    log_message: str = "Daemon thread task failed.",
    log_level: str = "error",
) -> JSONDict:
    loop = asyncio.get_running_loop()
    limiter = _get_sync_daemon_thread_limiter(loop)
    start = loop.time()
    if timeout is not None:
        await asyncio.wait_for(limiter.acquire(), timeout=timeout)
    else:
        await limiter.acquire()

    elapsed = loop.time() - start
    remaining_timeout = timeout - elapsed if timeout is not None else None
    if remaining_timeout is not None and remaining_timeout <= 0:
        limiter.release()
        raise TimeoutError

    completion_event = threading.Event()

    class _Outcome:
        __slots__ = ("exception", "result")

        def __init__(self) -> None:
            self.result: JSONDict | None = None
            self.exception: BaseException | None = None

    outcome = _Outcome()

    def _release_limiter_threadsafe() -> None:
        try:
            loop.call_soon_threadsafe(limiter.release)
        except RuntimeError:
            shutdown_logger = _get_daemon_thread_limiter_shutdown_logger()
            should_emit, suppressed = shutdown_logger.should_emit()
            if should_emit:
                suffix = f" (suppressed={suppressed})" if suppressed else ""
                logger.debug(
                    "Event loop closed; daemon thread limiter not released for operation '%s'%s.",
                    operation,
                    suffix,
                )

    def _runner() -> None:
        try:
            outcome.result = func()
        except RECOVERABLE_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(exception, operation=operation)
            log_exception(
                logger,
                coerced,
                message=log_message,
                operation=OPERATION_CORE_CONCURRENCY_THREADING_ASYNC_RUNNER,
                level=log_level,
            )
            outcome.exception = coerced
        except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(exception, operation=operation)
            log_exception(
                logger,
                coerced,
                message=log_message,
                operation=OPERATION_CORE_CONCURRENCY_THREADING_ASYNC_RUNNER,
                level="error",
            )
            outcome.exception = coerced
        except (SystemExit, KeyboardInterrupt, GeneratorExit) as exception:
            coerced = coerce_to_soai_error(exception, operation=operation)
            log_exception(
                logger,
                coerced,
                message=log_message,
                operation=OPERATION_CORE_CONCURRENCY_THREADING_ASYNC_RUNNER,
                level="error",
            )
            outcome.exception = exception
        finally:
            completion_event.set()
            _release_limiter_threadsafe()

    resolved_thread_name = thread_name or f"soai-daemon:{operation}"
    thread = threading.Thread(target=_runner, name=resolved_thread_name, daemon=True)
    try:
        thread.start()
    except asyncio.CancelledError:
        limiter.release()
        raise
    except RECOVERABLE_EXCEPTIONS:
        limiter.release()
        raise
    except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=operation)
        log_exception(
            logger,
            coerced,
            message="Failed to start daemon thread.",
            operation=OPERATION_CORE_CONCURRENCY_THREADING_ASYNC_RUNNER,
            level="error",
        )
        limiter.release()
        raise
    completed = await wait_for_threading_event(
        completion_event,
        timeout=remaining_timeout,
        poll_interval=TIGHT_POLL_INTERVAL_SEC,
    )
    if not completed:
        raise TimeoutError
    if outcome.exception is not None:
        if isinstance(outcome.exception, Exception):
            raise outcome.exception
        raise StateError(
            f"Daemon thread task raised a BaseException for operation '{operation}'.",
        ) from outcome.exception
    if outcome.result is None:
        raise StateError(
            f"Daemon thread task completed without a result for operation '{operation}'.",
        )
    return outcome.result

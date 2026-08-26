"""SoAI - Shared hard-deadline event consumption loop [backend/core/events/non_streaming_hard_deadline.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.deadlines import wait_for_hard_deadline
from core.errors.exceptions import SoAITimeoutError
from core.events.publication_errors import HardDeadlineExceededError

__all__ = (
    "ProgressEventHandler",
    "TerminalEventHandler",
    "run_hard_deadline_event_loop",
    "run_inactivity_timeout_event_loop",
)


@dataclass(frozen=True, slots=True)
class TerminalEventHandler[EventType, Result]:
    matches: Callable[[EventType], bool]
    handler: Callable[[EventType], Awaitable[Result]]


@dataclass(frozen=True, slots=True)
class ProgressEventHandler[EventType]:
    matches: Callable[[EventType], bool]
    handler: Callable[[EventType], Awaitable[None]]


async def run_hard_deadline_event_loop[EventType, Result](
    *,
    deadline_monotonic: float,
    next_event: Callable[[float], Awaitable[EventType]],
    terminal_handlers: Iterable[TerminalEventHandler[EventType, Result]],
    progress_handlers: Iterable[ProgressEventHandler[EventType]] = (),
    unknown_event_handler: Callable[[EventType], Awaitable[None]] | None = None,
    cleanup_callbacks: Iterable[Callable[[], Awaitable[None]]] = (),
    timeout_message: str,
    timeout_operation: str,
) -> Result:
    try:
        while True:
            try:
                event = await wait_for_hard_deadline(deadline_monotonic, next_event)
            except (SoAITimeoutError, TimeoutError) as exception:
                raise HardDeadlineExceededError(
                    timeout_message,
                    operation=timeout_operation,
                    cause=exception,
                ) from exception
            for terminal_handler in terminal_handlers:
                if terminal_handler.matches(event):
                    return await terminal_handler.handler(event)
            progress_handled = False
            for progress_handler in progress_handlers:
                if progress_handler.matches(event):
                    await progress_handler.handler(event)
                    progress_handled = True
                    break
            if progress_handled:
                continue
            if unknown_event_handler is not None:
                await unknown_event_handler(event)
    finally:
        for cleanup_callback in cleanup_callbacks:
            await uncancel_then_cleanup(cleanup_callback())


async def run_inactivity_timeout_event_loop[EventType, Result](
    *,
    inactivity_timeout_seconds: float,
    next_event: Callable[[float], Awaitable[EventType]],
    terminal_handlers: Iterable[TerminalEventHandler[EventType, Result]],
    progress_handlers: Iterable[ProgressEventHandler[EventType]] = (),
    unknown_event_handler: Callable[[EventType], Awaitable[None]] | None = None,
    cleanup_callbacks: Iterable[Callable[[], Awaitable[None]]] = (),
    timeout_message: str,
    timeout_operation: str,
) -> Result:
    timeout_seconds = float(inactivity_timeout_seconds)
    if timeout_seconds <= 0:
        timeout_seconds = 0.0
    deadline_monotonic = time.monotonic() + timeout_seconds
    try:
        while True:
            try:
                if timeout_seconds <= 0:
                    event = await next_event(3600.0 * 24.0 * 365.0 * 100.0)
                else:
                    event = await wait_for_hard_deadline(deadline_monotonic, next_event)
            except (SoAITimeoutError, TimeoutError) as exception:
                raise HardDeadlineExceededError(
                    timeout_message,
                    operation=timeout_operation,
                    cause=exception,
                ) from exception
            deadline_monotonic = time.monotonic() + timeout_seconds
            for terminal_handler in terminal_handlers:
                if terminal_handler.matches(event):
                    return await terminal_handler.handler(event)
            progress_handled = False
            for progress_handler in progress_handlers:
                if progress_handler.matches(event):
                    await progress_handler.handler(event)
                    progress_handled = True
                    break
            if progress_handled:
                continue
            if unknown_event_handler is not None:
                await unknown_event_handler(event)
    finally:
        for cleanup_callback in cleanup_callbacks:
            await uncancel_then_cleanup(cleanup_callback())

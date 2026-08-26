"""SoAI - Event publish/dispatch completion signals [backend/core/events/completion_signals.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.events.protocols import EventCompletionSignal

__all__ = (
    "EventDispatchCompletion",
    "EventDispatchCompletionSnapshot",
    "mark_completion_signal_completed",
    "mark_completion_signal_enqueued",
    "mark_completion_signal_not_enqueued",
)


@dataclass(frozen=True, slots=True)
class EventDispatchCompletionSnapshot:
    was_enqueued: bool
    completed: bool
    dispatch_timed_out: bool
    failure_message: str | None

    @property
    def succeeded(self) -> bool:
        return (
            self.was_enqueued
            and self.completed
            and (not self.dispatch_timed_out)
            and self.failure_message is None
        )


class EventDispatchCompletion:
    __slots__ = (
        "_completed",
        "_dispatch_timed_out",
        "_event",
        "_failure_message",
        "_was_enqueued",
    )

    def __init__(self) -> None:
        self._event = asyncio.Event()
        self._failure_message: str | None = None
        self._was_enqueued = False
        self._completed = False
        self._dispatch_timed_out = False

    async def wait(self) -> None:
        await self._event.wait()

    def is_set(self) -> bool:
        return self._event.is_set()

    def mark_enqueued(self) -> None:
        self._was_enqueued = True

    def mark_not_enqueued(self, failure_message: str | None = None) -> None:
        if failure_message:
            self._failure_message = failure_message
        self._completed = False
        self._event.set()

    def mark_completed(
        self,
        *,
        dispatch_timed_out: bool = False,
        failure_message: str | None = None,
    ) -> None:
        self._completed = True
        self._dispatch_timed_out = bool(dispatch_timed_out)
        if failure_message:
            self._failure_message = failure_message
        self._event.set()

    def snapshot(self) -> EventDispatchCompletionSnapshot:
        return EventDispatchCompletionSnapshot(
            was_enqueued=self._was_enqueued,
            completed=self._completed,
            dispatch_timed_out=self._dispatch_timed_out,
            failure_message=self._failure_message,
        )


def mark_completion_signal_enqueued(signal: EventCompletionSignal | None) -> None:
    if isinstance(signal, EventDispatchCompletion):
        signal.mark_enqueued()


def mark_completion_signal_not_enqueued(
    signal: EventCompletionSignal | None,
    *,
    failure_message: str | None = None,
) -> None:
    if signal is None:
        return
    if isinstance(signal, EventDispatchCompletion):
        signal.mark_not_enqueued(failure_message)
        return
    if isinstance(signal, asyncio.Event):
        signal.set()


def mark_completion_signal_completed(
    signal: EventCompletionSignal | None,
    *,
    dispatch_timed_out: bool = False,
    failure_message: str | None = None,
) -> None:
    if signal is None:
        return
    if isinstance(signal, EventDispatchCompletion):
        signal.mark_completed(
            dispatch_timed_out=dispatch_timed_out,
            failure_message=failure_message,
        )
        return
    if isinstance(signal, asyncio.Event):
        signal.set()

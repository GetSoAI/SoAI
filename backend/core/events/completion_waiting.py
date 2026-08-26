"""SoAI - Event publication receipt waiting operations [backend/core/events/completion_waiting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.deadlines import wait_for_hard_deadline
from core.events.completion_signals import EventDispatchCompletion
from core.events.publication_errors import (
    PublicationDeadlineExceededError,
    PublicationFailedError,
)

if TYPE_CHECKING:
    from core.state.protocols import AuthoritativePluginStateTransitionReceipt

__all__ = (
    "EVENT_COMPLETION_WAIT_TIMEOUT_SECONDS",
    "EventPublicationReceipt",
    "await_publication_receipt",
    "publication_completion_deadline",
)

EVENT_COMPLETION_WAIT_TIMEOUT_SECONDS: float = 30.0


def publication_completion_deadline() -> float:
    return time.monotonic() + EVENT_COMPLETION_WAIT_TIMEOUT_SECONDS


async def await_publication_receipt(
    receipt: AuthoritativePluginStateTransitionReceipt | EventPublicationReceipt | None,
) -> None:
    if receipt is None:
        return
    await receipt.wait_for_completion(publication_completion_deadline())


@dataclass(frozen=True, slots=True)
class EventPublicationReceipt:
    event_type: str
    operation: str
    completion_signal: EventDispatchCompletion

    @classmethod
    def create(cls, *, event_type: str, operation: str) -> EventPublicationReceipt:
        return cls(
            event_type=event_type,
            operation=operation,
            completion_signal=EventDispatchCompletion(),
        )

    async def wait_for_completion(self, deadline_monotonic: float) -> None:
        try:
            await wait_for_hard_deadline(
                deadline_monotonic,
                lambda remaining: asyncio.wait_for(
                    self.completion_signal.wait(),
                    timeout=remaining,
                ),
            )
        except TimeoutError as exception:
            raise PublicationDeadlineExceededError(
                (
                    f"Timed out waiting for event '{self.event_type}' completion "
                    f"(operation: {self.operation})."
                ),
                operation=self.operation,
                details={"event_type": self.event_type},
                cause=exception,
            ) from exception
        snapshot = self.completion_signal.snapshot()
        if snapshot.succeeded:
            return
        if not snapshot.was_enqueued:
            raise PublicationFailedError(
                snapshot.failure_message or f"Event '{self.event_type}' was not enqueued.",
                operation=self.operation,
                details={"event_type": self.event_type},
            )
        if snapshot.dispatch_timed_out:
            raise PublicationFailedError(
                snapshot.failure_message or f"Event '{self.event_type}' timed out during dispatch.",
                operation=self.operation,
                details={"event_type": self.event_type},
            )
        raise PublicationFailedError(
            snapshot.failure_message or f"Event '{self.event_type}' failed during dispatch.",
            operation=self.operation,
            details={"event_type": self.event_type},
        )

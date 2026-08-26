"""SoAI - Parameter mutation ordering and sequencing [backend/models/parameters/mutation_ordering.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import inspect
import weakref
from collections.abc import Callable
from typing import TYPE_CHECKING

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_groups import (
    DEFAULT_CANCELLATION_TIMEOUT_SEC,
    cancel_and_await,
)
from core.errors.exceptions import ValidationError
from core.types.json import JSONDict

if TYPE_CHECKING:
    type MutationCallable = Callable[[JSONDict, JSONDict], tuple[JSONDict, bool, str] | None]
else:
    MutationCallable = Callable

__all__ = ("MutationOrderTracker",)


class MutationOrderTracker:

    def __init__(self) -> None:
        self._universal_id_order_counters: dict[str, int] = {}
        self._universal_id_expected_orders: dict[str, int] = {}
        self._universal_id_tie_breakers: dict[str, int] = {}
        self._universal_id_order_events: dict[str, asyncio.Event] = {}
        self._universal_id_task_sequences: dict[
            str,
            weakref.WeakKeyDictionary[asyncio.Task[None], tuple[int, int]],
        ] = {}

    def determine_order(
        self,
        universal_id: str,
        override: int | tuple[int, int] | None,
    ) -> tuple[int, int]:
        if override is not None:
            response = (
                override
                if isinstance(override, tuple)
                else (override, self._next_tie_breaker(universal_id))
            )
            self.register_expected_order(universal_id, response[0])
            return response
        current_task = asyncio.current_task()
        if current_task is None:
            return (self.next_universal_id_order(universal_id), 0)
        task_sequence: weakref.WeakKeyDictionary[asyncio.Task[None], tuple[int, int]] | None = (
            self._universal_id_task_sequences.get(universal_id)
        )
        if task_sequence is None:
            task_sequence = weakref.WeakKeyDictionary[asyncio.Task[None], tuple[int, int]]()
            self._universal_id_task_sequences[universal_id] = task_sequence
        sequence_order: tuple[int, int] = task_sequence.get(current_task) or (
            self.next_universal_id_order(universal_id),
            0,
        )
        base, offset = sequence_order
        task_sequence[current_task] = (base, offset + 1)
        return (base, offset)

    def register_expected_order(self, universal_id: str, base: int) -> None:
        if universal_id not in self._universal_id_expected_orders:
            self._universal_id_expected_orders[universal_id] = base
        if universal_id not in self._universal_id_order_events:
            self._universal_id_order_events[universal_id] = asyncio.Event()

    def get_expected_order(self, universal_id: str) -> int | None:
        expected_order = self._universal_id_expected_orders.get(universal_id)
        if expected_order is None:
            if universal_id not in self._universal_id_order_events:
                self._universal_id_order_events[universal_id] = asyncio.Event()
        return expected_order

    def revoke_expected_order(self, universal_id: str, revoked_base: int) -> None:
        expected = self._universal_id_expected_orders.get(universal_id)
        if expected is not None and expected == revoked_base:
            self._universal_id_expected_orders[universal_id] = revoked_base + 1
            self.notify_order_ready(universal_id)

    def advance_expected_order(
        self,
        universal_id: str,
        *,
        completed_base: int,
        strict_order: bool,
    ) -> None:
        expected = self._universal_id_expected_orders.get(universal_id)
        if strict_order and expected is not None and (completed_base == expected):
            self._universal_id_expected_orders[universal_id] = completed_base + 1
            self.notify_order_ready(universal_id)

    async def wait_for_order(
        self,
        universal_id: str,
        *,
        shutdown_event: asyncio.Event,
    ) -> bool:
        if shutdown_event.is_set():
            return False
        order_event = self._universal_id_order_events.get(universal_id)
        if order_event is None:
            order_event = asyncio.Event()
            self._universal_id_order_events[universal_id] = order_event
        shutdown_waiter = create_ephemeral_task(shutdown_event.wait())
        order_waiter = create_ephemeral_task(order_event.wait())
        done_tasks: set[asyncio.Task[bool]] = set()
        pending_tasks: set[asyncio.Task[bool]] = {order_waiter, shutdown_waiter}
        try:
            while True:
                done_tasks, pending_tasks = await asyncio.wait(
                    {order_waiter, shutdown_waiter},
                    timeout=DEFAULT_CANCELLATION_TIMEOUT_SEC,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if done_tasks:
                    break
        finally:
            for pending_task in pending_tasks:
                pending_task.cancel()
            await cancel_and_await(pending_tasks, timeout_sec=DEFAULT_CANCELLATION_TIMEOUT_SEC)
        if order_waiter in done_tasks and (exception := order_waiter.exception()) is not None:
            raise exception
        order_ready = order_waiter in done_tasks and (not order_waiter.cancelled())
        if order_ready:
            order_event.clear()
        return order_ready

    def notify_order_ready(self, universal_id: str) -> None:
        order_event = self._universal_id_order_events.get(universal_id)
        if order_event is None:
            order_event = asyncio.Event()
            self._universal_id_order_events[universal_id] = order_event
        order_event.set()

    def next_universal_id_order(self, universal_id: str) -> int:
        counter = self._universal_id_order_counters.get(universal_id, 0) + 1
        self._universal_id_order_counters[universal_id] = counter
        return counter

    def normalize_mutation_callable(self, mutation: MutationCallable) -> MutationCallable:
        if mutation is None:
            raise ValidationError("Mutation callable must be provided.")
        try:
            signature = inspect.signature(mutation)
        except (TypeError, ValueError):
            return mutation
        if _signature_accepts_exactly_two_positional_parameters(signature):
            return mutation
        raise ValidationError(
            "Mutation callable must accept exactly 2 positional args (state, metadata).",
        )

    def clear_universal_id(self, universal_id: str) -> None:
        self._universal_id_order_counters.pop(universal_id, None)
        self._universal_id_tie_breakers.pop(universal_id, None)
        self._universal_id_expected_orders.pop(universal_id, None)
        self._universal_id_order_events.pop(universal_id, None)
        task_sequence = self._universal_id_task_sequences.get(universal_id)
        if task_sequence is not None:
            for task in list(task_sequence.keys()):
                if task.done():
                    task_sequence.pop(task, None)
            if not task_sequence:
                self._universal_id_task_sequences.pop(universal_id, None)

    def _next_tie_breaker(self, universal_id: str) -> int:
        counter = self._universal_id_tie_breakers.get(universal_id, 0) + 1
        self._universal_id_tie_breakers[universal_id] = counter
        return counter


def _signature_accepts_exactly_two_positional_parameters(
    signature: inspect.Signature,
) -> bool:
    positional_parameters = [
        parameter
        for parameter in signature.parameters.values()
        if parameter.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    has_var_positional = any(
        parameter.kind == inspect.Parameter.VAR_POSITIONAL
        for parameter in signature.parameters.values()
    )
    return len(positional_parameters) == 2 and not has_var_positional

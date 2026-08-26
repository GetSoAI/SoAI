"""SoAI - Unified singleflight coordinators for cache stampede prevention [backend/core/concurrency/singleflight.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import copy
import sys
import threading
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.errors.exceptions import StateError

__all__ = (
    "AsyncFlightState",
    "AsyncSingleflight",
    "ResultCopyMode",
    "SyncFlightState",
    "SyncSingleflight",
)


class ResultCopyMode(Enum):
    NONE = "none"
    DEEP = "deep"


@dataclass(slots=True)
class AsyncFlightState[ResultT]:
    event: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task[None] | None = None
    result: ResultT = field(init=False)
    has_result: bool = False
    error: BaseException | None = None


class AsyncSingleflight[KeyT, ResultT]:

    def __init__(
        self,
        result_copier: Callable[[ResultT], ResultT] | ResultCopyMode = ResultCopyMode.DEEP,
    ) -> None:
        self._registry_lock = asyncio.Lock()
        self._flights: dict[KeyT, AsyncFlightState[ResultT]] = {}
        self._result_copier = result_copier

    def _copy_result(self, result: ResultT) -> ResultT:
        if isinstance(self._result_copier, ResultCopyMode):
            if self._result_copier == ResultCopyMode.NONE:
                return result
            return copy.deepcopy(result)
        return self._result_copier(result)

    async def execute_or_wait(
        self,
        key: KeyT,
        computation: Callable[[], Awaitable[ResultT]],
    ) -> ResultT:
        is_leader = False
        flight: AsyncFlightState[ResultT]
        async with self._registry_lock:
            existing_flight = self._flights.get(key)
            if existing_flight is None:
                flight = AsyncFlightState()
                self._flights[key] = flight
                is_leader = True
            else:
                flight = existing_flight

        if is_leader:
            return await self._start_and_await_flight(key, flight, computation)
        return await self._wait_for_flight(flight)

    async def _wait_for_flight(self, flight: AsyncFlightState[ResultT]) -> ResultT:
        await flight.event.wait()
        if flight.error is not None:
            raise flight.error
        if not flight.has_result:
            raise StateError("Flight completed without result or error")
        return self._copy_result(flight.result)

    async def _run_computation(
        self,
        key: KeyT,
        flight: AsyncFlightState[ResultT],
        computation: Callable[[], Awaitable[ResultT]],
    ) -> None:
        try:
            result = await computation()
            flight.result = result
            flight.has_result = True
        finally:
            exc_info = sys.exc_info()
            if exc_info[0] is not None and exc_info[1] is not None:
                flight.error = exc_info[1]
            flight.event.set()
            async with self._registry_lock:
                self._flights.pop(key, None)

    async def _start_and_await_flight(
        self,
        key: KeyT,
        flight: AsyncFlightState[ResultT],
        computation: Callable[[], Awaitable[ResultT]],
    ) -> ResultT:
        task = create_ephemeral_task(
            self._run_computation(key, flight, computation),
            log_exceptions=False,
        )
        flight.task = task
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            await flight.event.wait()
            if task.done() and not task.cancelled():
                task.exception()
            raise
        if flight.error is not None:
            raise flight.error
        if not flight.has_result:
            raise StateError("Flight completed without result or error")
        return self._copy_result(flight.result)


@dataclass(slots=True)
class SyncFlightState[ResultT]:
    event: threading.Event = field(default_factory=threading.Event)
    result: ResultT = field(init=False)
    has_result: bool = False
    error: BaseException | None = None


class SyncSingleflight[KeyT, ResultT]:

    def __init__(
        self,
        result_copier: Callable[[ResultT], ResultT] | ResultCopyMode = ResultCopyMode.DEEP,
    ) -> None:
        self._registry_lock = threading.Lock()
        self._flights: dict[KeyT, SyncFlightState[ResultT]] = {}
        self._result_copier = result_copier

    def _copy_result(self, result: ResultT) -> ResultT:
        if isinstance(self._result_copier, ResultCopyMode):
            if self._result_copier == ResultCopyMode.NONE:
                return result
            return copy.deepcopy(result)
        return self._result_copier(result)

    def execute_or_wait(self, key: KeyT, computation: Callable[[], ResultT]) -> ResultT:
        is_leader = False
        flight: SyncFlightState[ResultT]
        with self._registry_lock:
            existing_flight = self._flights.get(key)
            if existing_flight is None:
                flight = SyncFlightState()
                self._flights[key] = flight
                is_leader = True
            else:
                flight = existing_flight
        if not is_leader:
            return self._wait_for_flight(flight)
        return self._execute_flight(key, flight, computation)

    def _wait_for_flight(self, flight: SyncFlightState[ResultT]) -> ResultT:
        flight.event.wait()
        if flight.error is not None:
            raise flight.error
        if not flight.has_result:
            raise StateError("Flight completed without result or error")
        return self._copy_result(flight.result)

    def _execute_flight(
        self,
        key: KeyT,
        flight: SyncFlightState[ResultT],
        computation: Callable[[], ResultT],
    ) -> ResultT:
        try:
            result = computation()
            flight.result = result
            flight.has_result = True
            return self._copy_result(result)
        finally:
            exc_info = sys.exc_info()
            if exc_info[0] is not None and exc_info[1] is not None:
                flight.error = exc_info[1]
            flight.event.set()
            with self._registry_lock:
                self._flights.pop(key, None)

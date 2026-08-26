"""SoAI - Bounded blocking call helpers for thread pools [backend/core/concurrency/bounded_blocking.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Callable
from concurrent.futures import Executor, ThreadPoolExecutor
from dataclasses import dataclass
from typing import override

from core.config.numeric import coerce_positive_int
from core.errors.exceptions import ValidationError

__all__ = (
    "BoundedBlockingCancelledBase",
    "BoundedBlockingCancelledError",
    "BoundedBlockingPool",
    "BoundedBlockingTimeoutBase",
    "BoundedBlockingTimeoutError",
    "BoundedThreadPoolConfig",
    "create_bounded_thread_pool",
    "create_bounded_thread_pool_from_env",
    "run_bounded_blocking_call",
    "shutdown_bounded_pool_executor",
)


@dataclass(frozen=True, slots=True)
class BoundedBlockingPool:
    executor: Executor
    semaphore: asyncio.Semaphore
    label: str


@dataclass(frozen=True, slots=True)
class BoundedThreadPoolConfig:
    label: str
    thread_name_prefix: str
    max_workers_env: str
    max_in_flight_env: str
    default_max_workers: int
    minimum_workers: int
    maximum_workers: int
    default_in_flight_multiplier: int
    default_min_in_flight: int
    max_in_flight_limit: int

    def __post_init__(self) -> None:
        if not self.max_workers_env.strip():
            raise ValidationError("max_workers_env is required.")
        if not self.max_in_flight_env.strip():
            raise ValidationError("max_in_flight_env is required.")
        if self.minimum_workers < 1:
            raise ValidationError("minimum_workers must be >= 1.")
        if self.maximum_workers < self.minimum_workers:
            raise ValidationError("maximum_workers must be >= minimum_workers.")
        if not self.minimum_workers <= self.default_max_workers <= self.maximum_workers:
            raise ValidationError("default_max_workers must be within worker bounds.")
        if self.default_in_flight_multiplier < 1:
            raise ValidationError("default_in_flight_multiplier must be >= 1.")
        if self.default_min_in_flight < 1:
            raise ValidationError("default_min_in_flight must be >= 1.")
        if self.max_in_flight_limit < self.minimum_workers:
            raise ValidationError("max_in_flight_limit must be >= minimum_workers.")
        if self.max_in_flight_limit < self.default_min_in_flight:
            raise ValidationError("max_in_flight_limit must be >= default_min_in_flight.")
        default_in_flight = max(
            self.default_min_in_flight,
            self.default_max_workers * self.default_in_flight_multiplier,
        )
        if default_in_flight > self.max_in_flight_limit:
            raise ValidationError("default in-flight value must be <= max_in_flight_limit.")


class BoundedBlockingTimeoutBase(TimeoutError):
    def cancel_future(self) -> None:
        return

    async def wait_for_completion(self, timeout_sec: float) -> None:
        del timeout_sec


class BoundedBlockingTimeoutError[ResultT](BoundedBlockingTimeoutBase):
    __slots__ = ("future", "pool_label", "timeout_sec")

    def __init__(
        self,
        *,
        future: asyncio.Future[ResultT] | None,
        timeout_sec: float,
        pool_label: str,
    ) -> None:
        super().__init__(
            f"Bounded blocking call timed out after {timeout_sec}s (pool={pool_label}); underlying work may still be running.",
        )
        self.future = future
        self.timeout_sec = timeout_sec
        self.pool_label = pool_label

    @override
    def __str__(self) -> str:
        return f"Bounded blocking call timed out after {self.timeout_sec}s (pool={self.pool_label}); underlying work may still be running."

    def __getnewargs_ex__(
        self,
    ) -> tuple[tuple[()], dict[str, asyncio.Future[ResultT] | float | str | None]]:
        return (
            (),
            {"future": self.future, "timeout_sec": self.timeout_sec, "pool_label": self.pool_label},
        )

    @override
    def cancel_future(self) -> None:
        if self.future is not None:
            self.future.cancel()

    @override
    async def wait_for_completion(self, timeout_sec: float) -> None:
        if self.future is not None:
            await asyncio.wait_for(asyncio.shield(self.future), timeout=timeout_sec)


class BoundedBlockingCancelledBase(asyncio.CancelledError):
    def cancel_future(self) -> None:
        return

    async def wait_for_completion(self, timeout_sec: float) -> None:
        del timeout_sec


class BoundedBlockingCancelledError[ResultT](BoundedBlockingCancelledBase):
    __slots__ = ("future", "pool_label")

    def __init__(
        self,
        *,
        future: asyncio.Future[ResultT],
        pool_label: str,
    ) -> None:
        super().__init__(
            f"Bounded blocking call was cancelled (pool={pool_label}); underlying work may still be running.",
        )
        self.future = future
        self.pool_label = pool_label

    @override
    def __str__(self) -> str:
        return f"Bounded blocking call was cancelled (pool={self.pool_label}); underlying work may still be running."

    def __getnewargs_ex__(
        self,
    ) -> tuple[tuple[()], dict[str, asyncio.Future[ResultT] | str]]:
        return ((), {"future": self.future, "pool_label": self.pool_label})

    @override
    def cancel_future(self) -> None:
        self.future.cancel()

    @override
    async def wait_for_completion(self, timeout_sec: float) -> None:
        await asyncio.wait_for(asyncio.shield(self.future), timeout=timeout_sec)


def create_bounded_thread_pool(
    *,
    label: str,
    thread_name_prefix: str,
    max_workers: int,
    max_in_flight: int,
) -> BoundedBlockingPool:
    normalized_label = str(label or "").strip()
    if not normalized_label:
        raise ValidationError("label is required.")
    normalized_prefix = str(thread_name_prefix or "").strip()
    if not normalized_prefix:
        raise ValidationError("thread_name_prefix is required.")
    workers = int(max_workers)
    if workers < 1:
        raise ValidationError("max_workers must be >= 1.")
    in_flight = int(max_in_flight)
    if in_flight < workers:
        raise ValidationError("max_in_flight must be >= max_workers.")
    pool_executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix=normalized_prefix)
    semaphore = asyncio.Semaphore(in_flight)
    return BoundedBlockingPool(
        executor=pool_executor,
        semaphore=semaphore,
        label=normalized_label,
    )


def create_bounded_thread_pool_from_env(config: BoundedThreadPoolConfig) -> BoundedBlockingPool:
    max_workers = coerce_positive_int(
        os.getenv(config.max_workers_env, None),
        default=config.default_max_workers,
        minimum=config.minimum_workers,
        maximum=config.maximum_workers,
        label=config.max_workers_env,
        logger=None,
    )
    max_in_flight = coerce_positive_int(
        os.getenv(config.max_in_flight_env, None),
        default=max(
            config.default_min_in_flight,
            max_workers * config.default_in_flight_multiplier,
        ),
        minimum=max_workers,
        maximum=config.max_in_flight_limit,
        label=config.max_in_flight_env,
        logger=None,
    )
    return create_bounded_thread_pool(
        label=config.label,
        thread_name_prefix=config.thread_name_prefix,
        max_workers=max_workers,
        max_in_flight=max_in_flight,
    )


async def run_bounded_blocking_call[*Ts, R](
    bounded: BoundedBlockingPool,
    func: Callable[[*Ts], R],
    *args: *Ts,
    timeout_sec: float | None = None,
    total_timeout_sec: float | None = None,
    on_timeout: Callable[[asyncio.Future[R]], None] | None = None,
    on_cancelled: Callable[[asyncio.Future[R]], None] | None = None,
) -> R:
    if bounded is None:
        raise ValidationError("bounded executor is required.")
    if func is None:
        raise ValidationError("func is required.")
    if timeout_sec is not None and timeout_sec <= 0.0:
        raise ValidationError("timeout_sec must be positive when provided.")
    if total_timeout_sec is not None and total_timeout_sec <= 0.0:
        raise ValidationError("total_timeout_sec must be positive when provided.")
    loop = asyncio.get_running_loop()
    if total_timeout_sec is None:
        deadline = None
        await bounded.semaphore.acquire()
    else:
        deadline = time.monotonic() + total_timeout_sec
        queue_remaining = deadline - time.monotonic()
        try:
            await asyncio.wait_for(bounded.semaphore.acquire(), timeout=queue_remaining)
        except TimeoutError as exception:
            raise BoundedBlockingTimeoutError(
                future=None,
                timeout_sec=total_timeout_sec,
                pool_label=bounded.label,
            ) from exception
    released = False

    def _release_once(future: asyncio.Future[R]) -> None:
        nonlocal released
        if released:
            return
        released = True
        if not future.cancelled():
            future.exception()
        bounded.semaphore.release()

    callback_attached = False
    try:
        submitted = loop.run_in_executor(bounded.executor, func, *args)
        submitted.add_done_callback(_release_once)
        callback_attached = True
    finally:
        if not callback_attached and not released:
            released = True
            bounded.semaphore.release()
    effective_timeout = timeout_sec
    if deadline is not None:
        deadline_remaining = max(0.0, deadline - time.monotonic())
        effective_timeout = (
            deadline_remaining
            if effective_timeout is None
            else min(effective_timeout, deadline_remaining)
        )
    if effective_timeout is None:
        try:
            return await asyncio.shield(submitted)
        except asyncio.CancelledError as exception:
            if on_cancelled is not None:
                on_cancelled(submitted)
            raise BoundedBlockingCancelledError(
                future=submitted,
                pool_label=bounded.label,
            ) from exception
    try:
        return await asyncio.wait_for(asyncio.shield(submitted), timeout=effective_timeout)
    except TimeoutError as exception:
        if submitted.done():
            return submitted.result()
        if on_timeout is not None:
            on_timeout(submitted)
        raise BoundedBlockingTimeoutError(
            future=submitted,
            timeout_sec=(total_timeout_sec if total_timeout_sec is not None else effective_timeout),
            pool_label=bounded.label,
        ) from exception
    except asyncio.CancelledError as exception:
        if on_cancelled is not None:
            on_cancelled(submitted)
        raise BoundedBlockingCancelledError(
            future=submitted,
            pool_label=bounded.label,
        ) from exception


def shutdown_bounded_pool_executor(pool: BoundedBlockingPool) -> None:
    pool.executor.shutdown(wait=False)

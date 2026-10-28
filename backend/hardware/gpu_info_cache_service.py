"""SoAI - GPU info cache service [backend/hardware/gpu_info_cache_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
import threading
from collections.abc import Callable
from functools import partial
from typing import TYPE_CHECKING

from core.concurrency.bounded_sync_submission import bounded_sync_lock, submit_bounded_sync_call
from core.concurrency.deadlines import MonotonicDeadline, deadline_after
from core.concurrency.singleflight import SyncSingleflight, SyncSingleflightWaitTimeoutError
from core.errors.exceptions import ServiceUnavailableError, SoAITimeoutError, StateError
from core.hardware.gpu_inventory_errors import (
    GPUObservationSupersededError,
    gpu_inventory_query_failure,
)
from core.logging.trace import get_logger
from hardware.gpu_observation import (
    GPUInfoCacheState,
    GPUInfoObservation,
    capture_gpu_info_observation,
    complete_retained_gpu_probe,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from hardware.gpu_observation import GPUInfoCacheServiceDependencies

__all__ = ("GPUInfoCacheService",)

LOGGER_NAME = "SoAI.hardware.gpu_info_cache_service"


class GPUInfoCacheService:
    __slots__ = (
        "_admission",
        "_executor",
        "_executor_factory",
        "_lock",
        "_worker_lock",
        "_worker_condition",
        "_state",
        "_singleflight",
        "_probe_timeout_seconds",
        "cache_ttl",
    )

    def __init__(self, dependencies: GPUInfoCacheServiceDependencies) -> None:
        self.cache_ttl: float = dependencies.cache_ttl_seconds
        self._state = GPUInfoCacheState()
        self._admission = threading.BoundedSemaphore(1)
        self._executor_factory = dependencies.probe_executor_factory
        self._executor = self._executor_factory()
        self._probe_timeout_seconds = dependencies.probe_timeout_seconds
        self._lock: threading.RLock = threading.RLock()
        self._worker_lock: threading.RLock = threading.RLock()
        self._worker_condition = threading.Condition(self._worker_lock)
        self._singleflight = SyncSingleflight[tuple[bool, int], GPUInfoObservation]()

    def acquire_observation(
        self,
        cache_key: bool,
        acquisition: Callable[[int, int], GPUInfoObservation],
        *,
        monotonic_clock_ms: Callable[[], float],
        deadline: MonotonicDeadline | None = None,
    ) -> GPUInfoObservation:
        caller_deadline = deadline or deadline_after(self._probe_timeout_seconds)
        for _attempt in range(3):
            if caller_deadline.expired():
                break
            try:
                return self._acquire_for_revision(
                    cache_key, acquisition, monotonic_clock_ms, caller_deadline
                )
            except GPUObservationSupersededError:
                continue
            except SyncSingleflightWaitTimeoutError as exception:
                raise gpu_inventory_query_failure(
                    "shared_deadline", diagnostic_message=str(exception), cause=exception
                ) from exception
            except TimeoutError as exception:
                if isinstance(exception, SoAITimeoutError):
                    raise
                raise gpu_inventory_query_failure(
                    "caller_deadline",
                    diagnostic_message=str(exception),
                    cause=exception,
                ) from exception
        if caller_deadline.expired():
            raise gpu_inventory_query_failure(
                "caller_deadline", diagnostic_message="GPU inventory observation deadline expired."
            )
        raise GPUObservationSupersededError(
            "GPU inventory changed repeatedly; retry after topology settles."
        )

    def _acquire_for_revision(
        self,
        cache_key: bool,
        acquisition: Callable[[int, int], GPUInfoObservation],
        monotonic_clock_ms: Callable[[], float],
        caller_deadline: MonotonicDeadline,
    ) -> GPUInfoObservation:
        with bounded_sync_lock(self._lock, caller_deadline), self._worker_lock:
            if self._state.stopping:
                raise StateError("GPU inventory observation service is stopping.")
            self._state.last_caller_deadline = caller_deadline.deadline_monotonic
            probe_revision = self._state.revision
            cached = self.get_cached_observation(cache_key, monotonic_clock_ms() / 1000.0)
            if cached is not None:
                return cached
            recovering = self._state.recovery_observation(cache_key, monotonic_clock_ms() / 1000.0)
            if recovering is not None:
                return recovering
        sampled_here = False

        def probe() -> GPUInfoObservation:
            nonlocal sampled_here
            with self._lock, self._worker_lock:
                if caller_deadline.expired():
                    raise TimeoutError(
                        "GPU inventory observation deadline expired before acquisition."
                    )
                if probe_revision != self._state.revision:
                    raise GPUObservationSupersededError("GPU inventory observation was superseded.")
                if self._state.stopping:
                    raise StateError("GPU inventory observation service is stopping.")
                cached = self.get_cached_observation(cache_key, monotonic_clock_ms() / 1000.0)
                if cached is not None:
                    return cached
                recovering = self._state.recovery_observation(
                    cache_key, monotonic_clock_ms() / 1000.0
                )
                if recovering is not None:
                    return recovering
                sequence = self.begin_acquisition(cache_key)
            sampled_here = True
            with self._lock, self._worker_lock:
                if probe_revision != self._state.revision:
                    raise GPUObservationSupersededError("GPU inventory observation was superseded.")
                if not self.is_current_acquisition(cache_key, sequence):
                    raise TimeoutError("GPU inventory acquisition expired before its native probe.")
            try:
                result = acquisition(probe_revision, sequence)
            except GPUObservationSupersededError:
                raise
            except (OSError, ServiceUnavailableError, SoAITimeoutError) as exception:
                with self._lock:
                    if probe_revision == self._state.revision:
                        self._state.record_failure(
                            cache_key, monotonic_clock_ms() / 1000.0, exception
                        )
                raise
            with self._lock:
                if probe_revision == self._state.revision:
                    self._state.record_observation(cache_key, monotonic_clock_ms() / 1000.0, result)
            return result

        def acquire_if_due() -> GPUInfoObservation:
            with self._worker_lock:
                if self._state.stopping:
                    raise StateError("GPU inventory observation service is stopping.")
                self._state.admissions_pending += 1
            try:
                try:
                    worker = submit_bounded_sync_call(
                        self._executor, self._admission, caller_deadline, probe
                    )
                except TimeoutError as exception:
                    raise gpu_inventory_query_failure(
                        "admission_deadline",
                        diagnostic_message="GPU inventory admission deadline expired.",
                        cause=exception,
                    ) from exception
                with self._worker_lock:
                    self._state.probe_leader_timed_out[worker] = False
                worker.add_done_callback(
                    partial(complete_retained_gpu_probe, self._state, self._worker_lock)
                )
            finally:
                with self._worker_lock:
                    self._state.admissions_pending -= 1
                    self._worker_condition.notify_all()
            try:
                return worker.result(timeout=caller_deadline.remaining_seconds())
            except TimeoutError as exception:
                with self._worker_lock:
                    if worker.done():
                        return worker.result()
                    self._state.probe_leader_timed_out[worker] = True
                raise gpu_inventory_query_failure(
                    "caller_deadline",
                    diagnostic_message="GPU inventory observation deadline expired; probe remains owned.",
                    cause=exception,
                ) from exception

        result = self._singleflight.execute_or_wait(
            (cache_key, probe_revision), acquire_if_due, timeout=caller_deadline.remaining_seconds()
        )
        with bounded_sync_lock(self._lock, caller_deadline), self._worker_lock:
            if self._state.stopping:
                raise StateError("GPU inventory observation service is stopping.")
            if caller_deadline.expired():
                raise TimeoutError("GPU inventory observation deadline expired before delivery.")
            if probe_revision != self._state.revision:
                raise GPUObservationSupersededError("GPU inventory observation was superseded.")
            return self._state.deliver_observation(
                cache_key,
                monotonic_clock_ms() / 1000.0,
                self.cache_ttl,
                result,
                sampled_here=sampled_here,
            )

    def shutdown(self) -> None:
        with self._worker_lock:
            self._state.stopping = True
        self._executor.shutdown(wait=True, cancel_futures=False)
        drain_deadline = deadline_after(self._probe_timeout_seconds)
        with self._worker_condition:
            while self._state.admissions_pending and not drain_deadline.expired():
                self._worker_condition.wait(timeout=drain_deadline.remaining_seconds())
            if self._state.admissions_pending or any(
                not worker.done() for worker in self._state.probe_leader_timed_out
            ):
                raise StateError("GPU inventory shutdown ownership did not settle.")

    def start(self) -> None:
        with self._lock, self._worker_lock:
            if not self._state.stopping:
                return
            if self._state.admissions_pending or any(
                not worker.done() for worker in self._state.probe_leader_timed_out
            ):
                raise StateError("Previous GPU inventory probes must settle before restart.")
            executor = self._executor_factory()
            self._executor = executor
            self._state.invalidate(owner="hardware.gpu_inventory", reason="monitoring_restarted")
            self._state.stopping = False

    @property
    def lock(self) -> threading.RLock:
        return self._lock

    def set_cache_ttl(self, cache_ttl_seconds: float) -> None:
        with self._lock:
            self.cache_ttl = cache_ttl_seconds

    def begin_acquisition(self, cache_key: bool) -> int:
        with self._lock:
            sequence = self._state.acquisition_sequences.get(cache_key, 0) + 1
            self._state.acquisition_sequences[cache_key] = sequence
            self._state.acquisition_deadlines[cache_key] = deadline_after(
                self._probe_timeout_seconds
            )
            return sequence

    def is_current_acquisition(self, cache_key: bool, sequence: int) -> bool:
        with self._lock, self._worker_lock:
            deadline = self._state.acquisition_deadlines.get(cache_key)
            return (
                not self._state.stopping
                and self._state.acquisition_sequences.get(cache_key) == sequence
                and deadline is not None
                and not deadline.expired()
            )

    def get_cached(self, cache_key: bool, now: float) -> JSONDict | None:
        observation = self.get_cached_observation(cache_key, now)
        return observation.payload if observation is not None else None

    def get_cached_observation(self, cache_key: bool, now: float) -> GPUInfoObservation | None:
        with self._lock:
            if cache_key in self._state.refresh_required:
                return None
            return self._state.valid_observation(cache_key, now, self.cache_ttl)

    def get_cached_with_gpus(self, now: float) -> JSONDict | None:
        with self._lock:
            return self._state.valid_payload_with_gpus(now, self.cache_ttl)

    def get_retained_observation(self) -> GPUInfoObservation | None:
        entries = self.get_retained_observations()
        return entries[0] if entries else None

    def get_retained_observations(self) -> tuple[GPUInfoObservation, ...]:
        with self._lock:
            return self._state.retained_observations()

    def set_cached(self, cache_key: bool, now: float, payload: JSONDict) -> None:
        observation = capture_gpu_info_observation(payload)
        with self._lock:
            self._state.cache_entries[cache_key] = (now, observation)
            self._state.refresh_required.discard(cache_key)

    def publish_acquisition(
        self, cache_key: bool, now: float, payload: JSONDict, *, revision: int, sequence: int
    ) -> GPUInfoObservation:
        observation = capture_gpu_info_observation(payload)
        with self._lock, self._worker_lock:
            if revision != self._state.revision:
                raise GPUObservationSupersededError("GPU inventory observation was superseded.")
            if not self.is_current_acquisition(cache_key, sequence):
                raise TimeoutError("GPU inventory acquisition expired before publication.")
            self._state.cache_entries[cache_key] = (now, observation)
            self._state.refresh_required.discard(cache_key)
            return copy.deepcopy(observation)

    def request_refresh(self) -> None:
        with self._lock:
            self._state.refresh_required.update(self._state.cache_entries)

    def invalidate_cache(self, *, owner: str, reason: str) -> None:
        with self._lock:
            diagnostic = self._state.invalidate(owner=owner, reason=reason)
        get_logger(LOGGER_NAME).debug("GPU inventory invalidated: %s", diagnostic)

    def observation_diagnostics(self) -> JSONDict:
        with self._lock, self._worker_lock:
            return self._state.diagnostics()

    def revision(self) -> int:
        with self._lock:
            return self._state.revision

"""SoAI - GPU observation and acquisition contracts [backend/hardware/gpu_observation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
import threading
from concurrent.futures import Future
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from core.concurrency.deadlines import MonotonicDeadline
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import (
    ServiceUnavailableError,
    SoAIError,
    SoAITimeoutError,
    ValidationError,
)
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.gpu_inventory_errors import gpu_inventory_query_failure
from core.logging.rate_limited_logger import RateLimitedLogger
from core.logging.trace import get_logger
from core.timing.epoch import epoch_ms
from core.timing.retry_backoff import compute_exponential_backoff_seconds
from core.validation.strict_numbers import (
    require_finite_float_strict,
    require_non_negative_int_strict,
)
from core.validation.strings import require_canonical_trimmed_json_text
from hardware.gpu_inventory.physical_observations import require_gpu_discovery_available
from hardware.internal_protocols import GPUInfoObservation, GPUProbeExecutorFactoryProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("GPUInfoObservation", "GPUInfoCacheServiceDependencies")

LOGGER_NAME = "SoAI.hardware.gpu_observation"
OPERATION_GPU_INVENTORY_ACQUISITION = "hardware.gpu_inventory.acquisition"
OPERATION_GPU_INVENTORY_RETAINED_PROBE = "hardware.gpu_inventory.retained_probe"


@dataclass(slots=True)
class GPUAcquisitionRetryState:
    failures: int = 0
    retry_at: float = 0.0
    healthy_since: float | None = None
    failure: SoAIError | None = None
    observation: GPUInfoObservation | None = None
    diagnostics: RateLimitedLogger = field(default_factory=lambda: RateLimitedLogger(60))


@dataclass(frozen=True, slots=True)
class GPUInfoCacheServiceDependencies:
    probe_executor_factory: GPUProbeExecutorFactoryProtocol
    cache_ttl_seconds: float = 1.0
    probe_timeout_seconds: float = 15.0

    def __post_init__(self) -> None:
        require_dependencies(
            owner="GPUInfoCacheServiceDependencies",
            probe_executor_factory=self.probe_executor_factory,
            cache_ttl_seconds=self.cache_ttl_seconds,
            probe_timeout_seconds=self.probe_timeout_seconds,
        )
        if (
            require_finite_float_strict(
                self.probe_timeout_seconds, error_message="GPU probe timeout must be finite."
            )
            <= 0
        ):
            raise ValidationError("GPU probe timeout must be positive.")


@dataclass(slots=True)
class GPUInfoCacheState:
    acquisition_retries: dict[bool, GPUAcquisitionRetryState] = field(
        default_factory=dict[bool, GPUAcquisitionRetryState]
    )
    acquisition_sequences: dict[bool, int] = field(default_factory=dict[bool, int])
    acquisition_deadlines: dict[bool, MonotonicDeadline] = field(
        default_factory=dict[bool, MonotonicDeadline]
    )
    cache_entries: dict[bool, tuple[float, GPUInfoObservation]] = field(
        default_factory=dict[bool, tuple[float, GPUInfoObservation]]
    )
    refresh_required: set[bool] = field(default_factory=set[bool])
    probe_leader_timed_out: dict[Future[GPUInfoObservation], bool] = field(
        default_factory=dict[Future[GPUInfoObservation], bool]
    )
    admissions_pending: int = 0
    stopping: bool = False
    revision: int = 0
    last_invalidation: JSONDict | None = None
    last_caller_deadline: float | None = None

    def valid_observation(
        self, cache_key: bool, now: float, cache_ttl: float
    ) -> GPUInfoObservation | None:
        entry = self.cache_entries.get(cache_key)
        if entry is None:
            return None
        remaining = cache_ttl - (now - entry[0])
        if remaining < 0:
            return None
        return replace(
            copy.deepcopy(entry[1]),
            inventory_revision=self.revision,
            valid_until_ms=epoch_ms() + int(remaining * 1000),
        )

    def recovery_observation(self, cache_key: bool, now: float) -> GPUInfoObservation | None:
        retry = self.acquisition_retries.get(cache_key)
        if retry is None or retry.failure is None or now >= retry.retry_at:
            return None
        retained = self.cache_entries.get(cache_key)
        observation = retry.observation or (retained[1] if retained is not None else None)
        if observation is not None:
            return replace(
                copy.deepcopy(observation),
                sampled_current=False,
                refresh_failed=True,
                valid_until_ms=None,
                inventory_revision=self.revision,
                refresh_error=copy.deepcopy(retry.failure),
            )
        raise retry.failure

    def record_failure(
        self,
        cache_key: bool,
        now: float,
        failure: SoAIError | OSError,
        observation: GPUInfoObservation | None = None,
    ) -> None:
        if not isinstance(failure, SoAIError) or failure.code not in (
            "gpu_inventory_timeout",
            "gpu_inventory_query_failed",
            "gpu_inventory_busy",
            "gpu_observation_unavailable",
        ):
            failure = gpu_inventory_query_failure(
                (
                    "permission_denied"
                    if isinstance(failure, PermissionError)
                    else (
                        "native_timeout"
                        if isinstance(failure, TimeoutError | SoAITimeoutError)
                        else "query_unavailable"
                    )
                ),
                diagnostic_message=str(failure),
                cause=failure,
            )
        if cache_key not in self.acquisition_retries:
            self.acquisition_retries[cache_key] = GPUAcquisitionRetryState()
        retry = self.acquisition_retries[cache_key]
        transition = retry.failure is None
        if transition:
            retry.diagnostics = RateLimitedLogger(60, _last_warning_monotonic=now - 60)
        retry.retry_at = now + compute_exponential_backoff_seconds(
            retry.failures, base_seconds=1, maximum_seconds=30, jitter_ratio=0.2
        )
        retry.failures += 1
        retry.healthy_since = None
        retry.failure = failure
        retry.observation = copy.deepcopy(observation)
        emit, suppressed = retry.diagnostics.should_emit(now=now)
        if emit:
            log_handled_exception(
                get_logger(LOGGER_NAME),
                failure,
                message="GPU inventory acquisition is recovering.",
                operation=OPERATION_GPU_INVENTORY_ACQUISITION,
                details={
                    "revision": self.revision,
                    "detailed": cache_key,
                    "retry_delay_seconds": retry.retry_at - now,
                    "suppressed_count": suppressed,
                    "diagnostics": (
                        [str(error) for error in observation.diagnostics]
                        if observation is not None
                        else []
                    ),
                },
            )

    def record_observation(self, cache_key: bool, now: float, result: GPUInfoObservation) -> None:
        if result.refresh_failed:
            try:
                require_gpu_discovery_available(result.payload)
            except (ServiceUnavailableError, SoAITimeoutError) as failure:
                self.record_failure(cache_key, now, failure, result)
            return
        retry = self.acquisition_retries.get(cache_key)
        if retry is None:
            return
        if retry.failure is not None:
            get_logger(LOGGER_NAME).info(
                "GPU inventory acquisition recovered (revision=%s, detailed=%s).",
                self.revision,
                cache_key,
            )
            retry.failure = None
            retry.observation = None
            retry.healthy_since = now
        elif retry.healthy_since is not None and now - retry.healthy_since >= 30:
            self.acquisition_retries.pop(cache_key, None)

    def deliver_observation(
        self,
        cache_key: bool,
        now: float,
        cache_ttl: float,
        result: GPUInfoObservation,
        *,
        sampled_here: bool,
    ) -> GPUInfoObservation:
        accepted = self.valid_observation(cache_key, now, cache_ttl)
        if result.refresh_failed and (accepted is None or cache_key in self.refresh_required):
            return result
        if accepted is None:
            raise TimeoutError("GPU inventory observation expired before delivery.")
        sampled_current = (
            sampled_here
            and result.sampled_current
            and result.observed_at_ms == accepted.observed_at_ms
            and result.payload == accepted.payload
        )
        return replace(accepted, sampled_current=sampled_current, refresh_failed=False)

    def retained_observations(self) -> tuple[GPUInfoObservation, ...]:
        entries = sorted(self.cache_entries.values(), key=lambda entry: entry[0], reverse=True)
        return tuple(copy.deepcopy(entry[1]) for entry in entries)

    def valid_payload_with_gpus(self, now: float, cache_ttl: float) -> JSONDict | None:
        for cache_key, (cached_time, observation) in self.cache_entries.items():
            rows = observation.payload.get("gpus")
            if (
                cache_key not in self.refresh_required
                and now - cached_time <= cache_ttl
                and isinstance(rows, list)
                and any(isinstance(entry, dict) for entry in rows)
            ):
                return copy.deepcopy(observation.payload)
        return None

    def invalidate(self, *, owner: str, reason: str) -> JSONDict:
        require_canonical_trimmed_json_text(
            owner, error_message="GPU invalidation owner is invalid."
        )
        require_canonical_trimmed_json_text(
            reason, error_message="GPU invalidation reason is invalid."
        )
        self.cache_entries.clear()
        self.acquisition_retries.clear()
        self.revision += 1
        self.last_invalidation = {"owner": owner, "reason": reason, "revision": self.revision}
        return copy.deepcopy(self.last_invalidation)

    def diagnostics(self) -> JSONDict:
        return {
            "revision": self.revision,
            "acquisition_sequences": {
                str(key): value for key, value in self.acquisition_sequences.items()
            },
            "last_invalidation": copy.deepcopy(self.last_invalidation),
            "caller_deadline_monotonic": self.last_caller_deadline,
            "probe_deadlines_monotonic": {
                str(key): value.deadline_monotonic
                for key, value in self.acquisition_deadlines.items()
            },
            "admissions_pending": self.admissions_pending,
            "native_probes_pending": sum(
                not worker.done() for worker in self.probe_leader_timed_out
            ),
            "stopping": self.stopping,
            "acquisition_retries": {
                str(scope): {
                    "failure_count": retry.failures,
                    "retry_at_monotonic": retry.retry_at,
                    "healthy_since_monotonic": retry.healthy_since,
                    "failure": str(retry.failure) if retry.failure is not None else None,
                    "diagnostics": (
                        [str(error) for error in retry.observation.diagnostics]
                        if retry.observation is not None
                        else []
                    ),
                }
                for scope, retry in self.acquisition_retries.items()
            },
        }


def capture_gpu_info_observation(payload: JSONDict) -> GPUInfoObservation:
    observed_at = require_non_negative_int_strict(
        epoch_ms(), error_message="GPU observation timestamp is invalid."
    )
    return GPUInfoObservation(copy.deepcopy(payload), observed_at, False, False)


def complete_retained_gpu_probe(
    state: GPUInfoCacheState, worker_lock: threading.RLock, worker: Future[GPUInfoObservation]
) -> None:
    with worker_lock:
        abandoned = state.probe_leader_timed_out.pop(worker, False)
    if worker.cancelled():
        return
    failure = worker.exception()
    if abandoned and failure is not None:
        logger = get_logger(LOGGER_NAME)
        if isinstance(failure, RECOVERABLE_EXCEPTIONS):
            logger.debug("Retained GPU observation settled: %s", type(failure).__name__)
        elif isinstance(failure, Exception):
            log_exception(
                logger,
                failure,
                message="Retained GPU observation failed after its caller timed out.",
                operation=OPERATION_GPU_INVENTORY_RETAINED_PROBE,
            )

"""SoAI - SoAIBench calibrated workload timing [backend/hardware/soaibench/workload_timing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass

from core.hardware.soaibench_workloads import MAX_COMPLETED_DISPATCHES
from core.validation.integers import is_strict_int
from hardware.soaibench.errors import SoAIBenchUnsupported

__all__ = ("MINIMUM_MEASURED_SECONDS", "CalibratedTiming", "measure_calibrated_batches")

MINIMUM_MEASURED_SECONDS = 1.0
MAX_MEASURED_DISPATCHES = MAX_COMPLETED_DISPATCHES


@dataclass(frozen=True, slots=True)
class CalibratedTiming:
    elapsed_seconds: float
    dispatches: int


def measure_calibrated_batches(
    *,
    batch_dispatches: int,
    run_batch: Callable[[int], None],
    reset_initial_state: Callable[[], None],
    minimum_seconds: float = MINIMUM_MEASURED_SECONDS,
) -> CalibratedTiming:
    if (
        not is_strict_int(batch_dispatches)
        or batch_dispatches < 1
        or batch_dispatches > MAX_MEASURED_DISPATCHES
        or not math.isfinite(minimum_seconds)
        or minimum_seconds <= 0.0
    ):
        raise SoAIBenchUnsupported(
            reason="opencl_workload_invalid",
            message="OpenCL workload timing parameters must be positive.",
        )
    _calibrate_batch(
        batch_dispatches=batch_dispatches,
        run_batch=run_batch,
        minimum_seconds=minimum_seconds,
    )
    reset_initial_state()
    started_at = time.monotonic()
    completed_dispatches = 0
    while time.monotonic() - started_at < minimum_seconds:
        if completed_dispatches > MAX_MEASURED_DISPATCHES - batch_dispatches:
            raise SoAIBenchUnsupported(
                reason="opencl_workload_invalid",
                message="OpenCL workload timing exceeded its dispatch bound.",
            )
        run_batch(batch_dispatches)
        completed_dispatches += batch_dispatches
    elapsed_seconds = time.monotonic() - started_at
    if elapsed_seconds < minimum_seconds or completed_dispatches < 1:
        raise SoAIBenchUnsupported(
            reason="opencl_workload_invalid",
            message="OpenCL workload did not complete a measured second.",
        )
    return CalibratedTiming(elapsed_seconds, completed_dispatches)


def _calibrate_batch(
    *,
    batch_dispatches: int,
    run_batch: Callable[[int], None],
    minimum_seconds: float,
) -> None:
    started_at = time.monotonic()
    completed_dispatches = 0
    while time.monotonic() - started_at < minimum_seconds:
        if completed_dispatches > MAX_MEASURED_DISPATCHES - batch_dispatches:
            raise SoAIBenchUnsupported(
                reason="opencl_workload_invalid",
                message="OpenCL workload calibration exceeded its dispatch bound.",
            )
        run_batch(batch_dispatches)
        completed_dispatches += batch_dispatches

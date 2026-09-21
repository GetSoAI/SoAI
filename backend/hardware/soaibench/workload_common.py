"""SoAI - SoAIBench OpenCL workload phase helpers [backend/hardware/soaibench/workload_common.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.hardware.soaibench_numerical import validate_sample_values
from core.hardware.soaibench_workloads import (
    DEFAULT_ELEMENT_COUNT,
    ELEMENT_ALIGNMENT,
    FLOAT_SIZE_BYTES,
    sample_positions,
)
from core.types.json import JSONDict
from hardware.soaibench.errors import SoAIBenchUnsupported
from hardware.soaibench.opencl_program import (
    enqueue_kernel,
    finish_queue,
    read_float_buffer_positions,
    set_uint_arg,
)
from hardware.soaibench.opencl_session import OpenCLExecutionSession
from hardware.soaibench.types import SoAIBenchGpuIdentity
from hardware.soaibench.workload_timing import measure_calibrated_batches

if TYPE_CHECKING:
    from hardware.soaibench.opencl_runtime import OpenCLRuntime

__all__ = (
    "DEFAULT_ELEMENT_COUNT",
    "FLOAT_SIZE_BYTES",
    "KERNEL_OPERATION_ESTIMATE",
    "SoAIBenchPhaseResult",
    "execute_opencl_phase",
)

KERNEL_OPERATION_ESTIMATE = 8
CHECKSUM_SAMPLE_COUNT = 64
MAX_DEVICE_MEMORY_PERCENT = 72
MAX_ALLOC_MEMORY_PERCENT = 85


@dataclass(frozen=True, slots=True)
class SoAIBenchPhaseResult:
    elapsed_seconds: float
    duration_ms: int
    checksum: int
    sample_count: int
    element_count: int
    rounds: int
    dispatches: int
    summary: JSONDict
    sample_positions: tuple[int, ...] = ()
    sample_values: tuple[float, ...] = ()


def execute_opencl_phase(
    *,
    identity: SoAIBenchGpuIdentity,
    source: str,
    kernel_name: str,
    rounds: int,
    repeats: int,
    summary_prefix: str,
    element_count: int = DEFAULT_ELEMENT_COUNT,
    synchronize_each_repeat: bool = False,
    initialization_kernel_name: str | None = None,
    require_exact_element_count: bool = False,
    stress: bool = False,
    session: OpenCLExecutionSession | None = None,
) -> SoAIBenchPhaseResult:
    _validate_workload_shape(rounds=rounds, repeats=repeats, element_count=element_count)
    owned_session = session is None
    execution_session = session or OpenCLExecutionSession(identity)
    started = time.monotonic()
    try:
        runtime = execution_session.runtime_for(identity)
        resolved_element_count = _resolve_element_count(
            runtime,
            element_count,
            require_exact=require_exact_element_count,
        )
        buffer_size_bytes = resolved_element_count * FLOAT_SIZE_BYTES
        resources = execution_session.acquire(
            identity=identity,
            source=source,
            kernel_name=kernel_name,
            initialization_kernel_name=initialization_kernel_name,
            element_count=resolved_element_count,
            buffer_size_bytes=buffer_size_bytes,
        )
        kernel = resources.kernel
        initialization_kernel = resources.initialization_kernel
        buffer = resources.buffer
        set_uint_arg(runtime, kernel, 1, rounds)
        if initialization_kernel:
            set_uint_arg(runtime, initialization_kernel, 1, rounds)
            enqueue_kernel(runtime, initialization_kernel, resolved_element_count)
            finish_queue(runtime)

        def run_batch(batch_dispatches: int) -> None:
            for _repeat in range(batch_dispatches):
                enqueue_kernel(runtime, kernel, resolved_element_count)
                if synchronize_each_repeat:
                    finish_queue(runtime)
            if not synchronize_each_repeat:
                finish_queue(runtime)

        def reset_initial_state() -> None:
            if initialization_kernel:
                enqueue_kernel(runtime, initialization_kernel, resolved_element_count)
                finish_queue(runtime)

        timing = measure_calibrated_batches(
            batch_dispatches=repeats,
            run_batch=run_batch,
            reset_initial_state=reset_initial_state,
        )
        positions = sample_positions(resolved_element_count)
        sample_values = tuple(read_float_buffer_positions(runtime, buffer, positions))
        validate_sample_values(
            summary_prefix,
            resolved_element_count,
            rounds,
            timing.dispatches,
            positions,
            sample_values,
            stress=stress,
        )
        checksum = _checksum(list(sample_values))
        duration_ms = max(1, round((time.monotonic() - started) * 1000))
        return SoAIBenchPhaseResult(
            elapsed_seconds=timing.elapsed_seconds,
            duration_ms=duration_ms,
            checksum=checksum,
            sample_count=timing.dispatches,
            element_count=resolved_element_count,
            rounds=rounds,
            dispatches=timing.dispatches,
            summary={
                f"{summary_prefix}_checksum": checksum,
                f"{summary_prefix}_elements": resolved_element_count,
                f"{summary_prefix}_requested_elements": element_count,
                f"{summary_prefix}_allocation_bytes": buffer_size_bytes,
                f"{summary_prefix}_checksum_sample_count": len(positions),
                "queue_api": runtime.queue_api,
                "match_basis": runtime.match_basis,
                "opencl_platform_name": runtime.platform_name,
                "opencl_platform_vendor": runtime.platform_vendor,
                "opencl_device_name": runtime.device_name,
                "opencl_device_vendor": runtime.device_vendor,
                "opencl_driver_version": runtime.driver_version,
                "opencl_global_mem_bytes": runtime.global_mem_bytes,
                "opencl_max_alloc_bytes": runtime.max_alloc_bytes,
            },
            sample_positions=positions,
            sample_values=sample_values,
        )
    finally:
        if owned_session:
            execution_session.close()


def _resolve_element_count(
    runtime: OpenCLRuntime,
    requested_element_count: int,
    *,
    require_exact: bool,
) -> int:
    max_elements = min(
        _memory_budget_elements(runtime.global_mem_bytes, MAX_DEVICE_MEMORY_PERCENT),
        _memory_budget_elements(runtime.max_alloc_bytes, MAX_ALLOC_MEMORY_PERCENT),
    )
    if requested_element_count <= max_elements:
        return requested_element_count
    if require_exact:
        raise SoAIBenchUnsupported(
            reason="opencl_memory_insufficient",
            message="OpenCL device memory limits are too small for SoAIBench.",
        )
    aligned_elements = _align_down(max_elements, ELEMENT_ALIGNMENT)
    if aligned_elements >= DEFAULT_ELEMENT_COUNT:
        return aligned_elements
    raise SoAIBenchUnsupported(
        reason="opencl_memory_insufficient",
        message="OpenCL device memory limits are too small for SoAIBench.",
    )


def _memory_budget_elements(memory_bytes: int, percent: int) -> int:
    return (memory_bytes * percent // 100) // FLOAT_SIZE_BYTES


def _align_down(value: int, alignment: int) -> int:
    return value - (value % alignment)


def _validate_workload_shape(*, rounds: int, repeats: int, element_count: int) -> None:
    if rounds < 1:
        raise SoAIBenchUnsupported(
            reason="opencl_workload_invalid",
            message="OpenCL workload rounds must be positive.",
        )
    if repeats < 1:
        raise SoAIBenchUnsupported(
            reason="opencl_workload_invalid",
            message="OpenCL workload repeats must be positive.",
        )
    if element_count < 1:
        raise SoAIBenchUnsupported(
            reason="opencl_workload_invalid",
            message="OpenCL workload element count must be positive.",
        )


def _checksum(values: list[float]) -> int:
    checksum = 0
    for index, value in enumerate(values):
        if not math.isfinite(value):
            raise SoAIBenchUnsupported(
                reason="opencl_checksum_failed",
                message="OpenCL workload returned a non-finite value.",
            )
        checksum = (checksum + int(abs(value) * 1000.0) + index) % 2_147_483_647
    if checksum <= 0:
        raise SoAIBenchUnsupported(
            reason="opencl_checksum_failed",
            message="OpenCL workload checksum was empty.",
        )
    return checksum

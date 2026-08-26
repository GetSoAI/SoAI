"""SoAI - SoAIBench OpenCL workload phase helpers [backend/hardware/soaibench/workload_common.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass

from core.types.json import JSONDict
from hardware.soaibench.errors import SoAIBenchUnsupported
from hardware.soaibench.opencl_program import (
    create_buffer,
    create_kernel,
    create_program,
    enqueue_kernel,
    finish_queue,
    read_float_buffer,
    release_buffer,
    release_kernel,
    release_program,
    set_buffer_arg,
    set_uint_arg,
)
from hardware.soaibench.opencl_runtime import (
    OpenCLRuntime,
    build_opencl_runtime,
    release_opencl_runtime,
)
from hardware.soaibench.types import SoAIBenchGpuIdentity

__all__ = (
    "DEFAULT_ELEMENT_COUNT",
    "FLOAT_SIZE_BYTES",
    "KERNEL_OPERATION_ESTIMATE",
    "SoAIBenchPhaseResult",
    "execute_opencl_phase",
)

DEFAULT_ELEMENT_COUNT = 1_048_576
FLOAT_SIZE_BYTES = 4
KERNEL_OPERATION_ESTIMATE = 8
CHECKSUM_SAMPLE_COUNT = 65_536
ELEMENT_ALIGNMENT = 262_144
MAX_DEVICE_MEMORY_PERCENT = 72
MAX_ALLOC_MEMORY_PERCENT = 85


@dataclass(frozen=True, slots=True)
class SoAIBenchPhaseResult:
    elapsed_seconds: float
    duration_ms: int
    checksum: int
    sample_count: int
    element_count: int
    summary: JSONDict


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
) -> SoAIBenchPhaseResult:
    _validate_workload_shape(rounds=rounds, repeats=repeats, element_count=element_count)
    runtime = build_opencl_runtime(identity)
    program = 0
    kernel = 0
    buffer = 0
    started = time.monotonic()
    try:
        resolved_element_count = _resolve_element_count(runtime, element_count)
        buffer_size_bytes = resolved_element_count * FLOAT_SIZE_BYTES
        program = create_program(runtime, source)
        kernel = create_kernel(runtime, program, kernel_name)
        buffer = create_buffer(runtime, buffer_size_bytes)
        set_buffer_arg(runtime, kernel, 0, buffer)
        set_uint_arg(runtime, kernel, 1, rounds)
        phase_started = time.monotonic()
        for _repeat in range(repeats):
            enqueue_kernel(runtime, kernel, resolved_element_count)
            if synchronize_each_repeat:
                finish_queue(runtime)
        if not synchronize_each_repeat:
            finish_queue(runtime)
        elapsed = max(time.monotonic() - phase_started, 0.000001)
        checksum_sample_count = min(CHECKSUM_SAMPLE_COUNT, resolved_element_count)
        output = read_float_buffer(runtime, buffer, checksum_sample_count)
        checksum = _checksum(output)
        duration_ms = max(1, round((time.monotonic() - started) * 1000))
        return SoAIBenchPhaseResult(
            elapsed_seconds=elapsed,
            duration_ms=duration_ms,
            checksum=checksum,
            sample_count=repeats,
            element_count=resolved_element_count,
            summary={
                f"{summary_prefix}_checksum": checksum,
                f"{summary_prefix}_elements": resolved_element_count,
                f"{summary_prefix}_requested_elements": element_count,
                f"{summary_prefix}_allocation_bytes": buffer_size_bytes,
                f"{summary_prefix}_checksum_sample_count": checksum_sample_count,
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
        )
    finally:
        _release_workload_resources(
            runtime=runtime,
            buffer=buffer,
            kernel=kernel,
            program=program,
            primary_exception=sys.exception(),
        )


def _release_workload_resources(
    *,
    runtime: OpenCLRuntime,
    buffer: int,
    kernel: int,
    program: int,
    primary_exception: BaseException | None,
) -> None:
    cleanup_failure: SoAIBenchUnsupported | None = None
    for release, handle in (
        (release_buffer, buffer),
        (release_kernel, kernel),
        (release_program, program),
    ):
        if handle:
            cleanup_failure = _release_workload_handle(
                release,
                runtime,
                handle,
                primary_exception,
                cleanup_failure,
            )
    try:
        release_opencl_runtime(runtime)
    except SoAIBenchUnsupported as exception:
        cleanup_failure = _record_cleanup_failure(
            exception,
            primary_exception,
            cleanup_failure,
        )
    if cleanup_failure is not None and primary_exception is None:
        raise cleanup_failure


def _release_workload_handle(
    release: Callable[[OpenCLRuntime, int], None],
    runtime: OpenCLRuntime,
    handle: int,
    primary_exception: BaseException | None,
    cleanup_failure: SoAIBenchUnsupported | None,
) -> SoAIBenchUnsupported | None:
    try:
        release(runtime, handle)
    except SoAIBenchUnsupported as exception:
        return _record_cleanup_failure(exception, primary_exception, cleanup_failure)
    return cleanup_failure


def _record_cleanup_failure(
    exception: SoAIBenchUnsupported,
    primary_exception: BaseException | None,
    cleanup_failure: SoAIBenchUnsupported | None,
) -> SoAIBenchUnsupported:
    if primary_exception is not None:
        primary_exception.add_note(
            f"OpenCL cleanup failed: {exception.reason}: {exception.message}",
        )
    return cleanup_failure or exception


def _resolve_element_count(runtime: OpenCLRuntime, requested_element_count: int) -> int:
    max_elements = min(
        _memory_budget_elements(runtime.global_mem_bytes, MAX_DEVICE_MEMORY_PERCENT),
        _memory_budget_elements(runtime.max_alloc_bytes, MAX_ALLOC_MEMORY_PERCENT),
    )
    if requested_element_count <= max_elements:
        return requested_element_count
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

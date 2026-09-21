"""SoAI - SoAIBench memory workload phase [backend/hardware/soaibench/workload_memory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.hardware.soaibench_workloads import (
    MEMORY_BATCH_DISPATCHES,
    MEMORY_ELEMENTS,
    MEMORY_ROUNDS,
    counted_bytes,
)
from hardware.soaibench.opencl_session import OpenCLExecutionSession
from hardware.soaibench.types import SoAIBenchGpuIdentity
from hardware.soaibench.workload_common import (
    FLOAT_SIZE_BYTES,
    SoAIBenchPhaseResult,
    execute_opencl_phase,
)

__all__ = (
    "STANDARD_MEMORY_REPEATS",
    "execute_memory_workload",
    "memory_counted_bytes",
    "memory_gbs",
)

STANDARD_MEMORY_REPEATS = MEMORY_BATCH_DISPATCHES
MEMORY_BUFFER_TARGET_BYTES = MEMORY_ELEMENTS * FLOAT_SIZE_BYTES
MEMORY_ELEMENT_COUNT = MEMORY_ELEMENTS

MEMORY_KERNEL_SOURCE = """
__kernel void soaibench_memory_initialize(__global float *data, const uint rounds) {
    const size_t gid = get_global_id(0);
    data[gid] = 0.001f + (float)(gid & 1023) * 0.0001f + (float)(rounds & 0) * 0.0f;
}

__kernel void soaibench_memory(__global float *data, const uint rounds) {
    const size_t gid = get_global_id(0);
    const float value = data[gid];
    data[gid] = value + 0.000001f + (float)(rounds & 0) * 0.0f;
}
"""


def execute_memory_workload(
    identity: SoAIBenchGpuIdentity,
    session: OpenCLExecutionSession | None = None,
) -> SoAIBenchPhaseResult:
    return execute_opencl_phase(
        identity=identity,
        source=MEMORY_KERNEL_SOURCE,
        kernel_name="soaibench_memory",
        rounds=MEMORY_ROUNDS,
        repeats=STANDARD_MEMORY_REPEATS,
        summary_prefix="memory",
        element_count=MEMORY_ELEMENT_COUNT,
        initialization_kernel_name="soaibench_memory_initialize",
        require_exact_element_count=True,
        session=session,
    )


def memory_gbs(result: SoAIBenchPhaseResult) -> float:
    return memory_counted_bytes(result) / result.elapsed_seconds / 1_000_000_000.0


def memory_counted_bytes(result: SoAIBenchPhaseResult) -> int:
    return counted_bytes("memory", result.element_count, result.dispatches)

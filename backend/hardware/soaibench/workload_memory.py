"""SoAI - SoAIBench memory workload phase [backend/hardware/soaibench/workload_memory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from hardware.soaibench.types import SoAIBenchGpuIdentity
from hardware.soaibench.workload_common import (
    FLOAT_SIZE_BYTES,
    SoAIBenchPhaseResult,
    execute_opencl_phase,
)

__all__ = (
    "STANDARD_MEMORY_REPEATS",
    "execute_memory_workload",
    "memory_gbs",
)

STANDARD_MEMORY_REPEATS = 256
MEMORY_ROUNDS = 32
MEMORY_BUFFER_TARGET_BYTES = 268_435_456
MEMORY_ELEMENT_COUNT = MEMORY_BUFFER_TARGET_BYTES // FLOAT_SIZE_BYTES

MEMORY_KERNEL_SOURCE = """
__kernel void soaibench_memory(__global volatile float *data, const uint rounds) {
    const size_t gid = get_global_id(0);
    float value = 0.001f + (float)(gid & 1023) * 0.0001f;
    for (uint i = 0; i < rounds; i++) {
        value = value + 0.000001f;
        data[gid] = value;
        value = data[gid];
    }
}
"""


def execute_memory_workload(identity: SoAIBenchGpuIdentity) -> SoAIBenchPhaseResult:
    return execute_opencl_phase(
        identity=identity,
        source=MEMORY_KERNEL_SOURCE,
        kernel_name="soaibench_memory",
        rounds=MEMORY_ROUNDS,
        repeats=STANDARD_MEMORY_REPEATS,
        summary_prefix="memory",
        element_count=MEMORY_ELEMENT_COUNT,
        synchronize_each_repeat=True,
    )


def memory_gbs(result: SoAIBenchPhaseResult) -> float:
    bytes_touched = (
        result.element_count * FLOAT_SIZE_BYTES * MEMORY_ROUNDS * result.sample_count * 2
    )
    return bytes_touched / result.elapsed_seconds / 1_000_000_000.0

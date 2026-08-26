"""SoAI - SoAIBench mixed high-power workload phase [backend/hardware/soaibench/workload_mixed.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from hardware.soaibench.types import SoAIBenchGpuIdentity
from hardware.soaibench.workload_common import (
    FLOAT_SIZE_BYTES,
    KERNEL_OPERATION_ESTIMATE,
    SoAIBenchPhaseResult,
    execute_opencl_phase,
)

__all__ = (
    "STANDARD_MIXED_REPEATS",
    "STRESS_MIXED_REPEATS",
    "execute_mixed_workload",
    "mixed_compute_gops",
    "mixed_memory_gbs",
)

STANDARD_MIXED_REPEATS = 64
STRESS_MIXED_REPEATS = 64
STANDARD_MIXED_ROUNDS = 128
STRESS_MIXED_ROUNDS = 160
STANDARD_MIXED_ELEMENT_COUNT = 4_194_304
STRESS_MIXED_ELEMENT_COUNT = 4_194_304

MIXED_KERNEL_SOURCE = """
__kernel void soaibench_mixed(__global volatile float *data, const uint rounds) {
    const size_t gid = get_global_id(0);
    float value = 0.001f + (float)(gid & 1023) * 0.0001f;
    for (uint i = 0; i < rounds; i++) {
        value = fma(value, 1.000001f, 0.000001f);
        value = sin(value) + cos(value * 0.5f) + sqrt(fabs(value) + 1.0f);
        value = value + 0.000001f;
        data[gid] = value;
        value = data[gid];
    }
    data[gid] = value;
}
"""


def execute_mixed_workload(
    identity: SoAIBenchGpuIdentity,
    *,
    stress: bool,
) -> SoAIBenchPhaseResult:
    return execute_opencl_phase(
        identity=identity,
        source=MIXED_KERNEL_SOURCE,
        kernel_name="soaibench_mixed",
        rounds=STRESS_MIXED_ROUNDS if stress else STANDARD_MIXED_ROUNDS,
        repeats=STRESS_MIXED_REPEATS if stress else STANDARD_MIXED_REPEATS,
        summary_prefix="mixed",
        element_count=STRESS_MIXED_ELEMENT_COUNT if stress else STANDARD_MIXED_ELEMENT_COUNT,
        synchronize_each_repeat=True,
    )


def mixed_compute_gops(result: SoAIBenchPhaseResult, *, stress: bool) -> float:
    rounds = STRESS_MIXED_ROUNDS if stress else STANDARD_MIXED_ROUNDS
    operations = result.element_count * rounds * result.sample_count * KERNEL_OPERATION_ESTIMATE
    return operations / result.elapsed_seconds / 1_000_000_000.0


def mixed_memory_gbs(result: SoAIBenchPhaseResult, *, stress: bool) -> float:
    rounds = STRESS_MIXED_ROUNDS if stress else STANDARD_MIXED_ROUNDS
    bytes_touched = result.element_count * FLOAT_SIZE_BYTES * rounds * result.sample_count * 2
    return bytes_touched / result.elapsed_seconds / 1_000_000_000.0

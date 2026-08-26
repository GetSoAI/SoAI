"""SoAI - SoAIBench compute workload phase [backend/hardware/soaibench/workload_compute.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from hardware.soaibench.types import SoAIBenchGpuIdentity
from hardware.soaibench.workload_common import (
    DEFAULT_ELEMENT_COUNT,
    KERNEL_OPERATION_ESTIMATE,
    SoAIBenchPhaseResult,
    execute_opencl_phase,
)

__all__ = (
    "STANDARD_COMPUTE_REPEATS",
    "compute_gops",
    "execute_compute_workload",
)

STANDARD_COMPUTE_REPEATS = 96
COMPUTE_ROUNDS = 512
COMPUTE_ELEMENT_COUNT = DEFAULT_ELEMENT_COUNT * 4

COMPUTE_KERNEL_SOURCE = """
__kernel void soaibench_compute(__global float *data, const uint rounds) {
    const size_t gid = get_global_id(0);
    float value = 0.001f + (float)(gid & 1023) * 0.0001f;
    for (uint i = 0; i < rounds; i++) {
        value = fma(value, 1.000001f, 0.000001f);
        value = sin(value) + cos(value * 0.5f) + sqrt(fabs(value) + 1.0f);
    }
    data[gid] = value;
}
"""


def execute_compute_workload(identity: SoAIBenchGpuIdentity) -> SoAIBenchPhaseResult:
    return execute_opencl_phase(
        identity=identity,
        source=COMPUTE_KERNEL_SOURCE,
        kernel_name="soaibench_compute",
        rounds=COMPUTE_ROUNDS,
        repeats=STANDARD_COMPUTE_REPEATS,
        summary_prefix="compute",
        element_count=COMPUTE_ELEMENT_COUNT,
    )


def compute_gops(result: SoAIBenchPhaseResult) -> float:
    operations = (
        result.element_count * COMPUTE_ROUNDS * result.sample_count * KERNEL_OPERATION_ESTIMATE
    )
    return operations / result.elapsed_seconds / 1_000_000_000.0

"""SoAI - SoAIBench latency workload phase [backend/hardware/soaibench/workload_latency.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.hardware.soaibench_workloads import (
    LATENCY_BATCH_DISPATCHES,
    LATENCY_ELEMENTS,
    LATENCY_ROUNDS,
)
from hardware.soaibench.opencl_session import OpenCLExecutionSession
from hardware.soaibench.types import SoAIBenchGpuIdentity
from hardware.soaibench.workload_common import (
    SoAIBenchPhaseResult,
    execute_opencl_phase,
)

__all__ = (
    "LATENCY_SCORE_RATE_DIVISOR",
    "execute_latency_workload",
    "latency_dispatches_per_second",
    "latency_score",
    "latency_us",
)

LATENCY_REPEATS = LATENCY_BATCH_DISPATCHES
LATENCY_ELEMENT_COUNT = LATENCY_ELEMENTS
LATENCY_SCORE_RATE_DIVISOR = 20.0

LATENCY_KERNEL_SOURCE = """
__kernel void soaibench_latency(__global float *data, const uint rounds) {
    const size_t gid = get_global_id(0);
    float value = 0.002f + (float)(gid & 255) * 0.0009765625f;
    float gate = 0.5f;
    for (uint i = 0; i < rounds; i++) {
        const float token = (float)((gid + i) & 31) * 0.03125f;
        value = fma(value, 1.0003f, token);
        gate = fma(gate, 0.9991f, value * 0.00001f);
        value = (value / (fabs(value) + 1.0f)) + gate;
    }
    data[gid] = value;
}
"""


def execute_latency_workload(
    identity: SoAIBenchGpuIdentity,
    session: OpenCLExecutionSession | None = None,
) -> SoAIBenchPhaseResult:
    return execute_opencl_phase(
        identity=identity,
        source=LATENCY_KERNEL_SOURCE,
        kernel_name="soaibench_latency",
        rounds=LATENCY_ROUNDS,
        repeats=LATENCY_REPEATS,
        summary_prefix="latency",
        element_count=LATENCY_ELEMENT_COUNT,
        synchronize_each_repeat=True,
        session=session,
    )


def latency_dispatches_per_second(result: SoAIBenchPhaseResult) -> float:
    return round(1_000_000.0 / latency_us(result), 6)


def latency_us(result: SoAIBenchPhaseResult) -> float:
    return round(result.elapsed_seconds * 1_000_000.0 / result.sample_count, 6)


def latency_score(result: SoAIBenchPhaseResult) -> float:
    return latency_dispatches_per_second(result) / LATENCY_SCORE_RATE_DIVISOR

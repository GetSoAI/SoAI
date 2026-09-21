"""SoAI - SoAIBench ALU workload phase [backend/hardware/soaibench/workload_alu.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.hardware.soaibench_workloads import (
    ALU_BATCH_DISPATCHES,
    ALU_MAXIMUM_ELEMENTS,
    ALU_OPERATION_FACTOR,
    ALU_ROUNDS,
    counted_operations,
)
from hardware.soaibench.opencl_session import OpenCLExecutionSession
from hardware.soaibench.types import SoAIBenchGpuIdentity
from hardware.soaibench.workload_common import (
    SoAIBenchPhaseResult,
    execute_opencl_phase,
)

__all__ = (
    "STANDARD_ALU_REPEATS",
    "alu_counted_operations",
    "alu_gops",
    "execute_alu_workload",
)

STANDARD_ALU_REPEATS = ALU_BATCH_DISPATCHES
ALU_ELEMENT_COUNT = ALU_MAXIMUM_ELEMENTS
ALU_OPERATIONS_PER_ROUND = ALU_OPERATION_FACTOR

ALU_KERNEL_SOURCE = """
__kernel void soaibench_alu(__global float *data, const uint rounds) {
    const size_t gid = get_global_id(0);
    float a0 = 0.001f + (float)(gid & 255) * 0.0001f;
    float a1 = a0 + 0.002f;
    float a2 = a0 + 0.003f;
    float a3 = a0 + 0.004f;
    float a4 = a0 + 0.005f;
    float a5 = a0 + 0.006f;
    float a6 = a0 + 0.007f;
    float a7 = a0 + 0.008f;
    for (uint i = 0; i < rounds; i++) {
        a0 = fma(a0, 1.000001f, 0.000001f + a4 * 0.000001f);
        a1 = fma(a1, 1.000002f, 0.000002f + a5 * 0.000001f);
        a2 = fma(a2, 1.000003f, 0.000003f + a6 * 0.000001f);
        a3 = fma(a3, 1.000004f, 0.000004f + a7 * 0.000001f);
        a4 = fma(a4, 0.999999f, 0.000005f + a0 * 0.000001f);
        a5 = fma(a5, 0.999998f, 0.000006f + a1 * 0.000001f);
        a6 = fma(a6, 0.999997f, 0.000007f + a2 * 0.000001f);
        a7 = fma(a7, 0.999996f, 0.000008f + a3 * 0.000001f);
        a0 = fma(a0, 0.999991f, 0.000009f + a7 * 0.000001f);
        a1 = fma(a1, 0.999992f, 0.000010f + a6 * 0.000001f);
        a2 = fma(a2, 0.999993f, 0.000011f + a5 * 0.000001f);
        a3 = fma(a3, 0.999994f, 0.000012f + a4 * 0.000001f);
        a4 = fma(a4, 1.000009f, 0.000013f + a3 * 0.000001f);
        a5 = fma(a5, 1.000008f, 0.000014f + a2 * 0.000001f);
        a6 = fma(a6, 1.000007f, 0.000015f + a1 * 0.000001f);
        a7 = fma(a7, 1.000006f, 0.000016f + a0 * 0.000001f);
    }
    data[gid] = a0 + a1 + a2 + a3 + a4 + a5 + a6 + a7;
}
"""


def execute_alu_workload(
    identity: SoAIBenchGpuIdentity,
    session: OpenCLExecutionSession | None = None,
) -> SoAIBenchPhaseResult:
    return execute_opencl_phase(
        identity=identity,
        source=ALU_KERNEL_SOURCE,
        kernel_name="soaibench_alu",
        rounds=ALU_ROUNDS,
        repeats=STANDARD_ALU_REPEATS,
        summary_prefix="alu",
        element_count=ALU_ELEMENT_COUNT,
        session=session,
    )


def alu_gops(result: SoAIBenchPhaseResult) -> float:
    return alu_counted_operations(result) / result.elapsed_seconds / 1_000_000_000.0


def alu_counted_operations(result: SoAIBenchPhaseResult) -> int:
    return counted_operations(
        "alu",
        result.element_count,
        result.rounds,
        result.dispatches,
    )

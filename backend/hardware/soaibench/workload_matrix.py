"""SoAI - SoAIBench matrix dense workload phase [backend/hardware/soaibench/workload_matrix.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.hardware.soaibench_workloads import (
    MATRIX_BATCH_DISPATCHES,
    MATRIX_MAXIMUM_ELEMENTS,
    MATRIX_OPERATION_FACTOR,
    MATRIX_ROUNDS,
    counted_operations,
)
from hardware.soaibench.opencl_session import OpenCLExecutionSession
from hardware.soaibench.types import SoAIBenchGpuIdentity
from hardware.soaibench.workload_common import (
    SoAIBenchPhaseResult,
    execute_opencl_phase,
)

__all__ = (
    "STANDARD_MATRIX_REPEATS",
    "execute_matrix_workload",
    "matrix_counted_operations",
    "matrix_gops",
)

STANDARD_MATRIX_REPEATS = MATRIX_BATCH_DISPATCHES
MATRIX_ELEMENT_COUNT = MATRIX_MAXIMUM_ELEMENTS
MATRIX_OPERATIONS_PER_ROUND = MATRIX_OPERATION_FACTOR

MATRIX_KERNEL_SOURCE = """
__kernel void soaibench_matrix_dense(__global float *data, const uint rounds) {
    const size_t gid = get_global_id(0);
    const uint row = (uint)(gid >> 10);
    const uint col = (uint)(gid & 1023);
    float acc0 = 0.0f;
    float acc1 = 0.0f;
    float acc2 = 0.0f;
    float acc3 = 0.0f;
    float grad0 = 0.001f;
    float grad1 = 0.002f;
    float grad2 = 0.003f;
    float grad3 = 0.004f;
    for (uint k = 0; k < rounds; k++) {
        const float activation = 0.001f + (float)((row + k) & 255) * 0.00390625f;
        const float weight0 = 0.002f + (float)((col + k) & 255) * 0.00390625f;
        const float weight1 = 0.003f + (float)((col + k + 17) & 255) * 0.00390625f;
        const float weight2 = 0.004f + (float)((col + k + 43) & 255) * 0.00390625f;
        const float weight3 = 0.005f + (float)((col + k + 71) & 255) * 0.00390625f;
        acc0 = fma(activation, weight0, acc0);
        acc1 = fma(activation, weight1, acc1);
        acc2 = fma(activation, weight2, acc2);
        acc3 = fma(activation, weight3, acc3);
        grad0 = fma(acc0, 0.000001f, grad0);
        grad1 = fma(acc1, 0.000001f, grad1);
        grad2 = fma(acc2, 0.000001f, grad2);
        grad3 = fma(acc3, 0.000001f, grad3);
    }
    data[gid] = (acc0 + acc1 + acc2 + acc3 + grad0 + grad1 + grad2 + grad3) * 0.000244140625f;
}
"""


def execute_matrix_workload(
    identity: SoAIBenchGpuIdentity,
    session: OpenCLExecutionSession | None = None,
) -> SoAIBenchPhaseResult:
    return execute_opencl_phase(
        identity=identity,
        source=MATRIX_KERNEL_SOURCE,
        kernel_name="soaibench_matrix_dense",
        rounds=MATRIX_ROUNDS,
        repeats=STANDARD_MATRIX_REPEATS,
        summary_prefix="matrix",
        element_count=MATRIX_ELEMENT_COUNT,
        session=session,
    )


def matrix_gops(result: SoAIBenchPhaseResult) -> float:
    return matrix_counted_operations(result) / result.elapsed_seconds / 1_000_000_000.0


def matrix_counted_operations(result: SoAIBenchPhaseResult) -> int:
    return counted_operations(
        "matrix",
        result.element_count,
        result.rounds,
        result.dispatches,
    )

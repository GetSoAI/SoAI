"""SoAI - SoAIBench compute workload phase [backend/hardware/soaibench/workload_compute.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.hardware.soaibench_workloads import (
    COMPUTE_BATCH_DISPATCHES,
    COMPUTE_MAXIMUM_ELEMENTS,
    COMPUTE_ROUNDS,
    counted_operations,
)
from hardware.soaibench.opencl_session import OpenCLExecutionSession
from hardware.soaibench.types import SoAIBenchGpuIdentity
from hardware.soaibench.workload_common import (
    SoAIBenchPhaseResult,
    execute_opencl_phase,
)
from hardware.soaibench.workload_transcendental_program import (
    TRANSCENDENTAL_KERNEL_NAME,
    TRANSCENDENTAL_KERNEL_SOURCE,
)

__all__ = (
    "STANDARD_COMPUTE_REPEATS",
    "compute_counted_operations",
    "compute_gops",
    "execute_compute_workload",
)

STANDARD_COMPUTE_REPEATS = COMPUTE_BATCH_DISPATCHES
COMPUTE_ELEMENT_COUNT = COMPUTE_MAXIMUM_ELEMENTS


def execute_compute_workload(
    identity: SoAIBenchGpuIdentity,
    session: OpenCLExecutionSession | None = None,
) -> SoAIBenchPhaseResult:
    return execute_opencl_phase(
        identity=identity,
        source=TRANSCENDENTAL_KERNEL_SOURCE,
        kernel_name=TRANSCENDENTAL_KERNEL_NAME,
        rounds=COMPUTE_ROUNDS,
        repeats=STANDARD_COMPUTE_REPEATS,
        summary_prefix="compute",
        element_count=COMPUTE_ELEMENT_COUNT,
        session=session,
    )


def compute_gops(result: SoAIBenchPhaseResult) -> float:
    return compute_counted_operations(result) / result.elapsed_seconds / 1_000_000_000.0


def compute_counted_operations(result: SoAIBenchPhaseResult) -> int:
    return counted_operations(
        "compute",
        result.element_count,
        result.rounds,
        result.dispatches,
    )

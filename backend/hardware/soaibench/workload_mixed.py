"""SoAI - SoAIBench mixed high-power workload phase [backend/hardware/soaibench/workload_mixed.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.hardware.soaibench_workloads import (
    MIXED_BATCH_DISPATCHES,
    MIXED_ELEMENTS,
    MIXED_STANDARD_ROUNDS,
    MIXED_STRESS_ROUNDS,
    counted_bytes,
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
    "STANDARD_MIXED_REPEATS",
    "STRESS_MIXED_REPEATS",
    "execute_mixed_workload",
    "mixed_counted_bytes",
    "mixed_counted_operations",
    "mixed_compute_gops",
    "mixed_memory_gbs",
)

STANDARD_MIXED_REPEATS = MIXED_BATCH_DISPATCHES
STRESS_MIXED_REPEATS = MIXED_BATCH_DISPATCHES
STANDARD_MIXED_ROUNDS = MIXED_STANDARD_ROUNDS
STRESS_MIXED_ROUNDS = MIXED_STRESS_ROUNDS
STANDARD_MIXED_ELEMENT_COUNT = MIXED_ELEMENTS
STRESS_MIXED_ELEMENT_COUNT = MIXED_ELEMENTS


def execute_mixed_workload(
    identity: SoAIBenchGpuIdentity,
    *,
    stress: bool,
    session: OpenCLExecutionSession | None = None,
) -> SoAIBenchPhaseResult:
    return execute_opencl_phase(
        identity=identity,
        source=TRANSCENDENTAL_KERNEL_SOURCE,
        kernel_name=TRANSCENDENTAL_KERNEL_NAME,
        rounds=STRESS_MIXED_ROUNDS if stress else STANDARD_MIXED_ROUNDS,
        repeats=STRESS_MIXED_REPEATS if stress else STANDARD_MIXED_REPEATS,
        summary_prefix="mixed",
        element_count=STRESS_MIXED_ELEMENT_COUNT if stress else STANDARD_MIXED_ELEMENT_COUNT,
        synchronize_each_repeat=True,
        stress=stress,
        session=session,
    )


def mixed_compute_gops(result: SoAIBenchPhaseResult, *, stress: bool) -> float:
    del stress
    return mixed_counted_operations(result) / result.elapsed_seconds / 1_000_000_000.0


def mixed_memory_gbs(result: SoAIBenchPhaseResult, *, stress: bool) -> float:
    del stress
    return mixed_counted_bytes(result) / result.elapsed_seconds / 1_000_000_000.0


def mixed_counted_operations(result: SoAIBenchPhaseResult) -> int:
    return counted_operations(
        "mixed",
        result.element_count,
        result.rounds,
        result.dispatches,
        stress=result.rounds == STRESS_MIXED_ROUNDS,
    )


def mixed_counted_bytes(result: SoAIBenchPhaseResult) -> int:
    return counted_bytes("mixed", result.element_count, result.dispatches)

"""SoAI - SoAIBench workload orchestration [backend/hardware/soaibench/workload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.types.json import JSONDict
from hardware.soaibench.scoring import score_payload
from hardware.soaibench.types import SoAIBenchGpuIdentity
from hardware.soaibench.workload_alu import alu_gops, execute_alu_workload
from hardware.soaibench.workload_common import SoAIBenchPhaseResult
from hardware.soaibench.workload_compute import compute_gops, execute_compute_workload
from hardware.soaibench.workload_latency import (
    execute_latency_workload,
    latency_dispatches_per_second,
    latency_score,
    latency_us,
)
from hardware.soaibench.workload_matrix import execute_matrix_workload, matrix_gops
from hardware.soaibench.workload_memory import execute_memory_workload, memory_gbs
from hardware.soaibench.workload_mixed import (
    execute_mixed_workload,
    mixed_compute_gops,
    mixed_memory_gbs,
)

__all__ = (
    "SoAIBenchWorkloadResult",
    "execute_soaibench_alu_phase",
    "execute_soaibench_compute_phase",
    "execute_soaibench_latency_phase",
    "execute_soaibench_matrix_phase",
    "execute_soaibench_memory_phase",
    "execute_soaibench_mixed_phase",
    "score_standard_phases",
    "score_stress_phase",
)


@dataclass(frozen=True, slots=True)
class SoAIBenchWorkloadResult:
    score_fields: JSONDict
    summary: JSONDict
    duration_ms: int
    sample_count: int


def execute_soaibench_alu_phase(
    identity: SoAIBenchGpuIdentity,
) -> SoAIBenchPhaseResult:
    return execute_alu_workload(identity)


def execute_soaibench_compute_phase(
    identity: SoAIBenchGpuIdentity,
) -> SoAIBenchPhaseResult:
    return execute_compute_workload(identity)


def execute_soaibench_matrix_phase(
    identity: SoAIBenchGpuIdentity,
) -> SoAIBenchPhaseResult:
    return execute_matrix_workload(identity)


def execute_soaibench_latency_phase(
    identity: SoAIBenchGpuIdentity,
) -> SoAIBenchPhaseResult:
    return execute_latency_workload(identity)


def execute_soaibench_memory_phase(
    identity: SoAIBenchGpuIdentity,
) -> SoAIBenchPhaseResult:
    return execute_memory_workload(identity)


def execute_soaibench_mixed_phase(
    identity: SoAIBenchGpuIdentity,
    stress: bool,
) -> SoAIBenchPhaseResult:
    return execute_mixed_workload(identity, stress=stress)


def score_standard_phases(
    *,
    alu: SoAIBenchPhaseResult,
    compute: SoAIBenchPhaseResult,
    matrix: SoAIBenchPhaseResult,
    memory: SoAIBenchPhaseResult,
    mixed: SoAIBenchPhaseResult,
    latency: SoAIBenchPhaseResult,
) -> SoAIBenchWorkloadResult:
    sample_count = (
        alu.sample_count
        + compute.sample_count
        + matrix.sample_count
        + memory.sample_count
        + mixed.sample_count
        + latency.sample_count
    )
    duration_ms = (
        alu.duration_ms
        + compute.duration_ms
        + matrix.duration_ms
        + memory.duration_ms
        + mixed.duration_ms
        + latency.duration_ms
    )
    alu_throughput = alu_gops(alu)
    matrix_throughput = matrix_gops(matrix)
    latency_points = latency_score(latency)
    compute_throughput = (
        alu_throughput
        + matrix_throughput
        + compute_gops(compute)
        + mixed_compute_gops(mixed, stress=False)
    ) / 4
    memory_throughput = (memory_gbs(memory) + mixed_memory_gbs(mixed, stress=False)) / 2
    score_fields = score_payload(
        compute_gops=compute_throughput,
        memory_gbs=memory_throughput,
        duration_ms=duration_ms,
        sample_count=sample_count,
        stability_multiplier=1.0,
        latency_score=latency_points,
    )
    rounded_alu_gops = round(alu_throughput, 6)
    rounded_matrix_gops = round(matrix_throughput, 6)
    rounded_latency_score = round(latency_points)
    rounded_latency_us = round(latency_us(latency), 6)
    rounded_latency_dispatches = round(latency_dispatches_per_second(latency), 6)
    return SoAIBenchWorkloadResult(
        score_fields={
            **score_fields,
            "alu_gops": rounded_alu_gops,
            "matrix_gops": rounded_matrix_gops,
            "latency_score": rounded_latency_score,
            "latency_us": rounded_latency_us,
            "latency_dispatches_per_second": rounded_latency_dispatches,
        },
        summary={
            **alu.summary,
            **compute.summary,
            **matrix.summary,
            **latency.summary,
            **memory.summary,
            **mixed.summary,
            "alu_gops": rounded_alu_gops,
            "matrix_gops": rounded_matrix_gops,
            "latency_score": rounded_latency_score,
            "latency_us": rounded_latency_us,
            "latency_dispatches_per_second": rounded_latency_dispatches,
        },
        duration_ms=duration_ms,
        sample_count=sample_count,
    )


def score_stress_phase(result: SoAIBenchPhaseResult) -> SoAIBenchWorkloadResult:
    return SoAIBenchWorkloadResult(
        score_fields=score_payload(
            compute_gops=mixed_compute_gops(result, stress=True),
            memory_gbs=mixed_memory_gbs(result, stress=True),
            duration_ms=result.duration_ms,
            sample_count=result.sample_count,
            stability_multiplier=1.0,
        ),
        summary=result.summary,
        duration_ms=result.duration_ms,
        sample_count=result.sample_count,
    )

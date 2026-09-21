"""SoAI - SoAIBench workload orchestration [backend/hardware/soaibench/workload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.hardware.soaibench_evidence import PhaseAccounting, standard_measurements
from core.types.json import JSONDict
from hardware.soaibench.scoring import score_payload
from hardware.soaibench.workload_alu import (
    alu_counted_operations,
    alu_gops,
)
from hardware.soaibench.workload_common import SoAIBenchPhaseResult
from hardware.soaibench.workload_compute import (
    compute_counted_operations,
    compute_gops,
)
from hardware.soaibench.workload_evidence import final_write_bytes, phase_evidence
from hardware.soaibench.workload_latency import (
    latency_dispatches_per_second,
    latency_score,
    latency_us,
)
from hardware.soaibench.workload_matrix import (
    matrix_counted_operations,
    matrix_gops,
)
from hardware.soaibench.workload_memory import memory_counted_bytes
from hardware.soaibench.workload_mixed import (
    mixed_compute_gops,
    mixed_counted_bytes,
    mixed_counted_operations,
    mixed_memory_gbs,
)

__all__ = (
    "SoAIBenchStandardPhases",
    "SoAIBenchWorkloadResult",
    "score_standard_phases",
    "score_stress_phase",
)


@dataclass(frozen=True, slots=True)
class SoAIBenchWorkloadResult:
    score_fields: JSONDict
    summary: JSONDict
    duration_ms: int
    sample_count: int
    active_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class SoAIBenchStandardPhases:
    alu: SoAIBenchPhaseResult
    compute: SoAIBenchPhaseResult
    matrix: SoAIBenchPhaseResult
    memory: SoAIBenchPhaseResult
    mixed: SoAIBenchPhaseResult
    latency: SoAIBenchPhaseResult


def score_standard_phases(phases: SoAIBenchStandardPhases) -> SoAIBenchWorkloadResult:
    alu = phases.alu
    compute = phases.compute
    matrix = phases.matrix
    memory = phases.memory
    mixed = phases.mixed
    latency = phases.latency
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
    compute_elapsed_seconds = (
        alu.elapsed_seconds
        + compute.elapsed_seconds
        + matrix.elapsed_seconds
        + mixed.elapsed_seconds
    )
    active_seconds = compute_elapsed_seconds + memory.elapsed_seconds + latency.elapsed_seconds
    measurements = standard_measurements(
        alu=PhaseAccounting(alu.elapsed_seconds, alu.element_count, alu.rounds, alu.dispatches),
        compute=PhaseAccounting(
            compute.elapsed_seconds, compute.element_count, compute.rounds, compute.dispatches
        ),
        matrix=PhaseAccounting(
            matrix.elapsed_seconds, matrix.element_count, matrix.rounds, matrix.dispatches
        ),
        mixed=PhaseAccounting(
            mixed.elapsed_seconds, mixed.element_count, mixed.rounds, mixed.dispatches
        ),
        memory=PhaseAccounting(
            memory.elapsed_seconds, memory.element_count, memory.rounds, memory.dispatches
        ),
        latency=PhaseAccounting(
            latency.elapsed_seconds, latency.element_count, latency.rounds, latency.dispatches
        ),
    )
    compute_throughput = measurements.compute_gops
    memory_throughput = measurements.memory_gbs
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
            "workload_evidence": {
                "alu": phase_evidence(
                    alu,
                    counted_operations=alu_counted_operations(alu),
                    counted_bytes=final_write_bytes(alu),
                    throughput=alu_throughput,
                ),
                "compute": phase_evidence(
                    compute,
                    counted_operations=compute_counted_operations(compute),
                    counted_bytes=final_write_bytes(compute),
                    throughput=compute_gops(compute),
                ),
                "matrix": phase_evidence(
                    matrix,
                    counted_operations=matrix_counted_operations(matrix),
                    counted_bytes=final_write_bytes(matrix),
                    throughput=matrix_throughput,
                ),
                "latency": phase_evidence(
                    latency,
                    counted_operations=0,
                    counted_bytes=final_write_bytes(latency),
                    throughput=latency.dispatches / latency.elapsed_seconds,
                ),
                "memory": phase_evidence(
                    memory,
                    counted_operations=0,
                    counted_bytes=memory_counted_bytes(memory),
                    throughput=memory_throughput,
                ),
                "mixed": phase_evidence(
                    mixed,
                    counted_operations=mixed_counted_operations(mixed),
                    counted_bytes=mixed_counted_bytes(mixed),
                    throughput=mixed_compute_gops(mixed, stress=False),
                ),
            },
        },
        duration_ms=duration_ms,
        sample_count=sample_count,
        active_seconds=active_seconds,
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
        summary={
            **result.summary,
            "workload_evidence": {
                "mixed": phase_evidence(
                    result,
                    counted_operations=mixed_counted_operations(result),
                    counted_bytes=mixed_counted_bytes(result),
                    throughput=mixed_compute_gops(result, stress=True),
                ),
            },
        },
        duration_ms=result.duration_ms,
        sample_count=result.sample_count,
        active_seconds=result.elapsed_seconds,
    )

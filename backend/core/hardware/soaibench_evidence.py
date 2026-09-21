"""SoAI - SoAIBench evidence validation [backend/core/hardware/soaibench_evidence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from dataclasses import dataclass

from core.hardware.soaibench_numerical import validate_sample_values
from core.hardware.soaibench_workloads import (
    ELEMENT_ALIGNMENT,
    MINIMUM_PHASE_SECONDS,
    counted_bytes,
    counted_operations,
    sample_positions,
    workload_spec,
)
from core.validation.strict_integer import is_strict_int

__all__ = (
    "SoAIBenchEvidenceError",
    "minimum_measured_duration_ms",
    "validate_workload_phase",
)


class SoAIBenchEvidenceError(ValueError):
    __slots__ = ()


@dataclass(frozen=True, slots=True)
class PhaseAccounting:
    elapsed_seconds: float
    element_count: int
    rounds: int
    dispatches: int


@dataclass(frozen=True, slots=True)
class StandardMeasurements:
    compute_gops: float
    memory_gbs: float
    alu_gops: float
    matrix_gops: float
    latency_us: float
    latency_dispatches_per_second: float
    sample_count: int


def minimum_measured_duration_ms(phases: tuple[PhaseAccounting, ...]) -> int:
    if not phases:
        raise SoAIBenchEvidenceError("SoAIBench measured duration requires phase evidence.")
    if any(
        not math.isfinite(phase.elapsed_seconds) or phase.elapsed_seconds <= 0 for phase in phases
    ):
        raise SoAIBenchEvidenceError("SoAIBench phase elapsed time must be positive and finite.")
    return sum(max(1, round(phase.elapsed_seconds * 1000)) for phase in phases)


def standard_measurements(
    *,
    alu: PhaseAccounting,
    compute: PhaseAccounting,
    matrix: PhaseAccounting,
    mixed: PhaseAccounting,
    memory: PhaseAccounting,
    latency: PhaseAccounting,
) -> StandardMeasurements:
    compute_phases = (("alu", alu), ("compute", compute), ("matrix", matrix), ("mixed", mixed))
    operations = tuple(
        counted_operations(name, phase.element_count, phase.rounds, phase.dispatches)
        for name, phase in compute_phases
    )
    phases = (alu, compute, matrix, mixed, memory, latency)
    minimum_measured_duration_ms(phases)
    latency_us = round(latency.elapsed_seconds * 1_000_000 / latency.dispatches, 6)
    if latency_us <= 0:
        raise SoAIBenchEvidenceError(
            "SoAIBench latency cannot be represented at measurement precision."
        )
    return StandardMeasurements(
        compute_gops=sum(operations)
        / sum(phase.elapsed_seconds for _, phase in compute_phases)
        / 1_000_000_000,
        memory_gbs=counted_bytes("memory", memory.element_count, memory.dispatches)
        / memory.elapsed_seconds
        / 1_000_000_000,
        alu_gops=operations[0] / alu.elapsed_seconds / 1_000_000_000,
        matrix_gops=operations[2] / matrix.elapsed_seconds / 1_000_000_000,
        latency_us=latency_us,
        latency_dispatches_per_second=round(1_000_000 / latency_us, 6),
        sample_count=sum(phase.dispatches for phase in phases),
    )


def validate_workload_phase(
    name: str,
    elapsed_seconds: float,
    element_count: int,
    rounds: int,
    dispatches: int,
    counted_operations_value: int,
    counted_bytes_value: int,
    throughput: float,
    positions: tuple[int, ...],
    values: tuple[float, ...],
    *,
    stress: bool = False,
) -> None:
    spec = workload_spec(name, stress=stress)
    elements_valid = (
        element_count == spec.maximum_elements
        if spec.exact_elements
        else spec.minimum_elements <= element_count <= spec.maximum_elements
        and element_count % ELEMENT_ALIGNMENT == 0
    )
    if (
        not math.isfinite(elapsed_seconds)
        or not math.isfinite(throughput)
        or throughput <= 0.0
        or elapsed_seconds < MINIMUM_PHASE_SECONDS
    ):
        raise SoAIBenchEvidenceError("SoAIBench workload timing evidence is invalid.")
    if (
        not is_strict_int(dispatches)
        or dispatches < spec.batch_dispatches
        or dispatches % spec.batch_dispatches != 0
    ):
        raise SoAIBenchEvidenceError("SoAIBench workload timing evidence is invalid.")
    if rounds != spec.rounds or not elements_valid:
        raise SoAIBenchEvidenceError("SoAIBench workload shape evidence is invalid.")
    try:
        expected_operations = counted_operations(
            name,
            element_count,
            rounds,
            dispatches,
            stress=stress,
        )
        expected_bytes = counted_bytes(name, element_count, dispatches, stress=stress)
        expected_positions = sample_positions(element_count)
        validate_sample_values(
            name,
            element_count,
            rounds,
            dispatches,
            positions,
            values,
            stress=stress,
        )
    except ValueError as exception:
        raise SoAIBenchEvidenceError(str(exception)) from exception
    if (
        counted_operations_value != expected_operations
        or counted_bytes_value != expected_bytes
        or positions != expected_positions
    ):
        raise SoAIBenchEvidenceError("SoAIBench workload count evidence is inconsistent.")
    expected_throughput = (
        dispatches / elapsed_seconds
        if name == "latency"
        else (
            expected_bytes / elapsed_seconds / 1_000_000_000.0
            if name == "memory"
            else expected_operations / elapsed_seconds / 1_000_000_000.0
        )
    )
    if round(throughput, 6) != round(expected_throughput, 6):
        raise SoAIBenchEvidenceError("SoAIBench workload throughput evidence is inconsistent.")

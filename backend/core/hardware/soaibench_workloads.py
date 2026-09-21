"""SoAI - SoAIBench workload accounting [backend/core/hardware/soaibench_workloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from dataclasses import dataclass

from core.validation.strict_integer import is_strict_int

__all__ = (
    "ALU_BATCH_DISPATCHES",
    "ALU_MAXIMUM_ELEMENTS",
    "ALU_OPERATION_FACTOR",
    "ALU_ROUNDS",
    "COMPUTE_BATCH_DISPATCHES",
    "COMPUTE_MAXIMUM_ELEMENTS",
    "COMPUTE_ROUNDS",
    "DEFAULT_ELEMENT_COUNT",
    "ELEMENT_ALIGNMENT",
    "FLOAT_SIZE_BYTES",
    "LATENCY_BATCH_DISPATCHES",
    "LATENCY_ELEMENTS",
    "LATENCY_ROUNDS",
    "MATRIX_BATCH_DISPATCHES",
    "MATRIX_MAXIMUM_ELEMENTS",
    "MATRIX_OPERATION_FACTOR",
    "MATRIX_ROUNDS",
    "MAX_COMPLETED_DISPATCHES",
    "MEMORY_BATCH_DISPATCHES",
    "MEMORY_ELEMENTS",
    "MEMORY_ROUNDS",
    "MINIMUM_PHASE_SECONDS",
    "MIXED_BATCH_DISPATCHES",
    "MIXED_ELEMENTS",
    "MIXED_STANDARD_ROUNDS",
    "MIXED_STRESS_ROUNDS",
    "SOAIBENCH_WORKLOAD_NAMES",
    "SoAIBenchWorkloadSpec",
    "counted_bytes",
    "counted_operations",
    "sample_positions",
    "throughput_diagnostics",
    "workload_spec",
)
DEFAULT_ELEMENT_COUNT = 1_048_576
ELEMENT_ALIGNMENT = 262_144
FLOAT_SIZE_BYTES = 4
MINIMUM_PHASE_SECONDS = 1.0
MAX_COMPLETED_DISPATCHES = 1_000_000
SAMPLE_COUNT = 64
SOAIBENCH_WORKLOAD_NAMES = ("alu", "compute", "matrix", "latency", "memory", "mixed")
ALU_ROUNDS = 768
ALU_BATCH_DISPATCHES = 160
ALU_MAXIMUM_ELEMENTS = 8_388_608
ALU_OPERATION_FACTOR = 32
COMPUTE_ROUNDS = 512
COMPUTE_BATCH_DISPATCHES = 96
COMPUTE_MAXIMUM_ELEMENTS = 4_194_304
MATRIX_ROUNDS = 768
MATRIX_BATCH_DISPATCHES = 160
MATRIX_MAXIMUM_ELEMENTS = 4_194_304
MATRIX_OPERATION_FACTOR = 16
LATENCY_ROUNDS = 24
LATENCY_BATCH_DISPATCHES = 4096
LATENCY_ELEMENTS = 16_384
MEMORY_ROUNDS = 1
MEMORY_BATCH_DISPATCHES = 256
MEMORY_ELEMENTS = 67_108_864
MIXED_STANDARD_ROUNDS = 128
MIXED_STRESS_ROUNDS = 160
MIXED_BATCH_DISPATCHES = 64
MIXED_ELEMENTS = 4_194_304


@dataclass(frozen=True, slots=True)
class SoAIBenchWorkloadSpec:
    name: str
    rounds: int
    batch_dispatches: int
    minimum_elements: int
    maximum_elements: int
    operation_factor: int
    bytes_per_dispatch: int
    exact_elements: bool = False


def workload_spec(name: str, *, stress: bool = False) -> SoAIBenchWorkloadSpec:
    match name:
        case "alu":
            return SoAIBenchWorkloadSpec(
                "alu",
                ALU_ROUNDS,
                ALU_BATCH_DISPATCHES,
                DEFAULT_ELEMENT_COUNT,
                ALU_MAXIMUM_ELEMENTS,
                ALU_OPERATION_FACTOR,
                4,
            )
        case "compute":
            return SoAIBenchWorkloadSpec(
                "compute",
                COMPUTE_ROUNDS,
                COMPUTE_BATCH_DISPATCHES,
                DEFAULT_ELEMENT_COUNT,
                COMPUTE_MAXIMUM_ELEMENTS,
                8,
                4,
            )
        case "matrix":
            return SoAIBenchWorkloadSpec(
                "matrix",
                MATRIX_ROUNDS,
                MATRIX_BATCH_DISPATCHES,
                DEFAULT_ELEMENT_COUNT,
                MATRIX_MAXIMUM_ELEMENTS,
                MATRIX_OPERATION_FACTOR,
                4,
            )
        case "latency":
            return SoAIBenchWorkloadSpec(
                "latency",
                LATENCY_ROUNDS,
                LATENCY_BATCH_DISPATCHES,
                LATENCY_ELEMENTS,
                LATENCY_ELEMENTS,
                0,
                4,
                True,
            )
        case "memory":
            return SoAIBenchWorkloadSpec(
                "memory",
                MEMORY_ROUNDS,
                MEMORY_BATCH_DISPATCHES,
                MEMORY_ELEMENTS,
                MEMORY_ELEMENTS,
                0,
                8,
                True,
            )
        case "mixed":
            return SoAIBenchWorkloadSpec(
                "mixed",
                MIXED_STRESS_ROUNDS if stress else MIXED_STANDARD_ROUNDS,
                MIXED_BATCH_DISPATCHES,
                MIXED_ELEMENTS,
                MIXED_ELEMENTS,
                8,
                4,
                True,
            )
        case _:
            raise ValueError("SoAIBench workload name is invalid.")


def counted_operations(
    name: str,
    element_count: int,
    rounds: int,
    dispatches: int,
    *,
    stress: bool = False,
) -> int:
    spec = workload_spec(name, stress=stress)
    if any(not is_strict_int(value) or value < 1 for value in (element_count, rounds, dispatches)):
        raise ValueError("SoAIBench completed-work counts must be positive.")
    if dispatches > MAX_COMPLETED_DISPATCHES:
        raise ValueError("SoAIBench completed-work count exceeds its evaluation bound.")
    if rounds != spec.rounds:
        raise ValueError("SoAIBench workload rounds are invalid.")
    return element_count * rounds * dispatches * spec.operation_factor


def counted_bytes(
    name: str,
    element_count: int,
    dispatches: int,
    *,
    stress: bool = False,
) -> int:
    spec = workload_spec(name, stress=stress)
    if any(not is_strict_int(value) or value < 1 for value in (element_count, dispatches)):
        raise ValueError("SoAIBench completed-work counts must be positive.")
    if dispatches > MAX_COMPLETED_DISPATCHES:
        raise ValueError("SoAIBench completed-work count exceeds its evaluation bound.")
    return element_count * dispatches * spec.bytes_per_dispatch


def sample_positions(element_count: int) -> tuple[int, ...]:
    if not is_strict_int(element_count) or element_count < SAMPLE_COUNT:
        raise ValueError("SoAIBench sample element count cannot provide 64 positions.")
    return tuple(
        (index * (element_count - 1)) // (SAMPLE_COUNT - 1) for index in range(SAMPLE_COUNT)
    )


def throughput_diagnostics(values: tuple[float, ...]) -> tuple[float, float]:
    if not values or any(not math.isfinite(value) or value <= 0.0 for value in values):
        raise ValueError("SoAIBench throughput diagnostics require positive finite values.")
    average = sum(values) / len(values)
    variance = sum((value - average) ** 2 for value in values) / len(values)
    variation_percent = round(math.sqrt(variance) / average * 100.0, 4)
    drift_percent = round((values[-1] / values[0] - 1.0) * 100.0, 4)
    return variation_percent, drift_percent

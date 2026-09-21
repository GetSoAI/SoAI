"""SoAI - SoAIBench numerical expectations [backend/core/hardware/soaibench_numerical.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
import struct
from functools import lru_cache

from core.hardware.soaibench_workloads import (
    ELEMENT_ALIGNMENT,
    MAX_COMPLETED_DISPATCHES,
    sample_positions,
    workload_spec,
)
from core.validation.strict_integer import is_strict_int

__all__ = (
    "MAX_NUMERICAL_EVALUATION_DISPATCHES",
    "SoAIBenchNumericalError",
    "expected_sample_values",
    "validate_sample_values",
)

MAX_NUMERICAL_EVALUATION_DISPATCHES = MAX_COMPLETED_DISPATCHES
MAX_MEMORY_EVALUATION_DISPATCHES = 65_536


class SoAIBenchNumericalError(ValueError):
    __slots__ = ()


def expected_sample_values(
    name: str,
    element_count: int,
    rounds: int,
    dispatches: int,
    *,
    stress: bool = False,
) -> tuple[float, ...]:
    if (
        not is_strict_int(dispatches)
        or dispatches < 1
        or dispatches > MAX_NUMERICAL_EVALUATION_DISPATCHES
    ):
        raise SoAIBenchNumericalError("SoAIBench evidence is too expensive to evaluate.")
    spec = workload_spec(name, stress=stress)
    if name == "memory" and dispatches > MAX_MEMORY_EVALUATION_DISPATCHES:
        raise SoAIBenchNumericalError("SoAIBench evidence is too expensive to evaluate.")
    if not is_strict_int(rounds) or rounds != spec.rounds:
        raise SoAIBenchNumericalError("SoAIBench workload rounds are invalid.")
    if not is_strict_int(element_count) or (
        element_count != spec.maximum_elements
        if spec.exact_elements
        else not spec.minimum_elements <= element_count <= spec.maximum_elements
        or element_count % ELEMENT_ALIGNMENT != 0
    ):
        raise SoAIBenchNumericalError("SoAIBench workload element count is invalid.")
    try:
        positions = sample_positions(element_count)
    except ValueError as exception:
        raise SoAIBenchNumericalError(str(exception)) from exception
    numerical_dispatches = dispatches if name == "memory" else 1
    return _expected_values(name, positions, rounds, numerical_dispatches, stress=stress)


def validate_sample_values(
    name: str,
    element_count: int,
    rounds: int,
    dispatches: int,
    positions: tuple[int, ...],
    values: tuple[float, ...],
    *,
    stress: bool = False,
) -> None:
    if dispatches > MAX_NUMERICAL_EVALUATION_DISPATCHES:
        raise SoAIBenchNumericalError("SoAIBench evidence is too expensive to evaluate.")
    try:
        expected_positions = sample_positions(element_count)
    except ValueError as exception:
        raise SoAIBenchNumericalError(str(exception)) from exception
    if positions != expected_positions or len(values) != len(positions):
        raise SoAIBenchNumericalError("SoAIBench sample boundaries are invalid.")
    expected_values = expected_sample_values(
        name,
        element_count,
        rounds,
        dispatches,
        stress=stress,
    )
    for expected, actual in zip(expected_values, values, strict=True):
        if (
            isinstance(actual, bool)
            or not isinstance(actual, int | float)
            or not math.isfinite(actual)
            or abs(actual - expected) > _error_bound(name, expected, rounds, dispatches)
        ):
            raise SoAIBenchNumericalError(
                "SoAIBench numerical evidence is outside its OpenCL bound."
            )


@lru_cache(maxsize=128)
def _expected_values(
    name: str,
    positions: tuple[int, ...],
    rounds: int,
    dispatches: int,
    *,
    stress: bool,
) -> tuple[float, ...]:
    match name:
        case "alu":
            return tuple(_alu_value(position, rounds) for position in positions)
        case "compute":
            return tuple(_compute_value(position, rounds) for position in positions)
        case "matrix":
            return tuple(_matrix_value(position, rounds) for position in positions)
        case "latency":
            return tuple(_latency_value(position, rounds) for position in positions)
        case "memory":
            return tuple(_memory_value(position, dispatches) for position in positions)
        case "mixed":
            return tuple(_compute_value(position, rounds) for position in positions)
        case _:
            del stress
            raise SoAIBenchNumericalError("SoAIBench workload name is invalid.")


def _alu_value(position: int, rounds: int) -> float:
    initial = _float32_add(_float32(0.001), _float32((position & 255) * 0.0001))
    a0, a1, a2, a3, a4, a5, a6, a7 = (
        _float32_add(initial, _float32(offset * 0.001)) for offset in (0, 2, 3, 4, 5, 6, 7, 8)
    )
    for _round in range(rounds):
        a0 = _fused(a0, 1.000001, _float32_add(0.000001, _float32(a4 * 0.000001)))
        a1 = _fused(a1, 1.000002, _float32_add(0.000002, _float32(a5 * 0.000001)))
        a2 = _fused(a2, 1.000003, _float32_add(0.000003, _float32(a6 * 0.000001)))
        a3 = _fused(a3, 1.000004, _float32_add(0.000004, _float32(a7 * 0.000001)))
        a4 = _fused(a4, 0.999999, _float32_add(0.000005, _float32(a0 * 0.000001)))
        a5 = _fused(a5, 0.999998, _float32_add(0.000006, _float32(a1 * 0.000001)))
        a6 = _fused(a6, 0.999997, _float32_add(0.000007, _float32(a2 * 0.000001)))
        a7 = _fused(a7, 0.999996, _float32_add(0.000008, _float32(a3 * 0.000001)))
        a0 = _fused(a0, 0.999991, _float32_add(0.000009, _float32(a7 * 0.000001)))
        a1 = _fused(a1, 0.999992, _float32_add(0.000010, _float32(a6 * 0.000001)))
        a2 = _fused(a2, 0.999993, _float32_add(0.000011, _float32(a5 * 0.000001)))
        a3 = _fused(a3, 0.999994, _float32_add(0.000012, _float32(a4 * 0.000001)))
        a4 = _fused(a4, 1.000009, _float32_add(0.000013, _float32(a3 * 0.000001)))
        a5 = _fused(a5, 1.000008, _float32_add(0.000014, _float32(a2 * 0.000001)))
        a6 = _fused(a6, 1.000007, _float32_add(0.000015, _float32(a1 * 0.000001)))
        a7 = _fused(a7, 1.000006, _float32_add(0.000016, _float32(a0 * 0.000001)))
    return _sum_float32((a0, a1, a2, a3, a4, a5, a6, a7))


def _compute_value(position: int, rounds: int) -> float:
    value = _float32_add(_float32(0.001), _float32((position & 1023) * 0.0001))
    for _round in range(rounds):
        value = _fused(value, 1.000001, 0.000001)
        sine = _float32(math.sin(value))
        cosine = _float32(math.cos(_float32(value * 0.5)))
        root = _float32(math.sqrt(_float32_add(abs(value), 1.0)))
        value = _float32_add(_float32_add(sine, cosine), root)
    return value


def _matrix_value(position: int, rounds: int) -> float:
    row = position >> 10
    column = position & 1023
    acc0 = acc1 = acc2 = acc3 = 0.0
    grad0, grad1, grad2, grad3 = tuple(_float32(value) for value in (0.001, 0.002, 0.003, 0.004))
    for round_index in range(rounds):
        activation = _float32_add(0.001, ((row + round_index) & 255) * 0.00390625)
        weight0 = _float32_add(0.002, ((column + round_index) & 255) * 0.00390625)
        weight1 = _float32_add(0.003, ((column + round_index + 17) & 255) * 0.00390625)
        weight2 = _float32_add(0.004, ((column + round_index + 43) & 255) * 0.00390625)
        weight3 = _float32_add(0.005, ((column + round_index + 71) & 255) * 0.00390625)
        acc0 = _fused(activation, weight0, acc0)
        acc1 = _fused(activation, weight1, acc1)
        acc2 = _fused(activation, weight2, acc2)
        acc3 = _fused(activation, weight3, acc3)
        grad0 = _fused(acc0, 0.000001, grad0)
        grad1 = _fused(acc1, 0.000001, grad1)
        grad2 = _fused(acc2, 0.000001, grad2)
        grad3 = _fused(acc3, 0.000001, grad3)
    return _float32(
        _sum_float32((acc0, acc1, acc2, acc3, grad0, grad1, grad2, grad3)) * 0.000244140625
    )


def _latency_value(position: int, rounds: int) -> float:
    value = _float32_add(_float32(0.002), _float32((position & 255) * 0.0009765625))
    gate = _float32(0.5)
    for round_index in range(rounds):
        token = _float32(((position + round_index) & 31) * 0.03125)
        value = _fused(value, 1.0003, token)
        gate = _fused(gate, 0.9991, _float32(value * 0.00001))
        value = _float32_add(_float32(value / _float32_add(abs(value), 1.0)), gate)
    return value


def _memory_value(position: int, dispatches: int) -> float:
    value = _float32_add(_float32(0.001), _float32((position & 1023) * 0.0001))
    for _dispatch in range(dispatches):
        value = _float32_add(value, 0.000001)
    return value


def _fused(first: float, second: float, third: float) -> float:
    return _float32(math.fma(_float32(first), _float32(second), _float32(third)))


def _float32_add(first: float, second: float) -> float:
    return _float32(_float32(first) + _float32(second))


def _sum_float32(values: tuple[float, ...] | list[float]) -> float:
    result = 0.0
    for value in values:
        result = _float32(result + value)
    return result


def _float32(value: float) -> float:
    return float(struct.unpack("=f", struct.pack("=f", value))[0])


def _error_bound(name: str, expected: float, rounds: int, dispatches: int) -> float:
    float32_ulp_bound = max(2.0**-149, abs(expected) * 2.0**-23)
    match name:
        case "alu":
            return float32_ulp_bound * (32 * rounds + 8)
        case "compute":
            return float32_ulp_bound * (16 * rounds + 4)
        case "matrix":
            return float32_ulp_bound * (8 * rounds + 8)
        case "latency":
            return float32_ulp_bound * (6 * rounds + 4)
        case "memory":
            return float32_ulp_bound * (dispatches + 2)
        case "mixed":
            return float32_ulp_bound * (16 * rounds + 4)
        case _:
            raise SoAIBenchNumericalError("SoAIBench workload name is invalid.")

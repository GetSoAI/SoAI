"""SoAI - Public SoAIBench workload evidence validation [backend/hardware/soaibench/publication_workload_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.hardware.soaibench_evidence import (
    PhaseAccounting,
    SoAIBenchEvidenceError,
    minimum_measured_duration_ms,
    validate_workload_phase,
)
from core.types.json import JSONDict
from core.types.json_value import coerce_json_dict_or_empty
from core.validation.strict_numbers import require_finite_float_strict
from hardware.soaibench.publication_numeric_validation import (
    require_public_integer,
    require_public_number,
)

WORKLOAD_ACCOUNTING_FIELDS = (
    "elapsed_seconds",
    "element_count",
    "rounds",
    "dispatches",
    "counted_operations",
    "counted_bytes",
    "throughput",
)
WORKLOAD_PHASE_FIELDS = (
    *WORKLOAD_ACCOUNTING_FIELDS,
    "sample_positions",
    "sample_values",
)
WORKLOAD_FIELDS = ("alu", "compute", "matrix", "latency", "memory", "mixed")

__all__ = (
    "WORKLOAD_ACCOUNTING_FIELDS",
    "WORKLOAD_FIELDS",
    "WORKLOAD_PHASE_FIELDS",
    "validate_public_workload",
)


def validate_public_workload(workload: JSONDict) -> int:
    if set(workload) != set(WORKLOAD_FIELDS):
        raise ValidationError("SoAIBench workload evidence fields are invalid.")
    accounting: list[PhaseAccounting] = []
    for name in WORKLOAD_FIELDS:
        phase = coerce_json_dict_or_empty(workload.get(name))
        if set(phase) != set(WORKLOAD_PHASE_FIELDS):
            raise ValidationError("SoAIBench workload phase evidence fields are invalid.")
        elapsed = require_public_number(phase.get("elapsed_seconds"), minimum=1.0)
        element_count = require_public_integer(phase.get("element_count"))
        rounds = require_public_integer(phase.get("rounds"))
        dispatches = require_public_integer(phase.get("dispatches"))
        counted_operations = require_public_integer(phase.get("counted_operations"))
        counted_bytes = require_public_integer(phase.get("counted_bytes"))
        throughput = require_public_number(
            phase.get("throughput"), minimum=0.0, exclusive=True, allow_zero=False
        )
        positions_value = phase.get("sample_positions")
        samples_value = phase.get("sample_values")
        if not isinstance(positions_value, list) or not isinstance(samples_value, list):
            raise ValidationError("SoAIBench workload samples are invalid.")
        positions = tuple(require_public_integer(value) for value in positions_value)
        samples = tuple(
            require_finite_float_strict(
                value,
                error_message="SoAIBench workload samples are invalid.",
            )
            for value in samples_value
        )
        try:
            validate_workload_phase(
                name,
                elapsed,
                element_count,
                rounds,
                dispatches,
                counted_operations,
                counted_bytes,
                throughput,
                positions,
                samples,
            )
        except SoAIBenchEvidenceError as exception:
            raise ValidationError(str(exception)) from exception
        accounting.append(PhaseAccounting(elapsed, element_count, rounds, dispatches))
    return minimum_measured_duration_ms(tuple(accounting))

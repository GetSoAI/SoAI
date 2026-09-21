"""SoAI - SoAIBench V2 publication evidence validation [backend/hardware/soaibench/publication_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from statistics import median, pstdev

from core.errors.exceptions import ValidationError
from core.hardware.soaibench_evidence import (
    PhaseAccounting,
    SoAIBenchEvidenceError,
    minimum_measured_duration_ms,
    validate_workload_phase,
)
from core.hardware.soaibench_workloads import SOAIBENCH_WORKLOAD_NAMES, throughput_diagnostics
from core.types.json import JSONDict
from core.types.json_value import coerce_json_dict_or_empty
from core.validation.integers import is_strict_int
from core.validation.strict_numbers import require_finite_float_strict
from hardware.soaibench.classification import classify_run
from hardware.soaibench.publication_numeric_validation import (
    require_public_integer,
    require_public_number,
    validate_public_temperature_threshold,
)
from hardware.soaibench.publication_workload_validation import WORKLOAD_PHASE_FIELDS
from hardware.soaibench.scoring import score_payload
from hardware.soaibench.workload import SoAIBenchStandardPhases, score_standard_phases
from hardware.soaibench.workload_common import (
    SoAIBenchPhaseResult,
)

__all__ = ("validated_measured_passes",)


def validated_measured_passes(run: JSONDict) -> list[JSONDict]:
    if classify_run(run).get("publication_eligible") is not True:
        raise ValidationError("SoAIBench run is not eligible for publication.")
    passes = coerce_json_dict_or_empty(run.get("passes")).get("measured")
    if not isinstance(passes, list):
        raise ValidationError("SoAIBench measured-pass evidence is missing.")
    measured: list[JSONDict] = []
    for index, value in enumerate(passes, start=1):
        if (
            not isinstance(value, dict)
            or not is_strict_int(value.get("index"))
            or value.get("index") != index
        ):
            raise ValidationError("SoAIBench measured-pass order is invalid.")
        _validate_pass(value)
        measured.append(value)
    _validate_temperature_threshold(run, measured)
    _validate_aggregate(run, measured)
    return measured


def _validate_pass(measured: JSONDict) -> None:
    if measured.get("warmup") is not False or measured.get("score_version") != "soaibench-v2":
        raise ValidationError("SoAIBench measured-pass version is invalid.")
    evidence = coerce_json_dict_or_empty(
        coerce_json_dict_or_empty(measured.get("workload")).get("workload_evidence")
    )
    if set(evidence) != {"alu", "compute", "matrix", "latency", "memory", "mixed"}:
        raise ValidationError("SoAIBench workload evidence is incomplete.")
    phases: dict[str, SoAIBenchPhaseResult] = {
        name: _validate_phase(name, coerce_json_dict_or_empty(value))
        for name, value in evidence.items()
    }
    calculated = score_standard_phases(
        SoAIBenchStandardPhases(
            phases["alu"],
            phases["compute"],
            phases["matrix"],
            phases["memory"],
            phases["mixed"],
            phases["latency"],
        )
    )
    expected_evidence = coerce_json_dict_or_empty(calculated.summary.get("workload_evidence"))
    if evidence != expected_evidence:
        raise ValidationError("SoAIBench workload count evidence is inconsistent.")
    for field in (
        "compute_gops",
        "memory_gbs",
        "alu_gops",
        "matrix_gops",
        "latency_dispatches_per_second",
        "latency_us",
    ):
        measured_value = require_public_number(measured.get(field), minimum=0.0, allow_zero=False)
        calculated_value = require_public_number(
            calculated.score_fields.get(field), minimum=0.0, allow_zero=False
        )
        if round(measured_value, 6) != round(calculated_value, 6):
            raise ValidationError(f"SoAIBench measured-pass {field} is inconsistent.")
    for field in ("overall_score", "compute_score", "memory_score", "latency_score"):
        if require_public_integer(measured.get(field)) != require_public_integer(
            calculated.score_fields.get(field)
        ):
            raise ValidationError("SoAIBench measured-pass score is inconsistent.")
    if round(require_public_number(measured.get("stability_multiplier"), minimum=0.0), 4) != round(
        require_public_number(calculated.score_fields.get("stability_multiplier"), minimum=0.0), 4
    ):
        raise ValidationError("SoAIBench measured-pass score is inconsistent.")
    if require_public_integer(measured.get("sample_count")) != calculated.sample_count:
        raise ValidationError("SoAIBench measured-pass sample count is inconsistent.")
    accounting = tuple(
        PhaseAccounting(
            phase.elapsed_seconds,
            phase.element_count,
            phase.rounds,
            phase.dispatches,
        )
        for phase in phases.values()
    )
    if require_public_integer(measured.get("duration_ms")) < minimum_measured_duration_ms(
        accounting
    ):
        raise ValidationError("SoAIBench measured-pass duration is inconsistent.")


def _validate_phase(name: str, phase: JSONDict) -> SoAIBenchPhaseResult:
    if set(phase) != set(WORKLOAD_PHASE_FIELDS):
        raise ValidationError("SoAIBench workload phase evidence is malformed.")
    elapsed = require_public_number(phase.get("elapsed_seconds"), minimum=1.0)
    elements = require_public_integer(phase.get("element_count"), allow_zero=False)
    rounds = require_public_integer(phase.get("rounds"), allow_zero=False)
    dispatches = require_public_integer(phase.get("dispatches"), allow_zero=False)
    counted_operations_value = require_public_integer(
        phase.get("counted_operations"), allow_zero=True
    )
    counted_bytes_value = require_public_integer(phase.get("counted_bytes"), allow_zero=True)
    throughput = require_public_number(phase.get("throughput"), minimum=0.0, allow_zero=False)
    phase_sample_positions = phase.get("sample_positions")
    phase_sample_values = phase.get("sample_values")
    if (phase_sample_positions is None) or (phase_sample_values is None):
        raise ValidationError("SoAIBench workload samples are malformed.")
    positions: tuple[int, ...] = ()
    values: tuple[float, ...] = ()
    if not isinstance(phase_sample_positions, list) or not isinstance(phase_sample_values, list):
        raise ValidationError("SoAIBench workload samples are malformed.")
    positions = tuple(require_public_integer(value) for value in phase_sample_positions)
    values = tuple(
        require_finite_float_strict(
            value,
            error_message="SoAIBench workload sample value is invalid.",
        )
        for value in phase_sample_values
    )
    try:
        validate_workload_phase(
            name,
            elapsed,
            elements,
            rounds,
            dispatches,
            counted_operations_value,
            counted_bytes_value,
            throughput,
            positions,
            values,
        )
    except SoAIBenchEvidenceError as exception:
        raise ValidationError(str(exception)) from exception
    return SoAIBenchPhaseResult(
        elapsed_seconds=elapsed,
        duration_ms=0,
        checksum=1,
        sample_count=dispatches,
        element_count=elements,
        rounds=rounds,
        dispatches=dispatches,
        summary={},
        sample_positions=positions,
        sample_values=values,
    )


def _validate_temperature_threshold(run: JSONDict, passes: list[JSONDict]) -> None:
    summary = coerce_json_dict_or_empty(run.get("summary"))
    limit = summary.get("temperature_limit_celsius")
    observations = [summary]
    observations.extend(coerce_json_dict_or_empty(measured.get("telemetry")) for measured in passes)
    validate_public_temperature_threshold(limit, observations)


def _validate_aggregate(run: JSONDict, passes: list[JSONDict]) -> None:
    medians = {
        field: float(
            median(
                require_public_number(entry.get(field), minimum=0.0, allow_zero=False)
                for entry in passes
            )
        )
        for field in (
            "compute_gops",
            "memory_gbs",
            "alu_gops",
            "matrix_gops",
            "latency_us",
            "latency_dispatches_per_second",
        )
    }
    latency_score = int(
        median(
            require_public_integer(entry.get("latency_score"), allow_zero=False) for entry in passes
        )
    )
    expected_score_fields = score_payload(
        compute_gops=medians["compute_gops"],
        memory_gbs=medians["memory_gbs"],
        duration_ms=0,
        sample_count=0,
        stability_multiplier=1.0,
        latency_score=float(latency_score),
    )
    for field in ("overall_score", "compute_score", "memory_score", "latency_score"):
        if require_public_integer(run.get(field)) != require_public_integer(
            expected_score_fields.get(field)
        ):
            raise ValidationError("SoAIBench aggregate score is inconsistent.")
    for field, expected in medians.items():
        if round(require_public_number(run.get(field), minimum=0.0, allow_zero=False), 6) != round(
            expected, 6
        ):
            raise ValidationError(f"SoAIBench aggregate {field} is inconsistent.")
    scores = [require_public_integer(entry.get("overall_score")) for entry in passes]
    expected_variance = (
        0.0 if sum(scores) == 0 else round(pstdev(scores) / (sum(scores) / len(scores)) * 100, 4)
    )
    if (
        round(
            require_public_number(run.get("score_variance_percent"), minimum=0.0),
            4,
        )
        != expected_variance
    ):
        raise ValidationError("SoAIBench aggregate variance is inconsistent.")
    if require_public_integer(run.get("sample_count")) != sum(
        require_public_integer(entry.get("sample_count")) for entry in passes
    ):
        raise ValidationError("SoAIBench aggregate sample count is inconsistent.")
    if require_public_integer(run.get("duration_ms")) != sum(
        require_public_integer(entry.get("duration_ms")) for entry in passes
    ):
        raise ValidationError("SoAIBench aggregate duration is inconsistent.")
    if (
        round(
            require_public_number(run.get("stability_multiplier"), minimum=0.0),
            4,
        )
        != 1.0
    ):
        raise ValidationError("SoAIBench aggregate stability is inconsistent.")
    certification = coerce_json_dict_or_empty(run.get("certification"))
    if (
        round(
            require_public_number(certification.get("score_variance_percent"), minimum=0.0),
            4,
        )
        != expected_variance
    ):
        raise ValidationError("SoAIBench certification variance is inconsistent.")
    _validate_phase_diagnostics(certification, passes)


def _validate_phase_diagnostics(certification: JSONDict, passes: list[JSONDict]) -> None:
    variation = certification.get("phase_variation_percent")
    drift = certification.get("phase_drift_percent")
    if not isinstance(variation, dict) or not isinstance(drift, dict):
        raise ValidationError("SoAIBench phase diagnostics are missing.")
    if set(variation) != set(SOAIBENCH_WORKLOAD_NAMES) or set(drift) != set(
        SOAIBENCH_WORKLOAD_NAMES
    ):
        raise ValidationError("SoAIBench phase diagnostics are incomplete.")
    for name in SOAIBENCH_WORKLOAD_NAMES:
        values = tuple(
            require_public_number(
                coerce_json_dict_or_empty(
                    coerce_json_dict_or_empty(
                        coerce_json_dict_or_empty(measured.get("workload")).get("workload_evidence")
                    ).get(name)
                ).get("throughput"),
                minimum=0.0,
                allow_zero=False,
            )
            for measured in passes
        )
        expected_variation, expected_drift = throughput_diagnostics(values)
        if (
            round(
                require_public_number(variation.get(name), minimum=0.0),
                4,
            )
            != expected_variation
            or round(
                require_public_number(drift.get(name), minimum=-100.0),
                4,
            )
            != expected_drift
        ):
            raise ValidationError("SoAIBench phase diagnostics are inconsistent.")

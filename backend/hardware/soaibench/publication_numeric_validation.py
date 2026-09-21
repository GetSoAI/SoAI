"""SoAI - SoAIBench public numeric contracts [backend/hardware/soaibench/publication_numeric_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.hardware.soaibench_score_fields import (
    SOAIBENCH_COMPONENT_FIELDS,
    SOAIBENCH_LATENCY_FIELDS,
    SOAIBENCH_THROUGHPUT_FIELDS,
)
from core.hardware.soaibench_workloads import SOAIBENCH_WORKLOAD_NAMES
from core.types.json import JSONDict, JSONValue
from core.validation.integers import is_strict_int
from core.validation.strict_numbers import (
    require_finite_float_strict,
    require_int_in_range_strict,
)

__all__ = (
    "has_public_certification_status",
    "require_public_integer",
    "require_public_number",
    "require_optional_public_number",
    "validate_public_benchmark_numbers",
    "validate_public_certification_numbers",
    "validate_public_pass_numbers",
    "validate_public_temperature_threshold",
)

_MAX_INTEGER = 9_223_372_036_854_775_807


def validate_public_benchmark_numbers(benchmark: JSONDict) -> None:
    if (
        benchmark.get("score_version") != "soaibench-v2"
        or benchmark.get("profile") != "standard"
        or benchmark.get("benchmark_mode") != "certified"
        or benchmark.get("status") != "completed"
    ):
        raise ValidationError("SoAIBench public benchmark classification is invalid.")
    started = require_public_integer(benchmark.get("started_at_ms"))
    completed = require_public_integer(benchmark.get("completed_at_ms"))
    if completed < started:
        raise ValidationError("SoAIBench public benchmark timing is invalid.")
    validate_public_pass_numbers(benchmark)
    require_public_number(benchmark.get("score_variance_percent"), minimum=0.0)


def validate_public_pass_numbers(measured: JSONDict) -> None:
    for field in SOAIBENCH_COMPONENT_FIELDS:
        require_public_integer(measured.get(field))
    for field in SOAIBENCH_THROUGHPUT_FIELDS:
        require_public_number(measured.get(field), minimum=0.0, maximum=1e15)
    for field in SOAIBENCH_LATENCY_FIELDS:
        require_public_number(measured.get(field), minimum=0.0, maximum=1e15, exclusive=True)
    require_public_number(measured.get("stability_multiplier"), minimum=1.0, maximum=1.0)
    require_public_integer(measured.get("duration_ms"))
    require_public_integer(measured.get("sample_count"))


def validate_public_certification_numbers(certification: JSONDict) -> None:
    if not has_public_certification_status(certification):
        raise ValidationError("SoAIBench public certification is invalid.")
    require_public_number(certification.get("score_variance_percent"), minimum=0.0)
    variation = certification.get("phase_variation_percent")
    drift = certification.get("phase_drift_percent")
    if not isinstance(variation, dict) or not isinstance(drift, dict):
        raise ValidationError("SoAIBench phase diagnostics are invalid.")
    if set(variation) != set(SOAIBENCH_WORKLOAD_NAMES) or set(drift) != set(
        SOAIBENCH_WORKLOAD_NAMES
    ):
        raise ValidationError("SoAIBench phase diagnostics are incomplete.")
    for name in SOAIBENCH_WORKLOAD_NAMES:
        require_public_number(variation.get(name), minimum=0.0)
        require_public_number(drift.get(name), minimum=-100.0)


def has_public_certification_status(certification: JSONDict) -> bool:
    valid_pass_counts = all(
        is_strict_int(certification.get(field)) and certification.get(field) == expected
        for field, expected in (("warmup_pass_count", 1), ("measured_pass_count", 5))
    )
    return (
        certification.get("mode") == "certified"
        and valid_pass_counts
        and certification.get("leaderboard_eligible") is True
        and certification.get("leaderboard_rejection_reason") is None
        and certification.get("score_confidence") is None
    )


def validate_public_temperature_threshold(
    limit: JSONValue,
    observations: list[JSONDict],
) -> None:
    if limit is None:
        return
    validated_limit = require_public_number(limit, minimum=-273.15, maximum=1000.0)
    for telemetry in observations:
        for field in ("temperature_celsius", "max_temperature_celsius"):
            value = telemetry.get(field)
            if (
                value is not None
                and require_public_number(
                    value,
                    minimum=-273.15,
                    maximum=1000.0,
                )
                > validated_limit
            ):
                raise ValidationError("SoAIBench completed run exceeded its temperature limit.")


def require_public_integer(
    value: JSONValue,
    *,
    minimum: int = 0,
    maximum: int = _MAX_INTEGER,
    allow_zero: bool = True,
) -> int:
    if not allow_zero and minimum <= 0:
        minimum = 1
    return require_int_in_range_strict(
        value,
        minimum=minimum,
        maximum=maximum,
        error_message="SoAIBench public integer evidence is invalid.",
    )


def require_public_number(
    value: JSONValue,
    *,
    minimum: float,
    maximum: float | None = None,
    exclusive: bool = False,
    allow_zero: bool = True,
) -> float:
    number = require_finite_float_strict(
        value, error_message="SoAIBench public numeric evidence is invalid."
    )
    if number < minimum or (exclusive and number == minimum) or (not allow_zero and number == 0.0):
        raise ValidationError("SoAIBench public numeric evidence is invalid.")
    if maximum is not None and number > maximum:
        raise ValidationError("SoAIBench public numeric evidence is invalid.")
    return number


def require_optional_public_number(
    value: JSONValue,
    *,
    minimum: float,
    maximum: float,
) -> float | None:
    if value is None:
        return None
    return require_public_number(value, minimum=minimum, maximum=maximum)

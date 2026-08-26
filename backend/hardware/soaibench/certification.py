"""SoAI - SoAIBench certified score aggregation [backend/hardware/soaibench/certification.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from statistics import median

from core.errors.exceptions import StateError
from core.types.json import JSONDict
from core.validation.numbers import (
    coerce_int_from_json,
    coerce_optional_float_from_json,
)
from hardware.soaibench.runtime import (
    CERTIFIED_MEASURED_PASSES,
    CERTIFIED_SCORE_VARIANCE_LIMIT_PERCENT,
)
from hardware.soaibench.scoring import score_payload, score_telemetry_summary_fields
from hardware.soaibench.workload import SoAIBenchWorkloadResult

__all__ = ("certified_result",)


def certified_result(
    *,
    measured_passes: list[JSONDict],
    telemetry_summary: JSONDict,
    temperature_limit_celsius: float | None,
) -> SoAIBenchWorkloadResult:
    alu_values = [_required_float(entry, "alu_gops") for entry in measured_passes]
    matrix_values = [_required_float(entry, "matrix_gops") for entry in measured_passes]
    compute_values = [_required_float(entry, "compute_gops") for entry in measured_passes]
    memory_values = [_required_float(entry, "memory_gbs") for entry in measured_passes]
    latency_scores = [_required_float(entry, "latency_score") for entry in measured_passes]
    latency_values = [_required_float(entry, "latency_us") for entry in measured_passes]
    latency_dispatches = [
        _required_float(entry, "latency_dispatches_per_second") for entry in measured_passes
    ]
    score_values = [_required_float(entry, "overall_score") for entry in measured_passes]
    duration_ms = sum(_required_int(entry, "duration_ms") for entry in measured_passes)
    sample_count = sum(_required_int(entry, "sample_count") for entry in measured_passes)
    variance_percent = _coefficient_variation_percent(score_values)
    rejection_reason = _rejection_reason(
        measured_count=len(measured_passes),
        telemetry_summary=telemetry_summary,
        temperature_limit_celsius=temperature_limit_celsius,
        variance_percent=variance_percent,
    )
    score_fields = score_payload(
        compute_gops=float(median(compute_values)),
        memory_gbs=float(median(memory_values)),
        duration_ms=duration_ms,
        sample_count=sample_count,
        stability_multiplier=1.0,
        latency_score=float(median(latency_scores)),
    )
    alu_gops = round(float(median(alu_values)), 6)
    matrix_gops = round(float(median(matrix_values)), 6)
    latency_score = round(float(median(latency_scores)))
    latency_us = round(float(median(latency_values)), 6)
    latency_dispatches_per_second = round(float(median(latency_dispatches)), 6)
    return SoAIBenchWorkloadResult(
        score_fields={
            **score_fields,
            **score_telemetry_summary_fields(telemetry_summary),
            "alu_gops": alu_gops,
            "matrix_gops": matrix_gops,
            "latency_score": latency_score,
            "latency_us": latency_us,
            "latency_dispatches_per_second": latency_dispatches_per_second,
            "score_variance_percent": variance_percent,
        },
        summary={
            "benchmark_mode": "certified",
            "alu_gops": alu_gops,
            "matrix_gops": matrix_gops,
            "latency_score": latency_score,
            "latency_us": latency_us,
            "latency_dispatches_per_second": latency_dispatches_per_second,
            "leaderboard_eligible": rejection_reason is None,
            "leaderboard_rejection_reason": rejection_reason,
            "score_variance_percent": variance_percent,
            "score_confidence": _score_confidence(variance_percent),
        },
        duration_ms=duration_ms,
        sample_count=sample_count,
    )


def _rejection_reason(
    *,
    measured_count: int,
    telemetry_summary: JSONDict,
    temperature_limit_celsius: float | None,
    variance_percent: float,
) -> str | None:
    if measured_count != CERTIFIED_MEASURED_PASSES:
        return "incomplete_pass_count"
    if telemetry_summary.get("telemetry_available") is not True:
        return "telemetry_unavailable"
    if telemetry_summary.get("throttle_detected") is True:
        return "throttle_detected"
    max_temperature = coerce_optional_float_from_json(
        telemetry_summary.get("max_temperature_celsius"),
        allow_bool=False,
        allow_nonfinite=False,
    )
    if max_temperature is None:
        return "temperature_telemetry_unavailable"
    if temperature_limit_celsius is not None and max_temperature > temperature_limit_celsius:
        return "temperature_limit_exceeded"
    if variance_percent > CERTIFIED_SCORE_VARIANCE_LIMIT_PERCENT:
        return "score_variance_exceeded"
    return None


def _score_confidence(variance_percent: float) -> float:
    ratio = max(0.0, min(1.0, 1.0 - (variance_percent / CERTIFIED_SCORE_VARIANCE_LIMIT_PERCENT)))
    return round(ratio, 4)


def _coefficient_variation_percent(values: list[float]) -> float:
    if not values:
        return 100.0
    mean = sum(values) / len(values)
    if mean <= 0.0:
        return 100.0
    variance = sum((value - mean) * (value - mean) for value in values) / len(values)
    return round((math.sqrt(variance) / mean) * 100.0, 4)


def _required_float(payload: JSONDict, key: str) -> float:
    value = coerce_optional_float_from_json(
        payload.get(key),
        allow_bool=False,
        allow_nonfinite=False,
    )
    if value is None:
        raise StateError(f"Certified pass result missing {key}.")
    return value


def _required_int(payload: JSONDict, key: str) -> int:
    value = coerce_int_from_json(
        payload.get(key),
        default=None,
        allow_bool=False,
    )
    if value is None:
        raise StateError(f"Certified pass result missing {key}.")
    return value

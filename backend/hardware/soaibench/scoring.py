"""SoAI - SoAIBench V1 score calculation [backend/hardware/soaibench/scoring.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.types.json import JSONDict
from core.validation.numbers import coerce_float_from_json
from hardware.soaibench.types import SOAIBENCH_SCORE_VERSION

__all__ = (
    "score_payload",
    "score_payload_with_stability_multiplier",
    "score_telemetry_summary_fields",
)

STANDARD_COMPUTE_WEIGHT = 0.62
STANDARD_MEMORY_WEIGHT = 0.26
STANDARD_LATENCY_WEIGHT = 0.12
STRESS_COMPUTE_WEIGHT = 0.7
STRESS_MEMORY_WEIGHT = 0.3


def score_payload(
    *,
    compute_gops: float,
    memory_gbs: float,
    duration_ms: int,
    sample_count: int,
    stability_multiplier: float,
    latency_score: float | None = None,
) -> JSONDict:
    compute_score = max(0.0, compute_gops)
    memory_score = max(0.0, memory_gbs)
    latency_points = None if latency_score is None else max(0.0, latency_score)
    overall = _weighted_overall(compute_score, memory_score, latency_points)
    payload: JSONDict = {
        "score_version": SOAIBENCH_SCORE_VERSION,
        "overall_score": round(overall * stability_multiplier),
        "compute_score": round(compute_score),
        "memory_score": round(memory_score),
        "stability_multiplier": round(stability_multiplier, 4),
        "compute_gops": round(compute_gops, 6),
        "memory_gbs": round(memory_gbs, 6),
        "duration_ms": duration_ms,
        "sample_count": sample_count,
    }
    if latency_points is not None:
        payload["latency_score"] = round(latency_points)
    return payload


def score_payload_with_stability_multiplier(
    score_fields: JSONDict,
    stability_multiplier: float,
) -> JSONDict:
    compute_score = _score_number(score_fields, "compute_score")
    memory_score = _score_number(score_fields, "memory_score")
    latency_score = _optional_score_number(score_fields, "latency_score")
    multiplier = max(0.0, min(1.0, float(stability_multiplier)))
    overall = _weighted_overall(compute_score, memory_score, latency_score) * multiplier
    return {
        **score_fields,
        "overall_score": round(overall),
        "stability_multiplier": round(multiplier, 4),
    }


def score_telemetry_summary_fields(summary: JSONDict) -> JSONDict:
    return {
        "max_temperature_celsius": summary.get("max_temperature_celsius"),
        "avg_power_watts": summary.get("avg_power_watts"),
        "max_power_watts": summary.get("max_power_watts"),
        "throttle_detected": summary.get("throttle_detected"),
        "telemetry_available": summary.get("telemetry_available"),
        "unavailable_sensors": summary.get("unavailable_sensors"),
    }


def _score_number(score_fields: JSONDict, key: str) -> float:
    return (
        coerce_float_from_json(
            score_fields.get(key),
            default=0.0,
            allow_bool=False,
            allow_nonfinite=False,
        )
        or 0.0
    )


def _optional_score_number(score_fields: JSONDict, key: str) -> float | None:
    return coerce_float_from_json(
        score_fields.get(key),
        default=None,
        allow_bool=False,
        allow_nonfinite=False,
    )


def _weighted_overall(
    compute_score: float,
    memory_score: float,
    latency_score: float | None,
) -> float:
    if latency_score is None:
        return compute_score * STRESS_COMPUTE_WEIGHT + memory_score * STRESS_MEMORY_WEIGHT
    return (
        compute_score * STANDARD_COMPUTE_WEIGHT
        + memory_score * STANDARD_MEMORY_WEIGHT
        + latency_score * STANDARD_LATENCY_WEIGHT
    )

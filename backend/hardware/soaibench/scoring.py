"""SoAI - SoAIBench V2 score calculation [backend/hardware/soaibench/scoring.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.hardware.soaibench_scoring import standard_scores, stress_scores
from core.types.json import JSONDict
from hardware.soaibench.types import SOAIBENCH_SCORE_VERSION

__all__ = (
    "score_payload",
    "score_telemetry_summary_fields",
)


def score_payload(
    *,
    compute_gops: float,
    memory_gbs: float,
    duration_ms: int,
    sample_count: int,
    stability_multiplier: float,
    latency_score: float | None = None,
) -> JSONDict:
    scores = (
        stress_scores(compute_gops, memory_gbs)
        if latency_score is None
        else standard_scores(compute_gops, memory_gbs)
    )
    latency_points = None if latency_score is None else max(0.0, latency_score)
    payload: JSONDict = {
        "score_version": SOAIBENCH_SCORE_VERSION,
        "overall_score": round(scores.overall * stability_multiplier),
        "compute_score": scores.compute,
        "memory_score": scores.memory,
        "stability_multiplier": round(stability_multiplier, 4),
        "compute_gops": round(compute_gops, 6),
        "memory_gbs": round(memory_gbs, 6),
        "duration_ms": duration_ms,
        "sample_count": sample_count,
    }
    if latency_points is not None:
        payload["latency_score"] = round(latency_points)
    return payload


def score_telemetry_summary_fields(summary: JSONDict) -> JSONDict:
    return {
        "max_temperature_celsius": summary.get("max_temperature_celsius"),
        "avg_power_watts": summary.get("avg_power_watts"),
        "max_power_watts": summary.get("max_power_watts"),
        "throttle_detected": summary.get("throttle_detected"),
        "telemetry_available": summary.get("telemetry_available"),
        "unavailable_sensors": summary.get("unavailable_sensors"),
    }

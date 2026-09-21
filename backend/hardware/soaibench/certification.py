"""SoAI - SoAIBench certified score aggregation [backend/hardware/soaibench/certification.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from statistics import median

from core.errors.exceptions import StateError
from core.hardware.soaibench_workloads import SOAIBENCH_WORKLOAD_NAMES, throughput_diagnostics
from core.types.json import JSONDict
from core.validation.integers import is_positive_strict_int
from hardware.soaibench.runtime import CERTIFIED_MEASURED_PASSES
from hardware.soaibench.scoring import score_payload, score_telemetry_summary_fields
from hardware.soaibench.workload import SoAIBenchWorkloadResult

__all__ = ("certified_result",)


def certified_result(
    *,
    measured_passes: list[JSONDict],
    telemetry_summary: JSONDict,
) -> SoAIBenchWorkloadResult:
    if len(measured_passes) != CERTIFIED_MEASURED_PASSES:
        raise StateError(
            f"Certified result requires exactly {CERTIFIED_MEASURED_PASSES} measured passes.",
        )
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
    phase_variation_percent: JSONDict = {}
    phase_drift_percent: JSONDict = {}
    for name in SOAIBENCH_WORKLOAD_NAMES:
        phase_values = tuple(_required_phase_throughput(entry, name) for entry in measured_passes)
        variation_percent, drift_percent = throughput_diagnostics(phase_values)
        phase_variation_percent[name] = variation_percent
        phase_drift_percent[name] = drift_percent
    duration_ms = sum(_required_int(entry, "duration_ms") for entry in measured_passes)
    sample_count = sum(_required_int(entry, "sample_count") for entry in measured_passes)
    variance_percent = _coefficient_variation_percent(score_values)
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
            "phase_variation_percent": phase_variation_percent,
            "phase_drift_percent": phase_drift_percent,
        },
        summary={
            "benchmark_mode": "certified",
            "alu_gops": alu_gops,
            "matrix_gops": matrix_gops,
            "latency_score": latency_score,
            "latency_us": latency_us,
            "latency_dispatches_per_second": latency_dispatches_per_second,
            "leaderboard_eligible": True,
            "leaderboard_rejection_reason": None,
            "score_variance_percent": variance_percent,
            "phase_variation_percent": phase_variation_percent,
            "phase_drift_percent": phase_drift_percent,
            "score_confidence": None,
        },
        duration_ms=duration_ms,
        sample_count=sample_count,
    )


def _coefficient_variation_percent(values: list[float]) -> float:
    mean = sum(values) / len(values)
    if mean == 0.0:
        return 0.0
    variance = sum((value - mean) * (value - mean) for value in values) / len(values)
    return round((math.sqrt(variance) / mean) * 100.0, 4)


def _required_float(payload: JSONDict, key: str) -> float:
    value = payload.get(key)
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(value)
        or value <= 0.0
    ):
        raise StateError(f"Certified pass result {key} must be finite and positive.")
    return float(value)


def _required_phase_throughput(payload: JSONDict, name: str) -> float:
    workload = payload.get("workload")
    if not isinstance(workload, dict):
        raise StateError("Certified pass workload evidence is missing.")
    evidence = workload.get("workload_evidence")
    if not isinstance(evidence, dict):
        raise StateError("Certified pass workload evidence is missing.")
    phase = evidence.get(name)
    if not isinstance(phase, dict):
        raise StateError("Certified pass workload phase evidence is missing.")
    return _required_float(phase, "throughput")


def _required_int(payload: JSONDict, key: str) -> int:
    value = payload.get(key)
    if not is_positive_strict_int(value):
        raise StateError(f"Certified pass result {key} must be a positive integer.")
    return value

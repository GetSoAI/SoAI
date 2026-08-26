"""SoAI - SoAIBench API payload shaping [backend/hardware/soaibench/responses.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.serialization.json_parsing import parse_optional_json_dict
from core.types.json_value import coerce_json_dict_or_empty, copy_json_dict

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("run_response",)


def run_response(
    run: JSONDict,
    *,
    accepted: bool,
    history: list[JSONDict] | None = None,
) -> JSONDict:
    score = _score_payload(run)
    summary = _summary_payload(run)
    payload: JSONDict = {
        "success": True,
        "accepted": accepted,
        "run_id": run.get("run_id"),
        "task_id": run.get("task_id"),
        "device_id": run.get("device_id"),
        "profile": run.get("profile"),
        "benchmark_mode": run.get("benchmark_mode") or "quick",
        "status": run.get("status"),
        "active": run.get("status") == "running",
        "leaderboard_eligible": run.get("leaderboard_eligible") is True,
        "leaderboard_rejection_reason": run.get("leaderboard_rejection_reason"),
        "score_variance_percent": run.get("score_variance_percent"),
        "unsupported_reason": run.get("unsupported_reason"),
        "failure_reason": run.get("failure_reason"),
        "score": score,
        "summary": copy_json_dict(summary),
        "certification": copy_json_dict(coerce_json_dict_or_empty(run.get("certification"))),
        "environment": copy_json_dict(coerce_json_dict_or_empty(run.get("environment"))),
        "passes": copy_json_dict(coerce_json_dict_or_empty(run.get("passes"))),
        "gpu_identity": {
            "device_id": run.get("device_id"),
            "gpu_name": run.get("gpu_name"),
            "gpu_model_key": run.get("gpu_model_key"),
            "vendor": run.get("vendor"),
            "driver_version": run.get("driver_version"),
            "gpu_uuid": run.get("gpu_uuid"),
            "pci_bdf": run.get("pci_bdf"),
            "gpu_index": run.get("gpu_index"),
        },
        "match_basis": run.get("match_basis") or summary.get("match_basis"),
        "started_at_ms": run.get("started_at_ms"),
        "completed_at_ms": run.get("completed_at_ms"),
        "last_heartbeat_at_ms": run.get("last_heartbeat_at_ms"),
        "stop_requested_at_ms": run.get("stop_requested_at_ms"),
        "update_seq": run.get("update_seq"),
    }
    if history is not None:
        payload["history"] = [copy_json_dict(item) for item in history]
    return payload


def _score_payload(run: JSONDict) -> JSONDict | None:
    if run.get("score_version") != "soaibench-v1":
        return None
    summary = _summary_payload(run)
    return {
        "score_version": run.get("score_version"),
        "overall_score": run.get("overall_score"),
        "compute_score": run.get("compute_score"),
        "memory_score": run.get("memory_score"),
        "latency_score": _run_value_or_summary(run, summary, "latency_score"),
        "stability_multiplier": run.get("stability_multiplier"),
        "compute_gops": run.get("compute_gops"),
        "alu_gops": _run_value_or_summary(run, summary, "alu_gops"),
        "matrix_gops": _run_value_or_summary(run, summary, "matrix_gops"),
        "memory_gbs": run.get("memory_gbs"),
        "latency_us": _run_value_or_summary(run, summary, "latency_us"),
        "latency_dispatches_per_second": _run_value_or_summary(
            run,
            summary,
            "latency_dispatches_per_second",
        ),
        "duration_ms": run.get("duration_ms"),
        "sample_count": run.get("sample_count"),
        "max_temperature_celsius": summary.get("max_temperature_celsius"),
        "avg_power_watts": summary.get("avg_power_watts"),
        "max_power_watts": summary.get("max_power_watts"),
        "core_utilization_percent": summary.get("core_utilization_percent"),
        "throttle_detected": summary.get("throttle_detected"),
        "telemetry_available": summary.get("telemetry_available"),
        "unavailable_sensors": summary.get("unavailable_sensors"),
        "failure_reason": run.get("failure_reason"),
        "score_variance_percent": run.get("score_variance_percent"),
        "score_confidence": coerce_json_dict_or_empty(run.get("certification")).get(
            "score_confidence",
        ),
    }


def _summary_payload(run: JSONDict) -> JSONDict:
    summary = coerce_json_dict_or_empty(run.get("summary"))
    if summary:
        return summary
    summary_json = run.get("summary_json")
    if isinstance(summary_json, str):
        return parse_optional_json_dict(summary_json, field="summary_json") or {}
    return {}


def _run_value_or_summary(run: JSONDict, summary: JSONDict, key: str) -> JSONValue:
    value = run.get(key)
    return value if value is not None else summary.get(key)

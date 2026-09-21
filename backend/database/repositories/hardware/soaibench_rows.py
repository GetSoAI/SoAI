"""SoAI - Database SoAIBench row materialization [backend/database/repositories/hardware/soaibench_rows.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.serialization.json_parsing import parse_optional_json_dict
from core.types.json_value import coerce_json_dict_or_empty
from core.validation.numbers import (
    coerce_float_from_json,
    coerce_int_from_json,
)
from database.core.row_materialization import sqlite_row_dict_to_json_dict

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from database.core.sqlite_values import SQLiteRowDict

__all__ = (
    "RUN_COLUMNS",
    "RUN_PLACEHOLDERS",
    "identity_text_or_empty",
    "materialize_row",
    "materialize_run",
    "optional_float",
    "optional_int",
    "optional_str",
    "with_history_match",
)

RUN_COLUMNS = (
    "run_id, created_by_user_id, device_id, gpu_name, gpu_model_key, vendor, "
    "driver_version, gpu_uuid, pci_bdf, gpu_index, profile, benchmark_mode, status, "
    "score_version, overall_score, compute_score, memory_score, latency_score, "
    "stability_multiplier, compute_gops, alu_gops, matrix_gops, memory_gbs, "
    "latency_us, latency_dispatches_per_second, "
    "started_at_ms, completed_at_ms, last_heartbeat_at_ms, stop_requested_at_ms, "
    "update_seq, duration_ms, sample_count, settings_snapshot_json, summary_json, "
    "pass_results_json, environment_json, certification_json, leaderboard_eligible, "
    "leaderboard_rejection_reason, score_variance_percent, failure_reason, "
    "unsupported_reason, publication_source_supported, created_by_tool"
)
RUN_PLACEHOLDERS = (
    "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
    "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?"
)


def materialize_run(row: SQLiteRowDict | None) -> JSONDict | None:
    if row is None:
        return None
    return materialize_row(row)


def materialize_row(row: SQLiteRowDict) -> JSONDict:
    payload = sqlite_row_dict_to_json_dict(row)
    payload["settings_snapshot"] = _json_field(payload, "settings_snapshot_json")
    payload["summary"] = _json_field(payload, "summary_json")
    payload["passes"] = _json_field(payload, "pass_results_json")
    payload["environment"] = _json_field(payload, "environment_json")
    payload["certification"] = _json_field(payload, "certification_json")
    payload["leaderboard_eligible"] = payload.get("leaderboard_eligible") == 1
    payload["publication_source_supported"] = payload.get("publication_source_supported") == 1
    payload.pop("settings_snapshot_json", None)
    payload.pop("summary_json", None)
    payload.pop("pass_results_json", None)
    payload.pop("environment_json", None)
    payload.pop("certification_json", None)
    return payload


def with_history_match(row: JSONDict, identity: JSONDict) -> JSONDict:
    basis = "stale"
    stale = True
    if _same_text(row, identity, "gpu_uuid"):
        basis = "gpu_uuid"
        stale = False
    elif _same_text(row, identity, "device_id") and _compatible_gpu_identity(row, identity):
        basis = "device_id"
        stale = False
    elif _same_text(row, identity, "pci_bdf") and _compatible_gpu_identity(row, identity):
        basis = "pci_bdf"
        stale = False
    row["match_basis"] = basis
    row["stale_hardware"] = stale
    return row


def optional_str(payload: JSONDict, key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value else None


def optional_int(payload: JSONDict, key: str) -> int | None:
    return coerce_int_from_json(
        payload.get(key),
        default=None,
        allow_bool=False,
    )


def optional_float(payload: JSONDict, key: str) -> float | None:
    return coerce_float_from_json(
        payload.get(key),
        default=None,
        allow_bool=False,
        allow_nonfinite=False,
    )


def identity_text_or_empty(value: JSONValue) -> str:
    if isinstance(value, str) and value:
        return value
    return ""


def _same_text(left: JSONDict, right: JSONDict, key: str) -> bool:
    left_value = identity_text_or_empty(left.get(key))
    right_value = identity_text_or_empty(right.get(key))
    return bool(left_value and left_value == right_value)


def _compatible_gpu_identity(row: JSONDict, identity: JSONDict) -> bool:
    if not _same_text(row, identity, "gpu_model_key"):
        return False
    vendor = identity_text_or_empty(identity.get("vendor"))
    return not vendor or row.get("vendor") == vendor


def _json_field(payload: JSONDict, key: str) -> JSONDict:
    value = payload.get(key)
    if isinstance(value, str):
        return parse_optional_json_dict(value, field=key) or {}
    return coerce_json_dict_or_empty(value)

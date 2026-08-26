"""SoAI - Database SoAIBench run persistence [backend/database/repositories/hardware/soaibench.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import DatabaseError
from core.validation.integers import coerce_non_negative_exact_int_or_zero
from core.validation.numberish import require_int_from_numberish
from database.core.query_execution import (
    query_one_to_dict,
    sync_fetch_changes_count,
)
from database.repositories.hardware.soaibench_rows import (
    RUN_COLUMNS,
    RUN_PLACEHOLDERS,
    materialize_run,
    optional_float,
    optional_int,
    optional_str,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "get_soaibench_run_for_user_query",
    "sync_create_soaibench_run",
    "sync_finish_soaibench_run",
    "sync_reconcile_soaibench_running_rows",
    "sync_request_soaibench_stop",
    "sync_update_soaibench_heartbeat",
)


def sync_create_soaibench_run(conn: sqlite3.Connection, run: JSONDict) -> None:
    conn.execute(
        f"INSERT INTO hardware_gpu_soaibench_runs ({RUN_COLUMNS}) VALUES ({RUN_PLACEHOLDERS})",
        (
            str(run["run_id"]),
            require_int_from_numberish(run["created_by_user_id"], field="created_by_user_id"),
            str(run["device_id"]),
            optional_str(run, "gpu_name"),
            optional_str(run, "gpu_model_key"),
            optional_str(run, "vendor"),
            optional_str(run, "driver_version"),
            optional_str(run, "gpu_uuid"),
            optional_str(run, "pci_bdf"),
            optional_int(run, "gpu_index"),
            str(run["profile"]),
            str(run.get("benchmark_mode") or "quick"),
            str(run["status"]),
            optional_str(run, "score_version"),
            optional_int(run, "overall_score"),
            optional_int(run, "compute_score"),
            optional_int(run, "memory_score"),
            optional_int(run, "latency_score"),
            optional_float(run, "stability_multiplier"),
            optional_float(run, "compute_gops"),
            optional_float(run, "alu_gops"),
            optional_float(run, "matrix_gops"),
            optional_float(run, "memory_gbs"),
            optional_float(run, "latency_us"),
            optional_float(run, "latency_dispatches_per_second"),
            require_int_from_numberish(run["started_at_ms"], field="started_at_ms"),
            optional_int(run, "completed_at_ms"),
            optional_int(run, "last_heartbeat_at_ms"),
            optional_int(run, "stop_requested_at_ms"),
            coerce_non_negative_exact_int_or_zero(run.get("update_seq")),
            optional_int(run, "duration_ms"),
            coerce_non_negative_exact_int_or_zero(run.get("sample_count")),
            optional_str(run, "settings_snapshot_json"),
            optional_str(run, "summary_json"),
            optional_str(run, "pass_results_json"),
            optional_str(run, "environment_json"),
            optional_str(run, "certification_json"),
            1 if run.get("leaderboard_eligible") is True else 0,
            optional_str(run, "leaderboard_rejection_reason"),
            optional_float(run, "score_variance_percent"),
            optional_str(run, "failure_reason"),
            optional_str(run, "unsupported_reason"),
            str(run["created_by_tool"]),
        ),
    )


def sync_update_soaibench_heartbeat(
    conn: sqlite3.Connection,
    run_id: str,
    last_heartbeat_at_ms: int,
    sample_count: int,
    summary_json: str | None,
) -> None:
    conn.execute(
        "UPDATE hardware_gpu_soaibench_runs SET last_heartbeat_at_ms = ?, sample_count = ?, summary_json = ?, update_seq = update_seq + 1 WHERE run_id = ? AND status = 'running'",
        (int(last_heartbeat_at_ms), int(sample_count), summary_json, run_id),
    )
    _require_changed(conn, "SoAIBench heartbeat row was not updated.")


def sync_finish_soaibench_run(conn: sqlite3.Connection, run_id: str, fields: JSONDict) -> None:
    conn.execute(
        "UPDATE hardware_gpu_soaibench_runs SET status = ?, score_version = ?, overall_score = ?, compute_score = ?, memory_score = ?, latency_score = ?, stability_multiplier = ?, compute_gops = ?, alu_gops = ?, matrix_gops = ?, memory_gbs = ?, latency_us = ?, latency_dispatches_per_second = ?, completed_at_ms = ?, duration_ms = ?, last_heartbeat_at_ms = ?, sample_count = ?, summary_json = ?, pass_results_json = ?, environment_json = ?, certification_json = ?, leaderboard_eligible = ?, leaderboard_rejection_reason = ?, score_variance_percent = ?, failure_reason = ?, unsupported_reason = ?, update_seq = update_seq + 1 WHERE run_id = ? AND status = 'running'",
        (
            str(fields["status"]),
            optional_str(fields, "score_version"),
            optional_int(fields, "overall_score"),
            optional_int(fields, "compute_score"),
            optional_int(fields, "memory_score"),
            optional_int(fields, "latency_score"),
            optional_float(fields, "stability_multiplier"),
            optional_float(fields, "compute_gops"),
            optional_float(fields, "alu_gops"),
            optional_float(fields, "matrix_gops"),
            optional_float(fields, "memory_gbs"),
            optional_float(fields, "latency_us"),
            optional_float(fields, "latency_dispatches_per_second"),
            optional_int(fields, "completed_at_ms"),
            optional_int(fields, "duration_ms"),
            optional_int(fields, "last_heartbeat_at_ms"),
            coerce_non_negative_exact_int_or_zero(fields.get("sample_count")),
            optional_str(fields, "summary_json"),
            optional_str(fields, "pass_results_json"),
            optional_str(fields, "environment_json"),
            optional_str(fields, "certification_json"),
            1 if fields.get("leaderboard_eligible") is True else 0,
            optional_str(fields, "leaderboard_rejection_reason"),
            optional_float(fields, "score_variance_percent"),
            optional_str(fields, "failure_reason"),
            optional_str(fields, "unsupported_reason"),
            run_id,
        ),
    )
    _require_changed(conn, "SoAIBench terminal row was not updated.")


def sync_request_soaibench_stop(
    conn: sqlite3.Connection,
    run_id: str,
    stop_requested_at_ms: int,
) -> bool:
    conn.execute(
        "UPDATE hardware_gpu_soaibench_runs SET stop_requested_at_ms = ?, update_seq = update_seq + 1 WHERE run_id = ? AND status = 'running' AND stop_requested_at_ms IS NULL",
        (int(stop_requested_at_ms), run_id),
    )
    return sync_fetch_changes_count(conn) > 0


def sync_reconcile_soaibench_running_rows(conn: sqlite3.Connection, completed_at_ms: int) -> int:
    conn.execute(
        "UPDATE hardware_gpu_soaibench_runs SET status = 'indeterminate', completed_at_ms = ?, update_seq = update_seq + 1 WHERE status = 'running'",
        (int(completed_at_ms),),
    )
    return sync_fetch_changes_count(conn)


async def get_soaibench_run_for_user_query(
    database: aiosqlite.Connection,
    user_id: int,
    run_id: str,
) -> JSONDict | None:
    row = await query_one_to_dict(
        database,
        f"SELECT {RUN_COLUMNS} FROM hardware_gpu_soaibench_runs WHERE created_by_user_id = ? AND run_id = ?",
        (int(user_id), run_id),
    )
    return materialize_run(row)


def _require_changed(conn: sqlite3.Connection, message: str) -> None:
    if sync_fetch_changes_count(conn) < 1:
        raise DatabaseError(message, operation="hardware.soaibench.persistence")

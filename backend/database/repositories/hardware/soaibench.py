"""SoAI - Database SoAIBench run persistence [backend/database/repositories/hardware/soaibench.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import DatabaseError
from core.hardware.soaibench_persistence import (
    SoAIBenchMutationOutcome,
    SoAIBenchMutationResult,
    SoAIBenchReconciliationResult,
)
from core.serialization.json import serialize_json_compact_stable
from core.validation.integers import coerce_non_negative_exact_int_or_zero
from core.validation.numberish import require_int_from_numberish
from database.core.query_execution import (
    query_one_to_dict,
    sync_fetch_all_as_dicts,
    sync_fetch_one_as_dict,
)
from database.repositories.hardware.soaibench_rows import (
    RUN_COLUMNS,
    RUN_PLACEHOLDERS,
    materialize_row,
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


def sync_create_soaibench_run(
    conn: sqlite3.Connection,
    run: JSONDict,
) -> SoAIBenchMutationResult:
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
            1 if run.get("publication_source_supported") is True else 0,
            str(run["created_by_tool"]),
        ),
    )
    return SoAIBenchMutationResult(
        outcome=SoAIBenchMutationOutcome.ACCEPTED,
        run=_require_materialized_run(conn, str(run["run_id"])),
    )


def sync_update_soaibench_heartbeat(
    conn: sqlite3.Connection,
    run_id: str,
    last_heartbeat_at_ms: int,
    sample_count: int,
    summary_json: str | None,
) -> SoAIBenchMutationResult:
    cursor = conn.execute(
        f"UPDATE hardware_gpu_soaibench_runs SET last_heartbeat_at_ms = ?, sample_count = ?, summary_json = ?, update_seq = update_seq + 1 WHERE run_id = ? AND status = 'running' AND stop_requested_at_ms IS NULL RETURNING {RUN_COLUMNS}",
        (int(last_heartbeat_at_ms), int(sample_count), summary_json, run_id),
    )
    updated = materialize_run(sync_fetch_one_as_dict(cursor))
    if updated is not None:
        return SoAIBenchMutationResult(SoAIBenchMutationOutcome.UPDATED, updated)
    existing = _materialized_run(conn, run_id)
    if existing is None:
        return SoAIBenchMutationResult(SoAIBenchMutationOutcome.INVARIANT_FAILURE, None)
    return SoAIBenchMutationResult(SoAIBenchMutationOutcome.TERMINAL_SUPERSEDED, existing)


def sync_finish_soaibench_run(
    conn: sqlite3.Connection,
    run_id: str,
    fields: JSONDict,
) -> SoAIBenchMutationResult:
    existing = _materialized_run(conn, run_id)
    if existing is None:
        return SoAIBenchMutationResult(SoAIBenchMutationOutcome.INVARIANT_FAILURE, None)
    if existing.get("status") != "running":
        return SoAIBenchMutationResult(SoAIBenchMutationOutcome.DUPLICATE, existing)
    terminal_fields = fields
    if existing.get("stop_requested_at_ms") is not None:
        stopped_status = "stopped" if existing.get("profile") == "stress" else "cancelled"
        supplied_failure_reason = optional_str(fields, "failure_reason")
        cleanup_failure_reason = (
            supplied_failure_reason
            if supplied_failure_reason == "opencl_child_termination_failed"
            else None
        )
        terminal_fields = {
            "status": stopped_status,
            "completed_at_ms": fields.get("completed_at_ms"),
            "duration_ms": fields.get("duration_ms"),
            "last_heartbeat_at_ms": fields.get("last_heartbeat_at_ms"),
            "sample_count": 0,
            "summary_json": (
                fields.get("summary_json")
                if cleanup_failure_reason is not None
                else serialize_json_compact_stable(
                    existing.get("summary") if isinstance(existing.get("summary"), dict) else {},
                )
            ),
            "failure_reason": cleanup_failure_reason,
        }
    cursor = conn.execute(
        f"UPDATE hardware_gpu_soaibench_runs SET status = ?, score_version = ?, overall_score = ?, compute_score = ?, memory_score = ?, latency_score = ?, stability_multiplier = ?, compute_gops = ?, alu_gops = ?, matrix_gops = ?, memory_gbs = ?, latency_us = ?, latency_dispatches_per_second = ?, completed_at_ms = ?, duration_ms = ?, last_heartbeat_at_ms = ?, sample_count = ?, summary_json = ?, pass_results_json = ?, environment_json = ?, certification_json = ?, leaderboard_eligible = ?, leaderboard_rejection_reason = ?, score_variance_percent = ?, failure_reason = ?, unsupported_reason = ?, update_seq = update_seq + 1 WHERE run_id = ? AND status = 'running' RETURNING {RUN_COLUMNS}",
        (
            str(terminal_fields["status"]),
            optional_str(terminal_fields, "score_version"),
            optional_int(terminal_fields, "overall_score"),
            optional_int(terminal_fields, "compute_score"),
            optional_int(terminal_fields, "memory_score"),
            optional_int(terminal_fields, "latency_score"),
            optional_float(terminal_fields, "stability_multiplier"),
            optional_float(terminal_fields, "compute_gops"),
            optional_float(terminal_fields, "alu_gops"),
            optional_float(terminal_fields, "matrix_gops"),
            optional_float(terminal_fields, "memory_gbs"),
            optional_float(terminal_fields, "latency_us"),
            optional_float(terminal_fields, "latency_dispatches_per_second"),
            optional_int(terminal_fields, "completed_at_ms"),
            optional_int(terminal_fields, "duration_ms"),
            optional_int(terminal_fields, "last_heartbeat_at_ms"),
            coerce_non_negative_exact_int_or_zero(terminal_fields.get("sample_count")),
            optional_str(terminal_fields, "summary_json"),
            optional_str(terminal_fields, "pass_results_json"),
            optional_str(terminal_fields, "environment_json"),
            optional_str(terminal_fields, "certification_json"),
            1 if terminal_fields.get("leaderboard_eligible") is True else 0,
            optional_str(terminal_fields, "leaderboard_rejection_reason"),
            optional_float(terminal_fields, "score_variance_percent"),
            optional_str(terminal_fields, "failure_reason"),
            optional_str(terminal_fields, "unsupported_reason"),
            run_id,
        ),
    )
    updated = materialize_run(sync_fetch_one_as_dict(cursor))
    if updated is None:
        return SoAIBenchMutationResult(
            SoAIBenchMutationOutcome.TERMINAL_SUPERSEDED,
            _materialized_run(conn, run_id),
        )
    return SoAIBenchMutationResult(SoAIBenchMutationOutcome.UPDATED, updated)


def sync_request_soaibench_stop(
    conn: sqlite3.Connection,
    user_id: int,
    run_id: str,
    stop_requested_at_ms: int,
) -> SoAIBenchMutationResult:
    cursor = conn.execute(
        f"UPDATE hardware_gpu_soaibench_runs SET stop_requested_at_ms = ?, update_seq = update_seq + 1 WHERE created_by_user_id = ? AND run_id = ? AND status = 'running' AND stop_requested_at_ms IS NULL RETURNING {RUN_COLUMNS}",
        (int(stop_requested_at_ms), int(user_id), run_id),
    )
    updated = materialize_run(sync_fetch_one_as_dict(cursor))
    if updated is not None:
        return SoAIBenchMutationResult(SoAIBenchMutationOutcome.ACCEPTED, updated)
    existing = _materialized_user_run(conn, user_id, run_id)
    if existing is None:
        return SoAIBenchMutationResult(SoAIBenchMutationOutcome.INVARIANT_FAILURE, None)
    return SoAIBenchMutationResult(SoAIBenchMutationOutcome.DUPLICATE, existing)


def sync_reconcile_soaibench_running_rows(
    conn: sqlite3.Connection,
    completed_at_ms: int,
) -> SoAIBenchReconciliationResult:
    cursor = conn.execute(
        f"UPDATE hardware_gpu_soaibench_runs SET status = 'indeterminate', completed_at_ms = ?, last_heartbeat_at_ms = ?, update_seq = update_seq + 1 WHERE status = 'running' RETURNING {RUN_COLUMNS}",
        (int(completed_at_ms), int(completed_at_ms)),
    )
    rows = tuple(materialize_row(row) for row in sync_fetch_all_as_dicts(cursor))
    return SoAIBenchReconciliationResult(runs=rows)


def _materialized_run(conn: sqlite3.Connection, run_id: str) -> JSONDict | None:
    cursor = conn.execute(
        f"SELECT {RUN_COLUMNS} FROM hardware_gpu_soaibench_runs WHERE run_id = ?",
        (run_id,),
    )
    return materialize_run(sync_fetch_one_as_dict(cursor))


def _materialized_user_run(
    conn: sqlite3.Connection,
    user_id: int,
    run_id: str,
) -> JSONDict | None:
    cursor = conn.execute(
        f"SELECT {RUN_COLUMNS} FROM hardware_gpu_soaibench_runs WHERE created_by_user_id = ? AND run_id = ?",
        (int(user_id), run_id),
    )
    return materialize_run(sync_fetch_one_as_dict(cursor))


def _require_materialized_run(conn: sqlite3.Connection, run_id: str) -> JSONDict:
    run = _materialized_run(conn, run_id)
    if run is None:
        raise DatabaseError(
            "SoAIBench persisted row was not materialized.",
            operation="hardware.soaibench.persistence",
        )
    return run


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

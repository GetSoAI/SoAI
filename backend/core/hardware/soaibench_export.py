"""SoAI - Core SoAIBench history CSV export [backend/core/hardware/soaibench_export.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.files.export import build_timestamped_export_filename, iter_export_csv_bytes
from core.serialization.json import serialize_json_compact_stable_strict

if TYPE_CHECKING:
    from core.files.export import CSVRow, CSVValue
    from core.types.json import JSONDict, JSONPrimitive, JSONValue

__all__ = (
    "SOAIBENCH_HISTORY_EXPORT_FIELDS",
    "build_soaibench_history_filename",
    "iter_soaibench_history_csv_bytes",
)

_SCALAR_FIELDS: tuple[str, ...] = (
    "run_id",
    "device_id",
    "gpu_name",
    "gpu_model_key",
    "vendor",
    "driver_version",
    "gpu_uuid",
    "pci_bdf",
    "gpu_index",
    "profile",
    "benchmark_mode",
    "status",
    "score_version",
    "overall_score",
    "compute_score",
    "memory_score",
    "latency_score",
    "stability_multiplier",
    "compute_gops",
    "alu_gops",
    "matrix_gops",
    "memory_gbs",
    "latency_us",
    "latency_dispatches_per_second",
    "started_at_ms",
    "completed_at_ms",
    "last_heartbeat_at_ms",
    "stop_requested_at_ms",
    "update_seq",
    "duration_ms",
    "sample_count",
    "leaderboard_eligible",
    "leaderboard_rejection_reason",
    "score_variance_percent",
    "failure_reason",
    "unsupported_reason",
    "created_by_tool",
    "match_basis",
    "stale_hardware",
)
_JSON_DETAIL_FIELDS: tuple[tuple[str, str], ...] = (
    ("settings_snapshot_json", "settings_snapshot"),
    ("summary_json", "summary"),
    ("passes_json", "passes"),
    ("environment_json", "environment"),
    ("certification_json", "certification"),
)
SOAIBENCH_HISTORY_EXPORT_FIELDS: tuple[str, ...] = (
    *_SCALAR_FIELDS,
    "settings_snapshot_json",
    "summary_json",
    "passes_json",
    "environment_json",
    "certification_json",
)


def build_soaibench_history_filename() -> str:
    return build_timestamped_export_filename("soai-soaibench-history")


def iter_soaibench_history_csv_bytes(runs: list[JSONDict]) -> AsyncIterator[bytes]:
    return iter_export_csv_bytes(
        fieldnames=SOAIBENCH_HISTORY_EXPORT_FIELDS,
        rows=_iter_soaibench_history_csv_rows(runs),
    )


async def _iter_soaibench_history_csv_rows(runs: list[JSONDict]) -> AsyncIterator[CSVRow]:
    for run in runs:
        row: dict[str, CSVValue] = {}
        for field in _SCALAR_FIELDS:
            row[field] = _csv_scalar(run.get(field), field=field)
        for output_field, source_field in _JSON_DETAIL_FIELDS:
            row[output_field] = _json_detail(run.get(source_field))
        yield row


def _csv_scalar(value: JSONValue, *, field: str) -> JSONPrimitive:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    raise ValidationError(f"SoAIBench history export scalar field is not scalar: {field}")


def _json_detail(value: JSONValue) -> str:
    if value is None:
        return ""
    return serialize_json_compact_stable_strict(value, ensure_ascii=False)

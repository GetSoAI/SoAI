"""SoAI - Core metrics CSV export [backend/core/metrics/export.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.files.export import (
    build_export_timestamp_conditions,
    build_keyset_paginated_export_query,
    build_timestamped_export_filename,
    iter_export_csv_bytes,
    iter_keyset_paginated_rows_as_dicts,
    require_export_database_core,
    validate_export_time_window,
)
from core.metrics.protocols import DatabaseMetricsProtocol

if TYPE_CHECKING:
    from core.files.export import CSVRow, SQLiteValue, SQLParam

__all__ = (
    "build_metrics_history_filename",
    "iter_metrics_history_csv_bytes",
    "iter_metrics_history_rows",
)

_METRICS_HISTORY_FIELDS: tuple[str, ...] = ("timestamp", "metric_key", "value")


def _coerce_int_value(value: SQLiteValue, *, field: str) -> int:
    if isinstance(value, bool) or value is None:
        raise ValidationError(f"Missing {field} value in metrics history")
    if isinstance(value, int | float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exception:
            raise ValidationError(f"Invalid {field} value in metrics history") from exception
    raise ValidationError(f"Invalid {field} value in metrics history")


def _coerce_str_value(value: SQLiteValue, *, field: str) -> str:
    if isinstance(value, str) and value:
        return value
    raise ValidationError(f"Missing {field} value in metrics history")


async def iter_metrics_history_rows(
    database_metrics: DatabaseMetricsProtocol,
    *,
    page_size: int = 5000,
    start_ts_ms: int | None = None,
    end_ts_ms: int | None = None,
) -> AsyncIterator[CSVRow]:
    database_core = require_export_database_core(database_metrics, label="database_metrics")
    validate_export_time_window(page_size=page_size, start_ts_ms=start_ts_ms, end_ts_ms=end_ts_ms)

    key_fields: tuple[str, ...] = ("timestamp", "metric_key")
    order_by = ", ".join(f"{field} ASC" for field in key_fields)
    base_sql = (
        "SELECT * FROM (SELECT observed_at_ms AS timestamp, metric_key, value FROM metrics_history)"
    )

    def _build_query(last_key: Sequence[SQLiteValue] | None) -> tuple[str, tuple[SQLParam, ...]]:
        conditions, params_list = build_export_timestamp_conditions(
            start_ts_ms=start_ts_ms,
            end_ts_ms=end_ts_ms,
        )
        return build_keyset_paginated_export_query(
            order_by=order_by,
            base_sql=base_sql,
            key_fields=key_fields,
            params_list=params_list,
            conditions=conditions,
            last_key=last_key,
        )

    def _last_key_from_row(row: CSVRow) -> Sequence[SQLiteValue]:
        return (
            _coerce_int_value(row.get("timestamp"), field="timestamp"),
            _coerce_str_value(row.get("metric_key"), field="metric_key"),
        )

    async for record in iter_keyset_paginated_rows_as_dicts(
        build_query=_build_query,
        reader=database_core.reader,
        last_key_from_row=_last_key_from_row,
        page_size=page_size,
    ):
        yield record


def iter_metrics_history_csv_bytes(
    database_metrics: DatabaseMetricsProtocol,
    *,
    page_size: int = 5000,
    start_ts_ms: int | None = None,
    end_ts_ms: int | None = None,
) -> AsyncIterator[bytes]:
    return iter_export_csv_bytes(
        fieldnames=_METRICS_HISTORY_FIELDS,
        rows=iter_metrics_history_rows(
            database_metrics,
            page_size=page_size,
            start_ts_ms=start_ts_ms,
            end_ts_ms=end_ts_ms,
        ),
    )


def build_metrics_history_filename() -> str:
    return build_timestamped_export_filename("soai-metrics-history")

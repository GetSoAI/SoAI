"""SoAI - Hardware history CSV export and formatting [backend/core/hardware/export.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import TYPE_CHECKING

from core.files.export import (
    build_export_timestamp_conditions,
    build_keyset_paginated_export_query,
    build_timestamped_export_filename,
    iter_export_csv_bytes,
    iter_keyset_paginated_rows_as_dicts,
    require_export_database_core,
    validate_export_time_window,
)
from core.hardware.hardware_history_query import (
    HARDWARE_HISTORY_FIELDS,
    HARDWARE_HISTORY_SORT_FIELDS,
    HARDWARE_HISTORY_UNION_SQL,
)
from core.hardware.history_selection import normalize_hardware_history_export_selection

if TYPE_CHECKING:
    from core.files.export import CSVRow, SQLiteValue, SQLParam
    from core.hardware.protocols import DatabaseHardwareProtocol

__all__ = (
    "build_hardware_history_filename",
    "iter_hardware_history_csv_bytes",
    "iter_hardware_history_rows",
)


async def iter_hardware_history_rows(
    database_hardware: DatabaseHardwareProtocol,
    *,
    page_size: int = 5000,
    start_ts_ms: int | None = None,
    end_ts_ms: int | None = None,
    component: str | None = None,
    identifier: str | None = None,
    gpu_index: int | None = None,
) -> AsyncIterator[CSVRow]:
    database_core = require_export_database_core(database_hardware, label="database_hardware")
    validate_export_time_window(page_size=page_size, start_ts_ms=start_ts_ms, end_ts_ms=end_ts_ms)
    selection = normalize_hardware_history_export_selection(
        component=component,
        identifier=identifier,
        gpu_index=gpu_index,
    )
    component_value = selection.component
    normalized_identifier = selection.identifier

    key_fields = HARDWARE_HISTORY_SORT_FIELDS
    order_by = ", ".join(f"{field} ASC" for field in key_fields)
    base_sql = f"SELECT * FROM ({HARDWARE_HISTORY_UNION_SQL})"

    def _build_query(last_key: Sequence[SQLiteValue] | None) -> tuple[str, tuple[SQLParam, ...]]:
        conditions, params_list = build_export_timestamp_conditions(
            start_ts_ms=start_ts_ms,
            end_ts_ms=end_ts_ms,
        )
        if component_value is not None:
            conditions.append("component = ?")
            params_list.append(component_value)
        if selection.gpu_index is not None:
            conditions.append("gpu_index = ?")
            params_list.append(selection.gpu_index)
        if normalized_identifier is not None and component_value is not None:
            if component_value in {"cpu", "gpu"}:
                conditions.append("device_id = ?")
                params_list.append(normalized_identifier)
            elif component_value == "disk":
                conditions.append("(mount = ? OR device = ?)")
                params_list.extend([normalized_identifier, normalized_identifier])
            else:
                conditions.append("interface = ?")
                params_list.append(normalized_identifier)
        return build_keyset_paginated_export_query(
            base_sql=base_sql,
            order_by=order_by,
            conditions=conditions,
            params_list=params_list,
            key_fields=key_fields,
            last_key=last_key,
        )

    def _last_key_from_row(row: CSVRow) -> Sequence[SQLiteValue]:
        return tuple(row[field] for field in key_fields)

    async for record in iter_keyset_paginated_rows_as_dicts(
        reader=database_core.reader,
        page_size=page_size,
        build_query=_build_query,
        last_key_from_row=_last_key_from_row,
    ):
        yield record


def iter_hardware_history_csv_bytes(
    database_hardware: DatabaseHardwareProtocol,
    *,
    page_size: int = 5000,
    start_ts_ms: int | None = None,
    end_ts_ms: int | None = None,
    component: str | None = None,
    identifier: str | None = None,
    gpu_index: int | None = None,
) -> AsyncIterator[bytes]:
    return iter_export_csv_bytes(
        fieldnames=HARDWARE_HISTORY_FIELDS,
        rows=iter_hardware_history_rows(
            database_hardware,
            page_size=page_size,
            start_ts_ms=start_ts_ms,
            end_ts_ms=end_ts_ms,
            component=component,
            identifier=identifier,
            gpu_index=gpu_index,
        ),
    )


def build_hardware_history_filename() -> str:
    return build_timestamped_export_filename("soai-hardware-history")

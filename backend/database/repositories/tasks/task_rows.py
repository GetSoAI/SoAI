"""SoAI - Unified task row materialization [backend/database/repositories/tasks/task_rows.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from database.core.json_codec import safe_json_deserialize
from database.repositories.row_formatting import format_row

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRowDict

__all__ = ("format_unified_task_row",)


def format_unified_task_row(row: SQLiteRowDict | None) -> JSONDict | None:
    formatted = format_row(row)
    if formatted is None:
        return None
    metadata_value = safe_json_deserialize(row.get("metadata"), None) if row is not None else None
    formatted["metadata"] = metadata_value
    result_value = safe_json_deserialize(row.get("result"), None) if row is not None else None
    formatted["result"] = result_value
    orchestration_value = (
        safe_json_deserialize(row.get("orchestration_state"), None) if row is not None else None
    )
    formatted["orchestration_state"] = orchestration_value
    return formatted

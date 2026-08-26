"""SoAI - Tool call claim ownership policy [backend/core/tool_calls/claim_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.tool_calls.status_values import (
    TOOL_CALL_STATUS_PENDING,
    is_active_tool_call_status,
    normalize_tool_call_status,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "is_unclaimed_projected_tool_call",
    "is_waitable_active_tool_call",
)


def is_unclaimed_projected_tool_call(row: Mapping[str, JSONValue]) -> bool:
    status_value = row.get("status")
    status = normalize_tool_call_status(status_value if isinstance(status_value, str) else "")
    return (
        status == TOOL_CALL_STATUS_PENDING
        and row.get("started_at_ms") is None
        and row.get("result") is None
        and row.get("error") is None
        and row.get("completed_at_ms") is None
    )


def is_waitable_active_tool_call(row: Mapping[str, JSONValue]) -> bool:
    status_value = row.get("status")
    status = normalize_tool_call_status(status_value if isinstance(status_value, str) else "")
    return is_active_tool_call_status(status) and not is_unclaimed_projected_tool_call(row)

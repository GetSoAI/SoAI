"""SoAI - Context compaction stored tool projections [backend/core/tool_calls/compaction_projections.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.tool_calls.context_compaction_markers import CONTEXT_COMPACTION_TOOL_NAME
from core.types.json import JSONDict

__all__ = ("normalize_boundary_projections",)


def normalize_boundary_projections(message: JSONDict) -> list[JSONDict]:
    projections_value = message.get("tool_call_projections")
    if not isinstance(projections_value, list):
        return []
    entries: list[JSONDict] = []
    for projection_value in projections_value:
        if not isinstance(projection_value, dict):
            continue
        call_id_value = projection_value.get("call_id")
        tool_call_id = (
            call_id_value.strip()
            if isinstance(call_id_value, str) and call_id_value.strip()
            else ""
        )
        tool_name_value = projection_value.get("tool_name")
        tool_name = (
            tool_name_value.strip()
            if isinstance(tool_name_value, str) and tool_name_value.strip()
            else ""
        )
        status_value = projection_value.get("status")
        status = status_value.strip() if isinstance(status_value, str) else ""
        if not tool_call_id or not tool_name or status != "completed":
            continue
        if tool_name == CONTEXT_COMPACTION_TOOL_NAME:
            continue
        entries.append(
            {
                "soai_boundary_type": "tool_call",
                "tool_call_id": tool_call_id,
                "tool_name": tool_name,
            },
        )
        entries.append(
            {
                "soai_boundary_type": "tool_result",
                "tool_call_id": tool_call_id,
            },
        )
    return entries

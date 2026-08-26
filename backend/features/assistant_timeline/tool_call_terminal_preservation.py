"""SoAI - Assistant timeline active owned tool-call preservation [backend/features/assistant_timeline/tool_call_terminal_preservation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.tool_calls.status_values import is_active_tool_call_status

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("should_preserve_active_owned_tool_call",)


def should_preserve_active_owned_tool_call(tool_call: JSONDict | None) -> bool:
    if tool_call is None:
        return False
    owner_task_id = tool_call.get("owner_task_id")
    if not isinstance(owner_task_id, str) or not owner_task_id.strip():
        return False
    if tool_call.get("completed_at_ms") is not None:
        return False
    status = tool_call.get("status")
    return isinstance(status, str) and is_active_tool_call_status(status)

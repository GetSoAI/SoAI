"""SoAI - Subagent parent tool call update error reporting [backend/features/agent/subagents/parent_tool_call_update_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "OPERATION_SUBAGENT_PARENT_TOOL_CALL_UPDATE_FINALIZE",
    "OPERATION_SUBAGENT_PARENT_TOOL_CALL_UPDATE_LIVE",
)

OPERATION_SUBAGENT_PARENT_TOOL_CALL_UPDATE_FINALIZE = (
    "agent.subagents.parent_tool_call_updates.finalize"
)
OPERATION_SUBAGENT_PARENT_TOOL_CALL_UPDATE_LIVE = "agent.subagents.parent_tool_call_updates.live"

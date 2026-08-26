"""SoAI - MCP task method to TaskTypeId mapping [backend/mcp/server/handlers/task_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.tasks.type_catalog import (
    TASK_TYPE_MCP_ELICITATION,
    TASK_TYPE_MCP_SAMPLING,
    TASK_TYPE_MCP_TOOL_CALL,
    TaskTypeId,
)

__all__ = ("method_to_task_type",)


def method_to_task_type(method: str) -> TaskTypeId:
    if method.startswith("tools/call"):
        return TASK_TYPE_MCP_TOOL_CALL
    if method == "sampling/createMessage":
        return TASK_TYPE_MCP_SAMPLING
    if method == "elicitation/create":
        return TASK_TYPE_MCP_ELICITATION
    return TASK_TYPE_MCP_TOOL_CALL

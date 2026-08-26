"""SoAI - Shared inference request primitives (validation and context serialization) [backend/orchestrator/control/inference_request_primitives.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.runtime.request_context import RequestContext
from core.serialization.json import normalize_for_json

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("serialize_request_context_payload",)


def serialize_request_context_payload(context: RequestContext) -> dict[str, JSONValue]:
    result: dict[str, JSONValue] = {
        "trace_id": context.trace_id,
        "cancellation_id": context.cancellation_id,
        "user_id": context.user_id,
        "timestamp": context.timestamp,
    }
    if context.client_ip is not None:
        result["client_ip"] = context.client_ip
    if context.agent_mode is not None:
        result["agent_mode"] = context.agent_mode
    if context.agent_turn_id is not None:
        result["agent_turn_id"] = context.agent_turn_id
    if context.agent_turn_execution_token is not None:
        result["agent_turn_execution_token"] = context.agent_turn_execution_token
    if context.agent_workspace_path is not None:
        result["agent_workspace_path"] = context.agent_workspace_path
    tool_context = context.mcp_tool_context
    if tool_context is not None:
        tool_payload: dict[str, JSONValue] = {
            "conv_id": tool_context.conv_id,
            "message_index": tool_context.message_index,
            "user_id": tool_context.user_id,
            "tool_map": normalize_for_json(tool_context.tool_map),
            "assistant_at_ms": tool_context.assistant_at_ms,
            "tool_approval_required": bool(tool_context.tool_approval_required),
            "user_interaction_timeout_ms": int(tool_context.user_interaction_timeout_ms),
        }
        if tool_context.visible_tool_names is not None:
            tool_payload["visible_tool_names"] = list(tool_context.visible_tool_names)
        result["mcp_tool_context"] = tool_payload
    return result

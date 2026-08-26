"""SoAI - Tool call visibility policy [backend/core/tool_calls/visibility.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.agent.turn_scope_values import TURN_SCOPE_SUBAGENT
from core.runtime.request_context import RequestContext

__all__ = ("should_persist_visible_tool_call_rows",)


def should_persist_visible_tool_call_rows(request_context: RequestContext) -> bool:
    return request_context.agent_turn_scope != TURN_SCOPE_SUBAGENT

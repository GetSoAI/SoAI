"""SoAI - Subagent background finalization actions [backend/features/agent/subagents/background_finalization_actions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.status_values import AGENT_TURN_STATUS_RUNNING
from core.runtime.request_context import RequestContext
from features.agent.subagents.parent_tool_call_update_models import (
    build_live_subagent_record,
)
from features.agent.subagents.parent_tool_call_updates import (
    SubagentParentToolCallUpdateBridge,
)
from features.agent.subagents.reads import load_subagent_turn_record_noncritical
from features.agent.subagents.snapshots import build_subagent_snapshot

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.orchestrator.types import MCPToolContext
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "finalize_parent_tool_call_noncritical",
    "load_terminal_turn_record",
)


async def load_terminal_turn_record(
    *,
    api_dependencies: ApiDependencies,
    logger: LoggerProtocol,
    subagent_context: RequestContext,
    subagent_tool_context: MCPToolContext,
) -> JSONDict | None:
    return await load_subagent_turn_record_noncritical(
        database_agent_turns=api_dependencies.database_agent_turns,
        logger=logger,
        trace_id=subagent_context.trace_id,
        conv_id=subagent_tool_context.conv_id,
        user_id=subagent_tool_context.user_id,
        subagent_id=str(subagent_context.agent_turn_id or ""),
    )


async def finalize_parent_tool_call_noncritical(
    *,
    bridge: SubagentParentToolCallUpdateBridge | None,
    turn_record: JSONDict | None,
    token_usage: JSONDict | None,
) -> None:
    if bridge is None:
        return
    snapshot = build_subagent_snapshot(turn_record)
    if snapshot is None:
        return
    if snapshot.status == AGENT_TURN_STATUS_RUNNING:
        return
    duration_ms = 0
    if snapshot.finished_at_ms is not None:
        duration_ms = max(0, int(snapshot.finished_at_ms) - int(snapshot.started_at_ms))
    subagent_record = build_live_subagent_record(
        snapshot=snapshot,
        result_text=snapshot.result_text,
        token_usage=token_usage,
    )
    await bridge.finalize_noncritical(
        subagent_status=snapshot.status,
        duration_ms=duration_ms,
        error_message=snapshot.error_message,
        subagent_record=subagent_record,
    )

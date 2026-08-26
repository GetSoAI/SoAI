"""SoAI - Subagent parent stream setup [backend/features/agent/subagents/background_parent_stream_setup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.runtime.request_context import RequestContext
from core.tool_calls.deferred_tool_call_streamer import DeferredToolCallDependencies
from core.validation.strict_numbers import (
    coerce_optional_non_negative_int_strict,
    coerce_optional_positive_int_strict,
)
from features.agent.subagents.parent_tool_call_streaming import (
    SUBAGENT_PARENT_TOOL_NAME,
)
from features.agent.subagents.parent_tool_call_update_models import (
    build_live_subagent_record,
)
from features.agent.subagents.parent_tool_call_updates import (
    SubagentParentToolCallUpdateBridge,
)
from features.agent.subagents.reads import load_subagent_turn_record_noncritical
from features.agent.subagents.snapshots import build_subagent_snapshot
from features.agent.subagents.subagent_tool_event_forwarder import (
    SubagentToolEventForwarder,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.orchestrator.types import MCPToolContext
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "maybe_build_parent_update_bridge",
    "maybe_subscribe_tool_event_forwarder",
    "prime_parent_update_bridge_noncritical",
)


def maybe_build_parent_update_bridge(
    *,
    api_dependencies: ApiDependencies,
    logger: LoggerProtocol,
    subagent_context: RequestContext,
    subagent_tool_context: MCPToolContext,
) -> SubagentParentToolCallUpdateBridge | None:
    parent_turn_id = str(subagent_context.agent_parent_turn_id or "").strip()
    parent_tool_call_id = str(subagent_context.agent_parent_tool_call_id or "").strip()
    parent_iteration_index = subagent_context.agent_parent_iteration_index
    if not parent_turn_id or not parent_tool_call_id:
        return None
    if (
        not isinstance(parent_iteration_index, int)
        or isinstance(parent_iteration_index, bool)
        or parent_iteration_index < 0
    ):
        return None
    assistant_turn_at_ms = coerce_optional_positive_int_strict(
        subagent_tool_context.assistant_turn_at_ms,
    )
    if assistant_turn_at_ms is None:
        return None
    model_variant_index = coerce_optional_non_negative_int_strict(
        subagent_tool_context.model_variant_index,
    )
    if model_variant_index is None:
        return None
    return SubagentParentToolCallUpdateBridge(
        deps=DeferredToolCallDependencies(
            database_tool_calls=api_dependencies.database_tool_calls,
            event_bus=api_dependencies.event_bus,
            logger=logger,
            trace_id=subagent_context.trace_id,
            user_id=int(subagent_context.user_id),
            conv_id=subagent_tool_context.conv_id,
            assistant_turn_at_ms=assistant_turn_at_ms,
            model_variant_index=model_variant_index,
            turn_id=parent_turn_id,
            iteration_index=int(parent_iteration_index),
            call_id=parent_tool_call_id,
            tool_name=SUBAGENT_PARENT_TOOL_NAME,
        ),
    )


def maybe_subscribe_tool_event_forwarder(
    *,
    api_dependencies: ApiDependencies,
    subagent_context: RequestContext,
    subagent_tool_context: MCPToolContext,
    bridge: SubagentParentToolCallUpdateBridge | None,
) -> SubagentToolEventForwarder | None:
    if bridge is None:
        return None
    subagent_turn_id = str(subagent_context.agent_turn_id or "").strip()
    if not subagent_turn_id:
        return None
    forwarder = SubagentToolEventForwarder(
        event_bus=api_dependencies.event_bus,
        subagent_turn_id=subagent_turn_id,
        subagent_conv_id=subagent_tool_context.conv_id,
        subagent_user_id=int(subagent_tool_context.user_id),
        bridge=bridge,
    )
    forwarder.subscribe()
    return forwarder


async def prime_parent_update_bridge_noncritical(
    *,
    api_dependencies: ApiDependencies,
    logger: LoggerProtocol,
    subagent_context: RequestContext,
    subagent_tool_context: MCPToolContext,
    bridge: SubagentParentToolCallUpdateBridge | None,
) -> None:
    if bridge is None:
        return
    turn_record = await load_subagent_turn_record_noncritical(
        database_agent_turns=api_dependencies.database_agent_turns,
        logger=logger,
        trace_id=subagent_context.trace_id,
        conv_id=subagent_tool_context.conv_id,
        user_id=subagent_tool_context.user_id,
        subagent_id=str(subagent_context.agent_turn_id or ""),
    )
    snapshot = build_subagent_snapshot(turn_record)
    if snapshot is None:
        return
    await bridge.seed_subagent_state_noncritical(
        subagent_record=build_live_subagent_record(
            snapshot=snapshot,
            result_text=snapshot.result_text,
            token_usage=snapshot.token_usage,
        ),
    )

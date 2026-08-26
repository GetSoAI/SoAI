"""SoAI - Agent inference request payload preparation [backend/features/agent/runtime/inference_request_payload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.prompt_injection_messages import (
    refresh_agent_subagent_state_prompt_message,
    refresh_agent_todo_state_prompt_message,
)
from core.agent.turn_scope_values import TURN_SCOPE_SUBAGENT
from core.errors.exceptions import ValidationError
from core.openai.token_accounting import count_prompt_occupancy_async
from core.runtime.request_context import RequestContext
from features.agent.runtime.request_messages import strip_internal_message_metadata
from features.agent.runtime.tool_image_relay_messages import (
    has_tool_image_relay_message,
)
from features.agent.runtime.turn_tool_result_postprocessors import (
    build_todo_state_prompt_payload,
)
from features.agent.session.agent_output_tokens import (
    resolve_agent_output_token_limit,
)
from features.agent.session.compaction_budget import (
    resolve_compaction_budget_from_agent_settings,
)
from features.agent.subagents.summaries import (
    list_serialized_subagent_snapshots_for_prompt,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.agent.runtime.turn_bootstrap import AgentTurnBootstrap
    from features.agent.runtime.turn_engine import AgentTurnEngineDependencies

__all__ = (
    "AGENT_TOOL_IMAGE_RELAY_REQUESTED_FIELD",
    "build_turn_inference_request_payload",
    "build_turn_inference_request_payload_for_iteration",
    "pop_agent_tool_image_relay_requested_flag",
    "resolve_agent_tool_image_relay_request",
)

AGENT_TOOL_IMAGE_RELAY_REQUESTED_FIELD = "_soai_agent_tool_image_relay_requested"


async def _apply_current_prompt_output_token_cap(
    *,
    deps: AgentTurnEngineDependencies,
    bootstrap: AgentTurnBootstrap,
    request_payload: JSONDict,
) -> None:
    compaction_budget = resolve_compaction_budget_from_agent_settings(bootstrap.settings)
    if compaction_budget is None:
        return
    prompt_occupancy = await count_prompt_occupancy_async(
        prompt_token_counter=deps.prompt_token_counter,
        request_payload=request_payload,
        token_estimation_profile=bootstrap.settings.token_estimation_profile,
    )
    output_token_limit = resolve_agent_output_token_limit(
        request_json=request_payload,
        agent_settings=bootstrap.settings,
        compaction_budget=compaction_budget,
        prompt_tokens=prompt_occupancy.prompt_tokens,
    )
    if output_token_limit <= 0:
        raise ValidationError("Agent prompt leaves no safe output token budget.")
    request_payload["max_tokens"] = output_token_limit


def pop_agent_tool_image_relay_requested_flag(payload: JSONDict) -> tuple[JSONDict, bool]:
    normalized_payload = dict(payload)
    relay_requested = normalized_payload.pop(AGENT_TOOL_IMAGE_RELAY_REQUESTED_FIELD, None) is True
    return (normalized_payload, relay_requested)


def resolve_agent_tool_image_relay_request(
    *,
    context: RequestContext,
    payload: JSONDict,
) -> tuple[JSONDict, bool]:
    cleaned_payload, relay_requested = pop_agent_tool_image_relay_requested_flag(payload)
    return (
        cleaned_payload,
        context.agent_turn_id is not None
        and bool(context.agent_turn_id.strip())
        and relay_requested,
    )


async def build_turn_inference_request_payload(
    *,
    deps: AgentTurnEngineDependencies,
    context: RequestContext,
    bootstrap: AgentTurnBootstrap,
    base_request_payload: JSONDict,
    current_history: list[JSONDict],
    suppress_tools: bool = False,
) -> JSONDict:
    prompt_history = [dict(message) for message in current_history]
    refresh_agent_todo_state_prompt_message(
        prompt_history,
        todo_state=build_todo_state_prompt_payload(bootstrap.todo_state),
    )
    if context.agent_turn_scope != TURN_SCOPE_SUBAGENT:
        serialized_subagent_summaries = await list_serialized_subagent_snapshots_for_prompt(
            database_agent_turns=deps.database_agent_turns,
            task_registry_queries=deps.task_registry_queries,
            token_collection=deps.token_collection,
            conv_id=bootstrap.primitives.conv_id,
            user_id=bootstrap.primitives.user_id,
            parent_turn_id=bootstrap.primitives.turn_id,
        )
        refresh_agent_subagent_state_prompt_message(
            prompt_history,
            subagent_summaries=serialized_subagent_summaries,
        )
    request_payload = dict(base_request_payload)
    request_payload["messages"] = strip_internal_message_metadata(prompt_history)
    await _apply_current_prompt_output_token_cap(
        deps=deps,
        bootstrap=bootstrap,
        request_payload=request_payload,
    )
    if has_tool_image_relay_message(current_history):
        request_payload[AGENT_TOOL_IMAGE_RELAY_REQUESTED_FIELD] = True
    if suppress_tools:
        request_payload.pop("tools", None)
        request_payload.pop("parallel_tool_calls", None)
        request_payload["tool_choice"] = "none"
    return request_payload


async def build_turn_inference_request_payload_for_iteration(
    deps: AgentTurnEngineDependencies,
    context: RequestContext,
    bootstrap: AgentTurnBootstrap,
    base_request_payload: JSONDict,
    current_history: list[JSONDict],
    suppress_tools: bool,
) -> JSONDict:
    return await build_turn_inference_request_payload(
        deps=deps,
        context=context,
        bootstrap=bootstrap,
        base_request_payload=base_request_payload,
        current_history=current_history,
        suppress_tools=suppress_tools,
    )

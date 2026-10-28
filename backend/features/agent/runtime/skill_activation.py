"""SoAI - Cumulative prompt fit and durable skill activation during a tool phase [backend/features/agent/runtime/skill_activation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.openai.agent_tool_messages import build_post_tool_prompt_messages
from core.openai.token_accounting import count_prompt_occupancy_async
from core.skills.checkpoint import SkillActivationCheckpoint
from core.skills.errors import build_skill_error
from core.skills.execution import SkillExecutionContext, propose_skill_activation
from core.skills.prompt_projection import project_skill_context
from features.agent.runtime.request_messages import strip_internal_message_metadata
from features.agent.session.compaction_budget import resolve_compaction_budget_from_agent_settings

if TYPE_CHECKING:
    from core.agent.settings_types import AgentSettings
    from core.openai.token_counter import PromptTokenCounter
    from core.skills.protocols import SkillActivationCallback
    from core.types.json import JSONDict
    from features.agent.runtime.tool_phase_execution_context import ToolPhaseExecutionContext

__all__ = ("build_skill_activation_callback",)


def build_skill_activation_callback(
    *,
    phase: ToolPhaseExecutionContext,
    prompt_token_counter: PromptTokenCounter,
    base_request_payload: JSONDict,
    settings: AgentSettings,
) -> SkillActivationCallback:
    async def activate(
        skill_id: str, call_id: str, result: JSONDict, arguments: str | None = None
    ) -> SkillExecutionContext:
        context = phase.request_context.skill_execution_context
        if context is None:
            raise StateError("Skill activation has no active execution.")
        if await phase.turn_cancelled():
            raise asyncio.CancelledError()
        completed = list(phase.turn_state_writer.latest_tool_results)
        call_index = len(completed)
        if call_index >= len(phase.tool_calls) or phase.tool_calls[call_index].get("id") != call_id:
            raise StateError("Skill activation does not match the next uncommitted tool call.")
        proposed = propose_skill_activation(context, skill_id, call_id=call_id, arguments=arguments)
        projected = project_skill_context(
            phase.message_history, proposed, automatic_loading_available=True
        )
        results = [*completed, result]
        pending_messages = build_post_tool_prompt_messages(
            tool_calls=phase.tool_calls,
            tool_results=results,
            assistant_text=phase.assistant_text,
            reasoning_content=phase.reasoning_text,
            settings=settings,
            shape_cache=phase.shape_cache,
        )
        budget = resolve_compaction_budget_from_agent_settings(settings)
        if budget is None:
            raise StateError("Skill activation requires a resolved prompt budget.")
        request = dict(base_request_payload)
        request["messages"] = strip_internal_message_metadata([*projected, *pending_messages])
        occupancy = await count_prompt_occupancy_async(
            prompt_token_counter=prompt_token_counter,
            request_payload=request,
            token_estimation_profile=settings.token_estimation_profile,
        )
        if occupancy.prompt_tokens > budget.maximum_prompt_tokens:
            raise build_skill_error("skill_context_full")
        if await phase.turn_cancelled():
            raise asyncio.CancelledError()
        await phase.turn_state_writer.checkpoint_skill_activation(
            iteration_index=phase.iteration_index,
            call_id=call_id,
            result=result,
            skill_activation=SkillActivationCheckpoint.from_execution(proposed),
        )
        phase.request_context.skill_execution_context = proposed
        phase.message_history[:] = projected
        return proposed

    return activate

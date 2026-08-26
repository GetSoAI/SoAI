"""SoAI - Preflight prompt compaction and output-budget fitting [backend/features/agent/runtime/preflight_compaction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.events.types_base import Event
from core.openai.token_accounting import count_prompt_occupancy_async
from features.agent.runtime.request_messages import strip_internal_message_metadata
from features.agent.runtime.turn_compaction_actions import try_compact_message_history
from features.agent.session.agent_output_tokens import resolve_agent_output_token_limit

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.agent.settings_types import AgentSettings
    from core.openai.token_accounting import PromptOccupancy
    from core.openai.token_counter import PromptTokenCounter
    from core.types.json import JSONDict
    from features.agent.runtime.context_compaction.activity_result import (
        AutoCompactionActivityMetadata,
    )
    from features.agent.session.compaction_budget import ResolvedCompactionBudget

__all__ = (
    "PreflightCompactionOutcome",
    "fit_prompt_to_compaction_budget",
)


@dataclass(frozen=True, slots=True)
class PreflightCompactionOutcome:
    compacted_messages: list[JSONDict]
    provider_messages: list[JSONDict]
    output_token_limit: int


async def fit_prompt_to_compaction_budget(
    *,
    message_history: list[JSONDict],
    boundary_source_messages: list[JSONDict],
    base_request_payload: JSONDict,
    prompt_token_counter: PromptTokenCounter,
    agent_settings: AgentSettings,
    compaction_budget: ResolvedCompactionBudget,
    summarize_messages: Callable[[list[JSONDict]], Awaitable[str]] | None,
    user_id: int,
    conv_id: str,
    message_index: int,
    on_completed_compaction: (
        Callable[
            [list[JSONDict], AutoCompactionActivityMetadata, str, JSONDict | None],
            None,
        ]
        | None
    ) = None,
    on_compacted_prompt_occupancy: Callable[[PromptOccupancy], None] | None = None,
) -> PreflightCompactionOutcome:
    compacted_messages = await try_compact_message_history(
        message_history=message_history,
        boundary_source_messages=boundary_source_messages,
        base_request_payload=base_request_payload,
        prompt_token_counter=prompt_token_counter,
        token_estimation_profile=agent_settings.token_estimation_profile,
        summarize_messages=summarize_messages,
        user_id=user_id,
        conv_id=conv_id,
        message_index=message_index,
        turn_id="preflight",
        iteration_index=0,
        compaction_budget=compaction_budget,
        next_action_sequence=_return_zero_sequence,
        publish_event=_discard_event,
        emit_events=False,
        turn_state_writer=None,
        on_compacted_prompt_occupancy=on_compacted_prompt_occupancy,
        on_completed_compaction=on_completed_compaction,
    )
    stripped_messages = strip_internal_message_metadata(compacted_messages)
    budget_payload = dict(base_request_payload)
    budget_payload["messages"] = stripped_messages
    prompt_occupancy = await count_prompt_occupancy_async(
        prompt_token_counter=prompt_token_counter,
        request_payload=budget_payload,
        token_estimation_profile=agent_settings.token_estimation_profile,
    )
    output_token_limit = resolve_agent_output_token_limit(
        request_json=base_request_payload,
        agent_settings=agent_settings,
        compaction_budget=compaction_budget,
        prompt_tokens=prompt_occupancy.prompt_tokens,
    )
    if output_token_limit <= 0:
        raise ValidationError("Agent prompt leaves no safe output token budget.")
    return PreflightCompactionOutcome(
        compacted_messages=compacted_messages,
        provider_messages=stripped_messages,
        output_token_limit=output_token_limit,
    )


async def _return_zero_sequence() -> int:
    return 0


async def _discard_event(_event: Event) -> None:
    return None

"""SoAI - Shared prepared execution request assembly [backend/features/agent/runtime/execution_request_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.request_field_filtering import build_inference_request_payload
from core.openai.request_fields import resolve_optional_model_name
from core.types.json_value import copy_json_dict, copy_json_dict_list
from core.validation.strings import coerce_optional_trimmed_str
from features.agent.runtime.context_compaction.activity_result import (
    AutoCompactionActivityMetadata,
    PreparedAutoCompactionSnapshot,
)
from features.agent.runtime.preflight_compaction import fit_prompt_to_compaction_budget
from features.agent.runtime.prepared_request_state import PreparedExecutionRequest
from features.agent.runtime.prompt_request_preparation import (
    build_prepared_agent_messages,
)
from features.agent.runtime.request_payloads import collect_tool_definitions
from features.agent.session.compaction_budget import (
    resolve_compaction_budget_from_agent_settings,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.agent.settings_types import AgentSettings
    from core.openai.token_accounting import PromptOccupancy
    from core.openai.token_counter import PromptTokenCounter
    from core.orchestrator.types import MCPToolContext
    from core.types.json import JSONDict

__all__ = ("build_prepared_execution_request",)


async def build_prepared_execution_request(
    *,
    prompt_token_counter: PromptTokenCounter,
    source_policy: str,
    request_json: JSONDict,
    source_messages: list[JSONDict],
    boundary_source_messages: list[JSONDict],
    conv_id: str,
    user_id: int,
    requested_model: str | None,
    agent_settings: AgentSettings,
    todo_state: JSONDict | None,
    subagent_summaries: list[JSONDict],
    tool_context: MCPToolContext | None,
    scope_message: JSONDict | None,
    prune_empty_messages: bool,
    stream: bool,
    summarize_messages: Callable[[list[JSONDict]], Awaitable[str]] | None,
) -> PreparedExecutionRequest:
    final_payload = copy_json_dict(request_json)
    resolved_model = coerce_optional_trimmed_str(requested_model)
    if resolved_model is None:
        resolved_model = resolve_optional_model_name(request_json) or ""
    if not resolved_model:
        raise ValidationError("Prepared execution request requires a model.")
    final_payload["model"] = resolved_model
    final_payload["stream"] = stream
    prepared_messages = build_prepared_agent_messages(
        source_messages=source_messages,
        agent_settings=agent_settings,
        todo_state=todo_state,
        subagent_summaries=subagent_summaries,
        tool_context=tool_context,
        scope_message=scope_message,
        prune_empty_messages=prune_empty_messages,
    )
    tool_definitions, tool_choice = _resolve_tool_payload_fields(request_json, tool_context)
    if tool_definitions:
        final_payload["tools"] = tool_definitions
        if tool_choice is None:
            raise ValidationError("Prepared execution request tool choice is invalid.")
        final_payload["tool_choice"] = tool_choice
    else:
        final_payload.pop("tools", None)
        if tool_choice == "none":
            final_payload["tool_choice"] = "none"
        else:
            final_payload.pop("tool_choice", None)
    final_payload = build_inference_request_payload(final_payload)
    prepared_auto_compaction: PreparedAutoCompactionSnapshot | None = None
    compacted_prompt_occupancy: PromptOccupancy | None = None

    def _capture_compacted_prompt_occupancy(occupancy: PromptOccupancy) -> None:
        nonlocal compacted_prompt_occupancy
        compacted_prompt_occupancy = occupancy

    def _capture_completed_compaction(
        compacted: list[JSONDict],
        metadata: AutoCompactionActivityMetadata,
        output_text: str,
        prompt_message: JSONDict | None,
    ) -> None:
        nonlocal prepared_auto_compaction
        if prepared_auto_compaction is not None:
            return
        if compacted_prompt_occupancy is None:
            raise ValidationError("Prepared auto-compaction prompt occupancy is unavailable.")
        prepared_auto_compaction = PreparedAutoCompactionSnapshot(
            compacted_messages=copy_json_dict_list(list(compacted)),
            output_text=str(output_text),
            prompt_message=prompt_message,
            metadata=metadata,
            prompt_occupancy=compacted_prompt_occupancy,
        )

    compaction_budget = resolve_compaction_budget_from_agent_settings(agent_settings)
    if compaction_budget is None:
        raise ValidationError("Prepared execution request requires a resolved compaction budget.")
    preflight_outcome = await fit_prompt_to_compaction_budget(
        message_history=prepared_messages,
        boundary_source_messages=boundary_source_messages,
        base_request_payload=final_payload,
        prompt_token_counter=prompt_token_counter,
        agent_settings=agent_settings,
        compaction_budget=compaction_budget,
        summarize_messages=summarize_messages,
        user_id=user_id,
        conv_id=conv_id,
        message_index=tool_context.message_index if tool_context is not None else 0,
        on_completed_compaction=_capture_completed_compaction,
        on_compacted_prompt_occupancy=_capture_compacted_prompt_occupancy,
    )
    final_payload["messages"] = preflight_outcome.provider_messages
    final_payload["max_tokens"] = preflight_outcome.output_token_limit
    return PreparedExecutionRequest(
        source_policy=source_policy,
        request_json=copy_json_dict(request_json),
        prepared_messages_before_compaction=copy_json_dict_list(prepared_messages),
        prepared_messages_after_compaction=copy_json_dict_list(
            preflight_outcome.compacted_messages,
        ),
        source_messages=copy_json_dict_list(source_messages),
        boundary_source_messages=copy_json_dict_list(boundary_source_messages),
        conv_id=conv_id,
        user_id=user_id,
        requested_model=resolved_model,
        agent_settings=agent_settings,
        todo_state=copy_json_dict(todo_state) if todo_state is not None else None,
        subagent_summaries=copy_json_dict_list(subagent_summaries),
        tool_context=tool_context,
        final_payload=copy_json_dict(final_payload),
        prepared_auto_compaction=prepared_auto_compaction,
    )


def _resolve_tool_choice_value(
    request_json: JSONDict,
    tool_context: MCPToolContext | None,
) -> JSONDict | str:
    tool_choice_value = request_json.get("tool_choice")
    if tool_choice_value == "none":
        raise ValidationError(
            "Prepared execution request cannot disable tools when tools are enabled.",
        )
    if isinstance(tool_choice_value, dict):
        return copy_json_dict(tool_choice_value)
    if isinstance(tool_choice_value, str) and tool_choice_value in {"auto", "required"}:
        return tool_choice_value
    if tool_context is not None and tool_context.tool_map:
        return "auto"
    return "none"


def _resolve_tool_payload_fields(
    request_json: JSONDict,
    tool_context: MCPToolContext | None,
) -> tuple[list[JSONDict], JSONDict | str | None]:
    tool_definitions: list[JSONDict] = []
    tools_value = request_json.get("tools")
    if isinstance(tools_value, list):
        for entry in tools_value:
            if isinstance(entry, dict):
                tool_definitions.append(dict(entry))
    if not tool_definitions:
        tool_definitions = collect_tool_definitions(tool_context)
    if tool_definitions:
        return (tool_definitions, _resolve_tool_choice_value(request_json, tool_context))
    if request_json.get("tool_choice") == "none":
        return ([], "none")
    return ([], None)

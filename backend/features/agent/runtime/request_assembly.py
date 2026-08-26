"""SoAI - Shared agentic request assembly [backend/features/agent/runtime/request_assembly.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.agent.settings_types import AgentSettings
from core.errors.exceptions import ValidationError
from core.openai.pinned_prefix import split_leading_pinned_prefix
from core.openai.request_field_filtering import build_inference_request_payload
from core.openai.system_prompt_support import (
    find_first_non_system_index,
    insert_system_message,
)
from core.orchestrator.types import MCPToolContext
from core.runtime.request_sources import RequestSource
from core.tool_calls.context_compaction_boundary_resolution import (
    resolve_context_compaction_boundaries,
)
from core.tool_calls.tool_result_prompt_cache import ToolResultPromptShapeCache
from core.tool_calls.tool_result_prompt_history import shape_prompt_history_tool_results
from core.types.json_value import copy_json_dict, copy_json_dict_list
from core.validation.strings import coerce_optional_trimmed_str
from features.agent.runtime.execution_request_preparation import (
    build_prepared_execution_request,
)
from features.agent.runtime.preflight_compaction import fit_prompt_to_compaction_budget
from features.agent.runtime.prepared_request_state import PreparedExecutionRequest
from features.agent.runtime.request_message_source import AgenticRequestMessageSource
from features.agent.runtime.request_messages import (
    extract_openai_messages,
    strip_internal_message_metadata,
)
from features.agent.runtime.system_prompt_injection import (
    inject_soai_and_user_system_prompts,
)
from features.agent.session.compaction_budget import (
    resolve_compaction_budget_from_agent_settings,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "PreparedAgenticRequestAssembly",
    "build_agentic_request_assembly",
)


@dataclass(frozen=True, slots=True)
class PreparedAgenticRequestAssembly:
    effective_request_json: JSONDict
    tool_context: MCPToolContext | None
    prepared_agent_request: PreparedExecutionRequest | None


async def build_agentic_request_assembly(
    *,
    api_dependencies: ApiDependencies,
    request_json: JSONDict,
    message_source: AgenticRequestMessageSource,
    user_id: int,
    conv_id: str,
    request_source: RequestSource,
    requested_model: str | None,
    agent_settings: AgentSettings,
    todo_state: JSONDict | None,
    subagent_summaries: list[JSONDict],
    tool_context: MCPToolContext | None,
    scope_message: JSONDict | None,
    prune_empty_messages: bool,
    stream: bool,
    source_policy: str,
    summarize_messages: Callable[[list[JSONDict]], Awaitable[str]] | None,
    extra_system_messages: tuple[str, ...] = (),
    model_settings_snapshot: JSONDict | None = None,
) -> PreparedAgenticRequestAssembly:
    canonical_source_messages = copy_json_dict_list(message_source.canonical_messages)
    pinned_source_prefix, source_message_body = split_leading_pinned_prefix(
        canonical_source_messages,
    )
    boundary_resolution = resolve_context_compaction_boundaries(
        source_message_body,
        strip_leading_pinned_prefix=False,
    )
    boundary_applied_source_messages = boundary_resolution.messages
    shape_cache = ToolResultPromptShapeCache()
    prompt_boundary_applied_source_messages = shape_prompt_history_tool_results(
        [
            *pinned_source_prefix,
            *boundary_applied_source_messages,
        ],
        shape_cache=shape_cache,
    )
    provider_prompt_source_messages = await message_source.build_provider_messages(
        prompt_boundary_applied_source_messages,
    )
    prompt_request_json = copy_json_dict(request_json)
    prompt_request_json["messages"] = copy_json_dict_list(provider_prompt_source_messages)
    tools_visible_to_model = bool(tool_context is not None and tool_context.tool_map)
    await inject_soai_and_user_system_prompts(
        config=api_dependencies.config,
        database_conversations=api_dependencies.database_conversations,
        database_chat_identity_defaults=api_dependencies.database_chat_identity_defaults,
        database_chat_model_defaults=api_dependencies.database_chat_model_defaults,
        request_json=prompt_request_json,
        user_id=user_id,
        request_source=request_source,
        tools_visible_to_model=tools_visible_to_model,
        model_settings_snapshot=model_settings_snapshot,
    )
    if extra_system_messages:
        messages_value = prompt_request_json.get("messages")
        if not isinstance(messages_value, list):
            raise ValidationError("build_agentic_request_assembly requires messages to be a list.")
        messages: list[JSONDict] = []
        for entry in messages_value:
            if not isinstance(entry, dict):
                raise ValidationError("build_agentic_request_assembly requires message objects.")
            messages.append(entry)
        insertion_index = find_first_non_system_index(messages)
        for system_message in reversed(tuple(extra_system_messages)):
            normalized = coerce_optional_trimmed_str(system_message)
            if normalized is None:
                continue
            insert_system_message(messages, normalized, index=insertion_index)
        prompt_request_json["messages"] = messages
    normalized_source_messages = extract_openai_messages(prompt_request_json)
    sanitized_prompt_request_json = build_inference_request_payload(prompt_request_json)
    sanitized_prompt_request_json["messages"] = strip_internal_message_metadata(
        normalized_source_messages,
    )
    if tool_context is None:
        compaction_budget = resolve_compaction_budget_from_agent_settings(agent_settings)
        if compaction_budget is None:
            raise ValidationError("Agent settings require a resolved compaction budget.")
        preflight_outcome = await fit_prompt_to_compaction_budget(
            message_history=normalized_source_messages,
            boundary_source_messages=boundary_applied_source_messages,
            base_request_payload=sanitized_prompt_request_json,
            prompt_token_counter=api_dependencies.prompt_token_counter,
            agent_settings=agent_settings,
            compaction_budget=compaction_budget,
            summarize_messages=summarize_messages,
            user_id=user_id,
            conv_id=conv_id,
            message_index=0,
        )
        sanitized_prompt_request_json["messages"] = preflight_outcome.provider_messages
        sanitized_prompt_request_json["max_tokens"] = preflight_outcome.output_token_limit
        return PreparedAgenticRequestAssembly(
            effective_request_json=sanitized_prompt_request_json,
            tool_context=None,
            prepared_agent_request=None,
        )
    prepared_agent_request = await build_prepared_execution_request(
        prompt_token_counter=api_dependencies.prompt_token_counter,
        source_policy=source_policy,
        request_json=prompt_request_json,
        source_messages=normalized_source_messages,
        boundary_source_messages=boundary_applied_source_messages,
        conv_id=tool_context.conv_id,
        user_id=tool_context.user_id,
        requested_model=requested_model,
        agent_settings=agent_settings,
        todo_state=todo_state,
        subagent_summaries=subagent_summaries,
        tool_context=tool_context,
        scope_message=scope_message,
        prune_empty_messages=prune_empty_messages,
        stream=stream,
        summarize_messages=summarize_messages,
    )
    effective_request_json = copy_json_dict(prepared_agent_request.final_payload)
    return PreparedAgenticRequestAssembly(
        effective_request_json=effective_request_json,
        tool_context=tool_context,
        prepared_agent_request=prepared_agent_request,
    )

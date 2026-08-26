"""SoAI - Manual compaction context helpers for agent WebUI routes [backend/features/api/routes/webui/conversation_agent_compaction/context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent_mode import normalize_agent_mode
from core.conversations.conversation_model_settings_resolution import (
    require_conversation_model_settings,
)
from core.errors.exceptions import StateError, ValidationError
from core.model_settings.normalization import read_optional_agent_settings
from core.serialization.json import serialize_json_compact_stable
from core.types.json_value import coerce_json_dict
from core.validation.strings import coerce_optional_trimmed_str
from features.agent.session.compaction_budget import (
    resolve_compaction_budget_for_request_model,
    resolve_compaction_budget_from_context_window,
    resolve_compaction_summary_prompt_budget_from_context_window,
)
from features.api.runtime.model_openai_capability_validation import (
    require_openai_capability_for_model,
)

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.types.json import JSONDict, JSONValue
    from features.api.runtime.context import ApiContext

__all__ = (
    "build_manual_tool_call_id",
    "coerce_compaction_history",
    "resolve_agent_mode_and_budget",
    "resolve_compaction_model_and_budget",
    "resolve_manual_target_prompt_tokens",
    "resolve_model_id",
    "resolve_summarizer_budget",
)

VALID_CHAT_ROLES = frozenset({"system", "user", "assistant", "tool"})


def build_manual_tool_call_id(turn_id: str) -> str:
    return f"context_compaction:{turn_id}"


def _coerce_message_content(value: JSONValue) -> str | list[JSONDict]:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        candidate = coerce_json_dict(value)
        if candidate is None:
            raise ValidationError("Conversation message content is invalid.")
        return serialize_json_compact_stable(candidate, ensure_ascii=False)
    if isinstance(value, list):
        parts: list[JSONDict] = []
        for item in value:
            if not isinstance(item, dict):
                raise ValidationError("Conversation message content part is invalid.")
            part = coerce_json_dict(item)
            if part is None:
                raise ValidationError("Conversation message content part is invalid.")
            parts.append(part)
        if not parts:
            return ""
        return parts
    return serialize_json_compact_stable(value, ensure_ascii=False)


def coerce_compaction_history(messages: list[JSONDict]) -> list[JSONDict]:
    history: list[JSONDict] = []
    for message in messages:
        role_value = message.get("role")
        role = coerce_optional_trimmed_str(role_value) or ""
        if role not in VALID_CHAT_ROLES:
            raise ValidationError("Conversation message role is invalid for compaction.")
        normalized: JSONDict = {
            "role": role,
            "content": _coerce_message_content(message.get("content")),
        }
        if role == "assistant":
            tool_calls_value = message.get("tool_calls")
            if isinstance(tool_calls_value, list):
                tool_calls: list[JSONDict] = []
                for tool_call_value in tool_calls_value:
                    if not isinstance(tool_call_value, dict):
                        continue
                    tool_call = coerce_json_dict(tool_call_value)
                    if tool_call is not None:
                        tool_calls.append(tool_call)
                if tool_calls:
                    normalized["tool_calls"] = tool_calls
        if role == "tool":
            tool_call_id_value = message.get("tool_call_id")
            tool_call_id = coerce_optional_trimmed_str(tool_call_id_value) or ""
            if tool_call_id:
                normalized["tool_call_id"] = tool_call_id
        history.append(normalized)
    return history


def resolve_model_id(conversation_record: JSONDict) -> str:
    settings = require_conversation_model_settings(conversation_record.get("model_settings"))
    model = coerce_optional_trimmed_str(settings.get("model"))
    if not model:
        raise ValidationError("Conversation model is missing; compaction requires a model.")
    return model


def _reject_removed_compaction_limit(agent_settings: JSONDict) -> None:
    if "compaction_max_prompt_tokens" in agent_settings:
        raise ValidationError(
            "model_settings.agent.compaction_max_prompt_tokens is no longer supported.",
        )


def resolve_agent_mode_and_budget(
    config: ConfigProtocol,
    conversation_record: JSONDict,
    *,
    context_window_tokens: int,
) -> tuple[str, int]:
    settings = require_conversation_model_settings(conversation_record.get("model_settings"))
    agent_settings = read_optional_agent_settings(
        settings,
        error_message="Conversation model_settings.agent payload is invalid.",
        exception_type=StateError,
    )
    _reject_removed_compaction_limit(agent_settings)
    compaction_budget = resolve_compaction_budget_from_context_window(
        config=config,
        context_window_tokens=context_window_tokens,
    )
    return (
        normalize_agent_mode(agent_settings.get("mode"), strict=True),
        compaction_budget.target_prompt_tokens,
    )


async def resolve_compaction_model_and_budget(
    *,
    api_context: ApiContext,
    conversation_record: JSONDict,
    model_candidate: str,
) -> tuple[str, int, str, int]:
    model = await require_openai_capability_for_model(
        model_resolution_service=api_context.dependencies.model_resolution_service,
        model_information_service=api_context.dependencies.model_information_service,
        virtual_model_get=api_context.dependencies.model_virtual_model_service.virtual_model_get,
        model_name=model_candidate,
        capability_key="chat_completions",
        label="Compaction model",
    )
    compaction_budget = await resolve_compaction_budget_for_request_model(
        config=api_context.dependencies.config,
        model_name=model,
        model_resolution_service=api_context.dependencies.model_resolution_service,
        model_information_service=api_context.dependencies.model_information_service,
        virtual_model_get=api_context.dependencies.model_virtual_model_service.virtual_model_get,
    )
    mode, compaction_limit = resolve_agent_mode_and_budget(
        api_context.dependencies.config,
        conversation_record,
        context_window_tokens=compaction_budget.context_window_tokens,
    )
    return (
        str(model),
        compaction_budget.context_window_tokens,
        str(mode),
        compaction_limit,
    )


def resolve_manual_target_prompt_tokens(
    *,
    current_prompt_tokens: int,
    configured_limit: int | None,
) -> int:
    if current_prompt_tokens <= 1:
        raise ValidationError("Conversation context is too small to compact.")
    if configured_limit is None:
        raise ValidationError("Manual compaction requires a resolved target prompt budget.")
    if configured_limit < 1:
        raise ValidationError("Manual compaction target prompt budget must be positive.")
    return int(configured_limit)


def resolve_summarizer_budget(
    *,
    config: ConfigProtocol,
    context_window_tokens: int,
) -> int:
    return resolve_compaction_summary_prompt_budget_from_context_window(
        config=config,
        context_window_tokens=context_window_tokens,
    )

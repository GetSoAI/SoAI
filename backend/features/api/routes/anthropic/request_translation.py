"""SoAI - Anthropic Messages to OpenAI request translation [backend/features/api/routes/anthropic/request_translation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.types.json import JSONDict
from core.validation.integers import is_strict_int
from features.api.routes.anthropic.content_translation import (
    translate_anthropic_messages,
    translate_anthropic_text_blocks,
)
from features.api.routes.anthropic.request_values import (
    invalid_anthropic_request,
    require_anthropic_dict,
    require_anthropic_json_schema,
    require_anthropic_trimmed_string,
)
from features.api.schemas.anthropic_messages import (
    AnthropicCountTokensRequest,
    AnthropicMessagesRequest,
)

__all__ = ("AnthropicRequestTranslation", "translate_anthropic_request")

_STRUCTURED_OUTPUT_TOOL_NAME = "soai_structured_output"


@dataclass(frozen=True, slots=True)
class AnthropicRequestTranslation:
    request_json: JSONDict
    extra_inference_parameters: JSONDict
    include_thinking_in_response: bool
    structured_output_schema: JSONDict | None


def _translate_tools(tools: list[JSONDict]) -> tuple[list[JSONDict], set[str]]:
    translated: list[JSONDict] = []
    declared_names: set[str] = set()
    for index, tool in enumerate(tools):
        name = require_anthropic_trimmed_string(tool.get("name"), f"tools.{index}.name")
        function: JSONDict = {
            "name": name,
            "parameters": require_anthropic_json_schema(
                tool.get("input_schema"),
                f"tools.{index}.input_schema",
            ),
        }
        description = tool.get("description")
        if isinstance(description, str):
            function["description"] = description
        elif description is not None:
            raise invalid_anthropic_request(f"tools.{index}.description must be a string.")
        translated.append({"type": "function", "function": function})
        declared_names.add(name)
    return translated, declared_names


def _translate_tool_choice(value: JSONDict, declared_tool_names: set[str]) -> str | JSONDict:
    if set(value).difference({"type", "name", "disable_parallel_tool_use"}):
        raise invalid_anthropic_request("tool_choice contains unsupported fields.")
    choice_type = value.get("type")
    if choice_type == "auto":
        return "auto"
    if choice_type == "none":
        return "none"
    if choice_type == "any":
        if not declared_tool_names:
            raise invalid_anthropic_request("tool_choice.type=any requires at least one tool.")
        return "required"
    if choice_type == "tool":
        name = require_anthropic_trimmed_string(value.get("name"), "tool_choice.name")
        if name not in declared_tool_names:
            raise invalid_anthropic_request("tool_choice.name must identify a declared tool.")
        return {
            "type": "function",
            "function": {"name": name},
        }
    raise invalid_anthropic_request("tool_choice.type is unsupported.")


def _apply_context_management(context_management: JSONDict | None) -> None:
    if context_management is None:
        return
    if set(context_management) != {"edits"}:
        raise invalid_anthropic_request("context_management only supports the edits field.")
    edits = context_management.get("edits")
    if not isinstance(edits, list) or not edits:
        raise invalid_anthropic_request(
            "context_management.edits must contain clear_thinking_20251015."
        )
    for index, edit_value in enumerate(edits):
        edit = require_anthropic_dict(edit_value, f"context_management.edits.{index}")
        if edit != {"type": "clear_thinking_20251015", "keep": "all"}:
            raise invalid_anthropic_request(
                "Only clear_thinking_20251015 with keep=all is supported.",
            )


def _apply_metadata(request_json: JSONDict, metadata: JSONDict | None) -> None:
    if metadata is None:
        return
    if set(metadata).difference({"user_id"}):
        raise invalid_anthropic_request("metadata only supports user_id.")
    user_id = metadata.get("user_id")
    if user_id is None:
        return
    request_json["safety_identifier"] = require_anthropic_trimmed_string(
        user_id,
        "metadata.user_id",
    )


def _apply_output_config(
    request_json: JSONDict,
    output_config: JSONDict | None,
) -> JSONDict | None:
    if output_config is None:
        return None
    format_value = output_config.get("format")
    if format_value is None:
        return None
    output_format = require_anthropic_dict(format_value, "output_config.format")
    if output_format.get("type") != "json_schema":
        raise invalid_anthropic_request("Only output_config.format.type=json_schema is supported.")
    if "tools" in request_json or "tool_choice" in request_json:
        raise invalid_anthropic_request(
            "Structured output cannot be combined with tools or tool_choice."
        )
    schema = require_anthropic_json_schema(
        output_format.get("schema"),
        "output_config.format.schema",
    )
    request_json["tools"] = [
        {
            "type": "function",
            "function": {"name": _STRUCTURED_OUTPUT_TOOL_NAME, "parameters": schema},
        }
    ]
    request_json["tool_choice"] = {
        "type": "function",
        "function": {"name": _STRUCTURED_OUTPUT_TOOL_NAME},
    }
    return schema


def _apply_thinking(
    request_json: JSONDict,
    thinking: JSONDict | None,
    max_tokens: int | None,
) -> bool:
    if thinking is None:
        return False
    thinking_type = thinking.get("type")
    if thinking_type == "enabled":
        if set(thinking) != {"type", "budget_tokens"}:
            raise invalid_anthropic_request(
                "Enabled thinking requires only type and budget_tokens."
            )
        budget_tokens = thinking.get("budget_tokens")
        if not is_strict_int(budget_tokens) or int(budget_tokens) < 1024:
            raise invalid_anthropic_request(
                "thinking.budget_tokens must be an integer of at least 1024."
            )
        if max_tokens is not None and int(budget_tokens) >= max_tokens:
            raise invalid_anthropic_request("thinking.budget_tokens must be less than max_tokens.")
        request_json["reasoning_effort"] = "high"
        return True
    if thinking_type == "disabled":
        if set(thinking) != {"type"}:
            raise invalid_anthropic_request("thinking contains unsupported fields.")
        return False
    if thinking_type == "adaptive":
        if set(thinking) == {"type"}:
            return True
        if thinking == {"type": "adaptive", "display": "omitted"}:
            return False
        raise invalid_anthropic_request("thinking contains unsupported fields.")
    raise invalid_anthropic_request("thinking.type is unsupported.")


def translate_anthropic_request(
    payload: AnthropicMessagesRequest | AnthropicCountTokensRequest,
) -> AnthropicRequestTranslation:
    translated_messages = translate_anthropic_messages(payload.messages)
    if payload.system is not None:
        translated_messages.insert(
            0,
            {
                "role": "system",
                "content": translate_anthropic_text_blocks(payload.system, "system"),
            },
        )
    request_json: JSONDict = {"model": payload.model, "messages": translated_messages}
    extra_inference_parameters: JSONDict = {}
    declared_tool_names: set[str] = set()
    if payload.tools:
        translated_tools, declared_tool_names = _translate_tools(payload.tools)
        request_json["tools"] = translated_tools
    if payload.tool_choice is not None:
        request_json["tool_choice"] = _translate_tool_choice(
            payload.tool_choice,
            declared_tool_names,
        )
        disable_parallel = payload.tool_choice.get("disable_parallel_tool_use")
        if disable_parallel is not None:
            if not isinstance(disable_parallel, bool):
                raise invalid_anthropic_request(
                    "tool_choice.disable_parallel_tool_use must be a boolean."
                )
            request_json["parallel_tool_calls"] = not disable_parallel
    max_tokens = payload.max_tokens if isinstance(payload, AnthropicMessagesRequest) else None
    include_thinking_in_response = _apply_thinking(
        request_json,
        payload.thinking,
        max_tokens,
    )
    output_config = payload.output_config
    if output_config is not None:
        unknown_output_fields = set(output_config).difference({"format", "effort"})
        if unknown_output_fields:
            raise invalid_anthropic_request("output_config contains unsupported fields.")
        effort = output_config.get("effort")
        if effort is not None:
            if effort not in {"low", "medium", "high", "max"}:
                raise invalid_anthropic_request("output_config.effort is unsupported.")
            request_json["reasoning_effort"] = effort
    structured_output_schema = _apply_output_config(request_json, output_config)
    _apply_context_management(payload.context_management)
    if isinstance(payload, AnthropicMessagesRequest):
        request_json["max_tokens"] = payload.max_tokens
        request_json["stream"] = payload.stream
        if payload.temperature is not None:
            request_json["temperature"] = payload.temperature
        if payload.top_p is not None:
            request_json["top_p"] = payload.top_p
        if payload.top_k is not None:
            extra_inference_parameters["top_k"] = payload.top_k
        if payload.stop_sequences is not None:
            request_json["stop"] = payload.stop_sequences
        _apply_metadata(request_json, payload.metadata)
    return AnthropicRequestTranslation(
        request_json=request_json,
        extra_inference_parameters=extra_inference_parameters,
        include_thinking_in_response=include_thinking_in_response,
        structured_output_schema=structured_output_schema,
    )

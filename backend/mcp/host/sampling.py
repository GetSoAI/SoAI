"""SoAI - MCP host-mode sampling conversions between MCP and OpenAI payloads [backend/mcp/host/sampling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.mcp.jsonrpc_validation import require_jsonrpc_dict_list, require_jsonrpc_int
from core.mcp.tool_catalog import build_openai_tool_definition
from core.serialization.json_parsing import parse_json_value
from core.types.json_value import coerce_json_dict
from mcp.host.content import sampling_messages_to_openai_messages
from mcp.protocol.types import MCPJSONRPCError

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "openai_response_to_sampling_result",
    "sampling_params_to_openai_payload",
)


def _build_invalid_params_error(message: str) -> MCPJSONRPCError:
    return MCPJSONRPCError(-32602, message)


def sampling_params_to_openai_payload(
    parameters: JSONDict,
    default_model: str | None,
) -> JSONDict:
    if not default_model:
        raise MCPJSONRPCError(
            -32602,
            "Missing TOOLS.MCP.HOST_MODE.SAMPLING.DEFAULT_MODEL for sampling requests",
        )
    messages = parameters.get("messages")
    system_prompt = parameters.get("systemPrompt")
    temperature = parameters.get("temperature")
    max_tokens = parameters.get("maxTokens")
    stop_sequences = parameters.get("stopSequences")
    tool_choice = parameters.get("toolChoice")
    tools = parameters.get("tools")
    normalized_messages = require_jsonrpc_dict_list(
        messages,
        build_error=_build_invalid_params_error,
        message="Invalid sampling messages",
    )
    if tools is not None and (not isinstance(tools, list)):
        raise MCPJSONRPCError(-32602, "Invalid tools array")
    if tool_choice is not None and tools is None:
        raise MCPJSONRPCError(-32602, "toolChoice requires tools")
    openai_messages: list[JSONDict] = []
    if system_prompt is not None:
        if not isinstance(system_prompt, str):
            raise MCPJSONRPCError(-32602, "Invalid systemPrompt")
        if system_prompt.strip():
            openai_messages.append({"role": "system", "content": system_prompt})
    openai_messages.extend(sampling_messages_to_openai_messages(normalized_messages))
    if max_tokens is None:
        raise MCPJSONRPCError(-32602, "maxTokens is required for sampling requests")
    max_tokens = require_jsonrpc_int(
        max_tokens,
        build_error=_build_invalid_params_error,
        message="Invalid maxTokens",
        minimum=1,
    )
    if stop_sequences is not None and (
        not isinstance(stop_sequences, list)
        or any(not isinstance(sequence, str) for sequence in stop_sequences)
    ):
        raise MCPJSONRPCError(-32602, "Invalid stopSequences")
    payload: JSONDict = {
        "model": default_model,
        "messages": openai_messages,
        "stream": False,
        "max_tokens": max_tokens,
    }
    if temperature is not None:
        payload["temperature"] = temperature
    if stop_sequences is not None:
        payload["stop"] = stop_sequences
    if tools is not None:
        tool_payloads: list[JSONDict] = []
        for tool in tools:
            if not isinstance(tool, dict):
                raise MCPJSONRPCError(-32602, "Invalid tools array")
            name_value = tool.get("name")
            input_schema_value = tool.get("inputSchema")
            if not isinstance(name_value, str) or not name_value:
                raise MCPJSONRPCError(-32602, "Invalid tool name")
            input_schema = coerce_json_dict(input_schema_value)
            if input_schema is None:
                raise MCPJSONRPCError(-32602, "Invalid tool inputSchema")
            description_value = tool.get("description")
            tool_definition: JSONDict = {"inputSchema": input_schema}
            if isinstance(description_value, str):
                tool_definition["description"] = description_value
            tool_payloads.append(build_openai_tool_definition(name_value, tool_definition))
        payload["tools"] = tool_payloads
    if tool_choice is not None:
        if not isinstance(tool_choice, dict) or tool_choice.get("mode") not in (
            "auto",
            "required",
            "none",
        ):
            raise MCPJSONRPCError(-32602, "Invalid toolChoice")
        payload["tool_choice"] = tool_choice["mode"]
    return payload


def openai_response_to_sampling_result(response: JSONDict, tools_provided: bool) -> JSONDict:
    model = response.get("model")
    if not isinstance(model, str) or not model:
        raise MCPJSONRPCError(-32603, "Invalid model response: missing model")
    choices = response.get("choices")
    if not choices or not isinstance(choices, list):
        raise MCPJSONRPCError(-32603, "Invalid model response: missing choices")
    first = choices[0] if isinstance(choices[0], dict) else {}
    message_value = first.get("message")
    if not isinstance(message_value, dict):
        raise MCPJSONRPCError(-32603, "Invalid model response: missing message")
    message = message_value
    finish = first.get("finish_reason")
    blocks: list[JSONDict] = []
    text_content = message.get("content")
    if isinstance(text_content, str) and text_content:
        blocks.append({"type": "text", "text": text_content})
    tool_calls_value = message.get("tool_calls") or []
    if not isinstance(tool_calls_value, list):
        raise MCPJSONRPCError(-32603, "Invalid tool calls in response")
    for call in tool_calls_value:
        if not isinstance(call, dict):
            raise MCPJSONRPCError(-32603, "Invalid tool call in response")
        call_id = call.get("id")
        function_value = call.get("function")
        function_name = function_value.get("name") if isinstance(function_value, dict) else None
        arguments_json = (
            function_value.get("arguments") if isinstance(function_value, dict) else None
        )
        if not call_id or not function_name or (not isinstance(arguments_json, str)):
            raise MCPJSONRPCError(-32603, "Invalid tool call in response")
        try:
            parsed = parse_json_value(arguments_json)
        except (ValueError, ValidationError) as exception:
            raise MCPJSONRPCError(
                -32603,
                "Invalid model response: tool_call arguments must be a JSON string",
            ) from exception
        blocks.append({"type": "tool_use", "id": call_id, "name": function_name, "input": parsed})
    stop_reason: str | None
    if tool_calls_value:
        stop_reason = "toolUse"
    elif finish is None:
        stop_reason = None
    elif isinstance(finish, str):
        stop_reason = {
            "stop": "endTurn",
            "length": "maxTokens",
            "tool_calls": "toolUse",
        }.get(
            finish,
            finish,
        )
    else:
        raise MCPJSONRPCError(-32603, "Invalid model response: finish_reason must be a string")
    result: JSONDict = {
        "role": "assistant",
        "model": model,
        **({"stopReason": stop_reason} if stop_reason else {}),
    }
    if tools_provided:
        result["content"] = blocks[0] if len(blocks) == 1 else blocks
    else:
        basic_blocks = [
            block for block in blocks if block.get("type") in ("text", "image", "audio")
        ]
        if len(basic_blocks) != 1:
            raise MCPJSONRPCError(
                -32603,
                "Invalid model response: expected a single basic content block",
            )
        result["content"] = basic_blocks[0]
    return result

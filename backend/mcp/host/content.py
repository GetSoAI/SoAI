"""SoAI - MCP content normalization to OpenAI format [backend/mcp/host/content.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.mcp.jsonrpc_validation import require_jsonrpc_dict, require_jsonrpc_dict_list
from core.serialization.base64_values import decode_base64_ascii
from core.serialization.json import serialize_json_compact_stable_strict
from mcp.protocol.audio_formats import resolve_openai_audio_format
from mcp.protocol.types import MCPJSONRPCError

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "mcp_content_to_openai_content",
    "normalize_sampling_message_content",
    "sampling_messages_to_openai_messages",
)


def _build_invalid_params_error(message: str) -> MCPJSONRPCError:
    return MCPJSONRPCError(-32602, message)


def normalize_sampling_message_content(content: JSONValue) -> list[JSONDict]:
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, dict):
        return [
            require_jsonrpc_dict(
                content,
                build_error=_build_invalid_params_error,
                message="Invalid message content",
            ),
        ]
    if isinstance(content, list):
        return require_jsonrpc_dict_list(
            content,
            build_error=_build_invalid_params_error,
            message="Invalid message content",
        )
    raise MCPJSONRPCError(-32602, "Invalid message content")


def mcp_content_to_openai_content(content: list[JSONDict]) -> JSONValue:
    response: list[JSONDict] = []
    for block in content:
        content_type = block.get("type")
        if content_type == "text":
            text = block.get("text")
            if not isinstance(text, str):
                raise MCPJSONRPCError(-32602, "Invalid text content")
            response.append({"type": "text", "text": text})
        elif content_type == "image":
            mime_type = block.get("mimeType")
            data = block.get("data")
            if (
                not isinstance(mime_type, str)
                or not mime_type
                or (not isinstance(data, str))
                or (not data)
            ):
                raise MCPJSONRPCError(-32602, "Invalid image content")
            try:
                decode_base64_ascii(
                    data,
                    error_message="Invalid image content: data is not valid base64",
                )
            except ValidationError as exception:
                raise MCPJSONRPCError(
                    -32602,
                    "Invalid image content: data is not valid base64",
                ) from exception
            response.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{data}"},
                },
            )
        elif content_type == "audio":
            mime_type = block.get("mimeType")
            data = block.get("data")
            if (
                not isinstance(mime_type, str)
                or not mime_type
                or (not isinstance(data, str))
                or (not data)
            ):
                raise MCPJSONRPCError(-32602, "Invalid audio content")
            audio_format = resolve_openai_audio_format(mime_type)
            if not audio_format:
                raise MCPJSONRPCError(-32602, f"Unsupported audio mimeType: {mime_type}")
            try:
                decode_base64_ascii(
                    data,
                    error_message="Invalid audio content: data is not valid base64",
                )
            except ValidationError as exception:
                raise MCPJSONRPCError(
                    -32602,
                    "Invalid audio content: data is not valid base64",
                ) from exception
            response.append(
                {
                    "type": "input_audio",
                    "input_audio": {"data": data, "format": audio_format},
                },
            )
        else:
            raise MCPJSONRPCError(-32602, f"Unsupported content type: {content_type}")
    if len(response) > 1:
        return response
    if len(response) == 1 and response[0].get("type") == "text":
        return response[0].get("text")
    return response


def sampling_messages_to_openai_messages(
    messages: list[JSONDict],
) -> list[JSONDict]:
    pending_tool_use_ids: list[str] = []
    openai_messages: list[JSONDict] = []
    for message in messages:
        if not isinstance(message, dict):
            raise MCPJSONRPCError(-32602, "Invalid sampling message")
        role = message.get("role")
        blocks = normalize_sampling_message_content(message.get("content"))
        if not isinstance(role, str) or not role:
            raise MCPJSONRPCError(-32602, "Invalid sampling message role")
        block_types: set[str] = set()
        for block in blocks:
            block_type = block.get("type")
            if not isinstance(block_type, str) or not block_type:
                raise MCPJSONRPCError(-32602, "Invalid sampling message content type")
            block_types.add(block_type)
        if pending_tool_use_ids and block_types != {"tool_result"}:
            raise MCPJSONRPCError(
                -32602,
                "Tool uses must be followed by a tool_result user message",
            )
        if "tool_result" in block_types:
            if role != "user" or block_types != {"tool_result"}:
                raise MCPJSONRPCError(
                    -32602,
                    "Tool result messages must use role 'user' and contain only tool_result content",
                )
            tool_result_ids: list[str] = []
            for block in blocks:
                tool_use_id = block.get("toolUseId")
                if not isinstance(tool_use_id, str) or not tool_use_id:
                    raise MCPJSONRPCError(-32602, "tool_result is missing toolUseId")
                if pending_tool_use_ids and tool_use_id not in pending_tool_use_ids:
                    raise MCPJSONRPCError(-32602, "tool_result references unknown toolUseId")
                tool_result_ids.append(tool_use_id)
                content = block.get("content", [])
                structured = block.get("structuredContent")
                if not isinstance(content, list):
                    raise MCPJSONRPCError(-32602, "tool_result content invalid")
                text_parts: list[str] = []
                for part in content:
                    if not isinstance(part, dict):
                        raise MCPJSONRPCError(-32602, "tool_result content invalid")
                    part_type = part.get("type")
                    text_value = part.get("text")
                    if part_type != "text" or not isinstance(text_value, str):
                        raise MCPJSONRPCError(-32602, "tool_result content invalid")
                    if text_value:
                        text_parts.append(text_value)
                openai_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_use_id,
                        "content": "\n".join(
                            text_parts
                            + (
                                [serialize_json_compact_stable_strict(structured)]
                                if isinstance(structured, dict)
                                else []
                            ),
                        ),
                    },
                )
            if pending_tool_use_ids and any(
                identifier not in tool_result_ids for identifier in pending_tool_use_ids
            ):
                raise MCPJSONRPCError(-32602, "Missing tool results for one or more tool uses")
            pending_tool_use_ids = []
            continue
        if "tool_use" in block_types:
            if role != "assistant" or any(
                block.get("type") not in ("text", "tool_use") for block in blocks
            ):
                raise MCPJSONRPCError(
                    -32602,
                    "Tool use messages must use role 'assistant' and contain only text/tool_use",
                )
            tool_calls: list[JSONDict] = []
            tool_use_ids: list[str] = []
            for block in blocks:
                if block.get("type") == "tool_use":
                    tool_use_id = block.get("id")
                    name = block.get("name")
                    tool_input = block.get("input")
                    if (
                        not isinstance(tool_use_id, str)
                        or not tool_use_id
                        or (not isinstance(name, str))
                        or (not name)
                        or (not isinstance(tool_input, dict))
                    ):
                        raise MCPJSONRPCError(-32602, "Invalid tool_use block")
                    tool_calls.append(
                        {
                            "id": tool_use_id,
                            "type": "function",
                            "function": {
                                "name": name,
                                "arguments": serialize_json_compact_stable_strict(tool_input),
                            },
                        },
                    )
                    tool_use_ids.append(tool_use_id)
            if not tool_calls:
                raise MCPJSONRPCError(-32602, "Tool use message contains no tool_use blocks")
            text_content = "\n".join(
                str(block.get("text", ""))
                for block in blocks
                if block.get("type") == "text" and isinstance(block.get("text"), str)
            )
            openai_messages.append(
                {"role": "assistant", "content": text_content, "tool_calls": tool_calls},
            )
            pending_tool_use_ids = tool_use_ids
            continue
        if role == "assistant" and any(block.get("type") != "text" for block in blocks):
            raise MCPJSONRPCError(-32602, "Assistant messages may only contain text content")
        openai_messages.append({"role": role, "content": mcp_content_to_openai_content(blocks)})
    if pending_tool_use_ids:
        raise MCPJSONRPCError(-32602, "Missing tool results for one or more tool uses")
    return openai_messages

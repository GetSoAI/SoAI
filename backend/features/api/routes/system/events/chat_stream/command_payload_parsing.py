"""SoAI - Shared WebSocket chat command payload parsing [backend/features/api/routes/system/events/chat_stream/command_payload_parsing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.state.access import AccessAction
from core.types.json_value import coerce_json_dict, coerce_json_list
from core.validation.strings import coerce_required_non_empty_str

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from features.api.streaming.websocket import WebsocketConnection

__all__ = (
    "ChatCommandPayloadHints",
    "ParsedChatCommandRequestFields",
    "connection_has_chat_command_access",
    "extract_chat_command_payload_hints",
    "parse_chat_command_request_fields",
    "require_chat_command_json_payload",
    "resolve_optional_chat_command_json_array",
    "resolve_optional_non_empty_chat_command_text",
)


@dataclass(frozen=True, slots=True)
class ChatCommandPayloadHints:
    conv_id: str
    request_id: str


@dataclass(frozen=True, slots=True)
class ParsedChatCommandRequestFields:
    conv_id: str
    request_id: str
    openai_request: JSONDict


def connection_has_chat_command_access(connection: WebsocketConnection) -> bool:
    return AccessAction.AUTH_COOKIE in connection.granted_actions


def extract_chat_command_payload_hints(data: JSONValue) -> ChatCommandPayloadHints:
    if not isinstance(data, dict):
        return ChatCommandPayloadHints(conv_id="", request_id="")
    return ChatCommandPayloadHints(
        conv_id=_strip_json_string(data.get("conv_id")),
        request_id=_strip_json_string(data.get("request_id")),
    )


def require_chat_command_json_payload(data: JSONValue, *, command_name: str) -> JSONDict:
    payload = coerce_json_dict(data)
    if payload is None:
        raise ValidationError(f"{command_name} payload must be a JSON object.")
    return payload


def parse_chat_command_request_fields(data: JSONDict) -> ParsedChatCommandRequestFields:
    conv_id = coerce_required_non_empty_str(data.get("conv_id"), label="conv_id")
    request_id = coerce_required_non_empty_str(data.get("request_id"), label="request_id")
    openai_request = coerce_json_dict(data.get("openai_request"))
    if openai_request is None:
        raise ValidationError("openai_request must be a JSON object.")
    return ParsedChatCommandRequestFields(
        conv_id=conv_id,
        request_id=request_id,
        openai_request=openai_request,
    )


def resolve_optional_non_empty_chat_command_text(data: JSONDict, field_name: str) -> str | None:
    value = data.get(field_name)
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return value if stripped else None


def resolve_optional_chat_command_json_array(
    data: JSONDict,
    field_name: str,
) -> list[JSONValue]:
    value = data.get(field_name)
    if value is None:
        return []
    result = coerce_json_list(value)
    if result is None:
        raise ValidationError(f"{field_name} must be a JSON array.")
    return result


def _strip_json_string(value: JSONValue) -> str:
    return value.strip() if isinstance(value, str) else ""

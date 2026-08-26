"""SoAI - Internal OpenAI chat message sequencing contracts [backend/core/openai/chat_messages_contracts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.chat_role_sets import OPENAI_ALLOWED_ROLES, OPENAI_PINNED_ROLES
from core.runtime.request_sources import RequestSource, normalize_request_source

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "TOOL_SEQUENCE_ERROR_DUPLICATE_TOOL_RESULT",
    "TOOL_SEQUENCE_ERROR_MISSING_TOOL_RESULTS",
    "TOOL_SEQUENCE_ERROR_NON_TOOL_BEFORE_ALL_RESULTS",
    "TOOL_SEQUENCE_ERROR_TOOL_CALL_ID_NOT_ACTIVE",
    "TOOL_SEQUENCE_ERROR_TOOL_CALL_ID_REQUIRED",
    "TOOL_SEQUENCE_ERROR_TOOL_MESSAGE_WITHOUT_ASSISTANT_TOOL_CALLS",
    "extract_expected_tool_call_ids",
    "extract_valid_tool_call_ids",
    "is_internal_chat_messages_tool_sequence_contract_violation_message",
    "validate_internal_chat_messages_contracts",
    "validate_internal_chat_messages_contracts_for_sources",
)

_PINNED_ROLES: frozenset[str] = OPENAI_PINNED_ROLES
_ALLOWED_ROLES: frozenset[str] = OPENAI_ALLOWED_ROLES

TOOL_SEQUENCE_ERROR_TOOL_MESSAGE_WITHOUT_ASSISTANT_TOOL_CALLS: str = (
    "Tool message without a preceding assistant tool_calls message."
)
TOOL_SEQUENCE_ERROR_TOOL_CALL_ID_REQUIRED: str = "tool_call_id is required for tool messages."
TOOL_SEQUENCE_ERROR_TOOL_CALL_ID_NOT_ACTIVE: str = (
    "tool_call_id does not match any active tool call."
)
TOOL_SEQUENCE_ERROR_DUPLICATE_TOOL_RESULT: str = "Duplicate tool result for tool_call_id."
TOOL_SEQUENCE_ERROR_NON_TOOL_BEFORE_ALL_RESULTS: str = (
    "Non-tool message encountered before all tool results were provided."
)
TOOL_SEQUENCE_ERROR_MISSING_TOOL_RESULTS: str = "Missing tool results for tool_calls."

_TOOL_SEQUENCE_CONTRACT_MESSAGES: frozenset[str] = frozenset(
    (
        TOOL_SEQUENCE_ERROR_TOOL_MESSAGE_WITHOUT_ASSISTANT_TOOL_CALLS,
        TOOL_SEQUENCE_ERROR_TOOL_CALL_ID_REQUIRED,
        TOOL_SEQUENCE_ERROR_TOOL_CALL_ID_NOT_ACTIVE,
        TOOL_SEQUENCE_ERROR_DUPLICATE_TOOL_RESULT,
        TOOL_SEQUENCE_ERROR_NON_TOOL_BEFORE_ALL_RESULTS,
        TOOL_SEQUENCE_ERROR_MISSING_TOOL_RESULTS,
    ),
)


def is_internal_chat_messages_tool_sequence_contract_violation_message(message: str) -> bool:
    normalized = str(message or "").strip()
    return normalized in _TOOL_SEQUENCE_CONTRACT_MESSAGES


def extract_expected_tool_call_ids(
    tool_calls_value: JSONValue,
    *,
    message_index: int,
) -> tuple[str, ...]:
    if not isinstance(tool_calls_value, list) or not tool_calls_value:
        return ()
    call_ids: list[str] = []
    for call_index, call in enumerate(tool_calls_value):
        if not isinstance(call, dict):
            raise ValidationError(
                f"Tool call at index {call_index} must be an object.",
                details={"param": f"messages[{message_index}].tool_calls[{call_index}]"},
            )
        call_id_value = call.get("id")
        call_id = call_id_value.strip() if isinstance(call_id_value, str) else ""
        if not call_id:
            raise ValidationError(
                "Tool call id is required.",
                details={"param": f"messages[{message_index}].tool_calls[{call_index}].id"},
            )
        call_ids.append(call_id)
    unique = tuple(dict.fromkeys(call_id for call_id in call_ids if call_id))
    if len(unique) != len(call_ids):
        raise ValidationError(
            "Tool call ids must be unique within a message.",
            details={"param": f"messages[{message_index}].tool_calls"},
        )
    return unique


def extract_valid_tool_call_ids(tool_calls_value: JSONValue) -> tuple[str, ...]:
    if not isinstance(tool_calls_value, list) or not tool_calls_value:
        return ()
    call_ids: list[str] = []
    for call in tool_calls_value:
        if not isinstance(call, dict):
            return ()
        call_id_value = call.get("id")
        call_id = call_id_value.strip() if isinstance(call_id_value, str) else ""
        if not call_id:
            return ()
        call_ids.append(call_id)
    unique = tuple(dict.fromkeys(call_id for call_id in call_ids if call_id))
    if len(unique) != len(call_ids):
        return ()
    return unique


def _format_role(role_value: JSONValue) -> str:
    if isinstance(role_value, str) and role_value:
        return role_value
    return "unknown"


def validate_internal_chat_messages_contracts(payload: JSONDict) -> None:
    messages_value = payload.get("messages")
    if not isinstance(messages_value, list):
        return
    expected_tool_call_ids: tuple[str, ...] | None = None
    satisfied_tool_call_ids: set[str] = set()
    expected_tool_call_ids_index: int | None = None
    for index, message in enumerate(messages_value):
        if not isinstance(message, dict):
            raise ValidationError(
                f"Message at index {index} must be an object.",
                details={"param": f"messages[{index}]"},
            )
        role_value = message.get("role")
        role = role_value.strip() if isinstance(role_value, str) else ""
        if role not in _ALLOWED_ROLES:
            raise ValidationError(
                f"Unsupported role '{_format_role(role_value)}' in internal request.",
                details={"param": f"messages[{index}].role"},
            )
        if role == "tool":
            active_tool_call_ids_value = expected_tool_call_ids
            if active_tool_call_ids_value is None:
                raise ValidationError(
                    TOOL_SEQUENCE_ERROR_TOOL_MESSAGE_WITHOUT_ASSISTANT_TOOL_CALLS,
                    details={"param": f"messages[{index}].role"},
                )
            active_tool_call_ids: tuple[str, ...] = tuple(active_tool_call_ids_value)
            tool_call_id_value = message.get("tool_call_id")
            tool_call_id = tool_call_id_value.strip() if isinstance(tool_call_id_value, str) else ""
            if not tool_call_id:
                raise ValidationError(
                    TOOL_SEQUENCE_ERROR_TOOL_CALL_ID_REQUIRED,
                    details={"param": f"messages[{index}].tool_call_id"},
                )
            if tool_call_id not in active_tool_call_ids:
                source_index = (
                    expected_tool_call_ids_index if expected_tool_call_ids_index is not None else 0
                )
                raise ValidationError(
                    TOOL_SEQUENCE_ERROR_TOOL_CALL_ID_NOT_ACTIVE,
                    details={
                        "param": f"messages[{index}].tool_call_id",
                        "source": f"messages[{source_index}].tool_calls",
                    },
                )
            if tool_call_id in satisfied_tool_call_ids:
                raise ValidationError(
                    TOOL_SEQUENCE_ERROR_DUPLICATE_TOOL_RESULT,
                    details={"param": f"messages[{index}].tool_call_id"},
                )
            satisfied_tool_call_ids.add(tool_call_id)
            if len(satisfied_tool_call_ids) == len(active_tool_call_ids):
                expected_tool_call_ids = None
                satisfied_tool_call_ids = set()
                expected_tool_call_ids_index = None
            continue
        if expected_tool_call_ids is not None:
            raise ValidationError(
                TOOL_SEQUENCE_ERROR_NON_TOOL_BEFORE_ALL_RESULTS,
                details={"param": f"messages[{index}].role"},
            )
        if role == "assistant":
            expected = extract_expected_tool_call_ids(
                message.get("tool_calls"),
                message_index=index,
            )
            if expected:
                expected_tool_call_ids = expected
                expected_tool_call_ids_index = index
                satisfied_tool_call_ids = set()
            continue
        if role in _PINNED_ROLES or role == "user":
            continue
        raise ValidationError(
            f"Unsupported role '{_format_role(role_value)}' in internal request.",
            details={"param": f"messages[{index}].role"},
        )
    if expected_tool_call_ids is not None:
        raise ValidationError(
            TOOL_SEQUENCE_ERROR_MISSING_TOOL_RESULTS,
            details={"param": "messages"},
        )


def validate_internal_chat_messages_contracts_for_sources(
    payload: JSONDict,
    *,
    request_source: RequestSource,
) -> None:
    if not isinstance(request_source, str):
        raise ValidationError("request_source must be a string.")
    if normalize_request_source(request_source) is None:
        raise ValidationError("request_source must be a non-empty string.")
    validate_internal_chat_messages_contracts(payload)

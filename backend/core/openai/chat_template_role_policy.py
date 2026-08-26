"""SoAI - Chat template role policy normalization for strict backends [backend/core/openai/chat_template_role_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import httpx2

from core.errors.exceptions import SoAIError, ValidationError
from core.errors.http_error_responses import extract_http_response_message
from core.openai.chat_role_sets import OPENAI_PINNED_ROLES
from core.openai.message_sequence_normalization import (
    coerce_openai_message_content_to_text,
    merge_adjacent_dialogue_turns_for_strict_templates,
    merge_text_fragments,
    prefix_user_message_with_text,
)
from core.openai.tool_dialogue_conversion import (
    convert_tool_messages_to_user_assistant_turns_for_strict_templates,
)
from core.types.json import JSONDict, JSONValue
from core.types.json_value import require_json_dict

__all__ = (
    "CHAT_TEMPLATE_ROLE_POLICY_AUTO",
    "CHAT_TEMPLATE_ROLE_REJECTION_CATEGORY",
    "CHAT_TEMPLATE_ROLE_REJECTION_CATEGORY_KEY",
    "CHAT_TEMPLATE_ROLE_POLICY_SEQUENCE",
    "SOAI_CHAT_TEMPLATE_MAX_ROLE_PARAMETER",
    "extract_chat_template_role_rejection_http_status",
    "is_chat_template_role_error_message",
    "normalize_chat_template_role_policy",
    "normalize_chat_template_role_policy_value",
    "normalize_openai_messages_for_chat_template_role_policy",
    "normalize_openai_responses_input_for_chat_template_role_policy",
    "prepare_openai_request_for_chat_template_role_policy",
    "read_message_compatibility_mode",
    "strip_soai_internal_chat_template_parameters",
)

SOAI_CHAT_TEMPLATE_MAX_ROLE_PARAMETER = "soai_chat_template_max_role"
CHAT_TEMPLATE_ROLE_POLICY_AUTO = "auto"
CHAT_TEMPLATE_ROLE_REJECTION_CATEGORY_KEY = "upstream_error_category"
CHAT_TEMPLATE_ROLE_REJECTION_CATEGORY = "chat_template_role_rejection"
CHAT_TEMPLATE_ROLE_POLICY_SEQUENCE: tuple[str, ...] = (
    "system",
    "system_strict",
    "user_strict",
)

_ALLOWED_MODES: frozenset[str] = frozenset(
    (CHAT_TEMPLATE_ROLE_POLICY_AUTO, *CHAT_TEMPLATE_ROLE_POLICY_SEQUENCE),
)
_PINNED_ROLES: frozenset[str] = OPENAI_PINNED_ROLES
_STRICT_ALLOWED_ROLES: frozenset[str] = frozenset(("user", "assistant", "tool"))
_ROLE_ERROR_MARKERS: tuple[str, ...] = (
    "conversation roles must alternate user/assistant/user/assistant",
    "only user, assistant and tool roles are supported",
    "unsupported role",
    "role must be",
    "got system",
)
_ROLE_PLACEMENT_SUBJECTS: tuple[str, ...] = (
    "developer message",
    "developer role",
    "system message",
    "system role",
)
_ROLE_PLACEMENT_REQUIREMENTS: tuple[str, ...] = (
    "must be at the beginning",
    "must be at the start",
    "must be first",
    "only allowed at the beginning",
    "only allowed at the start",
)


def read_message_compatibility_mode(config_value: JSONValue | None) -> str:
    return normalize_chat_template_role_policy_value(
        config_value,
        label="API.OPENAI.PROMPTS.MESSAGE_COMPATIBILITY_MODE",
    )


def strip_soai_internal_chat_template_parameters(parameters: JSONDict) -> JSONDict:
    if not parameters:
        return {}
    if SOAI_CHAT_TEMPLATE_MAX_ROLE_PARAMETER not in parameters:
        return dict(parameters)
    stripped = dict(parameters)
    stripped.pop(SOAI_CHAT_TEMPLATE_MAX_ROLE_PARAMETER, None)
    return stripped


def normalize_chat_template_role_policy(mode: str) -> str:
    normalized = mode.strip().lower()
    if normalized in _ALLOWED_MODES:
        return normalized
    raise ValidationError(f"Unsupported {SOAI_CHAT_TEMPLATE_MAX_ROLE_PARAMETER} value: {mode!r}.")


def normalize_chat_template_role_policy_value(value: JSONValue | None, *, label: str) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{label} must be a string.")
    return normalize_chat_template_role_policy(value)


def prepare_openai_request_for_chat_template_role_policy(
    *,
    request_json: JSONDict,
    model_parameters: JSONDict,
) -> tuple[JSONDict, JSONDict]:
    if SOAI_CHAT_TEMPLATE_MAX_ROLE_PARAMETER in request_json:
        mode = normalize_chat_template_role_policy_value(
            request_json.get(SOAI_CHAT_TEMPLATE_MAX_ROLE_PARAMETER),
            label=SOAI_CHAT_TEMPLATE_MAX_ROLE_PARAMETER,
        )
    elif SOAI_CHAT_TEMPLATE_MAX_ROLE_PARAMETER in model_parameters:
        mode = normalize_chat_template_role_policy_value(
            model_parameters.get(SOAI_CHAT_TEMPLATE_MAX_ROLE_PARAMETER),
            label=SOAI_CHAT_TEMPLATE_MAX_ROLE_PARAMETER,
        )
    else:
        mode = "system"
    if mode == CHAT_TEMPLATE_ROLE_POLICY_AUTO:
        mode = "system"
    effective_request_json = dict(request_json)
    effective_request_json.pop(SOAI_CHAT_TEMPLATE_MAX_ROLE_PARAMETER, None)
    messages_value = effective_request_json.get("messages")
    if isinstance(messages_value, list):
        raw_messages: list[JSONDict] = []
        for index, item in enumerate(messages_value):
            raw_messages.append(require_json_dict(item, label=f"messages[{index}]"))
        effective_request_json["messages"] = (
            normalize_openai_messages_for_chat_template_role_policy(
                messages=raw_messages,
                mode=mode,
            )
        )
    if "input" in effective_request_json:
        effective_request_json["input"] = (
            normalize_openai_responses_input_for_chat_template_role_policy(
                input_value=effective_request_json.get("input"),
                mode=mode,
            )
        )
    stripped_parameters = strip_soai_internal_chat_template_parameters(model_parameters)
    return (effective_request_json, stripped_parameters)


def normalize_openai_messages_for_chat_template_role_policy(
    *,
    messages: list[JSONDict],
    mode: str,
) -> list[JSONDict]:
    normalized_mode = normalize_chat_template_role_policy(mode)
    if normalized_mode == CHAT_TEMPLATE_ROLE_POLICY_AUTO:
        normalized_mode = "system"
    if normalized_mode == "system":
        return [
            require_json_dict(message, label=f"messages[{index}]")
            for index, message in enumerate(messages)
        ]
    pinned_fragments: list[str] = []
    remaining: list[JSONDict] = []
    for index, raw in enumerate(messages):
        message = require_json_dict(raw, label=f"messages[{index}]")
        role_value = message.get("role")
        role = role_value.strip() if isinstance(role_value, str) else ""
        if role in _PINNED_ROLES:
            pinned_fragments.append(
                coerce_openai_message_content_to_text(message.get("content")).strip(),
            )
            continue
        remaining.append(message)
    pinned_text = merge_text_fragments(
        "",
        "\n\n".join(fragment for fragment in pinned_fragments if fragment),
    )
    merged = merge_adjacent_dialogue_turns_for_strict_templates(remaining)
    for index, message in enumerate(merged):
        role_value = message.get("role")
        role = role_value.strip() if isinstance(role_value, str) else ""
        if role not in _STRICT_ALLOWED_ROLES:
            raise ValidationError(
                "Strict chat-template role policy does not support this role.",
                details={"param": f"messages[{index}].role", "role": role},
            )
    if normalized_mode == "system_strict":
        if merged:
            first_role_value = merged[0].get("role")
            first_role = first_role_value.strip() if isinstance(first_role_value, str) else ""
            if first_role == "assistant":
                raise ValidationError(
                    "Strict chat-template role policy requires the first non-system message to be a user message.",
                    details={"param": "messages[0].role", "role": first_role},
                )
        if pinned_text:
            return [{"role": "system", "content": pinned_text}, *merged]
        return merged
    if normalized_mode == "user_strict":
        dialogue = convert_tool_messages_to_user_assistant_turns_for_strict_templates(merged)
        if not pinned_text:
            if dialogue:
                first_role_value = dialogue[0].get("role")
                first_role = first_role_value.strip() if isinstance(first_role_value, str) else ""
                if first_role == "assistant":
                    raise ValidationError(
                        "Strict chat-template role policy requires the first non-system message to be a user message.",
                        details={"param": "messages[0].role", "role": first_role},
                    )
            return dialogue
        if dialogue and dialogue[0].get("role") == "user":
            dialogue[0] = prefix_user_message_with_text(dialogue[0], pinned_text)
            return dialogue
        return [{"role": "user", "content": pinned_text}, *dialogue]
    raise ValidationError(f"Unhandled {SOAI_CHAT_TEMPLATE_MAX_ROLE_PARAMETER} mode: {mode!r}.")


def normalize_openai_responses_input_for_chat_template_role_policy(
    *,
    input_value: JSONValue,
    mode: str,
) -> JSONValue:
    if not isinstance(input_value, list):
        return input_value
    message_entries: list[tuple[int, JSONDict]] = []
    passthrough: list[JSONValue] = []
    for index, entry in enumerate(input_value):
        if isinstance(entry, dict) and "role" in entry:
            message_entries.append((index, dict(entry)))
        else:
            passthrough.append(entry)
    if not message_entries:
        return list(input_value)
    normalized_messages = normalize_openai_messages_for_chat_template_role_policy(
        messages=[message for _, message in message_entries],
        mode=mode,
    )
    if passthrough:
        raise ValidationError(
            "Strict chat-template role policy does not support mixing message and non-message input items.",
            details={"param": "input"},
        )
    return [dict(message) for message in normalized_messages]


def is_chat_template_role_error_message(message: str) -> bool:
    normalized = str(message or "").strip().lower()
    if not normalized:
        return False
    has_role_placement_subject = any(subject in normalized for subject in _ROLE_PLACEMENT_SUBJECTS)
    has_role_placement_requirement = any(
        requirement in normalized for requirement in _ROLE_PLACEMENT_REQUIREMENTS
    )
    if has_role_placement_subject and has_role_placement_requirement:
        return True
    has_role_context = "role" in normalized or "jinja exception" in normalized
    if not has_role_context:
        return False
    for marker in _ROLE_ERROR_MARKERS:
        if marker in normalized:
            return True
    return False


def extract_chat_template_role_rejection_http_status(
    exception: BaseException,
) -> int | None:
    current_exception: BaseException | None = exception
    visited_exception_ids: set[int] = set()
    while current_exception is not None:
        exception_id = id(current_exception)
        if exception_id in visited_exception_ids:
            return None
        visited_exception_ids.add(exception_id)
        if isinstance(current_exception, httpx2.HTTPStatusError):
            response = current_exception.response
            if response is None or response.status_code < 400:
                return None
            upstream_message = extract_http_response_message(
                response,
                response.status_code,
            )
            if is_chat_template_role_error_message(upstream_message):
                return response.status_code
        next_exception = current_exception.__cause__
        if next_exception is None and isinstance(current_exception, SoAIError):
            next_exception = current_exception.cause
        if next_exception is None and not current_exception.__suppress_context__:
            next_exception = current_exception.__context__
        current_exception = next_exception
    return None

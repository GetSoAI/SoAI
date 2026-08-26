"""SoAI - WebUI conversation message role field contract [backend/core/conversations/conversation_message_role_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError

__all__ = ("validate_webui_chat_message_role_fields",)

_BASE_ALLOWED_FIELDS: frozenset[str] = frozenset(
    (
        "role",
        "message_type",
        "content",
        "timestamp",
        "assistant_turn_at_ms",
        "model_variant_index",
        "name",
        "model_id",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "finish_reason",
        "generation_latency_ms",
        "thinking_tail_duration_ms",
    ),
)


def _allowed_fields_for_role(role: str) -> frozenset[str]:
    if role == "assistant":
        return frozenset(("tool_calls", "assistant_event_timeline", "request_id", "usage_source"))
    if role == "tool":
        return frozenset(("tool_call_id",))
    return frozenset()


def _message_prefix(index: int | None) -> str:
    if index is None:
        return "Message"
    return f"Message at index {index}"


def validate_webui_chat_message_role_fields(
    *,
    role: str,
    field_names: frozenset[str],
    content_present: bool,
    content_is_none: bool,
    assistant_event_timeline_present: bool,
    assistant_turn_at_ms_present: bool,
    assistant_turn_at_ms_is_none: bool,
    model_variant_index_present: bool,
    model_variant_index_is_none: bool,
    tool_call_id_present: bool,
    tool_call_id: str | None,
    tool_calls_present: bool,
    index: int | None = None,
) -> None:
    prefix = _message_prefix(index)
    allowed_fields = _BASE_ALLOWED_FIELDS.union(_allowed_fields_for_role(role))
    for field_name in field_names:
        if field_name not in allowed_fields:
            raise ValidationError(f"{prefix} contains unsupported field '{field_name}'.")
    if role == "tool" and (not isinstance(tool_call_id, str) or not tool_call_id.strip()):
        raise ValidationError(f"{prefix} field 'tool_call_id' is required for tool messages.")
    if role != "tool" and tool_call_id_present:
        raise ValidationError(f"{prefix} field 'tool_call_id' is only allowed for tool messages.")
    if role != "assistant" and assistant_turn_at_ms_present:
        raise ValidationError(
            f"{prefix} field 'assistant_turn_at_ms' is only allowed for assistant messages.",
        )
    if role != "assistant" and model_variant_index_present:
        raise ValidationError(
            f"{prefix} field 'model_variant_index' is only allowed for assistant messages.",
        )
    if role != "assistant" and tool_calls_present:
        raise ValidationError(
            f"{prefix} field 'tool_calls' is only allowed for assistant messages.",
        )
    if role in {"system", "developer", "user", "tool"} and (not content_present or content_is_none):
        raise ValidationError(f"{prefix} field 'content' is required for this role.")
    if role != "assistant":
        return
    if not assistant_event_timeline_present:
        raise ValidationError(f"{prefix} missing required field 'assistant_event_timeline'.")
    if not assistant_turn_at_ms_present or assistant_turn_at_ms_is_none:
        raise ValidationError(
            f"{prefix} field 'assistant_turn_at_ms' is required for assistant messages.",
        )
    if not model_variant_index_present or model_variant_index_is_none:
        raise ValidationError(
            f"{prefix} field 'model_variant_index' is required for assistant messages.",
        )

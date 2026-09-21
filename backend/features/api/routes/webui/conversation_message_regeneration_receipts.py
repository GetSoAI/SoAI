"""SoAI - Conversation regeneration receipt serialization [backend/features/api/routes/webui/conversation_message_regeneration_receipts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict
from core.validation.integers import is_strict_int

__all__ = ("serialize_conversation_regeneration_attempt",)

_REGENERATION_STATES = frozenset(
    {
        "pending",
        "materializing",
        "running",
        "input_required",
        "completed",
        "failed",
        "cancelled",
        "effect_unknown",
    },
)


def serialize_conversation_regeneration_attempt(attempt: JSONDict) -> JSONDict:
    input_id = attempt.get("input_id")
    request_id = attempt.get("request_id")
    assistant_at_ms = attempt.get("assistant_at_ms")
    assistant_turn_at_ms = attempt.get("assistant_turn_at_ms")
    accepted_revision = attempt.get("regeneration_accepted_revision")
    accepted_at_ms = attempt.get("accepted_at_ms")
    state = attempt.get("state")
    is_dispatchable_head = attempt.get("is_dispatchable_head")
    has_assistant_replacement = attempt.get("has_assistant_replacement")
    regeneration_request = attempt.get("regeneration_request")
    text_fields_valid = all(
        isinstance(value, str) and bool(value.strip()) for value in (input_id, request_id)
    )
    boolean_fields_valid = all(
        isinstance(value, bool) for value in (is_dispatchable_head, has_assistant_replacement)
    )
    if (
        not text_fields_valid
        or not boolean_fields_valid
        or state not in _REGENERATION_STATES
        or not isinstance(regeneration_request, dict)
    ):
        raise ValidationError("Conversation regeneration receipt is invalid.")
    content_preview_feedback = regeneration_request.get("content_preview_feedback")
    preview_contract_feedback = regeneration_request.get("preview_contract_feedback")
    if not (
        (content_preview_feedback is None or isinstance(content_preview_feedback, dict))
        and (preview_contract_feedback is None or isinstance(preview_contract_feedback, dict))
    ):
        raise ValidationError("Conversation regeneration feedback receipt is invalid.")
    if (
        not is_strict_int(assistant_at_ms)
        or not is_strict_int(assistant_turn_at_ms)
        or not is_strict_int(accepted_revision)
        or not is_strict_int(accepted_at_ms)
    ):
        raise ValidationError("Conversation regeneration receipt is invalid.")
    receipt: JSONDict = {
        "input_id": input_id,
        "request_id": request_id,
        "assistant_at_ms": int(assistant_at_ms),
        "assistant_turn_at_ms": int(assistant_turn_at_ms),
        "accepted_at_ms": int(accepted_at_ms),
        "last_modified_at_ms": int(accepted_revision),
        "state": state,
        "is_dispatchable_head": is_dispatchable_head,
        "has_assistant_replacement": has_assistant_replacement,
        "content_preview_feedback": content_preview_feedback,
        "preview_contract_feedback": preview_contract_feedback,
    }
    terminal_code = attempt.get("terminal_code")
    terminal_args = attempt.get("terminal_args")
    if isinstance(terminal_code, str) and terminal_code.strip():
        receipt["terminal_code"] = terminal_code
    if isinstance(terminal_args, dict):
        receipt["terminal_args"] = dict(terminal_args)
    return receipt

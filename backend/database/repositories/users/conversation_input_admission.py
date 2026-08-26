"""SoAI - Conversation input admission normalization [backend/database/repositories/users/conversation_input_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.conversations.conversation_draft_content_validation import (
    CHAT_COMPOSER_TEXT_MAX_LENGTH,
)
from core.errors.exceptions import ValidationError
from core.serialization.json import serialize_json_compact_stable
from core.validation.strict_numbers import require_non_negative_int_strict
from core.validation.strings import (
    coerce_optional_trimmed_str,
    coerce_required_non_empty_str,
    require_bounded_trimmed_text,
)
from core.workspaces.soai_path_link_codec import extract_soai_path_tokens
from database.repositories.users.conversation_input_validation import (
    coerce_optional_request_id,
    now_ms,
    require_client_id,
    require_conversation_input_payload,
    require_input_type,
    require_source_key,
    require_transport_origin,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("ConversationInputAdmission", "normalize_conversation_input_admission")


@dataclass(frozen=True, slots=True)
class ConversationInputAdmission:
    input_id: str
    input_type: str
    transport_origin: str
    text: str
    prompt_history_text: str | None
    attachment_content: list[JSONValue]
    model_settings_json: str | None
    source_key: str
    client_id: str | None
    client_request_id: str | None
    messaging_ingress_id: str | None
    media_descriptors: list[JSONDict]
    accepted_at_ms: int
    expected_input_generation: int


def normalize_conversation_input_admission(
    *,
    conv_id: str,
    input_type: str,
    transport_origin: str,
    text: str | None,
    prompt_history_text: str | None,
    attachment_content: list[JSONValue],
    model_settings: JSONDict | None,
    expected_input_generation: int,
    client_id: str | None,
    client_request_id: str | None,
    messaging_ingress_id: str | None,
    media_descriptors: list[JSONDict] | None,
) -> ConversationInputAdmission:
    normalized_input_type = require_input_type(input_type)
    normalized_origin = require_transport_origin(transport_origin)
    normalized_media_descriptors = media_descriptors or []
    normalized_text, validated_attachments = require_conversation_input_payload(
        text,
        attachment_content,
        has_media_descriptors=bool(normalized_media_descriptors),
    )
    normalized_attachments: list[JSONValue] = list(validated_attachments)
    normalized_history_text = coerce_optional_trimmed_str(prompt_history_text)
    if prompt_history_text is not None and normalized_history_text is None:
        raise ValidationError("prompt_history_text must be non-empty when provided.")
    normalized_request_id = coerce_optional_request_id(client_request_id)
    normalized_client_id: str | None = None
    normalized_ingress_id: str | None = None
    if normalized_origin == "chat":
        if messaging_ingress_id is not None:
            raise ValidationError("Chat inputs cannot include messaging_ingress_id.")
        normalized_client_id = require_client_id(client_id or "")
        if normalized_request_id is None:
            raise ValidationError("Chat inputs require client_request_id.")
        source_key = require_source_key(
            f"{conv_id}:{normalized_client_id}:{normalized_request_id}",
        )
    else:
        if client_id is not None or normalized_request_id is not None:
            raise ValidationError("Messaging inputs cannot include Chat client identity.")
        normalized_ingress_id = coerce_required_non_empty_str(
            messaging_ingress_id,
            label="messaging_ingress_id",
        )
        source_key = require_source_key(normalized_ingress_id)
    if normalized_input_type == "prompt" and model_settings is None:
        raise ValidationError("Prompt inputs require model_settings.")
    if normalized_input_type != "prompt" and model_settings is not None:
        raise ValidationError("Only prompt inputs may include model_settings.")
    history_eligible = normalized_origin == "chat" and normalized_input_type in {"prompt", "steer"}
    if not history_eligible and prompt_history_text is not None:
        raise ValidationError("This input cannot include prompt_history_text.")
    if history_eligible and normalized_history_text is not None:
        normalized_history_text = require_bounded_trimmed_text(
            normalized_history_text,
            type_message="prompt_history_text must be a string.",
            empty_message="prompt_history_text must be non-empty.",
            max_length=CHAT_COMPOSER_TEXT_MAX_LENGTH,
            max_length_message="prompt_history_text exceeds the maximum length.",
        )
        if not normalized_text and not extract_soai_path_tokens(normalized_history_text):
            raise ValidationError(
                "Attachment-only inputs cannot include prompt_history_text.",
            )
    elif history_eligible and normalized_text:
        raise ValidationError("Textual Chat inputs require prompt_history_text.")
    return ConversationInputAdmission(
        input_id=f"cinput_{uuid.uuid4().hex[:16]}",
        input_type=normalized_input_type,
        transport_origin=normalized_origin,
        text=normalized_text or "",
        prompt_history_text=normalized_history_text,
        attachment_content=normalized_attachments,
        model_settings_json=(
            serialize_json_compact_stable(model_settings) if model_settings is not None else None
        ),
        source_key=source_key,
        client_id=normalized_client_id,
        client_request_id=normalized_request_id,
        messaging_ingress_id=normalized_ingress_id,
        media_descriptors=normalized_media_descriptors,
        accepted_at_ms=now_ms(),
        expected_input_generation=require_non_negative_int_strict(
            expected_input_generation,
            error_message="expected_input_generation must be a non-negative integer.",
        ),
    )

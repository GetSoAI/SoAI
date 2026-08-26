"""SoAI - Conversation input validation helpers [backend/database/repositories/users/conversation_input_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.timing.epoch import epoch_ms
from core.validation.attachment_content import require_attachment_content_list
from core.validation.strings import (
    coerce_optional_trimmed_str,
    coerce_required_non_empty_str,
    require_trimmed_text,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "coerce_optional_request_id",
    "now_ms",
    "require_client_id",
    "require_conversation_input_payload",
    "require_input_id",
    "require_input_type",
    "require_source_key",
    "require_transport_origin",
)


def now_ms() -> int:
    return epoch_ms()


def require_input_type(value: str) -> str:
    if not isinstance(value, str):
        raise ValidationError("input_type must be a string.")
    normalized = require_trimmed_text(value, "input_type must be a string.").lower()
    if normalized not in {"prompt", "steer", "control"}:
        raise ValidationError("input_type must be 'prompt', 'steer', or 'control'.")
    return normalized


def require_transport_origin(value: str) -> str:
    if not isinstance(value, str):
        raise ValidationError("transport_origin must be a string.")
    normalized = require_trimmed_text(value, "transport_origin must be a string.").lower()
    if normalized not in {"chat", "messaging"}:
        raise ValidationError("transport_origin must be 'chat' or 'messaging'.")
    return normalized


def require_conversation_input_payload(
    text: str | None,
    attachment_content: list[JSONValue],
    *,
    has_media_descriptors: bool = False,
) -> tuple[str | None, list[JSONDict]]:
    resolved_text = coerce_optional_trimmed_str(text)
    validated_attachments = require_attachment_content_list(attachment_content)
    if resolved_text is None and not attachment_content and not has_media_descriptors:
        raise ValidationError("Conversation input requires either text or attachment_content.")
    return resolved_text, validated_attachments


def require_client_id(client_id: str) -> str:
    normalized = coerce_required_non_empty_str(client_id, label="client_id")
    if len(normalized) > 128:
        raise ValidationError("client_id is too long.")
    return normalized


def coerce_optional_request_id(value: str | None) -> str | None:
    normalized = coerce_optional_trimmed_str(value)
    if normalized is None:
        return None
    if len(normalized) > 128:
        raise ValidationError("client_request_id is too long.")
    return normalized


def require_input_id(input_id: str) -> str:
    return coerce_required_non_empty_str(input_id, label="input_id")


def require_source_key(source_key: str) -> str:
    normalized = coerce_required_non_empty_str(source_key, label="source_key")
    if len(normalized) > 512:
        raise ValidationError("source_key is too long.")
    return normalized

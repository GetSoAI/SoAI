"""SoAI - Conversation input attachment semantic comparison [backend/database/repositories/users/conversation_input_attachment_semantics.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.serialization.json import serialize_json_compact_stable
from core.serialization.json_parsing import parse_json_value
from core.validation.attachment_content import require_attachment_content_fragment

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_expected_user_message_content",
    "decoded_message_content_fragments",
    "conversation_input_content_signature",
)


def _normalize_text(value: str) -> str:
    return value.strip()


def _require_fragment_dict(
    value: JSONValue,
    *,
    label: str,
    build_error: Callable[[str], Exception],
) -> JSONDict:
    return require_attachment_content_fragment(
        value,
        label=label,
        build_error=build_error,
        object_message=f"{label} must be a JSON dictionary.",
    )


def build_expected_user_message_content(
    prompt_text: str,
    attachment_content: list[JSONValue],
) -> list[JSONDict]:
    normalized_prompt_text = _normalize_text(prompt_text)
    expected: list[JSONDict] = []
    if normalized_prompt_text:
        expected.append({"type": "text", "text": normalized_prompt_text})
    for entry in attachment_content:
        expected.append(
            _require_fragment_dict(
                entry,
                label="conversation input attachment_content entry",
                build_error=StateError,
            ),
        )
    if not expected:
        raise StateError("Conversation input content is empty.")
    return expected


def _normalize_message_content_fragments(content: JSONValue) -> list[JSONDict]:
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        fragments: list[JSONDict] = []
        for entry in content:
            fragments.append(
                _require_fragment_dict(
                    entry,
                    label="message content fragment",
                    build_error=StateError,
                ),
            )
        return fragments
    raise StateError("Existing user message content must be a JSON array or string.")


def decoded_message_content_fragments(content_value: str) -> list[JSONDict]:
    try:
        decoded = parse_json_value(content_value)
    except ValidationError as exception:
        raise StateError("Existing user message content is invalid JSON.") from exception
    return _normalize_message_content_fragments(decoded)


def _semantic_fragment(fragment: JSONDict) -> JSONDict:
    part_type_value = fragment.get("type")
    part_type = part_type_value if isinstance(part_type_value, str) else ""
    if part_type == "soai_path":
        return {
            "type": "soai_path",
            "entry_type": fragment.get("entry_type"),
            "source_reference": fragment.get("source_reference"),
            "tool_reference": fragment.get("tool_reference"),
            "workspace_scope": fragment.get("workspace_scope"),
            "target_fingerprint": fragment.get("target_fingerprint"),
        }
    if part_type == "soai_knowledge":
        return {
            "type": "soai_knowledge",
            "knowledge_attachment_id": fragment.get("knowledge_attachment_id"),
            "summary_id": fragment.get("summary_id"),
            "source_type": fragment.get("source_type"),
            "operation_type": fragment.get("operation_type"),
            "created_at_ms": fragment.get("created_at_ms"),
        }
    normalized = dict(fragment)
    if part_type == "soai_file":
        normalized.pop("attachment_revision", None)
    return normalized


def conversation_input_content_signature(content: Sequence[JSONValue], *, label: str) -> str:
    fragments: list[JSONDict] = []
    for entry in content:
        fragments.append(
            _require_fragment_dict(
                entry,
                label=label,
                build_error=StateError,
            ),
        )
    semantic_fragments = [_semantic_fragment(fragment) for fragment in fragments]
    return serialize_json_compact_stable(semantic_fragments)

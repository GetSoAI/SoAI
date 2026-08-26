"""SoAI - OpenAI Responses input_items builder for persistence [backend/features/api/routes/openai/responses/input_items_builder.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.runtime.soai_identifiers import create_prefixed_hex_id
from core.validation.record_fields import require_json_object_list

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("build_response_input_items",)


def build_response_input_items(input_value: JSONValue) -> tuple[JSONDict, ...]:
    if isinstance(input_value, str):
        text = input_value.strip()
        return (
            {
                "id": create_prefixed_hex_id("msg"),
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": text}],
            },
        )
    if not isinstance(input_value, list):
        return ()
    normalized: list[JSONDict] = []
    for item_dict in require_json_object_list(
        input_value,
        label="input",
        build_error=ValidationError,
        invalid_message="input must contain only objects.",
        entry_message="input must contain only objects.",
    ):
        copied = dict(item_dict)
        item_id_value = copied.get("id")
        if not (isinstance(item_id_value, str) and item_id_value.strip()):
            copied["id"] = create_prefixed_hex_id("item")
        normalized.append(copied)
    return tuple(normalized)

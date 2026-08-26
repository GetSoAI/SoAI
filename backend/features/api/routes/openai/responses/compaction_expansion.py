"""SoAI - OpenAI Responses compaction item expansion helpers [backend/features/api/routes/openai/responses/compaction_expansion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.types.json_value import coerce_json_dict
from core.validation.record_fields import require_json_object_list

if TYPE_CHECKING:
    from core.openai.protocols_database_responses import DatabaseOpenAIResponsesProtocol
    from core.types.json import JSONValue

__all__ = ("expand_responses_compaction_items",)


def expand_responses_compaction_items(
    *,
    database_openai_responses: DatabaseOpenAIResponsesProtocol,
    input_value: JSONValue,
) -> JSONValue:
    if not isinstance(input_value, list):
        return input_value
    expanded: list[JSONValue] = []
    for item in input_value:
        item_dict = coerce_json_dict(item)
        if item_dict is None:
            expanded.append(item)
            continue
        item_type_value = item_dict.get("type")
        item_type = item_type_value.strip().lower() if isinstance(item_type_value, str) else ""
        if item_type != "compaction":
            expanded.append(item_dict)
            continue
        encrypted_value = item_dict.get("encrypted_content")
        encrypted_content = encrypted_value.strip() if isinstance(encrypted_value, str) else ""
        if not encrypted_content:
            raise ValidationError("Compaction item missing encrypted_content.")
        decoded = database_openai_responses.decrypt_compaction_content(
            encrypted_content=encrypted_content,
        )
        if decoded.get("format") != "soai.openai.responses.compaction.v1":
            raise ValidationError("Unsupported compaction payload format.")
        items_value = decoded.get("items")
        expanded.extend(
            require_json_object_list(
                items_value,
                label="compaction payload items",
                build_error=ValidationError,
                invalid_message="Invalid compaction payload items.",
                entry_message="Invalid compaction payload items.",
            ),
        )
    return expanded

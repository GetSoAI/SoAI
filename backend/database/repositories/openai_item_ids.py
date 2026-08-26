"""SoAI - Shared OpenAI item ID normalization helpers [backend/database/repositories/openai_item_ids.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.runtime.soai_identifiers import create_prefixed_hex_id

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "ensure_item_id",
    "ensure_item_ids",
)


def ensure_item_id(item: JSONDict) -> JSONDict:
    item_id = item.get("id")
    if isinstance(item_id, str) and item_id.strip():
        return item
    copied = dict(item)
    copied["id"] = create_prefixed_hex_id("item")
    return copied


def ensure_item_ids(items: Sequence[JSONDict]) -> list[JSONDict]:
    normalized: list[JSONDict] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValidationError("Input item must be an object.")
        normalized.append(ensure_item_id(item))
    return normalized

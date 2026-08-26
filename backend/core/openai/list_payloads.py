"""SoAI - OpenAI list payload builders [backend/core/openai/list_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("OpenAIListPayload", "build_openai_list_payload")


class OpenAIListPayload(TypedDict):
    object: str
    data: list[JSONDict]
    first_id: str
    last_id: str
    has_more: bool


def _list_item_id(item: JSONDict) -> str:
    item_id = item.get("id")
    return item_id if isinstance(item_id, str) else ""


def build_openai_list_payload(*, data: list[JSONDict], has_more: bool) -> OpenAIListPayload:
    first_id = _list_item_id(data[0]) if data else ""
    last_id = _list_item_id(data[-1]) if data else ""
    return {
        "object": "list",
        "data": data,
        "first_id": first_id,
        "last_id": last_id,
        "has_more": bool(has_more),
    }

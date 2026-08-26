"""SoAI - Shared account listing helpers [backend/features/external_accounts/listing_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.numeric import coerce_positive_int

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "paginate_json_items",
    "resolve_direction",
    "resolve_limit",
    "resolve_order",
)


def resolve_limit(
    config: ConfigProtocol,
    raw_limit: JSONValue,
    default_key: str,
    max_key: str,
) -> int:
    default_limit = int(config.get_int(default_key))
    max_limit = int(config.get_int(max_key))
    return coerce_positive_int(raw_limit, default=default_limit, minimum=1, maximum=max_limit)


def resolve_order(value: JSONValue, allowed: tuple[str, ...], default_value: str) -> str:
    if not isinstance(value, str):
        return default_value
    normalized = value.strip()
    if normalized not in allowed:
        return default_value
    return normalized


def resolve_direction(value: JSONValue, *, default_value: str) -> str:
    if not isinstance(value, str):
        return default_value
    normalized = value.strip().lower()
    if normalized not in {"asc", "desc"}:
        return default_value
    return normalized


def paginate_json_items(
    *,
    items: list[JSONDict],
    cursor: str | None,
    limit: int,
    order_by: str,
    order_direction: str,
    supported_sort_fields: tuple[str, ...],
) -> JSONDict:
    start_index = _coerce_cursor(cursor)
    safe_limit = max(1, limit)
    page_items = items[start_index : start_index + safe_limit]
    next_cursor = None
    if (start_index + safe_limit) < len(items):
        next_cursor = str(start_index + safe_limit)
    return {
        "items": page_items,
        "count": len(page_items),
        "next_cursor": next_cursor,
        "order_by": order_by,
        "order_direction": order_direction,
        "supported_sort_fields": list(supported_sort_fields),
    }


def _coerce_cursor(cursor: str | None) -> int:
    if cursor is None:
        return 0
    normalized = cursor.strip()
    if not normalized or not normalized.isdigit():
        return 0
    return max(int(normalized), 0)

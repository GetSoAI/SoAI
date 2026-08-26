"""SoAI - WebSocket command payload normalization [backend/features/api/routes/system/events/websocket_command_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.types.json_value import coerce_json_dict

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "resolve_body_or_root_dict",
    "resolve_body_or_root_value",
)


def resolve_body_or_root_dict(data: JSONDict) -> JSONDict:
    body = coerce_json_dict(data.get("body"))
    return data if body is None else body


def resolve_body_or_root_value(data: JSONDict, field_name: str) -> JSONValue:
    if field_name in data:
        return data[field_name]
    body = resolve_body_or_root_dict(data)
    if body is data:
        return None
    return body.get(field_name)

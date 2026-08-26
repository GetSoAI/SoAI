"""SoAI - WebSocket snapshot handlers for OpenAI API key quota status [backend/features/api/routes/system/events/snapshots/handlers_openai_api_keys.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import WebSocket

from core.auth.api_keys import list_openai_api_keys
from features.api.routes.webui.key_quota_status_listing import list_quota_status_payload
from features.api.streaming.websocket import WebsocketConnection

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("snapshot_openai_api_key_quota_status", "snapshot_openai_api_key_usage")


async def snapshot_openai_api_key_quota_status(
    _data: JSONDict,
    connection: WebsocketConnection,
    _websocket: WebSocket,
) -> JSONValue:
    database_api_keys = connection.api_context.dependencies.webui_manager.database_api_keys
    return {"keys": await list_quota_status_payload(database_api_keys)}


async def snapshot_openai_api_key_usage(
    _data: JSONDict,
    connection: WebsocketConnection,
    _websocket: WebSocket,
) -> JSONValue:
    database_api_keys = connection.api_context.dependencies.webui_manager.database_api_keys
    records = await list_openai_api_keys(database_api_keys, include_revoked=True)
    keys: list[JSONDict] = []
    for record in records:
        keys.append(
            {
                "key_id": record.get("key_id"),
                "label": record.get("label"),
                "prefix": record.get("prefix"),
                "revoked": record.get("revoked"),
                "expires_at_ms": record.get("expires_at_ms"),
                "last_used_at_ms": record.get("last_used_at_ms"),
                "request_count": record.get("request_count"),
                "rate_limited_count": record.get("rate_limited_count"),
            },
        )
    return {"keys": keys}

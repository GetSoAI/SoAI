"""SoAI - Owner-scoped memory and preset snapshots [backend/features/api/routes/system/events/snapshots/handlers_chat_libraries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import WebSocket

from core.types.json import JSONDict, JSONValue
from core.types.json_value import filter_json_mapping_strict
from core.users.user_id import require_strict_user_id
from features.api.routes.system.events.snapshots.payload_validation import (
    require_supported_snapshot_payload_keys,
)
from features.api.streaming.websocket import WebsocketConnection

__all__ = ("snapshot_chat_presets", "snapshot_memory_library")


async def snapshot_memory_library(
    payload: JSONDict, connection: WebsocketConnection, websocket: WebSocket
) -> JSONValue:
    _ = websocket
    require_supported_snapshot_payload_keys(payload, allowed_keys=set())
    return await connection.api_context.dependencies.database_memory.read_library(
        require_strict_user_id(connection.user.get("id"))
    )


async def snapshot_chat_presets(
    payload: JSONDict, connection: WebsocketConnection, websocket: WebSocket
) -> JSONValue:
    _ = websocket
    require_supported_snapshot_payload_keys(payload, allowed_keys=set())
    user_id = require_strict_user_id(connection.user.get("id"))
    result = await connection.api_context.dependencies.database_chat_presets.list_chat_presets(
        user_id
    )
    connection.chat_preset_integrity_diagnostics.log(
        user_id=user_id,
        invalid_count=result["structurally_invalid_count"],
        trace_id=connection.trace_id,
    )
    return filter_json_mapping_strict(
        result, error_message="Stored chat preset projection is not JSON-compatible."
    )

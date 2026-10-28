"""SoAI - Owner scoped skill library and conversation snapshots [backend/features/api/routes/system/events/snapshots/handlers_skills.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import WebSocket

from core.types.json import JSONDict, JSONValue
from core.users.user_id import require_strict_user_id
from core.validation.strings import coerce_required_non_empty_str
from features.api.routes.system.events.snapshots.payload_validation import (
    require_supported_snapshot_payload_keys,
)
from features.api.streaming.websocket import WebsocketConnection

__all__ = ("snapshot_skill_library", "snapshot_conversation_skills")


async def snapshot_skill_library(
    payload: JSONDict,
    connection: WebsocketConnection,
    websocket: WebSocket,
) -> JSONValue:
    _ = websocket
    require_supported_snapshot_payload_keys(payload, allowed_keys=set())
    return await connection.api_context.dependencies.database_skills.library(
        require_strict_user_id(connection.user.get("id"))
    )


async def snapshot_conversation_skills(
    payload: JSONDict,
    connection: WebsocketConnection,
    websocket: WebSocket,
) -> JSONValue:
    _ = websocket
    require_supported_snapshot_payload_keys(payload, allowed_keys={"conv_id"})
    conv_id = coerce_required_non_empty_str(payload.get("conv_id"), label="conv_id")
    return await connection.api_context.dependencies.database_skills.selection(
        require_strict_user_id(connection.user.get("id")), conv_id
    )

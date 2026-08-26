"""SoAI - Snapshot handlers for model-related resources [backend/features/api/routes/system/events/snapshots/handlers_models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import WebSocket

from core.errors.exceptions import ValidationError
from core.models.universal_id import is_universal_id
from features.api.streaming.websocket import WebsocketConnection

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("snapshot_model_parameters",)


async def snapshot_model_parameters(
    data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    universal_id = data.get("universal_id")
    if not isinstance(universal_id, str) or not universal_id.strip():
        raise ValidationError("models.parameters snapshot requires a universal_id")
    normalized = universal_id.strip()
    if not is_universal_id(normalized):
        raise ValidationError("models.parameters snapshot requires a SoAI universal_id")
    return await connection.api_context.dependencies.model_information_service.model_get_formatted_parameters(
        normalized,
    )

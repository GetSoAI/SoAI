"""SoAI - WebSocket snapshot handlers for OpenAI model catalog [backend/features/api/routes/system/events/snapshots/handlers_openai_models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import WebSocket

from core.openai.model_capability_catalog import build_model_capability_catalog_response
from features.api.streaming.websocket import WebsocketConnection

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("snapshot_openai_models",)


async def snapshot_openai_models(
    _data: JSONDict,
    connection: WebsocketConnection,
    _websocket: WebSocket,
) -> JSONValue:
    raw = (
        await connection.api_context.dependencies.model_information_service.model_get_openai_formatted_list()
    )
    return build_model_capability_catalog_response(raw)

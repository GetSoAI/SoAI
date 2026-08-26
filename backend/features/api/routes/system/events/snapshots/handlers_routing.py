"""SoAI - Snapshot handlers for routing configuration resources [backend/features/api/routes/system/events/snapshots/handlers_routing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import WebSocket

from core.errors.exceptions import StateError
from core.types.json_value import coerce_json_dict
from features.api.routes.routing.routing_snapshot import fetch_routing_config_snapshot
from features.api.streaming.websocket import WebsocketConnection

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "snapshot_routing_config",
    "snapshot_routing_virtual_models",
)


async def snapshot_routing_config(
    _data: JSONDict,
    connection: WebsocketConnection,
    ws: WebSocket,
) -> JSONValue:
    try:
        context = ws.state.context
    except AttributeError:
        context = None
    snapshot = await fetch_routing_config_snapshot(
        event_bus=connection.api_context.dependencies.event_bus,
        context=context,
    )
    return snapshot


async def snapshot_routing_virtual_models(
    _data: JSONDict,
    connection: WebsocketConnection,
    ws: WebSocket,
) -> JSONValue:
    try:
        context = ws.state.context
    except AttributeError:
        context = None
    snapshot = await fetch_routing_config_snapshot(
        event_bus=connection.api_context.dependencies.event_bus,
        context=context,
    )
    virtual_models_value = snapshot.get("virtual_models")
    if not isinstance(virtual_models_value, list):
        raise StateError(
            "routing.virtualModels snapshot missing virtual_models list.",
            operation="api_system.websocket.snapshot.routing.virtualModels",
        )
    virtual_models: list[JSONDict] = []
    for entry in virtual_models_value:
        virtual_model = coerce_json_dict(entry)
        if virtual_model is None:
            raise TypeError(
                "routing.virtualModels snapshot virtual_models entry must be an object.",
            )
        virtual_models.append(virtual_model)
    return virtual_models

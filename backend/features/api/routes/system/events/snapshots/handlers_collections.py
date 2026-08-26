"""SoAI - Snapshot handlers for collection-style resources [backend/features/api/routes/system/events/snapshots/handlers_collections.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.integers import is_strict_int
from features.api.runtime.context import get_openai_capability_taxonomy
from features.api.runtime.prompt_templates import list_prompts

if TYPE_CHECKING:
    from fastapi import WebSocket

    from core.types.json import JSONDict, JSONValue
    from features.api.streaming.websocket import WebsocketConnection

__all__ = (
    "snapshot_models_collection",
    "snapshot_plugins_capabilities_manifest",
    "snapshot_plugins_collection",
    "snapshot_prompts_collection",
    "snapshot_system_metrics",
    "snapshot_tasks_cancellations",
)


async def snapshot_prompts_collection(
    payload: JSONDict,
    connection: WebsocketConnection,
    websocket: WebSocket,
) -> JSONValue:
    _ = payload
    _ = websocket
    user_id_value = connection.user.get("id")
    if not is_strict_int(user_id_value):
        raise ValidationError("Invalid user id for prompt snapshot.")
    user_id = user_id_value
    webui_mgr = connection.api_context.dependencies.webui_manager
    async with connection.api_context.dependencies.prompts_update_locks[user_id]:
        return await list_prompts(webui_mgr.database_prompts, user_id)


async def snapshot_models_collection(
    payload: JSONDict,
    connection: WebsocketConnection,
    websocket: WebSocket,
) -> JSONValue:
    _ = payload
    _ = websocket
    return (
        await connection.api_context.dependencies.model_information_service.model_get_formatted_list()
    )


async def snapshot_plugins_collection(
    payload: JSONDict,
    connection: WebsocketConnection,
    websocket: WebSocket,
) -> JSONValue:
    _ = payload
    _ = websocket
    return await connection.api_context.dependencies.plugin_manager.list_plugins()


async def snapshot_plugins_capabilities_manifest(
    payload: JSONDict,
    connection: WebsocketConnection,
    websocket: WebSocket,
) -> JSONValue:
    _ = payload
    _ = connection
    _ = websocket
    return get_openai_capability_taxonomy()


async def snapshot_system_metrics(
    payload: JSONDict,
    connection: WebsocketConnection,
    websocket: WebSocket,
) -> JSONValue:
    _ = payload
    _ = websocket
    return await connection.api_context.dependencies.metrics_manager.get_all_metrics()


async def snapshot_tasks_cancellations(
    payload: JSONDict,
    connection: WebsocketConnection,
    websocket: WebSocket,
) -> JSONValue:
    _ = payload
    _ = websocket
    return await connection.api_context.dependencies.cancellation_coordinator.get_snapshot()

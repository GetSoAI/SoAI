"""SoAI - Snapshot handlers for system metadata resources [backend/features/api/routes/system/events/snapshots/handlers_system.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from fastapi import WebSocket

from core.errors.exceptions import StateError, ValidationError
from core.types.json import JSONDict
from core.validation.coercion import coerce_int_from_numberish
from features.api.routes.system.system_status_routes import (
    collect_system_status_snapshot,
)
from features.api.runtime.system_about import load_system_info_payload
from features.api.streaming.websocket import WebsocketConnection

__all__ = (
    "snapshot_system_health",
    "snapshot_system_info",
    "snapshot_system_logs_core",
    "snapshot_system_status",
)


async def snapshot_system_health(
    _data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> dict[str, str]:
    return {
        "status": "ok",
        "power_operations": (
            "healthy"
            if connection.api_context.dependencies.power_operation_supervisor.is_ready
            else "degraded"
        ),
    }


async def snapshot_system_info(
    _data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> dict[str, str]:
    return await asyncio.to_thread(
        load_system_info_payload,
        base_dir=connection.api_context.dependencies.base_dir,
        system_data_path=connection.api_context.dependencies.config.get_str(
            "SYSTEM.PATHS.SYSTEM_DATA",
        ),
    )


async def snapshot_system_status(
    _data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONDict:
    return await collect_system_status_snapshot(
        connection.api_context,
        _ws.url.scheme,
        include_security=False,
    )


async def snapshot_system_logs_core(
    data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONDict:
    log_manager = connection.api_context.dependencies.log_manager
    if log_manager is None:
        raise StateError("Logging service is unavailable.")
    source_raw = data.get("source")
    source = source_raw if isinstance(source_raw, str) and source_raw.strip() else "core"
    limit_raw = data.get("limit")
    limit_coerced = coerce_int_from_numberish(limit_raw) if limit_raw is not None else 200
    if limit_coerced is None:
        limit_coerced = 200
    limit = max(1, min(10000, limit_coerced))
    try:
        entries = await asyncio.to_thread(log_manager.get_recent_logs, source, limit)
    except (ValidationError, ValueError) as error:
        raise ValidationError(str(error)) from error
    return {"entries": entries, "source": source, "limit": limit}

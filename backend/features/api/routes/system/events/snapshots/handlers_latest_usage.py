"""SoAI - Latest model and plugin usage snapshot handlers [backend/features/api/routes/system/events/snapshots/handlers_latest_usage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.validation.epoch import EPOCH_MS_MIN
from core.validation.integers import is_strict_int
from features.api.routes.system.events.snapshots.payload_validation import (
    require_supported_snapshot_payload_keys,
)

if TYPE_CHECKING:
    from fastapi import WebSocket

    from core.types.json import JSONDict, JSONValue
    from features.api.streaming.websocket import WebsocketConnection

__all__ = ("snapshot_models_last_used", "snapshot_plugins_last_used")


def _build_latest_usage_snapshot(
    record: JSONDict | None,
    identity_field: str,
) -> JSONDict:
    if record is None:
        return {identity_field: None, "last_used_at_ms": None, "revision": 0}
    identity = record.get(identity_field)
    timestamp = record.get("last_used_at_ms")
    revision = record.get("revision")
    if not isinstance(identity, str) or not identity.strip():
        raise StateError(
            "Latest usage database record violates its snapshot contract.",
            operation="api_system.websocket.latest_usage_snapshot",
            details={"identity_field": identity_field},
        )
    if not is_strict_int(timestamp) or timestamp < EPOCH_MS_MIN:
        raise StateError(
            "Latest usage database record violates its snapshot contract.",
            operation="api_system.websocket.latest_usage_snapshot",
            details={"identity_field": identity_field},
        )
    if not is_strict_int(revision) or revision <= 0:
        raise StateError(
            "Latest usage database record violates its snapshot contract.",
            operation="api_system.websocket.latest_usage_snapshot",
            details={"identity_field": identity_field},
        )
    return {
        identity_field: identity,
        "last_used_at_ms": timestamp,
        "revision": revision,
    }


async def snapshot_models_last_used(
    payload: JSONDict,
    connection: WebsocketConnection,
    websocket: WebSocket,
) -> JSONValue:
    require_supported_snapshot_payload_keys(payload, allowed_keys=set())
    _ = websocket
    record = await connection.api_context.dependencies.database_models.get_latest_model_usage()
    return _build_latest_usage_snapshot(record, "universal_id")


async def snapshot_plugins_last_used(
    payload: JSONDict,
    connection: WebsocketConnection,
    websocket: WebSocket,
) -> JSONValue:
    require_supported_snapshot_payload_keys(payload, allowed_keys=set())
    _ = websocket
    record = await connection.api_context.dependencies.database_plugins.get_latest_plugin_usage()
    return _build_latest_usage_snapshot(record, "plugin_name")

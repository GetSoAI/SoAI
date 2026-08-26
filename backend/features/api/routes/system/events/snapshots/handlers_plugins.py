"""SoAI - Snapshot handlers for plugin and provider resources [backend/features/api/routes/system/events/snapshots/handlers_plugins.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import WebSocket

from core.errors.exceptions import ValidationError
from core.models.external_provider_public_projection import coerce_external_provider_record
from core.serialization.json import normalize_for_json
from core.types.json_value import coerce_json_dict
from features.api.routes.system.events.snapshots.payload_validation import (
    require_supported_snapshot_payload_keys,
)
from features.api.streaming.websocket import WebsocketConnection

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("snapshot_providers_collection",)


async def snapshot_providers_collection(
    data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    require_supported_snapshot_payload_keys(data, allowed_keys={"plugin_name"})
    plugin_name = data.get("plugin_name")
    if not isinstance(plugin_name, str) or not plugin_name.strip():
        raise ValidationError("providers.collection snapshot requires a plugin_name")
    plugin_name = plugin_name.strip()
    api_context = connection.api_context
    plugin_manager = api_context.dependencies.plugin_manager
    await plugin_manager.require_ready()
    canonical_plugin_name = plugin_manager.normalize_plugin_name(plugin_name)
    if canonical_plugin_name is None:
        raise ValidationError(f"Plugin '{plugin_name}' not found.")
    await plugin_manager.ensure_plugin_compatible(canonical_plugin_name)
    await plugin_manager.ensure_plugin_capability(
        canonical_plugin_name,
        "SUPPORTS_EXTERNAL_PROVIDERS",
        "External Providers",
    )
    providers = await api_context.dependencies.model_provider_coordinator.provider_list_for_plugin(
        canonical_plugin_name,
    )
    records: list[JSONValue] = []
    for provider in providers:
        normalized = coerce_json_dict(normalize_for_json(provider))
        if normalized is None:
            raise ValidationError("External provider record is invalid.")
        records.append(
            normalize_for_json(
                coerce_external_provider_record(
                    normalized,
                    label="External provider record",
                ),
            )
        )
    return records

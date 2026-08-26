"""SoAI - Authoritative plugin state event encoding [backend/core/events/authoritative_state_encoding.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import NotRequired, TypedDict

from core.events.types_plugins import (
    PluginInstallationStateChangedEvent,
    PluginRuntimeStateChangedEvent,
)
from core.serialization.json import serialize_json_compact_stable
from core.types.json import JSONDict
from core.types.json_value import filter_json_mapping_strict

__all__ = ("encode_authoritative_plugin_state_event",)


class _AuthoritativePluginStateFields(TypedDict):
    event_id: str
    timestamp: float
    trace_id: str | None
    plugin_name: str
    previous_state: str
    new_state: str
    reason: str
    authority: str
    details: NotRequired[JSONDict]


def encode_authoritative_plugin_state_event(
    event: PluginInstallationStateChangedEvent | PluginRuntimeStateChangedEvent,
) -> str:
    payload: _AuthoritativePluginStateFields = {
        "event_id": event.event_id,
        "timestamp": float(event.timestamp),
        "trace_id": event.trace_id,
        "plugin_name": event.plugin_name,
        "previous_state": event.previous_state,
        "new_state": event.new_state,
        "reason": event.reason,
        "authority": event.authority,
    }
    if isinstance(event, PluginRuntimeStateChangedEvent):
        payload["details"] = dict(event.details)
    return serialize_json_compact_stable(
        filter_json_mapping_strict(
            payload,
            error_message="Authoritative plugin state event must be JSON-compatible.",
        ),
    )

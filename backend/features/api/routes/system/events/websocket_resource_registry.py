"""SoAI - WebSocket live resource event and permission registry [backend/features/api/routes/system/events/websocket_resource_registry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.events.types_base import Event
from core.events.types_models_model_events import ModelLastUsedChangedEvent
from core.events.types_plugins import PluginLastUsedChangedEvent
from core.events.types_system import (
    ChatStreamActivityChangedEvent,
    ChatStreamEvent,
    ChatStreamStatusPreviewEvent,
    HardwareSnapshotUpdatedEvent,
    MetricsUpdatedEvent,
    PowerOperationChangedEvent,
    ProcessListUpdatedEvent,
    ToolCallLiveUpdatedEvent,
)
from core.state.access import AccessAction
from features.api.routes.system.events.agent_event_types import (
    REALTIME_AGENT_EVENT_TYPES,
)
from features.api.routes.system.events.permissions import SNAPSHOT_PERMISSION_RULES

__all__ = (
    "is_websocket_resource_interest_event_type",
    "is_websocket_chat_presentation_event_type",
    "resolve_websocket_resource_action",
    "resolve_websocket_resource_event_types",
)

RESOURCE_SYSTEM_METRICS = "system.metrics"
RESOURCE_HARDWARE_SNAPSHOT = "hardware.snapshot"
RESOURCE_HARDWARE_PROCESSES = "hardware.processes"
RESOURCE_POWER_OPERATIONS = "system.power.operations"
RESOURCE_WEBUI_CHAT_ACTIVITY = "webui.chat.activity"
RESOURCE_WEBUI_CHAT_PRESENTATION = "webui.chat.presentation"
RESOURCE_MODELS_LAST_USED = "models.last_used"
RESOURCE_PLUGINS_LAST_USED = "plugins.last_used"


def is_websocket_chat_presentation_event_type(event_type: type[Event]) -> bool:
    event_types = resolve_websocket_resource_event_types(RESOURCE_WEBUI_CHAT_PRESENTATION)
    return event_types is not None and event_type in event_types


def is_websocket_resource_interest_event_type(event_type: type[Event]) -> bool:
    for resource in (
        RESOURCE_SYSTEM_METRICS,
        RESOURCE_HARDWARE_SNAPSHOT,
        RESOURCE_HARDWARE_PROCESSES,
        RESOURCE_POWER_OPERATIONS,
        RESOURCE_WEBUI_CHAT_ACTIVITY,
        RESOURCE_WEBUI_CHAT_PRESENTATION,
        RESOURCE_MODELS_LAST_USED,
        RESOURCE_PLUGINS_LAST_USED,
    ):
        resource_event_types = resolve_websocket_resource_event_types(resource)
        if resource_event_types is not None and event_type in resource_event_types:
            return True
    return False


def resolve_websocket_resource_event_types(
    resource: str,
) -> set[type[Event]] | None:
    if resource == RESOURCE_SYSTEM_METRICS:
        return {MetricsUpdatedEvent}
    if resource == RESOURCE_HARDWARE_SNAPSHOT:
        return {HardwareSnapshotUpdatedEvent}
    if resource == RESOURCE_HARDWARE_PROCESSES:
        return {ProcessListUpdatedEvent}
    if resource == RESOURCE_POWER_OPERATIONS:
        return {PowerOperationChangedEvent}
    if resource == RESOURCE_WEBUI_CHAT_ACTIVITY:
        return {ChatStreamActivityChangedEvent}
    if resource == RESOURCE_WEBUI_CHAT_PRESENTATION:
        return {
            ChatStreamEvent,
            ChatStreamStatusPreviewEvent,
            ToolCallLiveUpdatedEvent,
            *REALTIME_AGENT_EVENT_TYPES,
        }
    if resource == RESOURCE_MODELS_LAST_USED:
        return {ModelLastUsedChangedEvent}
    if resource == RESOURCE_PLUGINS_LAST_USED:
        return {PluginLastUsedChangedEvent}
    return None


def resolve_websocket_resource_action(resource: str) -> AccessAction | None:
    if resource == RESOURCE_WEBUI_CHAT_PRESENTATION:
        return AccessAction.AUTH_COOKIE
    for rule_resource, action in SNAPSHOT_PERMISSION_RULES:
        if rule_resource == resource:
            return action
    return None

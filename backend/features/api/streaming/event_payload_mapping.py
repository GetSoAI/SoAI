"""SoAI - Mapping internal events to transport payloads [backend/features/api/streaming/event_payload_mapping.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import dataclasses
from dataclasses import is_dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.events.types_base import Event
from core.events.types_conversation import ConversationUpdatedEvent, MessageSavedEvent
from core.events.types_file_explorer import FileSystemChangedEvent
from core.events.types_models_model_events import (
    LoadFailedEvent,
    ModelDatabaseChangeEvent,
    ModelLoadedEvent,
    ModelParametersRequireReloadEvent,
)
from core.events.types_models_streaming import StreamChunkEvent
from core.events.types_system import (
    HardwareSnapshotUpdatedEvent,
    MetricsUpdatedEvent,
    ProcessListUpdatedEvent,
    SoAIBenchRunUpdatedEvent,
    SoAIMainStateChangedEvent,
)
from core.timing.epoch import epoch_ms

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("event_to_transport_payload",)


def event_to_transport_payload(event: Event | JSONDict) -> JSONDict:
    if isinstance(event, dict):
        data = dict(event)
        data.pop("reply_channel", None)
        data.pop("context", None)
        event_type = data.pop("type", "DictEvent")
        return {"type": event_type, **data}
    if not is_dataclass(event) or isinstance(event, type):
        raise StateError(
            f"Failed to serialize event to dictionary: event is not a dataclass ({type(event).__name__}).",
            operation="api_streaming.serialize_event_to_transport_payload",
            details={"event_type": type(event).__name__, "event": str(event)},
        )
    try:
        data = dataclasses.asdict(event)
    except (AttributeError, TypeError) as exception:
        raise StateError(
            f"Failed to serialize event to dictionary: {exception}. Event type: {type(event).__name__}",
            operation="api_streaming.serialize_event_to_transport_payload",
            details={"event_type": type(event).__name__, "event": str(event)},
            cause=exception,
        ) from exception
    data.pop("reply_channel", None)
    data.pop("context", None)
    if isinstance(
        event,
        ModelLoadedEvent | LoadFailedEvent | ModelParametersRequireReloadEvent,
    ):
        if "universal_id" in data and "uid" not in data:
            data["uid"] = data.pop("universal_id")
    if isinstance(event, ModelDatabaseChangeEvent):
        if "added_universal_ids" in data:
            data["added_uids"] = data.pop("added_universal_ids")
        if "removed_universal_ids" in data:
            data["removed_uids"] = data.pop("removed_universal_ids")
    if isinstance(event, StreamChunkEvent):
        chunk = data.get("chunk")
        if isinstance(chunk, bytes | bytearray):
            try:
                data["chunk"] = bytes(chunk).decode("utf-8")
            except (TypeError, AttributeError, UnicodeDecodeError):
                data["chunk"] = ""
        elif isinstance(chunk, memoryview):
            try:
                data["chunk"] = chunk.tobytes().decode("utf-8")
            except (TypeError, AttributeError, UnicodeDecodeError):
                data["chunk"] = ""
    if isinstance(event, SoAIMainStateChangedEvent):
        data["new_state"] = event.new_state.value
        data["previous_state"] = event.previous_state.value
    if isinstance(event, SoAIBenchRunUpdatedEvent):
        data.pop("delivery", None)
        data["update_type"] = event.update_type
        data["update_seq"] = event.update_seq
        data["run"] = event.run
    if isinstance(
        event,
        HardwareSnapshotUpdatedEvent | MetricsUpdatedEvent | ProcessListUpdatedEvent,
    ):
        data["timestamp_ms"] = _resolve_telemetry_timestamp_ms(data)
    if isinstance(event, FileSystemChangedEvent):
        data["operation"] = event.operation.value
        data.pop("workspace_root_path", None)
    if isinstance(event, ConversationUpdatedEvent):
        for optional_field in ("title", "is_favorite", "model_settings", "is_archived"):
            if data.get(optional_field) is None:
                data.pop(optional_field, None)
        color_present = data.pop("color_present", False)
        if not color_present:
            data.pop("color", None)
    if isinstance(event, MessageSavedEvent) and data.get("message") is None:
        data.pop("message", None)
    return {"type": type(event).__name__, **data}


def _resolve_telemetry_timestamp_ms(data: JSONDict) -> int:
    snapshot = data.get("snapshot")
    timestamp_value = snapshot.get("timestamp_ms") if isinstance(snapshot, dict) else None
    if isinstance(timestamp_value, int) and not isinstance(timestamp_value, bool):
        return int(timestamp_value)
    return int(epoch_ms())

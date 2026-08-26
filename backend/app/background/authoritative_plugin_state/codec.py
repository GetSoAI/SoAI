"""SoAI - Authoritative plugin state outbox event encoding/decoding [backend/app/background/authoritative_plugin_state/codec.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.background.outbox_payload_parsing import (
    require_positive_outbox_timestamp_seconds,
)
from core.errors.exceptions import ValidationError
from core.events.types_plugins import (
    PluginInstallationStateChangedEvent,
    PluginRuntimeStateChangedEvent,
)
from core.serialization.json_parsing import parse_json_dict_with_messages
from core.state.state_names import resolve_plugin_runtime_state_name
from core.validation.record_fields import require_optional_str
from core.validation.strings import coerce_required_non_empty_str

if TYPE_CHECKING:
    from core.events.types_plugins import AuthoritativeStateChangeEvent

__all__ = ("decode_authoritative_plugin_state_event",)


def decode_authoritative_plugin_state_event(
    *,
    event_type: str,
    payload_json: str,
) -> AuthoritativeStateChangeEvent:
    decoded = parse_json_dict_with_messages(
        payload_json,
        field="Authoritative plugin state outbox payload",
        invalid_object_message="Authoritative plugin state outbox payload must be an object.",
    )
    event_id = coerce_required_non_empty_str(decoded.get("event_id"), label="event_id")
    plugin_name = coerce_required_non_empty_str(decoded.get("plugin_name"), label="plugin_name")
    previous_state = coerce_required_non_empty_str(
        decoded.get("previous_state"),
        label="previous_state",
    )
    new_state = coerce_required_non_empty_str(decoded.get("new_state"), label="new_state")
    reason = coerce_required_non_empty_str(decoded.get("reason"), label="reason")
    trace_id = require_optional_str(
        decoded.get("trace_id"),
        label="trace_id",
        build_error=ValidationError,
        invalid_message="trace_id must be a string when provided.",
    )
    timestamp = require_positive_outbox_timestamp_seconds(
        decoded.get("timestamp"),
        error_message="Authoritative plugin state outbox timestamp is invalid.",
    )
    previous_state_name = resolve_plugin_runtime_state_name(previous_state)
    new_state_name = resolve_plugin_runtime_state_name(new_state)
    if previous_state_name is None:
        raise ValidationError("Authoritative plugin state previous_state is invalid.")
    if new_state_name is None:
        raise ValidationError("Authoritative plugin state new_state is invalid.")
    if event_type == PluginRuntimeStateChangedEvent.__name__:
        details_value = decoded.get("details")
        details = dict(details_value) if isinstance(details_value, dict) else {}
        return PluginRuntimeStateChangedEvent(
            plugin_name=plugin_name,
            previous_state=previous_state_name,
            new_state=new_state_name,
            reason=reason,
            details=details,
            context=None,
            event_id=event_id,
            timestamp=timestamp,
            trace_id=trace_id,
        )
    if event_type == PluginInstallationStateChangedEvent.__name__:
        return PluginInstallationStateChangedEvent(
            plugin_name=plugin_name,
            previous_state=previous_state_name,
            new_state=new_state_name,
            reason=reason,
            context=None,
            event_id=event_id,
            timestamp=timestamp,
            trace_id=trace_id,
        )
    raise ValidationError(f"Unsupported authoritative plugin state event type: {event_type}")

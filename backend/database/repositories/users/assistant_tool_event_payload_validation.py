"""SoAI - Assistant tool event payload validation [backend/database/repositories/users/assistant_tool_event_payload_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.assistant_timeline.tool_event_payload_contract import (
    build_tool_event_payload_preview,
    tool_event_type_requires_payload_contract,
    validate_tool_event_payload_contract,
)
from core.errors.exceptions import ValidationError
from core.serialization.json import serialize_json_compact_stable_strict
from core.types.json import is_json_dict
from core.validation.record_fields import require_json_object
from database.core.json_codec import safe_json_deserialize_required_object

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_validated_assistant_event_payload_json",
    "build_validated_live_tool_event_payload_json",
    "build_validated_timeline_event_payload",
)


def build_validated_timeline_event_payload(
    *,
    event_type: str,
    payload: JSONDict,
) -> JSONDict:
    if not tool_event_type_requires_payload_contract(event_type):
        return payload
    tool_payload = require_json_object(
        payload.get("tool"),
        label="Assistant tool event payload",
        build_error=ValidationError,
        invalid_message="Assistant tool event payload must contain a tool object.",
    )
    validated_payload: JSONDict = {}
    validated_payload.update(payload)
    validated_payload["tool"] = build_tool_event_payload_preview(tool_payload)
    return validated_payload


def build_validated_assistant_event_payload_json(
    *,
    event_type: str,
    payload_json: str,
) -> str:
    payload = safe_json_deserialize_required_object(
        payload_json,
        error_message="Assistant event payload_json must decode to an object.",
    )
    validated_payload = build_validated_timeline_event_payload(
        event_type=event_type,
        payload=payload,
    )
    return serialize_json_compact_stable_strict(validated_payload)


def build_validated_live_tool_event_payload_json(payload_json: str) -> str:
    payload = safe_json_deserialize_required_object(
        payload_json,
        error_message="Tool live event payload_json must decode to an object.",
    )
    tool_payload = payload.get("tool")
    if not is_json_dict(tool_payload):
        raise ValidationError("Tool live event payload_json must contain a tool object.")
    validate_tool_event_payload_contract(tool_payload)
    validated_payload: JSONDict = {}
    validated_payload.update(payload)
    validated_payload["tool"] = build_tool_event_payload_preview(tool_payload)
    return serialize_json_compact_stable_strict(validated_payload)

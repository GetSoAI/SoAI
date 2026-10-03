"""SoAI - Automation definition validation and schedule transitions [backend/core/automation/automation_update_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.automation.automation_constants import AUTOMATION_PAYLOAD_FIELDS
from core.automation.automation_interactive_tool_approval import strip_interactive_tool_approval
from core.automation.automation_payload_validation import validate_automation_definition_payload
from core.automation.automation_recurrence import resolve_next_run_at
from core.errors.exceptions import StateError, ValidationError
from core.types.json import JSONDict

__all__ = ("resolve_automation_update",)


def _automation_field_changed(
    current: JSONDict,
    validated: JSONDict,
    field_name: str,
) -> bool:
    validated_value = validated.get(field_name)
    if field_name == "model_settings" and isinstance(validated_value, dict):
        validated_value = strip_interactive_tool_approval(validated_value)
    return current.get(field_name) != validated_value


def resolve_automation_update(
    current: JSONDict,
    payload: JSONDict,
    *,
    now_ms: int,
    disallowed_unqualified_tools: tuple[str, ...],
) -> tuple[JSONDict, bool]:
    automation_field_set = frozenset(AUTOMATION_PAYLOAD_FIELDS)
    unexpected_fields = [key for key in payload if key not in automation_field_set]
    if unexpected_fields:
        unexpected_joined = ", ".join(sorted(unexpected_fields))
        allowed_joined = ", ".join(AUTOMATION_PAYLOAD_FIELDS)
        raise ValidationError(
            f"Unexpected automation update fields: {unexpected_joined}. Allowed: {allowed_joined}.",
        )
    merged: JSONDict = {}
    for field_name in AUTOMATION_PAYLOAD_FIELDS:
        if field_name not in current:
            raise StateError(f"Automation is missing required field '{field_name}'.")
        merged[field_name] = current[field_name]
    for field_name in AUTOMATION_PAYLOAD_FIELDS:
        if field_name in payload:
            merged[field_name] = payload[field_name]
    validated = validate_automation_definition_payload(
        merged,
        disallowed_unqualified_tools=disallowed_unqualified_tools,
    )
    schedule_changed = any(
        current[field_name] != validated[field_name]
        for field_name in ("timezone", "start_local", "recurrence", "enabled")
    )
    if schedule_changed:
        timezone_name = validated["timezone"]
        start_local = validated["start_local"]
        recurrence = validated["recurrence"]
        enabled = validated["enabled"]
        if (
            not isinstance(timezone_name, str)
            or not isinstance(start_local, str)
            or not isinstance(recurrence, str)
            or not isinstance(enabled, bool)
        ):
            raise StateError("Validated automation schedule is invalid.")
        validated["next_run_at_ms"] = resolve_next_run_at(
            timezone_name=timezone_name,
            start_local=start_local,
            recurrence=recurrence,
            enabled=enabled,
            now_ms=now_ms,
        )
    else:
        validated["next_run_at_ms"] = current["next_run_at_ms"]
    changed = current.get("next_run_at_ms") != validated.get("next_run_at_ms")
    for field_name in AUTOMATION_PAYLOAD_FIELDS:
        if _automation_field_changed(current, validated, field_name):
            changed = True
            break
    return (validated, changed)

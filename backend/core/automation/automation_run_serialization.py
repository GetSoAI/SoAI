"""SoAI - Automation run serialization [backend/core/automation/automation_run_serialization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.automation.automation_interactive_tool_approval import (
    strip_interactive_tool_approval,
)
from core.automation.automation_record_validation import (
    read_automation_requested_model,
    require_automation_epoch_field,
    require_automation_int_field,
    require_automation_json_object_field,
    require_automation_optional_bool_field,
    require_automation_optional_color_field,
    require_automation_optional_epoch_field,
    require_automation_optional_str_field,
    require_automation_run_status_field,
    require_automation_str_field,
    require_automation_str_list_field,
)
from core.errors.exceptions import StateError
from core.execution.protocols import AutomationRunSnapshot
from core.execution.serialization import serialize_owned_execution_core
from core.openai.model_settings_validation import validate_model_settings
from core.validation.epoch import EPOCH_MS_MIN

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_automation_run_snapshot",
    "build_automation_run_snapshot_json_schema",
    "serialize_automation_run_snapshot",
)

_LABEL_PREFIX = "Automation run field"


def serialize_automation_run_snapshot(
    run_record: Mapping[str, JSONValue] | AutomationRunSnapshot | None,
) -> JSONDict | None:
    snapshot = build_automation_run_snapshot(run_record)
    if snapshot is None:
        return None
    payload = serialize_owned_execution_core(snapshot)
    payload.update(
        {
            "run_id": snapshot.run_id,
            "automation_id": snapshot.automation_id,
            "user_id": snapshot.user_id,
            "scheduled_at_ms": snapshot.scheduled_at_ms,
            "started_at_actual_ms": snapshot.started_at_actual_ms,
            "finished_at_ms": snapshot.finished_at_ms,
            "conv_id": snapshot.conv_id,
            "result_excerpt": snapshot.result_excerpt,
            "title": snapshot.title,
            "enabled": snapshot.enabled,
            "color": snapshot.color,
            "turns_snapshot": list(snapshot.turns_snapshot),
            "model_settings_snapshot": strip_interactive_tool_approval(
                snapshot.model_settings_snapshot,
            ),
            "limits_snapshot": dict(snapshot.limits_snapshot),
        },
    )
    return payload


def build_automation_run_snapshot(
    run_record: Mapping[str, JSONValue] | AutomationRunSnapshot | None,
) -> AutomationRunSnapshot | None:
    if run_record is None:
        return None
    if isinstance(run_record, AutomationRunSnapshot):
        return run_record
    started_at_actual_ms = require_automation_optional_epoch_field(
        run_record,
        "started_at_actual_ms",
        build_error=StateError,
        label_prefix=_LABEL_PREFIX,
    )
    scheduled_at_ms = require_automation_epoch_field(
        run_record,
        "scheduled_at_ms",
        build_error=StateError,
        label_prefix=_LABEL_PREFIX,
    )
    if started_at_actual_ms is None:
        started_at_ms = scheduled_at_ms
    else:
        started_at_ms = started_at_actual_ms
    finished_at_ms = require_automation_optional_epoch_field(
        run_record,
        "finished_at_ms",
        build_error=StateError,
        label_prefix=_LABEL_PREFIX,
    )
    return AutomationRunSnapshot(
        execution_type="automation_run",
        owner_task_id=require_automation_optional_str_field(
            run_record,
            "owner_task_id",
            build_error=StateError,
            label_prefix=_LABEL_PREFIX,
        ),
        status=require_automation_run_status_field(
            run_record,
            "status",
            build_error=StateError,
            label_prefix=_LABEL_PREFIX,
        ),
        status_message=require_automation_optional_str_field(
            run_record,
            "status_message",
            build_error=StateError,
            label_prefix=_LABEL_PREFIX,
        ),
        started_at_ms=started_at_ms,
        updated_at_ms=(finished_at_ms if finished_at_ms is not None else started_at_ms),
        finished_at_ms=finished_at_ms,
        requested_model=read_automation_requested_model(
            run_record,
            build_error=StateError,
            label_prefix=_LABEL_PREFIX,
        ),
        token_usage=None,
        run_id=require_automation_str_field(
            run_record,
            "run_id",
            build_error=StateError,
            label_prefix=_LABEL_PREFIX,
        ),
        automation_id=require_automation_str_field(
            run_record,
            "automation_id",
            build_error=StateError,
            label_prefix=_LABEL_PREFIX,
        ),
        user_id=require_automation_int_field(
            run_record,
            "user_id",
            build_error=StateError,
            label_prefix=_LABEL_PREFIX,
            minimum=1,
        ),
        scheduled_at_ms=scheduled_at_ms,
        started_at_actual_ms=started_at_actual_ms,
        conv_id=require_automation_optional_str_field(
            run_record,
            "conv_id",
            build_error=StateError,
            label_prefix=_LABEL_PREFIX,
        ),
        result_excerpt=require_automation_optional_str_field(
            run_record,
            "result_excerpt",
            build_error=StateError,
            label_prefix=_LABEL_PREFIX,
        ),
        title=require_automation_optional_str_field(
            run_record,
            "title",
            build_error=StateError,
            label_prefix=_LABEL_PREFIX,
        ),
        enabled=require_automation_optional_bool_field(
            run_record,
            "enabled",
            build_error=StateError,
            label_prefix=_LABEL_PREFIX,
        ),
        color=require_automation_optional_color_field(
            run_record,
            "color",
            build_error=StateError,
            label_prefix=_LABEL_PREFIX,
        ),
        turns_snapshot=require_automation_str_list_field(
            run_record,
            "turns_snapshot",
            build_error=StateError,
            label_prefix=_LABEL_PREFIX,
        ),
        model_settings_snapshot=validate_model_settings(
            require_automation_json_object_field(
                run_record,
                "model_settings_snapshot",
                build_error=StateError,
                label_prefix=_LABEL_PREFIX,
            ),
        ),
        limits_snapshot=require_automation_json_object_field(
            run_record,
            "limits_snapshot",
            build_error=StateError,
            label_prefix=_LABEL_PREFIX,
        ),
    )


def build_automation_run_snapshot_json_schema(*, nullable: bool) -> JSONDict:
    schema_type: str | list[str] = ["object", "null"] if nullable else "object"
    return {
        "type": schema_type,
        "additionalProperties": False,
        "properties": {
            "run_id": {"type": "string"},
            "automation_id": {"type": "string"},
            "user_id": {"type": "integer", "minimum": 1},
            "execution_type": {"type": "string"},
            "owner_task_id": {"type": ["string", "null"]},
            "scheduled_at_ms": {"type": "integer", "minimum": EPOCH_MS_MIN},
            "started_at_actual_ms": {
                "type": ["integer", "null"],
                "minimum": EPOCH_MS_MIN,
            },
            "finished_at_ms": {
                "type": ["integer", "null"],
                "minimum": EPOCH_MS_MIN,
            },
            "status": {"type": "string"},
            "status_message": {"type": ["string", "null"]},
            "requested_model": {"type": ["string", "null"]},
            "token_usage": {
                "type": ["object", "null"],
                "additionalProperties": True,
            },
            "conv_id": {"type": ["string", "null"]},
            "result_excerpt": {"type": ["string", "null"]},
            "title": {"type": ["string", "null"]},
            "enabled": {"type": ["boolean", "null"]},
            "color": {"type": ["string", "null"]},
            "turns_snapshot": {"type": "array", "items": {"type": "string"}},
            "model_settings_snapshot": {
                "type": "object",
                "additionalProperties": True,
            },
            "limits_snapshot": {
                "type": "object",
                "additionalProperties": True,
            },
        },
        "required": [
            "run_id",
            "automation_id",
            "user_id",
            "execution_type",
            "owner_task_id",
            "scheduled_at_ms",
            "started_at_actual_ms",
            "finished_at_ms",
            "status",
            "status_message",
            "requested_model",
            "token_usage",
            "conv_id",
            "result_excerpt",
            "title",
            "enabled",
            "color",
            "turns_snapshot",
            "model_settings_snapshot",
            "limits_snapshot",
        ],
    }

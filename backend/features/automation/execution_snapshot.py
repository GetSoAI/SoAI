"""SoAI - Automation execution snapshot [backend/features/automation/execution_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.automation.automation_conversation_model_settings import (
    resolve_automation_conversation_model_settings,
    resolve_automation_effective_conversation_model_settings,
)
from core.automation.automation_model_reference import (
    validate_automation_model_settings_reference,
)
from core.automation.automation_record_validation import (
    require_automation_int_field,
    require_automation_json_list_field,
    require_automation_json_object_field,
    require_automation_str_field,
)
from core.automation.automation_turn_limits import (
    normalize_automation_turns,
    require_automation_limits_snapshot,
    require_automation_max_run_minutes_snapshot,
)
from core.errors.exceptions import StateError, ValidationError
from core.users.user_id import require_user_id

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "AutomationRunExecutionSnapshot",
    "resolve_automation_run_execution_snapshot",
)

_LABEL_PREFIX = "Automation run field"


def _require_limits_snapshot(run_record: JSONDict) -> tuple[int, int]:
    limits_snapshot = require_automation_json_object_field(
        run_record,
        "limits_snapshot",
        build_error=StateError,
        label_prefix=_LABEL_PREFIX,
    )
    return require_automation_limits_snapshot(limits_snapshot)


def _require_max_run_minutes_snapshot(run_record: JSONDict) -> int:
    limits_snapshot = require_automation_json_object_field(
        run_record,
        "limits_snapshot",
        build_error=StateError,
        label_prefix=_LABEL_PREFIX,
    )
    max_run_minutes = require_automation_max_run_minutes_snapshot(limits_snapshot)
    if max_run_minutes <= 0:
        raise ValidationError(
            "Automation limits_snapshot.max_run_minutes must be a positive integer.",
        )
    return int(max_run_minutes)


def _normalize_turns_snapshot(
    turns_snapshot: list[JSONValue],
    *,
    max_turns: int,
    max_turn_chars: int,
) -> list[str]:
    return normalize_automation_turns(
        turns_snapshot,
        max_turns=max_turns,
        max_turn_chars=max_turn_chars,
        label="Automation run turns",
    )


@dataclass(frozen=True, slots=True)
class AutomationRunExecutionSnapshot:
    automation_id: str
    user_id: int
    title: str
    max_turns: int
    max_turn_chars: int
    max_run_minutes: int
    normalized_turns: list[str]
    conversation_model_settings: JSONDict
    effective_conversation_model_settings: JSONDict
    requested_model: str


async def resolve_automation_run_execution_snapshot(
    api_dependencies: ApiDependencies,
    *,
    run_record: JSONDict,
) -> AutomationRunExecutionSnapshot:
    automation_id = require_automation_str_field(
        run_record,
        "automation_id",
        build_error=StateError,
        label_prefix=_LABEL_PREFIX,
    )
    user_id = require_user_id(
        require_automation_int_field(
            run_record,
            "user_id",
            build_error=StateError,
            label_prefix=_LABEL_PREFIX,
            minimum=0,
        ),
    )
    title = require_automation_str_field(
        run_record,
        "title",
        build_error=StateError,
        label_prefix=_LABEL_PREFIX,
    )
    max_turns, max_turn_chars = _require_limits_snapshot(run_record)
    max_run_minutes = _require_max_run_minutes_snapshot(run_record)
    turns_snapshot = require_automation_json_list_field(
        run_record,
        "turns_snapshot",
        build_error=StateError,
        label_prefix=_LABEL_PREFIX,
    )
    normalized_turns = _normalize_turns_snapshot(
        list(turns_snapshot),
        max_turns=max_turns,
        max_turn_chars=max_turn_chars,
    )
    model_settings_snapshot = require_automation_json_object_field(
        run_record,
        "model_settings_snapshot",
        build_error=StateError,
        label_prefix=_LABEL_PREFIX,
    )
    conversation_model_settings = await resolve_automation_conversation_model_settings(
        user_id=user_id,
        model_settings=model_settings_snapshot,
        database_chat_identity_defaults=(api_dependencies.database_chat_identity_defaults),
        database_chat_model_defaults=(api_dependencies.database_chat_model_defaults),
    )
    requested_model = conversation_model_settings.get("model")
    if not isinstance(requested_model, str) or not requested_model.strip():
        raise ValidationError("Automation model_settings.model is required.")
    await validate_automation_model_settings_reference(
        model_settings=conversation_model_settings,
        model_resolution_service=api_dependencies.model_resolution_service,
        model_information_service=api_dependencies.model_information_service,
        model_virtual_model_service=api_dependencies.model_virtual_model_service,
    )
    effective_conversation_model_settings = (
        await resolve_automation_effective_conversation_model_settings(
            user_id=user_id,
            automation_id=automation_id,
            executed_model_settings=conversation_model_settings,
            database_automations=api_dependencies.database_automations,
            database_chat_identity_defaults=(api_dependencies.database_chat_identity_defaults),
            database_chat_model_defaults=(api_dependencies.database_chat_model_defaults),
        )
    )
    return AutomationRunExecutionSnapshot(
        automation_id=automation_id,
        user_id=user_id,
        title=title,
        max_turns=max_turns,
        max_turn_chars=max_turn_chars,
        max_run_minutes=max_run_minutes,
        normalized_turns=normalized_turns,
        conversation_model_settings=conversation_model_settings,
        effective_conversation_model_settings=effective_conversation_model_settings,
        requested_model=requested_model.strip(),
    )

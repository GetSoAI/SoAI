"""SoAI - Automation update transactions [backend/database/repositories/users/automation_update_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.automation.automation_constants import AUTOMATION_PAYLOAD_FIELDS
from core.automation.automation_payload_validation import validate_automation_payload
from core.errors.exceptions import StateError, ValidationError
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from database.core.json_codec import (
    serialize_required_json_list_field,
    serialize_required_json_object_field,
)
from database.repositories.users.automation_abandoned_run_operations import (
    sync_list_abandoned_run_owner_task_ids,
    sync_mark_queued_runs_abandoned_for_disabled,
)
from database.repositories.users.automation_event_outbox import (
    sync_enqueue_automation_domain_event,
)
from database.repositories.users.automation_write_operations import sync_get_automation

__all__ = (
    "sync_update_automation",
    "sync_update_automation_and_abandon_disabled_runs",
)


def _resolve_validated_automation_update(
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
    validated = validate_automation_payload(
        merged,
        now_ms=now_ms,
        disallowed_unqualified_tools=disallowed_unqualified_tools,
    )
    changed = current.get("next_run_at_ms") != validated.get("next_run_at_ms")
    for field_name in AUTOMATION_PAYLOAD_FIELDS:
        if current.get(field_name) != validated.get(field_name):
            changed = True
            break
    return (validated, changed)


def _write_updated_automation(
    conn: sqlite3.Connection,
    *,
    automation_id: str,
    user_id: int,
    validated: JSONDict,
    now_ms: int,
) -> None:
    conn.execute(
        """
        UPDATE automations
        SET
            title = ?,
            enabled = ?,
            color = ?,
            last_modified_at_ms = ?,
            timezone = ?,
            start_local = ?,
            recurrence = ?,
            next_run_at_ms = ?,
            model_settings = ?,
            turns_json = ?,
            max_turns = ?,
            max_turn_chars = ?,
            max_run_minutes = ?
        WHERE id = ? AND user_id = ?
        """,
        (
            validated["title"],
            1 if validated["enabled"] else 0,
            validated["color"],
            now_ms,
            validated["timezone"],
            validated["start_local"],
            validated["recurrence"],
            validated["next_run_at_ms"],
            serialize_required_json_object_field(
                validated["model_settings"],
                error_message="Automation model_settings are invalid.",
            ),
            serialize_required_json_list_field(
                validated["turns"],
                error_message="Automation turns are invalid.",
            ),
            validated["max_turns"],
            validated["max_turn_chars"],
            validated["max_run_minutes"],
            automation_id,
            user_id,
        ),
    )


def _enqueue_automation_updated(
    conn: sqlite3.Connection,
    *,
    automation_id: str,
    user_id: int,
    created_at_ms: int,
) -> None:
    sync_enqueue_automation_domain_event(
        conn,
        event_type="AutomationUpdatedEvent",
        created_at_ms=created_at_ms,
        user_id=user_id,
        automation_id=automation_id,
    )


def _enqueue_run_updated_events(
    conn: sqlite3.Connection,
    *,
    automation_id: str,
    user_id: int,
    created_at_ms: int,
    run_ids: list[str],
) -> None:
    for run_id in run_ids:
        sync_enqueue_automation_domain_event(
            conn,
            event_type="AutomationRunUpdatedEvent",
            created_at_ms=created_at_ms,
            user_id=user_id,
            automation_id=automation_id,
            run_id=run_id,
        )


def sync_update_automation(
    conn: sqlite3.Connection,
    automation_id: str,
    user_id: int,
    payload: JSONDict,
    disallowed_unqualified_tools: tuple[str, ...],
) -> JSONDict | None:
    current = sync_get_automation(conn, automation_id, user_id)
    if current is None:
        return None
    now = epoch_ms()
    validated, changed = _resolve_validated_automation_update(
        current,
        payload,
        now_ms=now,
        disallowed_unqualified_tools=disallowed_unqualified_tools,
    )
    if not changed:
        return current
    _write_updated_automation(
        conn,
        automation_id=automation_id,
        user_id=user_id,
        validated=validated,
        now_ms=now,
    )
    _enqueue_automation_updated(
        conn,
        automation_id=automation_id,
        user_id=user_id,
        created_at_ms=now,
    )
    return sync_get_automation(conn, automation_id, user_id)


def sync_update_automation_and_abandon_disabled_runs(
    conn: sqlite3.Connection,
    automation_id: str,
    user_id: int,
    payload: JSONDict,
    disallowed_unqualified_tools: tuple[str, ...],
    *,
    status_message: str,
    finished_at_ms: int,
) -> tuple[JSONDict | None, list[str], list[str]]:
    current = sync_get_automation(conn, automation_id, user_id)
    if current is None:
        return (None, [], [])
    now = epoch_ms()
    validated, changed = _resolve_validated_automation_update(
        current,
        payload,
        now_ms=now,
        disallowed_unqualified_tools=disallowed_unqualified_tools,
    )
    updated = current
    if changed:
        _write_updated_automation(
            conn,
            automation_id=automation_id,
            user_id=user_id,
            validated=validated,
            now_ms=now,
        )
        loaded = sync_get_automation(conn, automation_id, user_id)
        if loaded is None:
            raise StateError("Updated automation could not be loaded.")
        updated = loaded
    abandoned_run_ids = (
        sync_mark_queued_runs_abandoned_for_disabled(
            conn,
            automation_id=automation_id,
            user_id=user_id,
            status_message=status_message,
            finished_at_ms=finished_at_ms,
        )
        if current.get("enabled") is True and updated.get("enabled") is False
        else []
    )
    abandoned_owner_task_ids = (
        sync_list_abandoned_run_owner_task_ids(
            conn,
            automation_id=automation_id,
            user_id=user_id,
            status_message=status_message,
        )
        if updated.get("enabled") is False
        else []
    )
    if changed:
        _enqueue_automation_updated(
            conn,
            automation_id=automation_id,
            user_id=user_id,
            created_at_ms=now,
        )
    if abandoned_run_ids:
        _enqueue_run_updated_events(
            conn,
            automation_id=automation_id,
            user_id=user_id,
            created_at_ms=finished_at_ms,
            run_ids=abandoned_run_ids,
        )
    return (updated, abandoned_run_ids, abandoned_owner_task_ids)

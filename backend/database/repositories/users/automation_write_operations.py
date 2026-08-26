"""SoAI - Automation create/update/delete transactions [backend/database/repositories/users/automation_write_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
import uuid

from core.automation.automation_payload_validation import validate_automation_payload
from core.errors.exceptions import ConflictError, StateError, ValidationError
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from database.core.json_codec import (
    serialize_required_json_list_field,
    serialize_required_json_object_field,
)
from database.core.query_execution import sync_fetch_one_as_dict, sync_fetch_one_scalar
from database.core.sqlite_errors import parse_sqlite_integrity_error
from database.repositories.users.automation_event_outbox import (
    sync_enqueue_automation_domain_event,
)
from database.repositories.users.automation_row_formatter import format_automation_row
from database.repositories.users.automation_sql_support import automation_select_sql

__all__ = (
    "sync_create_automation",
    "sync_delete_automation",
    "sync_get_automation",
)


def sync_get_automation(
    conn: sqlite3.Connection,
    automation_id: str,
    user_id: int,
) -> JSONDict | None:
    cursor = conn.execute(
        f"{automation_select_sql()} WHERE id = ? AND user_id = ?",
        (automation_id, user_id),
    )
    formatted = format_automation_row(sync_fetch_one_as_dict(cursor))
    return formatted if isinstance(formatted, dict) else None


def sync_create_automation(
    conn: sqlite3.Connection,
    user_id: int,
    payload: JSONDict,
    disallowed_unqualified_tools: tuple[str, ...],
) -> JSONDict:
    automation_id = f"auto_{uuid.uuid4().hex}"
    now = epoch_ms()
    validated = validate_automation_payload(
        payload,
        now_ms=now,
        disallowed_unqualified_tools=disallowed_unqualified_tools,
    )
    try:
        conn.execute(
            """
            INSERT INTO automations (
                id,
                user_id,
                title,
                enabled,
                color,
                created_at_ms,
                last_modified_at_ms,
                timezone,
                start_local,
                recurrence,
                next_run_at_ms,
                model_settings,
                turns_json,
                max_turns,
                max_turn_chars,
                max_run_minutes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                automation_id,
                user_id,
                validated["title"],
                1 if validated["enabled"] else 0,
                validated["color"],
                now,
                now,
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
            ),
        )
    except sqlite3.IntegrityError as exception:
        constraint_type, detail = parse_sqlite_integrity_error(exception)
        if constraint_type in {"unique", "primary_key"}:
            raise ConflictError("Automation already exists.") from exception
        if constraint_type == "foreign_key":
            raise ValidationError(f"User with ID '{user_id}' does not exist.") from exception
        if constraint_type == "check":
            raise ValidationError(
                f"Invalid automation data: constraint violation on {detail or 'unknown field'}.",
            ) from exception
        raise StateError(f"Database constraint violation: {exception}") from exception
    created = sync_get_automation(conn, automation_id, user_id)
    if created is None:
        raise StateError("Automation was created but could not be loaded.")
    sync_enqueue_automation_domain_event(
        conn,
        event_type="AutomationCreatedEvent",
        created_at_ms=now,
        user_id=user_id,
        automation_id=automation_id,
    )
    return created


def sync_delete_automation(conn: sqlite3.Connection, automation_id: str, user_id: int) -> bool:
    existing_marker = sync_fetch_one_scalar(
        conn.execute(
            "SELECT 1 FROM automations WHERE id = ? AND user_id = ? LIMIT 1",
            (automation_id, user_id),
        ),
    )
    if existing_marker is None:
        return False
    active_marker = sync_fetch_one_scalar(
        conn.execute(
            """
            SELECT 1
            FROM automation_runs
            WHERE automation_id = ? AND user_id = ? AND status IN ('queued', 'running')
            LIMIT 1
            """,
            (automation_id, user_id),
        ),
    )
    if active_marker is not None:
        raise ConflictError("Automation cannot be deleted while it has queued or running runs.")
    deleted = (
        conn.execute(
            "DELETE FROM automations WHERE id = ? AND user_id = ?",
            (automation_id, user_id),
        ).rowcount
        > 0
    )
    if deleted:
        sync_enqueue_automation_domain_event(
            conn,
            event_type="AutomationDeletedEvent",
            created_at_ms=epoch_ms(),
            user_id=user_id,
            automation_id=automation_id,
        )
    return deleted

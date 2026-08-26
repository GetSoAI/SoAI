"""SoAI - Automation run outbox event helpers [backend/database/repositories/users/automation_run_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import StateError
from core.types.json import JSONDict
from core.users.user_id import is_strict_user_id
from database.repositories.users.automation_event_outbox import (
    sync_enqueue_automation_domain_event,
)

__all__ = ()


def enqueue_run_event(
    conn: sqlite3.Connection,
    *,
    event_type: str,
    created_at_ms: int,
    automation_id: str,
    user_id: int,
    run_id: str,
) -> None:
    sync_enqueue_automation_domain_event(
        conn,
        event_type=event_type,
        created_at_ms=created_at_ms,
        user_id=user_id,
        automation_id=automation_id,
        run_id=run_id,
    )


def extract_run_event_fields(formatted: JSONDict, *, run_id: str) -> tuple[str, int, str]:
    automation_id_value = formatted.get("automation_id")
    user_id_value = formatted.get("user_id")
    run_id_value = formatted.get("run_id")
    if not isinstance(automation_id_value, str) or not automation_id_value:
        raise StateError("Automation run automation_id is invalid.")
    if not is_strict_user_id(user_id_value):
        raise StateError("Automation run user_id is invalid.")
    if not isinstance(run_id_value, str) or not run_id_value:
        raise StateError("Automation run run_id is invalid.")
    if run_id_value != run_id:
        raise StateError("Automation run id mismatch.")
    return automation_id_value, user_id_value, run_id


def enqueue_run_updated_event(
    conn: sqlite3.Connection,
    *,
    formatted: JSONDict,
    run_id: str,
    created_at_ms: int,
) -> None:
    automation_id_value, user_id_value, run_id_value = extract_run_event_fields(
        formatted,
        run_id=run_id,
    )
    enqueue_run_event(
        conn,
        event_type="AutomationRunUpdatedEvent",
        created_at_ms=created_at_ms,
        automation_id=automation_id_value,
        user_id=user_id_value,
        run_id=run_id_value,
    )

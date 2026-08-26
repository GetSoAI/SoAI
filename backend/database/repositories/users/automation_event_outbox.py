"""SoAI - Automation domain event outbox helpers [backend/database/repositories/users/automation_event_outbox.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.events.domain_event_payload import build_domain_event_payload
from core.users.user_id import is_strict_user_id
from database.repositories.event_outbox.sync_ops import sync_enqueue_domain_event_payload

if TYPE_CHECKING:
    from sqlite3 import Connection

__all__ = ("sync_enqueue_automation_domain_event",)


def sync_enqueue_automation_domain_event(
    conn: Connection,
    *,
    event_type: str,
    created_at_ms: int,
    user_id: int,
    automation_id: str,
    run_id: str | None = None,
) -> None:
    if not _is_supported_automation_event_type(event_type):
        raise StateError(f"Unsupported automation domain event type: {event_type}")
    if not is_strict_user_id(user_id):
        raise StateError("Automation domain events require user_id to be a positive integer.")
    if not isinstance(automation_id, str):
        raise StateError("Automation domain events require automation_id to be a string.")
    normalized_automation_id = automation_id.strip()
    if not normalized_automation_id:
        raise StateError("Automation domain events require a non-empty automation_id.")
    payload = build_domain_event_payload(
        fields={
            "user_id": int(user_id),
            "automation_id": normalized_automation_id,
        },
    )
    if _is_automation_run_event_type(event_type):
        if run_id is not None and not isinstance(run_id, str):
            raise StateError("Automation run domain events require run_id to be a string.")
        normalized_run_id = (run_id or "").strip()
        if not normalized_run_id:
            raise StateError(f"Automation domain event '{event_type}' requires a non-empty run_id.")
        payload["run_id"] = normalized_run_id
    elif run_id is not None:
        raise StateError(f"Automation domain event '{event_type}' must not include run_id.")
    sync_enqueue_domain_event_payload(
        conn,
        event_type=event_type,
        payload=payload,
        created_at_ms=created_at_ms,
    )


def _is_automation_run_event_type(event_type: str) -> bool:
    return event_type in {"AutomationRunCreatedEvent", "AutomationRunUpdatedEvent"}


def _is_supported_automation_event_type(event_type: str) -> bool:
    if _is_automation_run_event_type(event_type):
        return True
    return event_type in {
        "AutomationCreatedEvent",
        "AutomationUpdatedEvent",
        "AutomationDeletedEvent",
    }

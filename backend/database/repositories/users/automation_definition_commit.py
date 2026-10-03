"""SoAI - Atomic automation definition update commits [backend/database/repositories/users/automation_definition_commit.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.automation.automation_interactive_tool_approval import (
    extract_interactive_tool_approval,
    strip_interactive_tool_approval,
)
from core.automation.automation_mutation_results import AutomationUpdateResult
from core.automation.automation_revision import require_automation_revision_match
from core.automation.automation_update_validation import resolve_automation_update
from core.errors.exceptions import StateError
from core.timing.epoch import epoch_ms
from database.core.json_codec import (
    serialize_required_json_list_field,
    serialize_required_json_object_field,
)
from database.repositories.users.automation_abandoned_run_operations import (
    sync_list_abandoned_run_owner_task_ids,
    sync_mark_queued_runs_abandoned_for_disabled,
)
from database.repositories.users.automation_conversation_settings_propagation import (
    sync_propagate_automation_conversation_model_settings,
)
from database.repositories.users.automation_event_outbox import (
    sync_enqueue_automation_domain_event,
)
from database.repositories.users.automation_write_operations import sync_get_automation
from database.repositories.users.conversation_event_outbox import (
    sync_enqueue_conversation_updated_event,
)

if TYPE_CHECKING:
    from core.automation.automation_mutation_results import (
        AutomationConversationVersion,
        AutomationPreparedUpdate,
    )
    from core.types.json import JSONDict

__all__ = ("sync_commit_automation_update",)


def _write_updated_automation(
    conn: sqlite3.Connection,
    *,
    prepared: AutomationPreparedUpdate,
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
            prepared.automation_id,
            prepared.user_id,
        ),
    )


def _commit_definition_update(
    conn: sqlite3.Connection,
    *,
    prepared: AutomationPreparedUpdate,
    current: JSONDict,
    disallowed_unqualified_tools: tuple[str, ...],
    now_ms: int,
) -> JSONDict:
    validated, changed = resolve_automation_update(
        current,
        prepared.payload,
        now_ms=now_ms,
        disallowed_unqualified_tools=disallowed_unqualified_tools,
    )
    if not changed:
        return current
    _write_updated_automation(
        conn,
        prepared=prepared,
        validated=validated,
        now_ms=now_ms,
    )
    updated = sync_get_automation(conn, prepared.automation_id, prepared.user_id)
    if updated is None:
        raise StateError("Updated automation could not be loaded.")
    sync_enqueue_automation_domain_event(
        conn,
        event_type="AutomationUpdatedEvent",
        created_at_ms=now_ms,
        user_id=prepared.user_id,
        automation_id=prepared.automation_id,
    )
    return updated


def _recover_disabled_run_ownership(
    conn: sqlite3.Connection,
    *,
    prepared: AutomationPreparedUpdate,
    current: JSONDict,
    updated: JSONDict,
    now_ms: int,
) -> tuple[list[str], list[str]]:
    if prepared.payload.get("enabled") is not False or updated.get("enabled") is not False:
        return ([], [])
    abandoned_run_ids = (
        sync_mark_queued_runs_abandoned_for_disabled(
            conn,
            automation_id=prepared.automation_id,
            user_id=prepared.user_id,
            status_message="disabled",
            finished_at_ms=now_ms,
        )
        if current.get("enabled") is True
        else []
    )
    abandoned_owner_task_ids = sync_list_abandoned_run_owner_task_ids(
        conn,
        automation_id=prepared.automation_id,
        user_id=prepared.user_id,
        status_message="disabled",
    )
    for run_id in abandoned_run_ids:
        sync_enqueue_automation_domain_event(
            conn,
            event_type="AutomationRunUpdatedEvent",
            created_at_ms=now_ms,
            user_id=prepared.user_id,
            automation_id=prepared.automation_id,
            run_id=run_id,
        )
    return (abandoned_run_ids, abandoned_owner_task_ids)


def _validate_prepared_settings(
    prepared: AutomationPreparedUpdate,
    current: JSONDict,
    updated: JSONDict,
) -> None:
    settings_changed = (
        current["model_settings"] != updated["model_settings"]
        or current["interactive_tool_approval"] != updated["interactive_tool_approval"]
    )
    if settings_changed != (prepared.model_settings is not None):
        raise StateError("Prepared automation settings do not match the committed transition.")
    if prepared.model_settings is not None and (
        updated["model_settings"] != strip_interactive_tool_approval(prepared.model_settings)
        or updated["interactive_tool_approval"]
        != extract_interactive_tool_approval(prepared.model_settings)
    ):
        raise StateError("Automation settings changed after external defaults were prepared.")


def _propagate_conversation_settings(
    conn: sqlite3.Connection,
    *,
    prepared: AutomationPreparedUpdate,
    conversation_model_settings: JSONDict | None,
    now_ms: int,
) -> tuple[AutomationConversationVersion, ...]:
    if conversation_model_settings is None:
        return ()
    versions = sync_propagate_automation_conversation_model_settings(
        conn,
        prepared.automation_id,
        prepared.user_id,
        conversation_model_settings,
    )
    for version in versions:
        sync_enqueue_conversation_updated_event(
            conn,
            created_at_ms=now_ms,
            user_id=prepared.user_id,
            conv_id=version.conv_id,
            last_modified_at_ms=version.last_modified_at_ms,
            model_settings=conversation_model_settings,
            settings_authority_changed=True,
        )
    return versions


def sync_commit_automation_update(
    conn: sqlite3.Connection,
    prepared: AutomationPreparedUpdate,
    conversation_model_settings: JSONDict | None,
    disallowed_unqualified_tools: tuple[str, ...],
) -> AutomationUpdateResult:
    current = sync_get_automation(conn, prepared.automation_id, prepared.user_id)
    if current is None:
        return AutomationUpdateResult(automation=None)
    require_automation_revision_match(current, prepared.expected_revision)
    if (prepared.model_settings is None) != (conversation_model_settings is None):
        raise StateError("Automation conversation settings preparation is incomplete.")
    now_ms = epoch_ms()
    updated = _commit_definition_update(
        conn,
        prepared=prepared,
        current=current,
        disallowed_unqualified_tools=disallowed_unqualified_tools,
        now_ms=now_ms,
    )
    _validate_prepared_settings(prepared, current, updated)
    abandoned_run_ids, abandoned_owner_task_ids = _recover_disabled_run_ownership(
        conn,
        prepared=prepared,
        current=current,
        updated=updated,
        now_ms=now_ms,
    )
    versions = _propagate_conversation_settings(
        conn,
        prepared=prepared,
        conversation_model_settings=conversation_model_settings,
        now_ms=now_ms,
    )
    return AutomationUpdateResult(
        automation=updated,
        conversation_versions=versions,
        abandoned_run_ids=tuple(abandoned_run_ids),
        abandoned_owner_task_ids=tuple(abandoned_owner_task_ids),
    )

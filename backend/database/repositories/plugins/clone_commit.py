"""SoAI - Atomic plugin clone logical commit [backend/database/repositories/plugins/clone_commit.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.database.clone_requests import (
    CLONE_PROVISIONAL_STATE,
    CloneCommitOutboxRecord,
    CloneCommitRequest,
)
from core.errors.exceptions import StateError, ValidationError
from core.mutations.identifiers import require_mutation_request_id
from core.plugins.portable_identifiers import require_portable_plugin_identifier
from core.serialization.json_parsing import parse_json_dict
from core.state.state_names import resolve_plugin_runtime_state_name
from core.tasks.status_policy import ACTIVE_TASK_STATUS_VALUES, active_task_status_placeholders
from core.types.json import JSONDict
from core.validation.epoch import require_unix_epoch_ms
from core.validation.strict_numbers import require_positive_int_strict
from core.validation.strings import require_canonical_trimmed_json_text
from database.core.savepoints import SQLiteSavepoint

__all__ = ("sync_commit_clone_transaction",)

_REQUIRED_DOMAIN_EVENT_TYPES = (
    "PluginLoadedEvent",
    "TriggerConfigReconciliationCommand",
    "TaskCompleteEvent",
)


def _validate_outbox_record(record: CloneCommitOutboxRecord) -> JSONDict:
    event_id = require_canonical_trimmed_json_text(
        record.event_id,
        error_message="Clone commit outbox event identity is invalid.",
    )
    require_canonical_trimmed_json_text(
        record.event_type,
        error_message="Clone commit outbox event type is invalid.",
    )
    payload = parse_json_dict(record.payload_json, field="clone_commit_outbox_payload")
    if payload.get("event_id") != event_id:
        raise ValidationError("Clone commit outbox payload identity is invalid.")
    return payload


def _validate_domain_events(request: CloneCommitRequest) -> None:
    if tuple(record.event_type for record in request.domain_events) != _REQUIRED_DOMAIN_EVENT_TYPES:
        raise ValidationError("Clone commit domain events are invalid.")
    payloads = tuple(_validate_outbox_record(record) for record in request.domain_events)
    if any(payload.get("timestamp") != request.completed_at_ms / 1000.0 for payload in payloads):
        raise ValidationError("Clone commit domain event timestamp is invalid.")
    loaded, reconciliation, completion = payloads
    user_id = completion.get("user_id")
    if loaded.get("plugin_name") != request.target_plugin_name:
        raise ValidationError("Clone commit domain event target is invalid.")
    if reconciliation.get("reason") != f"plugin_cloned:{request.target_plugin_name}":
        raise ValidationError("Clone commit domain event target is invalid.")
    if completion.get("success") is not True:
        raise ValidationError("Clone commit terminal task event is invalid.")
    if completion.get("message") != request.task_status_message:
        raise ValidationError("Clone commit terminal task event is invalid.")
    if completion.get("task_id") != request.task_id:
        raise ValidationError("Clone commit terminal task event is invalid.")
    if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id < 0:
        raise ValidationError("Clone commit terminal task event is invalid.")
    if completion.get("status") != "completed":
        raise ValidationError("Clone commit terminal task event is invalid.")
    if completion.get("error_code") is not None:
        raise ValidationError("Clone commit terminal task event is invalid.")
    if completion.get("error_message") is not None:
        raise ValidationError("Clone commit terminal task event is invalid.")


def _validate_request(request: CloneCommitRequest) -> None:
    require_mutation_request_id(request.task_id)
    require_portable_plugin_identifier(
        request.target_plugin_name,
        field_name="target_plugin_name",
    )
    require_positive_int_strict(
        request.fencing_token,
        error_message="Clone commit requires a positive fencing token.",
    )
    ready_state = resolve_plugin_runtime_state_name(request.ready_state)
    if ready_state is None or ready_state != request.ready_state:
        raise ValidationError("Clone commit requires a ready plugin state.")
    require_unix_epoch_ms(
        request.completed_at_ms,
        error_message="Clone commit requires a positive completion timestamp.",
    )
    require_canonical_trimmed_json_text(
        request.task_status_message,
        error_message="Clone commit requires a terminal status message.",
    )
    task_result = parse_json_dict(request.task_result_json, field="clone_commit_task_result")
    if task_result.get("target_plugin") != request.target_plugin_name:
        raise ValidationError("Clone commit task result target is invalid.")
    _validate_outbox_record(request.authoritative_event)
    _validate_domain_events(request)
    event_ids = (request.authoritative_event.event_id,) + tuple(
        record.event_id for record in request.domain_events
    )
    if len(event_ids) != len(set(event_ids)):
        raise ValidationError("Clone commit outbox event identities must be unique.")


def _preconditions_hold(
    connection: sqlite3.Connection,
    request: CloneCommitRequest,
) -> bool:
    row = connection.execute(
        """SELECT clone.phase, clone.committed, plugin.state, admission.lifecycle_status,
            admission.fencing_token, admission.claim_owner, admission.lease_expires_at_ms,
            task.status
        FROM plugin_clone_transactions AS clone
        JOIN plugin_clone_target_reservations AS reservation ON reservation.task_id = clone.task_id
        JOIN plugins_catalog AS plugin ON plugin.plugin_name = clone.target_plugin_name
        JOIN mutation_admissions AS admission ON admission.accepted_task_id = clone.task_id
        JOIN unified_tasks AS task ON task.task_id = clone.task_id
        WHERE clone.task_id = ? AND clone.target_plugin_name = ?
            AND reservation.target_plugin_name = clone.target_plugin_name""",
        (request.task_id, request.target_plugin_name),
    ).fetchone()
    if row is None:
        return False
    return (
        row["phase"] == "registering"
        and row["committed"] == 0
        and row["state"] == CLONE_PROVISIONAL_STATE
        and row["lifecycle_status"] == "running"
        and row["fencing_token"] == request.fencing_token
        and row["claim_owner"] is not None
        and row["status"] in ACTIVE_TASK_STATUS_VALUES
    )


def _insert_authoritative_event(
    connection: sqlite3.Connection,
    request: CloneCommitRequest,
) -> None:
    record = request.authoritative_event
    connection.execute(
        """INSERT INTO plugin_authoritative_state_outbox (
            event_id, plugin_name, event_type, payload_json, created_at_ms,
            status, attempts, next_attempt_at_ms
        ) VALUES (?, ?, ?, ?, ?, 'pending', 0, 0)""",
        (
            record.event_id,
            request.target_plugin_name,
            record.event_type,
            record.payload_json,
            request.completed_at_ms,
        ),
    )


def _insert_domain_events(
    connection: sqlite3.Connection,
    request: CloneCommitRequest,
) -> None:
    connection.executemany(
        """INSERT INTO webui_domain_event_outbox (
            event_id, event_type, payload_json, created_at_ms,
            status, attempts, next_attempt_at_ms
        ) VALUES (?, ?, ?, ?, 'pending', 0, 0)""",
        (
            (
                record.event_id,
                record.event_type,
                record.payload_json,
                request.completed_at_ms,
            )
            for record in request.domain_events
        ),
    )


def _apply_commit(connection: sqlite3.Connection, request: CloneCommitRequest) -> None:
    plugin_updated = connection.execute(
        """UPDATE plugins_catalog SET state = ?, last_seen_at_ms = ?
        WHERE plugin_name = ? AND state = ?""",
        (
            request.ready_state,
            request.completed_at_ms,
            request.target_plugin_name,
            CLONE_PROVISIONAL_STATE,
        ),
    ).rowcount
    if plugin_updated != 1:
        raise StateError("Clone provisional plugin record could not be promoted.")
    _insert_authoritative_event(connection, request)
    _insert_domain_events(connection, request)
    task_updated = connection.execute(
        f"""UPDATE unified_tasks SET status = 'completed', result = ?, error_code = NULL,
            error_message = NULL, status_message = ?, updated_at_ms = ?, completed_at_ms = ?,
            orchestration_state = NULL,
            progress_current = CASE WHEN progress_total IS NOT NULL THEN progress_total
                ELSE progress_current END
        WHERE task_id = ? AND status IN ({active_task_status_placeholders()})""",
        (
            request.task_result_json,
            request.task_status_message,
            request.completed_at_ms,
            request.completed_at_ms,
            request.task_id,
            *ACTIVE_TASK_STATUS_VALUES,
        ),
    ).rowcount
    admission = connection.execute(
        """UPDATE mutation_admissions SET lifecycle_status = 'completed', terminal_result = ?,
            completed_at_ms = ?, claim_owner = NULL, lease_expires_at_ms = NULL,
            recovery_payload_encrypted = NULL
        WHERE request_id = ? AND accepted_task_id = ? AND lifecycle_status = 'running'
            AND fencing_token = ? AND claim_owner IS NOT NULL RETURNING request_id""",
        (
            request.task_result_json,
            request.completed_at_ms,
            request.task_id,
            request.task_id,
            request.fencing_token,
        ),
    ).fetchone()
    if task_updated != 1 or admission is None:
        raise StateError("Clone task or mutation admission could not be terminalized.")
    connection.execute(
        "DELETE FROM mutation_conflict_keys WHERE request_id = ?",
        (admission["request_id"],),
    )
    connection.execute(
        "DELETE FROM plugin_clone_target_reservations WHERE task_id = ?",
        (request.task_id,),
    )
    clone_updated = connection.execute(
        """UPDATE plugin_clone_transactions SET phase = 'committed', committed = 1
        WHERE task_id = ? AND phase = 'registering' AND committed = 0""",
        (request.task_id,),
    ).rowcount
    if clone_updated != 1:
        raise StateError("Clone journal could not reach its logical commit point.")


def sync_commit_clone_transaction(
    connection: sqlite3.Connection,
    request: CloneCommitRequest,
) -> bool:
    _validate_request(request)
    if not _preconditions_hold(connection, request):
        return False
    with SQLiteSavepoint(connection, "plugin_clone_commit"):
        _apply_commit(connection, request)
    return True

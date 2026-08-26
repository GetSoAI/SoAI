"""SoAI - Atomic licensing deactivation and rehost completion [backend/database/repositories/licensing/deactivation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hmac
import sqlite3
from collections.abc import Sequence

from cryptography.fernet import Fernet

from core.errors.exceptions import ConcurrencyError, StateError
from core.events.domain_event_payload import build_domain_event_payload
from core.licensing.deployment_transition import prepare_deployment_rehost_transition
from database.core.savepoints import SQLiteSavepoint
from database.repositories.event_outbox.sync_ops import sync_ensure_domain_event_payload
from database.repositories.licensing.deployment_identity import sync_rotate_deployment_identity
from database.repositories.licensing.operations import sync_complete_licensing_operation


def sync_complete_deactivation_operation(
    connection: sqlite3.Connection,
    fernets: Sequence[Fernet],
    operation_id: str,
    expected_state: str,
    deployment_id: str,
    response_content: bytes,
    completed_at_ms: int,
) -> None:
    with SQLiteSavepoint(connection, "licensing_deactivation_completion"):
        operation = connection.execute(
            """SELECT operation_type, state, instance_id, deployment_id,
            deactivation_reason FROM licensing_operations WHERE operation_id=?""",
            (operation_id,),
        ).fetchone()
        if operation is None:
            raise StateError("Licensing deactivation operation is unavailable.")
        if (
            operation[0] != "deactivation"
            or operation[1] != expected_state
            or operation[3] != deployment_id
            or operation[4] not in {"rehost", "retired", "disaster_recovery", "other"}
        ):
            raise ConcurrencyError("Licensing deactivation operation binding changed.")
        identity = connection.execute(
            "SELECT public_key FROM licensing_deployment_identity WHERE singleton=1"
        ).fetchone()
        if identity is None:
            raise StateError("Licensing deployment identity is unavailable.")
        active = connection.execute(
            """SELECT COUNT(*) FROM licensing_documents
            WHERE disposition='active' AND document_type!='licensing_status'
              AND deployment_id=?""",
            (deployment_id,),
        ).fetchone()
        if active is None or active[0] != 1:
            raise StateError("Licensing deactivation has no unique active entitlement.")
        if operation[4] == "rehost":
            rotation = sync_rotate_deployment_identity(
                connection,
                fernets,
                expected_public_key=bytes(identity[0]),
                created_at_ms=completed_at_ms,
            )
            transition = prepare_deployment_rehost_transition(
                rotation.old_keypair.private_key,
                operation_id=operation_id,
                instance_id=str(operation[2]),
                deployment_id=deployment_id,
                new_public_key=rotation.new_public_key,
                completed_at_ms=completed_at_ms,
            )
            connection.execute(
                """INSERT INTO licensing_deployment_transitions (
                operation_id, instance_id, deployment_id, old_public_key, new_public_key,
                canonical_transition, completed_at_ms) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    transition.operation_id,
                    transition.instance_id,
                    transition.deployment_id,
                    transition.old_public_key,
                    transition.new_public_key,
                    transition.canonical_document,
                    transition.completed_at_ms,
                ),
            )
            _remove_offline_request(connection, bytes(identity[0]))
        updated = connection.execute(
            """UPDATE licensing_documents SET disposition='historical'
            WHERE disposition='active' AND deployment_id=?""",
            (deployment_id,),
        ).rowcount
        if updated < 1:
            raise StateError("Licensing deactivation lost its active document.")
        sync_complete_licensing_operation(
            connection,
            operation_id,
            expected_state,
            response_content,
            completed_at_ms,
        )
        sync_ensure_domain_event_payload(
            connection,
            event_type="LicensingStatusChangedEvent",
            payload=build_domain_event_payload(
                event_id=f"licensing:deactivation:{operation_id}",
                timestamp_unix=completed_at_ms / 1000.0,
                fields={},
            ),
            created_at_ms=completed_at_ms,
        )


def _remove_offline_request(connection: sqlite3.Connection, public_key: bytes) -> None:
    request = connection.execute(
        "SELECT deployment_public_key FROM licensing_offline_requests WHERE singleton=1"
    ).fetchone()
    if request is None:
        return
    if not hmac.compare_digest(bytes(request[0]), public_key):
        raise StateError("Stored offline request does not match the deployment identity.")
    connection.execute("DELETE FROM licensing_offline_requests WHERE singleton=1")


__all__ = ("sync_complete_deactivation_operation",)

"""SoAI - Atomic licensing document promotion [backend/database/repositories/licensing/documents.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ConcurrencyError, StateError, ValidationError
from core.events.domain_event_payload import build_domain_event_payload
from core.licensing.storage_records import StoredLicensingDocument
from database.core.savepoints import SQLiteSavepoint
from database.repositories.event_outbox.sync_ops import sync_ensure_domain_event_payload
from database.repositories.licensing.operations import sync_complete_licensing_operation
from database.repositories.licensing.wizard import sync_mark_wizard_access_ready
from database.repositories.users.user_count_queries import (
    sync_require_uninitialized_bootstrap_state,
)

if TYPE_CHECKING:
    from database.core.sqlite_values import SQLiteValue


def _require_advancing_generation(
    connection: sqlite3.Connection,
    deployment_id: str,
    generation: int,
) -> None:
    generation_high_water = connection.execute(
        "SELECT MAX(generation) FROM licensing_documents WHERE deployment_id = ?",
        (deployment_id,),
    ).fetchone()[0]
    if generation_high_water is not None and generation <= int(generation_high_water):
        raise ValidationError("Licensing document generation does not advance.")


def sync_promote_licensing_document(
    connection: sqlite3.Connection,
    document: StoredLicensingDocument,
) -> None:
    values = _document_storage_values(document)
    existing = connection.execute(
        """SELECT canonical_content, document_type, entitlement_type, entitlement_id,
        license_id, deployment_id, generation, issuer_authorization_snapshot, accepted_at_ms
        FROM licensing_documents WHERE document_digest = ?""",
        (document.document_digest,),
    ).fetchone()
    if existing is not None:
        if tuple(existing) != values:
            raise StateError("Licensing document digest identity collided.")
        return
    _require_advancing_generation(connection, document.deployment_id, document.generation)
    with SQLiteSavepoint(connection, "licensing_document_promotion"):
        if document.document_type == "licensing_status":
            connection.execute("""UPDATE licensing_documents SET disposition = 'historical'
                WHERE disposition = 'active' AND document_type = 'licensing_status'""")
        else:
            connection.execute(
                "UPDATE licensing_documents SET disposition = 'historical' WHERE disposition = 'active'"
            )
        connection.execute(
            """INSERT INTO licensing_documents (
            document_digest, canonical_content, document_type, entitlement_type,
            entitlement_id, license_id, deployment_id, generation, disposition,
            issuer_authorization_snapshot, accepted_at_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)""",
            (document.document_digest, *values),
        )
        sync_ensure_domain_event_payload(
            connection,
            event_type="LicensingStatusChangedEvent",
            payload=build_domain_event_payload(
                event_id=f"licensing:{document.document_digest}",
                timestamp_unix=document.accepted_at_ms / 1000.0,
                fields={},
            ),
            created_at_ms=document.accepted_at_ms,
        )


def sync_store_pending_licensing_document(
    connection: sqlite3.Connection,
    document: StoredLicensingDocument,
) -> None:
    values = _document_storage_values(document)
    existing = connection.execute(
        """SELECT canonical_content, document_type, entitlement_type, entitlement_id,
        license_id, deployment_id, generation, issuer_authorization_snapshot, accepted_at_ms,
        disposition FROM licensing_documents WHERE document_digest = ?""",
        (document.document_digest,),
    ).fetchone()
    if existing is not None:
        if tuple(existing[:9]) != values or existing[9] != "pending":
            raise StateError("Licensing document digest identity collided.")
        return
    _require_advancing_generation(connection, document.deployment_id, document.generation)
    connection.execute(
        "UPDATE licensing_documents SET disposition = 'historical' WHERE disposition = 'pending'"
    )
    connection.execute(
        """INSERT INTO licensing_documents (
        document_digest, canonical_content, document_type, entitlement_type,
        entitlement_id, license_id, deployment_id, generation, disposition,
        issuer_authorization_snapshot, accepted_at_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
        (document.document_digest, *values),
    )


def _document_storage_values(document: StoredLicensingDocument) -> tuple[SQLiteValue, ...]:
    return (
        document.canonical_content,
        document.document_type,
        document.entitlement_type,
        document.entitlement_id,
        document.license_id,
        document.deployment_id,
        document.generation,
        document.issuer_authorization_snapshot,
        document.accepted_at_ms,
    )


def sync_accept_entitlement_operation(
    connection: sqlite3.Connection,
    operation_id: str,
    expected_operation_state: str,
    response_content: bytes,
    document: StoredLicensingDocument,
    disposition: str,
    edition: str,
    expected_draft_revision: int,
) -> None:
    if disposition not in {"active", "pending"}:
        raise ValidationError("Licensing document disposition is invalid.")
    with SQLiteSavepoint(connection, "licensing_operation_document_acceptance"):
        if disposition == "pending":
            sync_require_uninitialized_bootstrap_state(connection)
        store_document = (
            sync_promote_licensing_document
            if disposition == "active"
            else sync_store_pending_licensing_document
        )
        store_document(
            connection,
            document,
        )
        if disposition == "pending":
            sync_mark_wizard_access_ready(
                connection,
                edition=edition,
                expected_revision=expected_draft_revision,
                changed_at_ms=document.accepted_at_ms,
            )
        sync_complete_licensing_operation(
            connection,
            operation_id,
            expected_operation_state,
            response_content,
            document.accepted_at_ms,
        )


def sync_accept_licensing_status_operation(
    connection: sqlite3.Connection,
    operation_id: str,
    expected_operation_state: str,
    response_content: bytes,
    document: StoredLicensingDocument,
) -> None:
    with SQLiteSavepoint(connection, "licensing_status_operation_acceptance"):
        sync_promote_licensing_document(
            connection,
            document,
        )
        sync_complete_licensing_operation(
            connection,
            operation_id,
            expected_operation_state,
            response_content,
            document.accepted_at_ms,
        )


def sync_promote_pending_document_for_completion(
    connection: sqlite3.Connection,
    *,
    expected_document_digest: str,
    accepted_at_ms: int,
) -> None:
    pending = connection.execute(
        "SELECT document_digest FROM licensing_documents WHERE disposition = 'pending'"
    ).fetchall()
    if len(pending) != 1:
        raise StateError("Licensed setup requires exactly one pending entitlement.")
    document_digest = str(pending[0][0])
    if document_digest != expected_document_digest:
        raise ConcurrencyError("Pending licensing document changed during setup completion.")
    connection.execute(
        "UPDATE licensing_documents SET disposition = 'historical' WHERE disposition = 'active'"
    )
    updated = connection.execute(
        """UPDATE licensing_documents SET disposition = 'active'
        WHERE document_digest = ? AND disposition = 'pending'""",
        (document_digest,),
    ).rowcount
    if updated != 1:
        raise ConcurrencyError("Pending licensing document changed during setup completion.")
    sync_ensure_domain_event_payload(
        connection,
        event_type="LicensingStatusChangedEvent",
        payload=build_domain_event_payload(
            event_id=f"licensing:{document_digest}",
            timestamp_unix=accepted_at_ms / 1000.0,
            fields={},
        ),
        created_at_ms=accepted_at_ms,
    )


__all__ = (
    "sync_accept_entitlement_operation",
    "sync_accept_licensing_status_operation",
    "sync_promote_licensing_document",
    "sync_promote_pending_document_for_completion",
    "sync_store_pending_licensing_document",
)

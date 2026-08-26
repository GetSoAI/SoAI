"""SoAI - Durable offline activation exports [backend/database/repositories/licensing/offline_requests.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hmac
import sqlite3
from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import ConflictError, StateError, ValidationError
from core.licensing.storage_records import (
    LicensingOperationInsert,
    OfflineRequestInsert,
    OfflineRequestRecord,
    StoredLicensingDocument,
)
from database.core.query_execution import query_one_to_dict, sync_fetch_one_as_dict
from database.core.savepoints import SQLiteSavepoint
from database.core.sqlite_row_scalars import (
    require_sqlite_row_bytes,
    require_sqlite_row_int,
    require_sqlite_row_str,
    sqlite_row_optional_int,
)
from database.repositories.licensing.access_operation_supersession import (
    sync_supersede_access_operation,
)
from database.repositories.licensing.documents import (
    sync_promote_licensing_document,
    sync_store_pending_licensing_document,
)
from database.repositories.licensing.offline_replacements import (
    require_advancing_offline_replacement,
)
from database.repositories.licensing.operations import (
    sync_create_licensing_operation,
    sync_transition_licensing_operation,
)
from database.repositories.licensing.wizard import (
    sync_mark_wizard_access_ready,
    sync_read_wizard_draft,
)

if TYPE_CHECKING:
    from database.core.sqlite_values import SQLiteRow


def sync_get_or_create_offline_request(
    connection: sqlite3.Connection,
    candidate: OfflineRequestInsert,
) -> OfflineRequestRecord:
    existing = _read_offline_request(connection)
    offline_dispositions = _offline_document_dispositions(connection)
    live_offline_binding = bool(offline_dispositions & {"active", "pending"})
    if existing is None and live_offline_binding:
        raise StateError("A live offline entitlement has no request binding.")
    if existing is not None:
        binding_changed = (
            existing.draft_revision != candidate.draft_revision
            or existing.edition != candidate.edition
            or existing.licensed_product_scope != candidate.licensed_product_scope
            or existing.instance_id != candidate.instance_id
            or not hmac.compare_digest(
                existing.deployment_public_key, candidate.deployment_public_key
            )
        )
        if existing.fulfilled_at_ms is None:
            if live_offline_binding:
                raise StateError("A live offline entitlement has an unfulfilled request binding.")
            if not binding_changed:
                return existing
        else:
            if not offline_dispositions:
                raise StateError("A fulfilled offline request has no entitlement record.")
            if live_offline_binding:
                if binding_changed:
                    raise ConflictError(
                        "The live offline entitlement request binding is immutable."
                    )
                return existing
    with SQLiteSavepoint(connection, "offline_activation_export"):
        if existing is not None:
            connection.execute("DELETE FROM licensing_offline_requests WHERE singleton = 1")
        sync_supersede_access_operation(
            connection,
            "offline_export",
            candidate.created_at_ms,
        )
        sync_create_licensing_operation(
            connection,
            LicensingOperationInsert(
                operation_id=candidate.operation_id,
                operation_type="offline_export",
                idempotency_key=None,
                request_digest=candidate.request_digest,
                canonical_request=None,
                edition=candidate.edition,
                licensed_product_scope=candidate.licensed_product_scope,
                instance_id=candidate.instance_id,
                created_at_ms=candidate.created_at_ms,
            ),
        )
        connection.execute(
            """INSERT INTO licensing_offline_requests (
            singleton, operation_id, draft_revision, edition, licensed_product_scope, instance_id,
            deployment_public_key, request_digest, canonical_content, created_at_ms,
            fulfilled_at_ms
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)""",
            (
                candidate.operation_id,
                candidate.draft_revision,
                candidate.edition,
                candidate.licensed_product_scope,
                candidate.instance_id,
                candidate.deployment_public_key,
                candidate.request_digest,
                candidate.canonical_content,
                candidate.created_at_ms,
            ),
        )
        sync_transition_licensing_operation(
            connection,
            candidate.operation_id,
            expected_state="prepared",
            target_state="succeeded",
            updated_at_ms=candidate.created_at_ms,
        )
    created = _read_offline_request(connection)
    if created is None:
        raise ConflictError("Offline activation request was not persisted.")
    return created


def _offline_document_dispositions(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute("""SELECT disposition FROM licensing_documents
        WHERE document_type = 'offline_entitlement'""").fetchall()
    dispositions = {str(row[0]) for row in rows}
    if not dispositions.issubset({"active", "pending", "historical"}):
        raise StateError("Stored offline entitlement disposition is invalid.")
    return dispositions


def sync_accept_offline_entitlement(
    connection: sqlite3.Connection,
    operation_id: str,
    expected_draft_revision: int,
    edition: str,
    document_digest: str,
    canonical_content: bytes,
    entitlement_type: str,
    allocation_id: str,
    license_id: str,
    deployment_id: str,
    generation: int,
    root_snapshot: bytes,
    accepted_at_ms: int,
    disposition: str,
) -> None:
    if disposition not in {"active", "pending"}:
        raise ValidationError("Offline entitlement disposition is invalid.")
    with SQLiteSavepoint(connection, "offline_entitlement_import"):
        request = _read_offline_request(connection)
        if request is None:
            raise ConflictError("Offline activation request is unavailable.")
        if request.draft_revision != expected_draft_revision or request.edition != edition:
            raise ConflictError("Offline activation request binding changed.")
        draft = sync_read_wizard_draft(connection, edition)
        if draft["revision"] != expected_draft_revision:
            raise ConflictError("Offline activation draft binding changed.")
        replacement = request.fulfilled_at_ms is not None
        if replacement and not require_advancing_offline_replacement(
            connection,
            document_digest=document_digest,
            canonical_content=canonical_content,
            entitlement_type=entitlement_type,
            allocation_id=allocation_id,
            license_id=license_id,
            deployment_id=deployment_id,
            generation=generation,
            disposition=disposition,
        ):
            return
        sync_supersede_access_operation(
            connection,
            "offline_import",
            accepted_at_ms,
        )
        sync_create_licensing_operation(
            connection,
            LicensingOperationInsert(
                operation_id=operation_id,
                operation_type="offline_import",
                idempotency_key=None,
                request_digest=request.request_digest,
                canonical_request=None,
                edition=request.edition,
                licensed_product_scope=request.licensed_product_scope,
                instance_id=request.instance_id,
                created_at_ms=accepted_at_ms,
                parent_operation_id=request.operation_id,
                deployment_id=deployment_id,
            ),
        )
        store = (
            sync_promote_licensing_document
            if disposition == "active"
            else sync_store_pending_licensing_document
        )
        store(
            connection,
            StoredLicensingDocument(
                document_digest=document_digest,
                canonical_content=canonical_content,
                document_type="offline_entitlement",
                entitlement_type=entitlement_type,
                entitlement_id=allocation_id,
                license_id=license_id,
                deployment_id=deployment_id,
                generation=generation,
                issuer_authorization_snapshot=root_snapshot,
                accepted_at_ms=accepted_at_ms,
            ),
        )
        if not replacement:
            updated = connection.execute(
                """UPDATE licensing_offline_requests SET fulfilled_at_ms = ?
                WHERE singleton = 1 AND fulfilled_at_ms IS NULL""",
                (accepted_at_ms,),
            ).rowcount
            if updated != 1:
                raise ConflictError("Offline activation request was fulfilled concurrently.")
        if disposition == "pending":
            sync_mark_wizard_access_ready(
                connection,
                edition=edition,
                expected_revision=expected_draft_revision,
                changed_at_ms=accepted_at_ms,
            )
        transitioned = sync_transition_licensing_operation(
            connection,
            operation_id,
            expected_state="prepared",
            target_state="succeeded",
            updated_at_ms=accepted_at_ms,
        )
        if not transitioned:
            raise ConflictError("Offline entitlement operation changed concurrently.")


def _read_offline_request(connection: sqlite3.Connection) -> OfflineRequestRecord | None:
    row = sync_fetch_one_as_dict(
        connection.execute("SELECT * FROM licensing_offline_requests WHERE singleton = 1")
    )
    if row is None:
        return None
    return _offline_request_record(row)


async def read_offline_request_query(
    connection: aiosqlite.Connection,
) -> OfflineRequestRecord | None:
    row = await query_one_to_dict(
        connection,
        "SELECT * FROM licensing_offline_requests WHERE singleton = 1",
    )
    if row is None:
        return None
    return _offline_request_record(row)


def _offline_request_record(row: SQLiteRow) -> OfflineRequestRecord:
    label = "Stored offline licensing request"
    return OfflineRequestRecord(
        operation_id=require_sqlite_row_str(row, "operation_id", label=label),
        draft_revision=require_sqlite_row_int(row, "draft_revision", label=label),
        edition=require_sqlite_row_str(row, "edition", label=label),
        licensed_product_scope=require_sqlite_row_str(row, "licensed_product_scope", label=label),
        instance_id=require_sqlite_row_str(row, "instance_id", label=label),
        deployment_public_key=require_sqlite_row_bytes(
            row,
            "deployment_public_key",
            label="Stored offline licensing request",
        ),
        request_digest=require_sqlite_row_str(row, "request_digest", label=label),
        canonical_content=require_sqlite_row_bytes(
            row,
            "canonical_content",
            label="Stored offline licensing request",
        ),
        created_at_ms=require_sqlite_row_int(row, "created_at_ms", label=label),
        fulfilled_at_ms=sqlite_row_optional_int(row, "fulfilled_at_ms", label=label),
    )


__all__ = (
    "OfflineRequestInsert",
    "OfflineRequestRecord",
    "read_offline_request_query",
    "sync_accept_offline_entitlement",
    "sync_get_or_create_offline_request",
)

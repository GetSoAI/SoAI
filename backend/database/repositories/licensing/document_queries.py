"""SoAI - Licensing document read projections [backend/database/repositories/licensing/document_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

import aiosqlite

from core.errors.exceptions import StateError
from core.licensing.storage_records import StoredLicensingDocument
from database.core.sqlite_values import SQLiteValue


async def read_active_document_query(
    connection: aiosqlite.Connection,
) -> StoredLicensingDocument | None:
    return await _read_document(
        connection,
        "disposition = 'active' AND document_type != 'licensing_status'",
    )


async def read_active_status_query(
    connection: aiosqlite.Connection,
) -> StoredLicensingDocument | None:
    return await _read_document(
        connection,
        "disposition = 'active' AND document_type = 'licensing_status'",
    )


async def read_pending_document_query(
    connection: aiosqlite.Connection,
) -> StoredLicensingDocument | None:
    return await _read_document(connection, "disposition = 'pending'")


async def read_latest_document_query(
    connection: aiosqlite.Connection,
    deployment_id: str,
) -> StoredLicensingDocument | None:
    cursor = await connection.execute(
        """SELECT document_digest, canonical_content, document_type, entitlement_type, entitlement_id, license_id,
        deployment_id, generation, issuer_authorization_snapshot, accepted_at_ms FROM licensing_documents
        WHERE deployment_id = ? ORDER BY generation DESC LIMIT 1""",
        (deployment_id,),
    )
    row = await cursor.fetchone()
    await cursor.close()
    return _record(row)


async def _read_document(
    connection: aiosqlite.Connection,
    predicate: str,
) -> StoredLicensingDocument | None:
    if predicate not in {
        "disposition = 'active' AND document_type != 'licensing_status'",
        "disposition = 'active' AND document_type = 'licensing_status'",
        "disposition = 'pending'",
    }:
        raise ValueError("Licensing document query predicate is invalid.")
    cursor = await connection.execute(
        f"""SELECT document_digest, canonical_content, document_type, entitlement_type, entitlement_id, license_id,
        deployment_id, generation, issuer_authorization_snapshot, accepted_at_ms FROM licensing_documents
        WHERE {predicate}"""
    )
    row = await cursor.fetchone()
    await cursor.close()
    return _record(row)


def _record(row: sqlite3.Row | tuple[SQLiteValue, ...] | None) -> StoredLicensingDocument | None:
    if row is None:
        return None
    canonical_content = row[1]
    generation = row[7]
    authorization_snapshot = row[8]
    accepted_at_ms = row[9]
    if not isinstance(canonical_content, bytes) or not isinstance(authorization_snapshot, bytes):
        raise StateError("Stored licensing document fields are invalid.")
    if isinstance(generation, bool) or not isinstance(generation, int):
        raise StateError("Stored licensing document fields are invalid.")
    if isinstance(accepted_at_ms, bool) or not isinstance(accepted_at_ms, int):
        raise StateError("Stored licensing document fields are invalid.")
    return StoredLicensingDocument(
        document_digest=str(row[0]),
        canonical_content=canonical_content,
        document_type=str(row[2]),
        entitlement_type=str(row[3]) if row[3] is not None else None,
        entitlement_id=str(row[4]) if row[4] is not None else None,
        license_id=str(row[5]) if row[5] is not None else None,
        deployment_id=str(row[6]),
        generation=generation,
        issuer_authorization_snapshot=authorization_snapshot,
        accepted_at_ms=accepted_at_ms,
    )


__all__ = (
    "read_active_document_query",
    "read_active_status_query",
    "read_latest_document_query",
    "read_pending_document_query",
)

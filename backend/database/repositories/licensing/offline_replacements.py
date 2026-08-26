"""SoAI - Offline entitlement replacement persistence validation [backend/database/repositories/licensing/offline_replacements.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import ConflictError, StateError
from database.core.query_execution import sync_fetch_one_as_dict
from database.core.sqlite_row_scalars import (
    require_sqlite_row_bytes,
    require_sqlite_row_int,
    require_sqlite_row_str,
)


def require_advancing_offline_replacement(
    connection: sqlite3.Connection,
    *,
    document_digest: str,
    canonical_content: bytes,
    entitlement_type: str,
    allocation_id: str,
    license_id: str,
    deployment_id: str,
    generation: int,
    disposition: str,
) -> bool:
    current = sync_fetch_one_as_dict(
        connection.execute("""SELECT document_digest, canonical_content, entitlement_type,
            entitlement_id, license_id, deployment_id, generation, disposition
            FROM licensing_documents WHERE document_type = 'offline_entitlement'
            AND disposition IN ('active', 'pending')""")
    )
    if current is None:
        raise StateError("A fulfilled offline request has no live entitlement.")
    label = "Offline entitlement"
    stored_binding = (
        require_sqlite_row_str(current, "entitlement_type", label=label),
        require_sqlite_row_str(current, "entitlement_id", label=label),
        require_sqlite_row_str(current, "license_id", label=label),
        require_sqlite_row_str(current, "deployment_id", label=label),
        require_sqlite_row_str(current, "disposition", label=label),
    )
    replacement_binding = (
        entitlement_type,
        allocation_id,
        license_id,
        deployment_id,
        disposition,
    )
    if stored_binding != replacement_binding or entitlement_type != "commercial_term":
        raise ConflictError("Offline entitlement replacement binding changed.")
    current_generation = require_sqlite_row_int(current, "generation", label=label)
    if generation == current_generation:
        current_digest = require_sqlite_row_str(current, "document_digest", label=label)
        current_content = require_sqlite_row_bytes(current, "canonical_content", label=label)
        if document_digest == current_digest and canonical_content == current_content:
            return False
        raise ConflictError("Offline entitlement replacement generation does not advance.")
    if generation < current_generation:
        raise ConflictError("Offline entitlement replacement generation does not advance.")
    return True


__all__ = ("require_advancing_offline_replacement",)

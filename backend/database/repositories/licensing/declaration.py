"""SoAI - Authenticated licensing declaration transaction [backend/database/repositories/licensing/declaration.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import ConcurrencyError, ValidationError
from core.events.domain_event_payload import build_domain_event_payload
from core.licensing.declaration import PERSONAL_USE_ATTESTATION_REVISION
from core.licensing.edition import require_licensing_edition
from core.licensing.storage_records import LicensingWizardDraft
from core.users.bootstrap_state import BootstrapState
from database.core.savepoints import SQLiteSavepoint
from database.repositories.event_outbox.sync_ops import sync_ensure_domain_event_payload
from database.repositories.licensing.access_operation_supersession import (
    sync_cancel_access_operation,
)
from database.repositories.licensing.wizard import sync_read_wizard_draft
from database.repositories.users.user_count_queries import sync_read_bootstrap_state


def sync_set_authenticated_declaration(
    connection: sqlite3.Connection,
    edition: str,
    expected_revision: int,
    declaration: str,
    attestation_confirmed: bool,
    attestation_revision: str | None,
    expected_active_document_digest: str | None,
    retire_active_entitlement: bool,
    changed_at_ms: int,
    actor_user_id: int,
) -> LicensingWizardDraft:
    require_licensing_edition(edition)
    if sync_read_bootstrap_state(connection) is not BootstrapState.COMPLETE:
        raise ValidationError("Authenticated licensing administration is unavailable.")
    if declaration not in {"personal", "organization_commercial"}:
        raise ValidationError("Licensing use declaration is invalid.")
    if declaration == "personal":
        if (
            attestation_confirmed is not True
            or attestation_revision != PERSONAL_USE_ATTESTATION_REVISION
        ):
            raise ValidationError("Current personal-use attestation confirmation is required.")
        stored_revision = PERSONAL_USE_ATTESTATION_REVISION
        confirmed_at: int | None = changed_at_ms
    else:
        if attestation_confirmed is not False or attestation_revision is not None:
            raise ValidationError("Organizational use cannot carry a personal attestation.")
        stored_revision = None
        confirmed_at = None
    with SQLiteSavepoint(connection, "licensing_authenticated_declaration"):
        sync_cancel_access_operation(connection, changed_at_ms)
        active_document = connection.execute("""SELECT document_digest FROM licensing_documents
            WHERE disposition = 'active' AND document_type != 'licensing_status'""").fetchone()
        active_digest = str(active_document[0]) if active_document is not None else None
        if active_digest != expected_active_document_digest:
            raise ConcurrencyError("Active licensing entitlement changed.")
        if retire_active_entitlement:
            connection.execute("""UPDATE licensing_documents SET disposition = 'historical'
                WHERE disposition = 'active'""")
        updated = connection.execute(
            """UPDATE licensing_wizard_draft SET revision = revision + 1,
            declaration = ?, attestation_revision = ?, attestation_confirmed_at_ms = ?,
            evaluation_fingerprint = NULL, evaluation_acknowledged_at_ms = NULL,
            selected_access_flow = NULL, resume_step = 'complete', updated_at_ms = ?
            WHERE singleton = 1 AND edition = ? AND revision = ?
            AND accepted_license_fingerprint IS NOT NULL""",
            (
                declaration,
                stored_revision,
                confirmed_at,
                changed_at_ms,
                edition,
                expected_revision,
            ),
        ).rowcount
        if updated != 1:
            raise ConcurrencyError("Licensing state changed before declaration update.")
        connection.execute(
            """INSERT INTO licensing_acceptance_history (
            actor_user_id, event_type, edition, fingerprint, declaration, occurred_at_ms
            ) VALUES (?, 'declaration', ?, NULL, ?, ?)""",
            (actor_user_id, edition, declaration, changed_at_ms),
        )
        sync_ensure_domain_event_payload(
            connection,
            event_type="LicensingStatusChangedEvent",
            payload=build_domain_event_payload(
                event_id=f"licensing:declaration:{expected_revision + 1}",
                timestamp_unix=changed_at_ms / 1000.0,
                fields={},
            ),
            created_at_ms=changed_at_ms,
        )
    return sync_read_wizard_draft(connection, edition)


__all__ = ("sync_set_authenticated_declaration",)

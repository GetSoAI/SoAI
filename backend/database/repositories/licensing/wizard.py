"""SoAI - Revisioned licensing wizard persistence [backend/database/repositories/licensing/wizard.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
import sqlite3

import aiosqlite

from core.errors.exceptions import ConcurrencyError, ValidationError
from core.licensing.declaration import PERSONAL_USE_ATTESTATION_REVISION
from core.licensing.edition import require_licensing_edition
from core.licensing.storage_records import LicensingWizardDraft
from database.core.query_execution import query_one_to_dict, sync_fetch_one_as_dict
from database.core.row_materialization import sqlite_row_dict_to_json_dict
from database.core.savepoints import SQLiteSavepoint
from database.repositories.licensing.access_operation_supersession import (
    sync_cancel_access_operation,
    sync_supersede_access_operation,
)
from database.repositories.licensing.wizard_draft_records import (
    licensing_wizard_draft_from_row,
)
from database.repositories.users.user_count_queries import (
    sync_require_uninitialized_bootstrap_state,
)

__all__ = (
    "read_wizard_draft_query",
    "sync_begin_wizard_access",
    "sync_begin_wizard_evaluation",
    "sync_mark_wizard_access_ready",
    "sync_read_wizard_draft",
    "sync_set_wizard_use",
)


def _empty_wizard_draft(edition: str) -> LicensingWizardDraft:
    return {
        "singleton": 1,
        "edition": edition,
        "revision": 0,
        "accepted_license_fingerprint": None,
        "accepted_license_at_ms": None,
        "declaration": None,
        "attestation_revision": None,
        "attestation_confirmed_at_ms": None,
        "evaluation_fingerprint": None,
        "evaluation_acknowledged_at_ms": None,
        "selected_access_flow": None,
        "resume_step": "license",
        "created_at_ms": None,
        "updated_at_ms": None,
    }


def sync_read_wizard_draft(connection: sqlite3.Connection, edition: str) -> LicensingWizardDraft:
    require_licensing_edition(edition)
    raw_row = sync_fetch_one_as_dict(
        connection.execute("SELECT * FROM licensing_wizard_draft WHERE singleton = 1")
    )
    row = sqlite_row_dict_to_json_dict(raw_row) if raw_row is not None else None
    if row is not None:
        if row["edition"] != edition:
            raise ValidationError(
                "Licensing wizard edition snapshot does not match runtime edition."
            )
        return licensing_wizard_draft_from_row(row)
    return _empty_wizard_draft(edition)


async def read_wizard_draft_query(
    connection: aiosqlite.Connection,
    edition: str,
) -> LicensingWizardDraft:
    require_licensing_edition(edition)
    row = await query_one_to_dict(
        connection,
        "SELECT * FROM licensing_wizard_draft WHERE singleton = 1",
    )
    if row is None:
        return _empty_wizard_draft(edition)
    converted = sqlite_row_dict_to_json_dict(row)
    if converted["edition"] != edition:
        raise ValidationError("Licensing wizard edition snapshot does not match runtime edition.")
    return licensing_wizard_draft_from_row(converted)


def sync_set_wizard_use(
    connection: sqlite3.Connection,
    edition: str,
    expected_revision: int,
    declaration: str,
    attestation_confirmed: bool,
    attestation_revision: str | None,
    confirmed_at_ms: int,
    actor_user_id: int | None,
) -> LicensingWizardDraft:
    require_licensing_edition(edition)
    if declaration not in {"personal", "organization_commercial"}:
        raise ValidationError("Licensing use declaration is invalid.")
    if (
        isinstance(expected_revision, bool)
        or not isinstance(expected_revision, int)
        or expected_revision < 1
        or isinstance(confirmed_at_ms, bool)
        or not isinstance(confirmed_at_ms, int)
    ):
        raise ValidationError("Licensing use mutation input is invalid.")
    if declaration == "personal":
        if (
            attestation_confirmed is not True
            or attestation_revision != PERSONAL_USE_ATTESTATION_REVISION
        ):
            raise ValidationError("Current personal-use attestation confirmation is required.")
        stored_attestation_revision = PERSONAL_USE_ATTESTATION_REVISION
        stored_confirmation_time: int | None = confirmed_at_ms
    else:
        if attestation_confirmed is not False or attestation_revision is not None:
            raise ValidationError("Organizational use cannot carry a personal attestation.")
        stored_attestation_revision = None
        stored_confirmation_time = None
    resume_step = (
        "account" if edition == "soai-core" and declaration == "personal" else "product_access"
    )
    with SQLiteSavepoint(connection, "licensing_wizard_use"):
        sync_require_uninitialized_bootstrap_state(connection)
        current = sync_read_wizard_draft(connection, edition)
        if (
            current["revision"] == expected_revision
            and current["declaration"] == declaration == "organization_commercial"
        ):
            pending_evaluation = connection.execute(
                """SELECT 1 FROM licensing_documents WHERE disposition = 'pending'
                AND entitlement_type = 'organization_evaluation'"""
            ).fetchone()
            if pending_evaluation is not None:
                return current
        sync_cancel_access_operation(connection, confirmed_at_ms)
        updated = connection.execute(
            """UPDATE licensing_wizard_draft SET
            revision = revision + 1, declaration = ?, attestation_revision = ?,
            attestation_confirmed_at_ms = ?, evaluation_fingerprint = NULL,
            evaluation_acknowledged_at_ms = NULL, selected_access_flow = NULL,
            resume_step = ?, updated_at_ms = ?
            WHERE singleton = 1 AND edition = ? AND revision = ?
            AND accepted_license_fingerprint IS NOT NULL""",
            (
                declaration,
                stored_attestation_revision,
                stored_confirmation_time,
                resume_step,
                confirmed_at_ms,
                edition,
                expected_revision,
            ),
        ).rowcount
        if updated != 1:
            raise ConcurrencyError("Licensing wizard state changed or license is not accepted.")
        connection.execute(
            "UPDATE licensing_documents SET disposition = 'historical' WHERE disposition = 'pending'"
        )
        connection.execute(
            """INSERT INTO licensing_acceptance_history (
            actor_user_id, event_type, edition, fingerprint, declaration, occurred_at_ms
            ) VALUES (?, 'declaration', ?, NULL, ?, ?)""",
            (actor_user_id, edition, declaration, confirmed_at_ms),
        )
    return sync_read_wizard_draft(connection, edition)


def sync_begin_wizard_access(
    connection: sqlite3.Connection,
    edition: str,
    expected_revision: int,
    access_flow: str,
    changed_at_ms: int,
) -> LicensingWizardDraft:
    require_licensing_edition(edition)
    if access_flow not in {"online_activation", "offline_activation"}:
        raise ValidationError("Licensing product access flow is invalid.")
    with SQLiteSavepoint(connection, "licensing_wizard_access"):
        sync_require_uninitialized_bootstrap_state(connection)
        current = sync_read_wizard_draft(connection, edition)
        if current["revision"] != expected_revision:
            raise ConcurrencyError("Licensing wizard state changed in another request.")
        if current["selected_access_flow"] == access_flow:
            return current
        if current["accepted_license_fingerprint"] is None or current["declaration"] is None:
            raise ValidationError("Licensing wizard product access prerequisites are missing.")
        sync_supersede_access_operation(
            connection,
            "activation" if access_flow == "online_activation" else "offline_export",
            changed_at_ms,
        )
        updated = connection.execute(
            """UPDATE licensing_wizard_draft SET revision = revision + 1,
            selected_access_flow = ?, evaluation_fingerprint = NULL,
            evaluation_acknowledged_at_ms = NULL, resume_step = 'product_access',
            updated_at_ms = ? WHERE singleton = 1 AND edition = ? AND revision = ?""",
            (access_flow, changed_at_ms, edition, expected_revision),
        ).rowcount
        if updated != 1:
            raise ConcurrencyError("Licensing wizard state changed in another request.")
    return sync_read_wizard_draft(connection, edition)


def sync_begin_wizard_evaluation(
    connection: sqlite3.Connection,
    expected_revision: int,
    terms_fingerprint: str,
    acknowledged_at_ms: int,
) -> LicensingWizardDraft:
    if re.fullmatch(r"sha256:[a-f0-9]{64}", terms_fingerprint) is None:
        raise ValidationError("Evaluation terms fingerprint is invalid.")
    with SQLiteSavepoint(connection, "licensing_wizard_evaluation"):
        sync_require_uninitialized_bootstrap_state(connection)
        sync_supersede_access_operation(
            connection,
            "evaluation",
            acknowledged_at_ms,
        )
        updated = connection.execute(
            """UPDATE licensing_wizard_draft SET revision = revision + 1,
            evaluation_fingerprint = ?, evaluation_acknowledged_at_ms = ?,
            selected_access_flow = 'evaluation', resume_step = 'product_access',
            updated_at_ms = ? WHERE singleton = 1 AND edition = 'soai-core'
            AND declaration = 'organization_commercial'
            AND accepted_license_fingerprint IS NOT NULL AND revision = ?""",
            (terms_fingerprint, acknowledged_at_ms, acknowledged_at_ms, expected_revision),
        ).rowcount
        if updated != 1:
            raise ConcurrencyError("Licensing wizard state changed or prerequisites are missing.")
        connection.execute(
            """INSERT INTO licensing_acceptance_history (
            actor_user_id, event_type, edition, fingerprint, declaration, occurred_at_ms
            ) VALUES (NULL, 'evaluation_acknowledgement', 'soai-core', ?, NULL, ?)""",
            (terms_fingerprint, acknowledged_at_ms),
        )
    return sync_read_wizard_draft(connection, "soai-core")


def sync_mark_wizard_access_ready(
    connection: sqlite3.Connection,
    edition: str,
    expected_revision: int,
    changed_at_ms: int,
) -> None:
    sync_require_uninitialized_bootstrap_state(connection)
    updated = connection.execute(
        """UPDATE licensing_wizard_draft SET resume_step = 'account', updated_at_ms = ?
        WHERE singleton = 1 AND edition = ? AND revision = ?
        AND selected_access_flow IS NOT NULL""",
        (changed_at_ms, edition, expected_revision),
    ).rowcount
    if updated != 1:
        raise ConcurrencyError("Licensing wizard changed before product access completed.")

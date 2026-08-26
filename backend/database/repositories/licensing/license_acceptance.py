"""SoAI - Controlling-license acceptance transactions [backend/database/repositories/licensing/license_acceptance.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
import sqlite3

from core.errors.exceptions import ConcurrencyError, ConflictError, ValidationError
from core.events.domain_event_payload import build_domain_event_payload
from core.licensing.edition import require_licensing_edition
from core.licensing.storage_records import LicensingWizardDraft
from core.users.bootstrap_state import BootstrapState
from core.users.user_id import require_strict_user_id
from database.core.savepoints import SQLiteSavepoint
from database.repositories.event_outbox.sync_ops import sync_ensure_domain_event_payload
from database.repositories.licensing.wizard import sync_read_wizard_draft
from database.repositories.users.user_count_queries import (
    sync_read_bootstrap_state,
    sync_require_uninitialized_bootstrap_state,
)


def _validate_acceptance(
    edition: str,
    expected_revision: int,
    fingerprint: str,
    accepted_at_ms: int,
) -> None:
    require_licensing_edition(edition)
    revision_valid = (
        not isinstance(expected_revision, bool)
        and isinstance(expected_revision, int)
        and expected_revision >= 0
    )
    fingerprint_valid = re.fullmatch(r"sha256:[a-f0-9]{64}", fingerprint) is not None
    accepted_at_valid = (
        not isinstance(accepted_at_ms, bool)
        and isinstance(accepted_at_ms, int)
        and accepted_at_ms >= 0
    )
    if not all((revision_valid, fingerprint_valid, accepted_at_valid)):
        raise ValidationError("Licensing acceptance input is invalid.")


def _insert_initial_draft(
    connection: sqlite3.Connection,
    *,
    edition: str,
    fingerprint: str,
    accepted_at_ms: int,
    resume_step: str,
) -> None:
    try:
        connection.execute(
            """INSERT INTO licensing_wizard_draft (
            singleton, edition, revision, accepted_license_fingerprint,
            accepted_license_at_ms, resume_step, created_at_ms, updated_at_ms
            ) VALUES (1, ?, 1, ?, ?, ?, ?, ?)""",
            (
                edition,
                fingerprint,
                accepted_at_ms,
                resume_step,
                accepted_at_ms,
                accepted_at_ms,
            ),
        )
    except sqlite3.IntegrityError as exception:
        raise ConcurrencyError("Licensing state changed in another request.") from exception


def sync_accept_wizard_license(
    connection: sqlite3.Connection,
    edition: str,
    expected_revision: int,
    fingerprint: str,
    accepted_at_ms: int,
    actor_user_id: int | None,
) -> LicensingWizardDraft:
    _validate_acceptance(edition, expected_revision, fingerprint, accepted_at_ms)
    if actor_user_id is not None:
        raise ValidationError("Initial licensing acceptance cannot have an existing actor.")
    with SQLiteSavepoint(connection, "licensing_wizard_acceptance"):
        sync_require_uninitialized_bootstrap_state(connection)
        if expected_revision == 0:
            _insert_initial_draft(
                connection,
                edition=edition,
                fingerprint=fingerprint,
                accepted_at_ms=accepted_at_ms,
                resume_step="use",
            )
        else:
            updated = connection.execute(
                """UPDATE licensing_wizard_draft SET
                revision = revision + 1,
                accepted_license_fingerprint = ?, accepted_license_at_ms = ?,
                resume_step = 'use', updated_at_ms = ?
                WHERE singleton = 1 AND edition = ? AND revision = ?""",
                (fingerprint, accepted_at_ms, accepted_at_ms, edition, expected_revision),
            ).rowcount
            if updated != 1:
                raise ConcurrencyError("Licensing wizard state changed in another request.")
        _insert_acceptance_history(
            connection,
            actor_user_id=None,
            edition=edition,
            fingerprint=fingerprint,
            accepted_at_ms=accepted_at_ms,
        )
    return sync_read_wizard_draft(connection, edition)


def sync_accept_current_license(
    connection: sqlite3.Connection,
    edition: str,
    expected_revision: int,
    fingerprint: str,
    accepted_at_ms: int,
    actor_user_id: int,
) -> LicensingWizardDraft:
    _validate_acceptance(edition, expected_revision, fingerprint, accepted_at_ms)
    validated_actor_user_id = require_strict_user_id(actor_user_id)
    with SQLiteSavepoint(connection, "licensing_current_acceptance"):
        if sync_read_bootstrap_state(connection) is not BootstrapState.COMPLETE:
            raise ConflictError("Current license acceptance requires completed setup.")
        actor = connection.execute(
            """SELECT 1 FROM webui_users
            WHERE id = ? AND account_type = 'human' AND is_admin = 1""",
            (validated_actor_user_id,),
        ).fetchone()
        if actor is None:
            raise ConflictError("Current license acceptance requires an administrator.")
        draft = sync_read_wizard_draft(connection, edition)
        if draft["revision"] != expected_revision:
            raise ConcurrencyError("Licensing state changed in another request.")
        if (
            draft["accepted_license_fingerprint"] == fingerprint
            and draft["accepted_license_at_ms"] is not None
        ):
            raise ConflictError("The current controlling license is already accepted.")
        if expected_revision == 0:
            _insert_initial_draft(
                connection,
                edition=edition,
                fingerprint=fingerprint,
                accepted_at_ms=accepted_at_ms,
                resume_step="complete",
            )
        else:
            updated = connection.execute(
                """UPDATE licensing_wizard_draft SET revision = revision + 1,
                accepted_license_fingerprint = ?, accepted_license_at_ms = ?,
                resume_step = 'complete', updated_at_ms = ?
                WHERE singleton = 1 AND edition = ? AND revision = ?""",
                (fingerprint, accepted_at_ms, accepted_at_ms, edition, expected_revision),
            ).rowcount
            if updated != 1:
                raise ConcurrencyError("Licensing state changed in another request.")
        _insert_acceptance_history(
            connection,
            actor_user_id=validated_actor_user_id,
            edition=edition,
            fingerprint=fingerprint,
            accepted_at_ms=accepted_at_ms,
        )
        sync_ensure_domain_event_payload(
            connection,
            event_type="LicensingStatusChangedEvent",
            payload=build_domain_event_payload(
                event_id=(
                    f"licensing:acceptance:{validated_actor_user_id}:"
                    f"{expected_revision + 1}:{accepted_at_ms}"
                ),
                timestamp_unix=accepted_at_ms / 1000.0,
                fields={},
            ),
            created_at_ms=accepted_at_ms,
        )
    return sync_read_wizard_draft(connection, edition)


def _insert_acceptance_history(
    connection: sqlite3.Connection,
    *,
    actor_user_id: int | None,
    edition: str,
    fingerprint: str,
    accepted_at_ms: int,
) -> None:
    connection.execute(
        """INSERT INTO licensing_acceptance_history (
        actor_user_id, event_type, edition, fingerprint, declaration, occurred_at_ms
        ) VALUES (?, 'license_acceptance', ?, ?, NULL, ?)""",
        (actor_user_id, edition, fingerprint, accepted_at_ms),
    )


__all__ = ("sync_accept_current_license", "sync_accept_wizard_license")

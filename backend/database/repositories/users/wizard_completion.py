"""SoAI - Atomic licensed setup completion [backend/database/repositories/users/wizard_completion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import ConcurrencyError, StateError, ValidationError
from core.events.domain_event_payload import build_domain_event_payload
from core.licensing.declaration import PERSONAL_USE_ATTESTATION_REVISION
from core.media.tesseract_languages import ocr_language_for_ui_locale
from core.types.json import JSONDict
from core.users.user_id import require_strict_user_id
from database.core.query_execution import sync_fetch_one_as_dict
from database.core.savepoints import SQLiteSavepoint
from database.repositories.event_outbox.sync_ops import sync_ensure_domain_event_payload
from database.repositories.licensing.documents import (
    sync_promote_pending_document_for_completion,
)
from database.repositories.users.user_count_queries import (
    sync_require_uninitialized_bootstrap_state,
)
from database.repositories.users.user_preference_mutations import (
    sync_merge_user_preferences,
)
from database.repositories.users.user_sync_creation import (
    sync_create_example_prompt,
    sync_create_user,
)


def _require_completion_prerequisites(
    connection: sqlite3.Connection,
    *,
    edition: str,
    expected_revision: int,
    current_license_fingerprint: str,
    expected_pending_document_digest: str | None,
) -> bool:
    draft = sync_fetch_one_as_dict(
        connection.execute("SELECT * FROM licensing_wizard_draft WHERE singleton = 1")
    )
    if (
        draft is None
        or draft.get("edition") != edition
        or draft.get("revision") != expected_revision
    ):
        raise ConcurrencyError("Licensing wizard state changed in another request.")
    if (
        draft.get("accepted_license_fingerprint") != current_license_fingerprint
        or draft.get("accepted_license_at_ms") is None
    ):
        raise ValidationError("The current controlling license must be accepted.")
    declaration = draft.get("declaration")
    if declaration not in {"personal", "organization_commercial"}:
        raise ValidationError("A use declaration is required.")
    if declaration == "personal" and (
        draft.get("attestation_revision") != PERSONAL_USE_ATTESTATION_REVISION
        or draft.get("attestation_confirmed_at_ms") is None
    ):
        raise ValidationError("The current personal-use attestation is required.")
    if edition == "soai-core" and declaration == "personal":
        if expected_pending_document_digest is not None:
            raise ValidationError("Core Personal completion cannot promote an entitlement.")
        return False
    if (
        draft.get("selected_access_flow")
        not in {"evaluation", "online_activation", "offline_activation"}
        or draft.get("resume_step") != "account"
    ):
        raise ValidationError("Product access has not reached a completable state.")
    pending = connection.execute(
        "SELECT document_digest FROM licensing_documents WHERE disposition = 'pending'"
    ).fetchall()
    if len(pending) != 1:
        raise ValidationError("A valid product entitlement is required.")
    if (
        expected_pending_document_digest is None
        or pending[0][0] != expected_pending_document_digest
    ):
        raise ConcurrencyError("Pending licensing entitlement changed before completion.")
    return True


def sync_complete_licensing_wizard(
    connection: sqlite3.Connection,
    edition: str,
    expected_revision: int,
    current_license_fingerprint: str,
    expected_pending_document_digest: str | None,
    username: str,
    language: str,
    hashed_password: str,
    completed_at_ms: int,
) -> JSONDict:
    if edition not in {"soai-core", "soai-os"}:
        raise ValidationError("Licensing wizard edition is invalid.")
    with SQLiteSavepoint(connection, "licensed_wizard_completion"):
        sync_require_uninitialized_bootstrap_state(connection)
        requires_entitlement = _require_completion_prerequisites(
            connection,
            edition=edition,
            expected_revision=expected_revision,
            current_license_fingerprint=current_license_fingerprint,
            expected_pending_document_digest=expected_pending_document_digest,
        )
        user = sync_create_user(connection, username, hashed_password, is_admin=True)
        user_id = require_strict_user_id(user.get("id"))
        preferences = sync_merge_user_preferences(
            connection,
            user_id,
            {
                "ui": {"language": language},
                "settings": {"ocr_language": ocr_language_for_ui_locale(language)},
            },
        )
        if preferences is None:
            raise StateError("Initial user disappeared during preference persistence.")
        if requires_entitlement:
            if expected_pending_document_digest is None:
                raise ValidationError("Licensing wizard pending entitlement digest is required.")
            sync_promote_pending_document_for_completion(
                connection,
                expected_document_digest=expected_pending_document_digest,
                accepted_at_ms=completed_at_ms,
            )
        connection.execute(
            """UPDATE licensing_acceptance_history SET actor_user_id = ?
            WHERE actor_user_id IS NULL""",
            (user_id,),
        )
        sync_create_example_prompt(connection, user_id)
        connection.execute(
            "INSERT INTO webui_system_settings (key, value) VALUES ('wizard_completed', '1')"
        )
        if not requires_entitlement:
            sync_ensure_domain_event_payload(
                connection,
                event_type="LicensingStatusChangedEvent",
                payload=build_domain_event_payload(
                    event_id=f"licensing:setup:{user_id}",
                    timestamp_unix=completed_at_ms / 1000.0,
                    fields={},
                ),
                created_at_ms=completed_at_ms,
            )
    return user


__all__ = ("sync_complete_licensing_wizard",)

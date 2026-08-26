"""SoAI - Licensing wizard draft row validation [backend/database/repositories/licensing/wizard_draft_records.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.licensing.edition import require_licensing_edition
from core.licensing.storage_records import LicensingWizardDraft
from core.types.json import JSONDict
from database.core.sqlite_row_scalars import (
    require_sqlite_row_int,
    require_sqlite_row_str,
    sqlite_row_optional_int,
    sqlite_row_optional_str,
)

if TYPE_CHECKING:
    from core.licensing.types import UseDeclaration


def _stored_use_declaration(row: JSONDict, label: str) -> UseDeclaration | None:
    declaration = sqlite_row_optional_str(row, "declaration", label=label)
    if declaration is None:
        return None
    if declaration == "personal":
        return "personal"
    if declaration == "organization_commercial":
        return "organization_commercial"
    raise StateError("Stored licensing wizard declaration is invalid.")


def licensing_wizard_draft_from_row(row: JSONDict) -> LicensingWizardDraft:
    label = "Stored licensing wizard draft"
    singleton = require_sqlite_row_int(row, "singleton", label=label)
    edition = require_sqlite_row_str(row, "edition", label=label)
    require_licensing_edition(edition)
    accepted_fingerprint = sqlite_row_optional_str(row, "accepted_license_fingerprint", label=label)
    evaluation_fingerprint = sqlite_row_optional_str(row, "evaluation_fingerprint", label=label)
    declaration = _stored_use_declaration(row, label)
    access_flow = sqlite_row_optional_str(row, "selected_access_flow", label=label)
    resume_step = require_sqlite_row_str(row, "resume_step", label=label)
    if singleton != 1:
        raise StateError("Stored licensing wizard draft singleton is invalid.")
    if (
        accepted_fingerprint is not None
        and re.fullmatch(r"sha256:[a-f0-9]{64}", accepted_fingerprint) is None
    ):
        raise StateError("Stored licensing wizard acceptance fingerprint is invalid.")
    if (
        evaluation_fingerprint is not None
        and re.fullmatch(r"sha256:[a-f0-9]{64}", evaluation_fingerprint) is None
    ):
        raise StateError("Stored licensing wizard evaluation fingerprint is invalid.")
    if access_flow not in {None, "evaluation", "online_activation", "offline_activation"}:
        raise StateError("Stored licensing wizard access flow is invalid.")
    if resume_step not in {"license", "use", "product_access", "account", "complete"}:
        raise StateError("Stored licensing wizard resume step is invalid.")
    return {
        "singleton": singleton,
        "edition": edition,
        "revision": require_sqlite_row_int(row, "revision", label=label),
        "accepted_license_fingerprint": accepted_fingerprint,
        "accepted_license_at_ms": sqlite_row_optional_int(
            row, "accepted_license_at_ms", label=label
        ),
        "declaration": declaration,
        "attestation_revision": sqlite_row_optional_str(row, "attestation_revision", label=label),
        "attestation_confirmed_at_ms": sqlite_row_optional_int(
            row, "attestation_confirmed_at_ms", label=label
        ),
        "evaluation_fingerprint": evaluation_fingerprint,
        "evaluation_acknowledged_at_ms": sqlite_row_optional_int(
            row, "evaluation_acknowledged_at_ms", label=label
        ),
        "selected_access_flow": access_flow,
        "resume_step": resume_step,
        "created_at_ms": sqlite_row_optional_int(row, "created_at_ms", label=label),
        "updated_at_ms": sqlite_row_optional_int(row, "updated_at_ms", label=label),
    }


__all__ = ("licensing_wizard_draft_from_row",)

"""SoAI - Administrative licensing status projection [backend/features/api/routes/webui/licensing_status_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ConcurrencyError
from core.types.json import JSONDict
from features.api.routes.webui.wizard_status import build_wizard_status
from features.api.runtime.context import ApiContext


async def build_licensing_settings_status(api_context: ApiContext) -> JSONDict:
    wizard = await build_wizard_status(api_context)
    runtime = await api_context.dependencies.licensing_service.administrative_status()
    draft = await api_context.dependencies.database_licensing_wizard.read_wizard_draft(
        str(wizard["edition"])
    )
    if draft["revision"] != wizard["draft_revision"]:
        wizard = await build_wizard_status(api_context)
        runtime = await api_context.dependencies.licensing_service.administrative_status()
        draft = await api_context.dependencies.database_licensing_wizard.read_wizard_draft(
            str(wizard["edition"])
        )
    if draft["revision"] != wizard["draft_revision"]:
        raise ConcurrencyError("Licensing status changed while it was being read.")
    declaration = draft["declaration"]
    if declaration == "personal":
        declaration_effective_at_ms = draft["attestation_confirmed_at_ms"]
    elif declaration == "organization_commercial":
        declaration_effective_at_ms = draft["updated_at_ms"]
    else:
        declaration_effective_at_ms = None
    return {
        "schema_version": 1,
        "edition": wizard["edition"],
        "state": runtime["state"],
        "requires_repair_plane": runtime["requires_repair_plane"],
        "draft_revision": wizard["draft_revision"],
        "declaration": wizard["declaration"],
        "product_access_required": api_context.dependencies.licensing_policy.product_access_required(
            declaration
        ),
        "declaration_effective_at_ms": declaration_effective_at_ms,
        "personal_attestation_revision": wizard["personal_attestation_revision"],
        "personal_attestation_text": wizard["personal_attestation_text"],
        "personal_attestation_confirmed_at_ms": wizard["personal_attestation_confirmed_at_ms"],
        "license_document_name": wizard["license_document_name"],
        "license_fingerprint": wizard["license_fingerprint"],
        "license_accepted_at_ms": wizard["license_accepted_at_ms"],
        "operation": wizard["operation"],
        "entitlement": runtime["entitlement"],
    }


__all__ = ("build_licensing_settings_status",)

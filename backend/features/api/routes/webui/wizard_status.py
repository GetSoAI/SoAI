"""SoAI - Safe licensing wizard status projection [backend/features/api/routes/webui/wizard_status.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.licensing.canonicalization import parse_canonical_licensing_document
from core.licensing.declaration import (
    PERSONAL_USE_ATTESTATION_REVISION,
    PERSONAL_USE_ATTESTATION_TEXT,
)
from core.licensing.entitlement_payloads import parse_entitlement_payload
from core.licensing.entitlement_validation import build_safe_entitlement_summary
from core.licensing.legal_documents import load_licensing_document
from core.licensing.offline_entitlement_validation import parse_offline_entitlement_payload
from core.licensing.policy import EditionLicensingPolicy
from core.users.bootstrap_state import BootstrapState

if TYPE_CHECKING:
    from core.licensing.storage_records import LicensingWizardDraft
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext


def _unmet_prerequisites(
    draft: LicensingWizardDraft,
    *,
    policy: EditionLicensingPolicy,
    current_fingerprint: str,
    setup_state: BootstrapState,
    has_active_entitlement: bool,
) -> list[str]:
    if setup_state is BootstrapState.COMPLETE:
        return (
            []
            if draft["accepted_license_fingerprint"] == current_fingerprint
            else ["license_acceptance"]
        )
    unmet: list[str] = []
    if draft["accepted_license_fingerprint"] != current_fingerprint:
        unmet.append("license_acceptance")
    declaration = draft["declaration"]
    if declaration is None:
        unmet.append("use_declaration")
    elif declaration == "personal" and (
        draft["attestation_revision"] != PERSONAL_USE_ATTESTATION_REVISION
        or draft["attestation_confirmed_at_ms"] is None
    ):
        unmet.append("personal_attestation")
    if (
        declaration is not None
        and not has_active_entitlement
        and policy.product_access_required(declaration)
    ):
        unmet.append("product_access")
    unmet.append("administrator_account")
    return unmet


def _safe_entitlement(document: bytes, document_type: str) -> JSONDict | None:
    try:
        envelope = parse_canonical_licensing_document(document)
        if not isinstance(envelope, dict):
            raise ValidationError("Stored licensing document envelope is invalid.")
        if document_type == "offline_entitlement":
            raw_payload = envelope.get("payload")
            if not isinstance(raw_payload, dict):
                raise ValidationError("Stored offline entitlement payload is invalid.")
            payload, _license_id, _allocation_id = parse_offline_entitlement_payload(raw_payload)
        else:
            payload = parse_entitlement_payload(
                envelope.get("payload"),
                envelope.get("signature_domain"),
            )
        return build_safe_entitlement_summary(payload)
    except ValidationError:
        return None


def _safe_operation(operation: JSONDict | None) -> JSONDict | None:
    if operation is None:
        return None
    return {
        "operation_type": operation["operation_type"],
        "state": operation["state"],
        "attempt_count": operation["attempt_count"],
        "last_attempt_at_ms": operation["last_attempt_at_ms"],
        "next_retry_at_ms": operation["next_retry_at_ms"],
        "terminal_code": operation["terminal_code"],
        "updated_at_ms": operation["updated_at_ms"],
    }


async def build_wizard_status(
    api_context: ApiContext,
    *,
    include_completed_details: bool = True,
) -> JSONDict:
    dependencies = api_context.dependencies
    policy = dependencies.licensing_policy
    setup_state = await dependencies.webui_manager.get_bootstrap_state()
    has_users = await dependencies.webui_manager.has_human_users()
    if (setup_state is BootstrapState.UNINITIALIZED and has_users) or (
        setup_state is BootstrapState.COMPLETE and not has_users
    ):
        raise StateError("Cached bootstrap state and user presence are inconsistent.")
    if setup_state is not BootstrapState.UNINITIALIZED and not include_completed_details:
        return {
            "setup_needed": False,
            "has_users": has_users,
        }
    draft = await dependencies.database_licensing_wizard.read_wizard_draft(policy.edition)
    license_document = await asyncio.to_thread(
        load_licensing_document,
        dependencies.base_dir,
        policy.controlling_license_relative_path,
        policy.legal_catalog_relative_paths,
    )
    accepted_at = (
        draft["accepted_license_at_ms"]
        if draft["accepted_license_fingerprint"] == license_document.fingerprint
        else None
    )
    active_document = await dependencies.database_licensing.active_document()
    pending_document = await dependencies.database_licensing.pending_document()
    selected_document = (
        pending_document if setup_state is BootstrapState.UNINITIALIZED else active_document
    )
    entitlement = (
        _safe_entitlement(selected_document.canonical_content, selected_document.document_type)
        if selected_document is not None
        and selected_document.document_type in {"entitlement", "offline_entitlement"}
        else None
    )
    operation = _safe_operation(await dependencies.database_licensing.latest_operation())
    pending_evaluation: JSONDict | None = None
    evaluation_response = await dependencies.database_licensing.latest_operation_response(
        "evaluation"
    )
    if evaluation_response is not None:
        parsed_response = parse_canonical_licensing_document(evaluation_response.response_content)
        if (
            isinstance(parsed_response, dict)
            and parsed_response.get("state") == "evaluation_pending"
            and isinstance(parsed_response.get("evaluation_id"), str)
            and isinstance(parsed_response.get("pending_expires_at_ms"), int)
        ):
            pending_evaluation = {
                "evaluation_id": parsed_response["evaluation_id"],
                "pending_expires_at_ms": parsed_response["pending_expires_at_ms"],
            }
    evaluation_metadata: JSONDict | None = None
    if policy.evaluation_terms_relative_path is not None:
        evaluation_document = await asyncio.to_thread(
            load_licensing_document,
            dependencies.base_dir,
            policy.evaluation_terms_relative_path,
            policy.legal_catalog_relative_paths,
        )
        evaluation_metadata = {
            "document_name": policy.evaluation_terms_name,
            "fingerprint": evaluation_document.fingerprint,
        }
    purchase_metadata: JSONDict | None = None
    if policy.personal_purchase_terms_relative_path is not None:
        purchase_document = await asyncio.to_thread(
            load_licensing_document,
            dependencies.base_dir,
            policy.personal_purchase_terms_relative_path,
            policy.legal_catalog_relative_paths,
        )
        purchase_metadata = {
            "document_name": policy.personal_purchase_terms_name,
            "fingerprint": purchase_document.fingerprint,
        }
    unmet = _unmet_prerequisites(
        draft,
        policy=policy,
        current_fingerprint=license_document.fingerprint,
        setup_state=setup_state,
        has_active_entitlement=entitlement is not None,
    )
    if (
        setup_state is BootstrapState.COMPLETE
        and draft["accepted_license_fingerprint"] == license_document.fingerprint
    ):
        resume_step = "complete"
    elif draft["accepted_license_fingerprint"] != license_document.fingerprint:
        resume_step = "license"
    elif draft["declaration"] is None:
        resume_step = "use"
    elif "product_access" in unmet:
        resume_step = "product_access"
    else:
        resume_step = "account"
    return {
        "schema_version": 1,
        "setup_state": setup_state.value,
        "setup_needed": setup_state is BootstrapState.UNINITIALIZED,
        "has_users": has_users,
        "edition": policy.edition,
        "draft_revision": draft["revision"],
        "license_document_name": policy.controlling_license_name,
        "license_fingerprint": license_document.fingerprint,
        "license_accepted_at_ms": accepted_at,
        "declaration": draft["declaration"],
        "personal_attestation_revision": PERSONAL_USE_ATTESTATION_REVISION,
        "personal_attestation_text": PERSONAL_USE_ATTESTATION_TEXT,
        "personal_attestation_confirmed_at_ms": draft["attestation_confirmed_at_ms"],
        "evaluation_terms": evaluation_metadata,
        "personal_purchase_terms": purchase_metadata,
        "evaluation_acknowledged_at_ms": draft["evaluation_acknowledged_at_ms"],
        "selected_product_access_flow": draft["selected_access_flow"],
        "operation": operation,
        "pending_evaluation": pending_evaluation,
        "entitlement": entitlement,
        "resume_step": resume_step,
        "unmet_prerequisites": unmet,
        "completed_summary": (
            await build_wizard_completion_summary(api_context)
            if setup_state is BootstrapState.COMPLETE
            else None
        ),
    }


async def build_wizard_completion_summary(api_context: ApiContext) -> JSONDict:
    dependencies = api_context.dependencies
    runtime_status = await dependencies.licensing_service.public_status()
    entitlement = runtime_status.get("entitlement")
    entitlement_type = (
        entitlement.get("entitlement_type") if isinstance(entitlement, dict) else None
    )
    time_boundary = None
    if isinstance(entitlement, dict):
        if entitlement_type in {"organization_evaluation", "commercial_term"}:
            time_boundary = entitlement.get("term_ends_at")
        elif entitlement_type == "commercial_continuity":
            time_boundary = entitlement.get("continuity_ends_at")
    plugin_records = await dependencies.database_plugins.get_all_listable_plugins()
    detected_plugins = sorted(
        {
            plugin_name.strip()
            for plugin in plugin_records
            if isinstance((plugin_name := plugin.get("plugin_name")), str) and plugin_name.strip()
        }
    )
    return {
        "schema_version": 1,
        "account_created": True,
        "edition": dependencies.licensing_policy.edition,
        "declaration": runtime_status.get("declaration"),
        "entitlement_type": entitlement_type,
        "entitlement_status": runtime_status.get("state"),
        "time_boundary": time_boundary,
        "perpetual": entitlement_type in {"personal_os_perpetual", "commercial_full_perpetual"},
        "detected_plugins": detected_plugins,
    }


__all__ = ("build_wizard_completion_summary", "build_wizard_status")

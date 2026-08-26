"""SoAI - Signed authority outcome acceptance [backend/features/licensing/outcome_acceptance.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.errors.exceptions import ConcurrencyError, ValidationError
from core.licensing.canonicalization import canonicalize_licensing_json
from core.licensing.entitlement_validation import EntitlementBinding, validate_entitlement
from core.licensing.errors import LicensingIntegrityError
from core.licensing.licensing_status_validation import (
    LicensingStatusBinding,
    validate_signed_licensing_status,
)
from core.licensing.policy import EditionLicensingPolicy
from core.licensing.protocols import LicensingRepositoryProtocol
from core.licensing.storage_records import StoredLicensingDocument
from core.licensing.trust_material import ReleaseTrustMaterial
from core.types.json import JSONDict, JSONValue
from features.licensing.machine_client import LicensingAuthorityOutcome
from features.licensing.runtime_facts import parse_stored_entitlement


@dataclass(frozen=True, slots=True)
class LicensingAcceptanceBinding:
    public_key: bytes
    instance_id: str


async def accept_authority_outcome(
    *,
    repository: LicensingRepositoryProtocol,
    policy: EditionLicensingPolicy,
    trust_material: ReleaseTrustMaterial,
    document_disposition: str,
    operation_id: str,
    expected_state: str,
    outcome: LicensingAuthorityOutcome,
    binding: LicensingAcceptanceBinding,
    draft_revision: int,
    now_ms: int,
) -> JSONDict:
    response_content = canonicalize_licensing_json(outcome.fields)
    if outcome.state == "evaluation_pending":
        await repository.complete_operation_response(
            operation_id,
            expected_state=expected_state,
            response_content=response_content,
            completed_at_ms=now_ms,
        )
        return {
            "state": outcome.state,
            "evaluation_id": outcome.fields["evaluation_id"],
            "pending_expires_at_ms": outcome.fields["pending_expires_at_ms"],
            "draft_revision": draft_revision,
        }
    if outcome.signed_document is None or outcome.document_type is None:
        await _fail_invalid(
            repository,
            operation_id,
            expected_state,
            "invalid_contract",
            now_ms,
        )
        raise ValidationError("Licensing authority omitted its signed document.")
    active = await repository.active_document()
    if outcome.document_type == "licensing_status":
        return await _accept_status_outcome(
            repository=repository,
            trust_material=trust_material,
            operation_id=operation_id,
            expected_state=expected_state,
            outcome=outcome,
            active=active,
            response_content=response_content,
            draft_revision=draft_revision,
            now_ms=now_ms,
        )
    if outcome.document_type != "entitlement":
        await _fail_invalid(
            repository,
            operation_id,
            expected_state,
            "invalid_contract",
            now_ms,
        )
        raise ValidationError("Licensing authority signed document type is invalid.")
    validation_binding = EntitlementBinding(
        edition=policy.edition,
        instance_id=binding.instance_id,
        deployment_public_key=binding.public_key,
        current_deployment_id=active.deployment_id if active is not None else None,
        current_generation=active.generation if active is not None else None,
        current_document=active.canonical_content if active is not None else None,
    )
    try:
        validated = validate_entitlement(
            outcome.signed_document,
            trust_material.require_catalog(),
            validation_binding,
        )
        payload = parse_stored_entitlement(validated.canonical_document)
        _validate_outer_identity(outcome, payload.values, payload.entitlement_type)
    except LicensingIntegrityError as exception:
        await _fail_invalid(repository, operation_id, expected_state, exception.failure, now_ms)
        raise
    except ValidationError:
        await _fail_invalid(repository, operation_id, expected_state, "invalid_contract", now_ms)
        raise
    await repository.accept_entitlement_operation(
        operation_id=operation_id,
        expected_operation_state=expected_state,
        response_content=response_content,
        document=StoredLicensingDocument(
            document_digest=validated.document_digest,
            canonical_content=validated.canonical_document,
            document_type="entitlement",
            entitlement_type=validated.entitlement_type,
            entitlement_id=_optional_string(payload.values.get("evaluation_id")),
            license_id=_optional_string(payload.values.get("license_id")),
            deployment_id=validated.deployment_id,
            generation=validated.generation,
            issuer_authorization_snapshot=validated.authorization_snapshot,
            accepted_at_ms=now_ms,
        ),
        disposition=document_disposition,
        edition=policy.edition,
        expected_draft_revision=draft_revision,
    )
    return {"state": outcome.state, "draft_revision": draft_revision}


async def _accept_status_outcome(
    *,
    repository: LicensingRepositoryProtocol,
    trust_material: ReleaseTrustMaterial,
    operation_id: str,
    expected_state: str,
    outcome: LicensingAuthorityOutcome,
    active: StoredLicensingDocument | None,
    response_content: bytes,
    draft_revision: int,
    now_ms: int,
) -> JSONDict:
    if active is None or outcome.signed_document is None:
        await _fail_invalid(repository, operation_id, expected_state, "invalid_contract", now_ms)
        raise ValidationError("Licensing status requires an active paid entitlement.")
    try:
        entitlement = parse_stored_entitlement(active.canonical_content)
        license_id = entitlement.values.get("license_id")
        if not isinstance(license_id, str):
            raise ValidationError("Licensing status requires an active paid entitlement.")
        current_status = await repository.active_status_document()
        current_generation = active.generation
        current_document = None
        if current_status is not None and current_status.deployment_id == active.deployment_id:
            current_generation = max(current_generation, current_status.generation)
            current_document = current_status.canonical_content
        validated = validate_signed_licensing_status(
            outcome.signed_document,
            trust_material.require_catalog(),
            LicensingStatusBinding(
                entitlement.instance_id,
                active.deployment_id,
                license_id,
                entitlement.entitlement_type,
                entitlement.licensed_product_scope,
                current_generation,
                current_document,
            ),
        )
        if (
            outcome.state != validated.state
            or outcome.fields.get("deployment_id") != active.deployment_id
        ):
            raise ValidationError("Licensing status outer response binding is invalid.")
    except LicensingIntegrityError as exception:
        await _fail_invalid(repository, operation_id, expected_state, exception.failure, now_ms)
        raise
    except ValidationError:
        await _fail_invalid(repository, operation_id, expected_state, "invalid_contract", now_ms)
        raise
    await repository.accept_licensing_status_operation(
        operation_id=operation_id,
        expected_operation_state=expected_state,
        response_content=response_content,
        document=StoredLicensingDocument(
            document_digest=validated.document_digest,
            canonical_content=validated.canonical_document,
            document_type="licensing_status",
            entitlement_type=None,
            entitlement_id=None,
            license_id=license_id,
            deployment_id=active.deployment_id,
            generation=validated.generation,
            issuer_authorization_snapshot=validated.authorization_snapshot,
            accepted_at_ms=now_ms,
        ),
    )
    return {"state": validated.state, "draft_revision": draft_revision}


async def _fail_invalid(
    repository: LicensingRepositoryProtocol,
    operation_id: str,
    expected_state: str,
    failure: str,
    now_ms: int,
) -> None:
    transitioned = await repository.transition_operation(
        operation_id,
        expected_state=expected_state,
        target_state="failed",
        terminal_code=failure,
        updated_at_ms=now_ms,
    )
    if not transitioned:
        raise ConcurrencyError("Licensing operation changed before terminalization.")


def _optional_string(value: JSONValue) -> str | None:
    return value if isinstance(value, str) else None


def _validate_outer_identity(
    outcome: LicensingAuthorityOutcome,
    payload: JSONDict,
    entitlement_type: str,
) -> None:
    if entitlement_type == "organization_evaluation":
        matches = outcome.fields.get("evaluation_id") == payload.get(
            "evaluation_id"
        ) and outcome.fields.get("deployment_id") == payload.get("deployment_id")
    else:
        matches = outcome.fields.get("deployment_id") == payload.get("deployment_id")
        activation_id = outcome.fields.get("activation_id")
        if activation_id is not None:
            matches = matches and activation_id == payload.get("activation_id")
    if not matches:
        raise ValidationError("Licensing authority outer response binding is invalid.")


__all__ = ("LicensingAcceptanceBinding", "accept_authority_outcome")

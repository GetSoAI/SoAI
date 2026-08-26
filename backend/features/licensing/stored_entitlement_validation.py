"""SoAI - Stored entitlement trust and metadata validation [backend/features/licensing/stored_entitlement_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from core.di.validation import require_dependencies
from core.errors.exceptions import SecurityError, ValidationError
from core.licensing.entitlement_payloads import ParsedEntitlementPayload
from core.licensing.entitlement_validation import EntitlementBinding, validate_entitlement
from core.licensing.offline_entitlement_validation import (
    OfflineEntitlementBinding,
    validate_offline_entitlement,
)
from core.licensing.policy import EditionLicensingPolicy
from core.licensing.protocols import LicensingRepositoryProtocol
from core.licensing.storage_records import StoredLicensingDocument
from core.licensing.trust import IssuerAuthorizationCatalog
from core.licensing.trust_material import ReleaseTrustMaterial
from core.meta.instance_identity import resolve_instance_identity
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.types.json import JSONDict, JSONValue
from features.licensing.runtime_facts import parse_stored_entitlement


@dataclass(frozen=True, slots=True)
class StoredEntitlementValidationDependencies:
    policy: EditionLicensingPolicy
    repository: LicensingRepositoryProtocol
    database_plugins: DatabasePluginsProtocol
    trust_material: ReleaseTrustMaterial

    def __post_init__(self) -> None:
        require_dependencies(
            owner="StoredEntitlementValidationDependencies",
            database_plugins=self.database_plugins,
            policy=self.policy,
            repository=self.repository,
            trust_material=self.trust_material,
        )


@dataclass(frozen=True, slots=True)
class ValidatedStoredEntitlement:
    payload: ParsedEntitlementPayload
    safe_summary: JSONDict
    catalog: IssuerAuthorizationCatalog
    instance_id: str
    deployment_public_key: bytes
    verified_time_high_water_ms: int


async def validate_stored_entitlement(
    dependencies: StoredEntitlementValidationDependencies,
    stored: StoredLicensingDocument,
    *,
    now_ms: int,
) -> ValidatedStoredEntitlement:
    expected_digest = f"sha256:{hashlib.sha256(stored.canonical_content).hexdigest()}"
    if not hmac.compare_digest(stored.document_digest, expected_digest):
        raise ValidationError("Stored licensing entitlement digest is invalid.")
    identity = await dependencies.repository.read_deployment_identity()
    if identity is None:
        raise SecurityError("Stored entitlement has no deployment identity binding.")
    instance = await resolve_instance_identity(
        dependencies.database_plugins,
        dependencies.repository,
    )
    catalog = dependencies.trust_material.require_catalog()
    if stored.document_type == "entitlement":
        validated = validate_entitlement(
            stored.canonical_content,
            catalog,
            EntitlementBinding(
                dependencies.policy.edition,
                instance.instance_id,
                identity.public_key,
                stored.deployment_id,
                stored.generation,
                stored.canonical_content,
            ),
            stored.issuer_authorization_snapshot,
        )
        payload = parse_stored_entitlement(validated.canonical_document)
        safe_summary = validated.summary
        expected_entitlement_id = payload.values.get("evaluation_id")
        expected_license_id = payload.values.get("license_id")
    elif stored.document_type == "offline_entitlement":
        request = await dependencies.repository.offline_request()
        if request is None:
            raise ValidationError("Offline licensing request binding is unavailable.")
        validated_offline = validate_offline_entitlement(
            stored.canonical_content,
            catalog.root_public_key.public_bytes(Encoding.Raw, PublicFormat.Raw),
            OfflineEntitlementBinding(
                dependencies.policy.edition,
                instance.instance_id,
                identity.public_key,
                request.request_digest,
                stored.deployment_id,
                stored.generation,
                stored.canonical_content,
            ),
        )
        if not hmac.compare_digest(
            stored.issuer_authorization_snapshot,
            validated_offline.root_snapshot,
        ):
            raise ValidationError("Stored offline entitlement trust snapshot is invalid.")
        payload = validated_offline.payload
        safe_summary = validated_offline.summary
        expected_entitlement_id = validated_offline.allocation_id
        expected_license_id = validated_offline.license_id
    else:
        raise ValidationError("Stored licensing document type is invalid.")
    _validate_metadata(
        stored,
        payload,
        expected_entitlement_id=expected_entitlement_id,
        expected_license_id=expected_license_id,
    )
    verified_time = await dependencies.repository.advance_verified_time(
        max(
            now_ms,
            int(payload.issued_at.timestamp() * 1_000),
            int(payload.effective_at.timestamp() * 1_000),
        )
    )
    return ValidatedStoredEntitlement(
        payload,
        safe_summary,
        catalog,
        instance.instance_id,
        identity.public_key,
        verified_time,
    )


def _validate_metadata(
    stored: StoredLicensingDocument,
    payload: ParsedEntitlementPayload,
    *,
    expected_entitlement_id: JSONValue,
    expected_license_id: JSONValue,
) -> None:
    if (
        stored.entitlement_type != payload.entitlement_type
        or stored.entitlement_id != expected_entitlement_id
        or stored.license_id != expected_license_id
        or stored.deployment_id != payload.deployment_id
        or stored.generation != payload.generation
    ):
        raise ValidationError("Stored licensing entitlement metadata is invalid.")


__all__ = (
    "StoredEntitlementValidationDependencies",
    "ValidatedStoredEntitlement",
    "validate_stored_entitlement",
)

"""SoAI - Validated active online entitlement loading [backend/features/licensing/online_entitlement.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.errors.exceptions import StateError
from core.licensing.entitlement_payloads import ParsedEntitlementPayload
from core.licensing.entitlement_validation import (
    EntitlementBinding,
    ValidatedEntitlement,
    validate_entitlement,
)
from core.licensing.policy import EditionLicensingPolicy
from core.licensing.protocols import LicensingRepositoryProtocol
from core.licensing.storage_records import StoredLicensingDocument
from core.licensing.trust_material import ReleaseTrustMaterial
from core.meta.instance_identity import resolve_instance_identity
from core.plugins.protocols_database import DatabasePluginsProtocol
from features.licensing.operation_execution import LicensingOperationBinding
from features.licensing.runtime_facts import parse_stored_entitlement


@dataclass(frozen=True, slots=True)
class ActiveOnlineEntitlement:
    stored: StoredLicensingDocument
    parsed: ParsedEntitlementPayload
    validated: ValidatedEntitlement
    private_key: Ed25519PrivateKey
    public_key: bytes
    instance_id: str

    def operation_binding(self, edition: str) -> LicensingOperationBinding:
        return LicensingOperationBinding(
            edition=edition,
            licensed_product_scope=self.validated.licensed_product_scope,
            instance_id=self.instance_id,
            deployment_id=self.validated.deployment_id,
        )


async def load_active_online_entitlement(
    *,
    policy: EditionLicensingPolicy,
    repository: LicensingRepositoryProtocol,
    database_plugins: DatabasePluginsProtocol,
    trust_material: ReleaseTrustMaterial,
    now_ms: int,
) -> ActiveOnlineEntitlement:
    stored = await repository.active_document()
    if stored is None or stored.document_type != "entitlement":
        raise StateError("Online licensing maintenance requires an active entitlement.")
    parsed = parse_stored_entitlement(stored.canonical_content)
    identity = await repository.deployment_identity(now_ms)
    instance = await resolve_instance_identity(database_plugins, repository)
    validated = validate_entitlement(
        stored.canonical_content,
        trust_material.require_catalog(),
        EntitlementBinding(
            edition=policy.edition,
            instance_id=instance.instance_id,
            deployment_public_key=identity.public_key,
            current_deployment_id=stored.deployment_id,
            current_generation=stored.generation,
            current_document=stored.canonical_content,
        ),
        stored.issuer_authorization_snapshot,
    )
    if stored.generation != validated.generation or stored.deployment_id != validated.deployment_id:
        raise StateError("Stored licensing entitlement metadata is invalid.")
    latest = await repository.latest_document(validated.deployment_id)
    if latest is None:
        raise StateError("Licensing generation high-water document is unavailable.")
    return ActiveOnlineEntitlement(
        stored,
        parsed,
        validated,
        identity.private_key,
        identity.public_key,
        instance.instance_id,
    )


__all__ = ("ActiveOnlineEntitlement", "load_active_online_entitlement")

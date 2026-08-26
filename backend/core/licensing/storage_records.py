"""SoAI - Licensing persistence boundary records [backend/core/licensing/storage_records.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypedDict

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

if TYPE_CHECKING:
    from core.licensing.types import UseDeclaration


@dataclass(frozen=True, slots=True)
class DeploymentKeypair:
    private_key: Ed25519PrivateKey = field(repr=False)
    public_key: bytes


@dataclass(frozen=True, slots=True)
class StoredLicensingDocument:
    document_digest: str
    canonical_content: bytes
    document_type: str
    entitlement_type: str | None
    entitlement_id: str | None
    license_id: str | None
    deployment_id: str
    generation: int
    issuer_authorization_snapshot: bytes
    accepted_at_ms: int


@dataclass(frozen=True, slots=True)
class OfflineRequestInsert:
    operation_id: str
    draft_revision: int
    edition: str
    licensed_product_scope: str
    instance_id: str
    deployment_public_key: bytes
    request_digest: str
    canonical_content: bytes
    created_at_ms: int


@dataclass(frozen=True, slots=True)
class OfflineRequestRecord:
    operation_id: str
    draft_revision: int
    edition: str
    licensed_product_scope: str
    instance_id: str
    deployment_public_key: bytes
    request_digest: str
    canonical_content: bytes
    created_at_ms: int
    fulfilled_at_ms: int | None


class LicensingWizardDraft(TypedDict):
    singleton: int
    edition: str
    revision: int
    accepted_license_fingerprint: str | None
    accepted_license_at_ms: int | None
    declaration: UseDeclaration | None
    attestation_revision: str | None
    attestation_confirmed_at_ms: int | None
    evaluation_fingerprint: str | None
    evaluation_acknowledged_at_ms: int | None
    selected_access_flow: str | None
    resume_step: str
    created_at_ms: int | None
    updated_at_ms: int | None


@dataclass(frozen=True, slots=True)
class RecoverableLicensingOperation:
    operation_id: str
    operation_type: str
    state: str
    canonical_request: bytes | None
    attempt_count: int
    next_retry_at_ms: int | None


@dataclass(frozen=True, slots=True)
class StoredLicensingOperationResponse:
    operation_type: str
    idempotency_key: str
    request_digest: str
    response_content: bytes


@dataclass(frozen=True, slots=True)
class LicensingOperationInsert:
    operation_id: str
    operation_type: str
    idempotency_key: str | None
    request_digest: str | None
    edition: str
    licensed_product_scope: str
    instance_id: str
    created_at_ms: int
    request_nonce: bytes | None = None
    canonical_request: bytes | None = None
    parent_operation_id: str | None = None
    activation_id: str | None = None
    deployment_id: str | None = None
    deactivation_reason: str | None = None


__all__ = (
    "DeploymentKeypair",
    "OfflineRequestInsert",
    "OfflineRequestRecord",
    "LicensingOperationInsert",
    "LicensingWizardDraft",
    "RecoverableLicensingOperation",
    "StoredLicensingDocument",
    "StoredLicensingOperationResponse",
)

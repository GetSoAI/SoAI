"""SoAI - Cross-subsystem licensing protocols [backend/core/licensing/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

from core.licensing.admission import LicensingAdmissionDecision, LicensingOperationClass
from core.licensing.storage_records import (
    DeploymentKeypair,
    LicensingOperationInsert,
    LicensingWizardDraft,
    OfflineRequestInsert,
    OfflineRequestRecord,
    RecoverableLicensingOperation,
    StoredLicensingDocument,
    StoredLicensingOperationResponse,
)
from core.licensing.types import LicensingStatus
from core.types.json import JSONDict

__all__ = (
    "LicensingBindingQueryProtocol",
    "LicensingRepairPlaneCoordinatorProtocol",
    "LicensingRepositoryProtocol",
    "LicensingStatusProtocol",
    "LicensingWizardRepositoryProtocol",
)


class LicensingRepairPlaneCoordinatorProtocol(Protocol):
    @property
    def startup_repair_plane_active(self) -> bool: ...

    async def activate_startup_repair_plane(self) -> None: ...

    async def reconcile(self, dynamic_requires_repair_plane: bool) -> None: ...


class LicensingBindingQueryProtocol(Protocol):
    async def resolve_instance_id(self, candidate: str) -> str: ...


class LicensingStatusProtocol(Protocol):
    @property
    def controlling_license_fingerprint(self) -> str: ...

    async def validate_pending_completion(
        self,
        *,
        expected_revision: int,
        now_ms: int,
    ) -> str | None: ...

    async def public_status(self) -> JSONDict: ...

    async def administrative_status(self) -> JSONDict: ...

    async def resolved_status(self) -> LicensingStatus: ...

    async def dynamic_status(self) -> LicensingStatus: ...

    async def admission(
        self,
        operation_class: LicensingOperationClass,
    ) -> LicensingAdmissionDecision: ...


class LicensingWizardRepositoryProtocol(Protocol):
    async def read_wizard_draft(self, edition: str) -> LicensingWizardDraft: ...

    async def accept_wizard_license(
        self,
        *,
        edition: str,
        expected_revision: int,
        fingerprint: str,
        accepted_at_ms: int,
        actor_user_id: int | None,
    ) -> LicensingWizardDraft: ...

    async def accept_current_license(
        self,
        *,
        edition: str,
        expected_revision: int,
        fingerprint: str,
        accepted_at_ms: int,
        actor_user_id: int,
    ) -> LicensingWizardDraft: ...

    async def set_wizard_use(
        self,
        *,
        edition: str,
        expected_revision: int,
        declaration: str,
        attestation_confirmed: bool,
        attestation_revision: str | None,
        confirmed_at_ms: int,
        actor_user_id: int | None,
    ) -> LicensingWizardDraft: ...

    async def set_authenticated_declaration(
        self,
        *,
        edition: str,
        expected_revision: int,
        declaration: str,
        attestation_confirmed: bool,
        attestation_revision: str | None,
        expected_active_document_digest: str | None,
        retire_active_entitlement: bool,
        changed_at_ms: int,
        actor_user_id: int,
    ) -> LicensingWizardDraft: ...

    async def begin_wizard_access(
        self,
        *,
        edition: str,
        expected_revision: int,
        access_flow: str,
        changed_at_ms: int,
    ) -> LicensingWizardDraft: ...

    async def begin_wizard_evaluation(
        self,
        *,
        expected_revision: int,
        terms_fingerprint: str,
        acknowledged_at_ms: int,
    ) -> LicensingWizardDraft: ...


class LicensingRepositoryProtocol(Protocol):
    async def resolve_instance_id(self, candidate: str) -> str: ...

    async def deployment_identity(self, created_at_ms: int) -> DeploymentKeypair: ...

    async def read_deployment_identity(self) -> DeploymentKeypair | None: ...

    async def advance_verified_time(self, verified_time_ms: int) -> int: ...

    async def get_or_create_offline_request(
        self,
        candidate: OfflineRequestInsert,
    ) -> OfflineRequestRecord: ...

    async def offline_request(self) -> OfflineRequestRecord | None: ...

    async def accept_offline_entitlement(
        self,
        *,
        operation_id: str,
        expected_draft_revision: int,
        edition: str,
        document_digest: str,
        canonical_content: bytes,
        entitlement_type: str,
        allocation_id: str,
        license_id: str,
        deployment_id: str,
        generation: int,
        root_snapshot: bytes,
        accepted_at_ms: int,
        disposition: str,
    ) -> None: ...

    async def create_operation(self, operation: LicensingOperationInsert) -> JSONDict: ...

    async def claim_operation(self, operation_id: str, claimed_at_ms: int) -> bool: ...

    async def transition_operation(
        self,
        operation_id: str,
        *,
        expected_state: str,
        target_state: str,
        updated_at_ms: int,
        next_retry_at_ms: int | None = None,
        terminal_code: str | None = None,
    ) -> bool: ...

    async def latest_operation(self, operation_type: str | None = None) -> JSONDict | None: ...

    async def recoverable_operations(self) -> tuple[RecoverableLicensingOperation, ...]: ...

    async def latest_operation_response(
        self, operation_type: str
    ) -> StoredLicensingOperationResponse | None: ...

    async def complete_operation_response(
        self,
        operation_id: str,
        *,
        expected_state: str,
        response_content: bytes,
        completed_at_ms: int,
    ) -> None: ...

    async def active_document(self) -> StoredLicensingDocument | None: ...

    async def active_status_document(self) -> StoredLicensingDocument | None: ...

    async def latest_document(self, deployment_id: str) -> StoredLicensingDocument | None: ...

    async def pending_document(self) -> StoredLicensingDocument | None: ...

    async def accept_entitlement_operation(
        self,
        *,
        operation_id: str,
        expected_operation_state: str,
        response_content: bytes,
        document: StoredLicensingDocument,
        disposition: str,
        edition: str,
        expected_draft_revision: int,
    ) -> None: ...

    async def accept_licensing_status_operation(
        self,
        *,
        operation_id: str,
        expected_operation_state: str,
        response_content: bytes,
        document: StoredLicensingDocument,
    ) -> None: ...

    async def complete_deactivation_operation(
        self,
        operation_id: str,
        *,
        expected_state: str,
        deployment_id: str,
        response_content: bytes,
        completed_at_ms: int,
    ) -> None: ...

"""SoAI - Licensing repository service [backend/database/repositories/licensing/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.licensing.constants import VERIFIED_TIME_CHECKPOINT_INTERVAL_MS
from core.licensing.storage_records import (
    DeploymentKeypair,
    LicensingOperationInsert,
    OfflineRequestInsert,
    OfflineRequestRecord,
    RecoverableLicensingOperation,
    StoredLicensingDocument,
    StoredLicensingOperationResponse,
)
from core.validation.epoch import require_unix_epoch_ms
from database.repositories.licensing.deactivation import sync_complete_deactivation_operation
from database.repositories.licensing.deployment_identity import (
    read_deployment_identity_query,
    sync_get_or_create_deployment_identity,
    sync_resolve_instance_id,
)
from database.repositories.licensing.document_queries import (
    read_active_document_query,
    read_active_status_query,
    read_latest_document_query,
    read_pending_document_query,
)
from database.repositories.licensing.documents import (
    sync_accept_entitlement_operation,
    sync_accept_licensing_status_operation,
)
from database.repositories.licensing.offline_requests import (
    read_offline_request_query,
    sync_accept_offline_entitlement,
    sync_get_or_create_offline_request,
)
from database.repositories.licensing.operation_queries import (
    read_latest_operation_query,
    read_latest_operation_response_query,
    read_recoverable_operations_query,
)
from database.repositories.licensing.operations import (
    sync_claim_licensing_operation,
    sync_complete_licensing_operation,
    sync_create_licensing_operation,
    sync_transition_licensing_operation,
)
from database.repositories.licensing.verified_clock import (
    read_verified_time_high_water_query,
    sync_advance_verified_time,
)
from database.repositories.users.domain_event_outbox_dispatch_signal import (
    notify_domain_event_outbox_dispatch_requested,
)

__all__ = ("DatabaseLicensing",)

if TYPE_CHECKING:
    from core.database.protocols import DatabaseCoreProtocol
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies


class DatabaseLicensing:
    def __init__(self, dependencies: DatabaseRepositoryDependencies) -> None:
        self._core: DatabaseCoreProtocol = dependencies.core
        self._fernets = dependencies.fernet
        self._event_bus = dependencies.event_bus

    async def deployment_identity(self, created_at_ms: int) -> DeploymentKeypair:
        return await self._core.writer.queue_write_operation(
            sync_get_or_create_deployment_identity,
            self._fernets,
            created_at_ms,
        )

    async def read_deployment_identity(self) -> DeploymentKeypair | None:
        return await self._core.reader.execute_read(read_deployment_identity_query, self._fernets)

    async def resolve_instance_id(self, candidate: str) -> str:
        return await self._core.writer.queue_write_operation(
            sync_resolve_instance_id,
            candidate,
        )

    async def advance_verified_time(self, verified_time_ms: int) -> int:
        candidate = require_unix_epoch_ms(
            verified_time_ms,
            error_message="Licensing verified time must be a valid epoch-millisecond integer.",
        )
        persisted = await self._core.reader.execute_read(read_verified_time_high_water_query)
        if persisted is not None and candidate < persisted + VERIFIED_TIME_CHECKPOINT_INTERVAL_MS:
            return max(candidate, persisted)
        return await self._core.writer.queue_write_operation(
            sync_advance_verified_time,
            candidate,
        )

    async def get_or_create_offline_request(
        self,
        candidate: OfflineRequestInsert,
    ) -> OfflineRequestRecord:
        return await self._core.writer.queue_write_operation(
            sync_get_or_create_offline_request,
            candidate,
        )

    async def offline_request(self) -> OfflineRequestRecord | None:
        return await self._core.reader.execute_read(read_offline_request_query)

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
    ) -> None:
        await self._core.writer.queue_write_operation(
            sync_accept_offline_entitlement,
            operation_id,
            expected_draft_revision,
            edition,
            document_digest,
            canonical_content,
            entitlement_type,
            allocation_id,
            license_id,
            deployment_id,
            generation,
            root_snapshot,
            accepted_at_ms,
            disposition,
        )
        if disposition == "active":
            notify_domain_event_outbox_dispatch_requested(self._event_bus)

    async def create_operation(self, operation: LicensingOperationInsert) -> JSONDict:
        return await self._core.writer.queue_write_operation(
            sync_create_licensing_operation,
            operation,
        )

    async def claim_operation(self, operation_id: str, claimed_at_ms: int) -> bool:
        return bool(
            await self._core.writer.queue_write_operation(
                sync_claim_licensing_operation,
                operation_id,
                claimed_at_ms,
            )
        )

    async def transition_operation(
        self,
        operation_id: str,
        *,
        expected_state: str,
        target_state: str,
        updated_at_ms: int,
        next_retry_at_ms: int | None = None,
        terminal_code: str | None = None,
    ) -> bool:
        return bool(
            await self._core.writer.queue_write_operation(
                sync_transition_licensing_operation,
                operation_id,
                expected_state,
                target_state,
                updated_at_ms,
                next_retry_at_ms,
                terminal_code,
            )
        )

    async def latest_operation(self, operation_type: str | None = None) -> JSONDict | None:
        return await self._core.reader.execute_read(
            read_latest_operation_query,
            operation_type,
        )

    async def recoverable_operations(self) -> tuple[RecoverableLicensingOperation, ...]:
        return await self._core.reader.execute_read(read_recoverable_operations_query)

    async def latest_operation_response(
        self, operation_type: str
    ) -> StoredLicensingOperationResponse | None:
        return await self._core.reader.execute_read(
            read_latest_operation_response_query, operation_type
        )

    async def complete_operation_response(
        self,
        operation_id: str,
        *,
        expected_state: str,
        response_content: bytes,
        completed_at_ms: int,
    ) -> None:
        await self._core.writer.queue_write_operation(
            sync_complete_licensing_operation,
            operation_id,
            expected_state,
            response_content,
            completed_at_ms,
        )

    async def active_document(self) -> StoredLicensingDocument | None:
        return await self._core.reader.execute_read(read_active_document_query)

    async def pending_document(self) -> StoredLicensingDocument | None:
        return await self._core.reader.execute_read(read_pending_document_query)

    async def active_status_document(self) -> StoredLicensingDocument | None:
        return await self._core.reader.execute_read(read_active_status_query)

    async def latest_document(self, deployment_id: str) -> StoredLicensingDocument | None:
        return await self._core.reader.execute_read(read_latest_document_query, deployment_id)

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
    ) -> None:
        await self._core.writer.queue_write_operation(
            sync_accept_entitlement_operation,
            operation_id,
            expected_operation_state,
            response_content,
            document,
            disposition,
            edition,
            expected_draft_revision,
        )
        if disposition == "active":
            notify_domain_event_outbox_dispatch_requested(self._event_bus)

    async def accept_licensing_status_operation(
        self,
        *,
        operation_id: str,
        expected_operation_state: str,
        response_content: bytes,
        document: StoredLicensingDocument,
    ) -> None:
        await self._core.writer.queue_write_operation(
            sync_accept_licensing_status_operation,
            operation_id,
            expected_operation_state,
            response_content,
            document,
        )
        notify_domain_event_outbox_dispatch_requested(self._event_bus)

    async def complete_deactivation_operation(
        self,
        operation_id: str,
        *,
        expected_state: str,
        deployment_id: str,
        response_content: bytes,
        completed_at_ms: int,
    ) -> None:
        await self._core.writer.queue_write_operation(
            sync_complete_deactivation_operation,
            self._fernets,
            operation_id,
            expected_state,
            deployment_id,
            response_content,
            completed_at_ms,
        )
        notify_domain_event_outbox_dispatch_requested(self._event_bus)

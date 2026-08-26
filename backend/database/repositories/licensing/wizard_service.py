"""SoAI - Licensing wizard and declaration repository [backend/database/repositories/licensing/wizard_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.licensing.storage_records import LicensingWizardDraft
from database.repositories.licensing.declaration import sync_set_authenticated_declaration
from database.repositories.licensing.license_acceptance import (
    sync_accept_current_license,
    sync_accept_wizard_license,
)
from database.repositories.licensing.wizard import (
    read_wizard_draft_query,
    sync_begin_wizard_access,
    sync_begin_wizard_evaluation,
    sync_set_wizard_use,
)
from database.repositories.users.domain_event_outbox_dispatch_signal import (
    notify_domain_event_outbox_dispatch_requested,
)

if TYPE_CHECKING:
    from core.database.protocols import DatabaseCoreProtocol
    from core.events.protocols import EventBusProtocol
    from database.repositories.dependencies import DatabaseRepositoryDependencies


class DatabaseLicensingWizard:
    def __init__(self, dependencies: DatabaseRepositoryDependencies) -> None:
        self._core: DatabaseCoreProtocol = dependencies.core
        self._event_bus: EventBusProtocol | None = dependencies.event_bus

    async def read_wizard_draft(self, edition: str) -> LicensingWizardDraft:
        return await self._core.reader.execute_read(read_wizard_draft_query, edition)

    async def accept_wizard_license(
        self,
        *,
        edition: str,
        expected_revision: int,
        fingerprint: str,
        accepted_at_ms: int,
        actor_user_id: int | None,
    ) -> LicensingWizardDraft:
        return await self._core.writer.queue_write_operation(
            sync_accept_wizard_license,
            edition,
            expected_revision,
            fingerprint,
            accepted_at_ms,
            actor_user_id,
        )

    async def accept_current_license(
        self,
        *,
        edition: str,
        expected_revision: int,
        fingerprint: str,
        accepted_at_ms: int,
        actor_user_id: int,
    ) -> LicensingWizardDraft:
        updated = await self._core.writer.queue_write_operation(
            sync_accept_current_license,
            edition,
            expected_revision,
            fingerprint,
            accepted_at_ms,
            actor_user_id,
        )
        notify_domain_event_outbox_dispatch_requested(self._event_bus)
        return updated

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
    ) -> LicensingWizardDraft:
        return await self._core.writer.queue_write_operation(
            sync_set_wizard_use,
            edition,
            expected_revision,
            declaration,
            attestation_confirmed,
            attestation_revision,
            confirmed_at_ms,
            actor_user_id,
        )

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
    ) -> LicensingWizardDraft:
        updated = await self._core.writer.queue_write_operation(
            sync_set_authenticated_declaration,
            edition,
            expected_revision,
            declaration,
            attestation_confirmed,
            attestation_revision,
            expected_active_document_digest,
            retire_active_entitlement,
            changed_at_ms,
            actor_user_id,
        )
        notify_domain_event_outbox_dispatch_requested(self._event_bus)
        return updated

    async def begin_wizard_access(
        self,
        *,
        edition: str,
        expected_revision: int,
        access_flow: str,
        changed_at_ms: int,
    ) -> LicensingWizardDraft:
        return await self._core.writer.queue_write_operation(
            sync_begin_wizard_access,
            edition,
            expected_revision,
            access_flow,
            changed_at_ms,
        )

    async def begin_wizard_evaluation(
        self,
        *,
        expected_revision: int,
        terms_fingerprint: str,
        acknowledged_at_ms: int,
    ) -> LicensingWizardDraft:
        return await self._core.writer.queue_write_operation(
            sync_begin_wizard_evaluation,
            expected_revision,
            terms_fingerprint,
            acknowledged_at_ms,
        )


__all__ = ("DatabaseLicensingWizard",)

"""SoAI - Messaging provider delivery persistence [backend/database/repositories/users/messaging_deliveries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.timing.epoch import epoch_ms
from core.validation.strings import coerce_required_non_empty_str
from database.repositories.users.messaging_delivery_claims import (
    sync_claim_next_messaging_delivery_attempt,
)
from database.repositories.users.messaging_delivery_control_projection import (
    sync_project_control_messaging_delivery,
)
from database.repositories.users.messaging_delivery_interaction_projection import (
    sync_project_interaction_messaging_delivery,
)
from database.repositories.users.messaging_delivery_outcomes import (
    sync_record_messaging_chunk_failure,
    sync_record_messaging_chunk_sent,
)
from database.repositories.users.messaging_delivery_pre_send_recovery import (
    sync_record_messaging_claim_not_started,
    sync_record_messaging_claim_pre_send_failure,
)
from database.repositories.users.messaging_delivery_projection import (
    sync_project_terminal_messaging_delivery,
)
from database.repositories.users.messaging_delivery_recovery import (
    sync_reconcile_prior_boot_messaging_deliveries,
    sync_settle_messaging_delivery_worker_failure,
)
from database.repositories.users.messaging_delivery_request_start import (
    sync_mark_messaging_chunk_request_started,
)

if TYPE_CHECKING:
    from core.events.types_conversation_durable import (
        ConversationControlCompletedEvent,
        ConversationInputTerminalEvent,
        ConversationInteractionRequiredEvent,
    )
    from core.messaging.delivery_models import MessagingDeliveryAttempt
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseMessagingDeliveries",)


class DatabaseMessagingDeliveries:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core
        self.public_origin = deps.config.get_str("SERVER.PUBLIC_ORIGIN")

    async def project_terminal_event(
        self,
        event: ConversationInputTerminalEvent,
    ) -> JSONDict | None:
        return await self.core.writer.queue_write_operation(
            sync_project_terminal_messaging_delivery,
            event,
        )

    async def project_control_event(
        self,
        event: ConversationControlCompletedEvent,
    ) -> JSONDict | None:
        return await self.core.writer.queue_write_operation(
            sync_project_control_messaging_delivery,
            event,
        )

    async def project_interaction_event(
        self,
        event: ConversationInteractionRequiredEvent,
    ) -> JSONDict | None:
        return await self.core.writer.queue_write_operation(
            sync_project_interaction_messaging_delivery,
            event,
            self.public_origin,
        )

    async def reconcile_prior_boot_deliveries(
        self,
        *,
        current_server_boot_id: str,
    ) -> int:
        return await self.core.writer.queue_write_operation(
            sync_reconcile_prior_boot_messaging_deliveries,
            coerce_required_non_empty_str(
                current_server_boot_id,
                label="current_server_boot_id",
            ),
            epoch_ms(),
        )

    async def claim_next_delivery_attempt(
        self,
        *,
        claim_owner: str,
        server_boot_id: str,
    ) -> MessagingDeliveryAttempt | None:
        return await self.core.writer.queue_write_operation(
            sync_claim_next_messaging_delivery_attempt,
            coerce_required_non_empty_str(claim_owner, label="claim_owner"),
            coerce_required_non_empty_str(server_boot_id, label="server_boot_id"),
            epoch_ms(),
        )

    async def settle_worker_failure(
        self,
        *,
        delivery_id: str,
        claim_generation: int,
        claim_owner: str,
        server_boot_id: str,
    ) -> JSONDict:
        return await self.core.writer.queue_write_operation(
            sync_settle_messaging_delivery_worker_failure,
            coerce_required_non_empty_str(delivery_id, label="delivery_id"),
            claim_generation,
            coerce_required_non_empty_str(claim_owner, label="claim_owner"),
            coerce_required_non_empty_str(server_boot_id, label="server_boot_id"),
            epoch_ms(),
        )

    async def record_chunk_sent(
        self,
        *,
        delivery_id: str,
        claim_generation: int,
        claim_owner: str,
        server_boot_id: str,
        ordinal: int,
        provider_message_id: str,
        next_request_delay_ms: int,
    ) -> JSONDict:
        return await self.core.writer.queue_write_operation(
            sync_record_messaging_chunk_sent,
            coerce_required_non_empty_str(delivery_id, label="delivery_id"),
            claim_generation,
            coerce_required_non_empty_str(claim_owner, label="claim_owner"),
            coerce_required_non_empty_str(server_boot_id, label="server_boot_id"),
            ordinal,
            coerce_required_non_empty_str(
                provider_message_id,
                label="provider_message_id",
            ),
            next_request_delay_ms,
            epoch_ms(),
        )

    async def mark_chunk_request_started(
        self,
        *,
        delivery_id: str,
        claim_generation: int,
        claim_owner: str,
        server_boot_id: str,
        ordinal: int,
        credential_fingerprint: str,
    ) -> bool:
        return await self.core.writer.queue_write_operation(
            sync_mark_messaging_chunk_request_started,
            coerce_required_non_empty_str(delivery_id, label="delivery_id"),
            claim_generation,
            coerce_required_non_empty_str(claim_owner, label="claim_owner"),
            coerce_required_non_empty_str(server_boot_id, label="server_boot_id"),
            ordinal,
            coerce_required_non_empty_str(
                credential_fingerprint,
                label="credential_fingerprint",
            ),
            epoch_ms(),
        )

    async def record_claim_not_started(
        self,
        *,
        delivery_id: str,
        claim_generation: int,
        claim_owner: str,
        server_boot_id: str,
        ordinal: int,
        failure_code: str,
        retry_after_ms: int,
    ) -> JSONDict:
        return await self.core.writer.queue_write_operation(
            sync_record_messaging_claim_not_started,
            coerce_required_non_empty_str(delivery_id, label="delivery_id"),
            claim_generation,
            coerce_required_non_empty_str(claim_owner, label="claim_owner"),
            coerce_required_non_empty_str(server_boot_id, label="server_boot_id"),
            ordinal,
            coerce_required_non_empty_str(failure_code, label="failure_code"),
            retry_after_ms,
            epoch_ms(),
        )

    async def record_claim_pre_send_failure(
        self,
        *,
        delivery_id: str,
        claim_generation: int,
        claim_owner: str,
        server_boot_id: str,
        ordinal: int,
        failure_code: str,
    ) -> JSONDict:
        return await self.core.writer.queue_write_operation(
            sync_record_messaging_claim_pre_send_failure,
            coerce_required_non_empty_str(delivery_id, label="delivery_id"),
            claim_generation,
            coerce_required_non_empty_str(claim_owner, label="claim_owner"),
            coerce_required_non_empty_str(server_boot_id, label="server_boot_id"),
            ordinal,
            coerce_required_non_empty_str(failure_code, label="failure_code"),
            epoch_ms(),
        )

    async def record_chunk_failure(
        self,
        *,
        delivery_id: str,
        claim_generation: int,
        claim_owner: str,
        server_boot_id: str,
        ordinal: int,
        outcome: str,
        failure_code: str,
        retry_after_ms: int | None,
    ) -> JSONDict:
        return await self.core.writer.queue_write_operation(
            sync_record_messaging_chunk_failure,
            coerce_required_non_empty_str(delivery_id, label="delivery_id"),
            claim_generation,
            coerce_required_non_empty_str(claim_owner, label="claim_owner"),
            coerce_required_non_empty_str(server_boot_id, label="server_boot_id"),
            ordinal,
            coerce_required_non_empty_str(outcome, label="outcome"),
            coerce_required_non_empty_str(failure_code, label="failure_code"),
            retry_after_ms,
            epoch_ms(),
        )

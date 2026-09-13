"""SoAI - Messaging transport runtime protocol [backend/core/messaging/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from core.concurrency.protocols import AsyncContextManagerProtocol
from core.messaging.account_models import (
    MessagingAccountCreate,
    MessagingAccountDeleteFence,
    MessagingAccountReconciliationResult,
    MessagingAccountUpdate,
    MessagingConversationVersion,
    MessagingProgressTarget,
)
from core.messaging.ingress_models import NormalizedMessagingEvent
from core.messaging.interaction_resolution import (
    MessagingInteractionResolution,
    MessagingInteractionTimeout,
)
from core.types.json import JSONDict

if TYPE_CHECKING:
    from core.events.types_conversation_durable import (
        ConversationControlCompletedEvent,
        ConversationInputTerminalEvent,
        ConversationInteractionRequiredEvent,
    )
    from core.messaging.callback_contracts import MessagingCallbackOwnershipState
    from core.messaging.delivery_models import MessagingDeliveryAttempt

__all__ = (
    "DatabaseMessagingAccountsProtocol",
    "DatabaseMessagingDeliveriesProtocol",
    "DatabaseMessagingIngressProtocol",
)


class DatabaseMessagingAccountsProtocol(Protocol):
    def account_lifecycle_lock(
        self,
        account_id: str,
    ) -> AsyncContextManagerProtocol[None]: ...

    async def list_accounts(self, user_id: int) -> list[JSONDict]: ...

    async def get_account(self, user_id: int, account_id: str) -> JSONDict | None: ...

    async def get_credentials(self, user_id: int, account_id: str) -> JSONDict | None: ...

    async def get_transport_account(
        self,
        account_id: str,
        platform: str,
    ) -> JSONDict | None: ...

    async def list_enabled_transport_accounts(self, platform: str) -> list[JSONDict]: ...

    async def list_deleting_transport_accounts(self) -> list[JSONDict]: ...

    async def list_reconcilable_transport_accounts(self, platform: str) -> list[JSONDict]: ...

    async def list_bound_conversation_versions(
        self,
        user_id: int,
        account_id: str,
    ) -> tuple[MessagingConversationVersion, ...]: ...

    async def list_progress_targets(
        self,
        *,
        active_before_ms: int,
        limit: int,
    ) -> list[MessagingProgressTarget]: ...

    async def create_account(
        self,
        user_id: int,
        account: MessagingAccountCreate,
    ) -> JSONDict: ...

    async def update_account(
        self,
        user_id: int,
        account_id: str,
        expected_revision: int,
        account: MessagingAccountUpdate,
    ) -> JSONDict | None: ...

    async def set_account_lifecycle_state(
        self,
        user_id: int,
        account_id: str,
        expected_revision: int,
        *,
        enabled: bool,
    ) -> JSONDict | None: ...

    async def record_reconciliation(
        self,
        *,
        user_id: int,
        account_id: str,
        expected_revision: int,
        lifecycle_generation: int,
        healthy: bool | None,
        callback_fingerprint: str | None,
        ownership_state: MessagingCallbackOwnershipState,
        health_code: str | None,
    ) -> MessagingAccountReconciliationResult | None: ...

    async def begin_delete(
        self,
        user_id: int,
        account_id: str,
        expected_revision: int,
    ) -> MessagingAccountDeleteFence | None: ...

    async def finalize_delete(
        self,
        user_id: int,
        account_id: str,
        lifecycle_generation: int,
    ) -> tuple[MessagingConversationVersion, ...] | None: ...


class DatabaseMessagingDeliveriesProtocol(Protocol):
    async def project_terminal_event(
        self,
        event: ConversationInputTerminalEvent,
    ) -> JSONDict | None: ...

    async def project_control_event(
        self,
        event: ConversationControlCompletedEvent,
    ) -> JSONDict | None: ...

    async def project_interaction_event(
        self,
        event: ConversationInteractionRequiredEvent,
    ) -> JSONDict | None: ...

    async def reconcile_prior_boot_deliveries(
        self,
        *,
        current_server_boot_id: str,
    ) -> int: ...

    async def claim_next_delivery_attempt(
        self,
        *,
        claim_owner: str,
        server_boot_id: str,
    ) -> MessagingDeliveryAttempt | None: ...

    async def settle_worker_failure(
        self,
        *,
        delivery_id: str,
        claim_generation: int,
        claim_owner: str,
        server_boot_id: str,
    ) -> JSONDict: ...

    async def mark_chunk_request_started(
        self,
        *,
        delivery_id: str,
        claim_generation: int,
        claim_owner: str,
        server_boot_id: str,
        ordinal: int,
        credential_fingerprint: str,
    ) -> bool: ...

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
    ) -> JSONDict: ...

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
    ) -> JSONDict: ...

    async def record_claim_pre_send_failure(
        self,
        *,
        delivery_id: str,
        claim_generation: int,
        claim_owner: str,
        server_boot_id: str,
        ordinal: int,
        failure_code: str,
    ) -> JSONDict: ...

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
    ) -> JSONDict: ...


class DatabaseMessagingIngressProtocol(Protocol):
    async def admit_event(
        self,
        *,
        account_id: str,
        event: NormalizedMessagingEvent,
    ) -> JSONDict: ...

    async def complete_pending_resets(self) -> list[JSONDict]: ...

    async def reconcile_pending_cancellations(self) -> list[JSONDict]: ...

    async def cleanup_transport_records(self) -> JSONDict: ...

    async def get_interaction_resolution(
        self,
        ingress_id: str,
    ) -> MessagingInteractionResolution | None: ...

    async def list_interaction_resolutions(
        self,
        *,
        limit: int,
    ) -> list[MessagingInteractionResolution]: ...

    async def claim_expired_interactions(
        self,
        *,
        limit: int,
    ) -> list[MessagingInteractionTimeout]: ...

    async def fail_interaction_route(
        self,
        *,
        route_id: str,
        diagnostic_code: str,
    ) -> None: ...

    async def resolve_interaction_focus(
        self,
        *,
        user_id: int,
        conv_id: str,
        focus_nonce: str,
    ) -> JSONDict | None: ...

    async def begin_discord_connection(
        self,
        *,
        account_id: str,
        user_id: int,
    ) -> JSONDict: ...

    async def record_discord_ready(
        self,
        *,
        account_id: str,
        connection_generation: int,
        event: NormalizedMessagingEvent,
        session_id: str,
        resume_gateway_url: str,
    ) -> JSONDict: ...

    async def commit_discord_dispatch(
        self,
        *,
        account_id: str,
        connection_generation: int,
        event: NormalizedMessagingEvent,
    ) -> JSONDict: ...

    async def mark_discord_session_gap(
        self,
        *,
        account_id: str,
        connection_generation: int,
    ) -> None: ...

    async def close_discord_session(
        self,
        *,
        account_id: str,
        connection_generation: int,
    ) -> None: ...

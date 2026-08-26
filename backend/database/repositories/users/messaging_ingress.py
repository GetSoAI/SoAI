"""SoAI - Messaging ingress repository [backend/database/repositories/users/messaging_ingress.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from core.messaging.inbound_message_title import build_inbound_message_title
from core.runtime.soai_identifiers import create_prefixed_hex_id
from core.serialization.json import serialize_json_compact_stable
from core.timing.epoch import epoch_ms
from database.repositories.users.domain_event_outbox_dispatch_signal import (
    notify_domain_event_outbox_dispatch_requested,
)
from database.repositories.users.messaging_control_cancellation_recovery import (
    sync_reconcile_pending_messaging_cancellations,
)
from database.repositories.users.messaging_discord_sessions import (
    sync_begin_discord_connection,
    sync_close_discord_session,
    sync_commit_discord_dispatch,
    sync_mark_discord_session_gap,
    sync_record_discord_ready,
)
from database.repositories.users.messaging_ingress_admission import (
    sync_admit_messaging_event,
)
from database.repositories.users.messaging_interaction_fencing import (
    sync_fail_messaging_interaction_route,
)
from database.repositories.users.messaging_interaction_resolution_reads import (
    get_messaging_interaction_resolution,
    list_messaging_interaction_resolutions,
    resolve_messaging_interaction_focus,
)
from database.repositories.users.messaging_interaction_timeouts import (
    sync_claim_expired_messaging_interactions,
)
from database.repositories.users.messaging_reset_operations import (
    sync_complete_pending_messaging_resets,
)
from database.repositories.users.messaging_transport_retention import (
    sync_cleanup_messaging_transport_records,
)
from database.repositories.users.storage_backed_repository_runtime import (
    resolve_storage_backed_repository_root,
)

if TYPE_CHECKING:
    from core.messaging.ingress_models import NormalizedMessagingEvent
    from core.messaging.interaction_resolution import (
        MessagingInteractionResolution,
        MessagingInteractionTimeout,
    )
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseMessagingIngress",)


class DatabaseMessagingIngress:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core
        self.event_bus = deps.event_bus
        self.fernets = deps.fernet
        self.storage_root = resolve_storage_backed_repository_root(deps)

    async def admit_event(
        self,
        *,
        account_id: str,
        event: NormalizedMessagingEvent,
    ) -> JSONDict:
        fingerprint_json = serialize_json_compact_stable(event.fingerprint_payload())
        result = await self.core.writer.queue_write_operation(
            sync_admit_messaging_event,
            self.fernets,
            account_id,
            create_prefixed_hex_id("msgin"),
            create_prefixed_hex_id("cinput", length=16),
            create_prefixed_hex_id("conv"),
            event,
            hashlib.sha256(fingerprint_json.encode("utf-8")).hexdigest(),
            build_inbound_message_title(event),
            epoch_ms(),
            self.storage_root,
        )
        notify_domain_event_outbox_dispatch_requested(self.event_bus)
        return result

    async def complete_pending_resets(self) -> list[JSONDict]:
        results = await self.core.writer.queue_write_operation(
            sync_complete_pending_messaging_resets,
        )
        notify_domain_event_outbox_dispatch_requested(self.event_bus)
        return results

    async def reconcile_pending_cancellations(self) -> list[JSONDict]:
        return await self.core.writer.queue_write_operation(
            sync_reconcile_pending_messaging_cancellations,
        )

    async def cleanup_transport_records(self) -> JSONDict:
        return await self.core.writer.queue_write_operation(
            sync_cleanup_messaging_transport_records,
            epoch_ms(),
        )

    async def get_interaction_resolution(
        self,
        ingress_id: str,
    ) -> MessagingInteractionResolution | None:
        return await self.core.reader.execute_read(
            get_messaging_interaction_resolution,
            self.fernets,
            ingress_id,
            epoch_ms(),
        )

    async def list_interaction_resolutions(
        self,
        *,
        limit: int,
    ) -> list[MessagingInteractionResolution]:
        return await self.core.reader.execute_read(
            list_messaging_interaction_resolutions,
            self.fernets,
            limit,
            epoch_ms(),
        )

    async def claim_expired_interactions(
        self,
        *,
        limit: int,
    ) -> list[MessagingInteractionTimeout]:
        return await self.core.writer.queue_write_operation(
            sync_claim_expired_messaging_interactions,
            epoch_ms(),
            limit,
        )

    async def fail_interaction_route(
        self,
        *,
        route_id: str,
        diagnostic_code: str,
    ) -> None:
        await self.core.writer.queue_write_operation(
            sync_fail_messaging_interaction_route,
            route_id,
            diagnostic_code,
            epoch_ms(),
        )

    async def resolve_interaction_focus(
        self,
        *,
        user_id: int,
        conv_id: str,
        focus_nonce: str,
    ) -> JSONDict | None:
        return await self.core.reader.execute_read(
            resolve_messaging_interaction_focus,
            user_id=user_id,
            conv_id=conv_id,
            focus_nonce=focus_nonce,
            now_ms=epoch_ms(),
        )

    async def begin_discord_connection(self, *, account_id: str, user_id: int) -> JSONDict:
        return await self.core.writer.queue_write_operation(
            sync_begin_discord_connection,
            account_id,
            user_id,
            epoch_ms(),
        )

    async def record_discord_ready(
        self,
        *,
        account_id: str,
        connection_generation: int,
        event: NormalizedMessagingEvent,
        session_id: str,
        resume_gateway_url: str,
    ) -> JSONDict:
        fingerprint_json = serialize_json_compact_stable(event.fingerprint_payload())
        return await self.core.writer.queue_write_operation(
            sync_record_discord_ready,
            self.fernets,
            account_id,
            connection_generation,
            event,
            session_id,
            resume_gateway_url,
            create_prefixed_hex_id("msgin"),
            hashlib.sha256(fingerprint_json.encode("utf-8")).hexdigest(),
            epoch_ms(),
        )

    async def commit_discord_dispatch(
        self,
        *,
        account_id: str,
        connection_generation: int,
        event: NormalizedMessagingEvent,
    ) -> JSONDict:
        fingerprint_json = serialize_json_compact_stable(event.fingerprint_payload())
        result = await self.core.writer.queue_write_operation(
            sync_commit_discord_dispatch,
            self.fernets,
            account_id,
            connection_generation,
            event,
            create_prefixed_hex_id("msgin"),
            create_prefixed_hex_id("cinput", length=16),
            create_prefixed_hex_id("conv"),
            hashlib.sha256(fingerprint_json.encode("utf-8")).hexdigest(),
            build_inbound_message_title(event),
            epoch_ms(),
            self.storage_root,
        )
        notify_domain_event_outbox_dispatch_requested(self.event_bus)
        return result

    async def mark_discord_session_gap(
        self,
        *,
        account_id: str,
        connection_generation: int,
    ) -> None:
        await self.core.writer.queue_write_operation(
            sync_mark_discord_session_gap,
            account_id,
            connection_generation,
            epoch_ms(),
        )

    async def close_discord_session(
        self,
        *,
        account_id: str,
        connection_generation: int,
    ) -> None:
        await self.core.writer.queue_write_operation(
            sync_close_discord_session,
            account_id,
            connection_generation,
            epoch_ms(),
        )

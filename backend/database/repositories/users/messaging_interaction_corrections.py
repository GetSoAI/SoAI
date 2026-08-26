"""SoAI - Durable invalid Messaging interaction corrections [backend/database/repositories/users/messaging_interaction_corrections.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.messaging.response_catalog import resolve_messaging_response_text
from database.repositories.users.messaging_delivery_insertion import (
    MessagingDeliveryIntent,
    sync_insert_messaging_delivery_intent,
)
from database.repositories.users.messaging_ingress_records import (
    insert_messaging_ingress_record,
)

if TYPE_CHECKING:
    from core.conversations.conversation_source import MessagingPlatform
    from core.messaging.ingress_models import NormalizedMessagingEvent
    from core.types.json import JSONDict
    from database.repositories.users.messaging_interaction_correlation import (
        MessagingInteractionRouteCandidate,
    )

__all__ = ("sync_record_invalid_messaging_interaction",)


def sync_record_invalid_messaging_interaction(
    conn: sqlite3.Connection,
    *,
    route: MessagingInteractionRouteCandidate,
    ingress_id: str,
    account_id: str,
    user_id: int,
    account_generation: int,
    platform: MessagingPlatform,
    locale: str,
    event: NormalizedMessagingEvent,
    content_fingerprint: str,
    response_key: str,
    diagnostic_code: str,
    accepted_at_ms: int,
) -> JSONDict:
    insert_messaging_ingress_record(
        conn,
        classification="interaction",
        outcome="rejected",
        diagnostic_code=diagnostic_code,
        sender_id=event.sender_id,
        ingress_id=ingress_id,
        account_id=account_id,
        user_id=user_id,
        event=event,
        content_fingerprint=content_fingerprint,
        accepted_at_ms=accepted_at_ms,
    )
    conn.execute(
        """
        UPDATE messaging_ingress_events
        SET linked_interaction_route_id = ?, result_conv_id = ?,
            account_generation = ?, binding_generation = ?
        WHERE ingress_id = ?
        """,
        (
            route.route_id,
            route.conv_id,
            account_generation,
            route.binding_generation,
            ingress_id,
        ),
    )
    sync_insert_messaging_delivery_intent(
        conn,
        MessagingDeliveryIntent(
            source_event_id=f"messaging_interaction_correction:{ingress_id}",
            account_id=account_id,
            user_id=user_id,
            platform=platform,
            remote_thread_type=event.remote_thread_type,
            remote_thread_key=event.remote_thread_key,
            originating_sender_id=str(event.sender_id),
            account_generation=account_generation,
            binding_generation=route.binding_generation,
            source_input_id=route.input_id,
            source_message_id=None,
            purpose="interaction",
            content_text=resolve_messaging_response_text(locale, response_key),
            initial_state="pending",
            failure_code=None,
            created_at_ms=accepted_at_ms,
        ),
    )
    return {
        "status": "ignored",
        "outcome": "rejected",
        "classification": "interaction",
        "ingress_id": ingress_id,
        "conv_id": route.conv_id,
        "user_id": user_id,
    }

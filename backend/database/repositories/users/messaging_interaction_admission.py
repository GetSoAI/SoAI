"""SoAI - Atomic provider interaction answer admission [backend/database/repositories/users/messaging_interaction_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from cryptography.fernet import Fernet

from core.errors.exceptions import StateError, ValidationError
from core.messaging.interaction_answers import parse_messaging_interaction_answer
from core.serialization.json import serialize_json_compact_stable
from core.serialization.json_parsing import parse_json_dict
from core.tasks.interaction_secrets import interaction_secret_handoff_ttl_ms
from database.repositories.tasks.conversation_interaction_secrets import (
    sync_stage_interaction_secret_resolution,
)
from database.repositories.users.messaging_ingress_records import insert_messaging_ingress_record
from database.repositories.users.messaging_interaction_corrections import (
    sync_record_invalid_messaging_interaction,
)
from database.repositories.users.messaging_interaction_correlation import (
    sync_correlate_messaging_interaction,
)

if TYPE_CHECKING:
    from core.conversations.conversation_source import MessagingPlatform
    from core.messaging.ingress_models import NormalizedMessagingEvent
    from core.types.json import JSONDict

__all__ = ("sync_try_admit_messaging_interaction",)


def _record_interaction_ingress(
    conn: sqlite3.Connection,
    *,
    ingress_id: str,
    account_id: str,
    user_id: int,
    event: NormalizedMessagingEvent,
    content_fingerprint: str,
    outcome: str,
    diagnostic_code: str | None,
    accepted_at_ms: int,
) -> None:
    insert_messaging_ingress_record(
        conn,
        classification="interaction",
        outcome=outcome,
        sender_id=event.sender_id,
        diagnostic_code=diagnostic_code,
        accepted_at_ms=accepted_at_ms,
        ingress_id=ingress_id,
        account_id=account_id,
        user_id=user_id,
        event=event,
        content_fingerprint=content_fingerprint,
    )


def sync_try_admit_messaging_interaction(
    conn: sqlite3.Connection,
    fernets: tuple[Fernet, ...],
    *,
    ingress_id: str,
    account_id: str,
    user_id: int,
    account_generation: int,
    platform: MessagingPlatform,
    locale: str,
    plaintext_secret_replies_enabled: bool,
    event: NormalizedMessagingEvent,
    content_fingerprint: str,
    accepted_at_ms: int,
) -> JSONDict | None:
    correlation = sync_correlate_messaging_interaction(
        conn,
        account_id=account_id,
        user_id=user_id,
        account_generation=account_generation,
        event=event,
        accepted_at_ms=accepted_at_ms,
    )
    if correlation is None:
        return None
    route = correlation.route
    if correlation.state == "stale":
        return sync_record_invalid_messaging_interaction(
            conn,
            route=route,
            ingress_id=ingress_id,
            account_id=account_id,
            user_id=user_id,
            account_generation=account_generation,
            platform=platform,
            locale=locale,
            event=event,
            content_fingerprint=content_fingerprint,
            response_key="interaction_stale_answer",
            diagnostic_code="stale_interaction_answer",
            accepted_at_ms=accepted_at_ms,
        )
    metadata = parse_json_dict(
        route.task_metadata_json,
        field="Messaging interaction task metadata",
    )
    interaction_type = route.interaction_type
    if interaction_type == "vault_secret_request":
        if not plaintext_secret_replies_enabled or event.media:
            return sync_record_invalid_messaging_interaction(
                conn,
                route=route,
                ingress_id=ingress_id,
                account_id=account_id,
                user_id=user_id,
                account_generation=account_generation,
                platform=platform,
                locale=locale,
                event=event,
                content_fingerprint=content_fingerprint,
                response_key="interaction_secure_chat_required",
                diagnostic_code="secret_chat_required",
                accepted_at_ms=accepted_at_ms,
            )
        resolution_payload: JSONDict = {
            "password": event.text,
            "save_to_vault": False,
        }
        sync_stage_interaction_secret_resolution(
            conn,
            fernets,
            task_id=route.task_id,
            user_id=user_id,
            conv_id=route.conv_id,
            checkpoint_generation=route.checkpoint_generation,
            resolution_payload=resolution_payload,
            expires_at_ms=accepted_at_ms + interaction_secret_handoff_ttl_ms(),
            staged_at_ms=accepted_at_ms,
        )
        persisted_resolution: str | None = None
        secret_reply = True
    else:
        try:
            resolution_payload = parse_messaging_interaction_answer(
                interaction_type=interaction_type,
                task_metadata=metadata,
                text=event.text,
                matched_token=correlation.matched_token,
            )
        except ValidationError:
            return sync_record_invalid_messaging_interaction(
                conn,
                route=route,
                ingress_id=ingress_id,
                account_id=account_id,
                user_id=user_id,
                account_generation=account_generation,
                platform=platform,
                locale=locale,
                event=event,
                content_fingerprint=content_fingerprint,
                response_key="interaction_invalid_answer",
                diagnostic_code="invalid_interaction_answer",
                accepted_at_ms=accepted_at_ms,
            )
        persisted_resolution = serialize_json_compact_stable(resolution_payload)
        secret_reply = False
    _record_interaction_ingress(
        conn,
        ingress_id=ingress_id,
        account_id=account_id,
        user_id=user_id,
        event=event,
        content_fingerprint=content_fingerprint,
        outcome="accepted",
        diagnostic_code=None,
        accepted_at_ms=accepted_at_ms,
    )
    updated = conn.execute(
        """
        UPDATE messaging_interaction_routes
        SET state = 'resolving', resolution_ingress_id = ?
        WHERE route_id = ? AND state = 'pending' AND checkpoint_generation = ?
        """,
        (ingress_id, route.route_id, route.checkpoint_generation),
    ).rowcount
    if updated != 1:
        raise StateError("Messaging interaction resolution lost its route claim.")
    conn.execute(
        """
        UPDATE messaging_ingress_events
        SET linked_interaction_route_id = ?, result_conv_id = ?,
            account_generation = ?, binding_generation = ?,
            interaction_resolution_json = ?
        WHERE ingress_id = ?
        """,
        (
            route.route_id,
            route.conv_id,
            account_generation,
            route.binding_generation,
            persisted_resolution,
            ingress_id,
        ),
    )
    return {
        "status": "accepted",
        "outcome": "accepted",
        "classification": "interaction",
        "ingress_id": ingress_id,
        "route_id": route.route_id,
        "task_id": route.task_id,
        "conv_id": route.conv_id,
        "user_id": user_id,
        "interaction_type": interaction_type,
        "checkpoint_generation": route.checkpoint_generation,
        "interaction_resolution": resolution_payload if not secret_reply else None,
        "secret_reply": secret_reply,
    }

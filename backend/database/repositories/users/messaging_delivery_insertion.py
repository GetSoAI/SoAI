"""SoAI - Durable provider delivery intent insertion [backend/database/repositories/users/messaging_delivery_insertion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.messaging.delivery_chunking import plan_messaging_text_chunks
from core.preview_contract.preview_contract import render_preview_references_as_plain_text
from core.types.json import JSONDict

if TYPE_CHECKING:
    from typing import Literal

    from core.conversations.conversation_source import MessagingPlatform

    type MessagingDeliveryPurpose = Literal["assistant", "interaction", "control"]

__all__ = ("MessagingDeliveryIntent", "sync_insert_messaging_delivery_intent")


@dataclass(frozen=True, slots=True)
class MessagingDeliveryIntent:
    source_event_id: str
    account_id: str
    user_id: int
    platform: MessagingPlatform
    remote_thread_type: str
    remote_thread_key: str
    originating_sender_id: str
    account_generation: int
    binding_generation: int
    source_input_id: str | None
    source_message_id: int | None
    purpose: MessagingDeliveryPurpose
    content_text: str
    initial_state: str
    failure_code: str | None
    created_at_ms: int


def sync_insert_messaging_delivery_intent(
    conn: sqlite3.Connection,
    intent: MessagingDeliveryIntent,
) -> JSONDict:
    content_text = render_preview_references_as_plain_text(intent.content_text)
    chunk_plan = plan_messaging_text_chunks(intent.platform, content_text)
    state = intent.initial_state
    failure_code = intent.failure_code
    if state == "pending" and chunk_plan.failure_code is not None:
        state = "failed"
        failure_code = chunk_plan.failure_code
    created_at_ms = intent.created_at_ms
    terminal_at_ms = created_at_ms if state in {"failed", "skipped"} else None
    digest = hashlib.sha256(intent.source_event_id.encode()).hexdigest()[:24]
    delivery_id = f"delivery_{digest}"
    conn.execute(
        """
        INSERT INTO messaging_deliveries (
            delivery_id, account_id, user_id, remote_thread_type, remote_thread_key,
            originating_sender_id, account_generation, binding_generation,
            source_event_id, source_input_id, source_message_id, purpose, state,
            failure_code, next_attempt_at_ms, created_at_ms, terminal_at_ms,
            updated_at_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            delivery_id,
            intent.account_id,
            intent.user_id,
            intent.remote_thread_type,
            intent.remote_thread_key,
            intent.originating_sender_id,
            intent.account_generation,
            intent.binding_generation,
            intent.source_event_id,
            intent.source_input_id,
            intent.source_message_id,
            intent.purpose,
            state,
            failure_code,
            created_at_ms,
            created_at_ms,
            terminal_at_ms,
            created_at_ms,
        ),
    )
    if state == "pending":
        for ordinal, chunk in enumerate(chunk_plan.chunks):
            conn.execute(
                """
                INSERT INTO messaging_delivery_chunks (
                    delivery_id, ordinal, content_text, content_hash, state,
                    created_at_ms, updated_at_ms
                ) VALUES (?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    delivery_id,
                    ordinal,
                    chunk,
                    hashlib.sha256(chunk.encode()).hexdigest(),
                    created_at_ms,
                    created_at_ms,
                ),
            )
    result: JSONDict = {"delivery_id": delivery_id, "state": state}
    return result

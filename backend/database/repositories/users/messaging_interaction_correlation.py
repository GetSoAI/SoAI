"""SoAI - Messaging interaction sender and prompt correlation [backend/database/repositories/users/messaging_interaction_correlation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.errors.exceptions import StateError
from core.messaging.interaction_answers import extract_messaging_interaction_tokens

if TYPE_CHECKING:
    from core.messaging.ingress_models import NormalizedMessagingEvent

__all__ = (
    "MessagingInteractionCorrelation",
    "MessagingInteractionRouteCandidate",
    "sync_correlate_messaging_interaction",
)


@dataclass(frozen=True, slots=True)
class MessagingInteractionRouteCandidate:
    route_id: str
    task_id: str
    conv_id: str
    input_id: str
    interaction_type: str
    checkpoint_generation: int
    reply_token_hash: str
    provider_prompt_message_id: str | None
    task_metadata_json: str
    binding_generation: int
    state: str
    expires_at_ms: int
    task_status: str
    current_binding: bool

    def is_pending(self, accepted_at_ms: int) -> bool:
        return (
            self.state == "pending"
            and self.expires_at_ms > accepted_at_ms
            and self.task_status == "input_required"
            and self.current_binding
        )


@dataclass(frozen=True, slots=True)
class MessagingInteractionCorrelation:
    route: MessagingInteractionRouteCandidate
    matched_token: str | None
    state: Literal["pending", "stale"]


def _decode_candidate(row: sqlite3.Row) -> MessagingInteractionRouteCandidate:
    if not all(
        isinstance(row[index], str) and row[index] for index in (0, 1, 2, 3, 4, 6, 8, 10, 12)
    ):
        raise StateError("Messaging interaction correlation identity is invalid.")
    if not all(isinstance(row[index], int) for index in (5, 9, 11, 13)):
        raise StateError("Messaging interaction correlation generation is invalid.")
    prompt_id = row[7]
    if prompt_id is not None and not isinstance(prompt_id, str):
        raise StateError("Messaging interaction prompt identity is invalid.")
    return MessagingInteractionRouteCandidate(
        route_id=row[0],
        task_id=row[1],
        conv_id=row[2],
        input_id=row[3],
        interaction_type=row[4],
        checkpoint_generation=row[5],
        reply_token_hash=row[6],
        provider_prompt_message_id=prompt_id,
        task_metadata_json=row[8],
        binding_generation=row[9],
        state=row[10],
        expires_at_ms=row[11],
        task_status=row[12],
        current_binding=row[13] == 1,
    )


def _scoped_routes(
    conn: sqlite3.Connection,
    *,
    account_id: str,
    user_id: int,
    account_generation: int,
    event: NormalizedMessagingEvent,
) -> list[MessagingInteractionRouteCandidate]:
    rows = conn.execute(
        """
        SELECT route.route_id, route.task_id, route.conv_id, route.input_id,
               route.interaction_type, route.checkpoint_generation,
               route.reply_token_hash, route.provider_prompt_message_id,
               task.metadata, route.binding_generation, route.state,
               route.expires_at_ms, task.status,
               CASE WHEN binding.conv_id = route.conv_id
                          AND binding.binding_generation = route.binding_generation
                    THEN 1 ELSE 0 END
        FROM messaging_interaction_routes AS route
        JOIN unified_tasks AS task ON task.task_id = route.task_id
        LEFT JOIN messaging_thread_bindings AS binding
          ON binding.account_id = route.account_id AND binding.user_id = route.user_id
         AND binding.remote_thread_type = route.remote_thread_type
         AND binding.remote_thread_key = route.remote_thread_key
        WHERE route.account_id = ? AND route.user_id = ?
          AND route.account_generation = ?
          AND route.remote_thread_type = ? AND route.remote_thread_key = ?
          AND route.originating_sender_id = ?
        ORDER BY route.created_at_ms ASC, route.route_id ASC
        """,
        (
            account_id,
            user_id,
            account_generation,
            event.remote_thread_type,
            event.remote_thread_key,
            event.sender_id,
        ),
    ).fetchall()
    return [_decode_candidate(row) for row in rows]


def sync_correlate_messaging_interaction(
    conn: sqlite3.Connection,
    *,
    account_id: str,
    user_id: int,
    account_generation: int,
    event: NormalizedMessagingEvent,
    accepted_at_ms: int,
) -> MessagingInteractionCorrelation | None:
    routes = _scoped_routes(
        conn,
        account_id=account_id,
        user_id=user_id,
        account_generation=account_generation,
        event=event,
    )
    reply_reference = event.reply_to_provider_message_id
    if reply_reference is not None:
        matched = [route for route in routes if route.provider_prompt_message_id == reply_reference]
        if len(matched) == 1:
            route = matched[0]
            return MessagingInteractionCorrelation(
                route=route,
                matched_token=None,
                state="pending" if route.is_pending(accepted_at_ms) else "stale",
            )
        return None
    for token in extract_messaging_interaction_tokens(event.text):
        token_hash = hashlib.sha256(token.casefold().encode()).hexdigest()
        matched = [route for route in routes if route.reply_token_hash == token_hash]
        if len(matched) == 1:
            route = matched[0]
            return MessagingInteractionCorrelation(
                route=route,
                matched_token=token,
                state="pending" if route.is_pending(accepted_at_ms) else "stale",
            )
    pending = [route for route in routes if route.is_pending(accepted_at_ms)]
    if len(routes) == 1 and len(pending) == 1 and pending[0].provider_prompt_message_id is not None:
        return MessagingInteractionCorrelation(
            route=pending[0],
            matched_token=None,
            state="pending",
        )
    return None

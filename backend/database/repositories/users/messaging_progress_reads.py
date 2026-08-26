"""SoAI - Fenced Messaging progress target reads [backend/database/repositories/users/messaging_progress_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import StateError
from core.messaging.account_models import MessagingProgressTarget
from core.messaging.account_validation import require_messaging_platform
from core.security.secret_crypto import decrypt_required_secret
from core.serialization.json_parsing import parse_json_dict
from database.core.query_execution import query_to_dicts
from database.core.row_fields import require_row_non_empty_str, require_row_positive_int

if TYPE_CHECKING:
    from cryptography.fernet import Fernet

__all__ = ("read_messaging_progress_targets",)


async def read_messaging_progress_targets(
    database: aiosqlite.Connection,
    *,
    fernets: tuple[Fernet, ...],
    active_before_ms: int,
    limit: int,
) -> list[MessagingProgressTarget]:
    rows = await query_to_dicts(
        database,
        """
        SELECT input.input_id, ingress.account_id, input.user_id, ingress.platform,
               ingress.remote_thread_key, account.credential_ciphertext
        FROM webui_conversation_inputs AS input
        JOIN messaging_ingress_events AS ingress
          ON ingress.ingress_id = input.messaging_ingress_id
        JOIN messaging_accounts AS account
          ON account.account_id = ingress.account_id
         AND account.user_id = input.user_id
         AND account.platform = ingress.platform
        JOIN messaging_thread_bindings AS binding
          ON binding.account_id = ingress.account_id
         AND binding.user_id = input.user_id
         AND binding.remote_thread_type = ingress.remote_thread_type
         AND binding.remote_thread_key = ingress.remote_thread_key
         AND binding.conv_id = input.conv_id
        LEFT JOIN messaging_authorized_senders AS sender
          ON sender.account_id = ingress.account_id
         AND sender.user_id = input.user_id
         AND sender.sender_id = ingress.sender_id
        WHERE input.transport_origin = 'messaging'
          AND input.state IN ('materializing', 'running')
          AND account.platform IN ('telegram', 'discord')
          AND account.lifecycle_state IN ('enabled', 'degraded')
          AND (account.accept_messages_from_anyone = 1
               OR sender.sender_id IS NOT NULL)
          AND account.lifecycle_generation = ingress.account_generation
          AND binding.binding_generation = ingress.binding_generation
          AND COALESCE(input.running_at_ms, input.materialized_at_ms,
                       input.claimed_at_ms, input.accepted_at_ms) <= ?
        ORDER BY input.accepted_at_ms, input.id
        LIMIT ?
        """,
        (active_before_ms, limit),
    )
    targets: list[MessagingProgressTarget] = []
    for row in rows:
        ciphertext = require_row_non_empty_str(
            row.get("credential_ciphertext"),
            label="Messaging progress credentials",
            build_error=StateError,
        )
        targets.append(
            MessagingProgressTarget(
                input_id=require_row_non_empty_str(
                    row.get("input_id"),
                    label="Messaging progress input id",
                    build_error=StateError,
                ),
                account_id=require_row_non_empty_str(
                    row.get("account_id"),
                    label="Messaging progress account id",
                    build_error=StateError,
                ),
                user_id=require_row_positive_int(
                    row.get("user_id"),
                    label="Messaging progress user id",
                    build_error=StateError,
                ),
                platform=require_messaging_platform(
                    require_row_non_empty_str(
                        row.get("platform"),
                        label="Messaging progress platform",
                        build_error=StateError,
                    ),
                ),
                remote_thread_key=require_row_non_empty_str(
                    row.get("remote_thread_key"),
                    label="Messaging progress remote thread key",
                    build_error=StateError,
                ),
                credentials=parse_json_dict(
                    decrypt_required_secret(
                        fernets,
                        ciphertext,
                        label="Messaging progress credentials",
                    ),
                    field="Messaging progress credentials",
                ),
            ),
        )
    return targets

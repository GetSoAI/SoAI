"""SoAI - Durable Messaging interaction resolution reads [backend/database/repositories/users/messaging_interaction_resolution_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import sqlite3

import aiosqlite
from cryptography.fernet import Fernet

from core.errors.exceptions import StateError
from core.messaging.interaction_resolution import MessagingInteractionResolution
from core.security.secret_crypto import decrypt_required_secret
from core.serialization.json_parsing import parse_json_dict
from core.types.json import JSONDict

__all__ = (
    "get_messaging_interaction_resolution",
    "list_messaging_interaction_resolutions",
    "resolve_messaging_interaction_focus",
)

_RESOLUTION_SELECT = """
    SELECT ingress.ingress_id, route.route_id, route.task_id, route.conv_id,
           route.user_id, route.interaction_type, route.checkpoint_generation,
           ingress.interaction_resolution_json, secret.secret_ciphertext,
           secret.state, secret.expires_at_ms
    FROM messaging_interaction_routes AS route
    JOIN messaging_ingress_events AS ingress
      ON ingress.ingress_id = route.resolution_ingress_id
     AND ingress.linked_interaction_route_id = route.route_id
    JOIN unified_tasks AS task ON task.task_id = route.task_id
    LEFT JOIN task_interaction_secret_handoffs AS secret
      ON secret.task_id = route.task_id
     AND secret.user_id = route.user_id
     AND secret.conv_id = route.conv_id
     AND secret.checkpoint_generation = route.checkpoint_generation
    WHERE route.state = 'resolving' AND task.status = 'input_required'
      AND (
          route.interaction_type != 'vault_secret_request'
          OR (secret.state = 'resolution_staged' AND secret.expires_at_ms > ?)
      )
"""


def _decode_resolution(
    row: sqlite3.Row,
    fernets: tuple[Fernet, ...],
) -> MessagingInteractionResolution:
    if not all(isinstance(row[index], str) and row[index] for index in (0, 1, 2, 3, 5)):
        raise StateError("Messaging interaction resolution identity is invalid.")
    if not isinstance(row[4], int) or row[4] <= 0:
        raise StateError("Messaging interaction resolution owner is invalid.")
    if not isinstance(row[6], int) or row[6] <= 0:
        raise StateError("Messaging interaction resolution generation is invalid.")
    interaction_type = row[5]
    if interaction_type == "vault_secret_request":
        if row[9] != "resolution_staged" or not isinstance(row[8], str):
            raise StateError("Messaging secret interaction resolution is unavailable.")
        plaintext = decrypt_required_secret(
            fernets,
            row[8],
            label="staged interaction secret resolution",
        )
        payload = parse_json_dict(
            plaintext,
            field="Staged interaction secret resolution",
        )
    else:
        if not isinstance(row[7], str):
            raise StateError("Messaging interaction resolution payload is unavailable.")
        payload = parse_json_dict(row[7], field="Messaging interaction resolution")
    return MessagingInteractionResolution(
        ingress_id=row[0],
        route_id=row[1],
        task_id=row[2],
        conv_id=row[3],
        user_id=row[4],
        interaction_type=interaction_type,
        checkpoint_generation=row[6],
        payload=payload,
    )


async def get_messaging_interaction_resolution(
    conn: aiosqlite.Connection,
    fernets: tuple[Fernet, ...],
    ingress_id: str,
    now_ms: int,
) -> MessagingInteractionResolution | None:
    cursor = await conn.execute(
        f"{_RESOLUTION_SELECT} AND ingress.ingress_id = ? LIMIT 1",
        (now_ms, ingress_id),
    )
    row = await cursor.fetchone()
    return None if row is None else _decode_resolution(row, fernets)


async def list_messaging_interaction_resolutions(
    conn: aiosqlite.Connection,
    fernets: tuple[Fernet, ...],
    limit: int,
    now_ms: int,
) -> list[MessagingInteractionResolution]:
    cursor = await conn.execute(
        f"{_RESOLUTION_SELECT} ORDER BY route.created_at_ms ASC, route.route_id ASC LIMIT ?",
        (now_ms, limit),
    )
    rows = list(await cursor.fetchall())
    return [_decode_resolution(row, fernets) for row in rows]


async def resolve_messaging_interaction_focus(
    conn: aiosqlite.Connection,
    *,
    user_id: int,
    conv_id: str,
    focus_nonce: str,
    now_ms: int,
) -> JSONDict | None:
    nonce_hash = hashlib.sha256(focus_nonce.encode()).hexdigest()
    cursor = await conn.execute(
        """
        SELECT route.task_id, route.interaction_type
        FROM messaging_interaction_routes AS route
        JOIN unified_tasks AS task ON task.task_id = route.task_id
        WHERE route.user_id = ? AND route.conv_id = ? AND route.focus_nonce_hash = ?
          AND route.state = 'pending' AND route.expires_at_ms > ?
          AND task.status = 'input_required'
        ORDER BY route.created_at_ms DESC, route.route_id DESC
        LIMIT 2
        """,
        (user_id, conv_id, nonce_hash, now_ms),
    )
    rows = list(await cursor.fetchall())
    if not rows:
        return None
    if len(rows) != 1:
        raise StateError("Messaging interaction focus nonce is ambiguous.")
    task_id, interaction_type = rows[0]
    if not isinstance(task_id, str) or not isinstance(interaction_type, str):
        raise StateError("Messaging interaction focus identity is invalid.")
    return {"task_id": task_id, "interaction_type": interaction_type}

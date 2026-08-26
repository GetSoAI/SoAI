"""SoAI - Anchor-centered conversation message window candidate queries [backend/database/repositories/users/message_window_around_candidate_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import aiosqlite

from core.errors.exceptions import ValidationError
from database.core.query_execution import query_one_to_dict, query_to_dicts
from database.repositories.users.message_window_candidate_queries import (
    MESSAGE_WINDOW_IDENTITY_COLUMNS,
    MESSAGE_WINDOW_REPRESENTATIVE_PREDICATE,
    LogicalMessageIdentity,
    identities_from_rows,
    require_message_window_cursor,
    trim_split_pair_boundary,
)

__all__ = ("load_around_message_window_candidates",)


async def _resolve_anchor_identity(
    database: aiosqlite.Connection,
    *,
    conv_id: str,
    anchor_created_at_ms: int | None,
    anchor_id: int | None,
) -> LogicalMessageIdentity:
    anchor_at_ms, anchor_message_id = require_message_window_cursor(
        anchor_created_at_ms,
        anchor_id,
        "around",
    )
    row = await query_one_to_dict(
        database,
        """
        SELECT id, role, created_at_ms, assistant_turn_at_ms
        FROM webui_messages
        WHERE conv_id = ? AND created_at_ms = ? AND id = ?
        """,
        (conv_id, anchor_at_ms, anchor_message_id),
    )
    if row is None:
        raise ValidationError("around anchor message was not found.")
    identity = identities_from_rows([row])[0]
    if identity.assistant_turn_at_ms is None:
        return identity
    representative = await query_one_to_dict(
        database,
        f"""
        SELECT {MESSAGE_WINDOW_IDENTITY_COLUMNS}
        FROM webui_messages AS m
        WHERE m.conv_id = ?
          AND m.role = 'assistant'
          AND m.assistant_turn_at_ms = ?
          AND {MESSAGE_WINDOW_REPRESENTATIVE_PREDICATE}
        """,
        (conv_id, identity.assistant_turn_at_ms),
    )
    if representative is None:
        raise ValidationError("around anchor assistant turn is invalid.")
    return identities_from_rows([representative])[0]


async def load_around_message_window_candidates(
    database: aiosqlite.Connection,
    *,
    conv_id: str,
    candidate_limit: int,
    anchor_created_at_ms: int | None,
    anchor_id: int | None,
) -> tuple[list[LogicalMessageIdentity], LogicalMessageIdentity]:
    anchor = await _resolve_anchor_identity(
        database,
        conv_id=conv_id,
        anchor_created_at_ms=anchor_created_at_ms,
        anchor_id=anchor_id,
    )
    older_rows = await query_to_dicts(
        database,
        f"""
        SELECT {MESSAGE_WINDOW_IDENTITY_COLUMNS}
        FROM webui_messages AS m
        WHERE m.conv_id = ?
          AND {MESSAGE_WINDOW_REPRESENTATIVE_PREDICATE}
          AND (
              m.created_at_ms < ?
              OR (m.created_at_ms = ? AND m.id <= ?)
          )
        ORDER BY m.created_at_ms DESC, m.id DESC
        LIMIT ?
        """,
        (
            conv_id,
            anchor.created_at_ms,
            anchor.created_at_ms,
            anchor.message_id,
            candidate_limit,
        ),
    )
    newer_rows = await query_to_dicts(
        database,
        f"""
        SELECT {MESSAGE_WINDOW_IDENTITY_COLUMNS}
        FROM webui_messages AS m
        WHERE m.conv_id = ?
          AND {MESSAGE_WINDOW_REPRESENTATIVE_PREDICATE}
          AND (
              m.created_at_ms > ?
              OR (m.created_at_ms = ? AND m.id > ?)
          )
        ORDER BY m.created_at_ms ASC, m.id ASC
        LIMIT ?
        """,
        (
            conv_id,
            anchor.created_at_ms,
            anchor.created_at_ms,
            anchor.message_id,
            candidate_limit,
        ),
    )
    older_identities = trim_split_pair_boundary(
        identities_from_rows(older_rows),
        trim_older_boundary=len(older_rows) == candidate_limit,
        trim_newer_boundary=False,
    )
    newer_identities = trim_split_pair_boundary(
        identities_from_rows(newer_rows),
        trim_older_boundary=False,
        trim_newer_boundary=len(newer_rows) == candidate_limit,
    )
    identities_by_id = {
        identity.message_id: identity for identity in [*older_identities, *newer_identities]
    }
    return (
        sorted(
            identities_by_id.values(),
            key=lambda identity: (identity.created_at_ms, identity.message_id),
        ),
        anchor,
    )

"""SoAI - Shared user-conversation query filters [backend/database/repositories/users/conversation_query_filters.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from database.core.query_execution import query_one_to_dict

if TYPE_CHECKING:
    import aiosqlite

__all__ = (
    "build_before_timestamp_exclusive_filter",
    "conversation_exists_for_user",
)


async def conversation_exists_for_user(
    database: aiosqlite.Connection,
    *,
    conv_id: str,
    user_id: int,
) -> bool:
    row = await query_one_to_dict(
        database,
        "SELECT 1 FROM webui_conversations WHERE id = ? AND user_id = ?",
        (conv_id, user_id),
    )
    return row is not None


def build_before_timestamp_exclusive_filter(
    before_timestamp_exclusive: int | None,
    *,
    column: str = "created_at_ms",
) -> tuple[str, tuple[int, ...]]:
    if before_timestamp_exclusive is None:
        return ("", ())
    if (
        isinstance(before_timestamp_exclusive, bool)
        or not isinstance(before_timestamp_exclusive, int)
        or before_timestamp_exclusive < 0
    ):
        raise ValidationError(
            "before_timestamp_exclusive must be a non-negative integer when provided.",
        )
    normalized = int(before_timestamp_exclusive)
    return (f" AND {column} < ?", (normalized,))

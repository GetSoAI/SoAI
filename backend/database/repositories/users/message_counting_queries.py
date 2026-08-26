"""SoAI - Conversation message count query helpers [backend/database/repositories/users/message_counting_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Literal

import aiosqlite

from core.errors.exceptions import ValidationError
from core.validation.integers import is_strict_int
from database.core.query_execution import query_one_to_dict
from database.repositories.users.conversation_query_filters import (
    build_before_timestamp_exclusive_filter,
)

__all__ = ("load_conversation_message_count",)


async def load_conversation_message_count(
    database: aiosqlite.Connection,
    *,
    conv_id: str,
    before_timestamp_exclusive: int | None,
    counting_mode: Literal["canonical", "including_comparison_variants"],
) -> int:
    where_before, before_params = build_before_timestamp_exclusive_filter(
        before_timestamp_exclusive,
    )
    if counting_mode == "canonical":
        params_before: list[int | str] = [conv_id, *before_params]
        params_non_assistant: list[int | str] = list(params_before)
        params_assistant: list[int | str] = list(params_before)
        row = await query_one_to_dict(
            database,
            f"SELECT (SELECT COUNT(*) FROM webui_messages WHERE conv_id = ? AND message_type = 'chat' AND role != 'assistant'{where_before}) + (SELECT COUNT(DISTINCT assistant_turn_at_ms) FROM webui_messages WHERE conv_id = ? AND message_type = 'chat' AND role = 'assistant' AND assistant_turn_at_ms IS NOT NULL{where_before}) AS message_count",
            tuple(params_non_assistant + params_assistant),
        )
    elif counting_mode == "including_comparison_variants":
        if before_timestamp_exclusive is None:
            row = await query_one_to_dict(
                database,
                "SELECT message_count FROM webui_conversations WHERE id = ?",
                (conv_id,),
            )
        else:
            params: list[int | str] = [conv_id, *before_params]
            row = await query_one_to_dict(
                database,
                f"SELECT COUNT(*) AS message_count FROM webui_messages WHERE conv_id = ?{where_before}",
                tuple(params),
            )
    else:
        raise ValidationError("counting_mode must be canonical or including_comparison_variants.")
    if row is None:
        return 0
    count_value = row.get("message_count")
    if not is_strict_int(count_value) or count_value < 0:
        raise ValidationError("Stored conversation message count must be a non-negative integer.")
    return int(count_value)

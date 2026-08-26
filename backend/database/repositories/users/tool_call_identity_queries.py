"""SoAI - Tool-call identity query builders [backend/database/repositories/users/tool_call_identity_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("build_tool_call_identity_query",)


def build_tool_call_identity_query(
    *,
    conv_id: str,
    call_id: str,
    turn_id: str | None,
    iteration_index: int | None,
    message_index: int | None,
    assistant_turn_at_ms: int,
    model_variant_index: int,
) -> tuple[str, tuple[str | int | None, ...]]:
    normalized_turn_id = turn_id.strip() if turn_id and turn_id.strip() else None
    normalized_iteration_index = (
        iteration_index
        if isinstance(iteration_index, int)
        and not isinstance(iteration_index, bool)
        and iteration_index >= 0
        else None
    )
    normalized_message_index = (
        message_index
        if isinstance(message_index, int)
        and not isinstance(message_index, bool)
        and message_index >= 0
        else None
    )
    params: list[str | int | None] = [
        conv_id,
        call_id,
        assistant_turn_at_ms,
        model_variant_index,
        normalized_turn_id,
        normalized_turn_id,
        normalized_iteration_index if normalized_iteration_index is not None else -1,
        normalized_iteration_index if normalized_iteration_index is not None else -1,
        normalized_message_index if normalized_message_index is not None else -1,
        normalized_message_index if normalized_message_index is not None else -1,
    ]
    query = """
        SELECT *
        FROM webui_chat_tool_calls
        WHERE conv_id = ?
          AND call_id = ?
          AND assistant_turn_at_ms = ?
          AND model_variant_index = ?
          AND (
            (turn_id IS NULL AND ? IS NULL)
            OR turn_id = ?
          )
          AND (
            (iteration_index IS NULL AND ? = -1)
            OR iteration_index = ?
          )
          AND (
            (message_index IS NULL AND ? = -1)
            OR message_index = ?
          )
        ORDER BY created_at_ms DESC, id DESC
        LIMIT 1
        """
    return (query, tuple(params))

"""SoAI - Conversation message window logical activity counts [backend/database/repositories/users/message_window_activity_counts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import aiosqlite

from core.validation.requirements import require_non_negative_int
from database.core.data_conversions import SQLITE_BATCH_SIZE
from database.core.query_execution import query_to_dicts

__all__ = ("load_message_window_activity_counts",)


async def load_message_window_activity_counts(
    database: aiosqlite.Connection,
    *,
    conv_id: str,
    assistant_turn_at_ms_values: list[int],
) -> dict[int, int]:
    if not assistant_turn_at_ms_values:
        return {}
    counts: dict[int, int] = {}
    for start_index in range(0, len(assistant_turn_at_ms_values), SQLITE_BATCH_SIZE):
        batch = assistant_turn_at_ms_values[start_index : start_index + SQLITE_BATCH_SIZE]
        candidate_rows = ",".join("(?)" for _ in batch)
        rows = await query_to_dicts(
            database,
            f"""
            WITH candidate_turns(assistant_turn_at_ms) AS (
                VALUES {candidate_rows}
            ),
            logical_activities AS (
                SELECT
                    tool.assistant_turn_at_ms,
                    'tool' AS activity_type,
                    tool.model_variant_index,
                    tool.call_id AS activity_identity
                FROM webui_chat_tool_calls AS tool
                INNER JOIN candidate_turns AS candidate
                    ON candidate.assistant_turn_at_ms = tool.assistant_turn_at_ms
                WHERE tool.conv_id = ?
                UNION
                SELECT
                    message.assistant_turn_at_ms,
                    event.event_type AS activity_type,
                    message.model_variant_index,
                    CASE event.event_type
                        WHEN 'thinking_phase' THEN json_extract(
                            event.payload_json,
                            '$.thinking_phase.phase_id'
                        )
                        WHEN 'assistant_image' THEN event.sequence
                        WHEN 'loading_activity' THEN json_extract(
                            event.payload_json,
                            '$.loading_activity.started_at_ms'
                        )
                        WHEN 'processing_activity' THEN json_extract(
                            event.payload_json,
                            '$.processing_activity.started_at_ms'
                        )
                        WHEN 'wait_for_user_activity' THEN json_extract(
                            event.payload_json,
                            '$.wait_for_user_activity.started_at_ms'
                        )
                    END AS activity_identity
                FROM webui_assistant_message_events AS event
                INNER JOIN webui_messages AS message
                    ON message.conv_id = event.conv_id
                   AND message.role = 'assistant'
                   AND message.created_at_ms = event.assistant_at_ms
                INNER JOIN candidate_turns AS candidate
                    ON candidate.assistant_turn_at_ms = message.assistant_turn_at_ms
                WHERE event.conv_id = ?
                  AND event.event_type IN (
                      'thinking_phase',
                      'assistant_image',
                      'loading_activity',
                      'processing_activity',
                      'wait_for_user_activity'
                  )
            )
            SELECT assistant_turn_at_ms, COUNT(*) AS activity_count
            FROM logical_activities
            WHERE activity_identity IS NOT NULL
            GROUP BY assistant_turn_at_ms
            """,
            (
                *batch,
                conv_id,
                conv_id,
            ),
        )
        for row in rows:
            assistant_turn_at_ms = require_non_negative_int(
                row.get("assistant_turn_at_ms"),
                error_message="Conversation assistant turn must be a non-negative integer.",
            )
            counts[assistant_turn_at_ms] = require_non_negative_int(
                row.get("activity_count"),
                error_message="Conversation logical activity count must be a non-negative integer.",
            )
    return counts

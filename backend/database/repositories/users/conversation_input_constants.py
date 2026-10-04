"""SoAI - Conversation input repository constants [backend/database/repositories/users/conversation_input_constants.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.validation.epoch import EPOCH_MS_MIN

__all__ = (
    "ACTIVE_INPUT_STATES",
    "CONVERSATION_INPUT_ACTIVE_ORDER_SQL",
    "CONVERSATION_INPUT_DISPATCH_RANK_SQL",
    "CONVERSATION_INPUT_PRECEDES_SQL",
    "CONVERSATION_INPUT_RUNNING_ROOT_AVAILABLE_SQL",
    "CONVERSATION_REGENERATION_HAS_REPLACEMENT_SQL",
    "CONVERSATION_REGENERATION_SOURCE_EXISTS_SQL",
    "CONVERSATION_REGENERATION_SOURCE_FOLLOWED_SQL",
    "CONVERSATION_REGENERATION_SUPERSEDED_SQL",
    "EPOCH_MS_MIN",
    "TERMINAL_INPUT_STATES",
    "VALID_INPUT_STATES",
    "conversation_regeneration_retryable_sql",
)

CONVERSATION_INPUT_DISPATCH_RANK_SQL = """
CASE
    WHEN json_extract(source_metadata_json, '$.dispatch_mode') = 'forced_after_interrupt'
    THEN 0
    ELSE 1
END
"""

CONVERSATION_INPUT_ACTIVE_ORDER_SQL = """
CASE WHEN state IN ('materializing', 'running', 'input_required') THEN 0 ELSE 1 END ASC,
dispatch_rank ASC, accepted_at_ms ASC, id ASC
"""

CONVERSATION_INPUT_PRECEDES_SQL = """
earlier.dispatch_rank < input.dispatch_rank
OR (
    earlier.dispatch_rank = input.dispatch_rank
    AND (
        earlier.accepted_at_ms < input.accepted_at_ms
        OR (
            earlier.accepted_at_ms = input.accepted_at_ms
            AND earlier.id < input.id
        )
    )
)
"""

CONVERSATION_INPUT_RUNNING_ROOT_AVAILABLE_SQL = """
NOT EXISTS (
    SELECT 1 FROM webui_agent_turns AS root_turn
    WHERE root_turn.conv_id = input.conv_id
      AND root_turn.user_id = input.user_id
      AND root_turn.turn_scope = 'root'
      AND root_turn.status = 'running'
      AND (input.agent_turn_id IS NULL OR root_turn.turn_id != input.agent_turn_id)
)
"""

CONVERSATION_REGENERATION_HAS_REPLACEMENT_SQL = """
EXISTS (
    SELECT 1 FROM webui_messages AS replacement
    WHERE replacement.conv_id = input.conv_id
      AND replacement.role = 'assistant'
      AND (
          replacement.request_id = input.request_id
          OR replacement.request_id GLOB input.request_id || ':variant:[0-9]*'
      )
)
"""

CONVERSATION_REGENERATION_SUPERSEDED_SQL = """
EXISTS (
    SELECT 1 FROM webui_conversation_inputs AS later_attempt
    WHERE later_attempt.conv_id = input.conv_id
      AND later_attempt.regeneration_request_json IS NOT NULL
      AND later_attempt.materialized_message_id = input.materialized_message_id
      AND later_attempt.id > input.id
)
"""

CONVERSATION_REGENERATION_SOURCE_EXISTS_SQL = """
EXISTS (
    SELECT 1 FROM webui_messages AS source
    WHERE source.conv_id = input.conv_id
      AND source.id = input.materialized_message_id
      AND source.role = 'user'
)
"""

CONVERSATION_REGENERATION_SOURCE_FOLLOWED_SQL = """
EXISTS (
    SELECT 1 FROM webui_messages AS source
    JOIN webui_messages AS later_message
      ON later_message.conv_id = source.conv_id
     AND (
         later_message.created_at_ms > source.created_at_ms
         OR (
             later_message.created_at_ms = source.created_at_ms
             AND later_message.id > source.id
         )
     )
    WHERE source.conv_id = input.conv_id
      AND source.id = input.materialized_message_id
      AND source.role = 'user'
)
"""


def conversation_regeneration_retryable_sql() -> str:
    return f"""
(
    input.state IN ('failed', 'cancelled')
    AND input.request_id IS NOT NULL
    AND input.request_id != ''
    AND input.materialized_message_id IS NOT NULL
    AND NOT {CONVERSATION_REGENERATION_HAS_REPLACEMENT_SQL}
    AND NOT {CONVERSATION_REGENERATION_SUPERSEDED_SQL}
    AND {CONVERSATION_REGENERATION_SOURCE_EXISTS_SQL}
    AND NOT {CONVERSATION_REGENERATION_SOURCE_FOLLOWED_SQL}
)
"""


ACTIVE_INPUT_STATES: frozenset[str] = frozenset(
    {"pending", "materializing", "running", "input_required"},
)
TERMINAL_INPUT_STATES: frozenset[str] = frozenset(
    {"completed", "failed", "cancelled", "effect_unknown"},
)
VALID_INPUT_STATES: frozenset[str] = frozenset(
    {
        "pending",
        "materializing",
        "running",
        "input_required",
        "completed",
        "failed",
        "cancelled",
        "effect_unknown",
    },
)

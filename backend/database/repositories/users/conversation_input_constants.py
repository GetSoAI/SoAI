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
    "EPOCH_MS_MIN",
    "TERMINAL_INPUT_STATES",
    "VALID_INPUT_STATES",
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

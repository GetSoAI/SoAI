"""SoAI - Conversation input repository constants [backend/database/repositories/users/conversation_input_constants.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.validation.epoch import EPOCH_MS_MIN

__all__ = (
    "ACTIVE_INPUT_STATES",
    "CONVERSATION_INPUT_ACTIVE_ORDER_SQL",
    "CONVERSATION_INPUT_DISPATCH_RANK_SQL",
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

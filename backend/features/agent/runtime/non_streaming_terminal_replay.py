"""SoAI - Non-streaming terminal replay handling [backend/features/agent/runtime/non_streaming_terminal_replay.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.agent.status_values import (
    AGENT_TURN_STATUS_CANCELLED,
    AGENT_TURN_STATUS_COMPLETED,
    AGENT_TURN_STATUS_ERROR,
)
from core.errors.exceptions import ConflictError
from features.agent.runtime.persisted_terminal_turn_replay import (
    PersistedTerminalTurnReplay,
)

__all__ = ("raise_for_non_streaming_terminal_replay",)


def raise_for_non_streaming_terminal_replay(
    replay: PersistedTerminalTurnReplay,
) -> None:
    if replay.status == AGENT_TURN_STATUS_COMPLETED:
        raise ConflictError("Agent turn already finalized.")
    if replay.status == AGENT_TURN_STATUS_CANCELLED:
        raise ConflictError(replay.error_message or "Agent turn cancelled.")
    if replay.status == AGENT_TURN_STATUS_ERROR:
        raise ConflictError(replay.error_message or "Agent turn failed.")
    raise ConflictError(replay.error_message or "Agent turn already finalized.")

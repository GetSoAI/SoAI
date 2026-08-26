"""SoAI - Agent turn iteration cancellation identifiers [backend/features/agent/runtime/turn_iteration_cancellation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.runtime.cancellation_ids import build_agent_iteration_cancellation_id

if TYPE_CHECKING:
    from core.agent.settings_types import AgentSettings
    from core.agent.turn_state_writer import TurnStateWriter
    from features.agent.runtime.turn_engine import TurnPrimitives

__all__ = ("resolve_iteration_cancellation_id",)


def resolve_iteration_cancellation_id(
    *,
    turn_state_writer: TurnStateWriter,
    iteration_index: int,
    primitives: TurnPrimitives,
    settings: AgentSettings,
) -> str:
    pending = turn_state_writer.resolve_pending_inference_cancellation_id(
        iteration_index=iteration_index,
    )
    if pending is not None:
        return pending
    return build_agent_iteration_cancellation_id(
        turn_cancellation_id=primitives.turn_cancellation_id,
        iteration_index=iteration_index,
        mode=settings.mode,
    )

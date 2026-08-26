"""SoAI - Agent turn loop inference start transition [backend/features/agent/runtime/turn_loop_inference_start.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.agent.runtime.turn_iteration_cancellation import (
    resolve_iteration_cancellation_id,
)

if TYPE_CHECKING:
    from core.agent.settings_types import AgentSettings
    from core.agent.turn_state_writer import TurnStateWriter
    from core.types.json import JSONDict
    from features.agent.runtime.turn_engine import TurnPrimitives
    from features.agent.runtime.turn_iteration_policy_types import AgentOutputPublicationMode
    from features.agent.runtime.turn_loop_models import (
        TurnLoopInferenceResult,
        TurnLoopRunInferenceCallback,
    )

__all__ = ("start_turn_loop_inference",)


async def start_turn_loop_inference(
    *,
    turn_state_writer: TurnStateWriter,
    iteration_index: int,
    primitives: TurnPrimitives,
    settings: AgentSettings,
    message_history: list[JSONDict],
    suppress_tools_for_next_inference: bool,
    output_publication_mode: AgentOutputPublicationMode,
    run_inference: TurnLoopRunInferenceCallback,
) -> tuple[str, TurnLoopInferenceResult]:
    cancellation_id = resolve_iteration_cancellation_id(
        turn_state_writer=turn_state_writer,
        iteration_index=iteration_index,
        primitives=primitives,
        settings=settings,
    )
    await turn_state_writer.inference_started(
        iteration_index=iteration_index,
        cancellation_id=cancellation_id,
    )
    inference = await run_inference(
        iteration_index,
        cancellation_id,
        message_history,
        suppress_tools_for_next_inference,
        output_publication_mode,
    )
    return cancellation_id, inference

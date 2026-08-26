"""SoAI - Running agent turn state persistence [backend/features/agent/runtime/turn_state_running_persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.turn_state_record_rewrites import (
    build_running_turn_state_request_from_record,
)
from core.database.requests import ClaimAgentTurnStateRequest
from core.validation.strings import coerce_optional_trimmed_str
from features.agent.runtime.turn_state_invariants import (
    normalize_active_inference_cancellation_id,
)

if TYPE_CHECKING:
    from core.conversations.protocols_database_agents import DatabaseAgentTurnsProtocol
    from core.database.requests import ClaimAgentTurnAbandonRequest
    from core.types.json import JSONDict

__all__ = (
    "build_running_turn_state_request_from_record",
    "claim_stale_running_turns",
    "normalize_active_inference_cancellation_id",
    "persist_active_inference_cancellation_id",
    "read_active_inference_cancellation_id",
)


def read_active_inference_cancellation_id(record: JSONDict) -> str | None:
    return coerce_optional_trimmed_str(record.get("active_inference_cancellation_id"))


async def claim_stale_running_turns(
    database_agent_turns: DatabaseAgentTurnsProtocol,
    *,
    record: JSONDict,
    execution_token: str,
    expected_execution_token: str | None,
    active_inference_cancellation_id: str | None,
    stale_running_turns: tuple[ClaimAgentTurnAbandonRequest, ...],
) -> JSONDict:
    return await database_agent_turns.claim_turn_state(
        ClaimAgentTurnStateRequest(
            turn_state=build_running_turn_state_request_from_record(
                record=record,
                execution_token=execution_token,
                expected_execution_token=expected_execution_token,
                active_inference_cancellation_id=active_inference_cancellation_id,
            ),
            stale_running_turns=stale_running_turns,
        ),
    )


async def persist_active_inference_cancellation_id(
    database_agent_turns: DatabaseAgentTurnsProtocol,
    *,
    record: JSONDict,
    execution_token: str,
    expected_execution_token: str | None,
    active_inference_cancellation_id: str | None,
    stale_running_turns: tuple[ClaimAgentTurnAbandonRequest, ...],
) -> JSONDict:
    if stale_running_turns:
        return await claim_stale_running_turns(
            database_agent_turns,
            record=record,
            execution_token=execution_token,
            expected_execution_token=expected_execution_token,
            active_inference_cancellation_id=active_inference_cancellation_id,
            stale_running_turns=stale_running_turns,
        )
    return await database_agent_turns.write_turn_state(
        build_running_turn_state_request_from_record(
            record=record,
            execution_token=execution_token,
            expected_execution_token=expected_execution_token,
            active_inference_cancellation_id=active_inference_cancellation_id,
        ),
    )

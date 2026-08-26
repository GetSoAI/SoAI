"""SoAI - Existing agent turn resume and reclaim logic [backend/features/agent/runtime/turn_state_resume.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.status_values import AGENT_TURN_STATUS_RUNNING
from core.agent.turn_record_fields import TurnStateHeader, read_turn_int
from core.agent.turn_state_record_rewrites import (
    build_running_turn_state_request_from_record,
)
from core.database.requests import ClaimAgentTurnStateRequest
from core.errors.exceptions import ConflictError, ValidationError
from core.runtime.boot_id import get_boot_id
from core.validation.coercion import coerce_int_from_scalar
from features.agent.runtime.stale_turn_reconciliation import (
    persist_stale_turn_terminal_outcome,
)
from features.agent.runtime.stale_turn_terminal_outcome import (
    resolve_stale_turn_terminal_outcome,
)
from features.agent.runtime.turn_engine import create_turn_execution_token
from features.agent.runtime.turn_liveness import turn_record_is_live
from features.agent.runtime.turn_state_reconciliation import (
    collect_stale_running_turn_claims,
)
from features.agent.runtime.turn_state_running_persistence import (
    claim_stale_running_turns,
    persist_active_inference_cancellation_id,
    read_active_inference_cancellation_id,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.agent.runtime.turn_engine import AgentTurnEngineDependencies

__all__ = ("resume_existing_turn_state",)


def _assert_existing_turn_matches_inputs(
    *,
    record: JSONDict,
    header: TurnStateHeader,
    mode: str,
    max_iterations: int,
) -> None:
    persisted_turn_scope = str(record.get("turn_scope") or "").strip()
    if persisted_turn_scope and persisted_turn_scope != header.turn_scope:
        raise ConflictError("Agent turn scope does not match persisted turn state.")
    if str(record.get("parent_turn_id") or "") != str(header.parent_turn_id or ""):
        raise ConflictError("Agent turn parent_turn_id does not match persisted turn state.")
    if str(record.get("parent_tool_call_id") or "") != str(header.parent_tool_call_id or ""):
        raise ConflictError("Agent turn parent_tool_call_id does not match persisted turn state.")
    persisted_parent_iteration_index = coerce_int_from_scalar(record.get("parent_iteration_index"))
    if persisted_parent_iteration_index != header.parent_iteration_index:
        raise ConflictError(
            "Agent turn parent_iteration_index does not match persisted turn state.",
        )
    if str(record.get("display_name") or "") != str(header.display_name or ""):
        raise ConflictError("Agent turn display_name does not match persisted turn state.")
    if str(record.get("requested_model") or "") != str(header.requested_model or ""):
        raise ConflictError("Agent turn requested_model does not match persisted turn state.")
    if str(record.get("owner_task_id") or "") != str(header.owner_task_id or ""):
        raise ConflictError("Agent turn owner_task_id does not match persisted turn state.")
    persisted_mode = str(record.get("mode") or "")
    if persisted_mode and persisted_mode != mode:
        raise ConflictError("Agent turn mode does not match persisted turn state.")
    persisted_max_iterations = coerce_int_from_scalar(record.get("max_iterations"))
    if persisted_max_iterations is not None and persisted_max_iterations != max_iterations:
        raise ConflictError("Agent turn max_iterations does not match persisted turn state.")


async def _raise_if_finalized_after_restart(
    *,
    deps: AgentTurnEngineDependencies,
    record: JSONDict,
    persisted_boot_id: str,
) -> None:
    if persisted_boot_id == get_boot_id():
        return
    message = "Agent turn finalized after server restart. Start a new turn."
    tool_calls = await deps.database_tool_calls.get_tool_calls_for_turn(
        str(record.get("conv_id") or ""),
        str(record.get("turn_id") or ""),
    )
    outcome = resolve_stale_turn_terminal_outcome(record=record, tool_calls=tool_calls)
    try:
        await persist_stale_turn_terminal_outcome(
            database_agent_turns=deps.database_agent_turns,
            database_tool_calls=deps.database_tool_calls,
            record=record,
            tool_calls=tool_calls,
            outcome=outcome,
            completed_at_ms=max(
                0,
                read_turn_int(record, "finished_at_ms")
                or read_turn_int(record, "updated_at_ms")
                or 0,
            ),
            logger=deps.logger,
            task_registry=deps.task_registry,
        )
    except ValidationError as exception:
        raise ConflictError(message) from exception
    raise ConflictError(message)


async def _resume_same_execution_token_turn(
    *,
    deps: AgentTurnEngineDependencies,
    record: JSONDict,
    conv_id: str,
    user_id: int,
    turn_id: str,
    turn_scope: str,
    persisted_execution_token: str,
    active_inference_cancellation_id: str | None,
) -> JSONDict:
    stale_running_turns = await collect_stale_running_turn_claims(
        database_agent_turns=deps.database_agent_turns,
        database_tool_calls=deps.database_tool_calls,
        task_registry_queries=deps.task_registry_queries,
        token_collection=deps.token_collection,
        conv_id=conv_id,
        user_id=user_id,
        turn_scope=turn_scope,
        exclude_turn_id=turn_id,
    )
    try:
        if read_active_inference_cancellation_id(record) != active_inference_cancellation_id:
            return await persist_active_inference_cancellation_id(
                deps.database_agent_turns,
                record=record,
                execution_token=persisted_execution_token,
                expected_execution_token=persisted_execution_token,
                active_inference_cancellation_id=active_inference_cancellation_id,
                stale_running_turns=stale_running_turns,
            )
        if stale_running_turns:
            return await claim_stale_running_turns(
                deps.database_agent_turns,
                record=record,
                execution_token=persisted_execution_token,
                expected_execution_token=persisted_execution_token,
                active_inference_cancellation_id=active_inference_cancellation_id,
                stale_running_turns=stale_running_turns,
            )
        return record
    except ValidationError as exception:
        raise ConflictError(str(exception) or "Agent turn already running.") from exception


async def _reclaim_stale_existing_turn(
    *,
    deps: AgentTurnEngineDependencies,
    record: JSONDict,
    conv_id: str,
    user_id: int,
    turn_id: str,
    turn_scope: str,
    persisted_execution_token: str,
    active_inference_cancellation_id: str | None,
) -> JSONDict:
    stale_running_turns = await collect_stale_running_turn_claims(
        database_agent_turns=deps.database_agent_turns,
        database_tool_calls=deps.database_tool_calls,
        task_registry_queries=deps.task_registry_queries,
        token_collection=deps.token_collection,
        conv_id=conv_id,
        user_id=user_id,
        turn_scope=turn_scope,
        exclude_turn_id=turn_id,
    )
    try:
        return await deps.database_agent_turns.claim_turn_state(
            ClaimAgentTurnStateRequest(
                turn_state=build_running_turn_state_request_from_record(
                    record=record,
                    execution_token=create_turn_execution_token(),
                    expected_execution_token=persisted_execution_token,
                    active_inference_cancellation_id=active_inference_cancellation_id,
                ),
                stale_running_turns=stale_running_turns,
            ),
        )
    except ValidationError as exception:
        raise ConflictError(str(exception) or "Agent turn already running.") from exception


async def resume_existing_turn_state(
    deps: AgentTurnEngineDependencies,
    *,
    conv_id: str,
    user_id: int,
    turn_id: str,
    mode: str,
    max_iterations: int,
    active_inference_cancellation_id: str | None,
    existing_execution_token: str | None,
    header: TurnStateHeader,
) -> JSONDict | None:
    existing_turn = await deps.database_agent_turns.get_turn(
        conv_id=conv_id,
        user_id=user_id,
        turn_id=turn_id,
    )
    if existing_turn is None:
        return None
    if str(existing_turn.get("status") or "") != AGENT_TURN_STATUS_RUNNING:
        raise ConflictError("Agent turn already finalized.")
    _assert_existing_turn_matches_inputs(
        record=existing_turn,
        header=header,
        mode=mode,
        max_iterations=max_iterations,
    )
    persisted_execution_token = str(existing_turn.get("execution_token") or "").strip()
    persisted_boot_id = str(existing_turn.get("server_boot_id") or "").strip()
    if (
        isinstance(existing_execution_token, str)
        and existing_execution_token.strip()
        and persisted_execution_token == existing_execution_token.strip()
    ):
        await _raise_if_finalized_after_restart(
            deps=deps,
            record=existing_turn,
            persisted_boot_id=persisted_boot_id,
        )
        return await _resume_same_execution_token_turn(
            deps=deps,
            record=existing_turn,
            conv_id=conv_id,
            user_id=user_id,
            turn_id=turn_id,
            turn_scope=header.turn_scope,
            persisted_execution_token=persisted_execution_token,
            active_inference_cancellation_id=active_inference_cancellation_id,
        )
    is_live = await turn_record_is_live(
        task_registry_queries=deps.task_registry_queries,
        token_collection=deps.token_collection,
        record=existing_turn,
    )
    if is_live:
        raise ConflictError("Agent turn already running.")
    await _raise_if_finalized_after_restart(
        deps=deps,
        record=existing_turn,
        persisted_boot_id=persisted_boot_id,
    )
    return await _reclaim_stale_existing_turn(
        deps=deps,
        record=existing_turn,
        conv_id=conv_id,
        user_id=user_id,
        turn_id=turn_id,
        turn_scope=header.turn_scope,
        persisted_execution_token=persisted_execution_token,
        active_inference_cancellation_id=active_inference_cancellation_id,
    )

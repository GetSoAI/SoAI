"""SoAI - Agent turn existing-row validation [backend/database/repositories/users/agent_turn_existing_row_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.status_values import (
    AGENT_TURN_STATUS_RUNNING,
    AGENT_TURN_TERMINAL_STATUSES,
)
from core.agent.turn_write_conflicts import (
    TURN_WRITE_ALREADY_FINALIZED_MESSAGE,
    AgentTurnFinalizedWriteConflictError,
)
from core.database.requests import WriteAgentTurnStateRequest
from core.errors.exceptions import ValidationError
from database.repositories.users.agent_turn_persisted_snapshot import (
    PersistedTurnSnapshot,
    read_persisted_turn_snapshot,
    validate_lineage_matches,
    validate_monotonic_progress,
    validate_terminal_replay_matches,
)

if TYPE_CHECKING:
    from database.core.sqlite_values import SQLiteRow

__all__ = (
    "validate_turn_claim_against_existing_row",
    "validate_turn_write_against_existing_row",
)


def validate_turn_write_against_existing_row(
    existing_row: SQLiteRow,
    request: WriteAgentTurnStateRequest,
) -> None:
    persisted = read_persisted_turn_snapshot(existing_row)
    _validate_turn_identity(
        persisted,
        request,
        allow_execution_token_rotation=False,
    )
    validate_monotonic_progress(persisted.progress, request)
    _validate_terminal_turn_replay(persisted, request)


def validate_turn_claim_against_existing_row(
    existing_row: SQLiteRow,
    request: WriteAgentTurnStateRequest,
) -> None:
    persisted = read_persisted_turn_snapshot(existing_row)
    _validate_turn_identity(
        persisted,
        request,
        allow_execution_token_rotation=True,
    )
    validate_monotonic_progress(persisted.progress, request)
    if persisted.status in AGENT_TURN_TERMINAL_STATUSES:
        raise AgentTurnFinalizedWriteConflictError(TURN_WRITE_ALREADY_FINALIZED_MESSAGE)
    if request.status != AGENT_TURN_STATUS_RUNNING:
        raise ValidationError("Agent turn claim state must remain running.")


def _validate_turn_identity(
    persisted: PersistedTurnSnapshot,
    request: WriteAgentTurnStateRequest,
    *,
    allow_execution_token_rotation: bool,
) -> None:
    expected_execution_token = (
        request.expected_execution_token.strip()
        if isinstance(request.expected_execution_token, str)
        else ""
    )
    if expected_execution_token and persisted.execution_token != expected_execution_token:
        raise ValidationError("Agent turn execution token is stale.")
    if not allow_execution_token_rotation and persisted.execution_token != request.execution_token:
        raise ValidationError("Agent turn execution token is stale.")
    if allow_execution_token_rotation:
        if not expected_execution_token and persisted.execution_token != request.execution_token:
            raise ValidationError("Agent turn already running.")
    validate_lineage_matches(persisted.lineage, request, message_prefix="Agent turn ")


def _validate_terminal_turn_replay(
    persisted: PersistedTurnSnapshot,
    request: WriteAgentTurnStateRequest,
) -> None:
    if persisted.status not in AGENT_TURN_TERMINAL_STATUSES:
        return
    if request.status == AGENT_TURN_STATUS_RUNNING:
        raise AgentTurnFinalizedWriteConflictError(TURN_WRITE_ALREADY_FINALIZED_MESSAGE)
    if request.status != persisted.status:
        raise AgentTurnFinalizedWriteConflictError(
            "Agent turn terminal state does not match persisted final state."
        )
    try:
        validate_terminal_replay_matches(persisted, request)
    except ValidationError as exception:
        raise AgentTurnFinalizedWriteConflictError(
            str(exception),
            cause=exception,
        ) from exception

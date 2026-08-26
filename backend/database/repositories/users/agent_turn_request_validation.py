"""SoAI - Agent turn request validation [backend/database/repositories/users/agent_turn_request_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.agent.status_values import (
    AGENT_TURN_ALL_STATUSES,
    AGENT_TURN_STATUS_MAX_ITERATIONS,
    AGENT_TURN_STATUS_RUNNING,
    AGENT_TURN_TERMINAL_STATUSES,
)
from core.agent.turn_scope_values import (
    TURN_SCOPE_ALL,
    TURN_SCOPE_ROOT,
    TURN_SCOPE_SUBAGENT,
)
from core.database.requests import WriteAgentTurnStateRequest
from core.errors.exceptions import ValidationError
from core.users.user_id import is_strict_user_id
from database.repositories.users.agent_turn_text_normalization import (
    normalize_agent_turn_optional_text,
)

__all__ = ("validate_turn_state_request",)


def validate_turn_state_request(request: WriteAgentTurnStateRequest) -> None:
    conv_id = request.conv_id.strip() if isinstance(request.conv_id, str) else ""
    turn_id = request.turn_id.strip() if isinstance(request.turn_id, str) else ""
    execution_token = (
        request.execution_token.strip() if isinstance(request.execution_token, str) else ""
    )
    server_boot_id = (
        request.server_boot_id.strip() if isinstance(request.server_boot_id, str) else ""
    )
    status = request.status.strip() if isinstance(request.status, str) else ""
    mode = request.mode.strip() if isinstance(request.mode, str) else ""
    if not conv_id:
        raise ValidationError("Agent turn conv_id is required.")
    if not is_strict_user_id(request.user_id):
        raise ValidationError("Agent turn user_id is invalid.")
    if not turn_id:
        raise ValidationError("Agent turn turn_id is required.")
    turn_scope = request.turn_scope.strip() if isinstance(request.turn_scope, str) else ""
    if turn_scope not in TURN_SCOPE_ALL:
        raise ValidationError("Agent turn turn_scope is invalid.")
    if not execution_token:
        raise ValidationError("Agent turn execution_token is required.")
    if not server_boot_id:
        raise ValidationError("Agent turn server_boot_id is required.")
    expected_execution_token = (
        request.expected_execution_token.strip()
        if isinstance(request.expected_execution_token, str)
        else ""
    )
    if request.expected_execution_token is not None and not expected_execution_token:
        raise ValidationError("Agent turn expected_execution_token is invalid.")
    if not status:
        raise ValidationError("Agent turn status is required.")
    if status not in AGENT_TURN_ALL_STATUSES:
        raise ValidationError("Agent turn status is invalid.")
    if not mode:
        raise ValidationError("Agent turn mode is required.")
    if int(request.max_iterations) <= 0:
        raise ValidationError("Agent turn max_iterations is invalid.")
    if int(request.iteration_index) < 0:
        raise ValidationError("Agent turn iteration_index is invalid.")
    if int(request.sequence) < 0:
        raise ValidationError("Agent turn sequence is invalid.")
    if int(request.todo_revision) < 0:
        raise ValidationError("Agent turn todo_revision is invalid.")
    if int(request.started_at_ms) < 0 or int(request.updated_at_ms) < 0:
        raise ValidationError("Agent turn timestamps are invalid.")
    if request.finished_at_ms is not None and int(request.finished_at_ms) < 0:
        raise ValidationError("Agent turn finished_at_ms is invalid.")
    if status == AGENT_TURN_STATUS_RUNNING and request.finished_at_ms is not None:
        raise ValidationError("Running agent turns cannot have finished_at_ms.")
    if status in AGENT_TURN_TERMINAL_STATUSES and request.finished_at_ms is None:
        raise ValidationError("Terminal agent turns require finished_at_ms.")
    if bool(request.reached_max_iterations):
        if status != AGENT_TURN_STATUS_MAX_ITERATIONS:
            raise ValidationError("reached_max_iterations requires max_iterations status.")
    elif status == AGENT_TURN_STATUS_MAX_ITERATIONS:
        raise ValidationError("max_iterations status requires reached_max_iterations.")
    parent_turn_id = normalize_agent_turn_optional_text(request.parent_turn_id)
    parent_tool_call_id = normalize_agent_turn_optional_text(request.parent_tool_call_id)
    if turn_scope == TURN_SCOPE_ROOT:
        if (
            parent_turn_id is not None
            or parent_tool_call_id is not None
            or request.parent_iteration_index is not None
        ):
            raise ValidationError("Root agent turns cannot include subagent lineage fields.")
    if turn_scope == TURN_SCOPE_SUBAGENT:
        if parent_turn_id is None or parent_tool_call_id is None:
            raise ValidationError("Subagent turns require parent lineage fields.")
        if request.parent_iteration_index is None or int(request.parent_iteration_index) < 0:
            raise ValidationError("Subagent turns require parent_iteration_index.")
        if normalize_agent_turn_optional_text(request.owner_task_id) is None:
            raise ValidationError("Subagent turns require owner_task_id.")

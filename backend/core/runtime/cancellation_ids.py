"""SoAI - Canonical cancellation identifier builders [backend/core/runtime/cancellation_ids.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.agent_mode import is_agent_mode
from core.errors.exceptions import ValidationError
from core.runtime.soai_identifiers import extend_soai_id
from core.tasks.cancellation_ids import normalize_cancellation_id

__all__ = (
    "build_agent_iteration_cancellation_id",
    "build_agent_turn_cancellation_id",
    "build_automation_turn_cancellation_id",
    "build_chat_stream_task_cancellation_id",
    "build_subagent_base_cancellation_id",
)


def build_chat_stream_task_cancellation_id(*, context_cancellation_id: str, request_id: str) -> str:
    normalized_cancellation_id = normalize_cancellation_id(context_cancellation_id)
    if not normalized_cancellation_id:
        raise ValidationError("Chat stream requires a non-empty context cancellation_id.")
    normalized_request_id = str(request_id or "").strip()
    if not normalized_request_id:
        raise ValidationError("Chat stream requires a non-empty request_id.")
    return extend_soai_id(
        normalized_cancellation_id,
        ("webui", "chat_stream", normalized_request_id),
    )


def build_automation_turn_cancellation_id(
    *,
    context_cancellation_id: str,
    run_id: str,
    turn_index: int,
) -> str:
    normalized_cancellation_id = normalize_cancellation_id(context_cancellation_id)
    if not normalized_cancellation_id:
        raise ValidationError("Automation turn requires a non-empty context cancellation_id.")
    normalized_run_id = str(run_id or "").strip()
    if not normalized_run_id:
        raise ValidationError("Automation turn requires a non-empty run_id.")
    try:
        normalized_turn_index = int(turn_index)
    except (TypeError, ValueError) as exception:
        raise ValidationError("Automation turn_index must be an integer.") from exception
    if normalized_turn_index < 0:
        raise ValidationError("Automation turn_index must be non-negative.")
    return extend_soai_id(
        normalized_cancellation_id,
        ("webui", "automation", "run", normalized_run_id, "turn", str(normalized_turn_index)),
    )


def build_agent_turn_cancellation_id(*, base_cancellation_id: str, turn_id: str, mode: str) -> str:
    if not is_agent_mode(mode):
        return base_cancellation_id
    normalized_base = normalize_cancellation_id(base_cancellation_id)
    if not normalized_base:
        raise ValidationError("Agent turn cancellation id requires a base cancellation id.")
    normalized_turn_id = str(turn_id or "").strip()
    if not normalized_turn_id:
        raise ValidationError("Agent turn cancellation id requires a non-empty turn id.")
    return extend_soai_id(normalized_base, ("agent", "turn", normalized_turn_id))


def build_agent_iteration_cancellation_id(
    *,
    turn_cancellation_id: str,
    iteration_index: int,
    mode: str,
) -> str:
    if not is_agent_mode(mode):
        return turn_cancellation_id
    normalized_turn = normalize_cancellation_id(turn_cancellation_id)
    if not normalized_turn:
        raise ValidationError("Agent iteration cancellation id requires a turn cancellation id.")
    normalized_iteration_index = int(iteration_index)
    if normalized_iteration_index < 0:
        raise ValidationError("Agent iteration index must be non-negative.")
    return extend_soai_id(normalized_turn, ("iteration", str(normalized_iteration_index)))


def build_subagent_base_cancellation_id(*, parent_cancellation_id: str, subagent_id: str) -> str:
    normalized_parent = normalize_cancellation_id(parent_cancellation_id)
    if not normalized_parent:
        raise ValidationError("Subagent cancellation id requires a parent cancellation id.")
    normalized_subagent_id = str(subagent_id or "").strip()
    if not normalized_subagent_id:
        raise ValidationError("Subagent cancellation id requires a subagent_id.")
    return extend_soai_id(normalized_parent, ("agent", "subagent", normalized_subagent_id))

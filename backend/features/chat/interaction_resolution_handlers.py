"""SoAI - Non-secret interaction resolution handlers [backend/features/chat/interaction_resolution_handlers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.elicitation_ask_user_answers import normalize_ask_user_answers
from core.elicitation_interactions import resolve_cancelled_interaction_result
from core.errors.exceptions import ValidationError
from core.tasks.enums import TaskStatus
from core.tasks.interaction_mutations import ConversationInteractionMutation
from core.tool_approval.permission_key import require_tool_approval_remember_allowed
from core.tool_approval.task_metadata import require_tool_approval_tool_key
from features.chat.interaction_resolution_support import (
    build_interaction_resolution_response,
    finalize_interaction_resolution,
)

if TYPE_CHECKING:
    from core.tasks.protocols_registry import TaskRegistryProtocol
    from core.tasks.task import Task
    from core.types.json import JSONDict

__all__ = (
    "resolve_ask_user_interaction",
    "resolve_cancelled_interaction",
    "resolve_tool_approval_interaction",
)

OPERATION_ASK_USER_FINALIZE = "features.chat.interaction_service.ask_user_finalize"
OPERATION_CANCEL_FINALIZE = "features.chat.interaction_service.cancel_finalize"
OPERATION_TOOL_APPROVAL_FINALIZE = "features.chat.interaction_service.tool_approval_finalize"


async def resolve_cancelled_interaction(
    task_registry: TaskRegistryProtocol,
    task: Task,
    *,
    conv_id: str,
    interaction_type: str,
    checkpoint_generation: int | None,
) -> JSONDict:
    result = resolve_cancelled_interaction_result(interaction_type)
    resolved = await finalize_interaction_resolution(
        task_registry=task_registry,
        task_id=task.task_id,
        status=TaskStatus.CANCELLED,
        result=result,
        status_message="User cancelled",
        operation=OPERATION_CANCEL_FINALIZE,
        conv_id=conv_id,
        interaction_mutation=ConversationInteractionMutation(
            checkpoint_generation=checkpoint_generation,
        ),
    )
    return build_interaction_resolution_response(
        task_id=resolved.task_id,
        status=resolved.status.value,
    )


async def resolve_ask_user_interaction(
    task_registry: TaskRegistryProtocol,
    task: Task,
    *,
    conv_id: str,
    answers_value: JSONDict,
    checkpoint_generation: int | None,
) -> JSONDict:
    try:
        result = normalize_ask_user_answers(task, answers_value)
    except ValidationError as exception:
        raise ValidationError(str(exception)) from exception
    resolved = await finalize_interaction_resolution(
        task_registry=task_registry,
        task_id=task.task_id,
        status=TaskStatus.COMPLETED,
        result=result,
        status_message="User submitted",
        operation=OPERATION_ASK_USER_FINALIZE,
        conv_id=conv_id,
        interaction_mutation=ConversationInteractionMutation(
            checkpoint_generation=checkpoint_generation,
        ),
    )
    return build_interaction_resolution_response(
        task_id=resolved.task_id,
        status=resolved.status.value,
    )


async def resolve_tool_approval_interaction(
    task_registry: TaskRegistryProtocol,
    task: Task,
    *,
    conv_id: str,
    action: str,
    payload: JSONDict,
    checkpoint_generation: int | None,
) -> JSONDict:
    if action not in {"approve", "deny"}:
        raise ValidationError("action must be approve, deny, or cancel.")
    approved = action == "approve"
    remember = payload.get("remember") is True
    tool_key: str | None = None
    if approved and remember:
        metadata = dict(task.metadata)
        try:
            resolved_tool_key = require_tool_approval_tool_key(metadata)
            require_tool_approval_remember_allowed(tool_key=resolved_tool_key)
        except ValidationError as exception:
            raise ValidationError(str(exception)) from exception
        tool_key = resolved_tool_key
    resolved = await finalize_interaction_resolution(
        task_registry=task_registry,
        task_id=task.task_id,
        status=TaskStatus.COMPLETED,
        result={"approved": bool(approved), "remember": bool(remember)},
        status_message="User approved" if approved else "User denied",
        operation=OPERATION_TOOL_APPROVAL_FINALIZE,
        conv_id=conv_id,
        interaction_mutation=ConversationInteractionMutation(
            checkpoint_generation=checkpoint_generation,
            remembered_tool_permission=tool_key,
        ),
    )
    return build_interaction_resolution_response(
        task_id=resolved.task_id,
        status=resolved.status.value,
    )

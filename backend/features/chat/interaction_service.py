"""SoAI - Shared conversation interaction service [backend/features/chat/interaction_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.elicitation_ask_user import ASK_USER_INTERACTION_TYPE
from core.elicitation_vault_secret_request import CREDENTIAL_REQUEST_INTERACTION_TYPE
from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.tasks.enums import TaskStatus
from core.tasks.interaction_mutations import ConversationInteractionMutation
from core.timing.epoch import epoch_ms
from core.tool_approval.constants import TOOL_APPROVAL_INTERACTION_TYPE
from core.validation.strings import coerce_optional_trimmed_str
from features.chat.interaction_resolution_handlers import (
    resolve_ask_user_interaction,
    resolve_cancelled_interaction,
    resolve_tool_approval_interaction,
)
from features.chat.interaction_resolution_support import (
    build_interaction_resolution_response,
    cleanup_interaction_notification,
    finalize_interaction_resolution,
    resolve_interaction_cleanup_operation,
)
from features.chat.interaction_resolution_vault_secret_request import (
    resolve_vault_secret_request_interaction,
)
from features.chat.interaction_task_validation import (
    require_conversation_interaction_task,
)
from features.chat.interaction_tasks import (
    require_conversation_access_and_list_pending_conversation_interactions,
)

if TYPE_CHECKING:
    from fastapi import Request

    from core.notifications.protocols_database import DatabaseNotificationsProtocol
    from core.tasks.protocols_registry import TaskRegistryProtocol
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext

__all__ = (
    "ASK_USER_INTERACTION_TYPE",
    "CREDENTIAL_REQUEST_INTERACTION_TYPE",
    "ConversationInteractionResolutionDependencies",
    "InteractionEnvelope",
    "get_pending_interaction",
    "resolve_interaction",
)

LOGGER_NAME = "SoAI.features.chat.interaction_service"
OPERATION_TIMEOUT_FINALIZE = "features.chat.interaction_service.timeout_finalize"
TIMEOUT_ERROR_MESSAGE = "Timed out waiting for user input."


@dataclass(frozen=True, slots=True)
class InteractionEnvelope:
    conv_id: str
    interaction: JSONDict | None


@dataclass(frozen=True, slots=True)
class ConversationInteractionResolutionDependencies:
    task_registry: TaskRegistryProtocol
    database_notifications: DatabaseNotificationsProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ConversationInteractionResolutionDependencies",
            task_registry=self.task_registry,
            database_notifications=self.database_notifications,
        )


async def get_pending_interaction(
    request: Request,
    api_context: ApiContext,
    *,
    conv_id: str,
    user_id: int,
    interaction_type: str,
) -> InteractionEnvelope:
    pending = await require_conversation_access_and_list_pending_conversation_interactions(
        request,
        api_context,
        conv_id=conv_id,
        user_id=user_id,
    )
    interaction: JSONDict | None = None
    for item in pending:
        if item.get("interaction_type") == interaction_type:
            interaction = item
            break
    return InteractionEnvelope(conv_id=conv_id, interaction=interaction)


async def resolve_interaction(
    dependencies: ConversationInteractionResolutionDependencies,
    *,
    conv_id: str,
    task_id: str,
    user_id: int,
    interaction_type: str,
    payload: JSONDict,
    checkpoint_generation: int | None = None,
) -> JSONDict:
    logger = get_logger(LOGGER_NAME)
    task = await require_conversation_interaction_task(
        dependencies.task_registry,
        conv_id=conv_id,
        user_id=user_id,
        task_id=task_id,
        interaction_type=interaction_type,
        allow_terminal=True,
    )
    action_value = payload.get("action")
    action = coerce_optional_trimmed_str(action_value) or ""
    response_payload: JSONDict
    if task.status.is_terminal():
        response_payload = build_interaction_resolution_response(
            task_id=task.task_id,
            status=task.status.value,
        )
    elif task.ttl_expires_at_ms is not None and task.ttl_expires_at_ms <= epoch_ms():
        resolved = await finalize_interaction_resolution(
            task_registry=dependencies.task_registry,
            task_id=task.task_id,
            status=TaskStatus.FAILED,
            result=None,
            status_message="Timed out",
            error_code=504,
            error_message=TIMEOUT_ERROR_MESSAGE,
            operation=OPERATION_TIMEOUT_FINALIZE,
            conv_id=conv_id,
            interaction_mutation=ConversationInteractionMutation(
                checkpoint_generation=checkpoint_generation,
            ),
        )
        response_payload = build_interaction_resolution_response(
            task_id=resolved.task_id,
            status=resolved.status.value,
        )
    elif action == "cancel":
        response_payload = await resolve_cancelled_interaction(
            dependencies.task_registry,
            task,
            conv_id=conv_id,
            interaction_type=interaction_type,
            checkpoint_generation=checkpoint_generation,
        )
    elif interaction_type == ASK_USER_INTERACTION_TYPE:
        answers_value = payload.get("answers")
        if not isinstance(answers_value, dict):
            raise ValidationError("answers is required.")
        response_payload = await resolve_ask_user_interaction(
            dependencies.task_registry,
            task,
            conv_id=conv_id,
            answers_value=answers_value,
            checkpoint_generation=checkpoint_generation,
        )
    elif interaction_type == CREDENTIAL_REQUEST_INTERACTION_TYPE:
        response_payload = await resolve_vault_secret_request_interaction(
            dependencies.task_registry,
            task,
            conv_id=conv_id,
            user_id=user_id,
            payload=payload,
            checkpoint_generation=checkpoint_generation,
        )
    elif interaction_type == TOOL_APPROVAL_INTERACTION_TYPE:
        response_payload = await resolve_tool_approval_interaction(
            dependencies.task_registry,
            task,
            conv_id=conv_id,
            action=action,
            payload=payload,
            checkpoint_generation=checkpoint_generation,
        )
    else:
        raise ValidationError("Unsupported interaction type.")
    await cleanup_interaction_notification(
        database_notifications=dependencies.database_notifications,
        logger=logger,
        operation=resolve_interaction_cleanup_operation(action=action),
        user_id=user_id,
        metadata=task.metadata,
        conv_id=conv_id,
        task_id=task.task_id,
        interaction_type=interaction_type,
    )
    return response_payload

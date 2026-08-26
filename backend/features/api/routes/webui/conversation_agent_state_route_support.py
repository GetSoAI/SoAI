"""SoAI - Shared WebUI agent state route support [backend/features/api/routes/webui/conversation_agent_state_route_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, NoReturn

from starlette.responses import JSONResponse

from core.agent.state_errors import (
    AgentStateManualEditConflictError,
    AgentStateManualEditUnavailableError,
    AgentStateRevisionConflictError,
)
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from features.api.runtime.conversation_access import require_conversation_access_context
from features.api.runtime.errors import (
    raise_conflict,
    raise_invalid_request,
    raise_server_error,
)
from features.api.runtime.request_payloads import (
    read_json_object_with_required_field_or_raise,
)

if TYPE_CHECKING:
    from fastapi import Request

    from core.agent.protocols import (
        AgentStateServiceProtocol,
        PersistedAgentStateProtocol,
    )
    from core.events.types_base import Event
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext
    from features.api.runtime.current_user import CurrentUser

__all__ = (
    "AGENT_STATE_MANUAL_EDIT_EXCEPTIONS",
    "publish_agent_state_event",
    "raise_manual_edit_error",
    "require_request_json_object",
    "resolve_agent_plan_edit_context",
    "resolve_agent_state_edit_context",
    "resolve_agent_state_service",
    "resolve_agent_todo_edit_context",
    "respond_with_persisted_agent_state",
)

LOGGER_NAME = "SoAI.features.api.conversation_agent_state_route_support"
AGENT_STATE_MANUAL_EDIT_EXCEPTIONS = (
    StateError,
    ValidationError,
    AgentStateManualEditConflictError,
    AgentStateRevisionConflictError,
    AgentStateManualEditUnavailableError,
)


def resolve_agent_state_service(api_context: ApiContext) -> AgentStateServiceProtocol:
    return api_context.dependencies.agent_state_service


async def resolve_agent_state_edit_context(
    request: Request,
    *,
    api_context: ApiContext,
    conv_id: str,
    current_user: CurrentUser,
    required_field: str,
) -> tuple[str, JSONDict, AgentStateServiceProtocol]:
    conversation_context = await require_conversation_access_context(
        request,
        api_context=api_context,
        conv_id=conv_id,
        user_id=current_user["id"],
    )
    body = await require_request_json_object(request, required_field=required_field)
    return (conversation_context.resolved_conv_id, body, resolve_agent_state_service(api_context))


async def resolve_agent_plan_edit_context(
    request: Request,
    api_context: ApiContext,
    conv_id: str,
    current_user: CurrentUser,
) -> tuple[str, JSONDict, AgentStateServiceProtocol]:
    return await resolve_agent_state_edit_context(
        request,
        api_context=api_context,
        conv_id=conv_id,
        current_user=current_user,
        required_field="markdown",
    )


async def resolve_agent_todo_edit_context(
    request: Request,
    api_context: ApiContext,
    conv_id: str,
    current_user: CurrentUser,
) -> tuple[str, JSONDict, AgentStateServiceProtocol]:
    return await resolve_agent_state_edit_context(
        request,
        api_context=api_context,
        conv_id=conv_id,
        current_user=current_user,
        required_field="todo",
    )


async def require_request_json_object(
    request: Request,
    *,
    required_field: str,
) -> JSONDict:
    return await read_json_object_with_required_field_or_raise(
        request,
        required_field=required_field,
        invalid_json_message="Request body must be valid JSON.",
        invalid_object_message="Request body must be a JSON object.",
        missing_field_message=f"{required_field} is required.",
    )


def raise_manual_edit_error(
    request: Request,
    exception: Exception,
    *,
    state_name: str,
) -> NoReturn:
    if isinstance(exception, StateError | ValidationError):
        raise_invalid_request(request, str(exception))
    if isinstance(exception, AgentStateManualEditConflictError):
        raise_conflict(
            request,
            f"{state_name} edits are unavailable while an agent turn is running.",
        )
    if isinstance(exception, AgentStateRevisionConflictError):
        raise_conflict(
            request,
            f"Unable to persist {state_name.lower()} update because an agent turn is now running or the revision is stale.",
        )
    if isinstance(exception, AgentStateManualEditUnavailableError):
        raise_server_error(request, f"{state_name} editing is temporarily unavailable.")
    raise exception


async def publish_agent_state_event(
    api_context: ApiContext,
    event: Event,
    *,
    operation: str,
) -> None:
    try:
        await api_context.dependencies.event_bus.publish(event)
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=operation)
        log_handled_exception(
            get_logger(LOGGER_NAME),
            coerced,
            message="Failed to publish agent state event (non-critical).",
            operation=operation,
            level="debug",
        )


async def respond_with_persisted_agent_state(
    api_context: ApiContext,
    persisted: PersistedAgentStateProtocol,
    *,
    operation: str,
) -> JSONResponse:
    await publish_agent_state_event(
        api_context,
        persisted.event,
        operation=operation,
    )
    return JSONResponse(content=persisted.payload)

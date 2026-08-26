"""SoAI - Shared agent runtime preparation [backend/features/agent/runtime/execution_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from core.agent.settings_types import AgentSettings
from core.agent.turn_scope_values import TURN_SCOPE_ROOT
from core.errors.exceptions import ConfigurationError, ValidationError
from core.logging.protocols import LoggerProtocol
from core.openai.request_fields import resolve_optional_model_name
from core.orchestrator.types import MCPToolContext
from core.runtime.protocols import ConnectionProtocol
from core.runtime.request_context import RequestContext
from core.runtime.request_context_agent_fields import apply_agent_runtime_context_fields
from features.agent.runtime.prepared_request_state import PreparedExecutionRequest
from features.agent.runtime.turn_engine import AgentTurnEngineDependencies
from features.agent.session.runtime_resolution import resolve_agent_runtime_settings
from features.api.runtime.errors import raise_invalid_request, raise_server_error

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "AgentRuntimePreparation",
    "build_agent_turn_engine_dependencies",
    "build_headless_agent_turn_engine_dependencies_from_api_dependencies",
    "prepare_agent_runtime",
    "resolve_agent_request_settings",
)


@dataclass(frozen=True, slots=True)
class AgentRuntimePreparation:
    requested_model: str | None
    settings: AgentSettings
    owner_type: str
    owner_id: str
    deps: AgentTurnEngineDependencies


def build_agent_turn_engine_dependencies(
    *,
    api_dependencies: ApiDependencies,
    logger: LoggerProtocol,
) -> AgentTurnEngineDependencies:
    return AgentTurnEngineDependencies(
        database_agent_turns=api_dependencies.database_agent_turns,
        database_tool_calls=api_dependencies.database_tool_calls,
        database_agent_todo_state=api_dependencies.database_agent_todo_state,
        database_agent_plan=api_dependencies.database_agent_plan,
        database_notifications=api_dependencies.database_notifications,
        conversation_attention=api_dependencies.conversation_attention,
        database_input_queue=api_dependencies.database_input_queue,
        database_users=api_dependencies.database_users,
        agent_chronology_sequencer=api_dependencies.agent_chronology_sequencer,
        tool_call_processor=api_dependencies.tool_call_processor,
        prompt_token_counter=api_dependencies.prompt_token_counter,
        event_bus=api_dependencies.event_bus,
        cancellation_history=api_dependencies.cancellation_history,
        token_collection=api_dependencies.token_collection,
        task_cancellation_binder=api_dependencies.task_cancellation_binder,
        task_registry=api_dependencies.task_registry,
        task_registry_queries=api_dependencies.task_registry_queries,
        logger=logger,
    )


def build_headless_agent_turn_engine_dependencies_from_api_dependencies(
    *,
    api_dependencies: ApiDependencies,
    logger: LoggerProtocol,
) -> AgentTurnEngineDependencies:
    return replace(
        build_agent_turn_engine_dependencies(
            api_dependencies=api_dependencies,
            logger=logger,
        ),
        event_bus=None,
    )


async def resolve_agent_request_settings(
    *,
    request: ConnectionProtocol,
    api_dependencies: ApiDependencies,
    user_id: int,
    request_json: JSONDict,
    model_settings: JSONDict | None,
) -> tuple[str | None, int | None, AgentSettings]:
    request_model = resolve_optional_model_name(request_json)
    try:
        resolution = await resolve_agent_runtime_settings(
            api_dependencies=api_dependencies,
            user_id=user_id,
            model_settings=model_settings or {},
            request_model=request_model,
        )
    except ValidationError as exception:
        raise_invalid_request(request, str(exception))
    except ConfigurationError as exception:
        raise_server_error(request, str(exception))
    return (
        resolution.requested_model,
        resolution.context_window_tokens,
        resolution.settings,
    )


async def prepare_agent_runtime(
    *,
    request: ConnectionProtocol,
    api_dependencies: ApiDependencies,
    context: RequestContext,
    tool_context: MCPToolContext,
    prepared_agent_request: PreparedExecutionRequest,
    logger: LoggerProtocol,
) -> AgentRuntimePreparation:
    prepared_state = prepared_agent_request
    if (
        prepared_state.conv_id != tool_context.conv_id
        or prepared_state.user_id != tool_context.user_id
    ):
        raise_invalid_request(
            request,
            "Prepared agent request state does not match the conversation tool context.",
        )
    requested_model = prepared_state.requested_model
    settings = prepared_state.agent_settings
    if tool_context.user_id <= 0:
        raise_invalid_request(request, "Agent mode requires an authenticated WebUI user.")
    apply_agent_runtime_context_fields(
        context=context,
        settings=settings,
        requested_model=requested_model,
        turn_scope=TURN_SCOPE_ROOT,
    )
    owner_type = "conversation"
    owner_id = tool_context.conv_id
    deps = build_agent_turn_engine_dependencies(
        api_dependencies=api_dependencies,
        logger=logger,
    )
    return AgentRuntimePreparation(
        requested_model=requested_model,
        settings=settings,
        owner_type=owner_type,
        owner_id=owner_id,
        deps=deps,
    )

"""SoAI - Unified API runtime initialization [backend/app/server_api_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import FastAPI

from app.application_dependencies import ApplicationServerModuleDependencies
from app.composition.build_agent_subagent_service import build_agent_subagent_service
from app.composition.build_shell_background_service import (
    build_shell_background_service,
)
from core.errors.exceptions import StateError
from core.rate_limiting.moving_window import MovingWindowRateLimiter
from core.runtime.state_access import (
    read_state_flag,
    read_state_has_key,
    read_state_value,
)
from core.runtime.trusted_proxy import read_trusted_proxy_networks
from features.agent.runtime.agent_state_service import (
    AgentStateService,
    AgentStateServiceDependencies,
)
from features.agent.runtime.chronology_sequencer import (
    AgentChronologySequencer,
    AgentChronologySequencerDependencies,
)
from features.api.lifecycle.lifecycle import (
    ApiLifecycleManager,
    ApiLifecycleManagerDependencies,
)
from features.api.route_loader_service import (
    ApiRouteLoaderService,
    ApiRouteLoaderServiceDependencies,
)
from features.api.route_modules import get_route_registrars
from features.api.runtime.command_dispatcher import (
    CommandDispatcher,
    CommandDispatcherDependencies,
)
from features.api.runtime.container.api_runtime_services import ApiRuntimeServices
from features.api.runtime.container.types import ApiDependencies

if TYPE_CHECKING:
    from app.application_host_instance import ApplicationHostInstance

__all__ = (
    "UnifiedApiRuntime",
    "initialize_unified_api_runtime",
)


@dataclass(frozen=True, slots=True)
class UnifiedApiRuntime:
    app: FastAPI
    request_rate_limiter: MovingWindowRateLimiter
    proxy_headers_enabled: bool
    trusted_proxy_networks: tuple[str, ...]


def initialize_unified_api_runtime(
    application_instance: ApplicationHostInstance,
    module_dependencies: ApplicationServerModuleDependencies,
) -> UnifiedApiRuntime:
    api_app = module_dependencies.api_initialize()
    if not isinstance(api_app, FastAPI):
        raise StateError("API initializer did not return a FastAPI app instance.")
    request_rate_limiter = _resolve_request_rate_limiter(api_app)
    api_route_composition = application_instance.edition_composition.api_routes
    route_loader_service = ApiRouteLoaderService(
        ApiRouteLoaderServiceDependencies(
            route_registrars=get_route_registrars(api_route_composition.registrars),
        ),
    )

    def build_api_runtime_services() -> ApiRuntimeServices:
        services = application_instance.services
        return ApiRuntimeServices(
            command_dispatcher=CommandDispatcher(
                CommandDispatcherDependencies(
                    event_bus=services.infrastructure.event_bus,
                    task_registry=services.tasks.task_registry,
                ),
            ),
            agent_chronology_sequencer=AgentChronologySequencer(
                AgentChronologySequencerDependencies(
                    database_agent_event_sequences=services.databases.agent_event_sequences,
                ),
            ),
            agent_state_service=AgentStateService(
                AgentStateServiceDependencies(
                    database_agent_event_sequences=services.databases.agent_event_sequences,
                    database_agent_plan=services.databases.agent_plan,
                    database_agent_todo_state=services.databases.agent_todo_state,
                    database_agent_turns=services.databases.agent_turns,
                    database_tool_calls=services.databases.tool_calls,
                    task_registry_queries=services.tasks.task_registry_queries,
                    token_collection=services.tasks.token_collection,
                ),
            ),
        )

    unified_app = ApiLifecycleManager(
        ApiLifecycleManagerDependencies(
            build_api_runtime_services=build_api_runtime_services,
            fastapi_app=api_app,
            request_rate_limiter=request_rate_limiter,
            route_loader_service=route_loader_service,
            api_route_composition=api_route_composition,
        ),
    ).initialize(application_instance)
    api_dependencies = _resolve_api_dependencies(unified_app)
    build_agent_subagent_service(api_dependencies)
    build_shell_background_service(api_dependencies)
    proxy_headers_enabled = _resolve_proxy_headers_enabled(unified_app)
    trusted_proxy_networks = _resolve_trusted_proxy_networks(unified_app)
    return UnifiedApiRuntime(
        app=unified_app,
        request_rate_limiter=request_rate_limiter,
        proxy_headers_enabled=proxy_headers_enabled,
        trusted_proxy_networks=trusted_proxy_networks,
    )


def _resolve_request_rate_limiter(api_app: FastAPI) -> MovingWindowRateLimiter:
    request_rate_limiter = read_state_value(
        api_app.state,
        "request_rate_limiter",
        MovingWindowRateLimiter,
    )
    if request_rate_limiter is None:
        raise StateError(
            "API core module did not configure a request limiter instance.",
        )
    return request_rate_limiter


def _resolve_api_dependencies(unified_app: FastAPI) -> ApiDependencies:
    api_dependencies = read_state_value(unified_app.state, "api_dependencies", ApiDependencies)
    if api_dependencies is None:
        raise StateError("API dependencies were not attached to the FastAPI app.")
    if not isinstance(api_dependencies, ApiDependencies):
        raise StateError("FastAPI app is missing a valid ApiDependencies instance.")
    return api_dependencies


def _resolve_proxy_headers_enabled(unified_app: FastAPI) -> bool:
    if not read_state_has_key(unified_app.state, "proxy_headers_enabled"):
        raise StateError(
            "API lifecycle did not configure proxy header runtime state.",
        )
    return read_state_flag(unified_app.state, "proxy_headers_enabled")


def _resolve_trusted_proxy_networks(unified_app: FastAPI) -> tuple[str, ...]:
    proxy_networks = read_trusted_proxy_networks(unified_app.state)
    if proxy_networks is None:
        raise StateError("API lifecycle did not configure trusted proxy networks.")
    return tuple(str(network) for network in proxy_networks)

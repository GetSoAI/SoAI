"""SoAI - MCP server intermediate services initialization [backend/mcp/server/initialization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.browser_adblock.protocols import EasyListAdblockServiceProtocol
from core.concurrency.task_groups import ManagedTaskGroup
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.logging.trace import get_logger
from core.runtime.soai_identifiers import build_soai_id
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.timing.monotonic import monotonic_ms
from mcp.assembly import create_utility_tools, create_web_fetcher
from mcp.rag.scraper.internal_protocols import WebContentFetcherProtocol
from mcp.search.api_keys import SearchProviderApiKeys
from mcp.search.dependencies import MCPSearchDependencies
from mcp.search.providers import get_search_providers
from mcp.search.web_search import MCPWebSearch
from mcp.server.runtime_config import MCPRuntimeConfig, build_runtime_config
from mcp.server.state import MCPServerState

if TYPE_CHECKING:
    from core.timing.startup_timings import StartupTimingsRecorder
    from mcp.server.dependencies import MCPServerDependencies
    from mcp.tools.service import MCPUtilityTools

__all__ = (
    "MCPServerIntermediateServices",
    "create_mcp_server_intermediate_services",
)

LOGGER_NAME = "SoAI.mcp.server.initialization"
OPERATION_MCP_SERVER_REFRESH_ADBLOCK_SERVICE = "mcp.server.initialization.refresh_adblock_service"
ADBLOCK_REFRESH_EXCEPTIONS: tuple[type[Exception], ...] = (
    ValidationError,
    *RECOVERABLE_EXCEPTIONS,
)


@dataclass(frozen=True, slots=True)
class MCPServerIntermediateServices:
    runtime_config: MCPRuntimeConfig
    web_fetcher: WebContentFetcherProtocol | None
    state: MCPServerState
    mcp_search: MCPWebSearch
    mcp_search_api_keys: SearchProviderApiKeys
    utility_tools: MCPUtilityTools


def create_mcp_server_intermediate_services(
    deps: MCPServerDependencies,
    shutdown_event: asyncio.Event,
    background_tasks: ManagedTaskGroup,
    *,
    adblock_service: EasyListAdblockServiceProtocol,
    startup_timings: StartupTimingsRecorder,
) -> MCPServerIntermediateServices:
    logger = get_logger(LOGGER_NAME)
    step_started_ms = monotonic_ms()
    runtime_config = build_runtime_config(deps.config)
    startup_timings.record_since_ms("assembly.mcp.runtime_config_ms", step_started_ms)
    http_client = deps.http_client
    if http_client is None:
        raise ValidationError("HTTP client is required for MCP services.")
    step_started_ms = monotonic_ms()
    web_fetcher = create_web_fetcher(
        http_client,
        deps.config,
        deps.runtime_flags,
        deps.storage_manager,
        parser_registry_factory=deps.parser_registry_factory,
        adblock_service=adblock_service,
    )
    startup_timings.record_since_ms("assembly.mcp.web_fetcher_ms", step_started_ms)
    if web_fetcher is None:
        raise ValidationError("WebContentFetcher is required for MCP services.")
    step_started_ms = monotonic_ms()
    state = MCPServerState(shutdown_event=shutdown_event)
    state.background_tasks = background_tasks
    search_dependencies = MCPSearchDependencies(
        config=deps.config,
        database_plugins=deps.database_plugins,
        fernet=deps.database_plugins.fernet,
        http_client=http_client,
        runtime_flags=deps.runtime_flags,
        task_registry=deps.task_registry,
        event_bus=deps.event_bus,
        metrics_manager=deps.metrics_manager,
        cancellation_history=deps.cancellation_history,
        cancellation_event_bus=deps.cancellation_event_bus,
        token_collection=deps.token_collection,
        web_fetcher=web_fetcher,
        search_providers=get_search_providers(),
    )
    mcp_search_api_keys = SearchProviderApiKeys(
        search_dependencies.database_plugins,
        search_dependencies.fernet,
        search_dependencies.search_providers,
    )
    mcp_search = MCPWebSearch(
        search_dependencies,
        api_key_resolver=mcp_search_api_keys.resolve_search_provider_api_key,
    )
    startup_timings.record_since_ms("assembly.mcp.search_services_ms", step_started_ms)
    state.mcp_search = mcp_search
    state.mcp_search_api_keys = mcp_search_api_keys
    step_started_ms = monotonic_ms()
    utility_tools = create_utility_tools(
        http_client=http_client,
        web_fetcher=web_fetcher,
        config=deps.config,
        runtime_flags=deps.runtime_flags,
        storage_manager=deps.storage_manager,
        hardware_manager=deps.hardware_manager,
        hardware_control=deps.hardware_control,
        hardware_soaibench=deps.hardware_soaibench,
        active_client_context=deps.active_client_context,
        active_user_id_context=deps.active_user_id_context,
        active_tool_call_context=deps.active_tool_call_context,
        active_request_context=deps.active_request_context,
        database_files=deps.database_files,
        database_memory=deps.database_memory,
        database_plugins=deps.database_plugins,
        database_users=deps.database_users,
        database_agent_event_sequences=deps.database_agent_event_sequences,
        database_agent_todo_state=deps.database_agent_todo_state,
        database_agent_plan=deps.database_agent_plan,
        database_conversations=deps.database_conversations,
        database_messages=deps.database_messages,
        database_notifications=deps.database_notifications,
        conversation_attention=deps.conversation_attention,
        database_password_vault=deps.database_password_vault,
        database_automations=deps.database_automations,
        database_chat_identity_defaults=deps.database_chat_identity_defaults,
        database_chat_model_defaults=deps.database_chat_model_defaults,
        database_automation_runs=deps.database_automation_runs,
        database_tool_calls=deps.database_tool_calls,
        database_read_video=deps.database_read_video,
        task_registry=deps.task_registry,
        cancellation_binder=deps.cancellation_binder,
        model_resolution_service=deps.model_resolution_service,
        model_information_service=deps.model_information_service,
        model_virtual_model_service=deps.model_virtual_model_service,
        finalizer_tracker=deps.finalizer_tracker,
        secret_handle_store=deps.secret_handle_store,
        parser_registry_factory=deps.parser_registry_factory,
        document_reader=deps.document_reader,
        messaging_platform_detector=deps.messaging_platform_detector,
        messaging_parser_registry_factory=deps.messaging_parser_registry_factory,
        terminal=deps.terminal,
        mcp_remote=deps.mcp_remote,
        prompt_token_counter=deps.prompt_token_counter,
        event_bus=deps.event_bus,
        logger=logger,
        read_audio_gateway=deps.read_audio_gateway,
        adblock_service=adblock_service,
    )
    startup_timings.record_since_ms("assembly.mcp.utility_tools_ms", step_started_ms)
    state.utility_tools = utility_tools
    if not deps.runtime_flags.offline_mode:
        startup_refresh_task = spawn_tracked_task(
            _refresh_adblock_service(adblock_service, logger),
            name="mcp-browser-adblock-startup-refresh",
            logger=logger,
            cancellation_binder=deps.cancellation_binder,
            cancellation_id=build_soai_id(("sys", "mcp", "adblock_startup_refresh")),
            finalizer_tracker=deps.finalizer_tracker,
            owner="mcp_adblock_startup_refresh",
        )
        _ = background_tasks.track(startup_refresh_task)
    return MCPServerIntermediateServices(
        runtime_config=runtime_config,
        web_fetcher=web_fetcher,
        state=state,
        mcp_search=mcp_search,
        mcp_search_api_keys=mcp_search_api_keys,
        utility_tools=utility_tools,
    )


async def _refresh_adblock_service(
    adblock_service: EasyListAdblockServiceProtocol,
    logger: LoggerProtocol,
) -> None:
    try:
        await adblock_service.refresh_from_remote()
    except ADBLOCK_REFRESH_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Browser adblock refresh failed; keeping existing matcher.",
            operation=OPERATION_MCP_SERVER_REFRESH_ADBLOCK_SERVICE,
        )

"""SoAI - MCP utility tools service [backend/mcp/tools/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.agent.protocols import AgentSubagentServiceProtocol
from core.mcp.protocols_main import ShellBackgroundServiceProtocol
from mcp.tools.generate_image_horde_rate_limit import AnonymousHordeRateGate
from mcp.tools.handlers import build_internal_utility_tool_handlers
from mcp.tools.internal_protocols import MCPUtilityToolsDependencies
from mcp.tools.news_cache import NewsResponseCache
from mcp.tools.news_gal_feed import NewsArticleListSearch
from mcp.tools.news_provider_control import NewsProviderAccessController

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "MCPUtilityTools",
    "MCPUtilityToolsDependencies",
)


class MCPUtilityTools:
    def __init__(self, deps: MCPUtilityToolsDependencies) -> None:
        self.config = deps.config
        self.storage_manager = deps.storage_manager
        self.hardware_manager = deps.hardware_manager
        self.hardware_control = deps.hardware_control
        self.hardware_soaibench = deps.hardware_soaibench
        self.runtime_flags = deps.runtime_flags
        self.http_client = deps.http_client
        self.web_fetcher = deps.web_fetcher
        self.read_audio_gateway = deps.read_audio_gateway
        self.generate_image_horde_rate_gate = AnonymousHordeRateGate()
        self.news_provider_control = NewsProviderAccessController()
        self.news_article_list_search = NewsArticleListSearch()
        self.news_cache = NewsResponseCache()
        self.event_bus = deps.event_bus
        self.active_tool_call_context = deps.active_tool_call_context
        self.active_request_context = deps.active_request_context
        self.files = deps.files
        self.database_files = deps.database_files
        self.database_memory = deps.database_memory
        self.database_plugins = deps.database_plugins
        self.database_users = deps.database_users
        self.database_agent_event_sequences = deps.database_agent_event_sequences
        self.database_agent_todo_state = deps.database_agent_todo_state
        self.database_agent_plan = deps.database_agent_plan
        self.database_conversations = deps.database_conversations
        self.database_messages = deps.database_messages
        self.database_notifications = deps.database_notifications
        self.conversation_attention = deps.conversation_attention
        self.database_password_vault = deps.database_password_vault
        self.database_automations = deps.database_automations
        self.database_chat_identity_defaults = deps.database_chat_identity_defaults
        self.database_chat_model_defaults = deps.database_chat_model_defaults
        self.database_automation_runs = deps.database_automation_runs
        self.database_tool_calls = deps.database_tool_calls
        self.database_read_video = deps.database_read_video
        self.task_registry = deps.task_registry
        self.task_cancellation_binder = deps.task_cancellation_binder
        self.model_resolution_service = deps.model_resolution_service
        self.model_information_service = deps.model_information_service
        self.model_virtual_model_service = deps.model_virtual_model_service
        self.secret_handle_store = deps.secret_handle_store
        self.messaging_platform_detector = deps.messaging_platform_detector
        self.messaging_parser_registry_factory = deps.messaging_parser_registry_factory
        self.parser_registry_factory = deps.parser_registry_factory
        self.document_reader = deps.document_reader
        self.terminal = deps.terminal
        self.mcp_remote = deps.mcp_remote
        self.runtime_sessions = deps.runtime_sessions
        self.browser_sessions = deps.browser_sessions
        self.prompt_token_counter = deps.prompt_token_counter
        self.subagent_service = deps.subagent_service
        self.shell_background_service = deps.shell_background_service

    def get_tool_handlers(self) -> dict[str, Callable[[JSONDict], Awaitable[JSONValue]]]:
        return build_internal_utility_tool_handlers(self)

    def attach_subagent_service(self, service: AgentSubagentServiceProtocol) -> None:
        self.subagent_service = service

    def attach_shell_background_service(self, service: ShellBackgroundServiceProtocol) -> None:
        self.shell_background_service = service

    async def shutdown(self) -> None:
        if self.shell_background_service is not None:
            await self.shell_background_service.shutdown()
        await self.browser_sessions.shutdown()

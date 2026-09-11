"""SoAI - MCP server tool resource and prompt registration service [backend/mcp/server/handlers/registration_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping, MutableMapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.logging.trace import get_logger
from core.mcp.catalog_merging import merge_named_catalog_items
from core.mcp.protocols_main import MCPSearchProtocol, MCPServerProtocol
from core.mcp.protocols_rag import MCPRAGProtocol
from core.mcp.tool_catalog_scope import MCPToolCatalogScope
from core.mcp.validation import get_required_argument
from core.models.protocols import ModelInformationServiceProtocol
from mcp.calendar.handlers import build_calendar_tool_handlers
from mcp.calendar.resources import make_resource_calendar
from mcp.handlers.prompts import build_mcp_rag_prompt_handlers
from mcp.handlers.tools.builder import build_mcp_rag_tool_handlers
from mcp.mail.handlers import build_mail_tool_handlers
from mcp.mail.resources import make_resource_mail
from mcp.protocol.types import MCPJSONRPCError
from mcp.registry.prompts import (
    make_prompt_model_selection,
    make_prompt_plugin_info,
    make_prompt_system_overview,
)
from mcp.registry.resources import (
    make_resource_models,
    make_resource_plugins,
    make_resource_system_status,
)
from mcp.registry.tools_definitions import build_tool_definitions
from mcp.search.handlers import build_mcp_search_tool_handlers
from mcp.server.handlers.exposure_drift import report_exposed_tools_drift
from mcp.shared.protocol_arguments import get_required_str_with_missing_message
from mcp.tools.handlers import build_internal_utility_tool_handlers

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from mcp.protocol.types import PromptHandler, ToolHandler
    from mcp.server.state import MCPServerState
    from mcp.tools.service import MCPUtilityTools

__all__ = (
    "MCPRegistrationService",
    "MCPRegistrationServiceDependencies",
)

LOGGER_NAME = "SoAI.mcp.server.registration_service"


@dataclass(frozen=True, slots=True)
class MCPRegistrationServiceDependencies:
    state: MCPServerState
    exposed_tools: set[str] | None
    exposed_resources: set[str] | None
    exposed_prompts: set[str] | None
    model_information_service: ModelInformationServiceProtocol
    mcp_search: MCPSearchProtocol | None
    utility_tools: MCPUtilityTools | None
    require_authenticated_user_id: Callable[[str], int]
    current_session_identity: Callable[[], tuple[int, str | None]]
    server_ref: MCPServerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MCPRegistrationServiceDependencies",
            current_session_identity=self.current_session_identity,
            model_information_service=self.model_information_service,
            require_authenticated_user_id=self.require_authenticated_user_id,
            server_ref=self.server_ref,
            state=self.state,
        )


class MCPRegistrationService:
    def __init__(self, deps: MCPRegistrationServiceDependencies) -> None:
        self._state = deps.state
        self._exposed_tools = deps.exposed_tools
        self._exposed_resources = deps.exposed_resources
        self._exposed_prompts = deps.exposed_prompts
        self._model_information_service = deps.model_information_service
        self._mcp_search = deps.mcp_search
        self._utility_tools = deps.utility_tools
        self._require_authenticated_user_id = deps.require_authenticated_user_id
        self._current_session_identity = deps.current_session_identity
        self._server_ref = deps.server_ref

    def register_exposed_items[HandlerT](
        self,
        handlers: Mapping[str, HandlerT],
        exposed: Collection[str] | None,
        destination: MutableMapping[str, HandlerT],
        log_format: str,
        key_prefix: str = "",
        exposure_key: str = "",
    ) -> None:
        logger = get_logger(LOGGER_NAME)
        if exposed is None:
            logger.critical(
                "MCP server mode exposure list is not configured for %s; refusing to expose any %s.",
                exposure_key or "unknown",
                exposure_key or "items",
            )
            return
        for name, handler in handlers.items():
            if name in exposed:
                destination[f"{key_prefix}{name}"] = handler
                logger.debug(log_format, f"{key_prefix}{name}")

    def get_available_rag_tools(self) -> dict[str, ToolHandler]:
        if not self._state.mcp_rag:
            return {}
        handlers: dict[str, ToolHandler] = {}
        for name, handler in build_mcp_rag_tool_handlers(
            self._state.mcp_rag,
            require_authenticated_user_id=self._require_authenticated_user_id,
            get_session_identity=self._current_session_identity,
        ).items():
            handlers[name] = handler
        return handlers

    def get_available_search_tools(self) -> dict[str, ToolHandler]:
        if not self._mcp_search:
            return {}
        handlers: dict[str, ToolHandler] = {}
        for name, handler in build_mcp_search_tool_handlers(
            self._mcp_search,
            get_session_identity=self._current_session_identity,
            get_required_arg=self.get_required_str_argument,
        ).items():
            handlers[name] = handler
        return handlers

    def get_available_utility_tools(self) -> dict[str, ToolHandler]:
        if not self._utility_tools:
            return {}
        return build_internal_utility_tool_handlers(self._utility_tools)

    def get_available_mail_tools(self) -> dict[str, ToolHandler]:
        return build_mail_tool_handlers(
            self._server_ref.mail,
            account_queries=self._server_ref.mail_account_queries,
            require_authenticated_user_id=self._require_authenticated_user_id,
            request_context_provider=lambda: self._server_ref.utility_tools.active_request_context.get(
                None,
            ),
            notify_resource_updated=self._server_ref.notify_resource_updated,
        )

    def get_available_calendar_tools(self) -> dict[str, ToolHandler]:
        return build_calendar_tool_handlers(
            self._server_ref.calendar,
            account_queries=self._server_ref.calendar_account_queries,
            require_authenticated_user_id=self._require_authenticated_user_id,
            notify_resource_updated=self._server_ref.notify_resource_updated,
        )

    def build_local_tool_handlers(self) -> dict[str, ToolHandler]:
        tools: dict[str, ToolHandler] = {}
        tools = merge_named_catalog_items(
            tools,
            self.get_available_rag_tools(),
            existing_label="mcp_tool_handlers",
            incoming_label="rag_tool_handlers",
        )
        tools = merge_named_catalog_items(
            tools,
            self.get_available_search_tools(),
            existing_label="mcp_tool_handlers",
            incoming_label="search_tool_handlers",
        )
        tools = merge_named_catalog_items(
            tools,
            self.get_available_mail_tools(),
            existing_label="mcp_tool_handlers",
            incoming_label="mail_tool_handlers",
        )
        tools = merge_named_catalog_items(
            tools,
            self.get_available_calendar_tools(),
            existing_label="mcp_tool_handlers",
            incoming_label="calendar_tool_handlers",
        )
        return merge_named_catalog_items(
            tools,
            self.get_available_utility_tools(),
            existing_label="mcp_tool_handlers",
            incoming_label="utility_tool_handlers",
        )

    def register_local_tools(self) -> None:
        local_tools = self._state.registration.available_local_tools
        local_tools.clear()
        local_tools.update(self.build_local_tool_handlers())
        get_logger(LOGGER_NAME).debug(
            "Local MCP tool catalog holds %d tool(s).",
            len(local_tools),
        )

    def register_soai_tools(self) -> None:
        if not self._state.registration.available_local_tools:
            self.register_local_tools()
        exposable_definitions = self.tool_definitions("public")
        exposable_tools = {
            name: handler
            for name, handler in self._state.registration.available_local_tools.items()
            if name in exposable_definitions
        }
        report_exposed_tools_drift(
            exposed_tools=self._exposed_tools,
            known_tool_names=set(self.tool_definitions("internal_admin")),
            exposable_tool_names=set(exposable_definitions),
            logger=get_logger(LOGGER_NAME),
        )
        self.register_exposed_items(
            exposable_tools,
            self._exposed_tools,
            self._state.registration.registered_tools,
            "Registered MCP tool: %s",
            exposure_key="tools",
        )

    def register_soai_resources(self) -> None:
        self.register_exposed_items(
            {
                "models": make_resource_models(self._server_ref),
                "plugins": make_resource_plugins(self._server_ref),
                "system_status": make_resource_system_status(self._server_ref),
                "mail": make_resource_mail(self._server_ref),
                "calendar": make_resource_calendar(self._server_ref),
            },
            self._exposed_resources,
            self._state.registration.registered_resources,
            "Registered MCP resource: %s",
            key_prefix="soai://",
            exposure_key="resources",
        )

    def register_soai_prompts(self) -> None:
        prompts: dict[str, PromptHandler] = {
            "system_overview": make_prompt_system_overview(self._server_ref),
            "model_selection": make_prompt_model_selection(self._server_ref),
            "plugin_info": make_prompt_plugin_info(self._server_ref),
        }
        if self._state.mcp_rag:
            prompts = merge_named_catalog_items(
                prompts,
                build_mcp_rag_prompt_handlers(
                    self._state.mcp_rag,
                    require_authenticated_user_id=self._require_authenticated_user_id,
                ),
                existing_label="mcp_prompt_handlers",
                incoming_label="rag_prompt_handlers",
            )
        self.register_exposed_items(
            prompts,
            self._exposed_prompts,
            self._state.registration.registered_prompts,
            "Registered MCP prompt: %s",
            exposure_key="prompts",
        )

    def require[RequiredT](self, value: RequiredT | None, name: str) -> RequiredT:
        if value is None:
            raise MCPJSONRPCError(-32603, f"{name} not available")
        return value

    def require_rag(self) -> MCPRAGProtocol:
        return self.require(self._state.mcp_rag, "RAG engine")

    def get_required_str_argument(self, arguments: JSONDict, key: str) -> str:
        return get_required_str_with_missing_message(
            arguments,
            key,
            missing_message=f"Missing required parameter: {key}",
        )

    def get_argument(self, parameters: JSONDict, key: str) -> JSONValue:
        return get_required_argument(
            parameters,
            key,
            missing_message=f"Missing required parameter: {key}",
        )

    def registered_tool_names(self) -> list[str]:
        return sorted(self._state.registration.registered_tools)

    def available_local_tool_names(
        self,
        local_scope: MCPToolCatalogScope = "public",
    ) -> list[str]:
        definitions = self.tool_definitions(local_scope)
        return sorted(
            name for name in self._state.registration.available_local_tools if name in definitions
        )

    def plugin_tool_definitions(self) -> dict[str, JSONDict]:
        return self._server_ref.plugin_tool_definitions()

    def tool_definitions(self, local_scope: MCPToolCatalogScope = "public") -> dict[str, JSONDict]:
        definitions = dict(build_tool_definitions(local_scope))
        return merge_named_catalog_items(
            definitions,
            self.plugin_tool_definitions(),
            existing_label="soai_tool_definitions",
            incoming_label="plugin_tool_definitions",
        )

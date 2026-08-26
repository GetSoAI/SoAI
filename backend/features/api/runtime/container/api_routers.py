"""SoAI - API router definitions [backend/features/api/runtime/container/api_routers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import APIRouter

from core.errors.exceptions import StateError
from core.system_api.route_paths import (
    ANTHROPIC_MESSAGES_PATH,
    MCP_ROOT_PATH,
    OPENAI_CHAT_COMPLETIONS_PATH,
    OPENAI_COMPAT_PREFIX,
    OPENAI_COMPLETIONS_PATH,
    OPENAI_FILES_PATH,
    OPENAI_RESPONSES_PATH,
    SOAI_ACTIONS_PREFIX,
    SOAI_AUTOMATIONS_PREFIX,
    SOAI_BACKUPS_PREFIX,
    SOAI_CONFIGS_PREFIX,
    SOAI_FILE_EXPLORER_PREFIX,
    SOAI_FILES_PREFIX,
    SOAI_HARDWARE_PREFIX,
    SOAI_MCP_PREFIX,
    SOAI_MESSAGING_PREFIX,
    SOAI_METRICS_PREFIX,
    SOAI_MODELS_PREFIX,
    SOAI_PLUGINS_PREFIX,
    SOAI_ROUTING_PREFIX,
    SOAI_SEARCH_PREFIX,
    SOAI_SOFTWARE_PREFIX,
    SOAI_SYSTEM_PREFIX,
    SOAI_TASKS_PREFIX,
    SOAI_WEBUI_PREFIX,
)

__all__ = (
    "ApiRouterRateLimitSource",
    "ApiRouters",
    "build_api_routers",
    "iter_app_routers",
    "iter_rate_limit_router_sources",
)


@dataclass(frozen=True, slots=True)
class ApiRouters:
    anthropic_public: APIRouter
    openai_public: APIRouter
    openai_files: APIRouter
    messaging: APIRouter
    system: APIRouter
    metrics: APIRouter
    hardware: APIRouter
    models: APIRouter
    plugins: APIRouter
    configs: APIRouter
    routing: APIRouter
    software: APIRouter
    actions: APIRouter
    automations: APIRouter
    webui: APIRouter
    search: APIRouter
    files: APIRouter
    mcp: APIRouter
    mcp_streamable_http: APIRouter
    tasks: APIRouter
    backup: APIRouter
    file_explorer: APIRouter
    host_management: APIRouter | None

    def require_host_management(self) -> APIRouter:
        if self.host_management is None:
            raise StateError(
                "Host-management routes were registered without an edition router.",
                operation="features.api.runtime.container.api_routers.require_host_management",
            )
        return self.host_management


@dataclass(frozen=True, slots=True)
class ApiRouterRateLimitSource:
    name: str
    router: APIRouter
    default_stream_paths: tuple[str, ...] = ()


def build_api_routers(
    host_management_router_factory: Callable[[], APIRouter] | None = None,
) -> ApiRouters:
    return ApiRouters(
        anthropic_public=APIRouter(prefix=OPENAI_COMPAT_PREFIX, tags=["Anthropic API Surface"]),
        openai_public=APIRouter(prefix=OPENAI_COMPAT_PREFIX, tags=["OpenAI API Surface"]),
        openai_files=APIRouter(prefix=OPENAI_FILES_PATH, tags=["OpenAI Files"]),
        messaging=APIRouter(prefix=SOAI_MESSAGING_PREFIX, tags=["Messaging & Platforms"]),
        system=APIRouter(prefix=SOAI_SYSTEM_PREFIX, tags=["System & Monitoring"]),
        metrics=APIRouter(prefix=SOAI_METRICS_PREFIX, tags=["Metrics Monitoring"]),
        hardware=APIRouter(prefix=SOAI_HARDWARE_PREFIX, tags=["Hardware Management"]),
        models=APIRouter(prefix=SOAI_MODELS_PREFIX, tags=["Model Management"]),
        plugins=APIRouter(prefix=SOAI_PLUGINS_PREFIX, tags=["Plugin & Provider Management"]),
        configs=APIRouter(prefix=SOAI_CONFIGS_PREFIX, tags=["Configuration Management"]),
        routing=APIRouter(prefix=SOAI_ROUTING_PREFIX, tags=["Dynamic Routing"]),
        software=APIRouter(prefix=SOAI_SOFTWARE_PREFIX, tags=["Software Management"]),
        actions=APIRouter(prefix=SOAI_ACTIONS_PREFIX, tags=["Actions & Control"]),
        automations=APIRouter(prefix=SOAI_AUTOMATIONS_PREFIX, tags=["Automations"]),
        webui=APIRouter(prefix=SOAI_WEBUI_PREFIX, tags=["WebUI & User Management"]),
        search=APIRouter(prefix=SOAI_SEARCH_PREFIX, tags=["Search"]),
        files=APIRouter(prefix=SOAI_FILES_PREFIX, tags=["Files"]),
        mcp=APIRouter(prefix=SOAI_MCP_PREFIX, tags=["Model Context Protocol"]),
        mcp_streamable_http=APIRouter(prefix=MCP_ROOT_PATH, tags=["Model Context Protocol"]),
        tasks=APIRouter(prefix=SOAI_TASKS_PREFIX, tags=["Task Management"]),
        backup=APIRouter(prefix=SOAI_BACKUPS_PREFIX, tags=["Backup Management"]),
        file_explorer=APIRouter(prefix=SOAI_FILE_EXPLORER_PREFIX, tags=["File Explorer"]),
        host_management=(
            None if host_management_router_factory is None else host_management_router_factory()
        ),
    )


def iter_app_routers(routers: ApiRouters) -> tuple[APIRouter, ...]:
    base_routers = (
        routers.anthropic_public,
        routers.openai_public,
        routers.openai_files,
        routers.messaging,
        routers.system,
        routers.metrics,
        routers.hardware,
        routers.models,
        routers.plugins,
        routers.configs,
        routers.routing,
        routers.software,
        routers.actions,
        routers.automations,
        routers.webui,
        routers.search,
        routers.files,
        routers.mcp,
        routers.mcp_streamable_http,
        routers.tasks,
        routers.backup,
        routers.file_explorer,
    )
    if routers.host_management is None:
        return base_routers
    return base_routers + (routers.host_management,)


def iter_rate_limit_router_sources(routers: ApiRouters) -> tuple[ApiRouterRateLimitSource, ...]:
    base_sources = (
        ApiRouterRateLimitSource("system", routers.system),
        ApiRouterRateLimitSource("metrics", routers.metrics),
        ApiRouterRateLimitSource("hardware", routers.hardware),
        ApiRouterRateLimitSource("models", routers.models),
        ApiRouterRateLimitSource("plugins", routers.plugins),
        ApiRouterRateLimitSource("configs", routers.configs),
        ApiRouterRateLimitSource("routing", routers.routing),
        ApiRouterRateLimitSource("software", routers.software),
        ApiRouterRateLimitSource("actions", routers.actions),
        ApiRouterRateLimitSource("webui", routers.webui),
        ApiRouterRateLimitSource("search", routers.search),
        ApiRouterRateLimitSource("mcp", routers.mcp),
        ApiRouterRateLimitSource(
            "mcp_streamable_http",
            routers.mcp_streamable_http,
            (MCP_ROOT_PATH,),
        ),
        ApiRouterRateLimitSource("tasks", routers.tasks),
        ApiRouterRateLimitSource("backups", routers.backup),
        ApiRouterRateLimitSource("file_explorer", routers.file_explorer),
        ApiRouterRateLimitSource("files", routers.files),
        ApiRouterRateLimitSource(
            "public_anthropic",
            routers.anthropic_public,
            (ANTHROPIC_MESSAGES_PATH,),
        ),
        ApiRouterRateLimitSource(
            "public_openai",
            routers.openai_public,
            (OPENAI_CHAT_COMPLETIONS_PATH, OPENAI_COMPLETIONS_PATH, OPENAI_RESPONSES_PATH),
        ),
        ApiRouterRateLimitSource("openai_files", routers.openai_files, (OPENAI_FILES_PATH,)),
    )
    if routers.host_management is None:
        return base_sources
    return base_sources + (ApiRouterRateLimitSource("host_management", routers.host_management),)

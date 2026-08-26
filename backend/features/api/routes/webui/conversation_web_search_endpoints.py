"""SoAI - Per-conversation web search configuration API routes [backend/features/api/routes/webui/conversation_web_search_endpoints.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import APIRouter

from core.state.access import AccessAction
from features.api.routes.webui.conversation_web_search_handlers import (
    execute_web_search,
    get_web_search_config,
    update_web_search_config,
)
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.schemas.web_search import WebSearchConfigResponse

__all__ = (
    "register_endpoints",
    "register_routes",
)


def register_endpoints(router: APIRouter) -> None:
    router.get(
        "/conversations/{conv_id}/search/config",
        response_model=WebSearchConfigResponse,
        dependencies=require_action_dependencies(AccessAction.WEB_SEARCH),
    )(get_web_search_config)
    router.patch(
        "/conversations/{conv_id}/search/config",
        response_model=WebSearchConfigResponse,
        dependencies=require_action_dependencies(AccessAction.WEB_SEARCH),
    )(update_web_search_config)
    router.post(
        "/conversations/{conv_id}/search",
        dependencies=require_action_dependencies(AccessAction.WEB_SEARCH),
    )(execute_web_search)


def register_routes(routers: ApiRouters) -> None:
    register_endpoints(routers.webui)

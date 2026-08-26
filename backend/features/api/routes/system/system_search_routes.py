"""SoAI - Global search routes [backend/features/api/routes/system/system_search_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, Query, Request

from core.conversations.conversation_identifier import parse_conversation_identifier
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.state.access import AccessAction
from features.api.middleware.acl_enforcement import resolve_request_effective_actions
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_server_error
from features.api.schemas.search import SearchResults

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("register_routes",)

LOGGER_NAME = "SoAI.features.api.system_search_routes"
OPERATION = "api_system.global_search"


def register_routes(routers: ApiRouters) -> None:
    @routers.search.get(
        "/search",
        response_model=SearchResults,
        dependencies=require_action_dependencies(AccessAction.SEARCH_READ),
    )
    async def global_search(
        request: Request,
        query: str = Query(..., min_length=2, max_length=50, alias="q"),
        limit: int = Query(5, ge=1, le=20),
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> SearchResults:
        if not query.strip():
            return SearchResults()
        try:
            actions = await resolve_request_effective_actions(request)
            conversation_identifier = parse_conversation_identifier(query)
            if conversation_identifier is not None:
                if AccessAction.AUTH_COOKIE not in actions:
                    return SearchResults()
                conversation_records = api_context.dependencies.database_conversations
                referenced_conversations = (
                    await conversation_records.search_conversation_by_identifier(
                        current_user["id"],
                        conversation_identifier,
                    )
                )
                return SearchResults.model_validate(
                    {"conversations": referenced_conversations},
                )
            plugin_data = (
                await api_context.dependencies.plugin_manager.list_plugins()
                if AccessAction.PLUGIN_READ in actions
                else None
            )
            model_data = (
                await api_context.dependencies.model_information_service.model_get_formatted_list()
                if AccessAction.MODEL_READ in actions
                else None
            )
            hardware_data = (
                await api_context.dependencies.hw_manager.get_system_info(cache=True)
                if AccessAction.HARDWARE_READ in actions
                else None
            )
            results: dict[str, list[JSONDict]]
            if plugin_data is None and model_data is None and hardware_data is None:
                results = {"plugins": [], "models": [], "devices": []}
            else:
                results = api_context.dependencies.state_aggregator.search_store.search_with_data(
                    query,
                    plugin_data,
                    model_data,
                    hardware_data,
                    limit,
                )
            if AccessAction.AUTH_COOKIE in actions:
                results["conversations"] = (
                    await api_context.dependencies.database_conversations.search_conversation_titles(
                        current_user["id"],
                        query,
                        limit,
                    )
                )
                results["prompts"] = (
                    await api_context.dependencies.database_prompts.search_prompt_titles(
                        current_user["id"],
                        query,
                        limit,
                    )
                )
            else:
                results["conversations"] = []
                results["prompts"] = []
            return SearchResults.model_validate(results)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="Global search failed",
                operation=OPERATION,
                trace_id=request.state.context.trace_id,
                details={"query": query},
            )
            raise_server_error(request, "An error occurred during search.")

"""SoAI - Conversation-scoped SoAI path link routes [backend/features/api/routes/webui/soai_links_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, Request, status
from fastapi.responses import JSONResponse
from pydantic import Field

from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.meta.soai_v1 import SoAIV1StrictModel
from core.state.access import AccessAction
from core.workspaces.soai_path_link_codec import extract_soai_path_tokens
from features.api.routes.file_explorer.route_execution import (
    execute_file_explorer_route_json,
)
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.conversation_access import require_conversation_access
from features.api.runtime.conversation_workspace_scope import (
    build_conversation_workspace_scope,
)
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_server_error
from features.api.runtime.soai_links.resolution import resolve_soai_path_draft_token

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("register_routes",)

LOGGER_NAME = "SoAI.features.api.soai_links_routes"
OPERATION = "webui.soai_links.resolve"
RESOLVE_MAX_TOKENS_KEY = "SERVER.WEBUI.SOAI_LINKS.RESOLVE_MAX_TOKENS"
RESOLVE_MAX_DISTINCT_PATHS_KEY = "SERVER.WEBUI.SOAI_LINKS.RESOLVE_MAX_DISTINCT_PATHS"
RESOLVE_CONCURRENT_REQUESTS_KEY = (
    "SERVER.WEBUI.SOAI_LINKS.RESOLVE_CONCURRENT_REQUESTS_PER_CONVERSATION"
)


class SoaiLinksResolveRequest(SoAIV1StrictModel):
    raw_text: str = Field(max_length=262144)


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.post(
        "/conversations/{conv_id}/soai-links/resolve",
        status_code=status.HTTP_200_OK,
        dependencies=require_action_dependencies(AccessAction.FILE_EXPLORER_READ),
    )
    async def resolve_soai_links(
        request: Request,
        conv_id: str,
        body: SoaiLinksResolveRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        logger = get_logger(LOGGER_NAME)
        conversation_record = await require_conversation_access(
            request,
            api_context=api_context,
            conv_id=conv_id,
            user_id=current_user["id"],
        )
        if api_context.dependencies.file_explorer_core is None:
            raise_server_error(request, "File explorer service is not available.")

        async def run() -> JSONDict:
            concurrency_limit = api_context.dependencies.config.get_int(
                RESOLVE_CONCURRENT_REQUESTS_KEY,
            )
            scope = build_conversation_workspace_scope(
                current_user=current_user,
                conversation_record=conversation_record,
                api_context=api_context,
            )
            tokens = extract_soai_path_tokens(body.raw_text)
            max_tokens = api_context.dependencies.config.get_int(RESOLVE_MAX_TOKENS_KEY)
            max_distinct = api_context.dependencies.config.get_int(RESOLVE_MAX_DISTINCT_PATHS_KEY)
            if len(tokens) > max_tokens:
                raise ValidationError("SoAI link resolve request contains too many tokens.")
            distinct_paths = {token.virtual_path for token in tokens}
            if len(distinct_paths) > max_distinct:
                raise ValidationError("SoAI link resolve request contains too many distinct paths.")
            async with api_context.dependencies.soai_link_resolve_limiter.limit(
                key=(current_user["id"], conv_id),
                maximum=concurrency_limit,
            ):
                records: list[JSONDict] = []
                content_part_by_token_path: dict[str, JSONDict] = {}
                for token in tokens:
                    if await request.is_disconnected():
                        raise ValidationError("SoAI link resolve request was cancelled.")
                    cached_content_part = content_part_by_token_path.get(token.virtual_path)
                    if cached_content_part is None:
                        record = resolve_soai_path_draft_token(scope=scope, token=token)
                        content_part = record.get("content_part")
                        if not isinstance(content_part, dict):
                            raise ValidationError(
                                "SoAI link resolver returned an invalid content part.",
                            )
                        content_part_by_token_path[token.virtual_path] = dict(content_part)
                        records.append(record)
                        continue
                    records.append(
                        {
                            "token": token.token,
                            "occurrence_index": token.occurrence_index,
                            "display_label": token.label,
                            "content_part": dict(cached_content_part),
                        },
                    )
                return {"records": records, "token_count": len(records)}

        return await execute_file_explorer_route_json(
            request=request,
            run=run,
            logger=logger,
            recoverable_coerce_operation=OPERATION,
            operation=OPERATION,
            recoverable_log_message="SoAI link resolution failed",
            server_error_message="Resolution failed.",
            handle_validation_error=True,
        )

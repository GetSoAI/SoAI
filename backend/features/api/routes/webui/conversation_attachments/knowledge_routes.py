"""SoAI - WebUI conversation knowledge attachment routes [backend/features/api/routes/webui/conversation_attachments/knowledge_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Query, Request
from starlette.responses import JSONResponse, Response

from core.attachments.knowledge_attachment_statuses import KNOWLEDGE_ITEM_STATUSES
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ConflictError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from features.api.routes.webui.conversation_attachments.knowledge_contracts import (
    KnowledgeAttachmentClaimRequest,
    KnowledgeAttachmentItemsRequest,
)
from features.api.routes.webui.conversation_attachments.route_errors import (
    raise_attachment_route_error,
)
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import (
    ApiContext,
    get_request_trace_id,
    resolve_api_context,
)
from features.api.runtime.conversation_access import require_conversation_access_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_invalid_request, raise_not_found

__all__ = ("register_knowledge_attachment_routes",)

LOGGER_NAME = "SoAI.features.api.knowledge_routes"
OPERATION_WEBUI_KNOWLEDGE_ATTACHMENT_ROUTE = "webui.conversation_attachments.knowledge_route"
KNOWLEDGE_ATTACHMENT_ROUTE_ERROR_MESSAGE = "Conversation knowledge attachment route failed."


def _validate_items_query(
    *,
    cursor_item_index: int | None,
    cursor_id: int | None,
    status: str | None,
    query: str | None,
) -> tuple[str | None, str | None]:
    if (cursor_item_index is None) != (cursor_id is None):
        raise ValidationError("cursor_item_index and cursor_id must be provided together.")
    normalized_status = status.strip().lower() if isinstance(status, str) else None
    if normalized_status is not None and normalized_status not in KNOWLEDGE_ITEM_STATUSES:
        raise ValidationError("status is not a supported knowledge item status.")
    normalized_query = query.strip() if isinstance(query, str) and query.strip() else None
    if normalized_query is not None and len(normalized_query) > 256:
        raise ValidationError("query is too long.")
    return normalized_status, normalized_query


async def _knowledge_attachment_items_response(
    *,
    request: Request,
    conv_id: str,
    knowledge_attachment_id: str,
    limit: int,
    cursor_item_index: int | None,
    cursor_id: int | None,
    status: str | None,
    query: str | None,
    current_user: CurrentUser,
    api_context: ApiContext,
) -> Response:
    try:
        normalized_status, normalized_query = _validate_items_query(
            cursor_item_index=cursor_item_index,
            cursor_id=cursor_id,
            status=status,
            query=query,
        )
    except ValidationError as exception:
        raise_invalid_request(request, str(exception))
    conversation_context = await require_conversation_access_context(
        request,
        api_context=api_context,
        conv_id=conv_id,
        user_id=current_user["id"],
    )
    page = await api_context.dependencies.database_conversation_knowledge_attachments.get_knowledge_attachment_items_page(
        conv_id=conversation_context.resolved_conv_id,
        user_id=current_user["id"],
        knowledge_attachment_id=knowledge_attachment_id,
        limit=limit,
        cursor_item_index=cursor_item_index,
        cursor_id=cursor_id,
        status=normalized_status,
        query=normalized_query,
    )
    if page is None:
        raise_not_found(request, "Knowledge attachment not found.")
    return JSONResponse(content=page)


def register_knowledge_attachment_routes(routers: ApiRouters) -> None:
    @routers.webui.get("/conversations/{conv_id}/knowledge-attachments/draft")
    async def list_draft_knowledge_attachments(
        request: Request,
        conv_id: str,
        preview_limit: int = Query(6, ge=0, le=20),
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        conversation_context = await require_conversation_access_context(
            request,
            api_context=api_context,
            conv_id=conv_id,
            user_id=current_user["id"],
        )
        items = await api_context.dependencies.database_conversation_knowledge_attachments.list_draft_knowledge_attachments(
            conv_id=conversation_context.resolved_conv_id,
            user_id=current_user["id"],
            preview_limit=preview_limit,
        )
        return JSONResponse(content={"items": items})

    @routers.webui.post("/conversations/{conv_id}/knowledge-attachments/claim")
    async def claim_knowledge_attachments(
        request: Request,
        conv_id: str,
        body: KnowledgeAttachmentClaimRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        try:
            conversation_context = await require_conversation_access_context(
                request,
                api_context=api_context,
                conv_id=conv_id,
                user_id=current_user["id"],
            )
            content_parts = await api_context.dependencies.database_conversation_knowledge_attachments.claim_knowledge_attachments(
                conv_id=conversation_context.resolved_conv_id,
                user_id=current_user["id"],
                selections=[
                    (selection.knowledge_attachment_id, selection.attachment_revision)
                    for selection in body.selections
                ],
            )
            return JSONResponse(content={"content_parts": content_parts})
        except (ConflictError, ValidationError) as exception:
            raise_attachment_route_error(request, exception)
        except RECOVERABLE_EXCEPTIONS as exception:
            logger = get_logger(LOGGER_NAME)
            log_exception(
                logger,
                exception,
                message=KNOWLEDGE_ATTACHMENT_ROUTE_ERROR_MESSAGE,
                operation=OPERATION_WEBUI_KNOWLEDGE_ATTACHMENT_ROUTE,
                trace_id=get_request_trace_id(request),
            )
            raise_attachment_route_error(request, exception, already_logged=True)

    @routers.webui.get("/conversations/{conv_id}/knowledge-attachments/{knowledge_attachment_id}")
    async def get_knowledge_attachment(
        request: Request,
        conv_id: str,
        knowledge_attachment_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        user_id = current_user["id"]
        conversation_context = await require_conversation_access_context(
            request,
            api_context=api_context,
            conv_id=conv_id,
            user_id=user_id,
        )
        summary = await api_context.dependencies.database_conversation_knowledge_attachments.get_knowledge_attachment(
            conv_id=conversation_context.resolved_conv_id,
            user_id=user_id,
            knowledge_attachment_id=knowledge_attachment_id,
        )
        if summary is None:
            raise_not_found(request, "Knowledge attachment not found.")
        return JSONResponse(content=summary)

    @routers.webui.get(
        "/conversations/{conv_id}/knowledge-attachments/{knowledge_attachment_id}/items",
    )
    async def list_knowledge_attachment_items(
        request: Request,
        conv_id: str,
        knowledge_attachment_id: str,
        limit: int = Query(50, ge=1, le=200),
        cursor_item_index: int | None = Query(None, ge=0),
        cursor_id: int | None = Query(None, ge=1),
        status: str | None = Query(None),
        query: str | None = Query(None),
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        return await _knowledge_attachment_items_response(
            request=request,
            conv_id=conv_id,
            knowledge_attachment_id=knowledge_attachment_id,
            limit=limit,
            cursor_item_index=cursor_item_index,
            cursor_id=cursor_id,
            status=status,
            query=query,
            current_user=current_user,
            api_context=api_context,
        )

    @routers.webui.post(
        "/conversations/{conv_id}/knowledge-attachments/{knowledge_attachment_id}/items/query",
    )
    async def query_knowledge_attachment_items(
        request: Request,
        conv_id: str,
        knowledge_attachment_id: str,
        body: KnowledgeAttachmentItemsRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        return await _knowledge_attachment_items_response(
            request=request,
            conv_id=conv_id,
            knowledge_attachment_id=knowledge_attachment_id,
            limit=body.limit,
            cursor_item_index=body.cursor_item_index,
            cursor_id=body.cursor_id,
            status=body.status,
            query=body.query,
            current_user=current_user,
            api_context=api_context,
        )

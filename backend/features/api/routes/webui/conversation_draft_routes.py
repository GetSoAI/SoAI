"""SoAI - HTTP endpoints for conversation composer drafts [backend/features/api/routes/webui/conversation_draft_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from starlette.responses import JSONResponse, Response

from core.errors.exceptions import ConcurrencyError, ConflictError, ValidationError
from core.logging.trace import get_logger
from core.timing.epoch import epoch_ms
from features.api.routes.webui.conversation_draft_events import (
    publish_conversation_draft_changed,
)
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.conversation_access import require_conversation_access_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_conflict, raise_invalid_request
from features.api.schemas.conversation_draft import ConversationDraftSaveRequest

__all__ = (
    "delete_conversation_draft",
    "get_conversation_draft",
    "put_conversation_draft",
    "register_endpoints",
    "register_routes",
)

LOGGER_NAME = "SoAI.features.api.conversation_draft_routes"


def _log_dropped_draft_attachments(conv_id: str, dropped_count: int) -> None:
    if dropped_count <= 0:
        return
    get_logger(LOGGER_NAME).info(
        "Dropped unrestorable conversation draft attachments.",
        extra={"conv_id": conv_id, "dropped_attachment_count": int(dropped_count)},
    )


async def get_conversation_draft(
    request: Request,
    conv_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    conversation_context = await require_conversation_access_context(
        request,
        api_context=api_context,
        conv_id=conv_id,
        user_id=current_user["id"],
    )
    state = await api_context.dependencies.database_conversation_drafts.get_draft(
        conv_id=conversation_context.resolved_conv_id,
        user_id=current_user["id"],
    )
    if state.draft is not None:
        dropped_count = state.draft.get("dropped_attachment_count")
        if isinstance(dropped_count, int):
            _log_dropped_draft_attachments(conversation_context.resolved_conv_id, dropped_count)
    return JSONResponse(content={"draft": state.draft, "revision": state.revision})


async def put_conversation_draft(
    request: Request,
    conv_id: str,
    payload: ConversationDraftSaveRequest,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    conversation_context = await require_conversation_access_context(
        request,
        api_context=api_context,
        conv_id=conv_id,
        user_id=current_user["id"],
    )
    try:
        result = await api_context.dependencies.database_conversation_drafts.save_draft(
            conv_id=conversation_context.resolved_conv_id,
            user_id=current_user["id"],
            text=payload.text or "",
            source_text=payload.source_text,
            attachment_content=payload.attachment_content,
            client_id=payload.client_id,
            client_sequence=payload.client_sequence,
            base_revision=payload.base_revision,
        )
    except ValidationError as exception:
        raise_invalid_request(request, str(exception))
    except ConflictError as exception:
        raise_conflict(request, str(exception))
    except ConcurrencyError as exception:
        raise_conflict(
            request,
            str(exception),
            error_type="conversation_draft_revision_conflict",
            extra=dict(exception.details or {}),
        )
    draft = result.state.draft
    if result.applied:
        updated_at_ms = draft.get("updated_at_ms") if draft is not None else None
        await publish_conversation_draft_changed(
            api_context=api_context,
            user_id=current_user["id"],
            conv_id=conversation_context.resolved_conv_id,
            client_id=payload.client_id,
            updated_at_ms=updated_at_ms if isinstance(updated_at_ms, int) else epoch_ms(),
            deleted=False,
            revision=result.state.revision,
        )
    return JSONResponse(content={"draft": draft, "revision": result.state.revision})


async def delete_conversation_draft(
    request: Request,
    conv_id: str,
    client_id: str = Query(..., min_length=1, max_length=128),
    client_sequence: int = Query(..., ge=0),
    base_revision: int = Query(..., ge=0),
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    conversation_context = await require_conversation_access_context(
        request,
        api_context=api_context,
        conv_id=conv_id,
        user_id=current_user["id"],
    )
    try:
        result = await api_context.dependencies.database_conversation_drafts.delete_draft(
            conv_id=conversation_context.resolved_conv_id,
            user_id=current_user["id"],
            client_id=client_id,
            client_sequence=client_sequence,
            base_revision=base_revision,
        )
    except ConflictError as exception:
        raise_conflict(request, str(exception))
    except ConcurrencyError as exception:
        raise_conflict(
            request,
            str(exception),
            error_type="conversation_draft_revision_conflict",
            extra=dict(exception.details or {}),
        )
    if result.applied:
        await publish_conversation_draft_changed(
            api_context=api_context,
            user_id=current_user["id"],
            conv_id=conversation_context.resolved_conv_id,
            client_id=client_id,
            updated_at_ms=epoch_ms(),
            deleted=True,
            revision=result.state.revision,
        )
    return JSONResponse(content={"draft": result.state.draft, "revision": result.state.revision})


def register_endpoints(router: APIRouter) -> None:
    router.get("/conversations/{conv_id}/draft")(get_conversation_draft)
    router.put("/conversations/{conv_id}/draft")(put_conversation_draft)
    router.delete("/conversations/{conv_id}/draft")(delete_conversation_draft)


def register_routes(routers: ApiRouters) -> None:
    register_endpoints(routers.webui)

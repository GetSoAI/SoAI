"""SoAI - HTTP endpoints for conversation input queue [backend/features/api/routes/webui/conversation_input_queue_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request
from starlette.responses import JSONResponse, Response

from core.conversations.conversation_model_settings_resolution import (
    resolve_conversation_model_settings,
)
from core.conversations.settings_authority import resolve_conversation_settings_authority
from core.errors.exceptions import (
    CONVERSATION_INPUT_NOT_CANCELLABLE_CODE,
    ConflictError,
    ConversationInputNotCancellableError,
    StateError,
    ValidationError,
)
from core.validation.integers import is_non_negative_strict_int
from features.api.routes.webui.conversation_input_queue_events import (
    publish_current_input_queue_changed,
)
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.conversation_access import require_conversation_access_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_conflict, raise_invalid_request
from features.api.runtime.responses import create_no_content_response
from features.api.runtime.soai_links.input_queue_finalization import (
    finalize_input_queue_soai_links,
)
from features.api.schemas.input_queue import InputQueueEnqueueRequest

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "delete_input_queue_item",
    "enqueue_input_queue_item",
    "list_input_queue_items",
    "register_endpoints",
    "register_routes",
)


async def _apply_input_queue_change_and_publish(
    request: Request,
    *,
    api_context: ApiContext,
    conv_id: str,
    user_id: int,
    operation: Callable[[], Awaitable[JSONDict]],
) -> JSONDict:
    try:
        result = await operation()
    except ValidationError as exception:
        raise_invalid_request(request, str(exception))
    except ConversationInputNotCancellableError as exception:
        raise_conflict(
            request,
            str(exception),
            error_type=CONVERSATION_INPUT_NOT_CANCELLABLE_CODE,
            extra=dict(exception.details) if exception.details is not None else None,
        )
    except ConflictError as exception:
        raise_conflict(request, str(exception))
    await publish_current_input_queue_changed(
        api_dependencies=api_context.dependencies,
        user_id=user_id,
        conv_id=conv_id,
    )
    return result


async def list_input_queue_items(
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
    inputs = await api_context.dependencies.database_input_queue.list_active_inputs(
        conv_id=conversation_context.resolved_conv_id,
        user_id=current_user["id"],
    )
    return JSONResponse(content={"items": inputs})


async def enqueue_input_queue_item(
    request: Request,
    conv_id: str,
    payload: InputQueueEnqueueRequest,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    conversation_context = await require_conversation_access_context(
        request,
        api_context=api_context,
        conv_id=conv_id,
        user_id=current_user["id"],
    )
    finalized_text, finalized_attachment_content = await finalize_input_queue_soai_links(
        text=payload.text,
        attachment_content=payload.attachment_content,
        current_user=current_user,
        conversation_record=conversation_context.record,
        api_context=api_context,
    )
    authority = resolve_conversation_settings_authority(conversation_context.record)
    effective_settings = await resolve_conversation_model_settings(
        user_id=current_user["id"],
        model_settings_snapshot=authority.model_settings,
        database_chat_identity_defaults=(api_context.dependencies.database_chat_identity_defaults),
        database_chat_model_defaults=api_context.dependencies.database_chat_model_defaults,
    )
    input_generation = conversation_context.record.get("input_generation")
    if not is_non_negative_strict_int(input_generation):
        raise StateError("Conversation input_generation is invalid.")
    created = await _apply_input_queue_change_and_publish(
        request,
        api_context=api_context,
        conv_id=conversation_context.resolved_conv_id,
        user_id=current_user["id"],
        operation=lambda: api_context.dependencies.database_input_queue.enqueue_input(
            conv_id=conversation_context.resolved_conv_id,
            user_id=current_user["id"],
            input_type=payload.input_type,
            transport_origin="chat",
            text=finalized_text,
            prompt_history_text=payload.prompt_history_text,
            attachment_content=finalized_attachment_content,
            model_settings=(effective_settings if payload.input_type == "prompt" else None),
            expected_input_generation=input_generation,
            client_id=payload.client_id,
            client_request_id=payload.client_request_id,
        ),
    )
    return JSONResponse(content=created, status_code=201)


async def delete_input_queue_item(
    request: Request,
    conv_id: str,
    item_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    conversation_context = await require_conversation_access_context(
        request,
        api_context=api_context,
        conv_id=conv_id,
        user_id=current_user["id"],
    )
    await _apply_input_queue_change_and_publish(
        request,
        api_context=api_context,
        conv_id=conversation_context.resolved_conv_id,
        user_id=current_user["id"],
        operation=lambda: api_context.dependencies.database_input_queue.cancel_input(
            conv_id=conversation_context.resolved_conv_id,
            user_id=current_user["id"],
            input_id=item_id,
        ),
    )
    return create_no_content_response()


def register_endpoints(router: APIRouter) -> None:
    router.get("/conversations/{conv_id}/input-queue")(list_input_queue_items)
    router.post(
        "/conversations/{conv_id}/input-queue",
        status_code=201,
    )(enqueue_input_queue_item)
    router.delete(
        "/conversations/{conv_id}/input-queue/{item_id}",
        status_code=204,
    )(delete_input_queue_item)


def register_routes(routers: ApiRouters) -> None:
    register_endpoints(routers.webui)

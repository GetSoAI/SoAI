"""SoAI - HTTP endpoints for writing conversation messages [backend/features/api/routes/webui/conversation_message_write_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from starlette.responses import JSONResponse, Response

from core.errors.exceptions import ConflictError, ValidationError
from core.events.conversation_publication import (
    publish_conversation_updated_and_message_saved,
)
from core.types.json import JSONDict
from features.api.routes.webui.conversation_message_write_outputs import (
    publish_message_write_knowledge_events,
    serialize_message_write_result,
)
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import (
    raise_conflict,
    raise_invalid_request,
    raise_not_found,
)
from features.api.runtime.soai_links.message_finalization import (
    finalize_soai_links_in_messages,
)
from features.api.runtime.webui_records import webui_fetch_or_404
from features.api.schemas.conversations import (
    MessageCursorMutationRequest,
    MessageResubmitRequest,
    MessagesUpdateRequest,
)

__all__ = ("register_routes",)


async def _publish_write_result(
    api_context: ApiContext,
    *,
    user_id: int,
    conv_id: str,
    message_count: int,
    last_modified_at_ms: int,
) -> None:
    await publish_conversation_updated_and_message_saved(
        api_context.dependencies.event_bus,
        user_id=user_id,
        conv_id=conv_id,
        message_count=message_count,
        last_modified_at_ms=last_modified_at_ms,
    )


async def _load_conversation_record(
    request: Request,
    api_context: ApiContext,
    *,
    conv_id: str,
    user_id: int,
) -> JSONDict:
    return await webui_fetch_or_404(
        request,
        api_context.dependencies.database_conversations.get_conversation(
            conv_id,
            user_id,
        ),
        message="Conversation not found or you do not have permission to access it.",
    )


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.put("/conversations/{conv_id}/messages")
    async def update_conversation_messages(
        request: Request,
        conv_id: str,
        payload: MessagesUpdateRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        api_context.dependencies.metrics_manager.increment_counter(
            "api",
            "webui",
            "conversation_messages_updated",
        )
        try:
            conversation_record = await _load_conversation_record(
                request,
                api_context,
                conv_id=conv_id,
                user_id=current_user["id"],
            )
            serialized_messages = await finalize_soai_links_in_messages(
                messages=[message.model_dump(exclude_none=True) for message in payload.messages],
                current_user=current_user,
                conversation_record=conversation_record,
                api_context=api_context,
            )
            write_result = await api_context.dependencies.database_messages.overwrite_messages(
                conv_id,
                current_user["id"],
                serialized_messages,
                payload.expected_last_modified_at_ms,
            )
        except ConflictError as exception:
            raise_conflict(request, str(exception))
        except ValidationError as exception:
            raise_invalid_request(request, str(exception))
        except ValueError as exception:
            raise_not_found(request, str(exception))
        await _publish_write_result(
            api_context,
            user_id=current_user["id"],
            conv_id=conv_id,
            message_count=write_result.message_count,
            last_modified_at_ms=write_result.last_modified_at_ms,
        )
        await publish_message_write_knowledge_events(api_context, write_result)
        return JSONResponse(content=serialize_message_write_result(write_result))

    @routers.webui.post("/conversations/{conv_id}/messages")
    async def append_conversation_messages(
        request: Request,
        conv_id: str,
        payload: MessagesUpdateRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        try:
            conversation_record = await _load_conversation_record(
                request,
                api_context,
                conv_id=conv_id,
                user_id=current_user["id"],
            )
            serialized_messages = await finalize_soai_links_in_messages(
                messages=[message.model_dump(exclude_none=True) for message in payload.messages],
                current_user=current_user,
                conversation_record=conversation_record,
                api_context=api_context,
            )
            write_result = await api_context.dependencies.database_messages.append_messages(
                conv_id,
                current_user["id"],
                serialized_messages,
                payload.expected_last_modified_at_ms,
            )
        except ConflictError as exception:
            raise_conflict(request, str(exception))
        except ValidationError as exception:
            raise_invalid_request(request, str(exception))
        if serialized_messages:
            api_context.dependencies.metrics_manager.increment_counter(
                "api",
                "webui",
                "chat_messages_sent",
                value=len(serialized_messages),
            )
            await _publish_write_result(
                api_context,
                user_id=current_user["id"],
                conv_id=conv_id,
                message_count=write_result.message_count,
                last_modified_at_ms=write_result.last_modified_at_ms,
            )
            await publish_message_write_knowledge_events(api_context, write_result)
        return JSONResponse(content=serialize_message_write_result(write_result))

    @routers.webui.post("/conversations/{conv_id}/messages/resubmit")
    async def resubmit_conversation_user_message(
        request: Request,
        conv_id: str,
        payload: MessageResubmitRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        try:
            conversation_record = await _load_conversation_record(
                request,
                api_context,
                conv_id=conv_id,
                user_id=current_user["id"],
            )
            messages = await finalize_soai_links_in_messages(
                messages=[payload.message.model_dump(exclude_none=True)],
                current_user=current_user,
                conversation_record=conversation_record,
                api_context=api_context,
            )
            write_result = (
                await api_context.dependencies.database_messages.resubmit_user_message_by_cursor(
                    conv_id,
                    current_user["id"],
                    created_at_ms=payload.created_at_ms,
                    message_id=payload.message_id,
                    message=messages[0],
                    expected_last_modified_at_ms=payload.expected_last_modified_at_ms,
                )
            )
        except ConflictError as exception:
            raise_conflict(request, str(exception))
        except ValidationError as exception:
            raise_invalid_request(request, str(exception))
        await _publish_write_result(
            api_context,
            user_id=current_user["id"],
            conv_id=conv_id,
            message_count=write_result.message_count,
            last_modified_at_ms=write_result.last_modified_at_ms,
        )
        await publish_message_write_knowledge_events(api_context, write_result)
        return JSONResponse(content=serialize_message_write_result(write_result))

    @routers.webui.post("/conversations/{conv_id}/messages/truncate")
    async def truncate_conversation_messages(
        request: Request,
        conv_id: str,
        payload: MessageCursorMutationRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        try:
            await _load_conversation_record(
                request,
                api_context,
                conv_id=conv_id,
                user_id=current_user["id"],
            )
            write_result = (
                await api_context.dependencies.database_messages.truncate_messages_from_cursor(
                    conv_id,
                    current_user["id"],
                    created_at_ms=payload.created_at_ms,
                    message_id=payload.message_id,
                    expected_last_modified_at_ms=payload.expected_last_modified_at_ms,
                )
            )
        except ConflictError as exception:
            raise_conflict(request, str(exception))
        except ValidationError as exception:
            raise_invalid_request(request, str(exception))
        await _publish_write_result(
            api_context,
            user_id=current_user["id"],
            conv_id=conv_id,
            message_count=write_result.message_count,
            last_modified_at_ms=write_result.last_modified_at_ms,
        )
        return JSONResponse(content=serialize_message_write_result(write_result))

    @routers.webui.post("/conversations/{conv_id}/messages/delete")
    async def delete_conversation_message(
        request: Request,
        conv_id: str,
        payload: MessageCursorMutationRequest,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        try:
            await _load_conversation_record(
                request,
                api_context,
                conv_id=conv_id,
                user_id=current_user["id"],
            )
            write_result = (
                await api_context.dependencies.database_messages.delete_message_by_cursor(
                    conv_id,
                    current_user["id"],
                    created_at_ms=payload.created_at_ms,
                    message_id=payload.message_id,
                    expected_last_modified_at_ms=payload.expected_last_modified_at_ms,
                )
            )
        except ConflictError as exception:
            raise_conflict(request, str(exception))
        except ValidationError as exception:
            raise_invalid_request(request, str(exception))
        await _publish_write_result(
            api_context,
            user_id=current_user["id"],
            conv_id=conv_id,
            message_count=write_result.message_count,
            last_modified_at_ms=write_result.last_modified_at_ms,
        )
        return JSONResponse(content=serialize_message_write_result(write_result))

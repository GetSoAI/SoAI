"""SoAI - HTTP endpoints for listing and creating conversations [backend/features/api/routes/webui/conversation_list_create_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from core.chat.conversation_defaults import (
    read_chat_conversation_defaults_model_settings,
    read_chat_conversation_defaults_rag_config,
    read_chat_new_conversation_inherit_last_settings_enabled,
)
from core.conversations.conversation_model_settings_resolution import (
    resolve_conversation_model_settings,
)
from core.database.requests import UpdateRAGConfigRequest
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ConflictError, StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.conversation_publication import publish_conversation_created
from core.logging.trace import get_context_trace_id, get_logger
from features.api.routes.webui.conversation_rag.config.normalization import (
    build_normalized_rag_config_update_fields,
)
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.conversation_settings_projection import (
    project_effective_conversation_settings,
)
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_conflict
from features.api.runtime.model_settings_mcp import (
    normalize_model_settings_mcp,
)
from features.api.runtime.validation import (
    require_bool_value,
    require_field,
    require_optional_str_value,
    require_str_value,
    require_unix_timestamp_ms,
)
from features.api.schemas.conversations import ConversationCreate

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("register_routes",)

LOGGER_NAME = "SoAI.features.api.conversation_list_create_routes"
OPERATION_APPLY_RAG_DEFAULTS = "api_webui.conversations.create.apply_rag_defaults"


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.get("/conversations")
    async def list_my_conversations(
        request: Request,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        conversations = (
            await api_context.dependencies.webui_manager.database_conversations.list_conversations(
                current_user["id"],
            )
        )
        normalized_conversations: list[JSONDict] = []
        for conversation in conversations:
            if not isinstance(conversation, dict):
                raise ValidationError("Conversation record must be an object.")
            normalized = project_effective_conversation_settings(
                request=request,
                config=api_context.dependencies.config,
                conversation_record=conversation,
            )
            normalized_conversations.append(normalized)
        return JSONResponse(content=normalized_conversations)

    @routers.webui.post("/conversations", status_code=201)
    async def create_new_conversation(
        request: Request,
        payload: ConversationCreate,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        api_context.dependencies.metrics_manager.increment_counter(
            "api",
            "webui",
            "conversations_created",
        )
        user_prefs_value = await api_context.dependencies.database_users.get_user_preferences(
            current_user["id"]
        )
        inherit_last_used = read_chat_new_conversation_inherit_last_settings_enabled(
            user_prefs_value,
        )
        defaults_model_settings = (
            read_chat_conversation_defaults_model_settings(user_prefs_value)
            if inherit_last_used
            else None
        )
        defaults_rag_config = (
            read_chat_conversation_defaults_rag_config(user_prefs_value)
            if inherit_last_used
            else None
        )
        normalized_defaults_rag_updates = (
            build_normalized_rag_config_update_fields(defaults_rag_config)
            if defaults_rag_config is not None
            else None
        )
        model_settings_payload = normalize_model_settings_mcp(
            request,
            defaults_model_settings or {},
        )
        database_chat_identity_defaults = api_context.dependencies.database_chat_identity_defaults
        database_chat_model_defaults = api_context.dependencies.database_chat_model_defaults
        model_settings_payload = await resolve_conversation_model_settings(
            user_id=current_user["id"],
            model_settings_snapshot=model_settings_payload,
            database_chat_identity_defaults=database_chat_identity_defaults,
            database_chat_model_defaults=database_chat_model_defaults,
        )
        try:
            database_conversations = api_context.dependencies.webui_manager.database_conversations
            conversation_record = await database_conversations.create_conversation(
                current_user["id"],
                payload.title,
                model_settings_payload,
                False,
                payload.id,
            )
        except ConflictError as exception:
            raise_conflict(request, str(exception))
        conv_id_value = require_str_value(
            request,
            require_field(request, conversation_record, "id"),
            message="Conversation field 'id' must be a string.",
        )
        require_str_value(
            request,
            require_field(request, conversation_record, "title"),
            message="Conversation field 'title' must be a string.",
        )
        require_unix_timestamp_ms(
            request,
            require_field(request, conversation_record, "created_at_ms"),
            field="created_at_ms",
        )
        require_unix_timestamp_ms(
            request,
            require_field(request, conversation_record, "last_modified_at_ms"),
            field="last_modified_at_ms",
        )
        require_bool_value(
            request,
            conversation_record.get("is_favorite", False),
            field="is_favorite",
        )
        require_optional_str_value(request, conversation_record.get("color"), field="color")
        if normalized_defaults_rag_updates and any(
            value is not None for value in normalized_defaults_rag_updates.values()
        ):
            try:
                await api_context.dependencies.database_files.update_rag_config(
                    UpdateRAGConfigRequest(
                        conv_id=conv_id_value,
                        enabled=normalized_defaults_rag_updates["enabled"],
                        retrieval_strategy=normalized_defaults_rag_updates["retrieval_strategy"],
                        top_k=normalized_defaults_rag_updates["top_k"],
                        similarity_threshold=normalized_defaults_rag_updates[
                            "similarity_threshold"
                        ],
                        chunking_strategy=normalized_defaults_rag_updates["chunking_strategy"],
                        chunk_size=normalized_defaults_rag_updates["chunk_size"],
                        chunk_overlap=normalized_defaults_rag_updates["chunk_overlap"],
                        embedding_model=normalized_defaults_rag_updates["embedding_model"],
                    ),
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                try:
                    context = request.state.context
                except AttributeError:
                    context = None
                trace_id = get_context_trace_id(context)
                coerced = coerce_to_soai_error(
                    exception,
                    operation=OPERATION_APPLY_RAG_DEFAULTS,
                )
                log_exception(
                    get_logger(LOGGER_NAME),
                    coerced,
                    message="Failed to apply conversation RAG defaults; rolling back conversation.",
                    operation=OPERATION_APPLY_RAG_DEFAULTS,
                    trace_id=trace_id,
                    details={"conv_id": conv_id_value},
                )
                deleted_record = (
                    await api_context.dependencies.database_conversations.delete_conversation(
                        conv_id_value,
                        current_user["id"],
                    )
                )
                if deleted_record is None:
                    raise StateError(
                        "Failed to roll back conversation after applying RAG defaults failed.",
                    ) from coerced
                raise coerced from exception
        await publish_conversation_created(
            api_context.dependencies.event_bus,
            user_id=current_user["id"],
            conversation_record=conversation_record,
        )
        return JSONResponse(
            content=project_effective_conversation_settings(
                request=request,
                config=api_context.dependencies.config,
                conversation_record=conversation_record,
            ),
            status_code=201,
        )

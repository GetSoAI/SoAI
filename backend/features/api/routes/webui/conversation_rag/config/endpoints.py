"""SoAI - WebUI conversation RAG endpoint handlers [backend/features/api/routes/webui/conversation_rag/config/endpoints.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from core.database.requests import UpdateRAGConfigRequest, UpdateRAGConfigWithDefaultsRequest
from core.errors.exceptions import StateError, ValidationError
from core.files.database_types import RAGConversationConfigRecord
from core.mcp.protocols_rag import MCPRAGProtocol
from core.mcp.schema import AUTO_EMBEDDING_MODEL_SELECTOR
from core.rag.parameter_validation import validate_chunking_window
from core.rag.preferences import (
    read_chat_default_embedding_model,
)
from core.state.access import AccessAction
from core.types.json_value import coerce_json_dict
from core.validation.strings import coerce_optional_trimmed_str
from features.api.routes.webui.conversation_rag.config.normalization import (
    build_normalized_rag_config_response,
    build_normalized_rag_config_update_fields,
)
from features.api.routes.webui.rag_config_models import (
    RAGConversationConfigResponse,
    RAGReindexResponse,
)
from features.api.routes.webui.rag_dependencies import require_rag_engine
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.errors import raise_invalid_request
from features.api.schemas.rag import RAGConfigUpdate

__all__ = (
    "get_rag_config",
    "register_endpoints",
    "reindex_rag",
    "update_rag_config",
)


def _format_rag_config_response(
    conv_id: str,
    rag: MCPRAGProtocol,
    config: RAGConversationConfigRecord | None,
    default_embedding_model: str = "",
) -> RAGConversationConfigResponse:
    response = build_normalized_rag_config_response(conv_id, rag, config)
    response["default_embedding_model"] = default_embedding_model or None
    return response


async def get_rag_config(
    request: Request,
    conv_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> RAGConversationConfigResponse:
    rag_engine = require_rag_engine(request, api_context)
    resolved_id = await rag_engine.resolve_conv_id_for_user(conv_id, current_user["id"])
    config = await api_context.dependencies.database_files.get_rag_config(resolved_id)
    prefs = await api_context.dependencies.database_users.get_user_preferences(current_user["id"])
    default_model = read_chat_default_embedding_model(prefs)
    response = _format_rag_config_response(
        resolved_id,
        rag_engine,
        config,
        default_model,
    )
    embedding_model = response.get("embedding_model")
    embedding_model_str = (
        coerce_optional_trimmed_str(embedding_model if isinstance(embedding_model, str) else None)
        or ""
    )
    if embedding_model_str == AUTO_EMBEDDING_MODEL_SELECTOR:
        embedding_model_str = ""
    auto_reference_available = False
    if embedding_model_str.lower() == "auto":
        auto_reference_available = await rag_engine.is_embedding_model_available("auto")
    treat_as_auto = not embedding_model_str or (
        embedding_model_str.lower() == "auto" and not auto_reference_available
    )
    if treat_as_auto:
        should_apply_default = bool(default_model)
        if default_model.lower() == "auto" and not auto_reference_available:
            should_apply_default = await rag_engine.is_embedding_model_available("auto")
        if should_apply_default:
            response["embedding_model"] = default_model
    return response


async def update_rag_config(
    request: Request,
    conv_id: str,
    payload: RAGConfigUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> RAGConversationConfigResponse:
    rag_engine = require_rag_engine(request, api_context)
    resolved_id = await rag_engine.resolve_conv_id_for_user(conv_id, current_user["id"])
    async with api_context.dependencies.conversation_agent_settings_locks.lock(
        (current_user["id"], resolved_id),
    ):
        return await _update_rag_config_locked(
            request=request,
            resolved_id=resolved_id,
            payload=payload,
            user_id=current_user["id"],
            api_context=api_context,
            rag_engine=rag_engine,
        )


async def _update_rag_config_locked(
    *,
    request: Request,
    resolved_id: str,
    payload: RAGConfigUpdate,
    user_id: int,
    api_context: ApiContext,
    rag_engine: MCPRAGProtocol,
) -> RAGConversationConfigResponse:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        config = await api_context.dependencies.database_files.get_rag_config(resolved_id)
        preferences = await api_context.dependencies.database_users.get_user_preferences(user_id)
        return _format_rag_config_response(
            resolved_id,
            rag_engine,
            config,
            read_chat_default_embedding_model(preferences),
        )
    embedding_model = updates.get("embedding_model")
    if embedding_model is not None:
        trimmed = coerce_optional_trimmed_str(
            embedding_model if isinstance(embedding_model, str) else None,
        )
        if trimmed is None:
            raise_invalid_request(request, "embedding_model must be a non-empty string or 'auto'.")
        if trimmed == AUTO_EMBEDDING_MODEL_SELECTOR:
            trimmed = await rag_engine.ensure_any_embedding_model_available()
        elif trimmed.lower() == "auto":
            if await rag_engine.is_embedding_model_available("auto"):
                await rag_engine.validate_and_resolve_embedding_model("auto")
                trimmed = "auto"
            else:
                trimmed = await rag_engine.ensure_any_embedding_model_available()
        else:
            await rag_engine.validate_and_resolve_embedding_model(trimmed)
        updates["embedding_model"] = trimmed
    normalized_updates = build_normalized_rag_config_update_fields(updates)
    current_config = await api_context.dependencies.database_files.get_rag_config(resolved_id)
    current_values = build_normalized_rag_config_response(
        resolved_id,
        rag_engine,
        current_config,
    )
    try:
        validate_chunking_window(
            chunk_size=normalized_updates["chunk_size"] or current_values["chunk_size"],
            chunk_overlap=(
                normalized_updates["chunk_overlap"]
                if normalized_updates["chunk_overlap"] is not None
                else current_values["chunk_overlap"]
            ),
            chunking_strategy=(
                normalized_updates["chunking_strategy"] or current_values["chunking_strategy"]
            ),
        )
    except ValidationError:
        raise_invalid_request(
            request, "chunk_overlap must be less than chunk_size for this chunking strategy."
        )
    commit = await api_context.dependencies.database_files.update_rag_config_with_defaults(
        UpdateRAGConfigWithDefaultsRequest(
            update=UpdateRAGConfigRequest(
                conv_id=resolved_id,
                enabled=normalized_updates["enabled"],
                retrieval_strategy=normalized_updates["retrieval_strategy"],
                top_k=normalized_updates["top_k"],
                similarity_threshold=normalized_updates["similarity_threshold"],
                chunking_strategy=normalized_updates["chunking_strategy"],
                chunk_size=normalized_updates["chunk_size"],
                chunk_overlap=normalized_updates["chunk_overlap"],
                embedding_model=normalized_updates["embedding_model"],
            ),
            user_id=user_id,
        )
    )
    if commit.preferences is None:
        raise StateError("RAG configuration commit did not return user preferences.")
    return _format_rag_config_response(
        resolved_id,
        rag_engine,
        commit.config,
        read_chat_default_embedding_model(commit.preferences),
    )


async def reindex_rag(
    request: Request,
    conv_id: str,
    embedding_model: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> RAGReindexResponse:
    rag_engine = require_rag_engine(request, api_context)
    resolved_id = await rag_engine.resolve_conv_id_for_user(conv_id, current_user["id"])
    model_id = coerce_optional_trimmed_str(embedding_model)
    if model_id is None:
        config = await api_context.dependencies.database_files.get_rag_config(resolved_id)
        normalized_config = _format_rag_config_response(resolved_id, rag_engine, config)
        config_model = normalized_config.get("embedding_model")
        model_id = coerce_optional_trimmed_str(
            config_model if isinstance(config_model, str) else None,
        )
    if model_id is None or model_id.lower() == "auto":
        raise_invalid_request(request, "embedding_model must be provided or set in the RAG config.")
    reindex_result = await rag_engine.reindex_conversation(
        resolved_id,
        current_user["id"],
        model_id,
    )
    task_id = coerce_optional_trimmed_str(
        reindex_result.get("task_id") if isinstance(reindex_result.get("task_id"), str) else None,
    )
    knowledge_attachment = coerce_json_dict(reindex_result.get("knowledge_attachment"))
    if task_id is None or knowledge_attachment is None:
        raise StateError("RAG reindex did not return a valid task payload.")
    return {
        "status": "queued",
        "task_id": task_id,
        "conv_id": resolved_id,
        "embedding_model": model_id,
        "knowledge_attachment": knowledge_attachment,
    }


def register_endpoints(router: APIRouter) -> None:
    router.get(
        "/conversations/{conv_id}/rag/config",
        dependencies=require_action_dependencies(AccessAction.RAG_USE),
    )(get_rag_config)
    router.patch(
        "/conversations/{conv_id}/rag/config",
        dependencies=require_action_dependencies(AccessAction.RAG_USE),
    )(update_rag_config)
    router.post(
        "/conversations/{conv_id}/rag/reindex",
        status_code=202,
        dependencies=require_action_dependencies(AccessAction.RAG_USE),
    )(reindex_rag)

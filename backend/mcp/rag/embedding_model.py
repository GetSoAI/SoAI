"""SoAI - MCP RAG embedding model resolution [backend/mcp/rag/embedding_model.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.database.requests import UpdateRAGConfigRequest, UpdateRAGConfigWithDefaultsRequest
from core.errors.exceptions import StateError, ValidationError
from core.mcp.schema import is_auto_embedding_model_sentinel
from core.rag.conversation_config import ensure_conversation_rag_enabled
from core.rag.preferences import read_chat_default_embedding_model
from core.validation.strings import coerce_optional_trimmed_str
from mcp.storage import embedding_model_resolution
from mcp.storage.embedding_model import validate_and_resolve_embedding_model
from mcp.storage.embedding_model_resolution import (
    ensure_any_embedding_model_available,
    resolve_embedding_model_for_embeddings_request,
)

if TYPE_CHECKING:
    from mcp.rag.internal_protocols import MCPRAGInternalProtocol

__all__ = (
    "ensure_any_embedding_model_available_with_cache",
    "is_embedding_model_available_with_cache",
    "persist_effective_embedding_model",
    "prepare_ingest_context",
    "ResolvedEmbeddingModel",
    "resolve_embedding_model_with_precedence",
    "validate_requested_embedding_model",
)


@dataclass(frozen=True, slots=True)
class ResolvedEmbeddingModel:
    model_id: str
    stored_selector: str | None


async def validate_requested_embedding_model(
    self: MCPRAGInternalProtocol,
    model_id: str,
) -> tuple[str, int]:
    normalized_model_id = coerce_optional_trimmed_str(model_id)
    if normalized_model_id is None:
        raise ValidationError("embedding_model must be a non-empty string")
    return await validate_and_resolve_embedding_model(
        self.storage,
        normalized_model_id,
    )


async def is_embedding_model_available_with_cache(
    self: MCPRAGInternalProtocol,
    model_id: str,
) -> bool:
    normalized_model_id = coerce_optional_trimmed_str(model_id)
    if normalized_model_id is None:
        return False
    max_cache_size = max(0, int(self.cache_max_size))
    if max_cache_size <= 0:
        self.embedding_availability_cache.clear()
        return await embedding_model_resolution.is_embedding_model_available(
            self.storage,
            normalized_model_id,
        )
    now = time.monotonic()
    cached = self.embedding_availability_cache.get(normalized_model_id)
    if cached and (now - cached[1]) <= self.cache_ttl_sec:
        return cached[0]
    available = await embedding_model_resolution.is_embedding_model_available(
        self.storage,
        normalized_model_id,
    )
    if len(self.embedding_availability_cache) >= max_cache_size:
        self.embedding_availability_cache.clear()
    self.embedding_availability_cache[normalized_model_id] = (available, now)
    return available


async def ensure_any_embedding_model_available_with_cache(
    self: MCPRAGInternalProtocol,
) -> str:
    if int(self.cache_max_size) <= 0:
        self.auto_embedding_cache = None
        return await embedding_model_resolution.ensure_any_embedding_model_available(self.storage)
    now = time.monotonic()
    cached = self.auto_embedding_cache
    if cached and (now - cached[1]) <= self.cache_ttl_sec:
        return cached[0]
    resolved = await embedding_model_resolution.ensure_any_embedding_model_available(self.storage)
    self.auto_embedding_cache = (resolved, now)
    return resolved


async def resolve_embedding_model_with_precedence(
    self: MCPRAGInternalProtocol,
    conv_id: str,
    user_id: int,
    request_model: str | None = None,
) -> ResolvedEmbeddingModel:
    def _normalize_candidate(model_id: str | None) -> str | None:
        candidate = coerce_optional_trimmed_str(model_id)
        if candidate is None:
            return None
        if is_auto_embedding_model_sentinel(candidate) or candidate.lower() == "auto":
            return "auto"
        return candidate

    if request_model is not None:
        requested = _normalize_candidate(request_model)
        if requested is None:
            raise ValidationError("embedding_model must be a non-empty string")
        return ResolvedEmbeddingModel(requested, None)
    config = await self.database_files.get_rag_config(conv_id)
    if config is not None and not isinstance(config, dict):
        raise StateError("Stored RAG config is invalid.")
    if config and "embedding_model" in config:
        conv_model_value = config.get("embedding_model")
        if conv_model_value is not None:
            resolved = _normalize_candidate(
                conv_model_value if isinstance(conv_model_value, str) else None,
            )
            if resolved is not None:
                return ResolvedEmbeddingModel(resolved, conv_model_value)
            raise ValidationError("Stored RAG config has invalid embedding_model value.")
    if user_id and user_id > 0:
        prefs = await self.database_users.get_user_preferences(user_id)
        default_model = read_chat_default_embedding_model(prefs)
        if default_model:
            resolved = _normalize_candidate(default_model)
            if resolved is not None:
                return ResolvedEmbeddingModel(resolved, None)
    config_default = self.config.get("TOOLS.RAG.DEFAULT_EMBEDDING_MODEL", "auto")
    resolved = _normalize_candidate(config_default if isinstance(config_default, str) else None)
    if resolved is None:
        raise StateError(
            "Invalid configuration: TOOLS.RAG.DEFAULT_EMBEDDING_MODEL must be a non-empty string.",
        )
    if resolved != "auto":
        resolved = await resolve_embedding_model_for_embeddings_request(self.storage, resolved)
    return ResolvedEmbeddingModel(resolved, None)


async def persist_effective_embedding_model(
    self: MCPRAGInternalProtocol,
    *,
    conv_id: str,
    user_id: int,
    embedding_model: str,
    expected_embedding_selector: str | None,
) -> bool:
    model_id = coerce_optional_trimmed_str(embedding_model)
    if model_id is None:
        raise ValidationError(
            "embedding_model must be a non-empty string",
            operation="mcp.rag.embedding_model.persist_effective_embedding_model",
        )
    if user_id and user_id > 0:
        commit = await self.database_files.update_rag_config_with_defaults(
            UpdateRAGConfigWithDefaultsRequest(
                update=UpdateRAGConfigRequest(conv_id=conv_id, embedding_model=model_id),
                user_id=user_id,
                expected_embedding_selector=expected_embedding_selector,
                require_matching_embedding_selector=True,
            )
        )
        return not commit.superseded
    await self.database_files.update_rag_config(
        UpdateRAGConfigRequest(conv_id=conv_id, embedding_model=model_id),
    )
    return True


async def prepare_ingest_context(
    self: MCPRAGInternalProtocol,
    conv_id: str,
    user_id: int,
    embedding_model: str | None = None,
    check_reindex: bool = True,
    reindex_error_verb: str = "upload",
) -> tuple[str, str]:
    resolved_conv_id = await self.resolve_conv_id_for_user(conv_id, user_id)
    if check_reindex and await self.worker.reindex_locks.is_in_progress(resolved_conv_id):
        raise ValidationError(
            f"Cannot {reindex_error_verb} while reindex is in progress for conversation {resolved_conv_id}",
        )
    await ensure_conversation_rag_enabled(self.database_files, resolved_conv_id)
    resolution = await resolve_embedding_model_with_precedence(
        self,
        resolved_conv_id,
        user_id,
        request_model=embedding_model,
    )
    resolved_embedding_model = resolution.model_id
    normalized_candidate = coerce_optional_trimmed_str(resolved_embedding_model) or "auto"
    if (
        is_auto_embedding_model_sentinel(normalized_candidate)
        or normalized_candidate.lower() == "auto"
    ):
        resolved_embedding_model = await ensure_any_embedding_model_available(self.storage)
        await persist_effective_embedding_model(
            self,
            conv_id=resolved_conv_id,
            user_id=user_id,
            embedding_model=resolved_embedding_model,
            expected_embedding_selector=resolution.stored_selector,
        )
    else:
        resolved_embedding_model = await resolve_embedding_model_for_embeddings_request(
            self.storage,
            normalized_candidate,
        )
    return (resolved_conv_id, resolved_embedding_model)

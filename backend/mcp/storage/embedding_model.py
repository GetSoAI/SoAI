"""SoAI - MCP storage embedding model resolution [backend/mcp/storage/embedding_model.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError, ValidationError
from core.models.model_info_fields import is_model_info_active_and_enabled
from core.openai.capability_checks import is_openai_capability_enabled
from core.validation.strings import coerce_optional_trimmed_str
from mcp.storage.embeddings import generate_embeddings
from mcp.storage.internal_protocols import MCPStorageProtocol

__all__ = ("validate_and_resolve_embedding_model",)


async def validate_and_resolve_embedding_model(
    self: MCPStorageProtocol,
    model_id: str,
) -> tuple[str, int]:
    if not self.model_resolution_service or not self.model_information_service:
        raise StateError(
            "model_resolution_service and model_information_service are required for embedding model validation",
        )
    normalized_model_id = coerce_optional_trimmed_str(model_id)
    if normalized_model_id is None:
        raise ValidationError("model_id must be a non-empty string")
    universal_id = await self.model_resolution_service.model_resolve_to_universal_id(
        normalized_model_id,
    )
    if not universal_id:
        raise ValidationError(f"Embedding model not found: {normalized_model_id!r}")
    model_info = await self.model_information_service.model_get_info(universal_id)
    if not isinstance(model_info, dict):
        raise ValidationError(f"Embedding model info not found: {normalized_model_id!r}")
    if not is_model_info_active_and_enabled(model_info):
        raise ValidationError(
            f"Embedding model '{normalized_model_id}' is not available or does not support embeddings.",
        )
    openai_caps = model_info.get("openai_capabilities")
    if not isinstance(openai_caps, dict) or not is_openai_capability_enabled(
        openai_caps,
        "endpoints",
        "embeddings",
    ):
        raise ValidationError(
            f"Embedding model '{normalized_model_id}' is not available or does not support embeddings.",
        )
    embeddings = await generate_embeddings(
        self,
        texts=["test"],
        conv_id="__validation__",
        user_id=0,
        embedding_model=normalized_model_id,
    )
    if not embeddings or not embeddings[0]:
        raise ValidationError(
            f"Embedding dimension detection failed for model {normalized_model_id!r}: empty embedding returned",
        )
    dimensions = len(embeddings[0])
    if dimensions <= 0:
        raise ValidationError(
            f"Embedding model returned invalid dimensions: {normalized_model_id!r} ({dimensions})",
        )
    return (normalized_model_id, dimensions)

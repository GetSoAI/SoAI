"""SoAI - RAG API schemas [backend/features/api/schemas/rag.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from pydantic import Field, StrictInt, model_validator

from core.errors.exceptions import ValidationError
from core.meta.soai_v1 import SoAIV1StrictModel

__all__ = (
    "RAGConfigUpdate",
    "RAGFileExplorerIngestRequest",
    "RAGSearchRequest",
)


class RAGConfigUpdate(SoAIV1StrictModel):
    enabled: bool | None = None
    retrieval_strategy: str | None = Field(None, pattern="^(similarity|mmr|hybrid)$")
    top_k: StrictInt | None = Field(None, ge=1, le=50)
    similarity_threshold: float | None = Field(None, ge=0.0, le=1.0)
    chunking_strategy: str | None = Field(
        None,
        pattern="^(token_based|fixed_size|paragraph|semantic)$",
    )
    chunk_size: StrictInt | None = Field(None, ge=100, le=4000)
    chunk_overlap: StrictInt | None = Field(None, ge=0, le=500)
    embedding_model: str | None = None

    @model_validator(mode="after")
    def validate_explicit_nulls(self) -> RAGConfigUpdate:
        payload = self.model_dump()
        for field_name in self.model_fields_set:
            if payload.get(field_name) is None:
                raise ValidationError(f"{field_name} may not be null")
        return self


class RAGSearchRequest(SoAIV1StrictModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: StrictInt | None = Field(None, ge=1, le=50)
    retrieval_strategy: str | None = Field(None, pattern="^(similarity|mmr|hybrid)$")
    similarity_threshold: float | None = Field(None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_explicit_nulls(self) -> RAGSearchRequest:
        payload = self.model_dump()
        for field_name in self.model_fields_set:
            if payload.get(field_name) is None:
                raise ValidationError(f"{field_name} may not be null")
        return self


class RAGFileExplorerIngestRequest(SoAIV1StrictModel):
    path: str = Field(..., min_length=1, max_length=4096)
    recursive: bool = True
    client_batch_id: str | None = Field(None, min_length=1, max_length=128)

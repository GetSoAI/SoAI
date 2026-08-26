"""SoAI - MCP RAG upload preparation [backend/mcp/rag/upload_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.config.upload_limits import UploadLimitType, resolve_upload_limit_bytes
from core.errors.exceptions import ValidationError
from core.files.rag_document_identity import normalize_rag_file_type
from mcp.rag.configuration import validate_chunking_params
from mcp.rag.embedding_model import prepare_ingest_context

if TYPE_CHECKING:
    from mcp.rag.internal_protocols import MCPRAGInternalProtocol

__all__ = (
    "PreparedDocumentUpload",
    "prepare_document_upload",
    "resolve_upload_source",
)


@dataclass(frozen=True, slots=True)
class PreparedDocumentUpload:
    conv_id: str
    file_type: str
    chunk_size: int
    chunk_overlap: int
    chunking_strategy: str
    resolved_embedding_model: str
    max_upload_bytes: int


async def prepare_document_upload(
    rag_service: MCPRAGInternalProtocol,
    *,
    conv_id: str,
    user_id: int,
    file_type: str,
    chunk_size: int,
    chunk_overlap: int,
    embedding_model: str | None,
    chunking_strategy: str,
) -> PreparedDocumentUpload:
    normalized_file_type = normalize_rag_file_type(file_type)
    validate_chunking_params(
        rag_service,
        chunk_size,
        chunk_overlap,
        chunking_strategy,
        normalized_file_type,
    )
    max_upload_bytes = resolve_upload_limit_bytes(
        rag_service.config,
        UploadLimitType.FILE,
        default_mb=250,
    )
    resolved_conv_id, resolved_embedding_model = await prepare_ingest_context(
        rag_service,
        conv_id,
        user_id,
        embedding_model,
        check_reindex=True,
        reindex_error_verb="upload",
    )
    return PreparedDocumentUpload(
        conv_id=resolved_conv_id,
        file_type=normalized_file_type,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        chunking_strategy=chunking_strategy,
        resolved_embedding_model=resolved_embedding_model,
        max_upload_bytes=max_upload_bytes,
    )


def resolve_upload_source(source_path: str, max_upload_bytes: int) -> str:
    try:
        resolved_source_path = os.path.realpath(source_path)
        source_size = int(os.stat(resolved_source_path).st_size)
    except (OSError, TypeError, ValueError) as exception:
        raise ValidationError("Failed to read uploaded document metadata.") from exception
    if source_size <= 0:
        raise ValidationError("Uploaded document is empty.")
    if source_size > max_upload_bytes:
        raise ValidationError(
            f"Uploaded document exceeds the configured limit of {max_upload_bytes} bytes.",
        )
    return resolved_source_path

"""SoAI - BM25-only chunk hydration for hybrid search [backend/mcp/rag/hybrid_search/bm25_only_chunks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.errors.exceptions import StateError
from core.files.rag_chunk_identity import parse_rag_index_chunk_id
from core.logging.trace import get_logger
from core.serialization.json import normalize_for_json
from core.types.json_value import is_json_value, require_json_dict
from core.validation.requirements import (
    require_nonempty_str,
    require_optional_str,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from mcp.rag.internal_protocols import MCPRAGSearchContextProtocol

__all__ = ("fetch_bm25_only_chunks",)

LOGGER_NAME = "SoAI.mcp.rag.bm25_only_chunks"


def require_optional_json_value(value: JSONValue, *, field: str) -> JSONValue | None:
    if value is None or is_json_value(value):
        return value
    raise StateError(f"{field} must be JSON-compatible.")


def split_chunk_id(chunk_id: str) -> tuple[str, int]:
    identity = parse_rag_index_chunk_id(chunk_id)
    return (identity.document_id, identity.chunk_index)


async def fetch_bm25_only_chunks(
    self: MCPRAGSearchContextProtocol,
    bm25_only_ids: list[str],
) -> dict[str, JSONDict]:
    logger = get_logger(LOGGER_NAME)
    doc_to_chunk_ids: dict[str, list[str]] = {}
    chunk_id_to_index: dict[str, int] = {}
    for chunk_id in bm25_only_ids:
        doc_id, chunk_index = split_chunk_id(chunk_id)
        chunk_ids = doc_to_chunk_ids.get(doc_id)
        if chunk_ids is None:
            chunk_ids = []
            doc_to_chunk_ids[doc_id] = chunk_ids
        chunk_ids.append(chunk_id)
        chunk_id_to_index[chunk_id] = chunk_index

    async def fetch_doc_bundle(doc_id: str) -> tuple[str, list[JSONDict], JSONDict]:
        chunks_task = create_ephemeral_task(self.database_files.get_rag_chunks_for_document(doc_id))
        doc_task = create_ephemeral_task(self.database_files.get_rag_document_by_id(doc_id))
        chunks, doc_info = await asyncio.gather(chunks_task, doc_task, return_exceptions=False)
        if not isinstance(chunks, list):
            raise StateError("RAG chunks payload must be a list.")
        chunk_rows: list[JSONDict] = []
        for row in chunks:
            chunk_rows.append(require_json_dict(normalize_for_json(row), label="rag_chunk"))
        doc_row = require_json_dict(normalize_for_json(doc_info), label="rag_document")
        if doc_row.get("status") != "completed":
            return (doc_id, [], doc_row)
        return (doc_id, chunk_rows, doc_row)

    bundles = await asyncio.gather(
        *[fetch_doc_bundle(doc_id) for doc_id in doc_to_chunk_ids],
        return_exceptions=False,
    )
    fetched_by_chunk_id: dict[str, JSONDict] = {}
    for doc_id, chunk_rows, doc_row in bundles:
        by_index: dict[int, JSONDict] = {}
        for row in chunk_rows:
            index_value = row.get("chunk_index")
            if isinstance(index_value, int):
                by_index[index_value] = row
        doc_filename = require_optional_str(doc_row.get("filename"), field="rag_document.filename")
        doc_filename = doc_filename.strip() if doc_filename else None
        doc_file_type = require_optional_str(
            doc_row.get("file_type"),
            field="rag_document.file_type",
        )
        doc_file_type = doc_file_type.strip() if doc_file_type else None
        doc_source_type = require_optional_str(
            doc_row.get("source_type"),
            field="rag_document.source_type",
        )
        doc_source_type = doc_source_type.strip() if doc_source_type else None
        doc_source_url = require_optional_str(
            doc_row.get("source_url"),
            field="rag_document.source_url",
        )
        doc_source_url = doc_source_url.strip() if doc_source_url else None
        for chunk_id in doc_to_chunk_ids.get(doc_id, []):
            chunk_row = by_index.get(chunk_id_to_index[chunk_id])
            if chunk_row is None:
                logger.warning(
                    "BM25 hit refers to missing chunk (stale index): %s - skipping",
                    chunk_id,
                )
                continue
            content = require_nonempty_str(chunk_row.get("content"), field="rag_chunk.content")
            chunk_metadata: JSONDict = {
                "document_id": doc_id,
                "chunk_index": chunk_id_to_index[chunk_id],
                "token_count": require_optional_json_value(
                    chunk_row.get("token_count"),
                    field="rag_chunk.token_count",
                ),
                "start_char": require_optional_json_value(
                    chunk_row.get("start_char"),
                    field="rag_chunk.start_char",
                ),
                "end_char": require_optional_json_value(
                    chunk_row.get("end_char"),
                    field="rag_chunk.end_char",
                ),
                "filename": doc_filename,
                "file_type": doc_file_type,
                "source_type": doc_source_type,
                "source_url": doc_source_url,
            }
            fetched_by_chunk_id[chunk_id] = {"content": content, "metadata": chunk_metadata}
    return fetched_by_chunk_id

"""SoAI - MCP storage sparse index operations [backend/mcp/storage/sparse_index.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from collections.abc import Sequence
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.rag_chunk_identity import build_rag_index_chunk_id_prefix
from core.hardware.reservation_claims import claim_reserved_write
from core.logging.trace import get_logger
from core.rag.config_metadata import (
    normalize_rag_bm25_settings,
    parse_rag_config_metadata_value,
)
from core.rag.sparse_index_errors import SparseIndexRebuildRequiredError
from core.validation.coercion import coerce_non_negative_int_from_numberish
from mcp.rag.indexing.sqlite_fts import SQLiteFTS5BM25Index
from mcp.storage.chroma_naming import collection_prefix_from_conv_id
from mcp.storage.chunk_storage_reservations import encoded_sparse_index_payload_size
from mcp.storage.internal_protocols import MCPStorageProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "append_documents_to_sparse_index",
    "ensure_sqlite_sparse_index_ready",
    "get_all_chunks_for_conversation",
    "get_sparse_settings",
    "rebuild_sparse_index",
    "sparse_index_root_dir",
    "sparse_search",
    "sqlite_sparse_index_path",
)

LOGGER_NAME = "SoAI.mcp.storage.sparse_index"
OPERATION = "mcp.storage.sparse_index.append_documents"


def sparse_index_root_dir(self: MCPStorageProtocol) -> str:
    root = self.config.get_str("TOOLS.RAG.SPARSE_INDEX_DIR")
    if not isinstance(root, str) or not root.strip():
        raise ValidationError("TOOLS.RAG.SPARSE_INDEX_DIR must be configured.")
    return self.files.resolve_path(root)


def sqlite_sparse_index_path(self: MCPStorageProtocol, conv_id: str) -> str:
    return os.path.join(
        sparse_index_root_dir(self),
        f"{collection_prefix_from_conv_id(conv_id)}.sqlite3",
    )


async def get_sparse_settings(self: MCPStorageProtocol, conv_id: str) -> dict[str, str]:
    config = await self.database_files.get_rag_config(conv_id)
    raw_metadata: JSONDict = {}
    if config:
        raw_metadata = parse_rag_config_metadata_value(config.get("config_metadata"))
    return normalize_rag_bm25_settings(raw_metadata)


async def rebuild_sparse_index(self: MCPStorageProtocol, conv_id: str) -> None:
    settings = await get_sparse_settings(self, conv_id)
    index = SQLiteFTS5BM25Index(
        db_path=sqlite_sparse_index_path(self, conv_id),
        tokenizer=settings["tokenizer"],
        stopwords_mode=settings["stopwords"],
    )
    chunks_to_add = await get_all_chunks_for_conversation(self, conv_id)
    lock = await self.get_sparse_index_lock(conv_id)
    async with lock:
        required_bytes = encoded_sparse_index_payload_size(documents=chunks_to_add)
        with (
            self.storage_manager.reserve_disk_space(
                path=index.db_path,
                required_bytes=required_bytes,
                operation="mcp.storage.sparse_index.rebuild",
                details={"conv_id": conv_id},
            ) as reservation,
            claim_reserved_write(reservation, size_bytes=required_bytes),
        ):
            await asyncio.to_thread(index.rebuild, chunks_to_add)


async def ensure_sqlite_sparse_index_ready(
    self: MCPStorageProtocol,
    conv_id: str,
    index: SQLiteFTS5BM25Index,
) -> None:
    counts = await self.database_files.get_rag_counts_for_conversation(conv_id)
    db_chunk_count = (
        coerce_non_negative_int_from_numberish(counts.get("chunk_count", 0))
        if isinstance(counts, dict)
        else 0
    )
    lock = await self.get_sparse_index_lock(conv_id)
    async with lock:
        exists_before = os.path.exists(index.db_path)
        try:
            await asyncio.to_thread(index.ensure_ready)
        except SparseIndexRebuildRequiredError:
            chunks_to_add = await get_all_chunks_for_conversation(self, conv_id)
            await asyncio.to_thread(index.rebuild, chunks_to_add)
            return
        exists_after = os.path.exists(index.db_path)
        if (not exists_before) and exists_after:
            chunks_to_add = await get_all_chunks_for_conversation(self, conv_id)
            await asyncio.to_thread(index.rebuild, chunks_to_add)
            return
        recorded = await asyncio.to_thread(index.recorded_chunk_count)
        recorded_count = coerce_non_negative_int_from_numberish(recorded)
        if recorded_count != db_chunk_count:
            chunks_to_add = await get_all_chunks_for_conversation(self, conv_id)
            await asyncio.to_thread(index.rebuild, chunks_to_add)


async def append_documents_to_sparse_index(
    self: MCPStorageProtocol,
    conv_id: str,
    *,
    document_id: str,
    documents: Sequence[tuple[str, str]],
) -> None:
    logger = get_logger(LOGGER_NAME)
    try:
        settings = await get_sparse_settings(self, conv_id)
        index = SQLiteFTS5BM25Index(
            db_path=sqlite_sparse_index_path(self, conv_id),
            tokenizer=settings["tokenizer"],
            stopwords_mode=settings["stopwords"],
        )
        await ensure_sqlite_sparse_index_ready(self, conv_id, index)
        lock = await self.get_sparse_index_lock(conv_id)
        async with lock:
            await asyncio.to_thread(index.add_documents, list(documents))
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message=(
                "Failed to update sparse index incrementally; it will be rebuilt on "
                "demand (non-critical)."
            ),
            operation=OPERATION,
            details={"conv_id": conv_id, "document_id": document_id},
            level="debug",
        )


async def sparse_search(
    self: MCPStorageProtocol,
    conv_id: str,
    query: str,
    top_k: int,
    document_id: str | None = None,
) -> list[tuple[str, float]]:
    settings = await get_sparse_settings(self, conv_id)
    index = SQLiteFTS5BM25Index(
        db_path=sqlite_sparse_index_path(self, conv_id),
        tokenizer=settings["tokenizer"],
        stopwords_mode=settings["stopwords"],
    )
    await ensure_sqlite_sparse_index_ready(self, conv_id, index)
    if document_id is None:
        return await asyncio.to_thread(index.search, query, top_k)
    return await asyncio.to_thread(
        index.search,
        query,
        top_k,
        build_rag_index_chunk_id_prefix(document_id),
    )


async def get_all_chunks_for_conversation(
    self: MCPStorageProtocol,
    conv_id: str,
) -> list[tuple[str, str]]:
    rows = await self.database_files.get_rag_chunks_for_conversation(conv_id)
    all_chunks: list[tuple[str, str]] = []
    if not isinstance(rows, list):
        return all_chunks
    for row in rows:
        if not isinstance(row, dict):
            continue
        chunk_id = str(row.get("id") or "").strip()
        if not chunk_id:
            continue
        content = str(row.get("content") or "")
        all_chunks.append((chunk_id, content))
    return all_chunks

"""SoAI - Chroma IPC gateway (killable worker pool) [backend/mcp/storage/chroma_ipc_gateway.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, override

from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ValidationError
from core.files.protocols import DatabaseFilesProtocol
from core.validation.strings import coerce_optional_trimmed_str
from mcp.storage.chroma_ipc_gateway_jobs import ChromaIpcJobRunner
from mcp.storage.chroma_ipc_gateway_shards import ChromaIpcShardPool
from mcp.storage.chroma_naming import collection_prefix_from_conv_id
from mcp.storage.internal_protocols import ChromaGatewayProtocol

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from core.concurrency.protocols import CancellationTokenProtocol
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.ipc.managed_worker import ManagedIpcWorkerDependencies
    from core.ipc.protocols import ManagedIpcWorkerProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = ("ChromaIpcGateway",)


class ChromaIpcGateway(ChromaGatewayProtocol):
    def __init__(
        self,
        *,
        config: ConfigProtocol,
        shutdown_event: asyncio.Event,
        database_files: DatabaseFilesProtocol,
        chroma_path: str,
        storage_manager: StorageManagerProtocol,
        managed_ipc_worker_builder: Callable[
            [ManagedIpcWorkerDependencies],
            ManagedIpcWorkerProtocol,
        ],
    ) -> None:
        self._database_files = database_files
        self._pool = ChromaIpcShardPool(
            config=config,
            shutdown_event=shutdown_event,
            chroma_base=str(chroma_path or ""),
            storage_manager=storage_manager,
            managed_ipc_worker_builder=managed_ipc_worker_builder,
        )
        self._runner = ChromaIpcJobRunner(config=config, pool=self._pool)

    @override
    async def start(self) -> None:
        await self._pool.start()

    @override
    async def shutdown(self) -> None:
        await self._pool.shutdown()

    def shard_for_conv_id(self, conv_id: str) -> int:
        return self._pool.shard_for_conv_id(conv_id)

    @override
    async def ensure_collection(
        self,
        *,
        conv_id: str,
        collection_name: str,
        embedding_model: str,
        effective_model: str,
        timeout_sec: float,
    ) -> None:
        await self._runner.run_job(
            conv_id=conv_id,
            op="chroma.ensure_collection",
            payload={
                "collection_name": str(collection_name or "").strip(),
                "embedding_model": coerce_optional_trimmed_str(embedding_model) or "",
                "effective_model": coerce_optional_trimmed_str(effective_model) or "",
            },
            timeout_sec=float(timeout_sec),
            cancel_wait_sec=0.0,
            token=None,
        )

    @override
    async def add_upsert_ids(
        self,
        *,
        conv_id: str,
        collection_name: str,
        ids: Sequence[str],
        embeddings: Sequence[Sequence[float]],
        documents: Sequence[str],
        metadatas: Sequence[Mapping[str, JSONValue]],
        batch_size: int,
        timeout_sec: float,
        cancel_wait_sec: float,
        token: CancellationTokenProtocol | None,
    ) -> None:
        await self._runner.run_job(
            conv_id=conv_id,
            op="chroma.add_upsert",
            payload={
                "collection_name": str(collection_name or "").strip(),
                "ids": list(ids),
                "embeddings": [list(row) for row in embeddings],
                "documents": list(documents),
                "metadatas": list(metadatas),
                "batch_size": int(batch_size),
            },
            timeout_sec=float(timeout_sec),
            cancel_wait_sec=float(cancel_wait_sec),
            token=token,
        )

    @override
    async def query(
        self,
        *,
        conv_id: str,
        collection_name: str,
        query_embeddings: Sequence[Sequence[float]],
        n_results: int,
        where: Mapping[str, JSONValue] | None,
        include: Sequence[str],
        timeout_sec: float,
    ) -> JSONDict | None:
        response = await self._runner.run_job(
            conv_id=conv_id,
            op="chroma.query",
            payload={
                "collection_name": str(collection_name or "").strip(),
                "query_embeddings": [list(row) for row in query_embeddings],
                "n_results": int(n_results),
                "where": dict(where) if isinstance(where, dict) else None,
                "include": [str(item) for item in include],
            },
            timeout_sec=float(timeout_sec),
            cancel_wait_sec=0.0,
            token=None,
        )
        result = response.get("result")
        return result if isinstance(result, dict) else None

    @override
    async def get(
        self,
        *,
        conv_id: str,
        collection_name: str,
        ids: Sequence[str] | None,
        where: Mapping[str, JSONValue] | None,
        include: Sequence[str],
        timeout_sec: float,
    ) -> JSONDict | None:
        response = await self._runner.run_job(
            conv_id=conv_id,
            op="chroma.get",
            payload={
                "collection_name": str(collection_name or "").strip(),
                "ids": list(ids) if ids is not None else None,
                "where": dict(where) if isinstance(where, dict) else None,
                "include": [str(item) for item in include],
            },
            timeout_sec=float(timeout_sec),
            cancel_wait_sec=0.0,
            token=None,
        )
        result = response.get("result")
        return result if isinstance(result, dict) else None

    @override
    async def delete(
        self,
        *,
        conv_id: str,
        collection_name: str,
        ids: Sequence[str] | None,
        where: Mapping[str, JSONValue] | None,
        timeout_sec: float,
    ) -> None:
        await self._runner.run_job(
            conv_id=conv_id,
            op="chroma.delete",
            payload={
                "collection_name": str(collection_name or "").strip(),
                "ids": list(ids) if ids is not None else None,
                "where": dict(where) if isinstance(where, dict) else None,
            },
            timeout_sec=float(timeout_sec),
            cancel_wait_sec=0.0,
            token=None,
        )

    @override
    async def delete_collection(
        self,
        *,
        conv_id: str,
        collection_name: str,
        timeout_sec: float,
    ) -> None:
        await self._runner.run_job(
            conv_id=conv_id,
            op="chroma.delete_collection",
            payload={"collection_name": str(collection_name or "").strip()},
            timeout_sec=float(timeout_sec),
            cancel_wait_sec=0.0,
            token=None,
        )

    @override
    async def list_collections(self, *, timeout_sec: float) -> list[str]:
        response = await self._runner.run_job(
            conv_id="system",
            op="chroma.list_collections",
            payload={},
            timeout_sec=float(timeout_sec),
            cancel_wait_sec=0.0,
            token=None,
            shard_override=0,
        )
        raw = response.get("result")
        if isinstance(raw, list):
            return [str(item) for item in raw if isinstance(item, str) and item.strip()]
        return []

    @override
    async def list_collections_for_conv(self, *, conv_id: str, timeout_sec: float) -> list[str]:
        shard_id = self.shard_for_conv_id(conv_id)
        response = await self._runner.run_job(
            conv_id=conv_id,
            op="chroma.list_collections",
            payload={},
            timeout_sec=float(timeout_sec),
            cancel_wait_sec=0.0,
            token=None,
            shard_override=int(shard_id),
        )
        raw = response.get("result")
        if isinstance(raw, list):
            return [str(item) for item in raw if isinstance(item, str) and item.strip()]
        return []

    @override
    async def count(
        self,
        *,
        conv_id: str,
        collection_name: str,
        timeout_sec: float,
    ) -> int:
        response = await self._runner.run_job(
            conv_id=conv_id,
            op="chroma.count",
            payload={"collection_name": str(collection_name or "").strip()},
            timeout_sec=float(timeout_sec),
            cancel_wait_sec=0.0,
            token=None,
        )
        value = response.get("result")
        return int(value) if isinstance(value, int) else 0

    @override
    async def resolve_active_collection_name(self, conv_id: str) -> str:
        normalized = str(conv_id or "").strip()
        if not normalized:
            raise ValidationError("conv_id is required.")
        metadata = await self._database_files.get_rag_collection_metadata(normalized)
        if metadata and isinstance(metadata, dict):
            name_value = metadata.get("collection_name")
            if isinstance(name_value, str) and name_value.strip():
                return name_value.strip()
        return collection_prefix_from_conv_id(normalized)

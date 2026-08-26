"""SoAI - Chroma IPC shard worker pool management [backend/mcp/storage/chroma_ipc_gateway_shards.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from hashlib import sha256
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import (
    ConfigurationError,
    ServiceUnavailableError,
    SoAIError,
    ValidationError,
)
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.ipc.job_files import JobFileStore
from core.ipc.ndjson import NdjsonCodec
from core.ipc.protocols import ManagedIpcWorkerProtocol
from core.ipc.server import LocalIpcServer
from core.ipc.settings import resolve_ipc_max_message_bytes
from core.logging.trace import get_logger
from mcp.storage.chroma_ipc_gateway_manifest import ensure_shard_manifest
from mcp.storage.chroma_ipc_worker_launch import build_chroma_shard_worker

if TYPE_CHECKING:
    from collections.abc import Callable

    from core.config.protocols import ConfigProtocol
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.ipc.managed_worker import ManagedIpcWorkerDependencies

__all__ = (
    "ChromaIpcShardPool",
    "ShardRuntime",
)

LOGGER_NAME = "SoAI.mcp.storage.chroma_ipc_gateway_shards"
OPERATION_MCP_STORAGE_CHROMA_IPC_SHUTDOWN_TERMINATE_WORKER = (
    "mcp.storage.chroma_ipc.shutdown.terminate_worker"
)
OPERATION_MCP_STORAGE_CHROMA_IPC_START = "mcp.storage.chroma_ipc.start"
OPERATION_MCP_STORAGE_CHROMA_IPC_START_CLEANUP_TERMINATE_WORKER = (
    "mcp.storage.chroma_ipc.start.cleanup.terminate_worker"
)


@dataclass(slots=True)
class ShardRuntime:
    shard_id: int
    persist_dir: str
    job_store: JobFileStore
    worker: ManagedIpcWorkerProtocol
    lock: asyncio.Lock


class ChromaIpcShardPool:
    def __init__(
        self,
        *,
        config: ConfigProtocol,
        shutdown_event: asyncio.Event,
        chroma_base: str,
        storage_manager: StorageManagerProtocol,
        managed_ipc_worker_builder: Callable[
            [ManagedIpcWorkerDependencies],
            ManagedIpcWorkerProtocol,
        ],
    ) -> None:
        self._config = config
        self._shutdown_event = shutdown_event
        self._chroma_base = os.path.abspath(str(chroma_base or "").strip())
        if storage_manager is None:
            raise ValidationError("storage_manager is required for ChromaIpcShardPool.")
        self._storage_manager = storage_manager
        self._managed_ipc_worker_builder = managed_ipc_worker_builder
        self._server = LocalIpcServer(
            codec=NdjsonCodec(max_line_bytes=resolve_ipc_max_message_bytes(config)),
        )
        self._shards: dict[int, ShardRuntime] = {}
        self._started = False
        self._shutdown_in_progress = False
        self._start_lock = asyncio.Lock()

    @property
    def server(self) -> LocalIpcServer:
        return self._server

    @property
    def storage_manager(self) -> StorageManagerProtocol:
        return self._storage_manager

    @property
    def started(self) -> bool:
        return bool(self._started)

    @property
    def shutdown_in_progress(self) -> bool:
        return bool(self._shutdown_in_progress)

    @property
    def accepting_jobs(self) -> bool:
        return not (self._shutdown_event.is_set() or self._shutdown_in_progress)

    @property
    def shard_count(self) -> int:
        return len(self._shards)

    def get_runtime(self, shard_id: int) -> ShardRuntime | None:
        return self._shards.get(int(shard_id))

    async def start(self) -> None:
        async with self._start_lock:
            self._raise_if_shutdown_started()
            if self._started:
                return
            logger = get_logger(LOGGER_NAME)
            if not self._chroma_base:
                raise ValidationError("ChromaDB path is not configured.")
            shard_count = int(self._config.get_int("TOOLS.RAG.CHROMA_SHARD_COUNT"))
            if shard_count < 1:
                raise ConfigurationError("TOOLS.RAG.CHROMA_SHARD_COUNT must be at least 1.")
            os.makedirs(self._chroma_base, exist_ok=True)
            ensure_shard_manifest(self._chroma_base, shard_count, self._storage_manager)
            await self._server.start()
            try:
                for shard_id in range(shard_count):
                    persist_dir = os.path.join(self._chroma_base, "shards", f"shard_{shard_id}")
                    os.makedirs(persist_dir, exist_ok=True)
                    job_dir = os.path.join(persist_dir, ".soai_ipc")
                    job_store = JobFileStore(
                        base_dir=job_dir,
                        ttl_sec=float(self._config.get_int("TOOLS.RAG.CHROMA_IPC_JOB_TTL_SEC")),
                        storage_manager=self._storage_manager,
                    )
                    await job_store.ensure_dirs()
                    await job_store.sweep_orphaned_files()
                    worker = build_chroma_shard_worker(
                        shard_id=shard_id,
                        persist_dir=persist_dir,
                        server=self._server,
                        managed_ipc_worker_builder=self._managed_ipc_worker_builder,
                    )
                    self._shards[shard_id] = ShardRuntime(
                        shard_id=shard_id,
                        persist_dir=persist_dir,
                        job_store=job_store,
                        worker=worker,
                        lock=asyncio.Lock(),
                    )
                startup_timeout = float(
                    self._config.get_int("TOOLS.RAG.CHROMA_IPC_STARTUP_TIMEOUT_SEC"),
                )
                if startup_timeout < 1.0:
                    raise ConfigurationError(
                        "TOOLS.RAG.CHROMA_IPC_STARTUP_TIMEOUT_SEC must be at least 1.",
                    )
                for runtime in self._shards.values():
                    await runtime.worker.spawn(
                        server=self._server,
                        startup_timeout_sec=startup_timeout,
                    )
            except asyncio.CancelledError:
                for runtime in list(self._shards.values()):
                    try:
                        await runtime.worker.terminate(
                            operation="mcp.storage.chroma_ipc.start.cleanup",
                        )
                    except SoAIError as terminate_error:
                        log_handled_exception(
                            logger,
                            terminate_error,
                            message="Failed to terminate Chroma worker during startup cleanup (non-critical).",
                            operation=OPERATION_MCP_STORAGE_CHROMA_IPC_START_CLEANUP_TERMINATE_WORKER,
                            details={"shard_id": int(runtime.shard_id)},
                            level="debug",
                        )
                self._shards.clear()
                await self._server.shutdown()
                raise
            except RECOVERABLE_EXCEPTIONS as exception:
                error = coerce_to_soai_error(
                    exception,
                    operation="mcp.storage.chroma_ipc.start",
                )
                log_exception(
                    logger,
                    error,
                    message="Failed to start Chroma IPC gateway; cleaning up.",
                    operation=OPERATION_MCP_STORAGE_CHROMA_IPC_START,
                    level="warning",
                )
                for runtime in list(self._shards.values()):
                    try:
                        await runtime.worker.terminate(
                            operation="mcp.storage.chroma_ipc.start.cleanup",
                        )
                    except SoAIError as terminate_error:
                        log_handled_exception(
                            logger,
                            terminate_error,
                            message="Failed to terminate Chroma worker during startup cleanup (non-critical).",
                            operation=OPERATION_MCP_STORAGE_CHROMA_IPC_START_CLEANUP_TERMINATE_WORKER,
                            details={"shard_id": int(runtime.shard_id)},
                            level="debug",
                        )
                self._shards.clear()
                await self._server.shutdown()
                raise
            logger.info(
                "Chroma IPC gateway started with %d shard workers (base=%s).",
                shard_count,
                self._chroma_base,
            )
            self._started = True

    def _raise_if_shutdown_started(self) -> None:
        if not self._shutdown_event.is_set():
            return
        raise ServiceUnavailableError(
            "Chroma IPC gateway is shutting down.",
            operation="mcp.storage.chroma_ipc.start.shutdown",
        )

    async def shutdown(self) -> None:
        logger = get_logger(LOGGER_NAME)
        async with self._start_lock:
            if not self._started:
                return
            self._shutdown_in_progress = True
            try:
                await self._server.shutdown()
                for runtime in list(self._shards.values()):
                    async with runtime.lock:
                        try:
                            await runtime.worker.terminate(
                                operation="mcp.storage.chroma_ipc.shutdown",
                            )
                        except SoAIError as exception:
                            log_handled_exception(
                                logger,
                                exception,
                                message="Failed to terminate Chroma shard worker (non-critical).",
                                operation=OPERATION_MCP_STORAGE_CHROMA_IPC_SHUTDOWN_TERMINATE_WORKER,
                                details={"shard_id": int(runtime.shard_id)},
                                level="warning",
                            )
                self._shards.clear()
                self._started = False
            finally:
                self._shutdown_in_progress = False

    def shard_for_conv_id(self, conv_id: str) -> int:
        normalized = str(conv_id or "").strip()
        if not normalized:
            raise ValidationError("conv_id is required.")
        shard_count = (
            max(1, len(self._shards))
            if self._shards
            else int(self._config.get_int("TOOLS.RAG.CHROMA_SHARD_COUNT"))
        )
        shard_count = max(shard_count, 1)
        digest = sha256(normalized.encode("utf-8", errors="strict")).digest()
        value = int.from_bytes(digest[:8], "big", signed=False)
        return int(value % shard_count)

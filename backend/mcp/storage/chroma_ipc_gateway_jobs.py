"""SoAI - Chroma IPC job execution with retries [backend/mcp/storage/chroma_ipc_gateway_jobs.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import uuid
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import ServiceUnavailableError, SoAIError, ValidationError
from core.logging.trace import get_logger
from mcp.storage.chroma_ipc_gateway_ipc import (
    build_task_cancelled_error,
    cleanup_ipc_files,
    error_from_ipc_payload,
    ipc_error_is_cancelled,
    request_with_optional_token_cancellation,
    should_retry_after_ipc_error,
    touch_cancel_file,
)
from mcp.storage.chroma_ipc_gateway_shards import ChromaIpcShardPool, ShardRuntime

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.config.protocols import ConfigProtocol
    from core.types.json import JSONDict

__all__ = ("ChromaIpcJobRunner",)

LOGGER_NAME = "SoAI.mcp.storage.chroma_ipc_gateway_jobs"
OPERATION_MCP_STORAGE_CHROMA_IPC_CANCEL_RESTART_FAILED = (
    "mcp.storage.chroma_ipc.cancel.restart_failed"
)
OPERATION_MCP_STORAGE_CHROMA_IPC_RESTART_WORKER = "mcp.storage.chroma_ipc.restart_worker"


class ChromaIpcJobRunner:
    def __init__(self, *, config: ConfigProtocol, pool: ChromaIpcShardPool) -> None:
        self._config = config
        self._pool = pool

    async def run_job(
        self,
        *,
        conv_id: str,
        op: str,
        payload: JSONDict,
        timeout_sec: float,
        cancel_wait_sec: float,
        token: CancellationTokenProtocol | None,
        shard_override: int | None = None,
    ) -> JSONDict:
        self._raise_if_pool_is_shutting_down()
        await self._pool.start()
        self._raise_if_pool_is_shutting_down()
        request_id = uuid.uuid4().hex
        shard_id = (
            int(shard_override)
            if shard_override is not None
            else self._pool.shard_for_conv_id(conv_id)
        )
        runtime = self._pool.get_runtime(int(shard_id))
        if runtime is None:
            raise ServiceUnavailableError(
                "Chroma shard worker unavailable.",
                operation="mcp.storage.chroma_ipc.run_job.missing_shard",
                details={"shard_id": int(shard_id)},
            )
        paths = runtime.job_store.build_paths(request_id)
        cancel_path_value = os.path.join(runtime.job_store.base_dir, f"{request_id}.cancel")
        job: JSONDict = {
            "request_id": request_id,
            "op": str(op or "").strip(),
            "payload": dict(payload),
            "response_path": paths.response_path,
            "cancel_path": cancel_path_value,
        }
        await runtime.job_store.write_job(paths.job_path, job)
        attempt = 0
        retry_count = self._config.get_int("TOOLS.RAG.CHROMA_IPC_RETRY_COUNT")
        if retry_count < 0:
            raise ValidationError("TOOLS.RAG.CHROMA_IPC_RETRY_COUNT must be >= 0.")
        max_attempts = 1 + int(retry_count)
        try:
            while attempt < max_attempts:
                attempt += 1
                async with runtime.lock:
                    try:

                        async def _restart_after_token_cancel() -> None:
                            self._raise_if_pool_is_shutting_down()
                            await self._restart_shard_worker(
                                runtime,
                                cause=ServiceUnavailableError(
                                    "Chroma worker did not stop after cancellation; restarting.",
                                    operation="mcp.storage.chroma_ipc.token_cancel.restart",
                                    details={"shard_id": int(runtime.shard_id)},
                                ),
                                cancel_wait_sec=0.0,
                                cancel_path=cancel_path_value,
                            )

                        response_envelope = await request_with_optional_token_cancellation(
                            self._pool.server,
                            worker_id=int(shard_id),
                            method="run_job",
                            request_id=request_id,
                            payload={"job_path": paths.job_path},
                            timeout_sec=float(timeout_sec),
                            cancel_path=cancel_path_value,
                            storage_manager=self._pool.storage_manager,
                            cancel_wait_sec=float(cancel_wait_sec),
                            token=token,
                            restart_worker=_restart_after_token_cancel,
                        )
                        if response_envelope.get("ok") is not True:
                            envelope_payload = response_envelope.get("payload")
                            if isinstance(envelope_payload, dict):
                                raise error_from_ipc_payload(envelope_payload)
                            raise ValidationError("IPC worker returned a failed response envelope.")
                        response = await runtime.job_store.read_json_dict(paths.response_path)
                        if response.get("request_id") != request_id:
                            raise ValidationError("IPC response request_id mismatch.")
                        ok_value = response.get("ok")
                        if ok_value is True:
                            return response
                        error_value = response.get("error")
                        if ipc_error_is_cancelled(error_value):
                            if token is None:
                                raise ServiceUnavailableError(
                                    "Chroma IPC operation cancelled.",
                                    operation="mcp.storage.chroma_ipc.cancelled",
                                )
                            raise build_task_cancelled_error(token)
                        raise error_from_ipc_payload(error_value)
                    except asyncio.CancelledError:
                        if not self._pool.accepting_jobs:
                            raise
                        await touch_cancel_file(cancel_path_value, self._pool.storage_manager)
                        try:
                            await self._restart_shard_worker(
                                runtime,
                                cause=ValidationError(
                                    "Operation cancelled; restarting worker to avoid wedged shard.",
                                ),
                                cancel_wait_sec=cancel_wait_sec,
                                cancel_path=cancel_path_value,
                            )
                        except SoAIError as exception:
                            logger = get_logger(LOGGER_NAME)
                            log_exception(
                                logger,
                                exception,
                                message="Failed to restart Chroma worker during cancellation cleanup.",
                                operation=OPERATION_MCP_STORAGE_CHROMA_IPC_CANCEL_RESTART_FAILED,
                                details={"shard_id": int(runtime.shard_id)},
                                level="warning",
                            )
                        raise
                    except SoAIError as exception:
                        self._raise_if_pool_is_shutting_down(cause=exception)
                        if not should_retry_after_ipc_error(exception):
                            raise
                        if attempt >= max_attempts:
                            raise
                        await self._restart_shard_worker(
                            runtime,
                            cause=exception,
                            cancel_wait_sec=cancel_wait_sec,
                            cancel_path=cancel_path_value,
                        )
            raise ServiceUnavailableError(
                "Chroma IPC operation failed after retries.",
                operation="mcp.storage.chroma_ipc.run_job.exhausted",
            )
        finally:
            await cleanup_ipc_files(paths.job_path, paths.response_path, cancel_path_value)

    def _raise_if_pool_is_shutting_down(self, *, cause: BaseException | None = None) -> None:
        if self._pool.accepting_jobs:
            return
        raise ServiceUnavailableError(
            "Chroma IPC gateway is shutting down.",
            operation="mcp.storage.chroma_ipc.run_job.shutdown",
            cause=cause,
        )

    async def _restart_shard_worker(
        self,
        runtime: ShardRuntime,
        *,
        cause: BaseException,
        cancel_wait_sec: float,
        cancel_path: str | None,
    ) -> None:
        logger = get_logger(LOGGER_NAME)
        log_exception(
            logger,
            cause,
            message="Restarting Chroma shard worker after IPC failure.",
            operation=OPERATION_MCP_STORAGE_CHROMA_IPC_RESTART_WORKER,
            details={"shard_id": int(runtime.shard_id)},
            level="warning",
        )
        if cancel_path:
            await touch_cancel_file(cancel_path, self._pool.storage_manager)
            if cancel_wait_sec > 0:
                await asyncio.sleep(max(0.0, float(cancel_wait_sec)))
        await runtime.worker.terminate(operation="mcp.storage.chroma_ipc.restart.terminate")
        startup_timeout = float(self._config.get_int("TOOLS.RAG.CHROMA_IPC_STARTUP_TIMEOUT_SEC"))
        if startup_timeout < 1.0:
            raise ValidationError("TOOLS.RAG.CHROMA_IPC_STARTUP_TIMEOUT_SEC must be >= 1.")
        await runtime.worker.spawn(server=self._pool.server, startup_timeout_sec=startup_timeout)

"""SoAI - Chroma shard worker process (IPC) [backend/mcp/storage/chroma_ipc_worker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING

import chromadb
from chromadb.config import Settings

from core.bootstrap.disk_reservation_provider import (
    create_bootstrap_disk_reservation_provider,
)
from core.config.byte_sizes import MIB_BYTES
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.trace_logging import ensure_trace_logging
from core.ipc.ndjson_rpc_loop import (
    NdjsonRpcRequest,
    NdjsonRpcResponse,
    run_ndjson_rpc_loop,
)
from core.ipc.ndjson_worker_handshake import connect_ndjson_ipc_worker_session
from core.logging.configuration_constants import DEFAULT_LOG_DATE_FORMAT, DEFAULT_LOG_FORMAT
from core.logging.formatters import UnifiedFormatter
from core.logging.protocols import StandardLogger
from core.logging.trace import get_logger
from core.meta.paths import get_repo_root
from core.runtime.worker_entrypoint import run_worker_entrypoint
from core.timing.constants import LONG_IDLE_TIMEOUT_SEC
from mcp.storage.chroma_ipc_worker_operations import execute_chroma_op
from mcp.storage.chroma_ipc_worker_responses import load_job, respond_error, respond_ok

if TYPE_CHECKING:
    from chromadb.api import ClientAPI

    from core.hardware.protocols_storage import StorageManagerProtocol

__all__ = ("main",)

OPERATION_MCP_STORAGE_CHROMA_IPC_WORKER_HANDLE_JOB = "mcp.storage.chroma_ipc_worker.handle_job"


LOGGER_NAME = "SoAI.mcp.storage.chroma_ipc_worker"
OPERATION_MCP_STORAGE_CHROMA_WORKER_FATAL_UNHANDLED = "mcp.storage.chroma_worker.fatal.unhandled"


async def _connect() -> tuple[asyncio.StreamReader, asyncio.StreamWriter, int]:
    return await connect_ndjson_ipc_worker_session(worker_label="Chroma worker")


def _setup_worker_logging() -> StandardLogger:
    ensure_trace_logging()
    log_path = str(os.environ.get("SOAI_CHROMA_WORKER_LOG", "")).strip()
    logger = get_logger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = UnifiedFormatter(
        DEFAULT_LOG_FORMAT,
        DEFAULT_LOG_DATE_FORMAT,
        use_colors=False,
    )
    handler: logging.Handler
    if log_path:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        handler = RotatingFileHandler(log_path, maxBytes=5 * MIB_BYTES, backupCount=3)
        handler.setFormatter(formatter)
    else:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(formatter)
    previous_handlers = list(logger.handlers)
    logger.handlers = [handler]
    for previous_handler in previous_handlers:
        previous_handler.close()
    return logger


async def _handle_job(
    client: ClientAPI,
    job_path: str,
    *,
    logger: StandardLogger,
    storage_manager: StorageManagerProtocol,
) -> None:
    job = load_job(job_path)
    request_id = str(job.get("request_id") or "").strip()
    response_path = str(job.get("response_path") or "").strip()
    cancel_path = str(job.get("cancel_path") or "").strip() if job.get("cancel_path") else None
    op = str(job.get("op") or "").strip()
    payload = job.get("payload")
    if not request_id:
        raise ValidationError("Job request_id is missing.")
    if not response_path:
        raise ValidationError("Job response_path is missing.")
    if not op:
        raise ValidationError("Job op is missing.")
    if not isinstance(payload, dict):
        raise ValidationError("Job payload must be a JSON object.")
    operation = f"mcp.storage.chroma_worker.{op}"
    try:
        result = execute_chroma_op(client, op=op, payload=payload, cancel_path=cancel_path)
        respond_ok(
            request_id=request_id,
            response_path=response_path,
            result=result,
            storage_manager=storage_manager,
        )
    except asyncio.CancelledError as exception:
        respond_error(
            request_id=request_id,
            response_path=response_path,
            exception=exception,
            operation=operation,
            storage_manager=storage_manager,
            details={"cancelled": True},
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        error = coerce_to_soai_error(exception, operation=operation)
        log_exception(
            logger,
            error,
            message="Chroma worker job failed.",
            operation=OPERATION_MCP_STORAGE_CHROMA_IPC_WORKER_HANDLE_JOB,
            level="warning",
        )
        respond_error(
            request_id=request_id,
            response_path=response_path,
            exception=error,
            operation=operation,
            storage_manager=storage_manager,
        )


async def _run() -> None:
    logger = _setup_worker_logging()
    persist_dir = str(os.environ.get("SOAI_CHROMA_PERSIST_DIR", "")).strip()
    if not persist_dir:
        raise ValidationError("SOAI_CHROMA_PERSIST_DIR is required for Chroma worker.")
    storage_manager = create_bootstrap_disk_reservation_provider(get_repo_root())
    os.makedirs(persist_dir, exist_ok=True)
    settings = Settings(anonymized_telemetry=False, chroma_otel_granularity="none")
    client = chromadb.PersistentClient(path=persist_dir, settings=settings)
    reader, writer, worker_id = await _connect()
    logger.info("Chroma shard worker %d connected (persist_dir=%s).", worker_id, persist_dir)

    async def handle_request(request: NdjsonRpcRequest) -> NdjsonRpcResponse:
        payload = request.payload
        if request.method != "run_job" or not isinstance(payload, dict):
            return NdjsonRpcResponse(
                request_id=request.request_id,
                ok=False,
                payload={
                    "error": "invalid_request",
                    "message": "Invalid method or payload.",
                },
            )
        job_path = str(payload.get("job_path") or "").strip()
        if not job_path:
            return NdjsonRpcResponse(
                request_id=request.request_id,
                ok=False,
                payload={
                    "error": "missing_job_path",
                    "message": "Missing job_path.",
                },
            )
        try:
            await _handle_job(
                client,
                job_path,
                logger=logger,
                storage_manager=storage_manager,
            )
        except SoAIError as exception:
            return NdjsonRpcResponse(
                request_id=request.request_id,
                ok=False,
                payload={
                    "error": exception.code,
                    "message": str(exception),
                    "operation": str(exception.operation or "mcp.storage.chroma_worker.handle_job"),
                    "details": dict(exception.details) if exception.details else None,
                },
            )
        return NdjsonRpcResponse(request_id=request.request_id, ok=True)

    await run_ndjson_rpc_loop(
        reader=reader,
        writer=writer,
        idle_timeout_sec=LONG_IDLE_TIMEOUT_SEC,
        handle_request=handle_request,
    )


def main() -> None:
    logger = _setup_worker_logging()
    run_worker_entrypoint(
        _run(),
        logger=logger,
        soai_error_message="Chroma worker fatal error.",
        unhandled_message="Chroma worker unhandled fatal error.",
        operation=OPERATION_MCP_STORAGE_CHROMA_WORKER_FATAL_UNHANDLED,
    )


if __name__ == "__main__":
    main()

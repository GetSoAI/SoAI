"""SoAI - Chroma IPC job request utilities [backend/mcp/storage/chroma_ipc_gateway_ipc.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from core.concurrency.cancellation import TaskCancelledError
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_groups import cancel_and_await
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import InsufficientDiskSpaceError, SoAIError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.atomic_writes import atomic_write_text_content
from core.hardware.reservation_claims import claim_reserved_write
from core.logging.trace import get_logger
from core.tasks.cancellation_ids import normalize_cancellation_id

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.concurrency.protocols import CancellationTokenProtocol
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.ipc.server import LocalIpcServer
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_task_cancelled_error",
    "cleanup_ipc_files",
    "error_from_ipc_payload",
    "ipc_error_is_cancelled",
    "request_with_optional_token_cancellation",
    "should_retry_after_ipc_error",
    "touch_cancel_file",
)

LOGGER_NAME = "SoAI.mcp.storage.chroma_ipc_gateway_ipc"
OPERATION_MCP_STORAGE_CHROMA_IPC_CANCEL_AWAIT_COMPLETED_REQUEST = (
    "mcp.storage.chroma_ipc.cancel.await_completed_request"
)
OPERATION_MCP_STORAGE_CHROMA_IPC_CANCEL_FILE_WRITE = "mcp.storage.chroma_ipc.cancel_file.write"
OPERATION_MCP_STORAGE_CHROMA_IPC_CLEANUP_FILES = "mcp.storage.chroma_ipc.cleanup_files"


def error_from_ipc_payload(payload: JSONValue) -> SoAIError:
    if not isinstance(payload, dict):
        return SoAIError("Chroma IPC worker failed with an invalid error payload.")
    message = str(payload.get("message") or "Chroma IPC worker error")
    operation = str(payload.get("operation") or "mcp.storage.chroma_ipc.worker")
    details_raw = payload.get("details")
    details = dict(details_raw) if isinstance(details_raw, dict) else None
    error = SoAIError(message, details=details, operation=operation)
    code = payload.get("code")
    if code is None:
        code = payload.get("error")
    if code == InsufficientDiskSpaceError.code:
        return InsufficientDiskSpaceError(message, operation=operation, details=details)
    if isinstance(code, str | int):
        error.code = code
    return error


def ipc_error_is_cancelled(payload: JSONValue) -> bool:
    if not isinstance(payload, dict):
        return False
    details_raw = payload.get("details")
    if not isinstance(details_raw, dict):
        return False
    return details_raw.get("cancelled") is True


def build_task_cancelled_error(token: CancellationTokenProtocol) -> BaseException:
    cancellation_id = normalize_cancellation_id(token.cancellation_id) or "unknown"
    reason = str(token.cancellation_reason or "").strip() or "Cancelled by user"
    return TaskCancelledError(cancellation_id, reason)


def should_retry_after_ipc_error(exception: SoAIError) -> bool:
    code = exception.code
    operation = str(exception.operation or "")
    is_worker_error = operation.startswith("mcp.storage.chroma_worker.")
    if is_worker_error and code in {
        "invalid_request_error",
        "payload_too_large",
        "precondition_failed",
        "not_found_error",
        "security_error",
        "config_error",
        "feature_disabled",
    }:
        return False
    if code in {"service_unavailable"}:
        return True
    if code in {"internal_error"}:
        return True
    return bool(exception.is_transient)


async def touch_cancel_file(path: str, storage_manager: StorageManagerProtocol) -> None:
    logger = get_logger(LOGGER_NAME)
    normalized = str(path or "").strip()
    if not normalized:
        return
    try:
        with (
            storage_manager.reserve_disk_space(
                path=normalized,
                required_bytes=1,
                operation=OPERATION_MCP_STORAGE_CHROMA_IPC_CANCEL_FILE_WRITE,
                details={"path": normalized, "required_bytes": 1},
            ) as reservation,
            claim_reserved_write(reservation, size_bytes=1),
        ):
            await asyncio.to_thread(
                atomic_write_text_content,
                normalized,
                "1",
                encoding="utf-8",
                errors="strict",
                fsync=True,
            )
    except OSError as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to create Chroma IPC cancel file (non-critical).",
            operation=OPERATION_MCP_STORAGE_CHROMA_IPC_CANCEL_FILE_WRITE,
            details={"path": normalized},
            level="debug",
        )


async def cleanup_ipc_files(job_path: str, response_path: str, cancel_path: str | None) -> None:
    logger = get_logger(LOGGER_NAME)
    for path in (job_path, response_path, cancel_path):
        if not path:
            continue
        try:
            await asyncio.to_thread(os.remove, path)
        except FileNotFoundError:
            continue
        except OSError as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to cleanup Chroma IPC file (non-critical).",
                operation=OPERATION_MCP_STORAGE_CHROMA_IPC_CLEANUP_FILES,
                details={"path": str(path)},
                level="debug",
            )


async def request_with_optional_token_cancellation(
    server: LocalIpcServer,
    *,
    worker_id: int,
    method: str,
    request_id: str,
    payload: JSONDict,
    timeout_sec: float,
    cancel_path: str,
    storage_manager: StorageManagerProtocol,
    cancel_wait_sec: float,
    token: CancellationTokenProtocol | None,
    restart_worker: Callable[[], Awaitable[None]] | None,
) -> JSONDict:
    if token is None:
        return await server.request(
            worker_id,
            method=method,
            request_id=request_id,
            payload=payload,
            timeout_sec=float(timeout_sec),
        )
    if token.thread_event.is_set():
        await touch_cancel_file(cancel_path, storage_manager)
        raise build_task_cancelled_error(token)
    request_task = create_ephemeral_task(
        server.request(
            worker_id,
            method=method,
            request_id=request_id,
            payload=payload,
            timeout_sec=float(timeout_sec),
        ),
    )
    cancel_task = create_ephemeral_task(token.wait())
    try:
        done, _pending = await asyncio.wait(
            {request_task, cancel_task},
            timeout=float(timeout_sec),
            return_when=asyncio.FIRST_COMPLETED,
        )
        if not done:
            if restart_worker is not None:
                await restart_worker()
            raise TimeoutError(f"IPC request timed out after {float(timeout_sec)} seconds.")
        if cancel_task in done:
            await touch_cancel_file(cancel_path, storage_manager)
            if request_task in done:
                try:
                    await request_task
                except RECOVERABLE_EXCEPTIONS as exception:
                    logger = get_logger(LOGGER_NAME)
                    error = coerce_to_soai_error(
                        exception,
                        operation="mcp.storage.chroma_ipc.cancel.await_completed_request",
                    )
                    log_handled_exception(
                        logger,
                        error,
                        message="IPC request completed with an error after cancellation; ignoring because cancellation won (non-critical).",
                        operation=OPERATION_MCP_STORAGE_CHROMA_IPC_CANCEL_AWAIT_COMPLETED_REQUEST,
                        level="debug",
                    )
            else:
                try:
                    await asyncio.wait_for(request_task, timeout=max(0.0, float(cancel_wait_sec)))
                except TimeoutError:
                    if restart_worker is not None:
                        await restart_worker()
                    request_task.cancel()
                    cleanup_results = await asyncio.gather(request_task, return_exceptions=True)
                    for cleanup_result in cleanup_results:
                        if isinstance(cleanup_result, asyncio.CancelledError):
                            continue
                        if isinstance(cleanup_result, BaseException):
                            local_logger = get_logger(LOGGER_NAME)
                            log_handled_exception(
                                local_logger,
                                cleanup_result,
                                message="IPC request task raised during cancellation cleanup (non-critical).",
                                operation=OPERATION_MCP_STORAGE_CHROMA_IPC_CANCEL_AWAIT_COMPLETED_REQUEST,
                                level="debug",
                            )
            raise build_task_cancelled_error(token)
        return await request_task
    finally:
        await cancel_and_await((request_task, cancel_task), task_label="chroma IPC request tasks")
        for task in (request_task, cancel_task):
            if task.cancelled():
                continue
            task_exception = task.exception()
            if task_exception is not None:
                local_logger = get_logger(LOGGER_NAME)
                log_handled_exception(
                    local_logger,
                    task_exception,
                    message="IPC request cancellation cleanup raised (non-critical).",
                    operation=OPERATION_MCP_STORAGE_CHROMA_IPC_CANCEL_AWAIT_COMPLETED_REQUEST,
                    level="debug",
                )

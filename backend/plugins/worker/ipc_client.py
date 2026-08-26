"""SoAI - Plugin worker multiplexed IPC client [backend/plugins/worker/ipc_client.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_groups import cancel_and_await
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import UNEXPECTED_RUNTIME_EXCEPTIONS
from core.ipc.error_payload import build_ipc_error_payload
from core.ipc.ndjson import IpcStreamClosedError
from core.ipc.settings import build_ndjson_codec_from_env
from core.logging.trace import get_logger
from core.openai.chat_template_role_policy import (
    CHAT_TEMPLATE_ROLE_REJECTION_CATEGORY,
    CHAT_TEMPLATE_ROLE_REJECTION_CATEGORY_KEY,
    extract_chat_template_role_rejection_http_status,
)
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC
from core.types.json import JSONDict
from core.validation.record_fields import require_json_object

__all__ = ("PluginWorkerIpcClient",)

LOGGER_NAME = "SoAI.plugins.worker.ipc_client"
OPERATION_IPC_CLIENT_REQUEST = "plugins.worker.ipc_client.request"
WORKER_IPC_CALL_EXCEPTIONS: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    SoAIError,
    *UNEXPECTED_RUNTIME_EXCEPTIONS,
)


class PluginWorkerIpcClient:
    def __init__(
        self,
        *,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        request_handler: Callable[[str, str, JSONDict], Awaitable[JSONDict]],
        cancel_handler: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._request_handler = request_handler
        self._cancel_handler = cancel_handler
        self._codec = build_ndjson_codec_from_env()
        self._write_lock = asyncio.Lock()
        self._pending: dict[str, asyncio.Future[JSONDict]] = {}
        self._active_calls: dict[str, asyncio.Task[None]] = {}

    async def run(self) -> None:
        try:
            while True:
                message = await self._codec.read_message(self._reader, timeout_sec=None)
                message_type = str(message.get("type") or "")
                request_id = str(message.get("request_id") or "")
                if not message_type:
                    raise ValidationError("Worker IPC message type is required.")
                if message_type == "response":
                    future = self._pending.get(request_id)
                    if future is not None and not future.done():
                        future.set_result(message)
                    continue
                if message_type == "request":
                    if not request_id:
                        raise ValidationError("Worker IPC request_id is required.")
                    task = create_ephemeral_task(
                        self._run_parent_request(message),
                        name=f"plugin-worker-call-{request_id}",
                    )
                    self._active_calls[request_id] = task

                    def remove_active_call(
                        _task: asyncio.Task[None],
                        key: str = request_id,
                    ) -> None:
                        self._active_calls.pop(key, None)

                    task.add_done_callback(remove_active_call)
                    continue
                raise ValidationError(f"Unsupported worker IPC message type '{message_type}'.")
        except IpcStreamClosedError:
            return
        finally:
            await self._cancel_active_calls()
            self._fail_pending_host_requests()

    async def request_host(self, method: str, payload: JSONDict) -> JSONDict:
        request_id = f"worker_host_{uuid.uuid4().hex}"
        loop = asyncio.get_running_loop()
        future: asyncio.Future[JSONDict] = loop.create_future()
        self._pending[request_id] = future
        try:
            await self._write_message(
                {
                    "type": "request",
                    "request_id": request_id,
                    "method": method,
                    "payload": dict(payload),
                },
            )
            response = await future
            payload_value = response.get("payload")
            ok_value = response.get("ok")
            if not isinstance(ok_value, bool):
                raise ValidationError("Host response ok flag must be a boolean.")
            if not ok_value:
                raise ValidationError(str(payload_value))
            return require_json_object(
                payload_value,
                label="Host response payload",
                build_error=ValidationError,
                invalid_message="Host response payload must be a JSON object.",
            )
        finally:
            self._pending.pop(request_id, None)

    async def send_event(self, message: JSONDict) -> None:
        await self._write_message(message)

    async def _run_parent_request(self, message: JSONDict) -> None:
        request_id = str(message.get("request_id") or "")
        method = str(message.get("method") or "")
        payload_value = message.get("payload")
        if not method:
            await self._write_response(
                request_id,
                {
                    "error": "ValidationError",
                    "message": "Worker request method is required.",
                },
                ok=False,
            )
            return
        if not isinstance(payload_value, dict):
            await self._write_response(
                request_id,
                {
                    "error": "ValidationError",
                    "message": "Worker request payload must be a JSON object.",
                },
                ok=False,
            )
            return
        payload = dict(payload_value)
        if method == "worker.cancel_call":
            await self._cancel_call(payload)
            await self._write_response(request_id, {"cancelled": True}, ok=True)
            return
        try:
            result = await self._request_handler(request_id, method, payload)
            await self._write_response(request_id, result, ok=True)
        except WORKER_IPC_CALL_EXCEPTIONS as exception:
            error_details: JSONDict = {"method": method}
            rejection_status = extract_chat_template_role_rejection_http_status(exception)
            if rejection_status is not None:
                error_details[CHAT_TEMPLATE_ROLE_REJECTION_CATEGORY_KEY] = (
                    CHAT_TEMPLATE_ROLE_REJECTION_CATEGORY
                )
                error_details["upstream_http_status"] = rejection_status
            error = coerce_to_soai_error(
                exception,
                operation=OPERATION_IPC_CLIENT_REQUEST,
                details=error_details,
            )
            log_exception(
                get_logger(LOGGER_NAME),
                error,
                message="Plugin worker IPC call failed.",
                operation=OPERATION_IPC_CLIENT_REQUEST,
                details={"request_id": request_id, "method": method},
                level="warning",
            )
            await self._write_response(
                request_id,
                build_ipc_error_payload(error),
                ok=False,
            )

    async def _cancel_call(self, payload: JSONDict) -> None:
        target_value = payload.get("request_id")
        target = target_value if isinstance(target_value, str) else ""
        if self._cancel_handler is not None:
            await self._cancel_handler(target)
        task = self._active_calls.get(target)
        if task is not None:
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=LOCAL_IO_TIMEOUT_SEC)
            except asyncio.CancelledError:
                return
            except TimeoutError as exception:
                raise ValidationError(
                    f"Worker call '{target}' did not cancel within timeout.",
                ) from exception

    async def _cancel_active_calls(self) -> None:
        tasks = tuple(self._active_calls.values())
        self._active_calls.clear()
        await cancel_and_await(
            tasks,
            task_label="plugin worker active IPC calls",
            timeout_sec=LOCAL_IO_TIMEOUT_SEC,
        )

    def _fail_pending_host_requests(self) -> None:
        pending = tuple(self._pending.values())
        self._pending.clear()
        for future in pending:
            if not future.done():
                future.set_exception(ValidationError("Plugin worker IPC connection closed."))

    async def _write_response(self, request_id: str, payload: JSONDict, *, ok: bool) -> None:
        await self._write_message(
            {
                "type": "response",
                "request_id": request_id,
                "ok": ok,
                "payload": dict(payload),
            },
        )

    async def _write_message(self, message: JSONDict) -> None:
        async with self._write_lock:
            await self._codec.write_message(self._writer, message, timeout_sec=LOCAL_IO_TIMEOUT_SEC)

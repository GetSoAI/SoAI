"""SoAI - Proxy plugin worker IPC invocation helpers [backend/plugins/worker/proxy_invocation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterable, Awaitable, Callable

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_groups import cancel_and_await
from core.errors.exceptions import ValidationError
from core.ipc.multiplexed import MultiplexedIpcServer
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC
from core.types.json import JSONDict, JSONValue
from core.validation.record_fields import require_json_object
from plugins.worker.handle_request_payload_budget import (
    fit_handle_request_payload_to_ipc_budget,
)
from plugins.worker.proxy_payloads import payload_from_message, require_json_response_value
from plugins.worker.proxy_streaming import prepare_stream_or_json_response, stream_queue
from plugins.worker.stream_protocol import (
    PLUGIN_STREAM_CHUNK_EVENT,
    PLUGIN_STREAM_END_EVENT,
    decode_stream_chunk_event,
    is_stream_response_payload,
)

__all__ = ("ProxyInvocationClient",)


class ProxyInvocationClient:
    def __init__(
        self,
        *,
        plugin_name: str,
        worker_id: int,
        server: MultiplexedIpcServer,
    ) -> None:
        self._plugin_name = plugin_name
        self._worker_id = worker_id
        self._server = server

    async def bool_call(
        self,
        method: str,
        payload: JSONDict,
        *,
        timeout_sec: float | None = None,
    ) -> bool:
        value = await self.value_call(method, payload, timeout_sec=timeout_sec)
        if not isinstance(value, bool):
            raise ValidationError(f"Plugin worker method '{method}' did not return a boolean.")
        return value

    async def value_call(
        self,
        method: str,
        payload: JSONDict,
        *,
        timeout_sec: float | None = None,
    ) -> JSONValue | JSONDict:
        response = await self.request(method, payload, timeout_sec=timeout_sec)
        response_payload = payload_from_message(response)
        value = response_payload.get("value")
        if isinstance(value, dict):
            return dict(value)
        return value

    async def dict_call(
        self,
        method: str,
        payload: JSONDict,
        *,
        timeout_sec: float | None = None,
    ) -> JSONDict:
        value = await self.value_call(method, payload, timeout_sec=timeout_sec)
        return require_json_object(
            value,
            label=f"Plugin worker method '{method}' response",
            build_error=ValidationError,
            invalid_message=f"Plugin worker method '{method}' did not return a JSON object.",
        )

    async def call_with_text_callback(
        self,
        method: str,
        payload: JSONDict,
        callback: Callable[[str], Awaitable[None] | None],
    ) -> JSONValue:
        async def event_handler(message: JSONDict) -> None:
            _require_event_type(message, "event.callback_text")
            message_value = payload_from_message(message).get("message")
            if not isinstance(message_value, str):
                raise ValidationError("Plugin worker text callback payload is malformed.")
            result = callback(message_value)
            if isinstance(result, Awaitable):
                await result

        response = await self.request(method, payload, event_handler=event_handler)
        return payload_from_message(response).get("value")

    async def json_tuple_call(
        self,
        method: str,
        payload: JSONDict,
        callback: Callable[[JSONDict], Awaitable[None]],
        *,
        request_timeout_sec: float | None = None,
    ) -> tuple[bool, str] | tuple[bool, str, JSONDict | None]:
        async def event_handler(message: JSONDict) -> None:
            _require_event_type(message, "event.callback_json")
            message_value = payload_from_message(message).get("message")
            callback_payload = require_json_object(
                message_value,
                label="Plugin worker JSON callback payload",
                build_error=ValidationError,
                invalid_message="Plugin worker JSON callback payload is malformed.",
            )
            await callback(callback_payload)

        response = await self.request(
            method,
            payload,
            event_handler=event_handler,
            timeout_sec=request_timeout_sec,
        )
        value = payload_from_message(response).get("value")
        if isinstance(value, list | tuple) and len(value) >= 3:
            if not isinstance(value[0], bool) or not isinstance(value[1], str):
                raise ValidationError(
                    f"Plugin worker method '{method}' returned a malformed tuple.",
                )
            detail = (
                require_json_object(
                    value[2],
                    label=f"Plugin worker method '{method}' tuple detail",
                    build_error=ValidationError,
                    invalid_message=f"Plugin worker method '{method}' returned a malformed tuple.",
                )
                if isinstance(value[2], dict)
                else None
            )
            return (value[0], value[1], detail)
        if isinstance(value, list | tuple) and len(value) >= 2:
            if not isinstance(value[0], bool) or not isinstance(value[1], str):
                raise ValidationError(
                    f"Plugin worker method '{method}' returned a malformed tuple.",
                )
            return (value[0], value[1])
        raise ValidationError(f"Plugin worker method '{method}' returned a malformed tuple.")

    async def cancellable_json_tuple_call(
        self,
        method: str,
        payload: JSONDict,
        callback: Callable[[JSONDict], Awaitable[None]],
        shutdown_event: asyncio.Event,
    ) -> tuple[bool, str] | tuple[bool, str, JSONDict | None]:
        if shutdown_event.is_set():
            raise asyncio.CancelledError()
        call_task = create_ephemeral_task(
            self.json_tuple_call(
                method,
                payload,
                callback,
                request_timeout_sec=None,
            ),
            name=f"plugin-proxy-call-{self._plugin_name}",
        )
        shutdown_task = create_ephemeral_task(
            shutdown_event.wait(),
            name=f"plugin-proxy-shutdown-watch-{self._plugin_name}",
            log_exceptions=False,
        )
        try:
            while True:
                done, _pending = await asyncio.wait(
                    {call_task, shutdown_task},
                    timeout=LOCAL_IO_TIMEOUT_SEC,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if not done:
                    continue
                if shutdown_task in done and not call_task.done():
                    await cancel_and_await((call_task,), task_label="plugin proxy call")
                    raise asyncio.CancelledError()
                return await call_task
        except asyncio.CancelledError:
            if not call_task.done():
                await cancel_and_await((call_task,), task_label="plugin proxy call")
            raise
        finally:
            if not shutdown_task.done():
                await cancel_and_await(
                    (shutdown_task,),
                    task_label="plugin proxy shutdown watch",
                )

    async def stream_call(
        self,
        method: str,
        payload: JSONDict,
        *,
        expected_stream: bool,
    ) -> JSONDict | AsyncIterable[bytes]:
        queue: asyncio.Queue[bytes | None] = asyncio.Queue()

        async def event_handler(message: JSONDict) -> None:
            message_type = str(message.get("type") or "")
            if message_type == PLUGIN_STREAM_CHUNK_EVENT:
                queue.put_nowait(decode_stream_chunk_event(message))
            elif message_type == PLUGIN_STREAM_END_EVENT:
                queue.put_nowait(None)
            else:
                raise ValidationError(f"Unexpected plugin worker stream event '{message_type}'.")

        response_task = create_ephemeral_task(
            self.request(method, payload, event_handler=event_handler, timeout_sec=None),
            name=f"plugin-proxy-stream-{self._plugin_name}",
        )
        if expected_stream:
            return await prepare_stream_or_json_response(
                queue,
                response_task,
                method=method,
            )
        response = await response_task
        response_payload = payload_from_message(response)
        if is_stream_response_payload(response_payload):
            return stream_queue(queue, response_task)
        return require_json_response_value(response_payload, method=method)

    async def request(
        self,
        method: str,
        payload: JSONDict,
        *,
        event_handler: Callable[[JSONDict], Awaitable[None]] | None = None,
        timeout_sec: float | None = None,
    ) -> JSONDict:
        request_id = f"plugin_{self._plugin_name}_{uuid.uuid4().hex}"
        next_payload = dict(payload)
        if method == "call.handle_request":
            next_payload = fit_handle_request_payload_to_ipc_budget(
                request_id=request_id,
                payload=next_payload,
                max_bytes=self._server.max_request_bytes,
            )
        return await self._server.request(
            self._worker_id,
            method=method,
            request_id=request_id,
            payload=next_payload,
            timeout_sec=timeout_sec,
            event_handler=event_handler,
        )


def _require_event_type(message: JSONDict, expected_type: str) -> None:
    message_type = str(message.get("type") or "")
    if message_type != expected_type:
        raise ValidationError(f"Unexpected plugin worker event '{message_type}'.")

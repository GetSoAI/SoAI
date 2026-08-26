"""SoAI - Proxy plugin worker stream response draining [backend/plugins/worker/proxy_streaming.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_groups import cancel_and_await
from core.errors.exceptions import ValidationError
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC
from core.types.json import JSONDict
from plugins.worker.proxy_payloads import payload_from_message, require_json_response_value
from plugins.worker.stream_protocol import is_stream_response_payload

__all__ = ("prepare_stream_or_json_response", "stream_queue")


async def prepare_stream_or_json_response(
    queue: asyncio.Queue[bytes | None],
    response_task: asyncio.Task[JSONDict],
    *,
    method: str,
) -> JSONDict | AsyncIterable[bytes]:
    chunk_task = create_ephemeral_task(
        queue.get(),
        name="plugin-proxy-initial-stream-chunk",
        log_exceptions=False,
    )
    try:
        while True:
            done, _pending = await asyncio.wait(
                {chunk_task, response_task},
                timeout=LOCAL_IO_TIMEOUT_SEC,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done:
                continue
            if chunk_task in done:
                return stream_queue(
                    queue,
                    response_task,
                    initial_item=chunk_task.result(),
                    initial_item_received=True,
                )
            response_payload = payload_from_message(await response_task)
            if is_stream_response_payload(response_payload):
                return stream_queue(queue, response_task)
            return require_json_response_value(response_payload, method=method)
    finally:
        if not chunk_task.done():
            await cancel_and_await(
                (chunk_task,),
                task_label="plugin proxy initial stream chunk wait",
            )


async def stream_queue(
    queue: asyncio.Queue[bytes | None],
    response_task: asyncio.Task[JSONDict],
    *,
    initial_item: bytes | None = None,
    initial_item_received: bool = False,
) -> AsyncIterable[bytes]:
    chunk_task: asyncio.Task[bytes | None] | None = None
    try:
        if initial_item_received:
            if initial_item is None:
                _validate_stream_response(await response_task)
                return
            yield initial_item
        while True:
            if not queue.empty():
                chunk = queue.get_nowait()
            else:
                chunk_task = create_ephemeral_task(
                    queue.get(),
                    name="plugin-proxy-stream-chunk",
                    log_exceptions=False,
                )
                while True:
                    done, _pending = await asyncio.wait(
                        {chunk_task, response_task},
                        timeout=LOCAL_IO_TIMEOUT_SEC,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if done:
                        break
                if response_task in done and not chunk_task.done():
                    await cancel_and_await(
                        (chunk_task,),
                        task_label="plugin proxy stream chunk wait",
                    )
                    chunk_task = None
                    _validate_stream_response(await response_task)
                    break
                chunk = chunk_task.result()
                chunk_task = None
            if chunk is None:
                _validate_stream_response(await response_task)
                break
            yield chunk
    finally:
        if chunk_task is not None and not chunk_task.done():
            await cancel_and_await(
                (chunk_task,),
                task_label="plugin proxy stream chunk wait",
            )
        if not response_task.done():
            await cancel_and_await(
                (response_task,),
                task_label="plugin proxy stream response",
            )


def _validate_stream_response(response: JSONDict) -> None:
    response_payload = payload_from_message(response)
    if not is_stream_response_payload(response_payload):
        value = response_payload.get("value")
        if isinstance(value, dict) and value:
            raise ValidationError("Plugin worker returned JSON after stream events.")
        raise ValidationError("Plugin worker stream ended without a stream response.")

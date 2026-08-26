"""SoAI - Plugin worker process entrypoint [backend/plugins/worker/main.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os

from core.errors.exceptions import ValidationError
from core.ipc.ndjson_worker_handshake import connect_ndjson_ipc_worker_session
from core.ipc.stream_closing import close_ipc_writer
from core.serialization.json_parsing import parse_json_value
from core.types.json import JSONDict
from core.validation.record_fields import require_json_object
from plugins.worker.ipc_client import PluginWorkerIpcClient
from plugins.worker.runtime import PluginWorkerRuntime

__all__ = ("main",)


def _load_bootstrap() -> JSONDict:
    payload = os.environ.get("SOAI_PLUGIN_WORKER_BOOTSTRAP", "")
    if not payload:
        raise ValidationError("Plugin worker bootstrap payload is missing.")
    return require_json_object(
        parse_json_value(payload, field="Plugin worker bootstrap payload"),
        label="Plugin worker bootstrap payload",
        build_error=ValidationError,
        invalid_message="Plugin worker bootstrap payload must be a JSON object.",
    )


async def _run_worker() -> None:
    reader, writer, _worker_id = await connect_ndjson_ipc_worker_session(
        worker_label="Plugin worker",
    )
    bootstrap = _load_bootstrap()
    runtime_holder: dict[str, PluginWorkerRuntime] = {}

    async def handle_request(request_id: str, method: str, payload: JSONDict) -> JSONDict:
        runtime = runtime_holder.get("runtime")
        if runtime is None:
            raise ValidationError("Plugin runtime is not initialized.")
        return await runtime.handle_request(request_id, method, payload)

    async def handle_cancel(request_id: str) -> None:
        runtime = runtime_holder.get("runtime")
        if runtime is not None:
            await runtime.cancel_request(request_id)

    client = PluginWorkerIpcClient(
        reader=reader,
        writer=writer,
        request_handler=handle_request,
        cancel_handler=handle_cancel,
    )
    runtime = PluginWorkerRuntime(ipc_client=client, bootstrap=bootstrap)
    runtime_holder["runtime"] = runtime
    try:
        runtime.initialize()
        await client.run()
    finally:
        await runtime.close()
        await close_ipc_writer(writer, worker_id=None)


def main() -> None:
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_run_worker())
    finally:
        loop.close()


if __name__ == "__main__":
    main()

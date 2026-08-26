"""SoAI - Managed media IPC worker session [backend/core/media/worker_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

from core.ipc.ndjson_rpc_loop import NdjsonRpcRequest, NdjsonRpcResponse, run_ndjson_rpc_loop
from core.ipc.ndjson_worker_handshake import connect_ndjson_ipc_worker_session
from core.timing.constants import LONG_IDLE_TIMEOUT_SEC

__all__ = ("run_media_worker_session",)


async def run_media_worker_session(
    *,
    worker_label: str,
    handle_request: Callable[[NdjsonRpcRequest], Awaitable[NdjsonRpcResponse]],
) -> None:
    reader, writer, _worker_id = await connect_ndjson_ipc_worker_session(
        worker_label=worker_label,
    )
    await run_ndjson_rpc_loop(
        reader=reader,
        writer=writer,
        idle_timeout_sec=LONG_IDLE_TIMEOUT_SEC,
        handle_request=handle_request,
    )

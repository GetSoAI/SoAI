"""SoAI - Plugin worker callback event senders [backend/plugins/worker/runtime_callbacks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

from core.types.json import JSONDict
from plugins.worker.ipc_client import PluginWorkerIpcClient

__all__ = (
    "build_json_callback",
    "build_text_callback",
)


def build_text_callback(
    ipc_client: PluginWorkerIpcClient,
    request_id: str,
) -> Callable[[str], Awaitable[None]]:
    async def callback(message: str) -> None:
        await ipc_client.send_event(
            {
                "type": "event.callback_text",
                "request_id": request_id,
                "payload": {"message": str(message)},
            },
        )

    return callback


def build_json_callback(
    ipc_client: PluginWorkerIpcClient,
    request_id: str,
) -> Callable[[JSONDict], Awaitable[None]]:
    async def callback(message: JSONDict) -> None:
        await ipc_client.send_event(
            {
                "type": "event.callback_json",
                "request_id": request_id,
                "payload": {"message": dict(message)},
            },
        )

    return callback

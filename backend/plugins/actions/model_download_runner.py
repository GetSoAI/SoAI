"""SoAI - Plugin model download runner [backend/plugins/actions/model_download_runner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.events.types_models_model_commands import ModelDownloadCommand
from core.plugins.protocols_instance import PluginInstanceProtocol
from plugins.worker.proxy import ProxyPluginInstance

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("run_plugin_download",)


async def run_plugin_download(
    plugin_instance: PluginInstanceProtocol,
    command: ModelDownloadCommand,
    shutdown_event: asyncio.Event,
    output_callback: Callable[[JSONDict], Awaitable[None]],
) -> tuple[bool, str, JSONDict | None]:
    try:
        if not isinstance(plugin_instance, ProxyPluginInstance):
            raise StateError("Model downloads require a worker-backed plugin instance.")
        download_plan = await plugin_instance.get_model_download_plan(
            command.model_id,
            command.quantization,
        )
        result = await plugin_instance.download_model(
            model_id=command.model_id,
            quantization=command.quantization,
            output_callback=output_callback,
            shutdown_event=shutdown_event,
            active_disk_reservation_plan=download_plan,
        )
    except asyncio.CancelledError:
        shutdown_event.set()
        raise
    if len(result) == 3:
        return result[0], result[1], result[2]
    return result[0], result[1], None

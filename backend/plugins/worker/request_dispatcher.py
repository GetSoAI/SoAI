"""SoAI - Plugin worker request dispatching [backend/plugins/worker/request_dispatcher.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable

from core.plugins.base_plugin import BasePlugin
from core.serialization.json import normalize_for_json
from core.types.json import JSONDict
from plugins.worker.ipc_client import PluginWorkerIpcClient
from plugins.worker.payload_fields import (
    read_bool_field,
    read_dict_field,
    read_optional_str_field,
    read_worker_request_str_field,
)
from plugins.worker.runtime_adapters import WorkerRuntimeFlags
from plugins.worker.runtime_callbacks import build_json_callback, build_text_callback
from plugins.worker.runtime_payloads import (
    class_fields,
    update_runtime_flags_from_payload,
)
from plugins.worker.serialization import decode_model_context, decode_request_context
from plugins.worker.simple_request_dispatch import dispatch_simple_plugin_call
from plugins.worker.storage_scope import WorkerStorageScopeState
from plugins.worker.stream_protocol import (
    PLUGIN_STREAM_RESPONSE_KEY,
    encode_stream_chunk_event,
    encode_stream_end_event,
)

__all__ = ("PluginWorkerRequestDispatcher",)

WORKER_FIELD_LABEL = "Worker request field"


class PluginWorkerRequestDispatcher:
    def __init__(
        self,
        *,
        ipc_client: PluginWorkerIpcClient,
        shutdown_events: dict[str, asyncio.Event],
        runtime_flags: WorkerRuntimeFlags,
        storage_scope_state: WorkerStorageScopeState,
    ) -> None:
        self._ipc_client = ipc_client
        self._shutdown_events = shutdown_events
        self._runtime_flags = runtime_flags
        self._storage_scope_state = storage_scope_state

    async def cancel_request(self, request_id: str) -> None:
        event = self._shutdown_events.get(request_id)
        if event is not None:
            event.set()

    async def dispatch(
        self,
        plugin: BasePlugin,
        *,
        request_id: str,
        method: str,
        payload: JSONDict,
    ) -> JSONDict:
        if method == "bootstrap.surface":
            return await self._surface(plugin)
        if method == "call.update_runtime_flags":
            update_runtime_flags_from_payload(self._runtime_flags, payload)
            return {"value": {}}
        if method == "call.get_default_configuration":
            return {"value": await plugin.get_default_configuration()}
        if method == "call.refresh_runtime_configuration":
            return {"value": await plugin.refresh_runtime_configuration()}
        if method == "call.get_parameter_schema":
            return {"value": await plugin.get_parameter_schema()}
        if method == "call.check_system_dependencies":
            return {"value": await plugin.check_system_dependencies()}
        if method == "call.install_backend":
            return {
                "value": await plugin.install_backend(
                    build_text_callback(self._ipc_client, request_id),
                    read_worker_request_str_field(payload, "backend_variant_id"),
                ),
            }
        if method == "call.update_backend":
            return {
                "value": await plugin.update_backend(
                    build_text_callback(self._ipc_client, request_id),
                    read_worker_request_str_field(payload, "backend_variant_id"),
                ),
            }
        if method == "call.remove_backend":
            return {
                "value": await plugin.remove_backend(
                    build_text_callback(self._ipc_client, request_id),
                    read_bool_field(payload, "delete_models", label=WORKER_FIELD_LABEL),
                ),
            }
        if method == "call.download_model":
            return await self._download_model(plugin, request_id=request_id, payload=payload)
        if method == "call.get_model_download_plan":
            return {"value": await self._get_model_download_plan(plugin, payload=payload)}
        if method == "call.delete_model":
            return await self._delete_model(plugin, request_id=request_id, payload=payload)
        if method == "call.handle_request":
            return await self._handle_inference(plugin, request_id=request_id, payload=payload)
        return await dispatch_simple_plugin_call(plugin, method=method, payload=payload)

    async def _surface(self, plugin: BasePlugin) -> JSONDict:
        plugin_class = type(plugin)
        return {
            "class_fields": class_fields(plugin_class),
            "default_configuration": await plugin.get_default_configuration(),
            "parameter_schema": await plugin.get_parameter_schema(),
            "openai_capabilities": plugin_class.get_openai_capabilities(),
            "models_directory": plugin.get_models_directory(),
            "log_file_path": plugin.get_log_file_path(),
        }

    async def _download_model(
        self,
        plugin: BasePlugin,
        *,
        request_id: str,
        payload: JSONDict,
    ) -> JSONDict:
        shutdown_event = asyncio.Event()
        self._shutdown_events[request_id] = shutdown_event
        try:
            with self._storage_scope_state.active_scope(
                read_optional_str_field(
                    payload,
                    "active_disk_reservation_scope",
                    label=WORKER_FIELD_LABEL,
                ),
                read_optional_str_field(
                    payload,
                    "active_disk_reservation_root",
                    label=WORKER_FIELD_LABEL,
                ),
            ):
                result = await plugin.download_model(
                    read_worker_request_str_field(payload, "model_id"),
                    read_optional_str_field(payload, "quantization", label=WORKER_FIELD_LABEL),
                    build_json_callback(self._ipc_client, request_id),
                    shutdown_event,
                )
        finally:
            self._shutdown_events.pop(request_id, None)
        return {"value": normalize_for_json(result)}

    async def _get_model_download_plan(
        self,
        plugin: BasePlugin,
        *,
        payload: JSONDict,
    ) -> JSONDict:
        result = await plugin.get_model_download_plan(
            read_worker_request_str_field(payload, "model_id"),
            read_optional_str_field(payload, "quantization", label=WORKER_FIELD_LABEL),
        )
        return dict(result)

    async def _delete_model(
        self,
        plugin: BasePlugin,
        *,
        request_id: str,
        payload: JSONDict,
    ) -> JSONDict:
        shutdown_event = asyncio.Event()
        self._shutdown_events[request_id] = shutdown_event
        try:
            result = await plugin.delete_model(
                read_dict_field(payload, "model_info", label=WORKER_FIELD_LABEL),
                build_json_callback(self._ipc_client, request_id),
                shutdown_event,
            )
        finally:
            self._shutdown_events.pop(request_id, None)
        return {"value": normalize_for_json(result)}

    async def _handle_inference(
        self,
        plugin: BasePlugin,
        *,
        request_id: str,
        payload: JSONDict,
    ) -> JSONDict:
        result = await plugin.handle_request(
            read_dict_field(payload, "request_json", label=WORKER_FIELD_LABEL),
            decode_request_context(read_dict_field(payload, "context", label=WORKER_FIELD_LABEL)),
            decode_model_context(
                read_dict_field(payload, "model_context", label=WORKER_FIELD_LABEL),
            ),
        )
        if isinstance(result, AsyncIterable):
            async for chunk in result:
                await self._ipc_client.send_event(
                    encode_stream_chunk_event(request_id=request_id, chunk=chunk),
                )
            await self._ipc_client.send_event(encode_stream_end_event(request_id=request_id))
            return {PLUGIN_STREAM_RESPONSE_KEY: True}
        return {"value": normalize_for_json(result)}

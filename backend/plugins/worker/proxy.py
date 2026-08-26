"""SoAI - Parent-side proxy plugin instance backed by worker IPC [backend/plugins/worker/proxy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable, Awaitable, Callable, Sequence

from core.plugins.protocols_instance import (
    ModelContextProtocol,
    RemoteModelSearchResultProtocol,
)
from core.runtime.protocols import RuntimeFlagsViewProtocol
from core.runtime.request_context import RequestContext
from core.types.json import JSONDict
from plugins.worker.bootstrap_payload import build_plugin_worker_runtime_flags_payload
from plugins.worker.proxy_dependencies import ProxyPluginInstanceDependencies
from plugins.worker.proxy_invocation import ProxyInvocationClient
from plugins.worker.proxy_payloads import json_dict_list
from plugins.worker.proxy_response_validation import (
    require_bool_text_tuple,
    require_discovered_models,
    require_plugin_worker_bool,
    require_process_ids,
)
from plugins.worker.proxy_static_surface import ProxyPluginStaticSurface
from plugins.worker.proxy_surface_fields import apply_proxy_surface_fields
from plugins.worker.serialization import encode_model_context, encode_request_context
from plugins.worker.stream_protocol import is_stream_requested_payload

__all__ = ("ProxyPluginInstance", "ProxyPluginInstanceDependencies")


class ProxyPluginInstance(ProxyPluginStaticSurface):
    def __init__(self, deps: ProxyPluginInstanceDependencies) -> None:
        plugin_name = deps.plugin_name
        self.plugin_name = plugin_name
        self._calls = ProxyInvocationClient(
            plugin_name=plugin_name,
            worker_id=deps.worker_id,
            server=deps.server,
        )
        self._surface = deps.surface
        self._worker_id = deps.worker_id
        self._download_reservation_scope_factory = deps.download_reservation_scope_factory
        self.install_path: str | None = deps.install_path
        self.openai_capabilities: JSONDict = dict(deps.surface.openai_capabilities)
        apply_proxy_surface_fields(self, deps.surface)

    def get_models_directory(self) -> str:
        return self._surface.models_directory

    def get_log_file_path(self) -> str | None:
        return self._surface.log_file_path

    async def get_default_configuration(self) -> JSONDict:
        return await self._calls.dict_call("call.get_default_configuration", {})

    async def refresh_runtime_configuration(self) -> JSONDict:
        return await self._calls.dict_call("call.refresh_runtime_configuration", {})

    async def update_runtime_flags(self, runtime_flags: RuntimeFlagsViewProtocol) -> None:
        payload: JSONDict = {
            "runtime_flags": build_plugin_worker_runtime_flags_payload(runtime_flags),
        }
        await self._calls.value_call("call.update_runtime_flags", payload)

    async def get_parameter_schema(self) -> JSONDict:
        return await self._calls.dict_call("call.get_parameter_schema", {})

    async def check_system_dependencies(self) -> tuple[bool, str]:
        value = await self._calls.value_call("call.check_system_dependencies", {})
        return require_bool_text_tuple(value, label="dependency")

    async def install_backend(
        self,
        output_callback: Callable[[str], Awaitable[None] | None],
        backend_variant_id: str,
    ) -> bool:
        value = await self._calls.call_with_text_callback(
            "call.install_backend",
            {"backend_variant_id": backend_variant_id},
            output_callback,
        )
        return require_plugin_worker_bool(value, label="install-backend")

    async def update_backend(
        self,
        output_callback: Callable[[str], Awaitable[None] | None],
        backend_variant_id: str,
    ) -> bool:
        value = await self._calls.call_with_text_callback(
            "call.update_backend",
            {"backend_variant_id": backend_variant_id},
            output_callback,
        )
        return require_plugin_worker_bool(value, label="update-backend")

    async def remove_backend(
        self,
        output_callback: Callable[[str], Awaitable[None] | None],
        delete_models: bool,
    ) -> bool:
        value = await self._calls.call_with_text_callback(
            "call.remove_backend",
            {"delete_models": delete_models},
            output_callback,
        )
        return require_plugin_worker_bool(value, label="remove-backend")

    async def discover_models(
        self,
        existing_models: dict[str, JSONDict] | None = None,
    ) -> dict[str, JSONDict] | None:
        value = await self._calls.value_call(
            "call.discover_models",
            {"existing_models": existing_models or {}},
        )
        return require_discovered_models(value)

    async def get_status(self) -> JSONDict:
        return await self._calls.dict_call("call.get_status", {})

    async def get_available_variants(self, model_id: str) -> list[JSONDict]:
        value = await self._calls.value_call(
            "call.get_available_variants",
            {"model_id": model_id},
        )
        return json_dict_list(value)

    async def get_backend_process_pids(self) -> list[int]:
        value = await self._calls.value_call("call.get_backend_process_pids", {})
        return require_process_ids(value)

    async def health_ping(self) -> tuple[bool, str]:
        value = await self._calls.value_call("call.health_ping", {})
        return require_bool_text_tuple(value, label="health")

    def start(self) -> Awaitable[bool]:
        return self._calls.bool_call("call.start", {})

    async def start_with_model(
        self,
        model_context: ModelContextProtocol,
        context: RequestContext,
    ) -> bool:
        return await self._calls.bool_call(
            "call.start_with_model",
            {
                "model_context": encode_model_context(model_context),
                "context": encode_request_context(context),
            },
        )

    async def stop(self) -> bool:
        return await self._calls.bool_call("call.stop", {})

    async def cancel_task(self, task_id: str, context: RequestContext) -> tuple[bool, str]:
        value = await self._calls.value_call(
            "call.cancel_task",
            {"task_id": task_id, "context": encode_request_context(context)},
        )
        return require_bool_text_tuple(value, label="cancellation")

    async def cleanup_partial_installation(self) -> None:
        await self._calls.value_call("call.cleanup_partial_installation", {})

    async def load_model_in_service(
        self,
        model_context: ModelContextProtocol,
        context: RequestContext,
    ) -> bool:
        return await self._calls.bool_call(
            "call.load_model_in_service",
            {
                "model_context": encode_model_context(model_context),
                "context": encode_request_context(context),
            },
        )

    async def unload_model_in_service(self, universal_id: str) -> bool:
        return await self._calls.bool_call(
            "call.unload_model_in_service",
            {"universal_id": universal_id},
        )

    async def download_model(
        self,
        model_id: str,
        quantization: str | None,
        output_callback: Callable[[JSONDict], Awaitable[None]],
        shutdown_event: asyncio.Event,
        active_disk_reservation_plan: JSONDict | None = None,
    ) -> tuple[bool, str] | tuple[bool, str, JSONDict | None]:
        with self._download_reservation_scope_factory(
            self._worker_id,
            active_disk_reservation_plan,
        ) as active_reservation_scope:
            payload: JSONDict = {"model_id": model_id, "quantization": quantization}
            if active_reservation_scope is not None:
                active_reservation_id, active_reservation_root = active_reservation_scope
                payload["active_disk_reservation_scope"] = active_reservation_id
                payload["active_disk_reservation_root"] = active_reservation_root
            return await self._calls.cancellable_json_tuple_call(
                "call.download_model",
                payload,
                output_callback,
                shutdown_event,
            )

    async def get_model_download_plan(self, model_id: str, quantization: str | None) -> JSONDict:
        payload: JSONDict = {"model_id": model_id, "quantization": quantization}
        return await self._calls.dict_call("call.get_model_download_plan", payload)

    async def delete_model(
        self,
        model_info: JSONDict,
        output_callback: Callable[[JSONDict], Awaitable[None]],
        shutdown_event: asyncio.Event,
    ) -> tuple[bool, str]:
        value = await self._calls.cancellable_json_tuple_call(
            "call.delete_model",
            {"model_info": dict(model_info)},
            output_callback,
            shutdown_event,
        )
        return require_bool_text_tuple(value, label="delete-model")

    async def handle_request(
        self,
        request_json: JSONDict,
        context: RequestContext,
        model_context: ModelContextProtocol,
    ) -> JSONDict | AsyncIterable[bytes]:
        return await self._calls.stream_call(
            "call.handle_request",
            {
                "request_json": dict(request_json),
                "context": encode_request_context(context),
                "model_context": encode_model_context(model_context),
            },
            expected_stream=is_stream_requested_payload(request_json),
        )

    async def count_prompt_tokens(
        self,
        request_json: JSONDict,
        context: RequestContext,
        model_context: ModelContextProtocol,
    ) -> JSONDict:
        return await self._calls.dict_call(
            "call.count_prompt_tokens",
            {
                "request_json": dict(request_json),
                "context": encode_request_context(context),
                "model_context": encode_model_context(model_context),
            },
        )

    async def handle_embedding_request(
        self,
        request_json: JSONDict,
        context: RequestContext,
        model_context: ModelContextProtocol,
    ) -> JSONDict:
        return await self._calls.dict_call(
            "call.handle_embedding_request",
            {
                "request_json": dict(request_json),
                "context": encode_request_context(context),
                "model_context": encode_model_context(model_context),
            },
        )

    async def check_for_backend_update(self) -> JSONDict:
        return await self._calls.dict_call("call.check_for_backend_update", {})

    async def search_remote_models(
        self,
        query: str,
        limit: int = 10,
    ) -> Sequence[RemoteModelSearchResultProtocol]:
        value = await self._calls.value_call(
            "call.search_remote_models",
            {"query": query, "limit": limit},
        )
        return json_dict_list(value)

"""SoAI - Plugin worker runtime method dispatcher [backend/plugins/worker/runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

import httpx2

from core.config.runtime_config import Config
from core.config.value_validation import is_config_dict
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError, StateError
from core.errors.http_recoverable import HTTP_RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import UNEXPECTED_RUNTIME_EXCEPTIONS
from core.files.path_resolver import ConfigFilesPathResolver
from core.logging.trace import get_logger
from core.plugins.base_plugin import BasePlugin
from core.plugins.runtime_services import PluginRuntimeServices
from core.runtime.network_http_client import create_guarded_async_http_client
from core.types.json import JSONDict
from plugins.worker.host_services import (
    WorkerHardwareAdapter,
    WorkerModelRegistryAdapter,
    WorkerPluginManagerAdapter,
)
from plugins.worker.host_storage_services import WorkerStorageAdapter
from plugins.worker.ipc_client import PluginWorkerIpcClient
from plugins.worker.payload_fields import (
    read_dict_field,
    read_optional_str_field,
    read_worker_request_str_field,
)
from plugins.worker.request_dispatcher import PluginWorkerRequestDispatcher
from plugins.worker.runtime_adapters import (
    WorkerEventBusAdapter,
    WorkerMetricsAdapter,
)
from plugins.worker.runtime_failure_reporting import WorkerRuntimeFailureReporter
from plugins.worker.runtime_loader import load_plugin_class
from plugins.worker.runtime_payloads import runtime_flags_from_bootstrap
from plugins.worker.storage_scope import WorkerStorageScopeState

__all__ = ("PluginWorkerRuntime",)

LOGGER_NAME = "SoAI.plugins.worker.runtime"
OPERATION_WORKER_HANDLE_REQUEST = "plugins.worker.runtime.handle_request"
OPERATION_WORKER_FLUSH_METRICS = "plugins.worker.runtime.flush_metrics"
WORKER_FIELD_LABEL = "Worker request field"


class PluginWorkerRuntime:
    def __init__(
        self,
        *,
        ipc_client: PluginWorkerIpcClient,
        bootstrap: JSONDict,
    ) -> None:
        self._ipc_client = ipc_client
        self._bootstrap = dict(bootstrap)
        self._plugin_name = read_worker_request_str_field(self._bootstrap, "plugin_name")
        self._runtime_flags = runtime_flags_from_bootstrap(self._bootstrap)
        config_snapshot = read_dict_field(
            self._bootstrap,
            "config_snapshot",
            label=WORKER_FIELD_LABEL,
        )
        self._config = _build_worker_config(config_snapshot)
        self._http_client: httpx2.AsyncClient = create_guarded_async_http_client(
            self._runtime_flags,
            source=f"plugin_worker.{self._plugin_name}",
            trust_env=self._config.get_bool("MODELS.ROUTING.HTTP_CLIENT_TRUST_ENV"),
        )
        self._metrics = WorkerMetricsAdapter(plugin_name=self._plugin_name)
        self._plugin: BasePlugin | None = None
        self._shutdown_events: dict[str, asyncio.Event] = {}
        self._storage_scope_state = WorkerStorageScopeState()
        self._dispatcher = PluginWorkerRequestDispatcher(
            ipc_client=self._ipc_client,
            shutdown_events=self._shutdown_events,
            runtime_flags=self._runtime_flags,
            storage_scope_state=self._storage_scope_state,
        )

    def initialize(self) -> None:
        plugin_package_root = read_worker_request_str_field(
            self._bootstrap,
            "plugin_package_root",
        )
        plugin_entrypoint_path = read_worker_request_str_field(
            self._bootstrap,
            "plugin_entrypoint_path",
        )
        plugin_config = read_dict_field(
            self._bootstrap,
            "plugin_config",
            label=WORKER_FIELD_LABEL,
        )
        runtime_services = PluginRuntimeServices(
            metrics_manager=self._metrics,
            model_registry=WorkerModelRegistryAdapter(
                self._ipc_client.request_host,
                plugin_name=self._plugin_name,
            ),
            plugin_manager=WorkerPluginManagerAdapter(
                self._ipc_client.request_host,
                plugin_name=self._plugin_name,
            ),
            runtime_reporter=WorkerRuntimeFailureReporter(
                self._ipc_client.request_host,
                plugin_name=self._plugin_name,
            ),
            hw_manager=WorkerHardwareAdapter(self._ipc_client.request_host),
            storage_manager=WorkerStorageAdapter(
                self._ipc_client.request_host,
                storage_scope_state=self._storage_scope_state,
            ),
            runtime_flags=self._runtime_flags,
            files=ConfigFilesPathResolver(self._config),
            plugin_config=plugin_config,
            http_client=self._http_client,
            install_path=read_optional_str_field(
                self._bootstrap,
                "install_path",
                label=WORKER_FIELD_LABEL,
            ),
        )
        plugin_class = load_plugin_class(
            self._plugin_name,
            plugin_package_root=plugin_package_root,
            plugin_entrypoint_path=plugin_entrypoint_path,
        )
        self._plugin = plugin_class(
            plugin_name=self._plugin_name,
            config=self._config,
            event_bus=WorkerEventBusAdapter(
                self._ipc_client.request_host,
                plugin_name=self._plugin_name,
            ),
            runtime=runtime_services,
        )

    async def close(self) -> None:
        await self._http_client.aclose()

    async def handle_request(self, request_id: str, method: str, payload: JSONDict) -> JSONDict:
        plugin = self._require_plugin()
        suppress_flush_failure = False
        try:
            return await self._dispatcher.dispatch(
                plugin,
                request_id=request_id,
                method=method,
                payload=payload,
            )
        except HTTP_RECOVERABLE_EXCEPTIONS:
            suppress_flush_failure = True
            raise
        except SoAIError as exception:
            suppress_flush_failure = True
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="Plugin worker request dispatch failed.",
                operation=OPERATION_WORKER_HANDLE_REQUEST,
                details={"request_id": request_id, "method": method},
                level="warning",
            )
            raise
        except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
            suppress_flush_failure = True
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_WORKER_HANDLE_REQUEST,
                details={"request_id": request_id, "method": method},
            )
            log_exception(
                get_logger(LOGGER_NAME),
                coerced,
                message="Plugin worker request dispatch failed.",
                operation=OPERATION_WORKER_HANDLE_REQUEST,
                details={"request_id": request_id, "method": method},
                level="warning",
            )
            raise coerced from exception
        except asyncio.CancelledError:
            suppress_flush_failure = True
            raise
        finally:
            await self._flush_metrics(
                request_id=request_id,
                method=method,
                suppress_failure=suppress_flush_failure,
            )

    async def cancel_request(self, request_id: str) -> None:
        await self._dispatcher.cancel_request(request_id)

    def _require_plugin(self) -> BasePlugin:
        if self._plugin is None:
            raise StateError("Plugin worker is not initialized.")
        return self._plugin

    async def _flush_metrics(
        self,
        *,
        request_id: str,
        method: str,
        suppress_failure: bool,
    ) -> None:
        try:
            await self._metrics.flush(self._ipc_client.request_host)
        except HTTP_RECOVERABLE_EXCEPTIONS as exception:
            if not suppress_failure:
                raise
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="Plugin worker metrics flush failed after request failure.",
                operation=OPERATION_WORKER_FLUSH_METRICS,
                details={"request_id": request_id, "method": method},
                level="warning",
            )
        except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_WORKER_FLUSH_METRICS,
                details={"request_id": request_id, "method": method},
            )
            if not suppress_failure:
                raise coerced from exception
            log_exception(
                get_logger(LOGGER_NAME),
                coerced,
                message="Plugin worker metrics flush failed after request failure.",
                operation=OPERATION_WORKER_FLUSH_METRICS,
                details={"request_id": request_id, "method": method},
                level="warning",
            )


def _build_worker_config(config_snapshot: JSONDict) -> Config:
    if not is_config_dict(config_snapshot):
        raise StateError("Plugin worker config snapshot is invalid.")
    system_section_value = config_snapshot.get("SYSTEM")
    if not is_config_dict(system_section_value):
        raise StateError("Plugin worker SYSTEM config snapshot is invalid.")
    paths_section_value = system_section_value.get("PATHS")
    if not is_config_dict(paths_section_value):
        raise StateError("Plugin worker SYSTEM.PATHS config snapshot is invalid.")
    base_path_value = paths_section_value.get("BASE")
    if not isinstance(base_path_value, str) or not base_path_value.strip():
        raise StateError("Plugin worker SYSTEM.PATHS.BASE config snapshot is invalid.")
    base_path = base_path_value
    return Config(config_snapshot, main_app_base_dir=base_path)

"""SoAI - Parent-side plugin worker host request routing [backend/plugins/worker/host_router.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable, Generator
from contextlib import contextmanager

from core.errors.exceptions import ValidationError
from core.events.types_plugins import ProviderStatusUpdatedEvent
from core.serialization.json import normalize_for_json
from core.types.json import JSONDict, JSONValue
from plugins.manager.configuration import (
    get_plugin_configuration,
    set_plugin_configuration,
)
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)
from plugins.worker.host_metrics import record_worker_metrics_batch
from plugins.worker.host_payloads import (
    enforce_plugin_scope,
)
from plugins.worker.host_storage import PluginWorkerHostStorageReservations
from plugins.worker.payload_fields import (
    read_bool_field,
    read_dict_field,
    read_dict_list_field,
    read_int_field,
    read_optional_int_field,
    read_optional_str_field,
    read_required_named_str_field,
    read_str_list_field,
)
from plugins.worker.runtime_failure_reporting import report_managed_runtime_failure

__all__ = ("PluginWorkerHostRouter",)

HOST_FIELD_LABEL = "Worker host request field"


class PluginWorkerHostRouter:
    def __init__(
        self,
        manager: PluginManagerRuntimeProtocol,
        *,
        resolve_plugin_name_for_worker: Callable[[int], Awaitable[str | None]],
    ) -> None:
        self._manager = manager
        self._resolve_plugin_name_for_worker = resolve_plugin_name_for_worker
        self._storage_reservations = PluginWorkerHostStorageReservations()

    async def handle_request(self, worker_id: int, method: str, payload: JSONDict) -> JSONDict:
        resolved_plugin_name = await self._resolve_plugin_name_for_worker(worker_id)
        if resolved_plugin_name is None:
            raise ValidationError("Plugin worker host request received unknown worker_id.")
        value: JSONValue
        if method == "plugin_manager.get_plugin_configuration":
            enforce_plugin_scope(payload, resolved_plugin_name)
            value = await get_plugin_configuration(self._manager, resolved_plugin_name)
        elif method == "plugin_manager.set_plugin_configuration":
            enforce_plugin_scope(payload, resolved_plugin_name)
            value = await set_plugin_configuration(
                self._manager,
                resolved_plugin_name,
                read_dict_field(payload, "config_data", label=HOST_FIELD_LABEL),
                apply_runtime=False,
            )
        elif method == "hardware.get_system_capabilities":
            value = (
                await self._manager.dependencies.infrastructure.hw_manager.get_system_capabilities()
            )
        elif method == "hardware.get_system_info":
            include_gpu_capabilities_value = payload.get("include_gpu_capabilities")
            include_gpu_capabilities = (
                True
                if include_gpu_capabilities_value is None
                else read_bool_field(
                    payload,
                    "include_gpu_capabilities",
                    label=HOST_FIELD_LABEL,
                )
            )
            value = await self._manager.dependencies.infrastructure.hw_manager.get_system_info(
                components=read_str_list_field(payload, "components", label=HOST_FIELD_LABEL),
                cache=read_bool_field(payload, "cache", label=HOST_FIELD_LABEL),
                include_gpu_capabilities=include_gpu_capabilities,
            )
        elif method == "event.provider_status_updated":
            enforce_plugin_scope(payload, resolved_plugin_name)
            await self._manager.dependencies.infrastructure.event_bus.publish(
                ProviderStatusUpdatedEvent(
                    plugin_name=resolved_plugin_name,
                    provider_id=read_required_named_str_field(
                        payload,
                        "provider_id",
                        label=HOST_FIELD_LABEL,
                    ),
                    new_status=read_required_named_str_field(
                        payload,
                        "new_status",
                        label=HOST_FIELD_LABEL,
                    ),
                    error=read_optional_str_field(payload, "error", label=HOST_FIELD_LABEL),
                ),
            )
            value = None
        elif method == "runtime.report_failure":
            enforce_plugin_scope(payload, resolved_plugin_name)
            await report_managed_runtime_failure(
                self._manager,
                plugin_name=resolved_plugin_name,
                component=read_required_named_str_field(
                    payload,
                    "component",
                    label=HOST_FIELD_LABEL,
                ),
                failure_code=read_required_named_str_field(
                    payload,
                    "failure_code",
                    label=HOST_FIELD_LABEL,
                ),
                exit_status=read_optional_int_field(
                    payload,
                    "exit_status",
                    label=HOST_FIELD_LABEL,
                ),
            )
            value = None
        elif method == "metrics.record_batch":
            record_worker_metrics_batch(
                self._manager.dependencies.infrastructure.metrics_manager,
                resolved_plugin_name=resolved_plugin_name,
                records=read_dict_list_field(payload, "records", label=HOST_FIELD_LABEL),
            )
            value = None
        elif method == "storage.reserve_disk_space":
            value = self._storage_reservations.reserve_disk_space(
                worker_id=worker_id,
                storage_manager=self._manager.dependencies.infrastructure.storage_manager,
                payload=payload,
            )
        elif method == "storage.claim_reservation":
            value = self._storage_reservations.claim_reservation(
                worker_id=worker_id,
                payload=payload,
            )
        elif method == "storage.commit_claim":
            self._storage_reservations.commit_claim(worker_id=worker_id, payload=payload)
            value = None
        elif method == "storage.rollback_claim":
            self._storage_reservations.rollback_claim(worker_id=worker_id, payload=payload)
            value = None
        elif method == "storage.release_reservation":
            self._storage_reservations.release_reservation(worker_id=worker_id, payload=payload)
            value = None
        else:
            value = await self._handle_model_registry(method, payload, resolved_plugin_name)
        return {"value": normalize_for_json(value)}

    def release_worker_reservations(self, worker_id: int) -> None:
        self._storage_reservations.release_worker_reservations(worker_id)

    @contextmanager
    def download_reservation_scope(
        self,
        worker_id: int,
        plan: JSONDict | None,
    ) -> Generator[tuple[str, str] | None]:
        if plan is None:
            yield None
            return
        required_bytes = read_int_field(plan, "required_bytes", label=HOST_FIELD_LABEL, default=0)
        if required_bytes <= 0:
            yield None
            return
        reservation_root = read_optional_str_field(plan, "reservation_root", label=HOST_FIELD_LABEL)
        if reservation_root is None:
            reservation_root = read_required_named_str_field(
                plan,
                "reservation_path",
                label=HOST_FIELD_LABEL,
            )
        with self._manager.dependencies.infrastructure.storage_manager.reserve_disk_space(
            path=reservation_root,
            required_bytes=required_bytes,
            operation="plugins.model_download.declared_plan",
            details={
                "reservation_root": reservation_root,
                "required_bytes": required_bytes,
            },
        ) as reservation:
            reservation_id = self._storage_reservations.register_reservation(
                worker_id=worker_id,
                lease=reservation,
            )
            try:
                yield (reservation_id, reservation_root)
            finally:
                self._storage_reservations.release_reservation_id(
                    worker_id=worker_id,
                    reservation_id=reservation_id,
                )

    async def _handle_model_registry(
        self,
        method: str,
        payload: JSONDict,
        resolved_plugin_name: str,
    ) -> JSONValue:
        registry = self._manager.dependencies.models.model_registry
        if method == "model_registry.model_get_info":
            universal_id = read_required_named_str_field(
                payload,
                "universal_id",
                label=HOST_FIELD_LABEL,
            )
            model_info = await registry.model_get_info(universal_id)
            if model_info is None:
                return None
            model_plugin_value = model_info.get("plugin")
            if not isinstance(model_plugin_value, str) or not model_plugin_value:
                raise ValidationError("Model record is missing plugin field.")
            if model_plugin_value != resolved_plugin_name:
                return None
            return model_info
        if method == "model_registry.get_external_provider_for_model":
            universal_id = read_required_named_str_field(
                payload,
                "universal_id",
                label=HOST_FIELD_LABEL,
            )
            model_info = await registry.model_get_info(universal_id)
            if model_info is None:
                return None
            model_plugin_value = model_info.get("plugin")
            if not isinstance(model_plugin_value, str) or not model_plugin_value:
                raise ValidationError("Model record is missing plugin field.")
            if model_plugin_value != resolved_plugin_name:
                raise ValidationError("Worker host request cannot access other plugin models.")
            provider = await registry.get_external_provider_for_model(universal_id)
            return normalize_for_json(provider)
        if method == "model_registry.provider_get_external":
            provider = await registry.provider_get_external(
                read_required_named_str_field(payload, "provider_id", label=HOST_FIELD_LABEL),
                decrypt_key=read_bool_field(payload, "decrypt_key", label=HOST_FIELD_LABEL),
            )
            if provider is None:
                return None
            plugin_name_value = provider.get("plugin_name")
            if not isinstance(plugin_name_value, str) or not plugin_name_value:
                raise ValidationError("External provider record is missing plugin_name.")
            if plugin_name_value != resolved_plugin_name:
                raise ValidationError("Worker host request cannot access other plugin providers.")
            return normalize_for_json(provider)
        if method == "model_registry.provider_list_for_plugin":
            enforce_plugin_scope(payload, resolved_plugin_name)
            providers = await registry.provider_list_for_plugin(resolved_plugin_name)
            return normalize_for_json(providers)
        if method == "model_registry.update_provider_status":
            provider_id = read_required_named_str_field(
                payload,
                "provider_id",
                label=HOST_FIELD_LABEL,
            )
            provider = await registry.provider_get_external(provider_id, decrypt_key=False)
            if provider is None:
                raise ValidationError("External provider not found.")
            plugin_name_value = provider.get("plugin_name")
            if not isinstance(plugin_name_value, str) or not plugin_name_value:
                raise ValidationError("External provider record is missing plugin_name.")
            if plugin_name_value != resolved_plugin_name:
                raise ValidationError("Worker host request cannot access other plugin providers.")
            await registry.update_provider_status(
                provider_id,
                read_required_named_str_field(payload, "status", label=HOST_FIELD_LABEL),
                read_optional_str_field(payload, "error", label=HOST_FIELD_LABEL),
            )
            return None
        if method == "model_registry.upsert_plugin_managed_provider":
            enforce_plugin_scope(payload, resolved_plugin_name)
            provider = await registry.upsert_plugin_managed_provider(
                resolved_plugin_name,
                read_required_named_str_field(payload, "provider_id", label=HOST_FIELD_LABEL),
                read_required_named_str_field(payload, "name", label=HOST_FIELD_LABEL),
                read_required_named_str_field(payload, "url", label=HOST_FIELD_LABEL),
            )
            return normalize_for_json(provider)
        raise ValidationError(f"Unsupported plugin worker host method '{method}'.")

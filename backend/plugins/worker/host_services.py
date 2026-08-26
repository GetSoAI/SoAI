"""SoAI - Plugin worker asynchronous host service adapters [backend/plugins/worker/host_services.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

from core.errors.exceptions import ValidationError
from core.plugins.name_validation import require_plugin_name
from core.types.json import JSONDict, JSONValue
from core.validation.record_fields import require_json_object, require_json_object_list

__all__ = (
    "WorkerHardwareAdapter",
    "WorkerModelRegistryAdapter",
    "WorkerPluginManagerAdapter",
)


class WorkerPluginManagerAdapter:
    def __init__(
        self,
        request: Callable[[str, JSONDict], Awaitable[JSONDict]],
        *,
        plugin_name: str,
    ) -> None:
        self._request = request
        self._plugin_name = plugin_name

    async def get_plugin_configuration(self, plugin_name: str) -> JSONDict:
        normalized_plugin_name = require_plugin_name(plugin_name)
        if normalized_plugin_name != self._plugin_name:
            raise ValidationError("Plugin worker cannot access configuration for other plugins.")
        result = await self._request(
            "plugin_manager.get_plugin_configuration",
            {"plugin_name": self._plugin_name},
        )
        value = result.get("value")
        return _require_dict(value, "plugin configuration")

    async def set_plugin_configuration(self, plugin_name: str, config_data: JSONDict) -> bool:
        normalized_plugin_name = require_plugin_name(plugin_name)
        if normalized_plugin_name != self._plugin_name:
            raise ValidationError("Plugin worker cannot update configuration for other plugins.")
        result = await self._request(
            "plugin_manager.set_plugin_configuration",
            {"plugin_name": self._plugin_name, "config_data": dict(config_data)},
        )
        value = result.get("value")
        if not isinstance(value, bool):
            raise ValidationError("Host service configuration update result must be a boolean.")
        return value


class WorkerHardwareAdapter:
    def __init__(self, request: Callable[[str, JSONDict], Awaitable[JSONDict]]) -> None:
        self._request = request

    async def get_system_capabilities(self) -> JSONDict:
        result = await self._request("hardware.get_system_capabilities", {})
        value = result.get("value")
        return _require_dict(value, "hardware capabilities")

    async def get_system_info(
        self,
        components: list[str] | None = None,
        cache: bool = True,
        include_gpu_capabilities: bool = True,
    ) -> JSONDict:
        result = await self._request(
            "hardware.get_system_info",
            {
                "components": list(components or []),
                "cache": cache,
                "include_gpu_capabilities": include_gpu_capabilities,
            },
        )
        value = result.get("value")
        return _require_dict(value, "hardware info")


class WorkerModelRegistryAdapter:
    def __init__(
        self,
        request: Callable[[str, JSONDict], Awaitable[JSONDict]],
        *,
        plugin_name: str,
    ) -> None:
        self._request = request
        self._plugin_name = plugin_name

    async def model_get_info(self, universal_id: str) -> JSONDict | None:
        return _dict_or_none(
            await self._request("model_registry.model_get_info", {"universal_id": universal_id}),
        )

    async def get_external_provider_for_model(self, universal_id: str) -> JSONDict | None:
        return _dict_or_none(
            await self._request(
                "model_registry.get_external_provider_for_model",
                {"universal_id": universal_id},
            ),
        )

    async def provider_get_external(
        self,
        provider_id: str,
        decrypt_key: bool = False,
    ) -> JSONDict | None:
        return _dict_or_none(
            await self._request(
                "model_registry.provider_get_external",
                {"provider_id": provider_id, "decrypt_key": decrypt_key},
            ),
        )

    async def provider_list_for_plugin(self, plugin_name: str) -> list[JSONDict]:
        normalized_plugin_name = require_plugin_name(plugin_name)
        if normalized_plugin_name != self._plugin_name:
            raise ValidationError("Plugin worker cannot list providers for other plugins.")
        result = await self._request(
            "model_registry.provider_list_for_plugin",
            {"plugin_name": self._plugin_name},
        )
        return require_json_object_list(
            result.get("value"),
            label="Host service provider list response",
            build_error=ValidationError,
            invalid_message="Host service provider list response must be a list.",
            entry_message="Host service provider list response must contain only JSON objects.",
        )

    async def update_provider_status(
        self,
        provider_id: str,
        status: str,
        error: str | None = None,
    ) -> None:
        await self._request(
            "model_registry.update_provider_status",
            {"provider_id": provider_id, "status": status, "error": error},
        )

    async def upsert_plugin_managed_provider(
        self,
        plugin_name: str,
        provider_id: str,
        name: str,
        url: str,
    ) -> JSONDict | None:
        normalized_plugin_name = require_plugin_name(plugin_name)
        if normalized_plugin_name != self._plugin_name:
            raise ValidationError("Plugin worker cannot mutate providers for other plugins.")
        return _dict_or_none(
            await self._request(
                "model_registry.upsert_plugin_managed_provider",
                {
                    "plugin_name": self._plugin_name,
                    "provider_id": provider_id,
                    "name": name,
                    "url": url,
                },
            ),
        )


def _dict_or_none(result: JSONDict) -> JSONDict | None:
    value: JSONValue | None = result.get("value")
    if value is None:
        return None
    return _require_dict(value, "response value")


def _require_dict(value: JSONValue | None, label: str) -> JSONDict:
    return require_json_object(
        value,
        label=f"Host service {label}",
        build_error=ValidationError,
        invalid_message=f"Host service {label} must be a JSON object.",
    )

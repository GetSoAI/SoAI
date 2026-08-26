"""SoAI - Plugin worker host service adapters [backend/plugins/worker/runtime_adapters.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from core.errors.exceptions import ValidationError
from core.events.types_base import Event
from core.events.types_plugins import ProviderStatusUpdatedEvent
from core.plugins.name_validation import require_plugin_name
from core.runtime.flags_service import (
    RuntimeFlagsService,
    RuntimeFlagsServiceDependencies,
)
from core.types.json import JSONDict

__all__ = (
    "WorkerEventBusAdapter",
    "WorkerMetricsAdapter",
    "WorkerRuntimeFlags",
)


class WorkerRuntimeFlags(RuntimeFlagsService):
    def __init__(
        self,
        *,
        host_system_actions_disabled: bool,
        hardware_mutation_disabled: bool,
        offline_mode: bool,
        block_private_network_egress: bool,
        dns_validation_timeout_sec: float,
        host_management_available: bool,
    ) -> None:
        super().__init__(
            RuntimeFlagsServiceDependencies(
                initial_host_system_actions_disabled=host_system_actions_disabled,
                initial_hardware_mutation_disabled=hardware_mutation_disabled,
                initial_offline_mode=offline_mode,
                initial_block_private_network_egress=block_private_network_egress,
                dns_validation_timeout_sec=dns_validation_timeout_sec,
                initial_host_management_available=host_management_available,
            ),
        )


class WorkerEventBusAdapter:
    def __init__(
        self,
        request: Callable[[str, JSONDict], Awaitable[JSONDict]],
        *,
        plugin_name: str,
    ) -> None:
        self._request = request
        self._plugin_name = plugin_name

    async def publish(self, event: Event) -> None:
        if isinstance(event, ProviderStatusUpdatedEvent):
            await self._request(
                "event.provider_status_updated",
                {
                    "plugin_name": self._plugin_name,
                    "provider_id": event.provider_id,
                    "new_status": event.new_status,
                    "error": event.error,
                },
            )
            return
        raise ValidationError(f"Unsupported worker event publication: {type(event).__name__}")


class WorkerMetricsAdapter:
    def __init__(self, *, plugin_name: str) -> None:
        self._plugin_name = plugin_name
        self._records: list[JSONDict] = []
        self._flush_lock = asyncio.Lock()

    def increment_counter(self, *keys: str, value: int = 1) -> None:
        self._records.append({"operation": "increment_counter", "keys": list(keys), "value": value})

    def set_gauge(self, *keys: str, value: float) -> None:
        self._records.append({"operation": "set_gauge", "keys": list(keys), "value": value})

    def record_timing(self, *keys: str, duration_ms: float) -> None:
        self._records.append(
            {"operation": "record_timing", "keys": list(keys), "value": duration_ms},
        )

    def record_historical_metric(
        self,
        metric_key: str,
        value: float,
        observed_at_ms: int | None = None,
    ) -> None:
        self._records.append(
            {
                "operation": "record_historical_metric",
                "metric_key": metric_key,
                "value": value,
                "observed_at_ms": observed_at_ms,
            },
        )

    def record_unique(self, *keys: str, item: str | float) -> None:
        self._records.append({"operation": "record_unique", "keys": list(keys), "item": item})

    def record_tokens_for_billing(
        self,
        plugin: str,
        model_id: str,
        client_id: str,
        tokens: int,
    ) -> None:
        if not plugin:
            raise ValidationError("plugin is required.")
        if plugin != self._plugin_name:
            raise ValidationError("Plugin worker cannot record billing for other plugins.")
        record: JSONDict = {
            "operation": "record_tokens_for_billing",
            "plugin": self._plugin_name,
            "model_id": model_id,
            "client_id": client_id,
            "tokens": tokens,
        }
        self._records.append(record)

    def record_completion_tokens(
        self,
        plugin: str,
        tokens: int,
    ) -> None:
        if plugin != self._plugin_name:
            raise ValidationError(
                "Plugin worker cannot record completion tokens for other plugins."
            )
        self._records.append(
            {
                "operation": "record_completion_tokens",
                "plugin": self._plugin_name,
                "tokens": tokens,
            },
        )

    def update_download_speed_metrics(
        self,
        bytes_per_second: float,
        source: str = "real_download",
    ) -> None:
        self._records.append(
            {
                "operation": "update_download_speed_metrics",
                "bytes_per_second": bytes_per_second,
                "source": source,
            },
        )

    def increment_genesis_request(self) -> None:
        self._records.append({"operation": "increment_genesis_request"})

    def purge_plugin_metrics(self, plugin_name: str) -> None:
        normalized_plugin_name = require_plugin_name(plugin_name)
        if normalized_plugin_name != self._plugin_name:
            raise ValidationError("Plugin worker cannot purge metrics for other plugins.")
        self._records.append(
            {"operation": "purge_plugin_metrics", "plugin_name": self._plugin_name},
        )

    async def flush(self, request: Callable[[str, JSONDict], Awaitable[JSONDict]]) -> None:
        async with self._flush_lock:
            if not self._records:
                return
            record_count = len(self._records)
            records = list(self._records)
            await request("metrics.record_batch", {"records": records})
            del self._records[:record_count]

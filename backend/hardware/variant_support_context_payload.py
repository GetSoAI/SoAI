"""SoAI - Hardware variant support context payload construction [backend/hardware/variant_support_context_payload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.hardware.protocols import DatabaseHardwareProtocol
from core.hardware.protocols_speed_test import (
    DiskSpeedTestServiceProtocol,
    NetworkSpeedTestServiceProtocol,
)
from core.hardware.variant_support import VariantSupportContext
from core.types.protocols import HttpClientProtocol
from core.validation.numbers import coerce_float_from_json
from hardware.storage.path_resolution import (
    collect_disk_free_bytes,
    resolve_storage_path,
)
from hardware.variant_support_speed_templates import (
    collect_disk_speed_template,
    collect_network_speed_template,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("build_variant_support_context_payload",)


def _get_capability_value(capabilities: Mapping[str, JSONValue], *keys: str) -> JSONValue:
    current: JSONValue = dict(capabilities)
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


async def build_variant_support_context_payload(
    *,
    capabilities: Mapping[str, JSONValue],
    models_dir: str | None,
    include_speed_tests: bool,
    disk_speed_test_service: DiskSpeedTestServiceProtocol,
    network_speed_test_service: NetworkSpeedTestServiceProtocol,
    database_hardware: DatabaseHardwareProtocol | None = None,
    http_client: HttpClientProtocol | None = None,
    require_measurements: bool = True,
) -> VariantSupportContext:
    storage_path = resolve_storage_path(models_dir)
    disk_free_bytes = collect_disk_free_bytes(storage_path)
    available_vram_gb = coerce_float_from_json(
        _get_capability_value(capabilities, "total_vram_gb"),
        default=None,
    )
    if available_vram_gb is None:
        available_vram_gb = coerce_float_from_json(
            _get_capability_value(capabilities, "gpu", "vram_gb"),
            default=None,
        )
    system_ram_gb = coerce_float_from_json(
        _get_capability_value(capabilities, "system_ram_gb"),
        default=None,
    )
    total_memory_gb = coerce_float_from_json(
        _get_capability_value(capabilities, "total_system_memory_gb"),
        default=None,
    )
    if total_memory_gb is None and system_ram_gb is not None and (available_vram_gb is not None):
        total_memory_gb = system_ram_gb + available_vram_gb
    disk_speed_template, network_speed_template = await asyncio.gather(
        collect_disk_speed_template(
            storage_path,
            include_speed_tests,
            database_hardware=database_hardware,
            disk_speed_test_service=disk_speed_test_service,
            require_measurements=require_measurements,
        ),
        collect_network_speed_template(
            include_speed_tests,
            database_hardware=database_hardware,
            http_client=http_client,
            network_speed_test_service=network_speed_test_service,
            require_measurements=require_measurements,
        ),
        return_exceptions=False,
    )
    return VariantSupportContext(
        disk_free_bytes=disk_free_bytes,
        disk_speed_template=disk_speed_template,
        network_speed_template=network_speed_template,
        available_vram_gb=available_vram_gb,
        total_memory_gb=total_memory_gb,
        system_ram_gb=system_ram_gb,
    )

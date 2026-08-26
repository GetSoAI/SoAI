"""SoAI - Variant support context types and resolution [backend/core/hardware/variant_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.hardware.protocols import (
    DatabaseHardwareProtocol,
    HardwareManagerProtocol,
    VariantSupportContextProtocol,
)
from core.hardware.variants import coerce_variant_size_bytes, estimate_download_seconds
from core.validation.coercion import coerce_float_with_bool

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from core.types.protocols import HttpClientProtocol

__all__ = (
    "VariantSupportContext",
    "render_variant_speed_template",
    "resolve_variant_support_context",
    "variant_support_context_to_dict",
)


@dataclass(slots=True)
class VariantSupportContext:
    disk_free_bytes: int | None
    disk_speed_template: JSONDict | None
    network_speed_template: JSONDict | None
    available_vram_gb: float | None
    total_memory_gb: float | None
    system_ram_gb: float | None


def variant_support_context_to_dict(
    context: VariantSupportContextProtocol | Mapping[str, JSONValue] | None,
) -> JSONDict:
    defaults = {
        "disk_free_bytes": None,
        "disk_speed_template": None,
        "network_speed_template": None,
        "available_vram_gb": None,
        "total_memory_gb": None,
        "system_ram_gb": None,
    }
    if not context:
        return dict(defaults)
    if isinstance(context, VariantSupportContext):
        raw = asdict(context)
    elif isinstance(context, Mapping):
        raw = dict(context)
    else:
        try:
            disk_free_bytes = context.disk_free_bytes
        except AttributeError:
            disk_free_bytes = None
        try:
            disk_speed_template = context.disk_speed_template
        except AttributeError:
            disk_speed_template = None
        try:
            network_speed_template = context.network_speed_template
        except AttributeError:
            network_speed_template = None
        try:
            available_vram_gb = context.available_vram_gb
        except AttributeError:
            available_vram_gb = None
        try:
            total_memory_gb = context.total_memory_gb
        except AttributeError:
            total_memory_gb = None
        try:
            system_ram_gb = context.system_ram_gb
        except AttributeError:
            system_ram_gb = None
        raw = {
            "disk_free_bytes": disk_free_bytes,
            "disk_speed_template": disk_speed_template,
            "network_speed_template": network_speed_template,
            "available_vram_gb": available_vram_gb,
            "total_memory_gb": total_memory_gb,
            "system_ram_gb": system_ram_gb,
        }
    return {key: raw.get(key) for key in defaults}


def render_variant_speed_template(
    template: JSONDict | None,
    variant: Mapping[str, JSONValue],
) -> JSONDict | None:
    if template is None:
        return None
    payload = dict(template)
    variant_dict = variant if isinstance(variant, dict) else dict(variant)
    size_bytes = coerce_variant_size_bytes(variant_dict)
    payload["size_bytes"] = size_bytes
    throughput = coerce_float_with_bool(payload.get("bytes_per_second"))
    base_estimate_seconds = estimate_download_seconds(size_bytes, throughput)
    base_estimate_ms = (
        int(base_estimate_seconds * 1000) if base_estimate_seconds is not None else None
    )
    payload["base_estimated_ms"] = base_estimate_ms
    raw_factor = payload.get("estimation_factor", 1.0)
    factor = coerce_float_with_bool(raw_factor)
    if factor is None:
        factor = 1.0
    payload["estimation_factor"] = factor
    payload["estimated_ms"] = (
        int(base_estimate_ms * factor) if base_estimate_ms is not None else None
    )
    return payload


async def resolve_variant_support_context(
    hw_manager_instance: HardwareManagerProtocol | None,
    models_dir: str | None,
    include_speed_tests: bool,
    *,
    database_hardware: DatabaseHardwareProtocol | None = None,
    http_client: HttpClientProtocol | None = None,
    config: Mapping[str, JSONValue] | None = None,
) -> VariantSupportContextProtocol | None:
    _ = config
    if hw_manager_instance is None:
        raise StateError("Variant support context builder is unavailable.")
    primary_context = await hw_manager_instance.build_variant_support_context(
        models_dir,
        include_speed_tests,
        database_hardware=database_hardware,
        http_client=http_client,
    )
    if primary_context is None:
        raise StateError("Variant support context builder returned no data.")
    return primary_context

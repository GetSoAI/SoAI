"""SoAI - GPU tuning control backend selection [backend/hardware/gpu_tuning/control_backend_selection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_settings_contract import (
    GPU_CLOCK_SETTING_FIELDS,
    GPU_RESET_CLOCKS_FIELD,
    validate_gpu_reset_clock_conflict,
)
from hardware.gpu_capabilities.payloads import (
    coerce_control_backend,
    read_control_capability_section,
)
from hardware.gpu_tuning.setting_capabilities import setting_descriptor_for_key

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "group_settings_by_control_backend",
    "resolve_setting_control_backend",
)


def resolve_setting_control_backend(setting_key: str, capabilities: JSONDict | None) -> str:
    if setting_key == GPU_RESET_CLOCKS_FIELD:
        return _resolve_reset_clocks_backend(capabilities)
    descriptor = setting_descriptor_for_key(setting_key)
    if descriptor is None:
        raise ValidationError(f"Unsupported GPU setting key '{setting_key}'.")
    caps = capabilities if isinstance(capabilities, dict) else {}
    cap_entry = read_control_capability_section(caps, descriptor.caps_key)
    backend = coerce_control_backend(cap_entry.get("control_backend"))
    if backend is None:
        raise ValidationError(f"{descriptor.label} has no supported control backend.")
    return backend


def group_settings_by_control_backend(
    settings: JSONDict,
    capabilities: JSONDict | None,
) -> dict[str, JSONDict]:
    validate_gpu_reset_clock_conflict(
        reset_clocks=settings.get(GPU_RESET_CLOCKS_FIELD) is True,
        core_clock=settings.get("core_clock"),
        mem_clock=settings.get("mem_clock"),
    )
    grouped: dict[str, JSONDict] = {}
    for setting_key, setting_value in settings.items():
        if setting_key == GPU_RESET_CLOCKS_FIELD:
            if setting_value is not True:
                raise ValidationError("Clock reset grouping requires a validated true request.")
            for field, backend in _resolve_reset_clock_routes(capabilities):
                if backend not in grouped:
                    grouped[backend] = {}
                grouped[backend][field] = "auto"
            continue
        backend = resolve_setting_control_backend(setting_key, capabilities)
        if backend not in grouped:
            grouped[backend] = {}
        grouped[backend][setting_key] = setting_value
    return grouped


def _resolve_reset_clocks_backend(capabilities: JSONDict | None) -> str:
    backends = _resolve_reset_clocks_backends(capabilities)
    if len(backends) < 1:
        raise ValidationError("Clock reset has no supported control backend.")
    if len(backends) > 1:
        raise ValidationError("Clock reset requires backend fan-out.")
    return backends[0]


def _resolve_reset_clocks_backends(capabilities: JSONDict | None) -> tuple[str, ...]:
    return tuple(sorted({backend for _, backend in _resolve_reset_clock_routes(capabilities)}))


def _resolve_reset_clock_routes(capabilities: JSONDict | None) -> tuple[tuple[str, str], ...]:
    caps = capabilities if isinstance(capabilities, dict) else {}
    routes: list[tuple[str, str]] = []
    for setting_key in GPU_CLOCK_SETTING_FIELDS:
        descriptor = setting_descriptor_for_key(setting_key)
        if descriptor is None:
            continue
        cap_entry = read_control_capability_section(caps, descriptor.caps_key)
        backend = coerce_control_backend(cap_entry.get("control_backend"))
        supported = cap_entry.get("supported") is True
        if supported and backend is not None and cap_entry.get("auto_supported", True) is True:
            routes.append((setting_key, backend))
    if not routes:
        raise ValidationError("Clock reset has no supported control backend.")
    return tuple(routes)

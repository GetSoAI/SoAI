"""SoAI - GPU tuning control backend selection [backend/hardware/gpu_tuning/control_backend_selection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_settings_contract import (
    GPU_CLOCK_SETTING_FIELDS,
    GPU_RESET_CLOCKS_FIELD,
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
    grouped: dict[str, JSONDict] = {}
    for setting_key, setting_value in settings.items():
        if setting_key == GPU_RESET_CLOCKS_FIELD:
            for backend in _resolve_reset_clocks_backends(capabilities):
                if backend not in grouped:
                    grouped[backend] = {}
                grouped[backend][setting_key] = setting_value
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
    caps = capabilities if isinstance(capabilities, dict) else {}
    backends: set[str] = set()
    for setting_key in GPU_CLOCK_SETTING_FIELDS:
        descriptor = setting_descriptor_for_key(setting_key)
        if descriptor is None:
            continue
        cap_entry = read_control_capability_section(caps, descriptor.caps_key)
        backend = coerce_control_backend(cap_entry.get("control_backend"))
        supported = cap_entry.get("supported") is True
        if supported and backend is not None:
            backends.add(backend)
    if not backends:
        raise ValidationError("Clock reset has no supported control backend.")
    return tuple(sorted(backends))

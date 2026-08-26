"""SoAI - GPU capability payload construction [backend/hardware/gpu_capabilities/payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.payload import ErrorPublicPayload
from core.types.json_value import coerce_json_dict_or_empty
from core.validation.boolean_coercion import coerce_bool_with_recovery

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "CONTROL_CAPABILITY_KEYS",
    "build_default_gpu_capabilities",
    "build_gpu_capability_error",
    "build_unsupported_control_capability",
    "coerce_control_backend",
    "enforce_gpu_control_backend_support",
    "mark_all_control_capabilities_unsupported",
    "mark_control_capability_unsupported",
    "merge_supported_capability_section",
    "normalize_gpu_control_capabilities",
    "read_control_capability_section",
    "supported_capability_flag",
    "update_control_capability_section",
)

CONTROL_CAPABILITY_KEYS: tuple[str, ...] = (
    "power_limit_watts",
    "core_clock_mhz",
    "mem_clock_mhz",
    "fan_speed_percent",
)

CONTROL_CAPABILITY_UNIT_ITEMS: tuple[tuple[str, str], ...] = (
    ("power_limit_watts", "W"),
    ("core_clock_mhz", "MHz"),
    ("mem_clock_mhz", "MHz"),
    ("fan_speed_percent", "%"),
)

CONTROL_CAPABILITY_DEFAULT_ITEMS: tuple[tuple[str, JSONValue], ...] = (
    ("supported", False),
    ("current", None),
    ("default", None),
    ("min", None),
    ("max", None),
    ("step", 1),
    ("unit", ""),
    ("mode", "auto"),
    ("control_backend", None),
    ("requires_admin", False),
    ("unsupported_reason", "unsupported_hardware"),
    ("error", None),
)


def _control_capability_unit(caps_key: str) -> str:
    for candidate_key, unit in CONTROL_CAPABILITY_UNIT_ITEMS:
        if candidate_key == caps_key:
            return unit
    raise KeyError(caps_key)


def build_default_gpu_capabilities(name: str = "GPU") -> JSONDict:
    return {
        "name": name,
        "power_limit_watts": build_unsupported_control_capability("power_limit_watts"),
        "core_clock_mhz": build_unsupported_control_capability("core_clock_mhz"),
        "mem_clock_mhz": build_unsupported_control_capability("mem_clock_mhz"),
        "fan_speed_percent": build_unsupported_control_capability("fan_speed_percent"),
    }


def build_unsupported_control_capability(
    caps_key: str,
    reason: str = "unsupported_hardware",
) -> JSONDict:
    capability = dict(CONTROL_CAPABILITY_DEFAULT_ITEMS)
    capability["unit"] = _control_capability_unit(caps_key)
    capability["unsupported_reason"] = reason
    if caps_key == "fan_speed_percent":
        capability["min"] = 0
        capability["max"] = 100
    return capability


def build_gpu_capability_error(
    code: str,
    message: str,
    *,
    vendor_id: int,
    reason: str | None = None,
) -> JSONDict:
    details: JSONDict = {"vendor_id": vendor_id}
    if reason is not None:
        details["reason"] = reason
    return ErrorPublicPayload(code=code, message=message, details=details).to_dict()


def read_control_capability_section(gpu_caps: Mapping[str, JSONValue], caps_key: str) -> JSONDict:
    section = build_unsupported_control_capability(caps_key)
    section.update(coerce_json_dict_or_empty(gpu_caps.get(caps_key)))
    return section


def update_control_capability_section(
    gpu_caps: JSONDict,
    caps_key: str,
    updates: JSONDict,
) -> JSONDict:
    section = read_control_capability_section(gpu_caps, caps_key)
    section.update(updates)
    if section.get("supported") is True:
        section["unsupported_reason"] = None
        section["error"] = None
    gpu_caps[caps_key] = section
    return section


def mark_control_capability_unsupported(
    gpu_caps: JSONDict,
    caps_key: str,
    reason: str,
    *,
    force: bool,
) -> None:
    error_payload = gpu_caps.get("error")
    section = read_control_capability_section(gpu_caps, caps_key)
    if force or section.get("supported") is not True:
        section["supported"] = False
        section["control_backend"] = None
        section["unsupported_reason"] = reason
        section["error"] = error_payload if isinstance(error_payload, dict) else None
        gpu_caps[caps_key] = section


def mark_all_control_capabilities_unsupported(
    gpu_caps: JSONDict,
    reason: str,
    *,
    force: bool = False,
) -> JSONDict:
    for caps_key in CONTROL_CAPABILITY_KEYS:
        mark_control_capability_unsupported(gpu_caps, caps_key, reason, force=force)
    return gpu_caps


def coerce_control_backend(value: JSONValue) -> str | None:
    if not isinstance(value, str):
        return None
    backend = value.strip()
    return backend or None


def _mark_control_backend_missing(capability: JSONDict) -> None:
    capability["supported"] = False
    capability["control_backend"] = None
    capability["unsupported_reason"] = "control_backend_missing"
    capability["error"] = None


def supported_capability_flag(
    value: JSONValue,
    *,
    logger: LoggerProtocol,
    operation: str,
    recover_message: str = "Failed to parse supported flag (non-critical).",
) -> bool:
    return coerce_bool_with_recovery(
        value,
        logger=logger,
        operation=operation,
        default=False,
        recover_message=recover_message,
    )


def merge_supported_capability_section(
    gpu_caps: JSONDict,
    caps_key: str,
    candidate: JSONDict,
    *,
    logger: LoggerProtocol,
    operation: str,
) -> None:
    if supported_capability_flag(candidate.get("supported"), logger=logger, operation=operation):
        section = update_control_capability_section(gpu_caps, caps_key, candidate)
        section["supported"] = True
        section["unsupported_reason"] = None
        section["error"] = None


def normalize_gpu_control_capabilities(
    gpu_caps: JSONDict,
    backend: str | None,
    *,
    enforce_backend: bool = True,
) -> JSONDict:
    normalized_backend = coerce_control_backend(backend)
    for caps_key in CONTROL_CAPABILITY_KEYS:
        normalized = read_control_capability_section(gpu_caps, caps_key)
        supported = normalized.get("supported") is True
        if supported and normalized_backend is not None:
            normalized["control_backend"] = normalized_backend
            normalized["unsupported_reason"] = None
            normalized["error"] = None
        elif supported and enforce_backend:
            _mark_control_backend_missing(normalized)
        elif supported:
            normalized["unsupported_reason"] = None
            normalized["error"] = None
        elif normalized.get("unsupported_reason") is None:
            normalized["supported"] = False
            normalized["unsupported_reason"] = "unsupported_hardware"
        else:
            normalized["supported"] = False
        if not isinstance(normalized.get("unit"), str) or not normalized.get("unit"):
            normalized["unit"] = _control_capability_unit(caps_key)
        gpu_caps[caps_key] = normalized
    return gpu_caps


def enforce_gpu_control_backend_support(gpu_caps: JSONDict) -> JSONDict:
    for caps_key in CONTROL_CAPABILITY_KEYS:
        capability = read_control_capability_section(gpu_caps, caps_key)
        if (
            capability.get("supported") is True
            and coerce_control_backend(capability.get("control_backend")) is None
        ):
            _mark_control_backend_missing(capability)
        gpu_caps[caps_key] = capability
    return gpu_caps

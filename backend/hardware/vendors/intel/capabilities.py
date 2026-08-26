"""SoAI - Intel GPU control capability probing [backend/hardware/vendors/intel/capabilities.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.payload import ErrorPublicPayload
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.runtime.platform import get_runtime_platform
from core.validation.coercion import coerce_int_from_numberish
from hardware.gpu_capabilities.payloads import (
    build_default_gpu_capabilities,
    mark_all_control_capabilities_unsupported,
    normalize_gpu_control_capabilities,
    update_control_capability_section,
)
from hardware.vendors.intel.capability_parsing import (
    extract_intel_config_device,
    extract_intel_dump_device,
    resolve_intel_frequency_capability,
)
from hardware.vendors.intel.commands import execute_intel_config_json, execute_intel_dump_json
from hardware.vendors.intel.runtime import is_xpu_smi_available

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = ("sync_get_intel_capabilities",)

OPERATION = "hardware_intel.sync_get_intel_capabilities"
INTEL_CAPABILITY_EXCEPTIONS: tuple[type[Exception], ...] = (
    AttributeError,
    KeyError,
    RuntimeError,
    TypeError,
    ValueError,
    StateError,
    ValidationError,
    *RECOVERABLE_EXCEPTIONS,
)


def sync_get_intel_capabilities(
    executor: CommandExecutorProtocol,
    logger: TraceLogger | None,
    vendor_id: int,
) -> JSONDict:
    gpu_caps = build_default_gpu_capabilities("Intel GPU")
    xpu_smi_available = is_xpu_smi_available()
    gpu_caps["control_backends"] = ["intel_xpum"] if xpu_smi_available else []
    if not xpu_smi_available:
        gpu_caps["error"] = ErrorPublicPayload(
            code="service_unavailable",
            message="xpu-smi not found",
            details={"vendor_id": vendor_id, "reason": "tool_missing"},
        ).to_dict()
        mark_all_control_capabilities_unsupported(gpu_caps, "tool_missing", force=True)
        return gpu_caps
    try:
        config_device = extract_intel_config_device(execute_intel_config_json(executor, vendor_id))
        if not config_device:
            raise StateError("xpu-smi config returned no device data.")
        dump_device = _read_dump_device(executor, logger, vendor_id)
        _apply_name(gpu_caps, dump_device)
        _apply_power_caps(gpu_caps, config_device, dump_device)
        _apply_clock_caps(gpu_caps, config_device)
        _apply_unsupported_telemetry(gpu_caps, dump_device)
    except INTEL_CAPABILITY_EXCEPTIONS as exception:
        if logger is not None:
            log_exception(
                logger,
                exception,
                message="Failed to parse xpu-smi capability output",
                operation=OPERATION,
                details={"vendor_id": vendor_id},
            )
        gpu_caps["error"] = ErrorPublicPayload(
            code="process_error",
            message="Failed to parse xpu-smi output.",
            details={"vendor_id": vendor_id, "reason": str(exception)},
        ).to_dict()
        mark_all_control_capabilities_unsupported(gpu_caps, "parse_error", force=True)
    return normalize_gpu_control_capabilities(gpu_caps, "intel_xpum")


def _read_dump_device(
    executor: CommandExecutorProtocol,
    logger: TraceLogger | None,
    vendor_id: int,
) -> JSONDict:
    try:
        return extract_intel_dump_device(execute_intel_dump_json(executor, vendor_id))
    except INTEL_CAPABILITY_EXCEPTIONS as exception:
        if logger is not None:
            log_handled_exception(
                logger,
                exception,
                message="xpu-smi dump capability enrichment failed (non-critical).",
                operation=OPERATION,
                details={"vendor_id": vendor_id},
                level="trace",
            )
        return {}


def _apply_name(gpu_caps: JSONDict, dump_device: JSONDict) -> None:
    device_name_value = dump_device.get("device_name")
    gpu_caps["name"] = (
        device_name_value
        if isinstance(device_name_value, str) and device_name_value
        else "Intel GPU"
    )


def _apply_power_caps(gpu_caps: JSONDict, config_device: JSONDict, dump_device: JSONDict) -> None:
    current_limit = _first_positive_int(
        config_device.get("pl_card_sustain"),
        config_device.get("pl_package_sustain"),
        dump_device.get("power_limit"),
    )
    maximum_limit = _first_positive_int(config_device.get("power_valid_range"), current_limit)
    if maximum_limit is None:
        return
    default_limit = current_limit if current_limit is not None else maximum_limit
    update_control_capability_section(
        gpu_caps,
        "power_limit_watts",
        {
            "max": maximum_limit,
            "default": default_limit,
            "current": current_limit,
            "supported": True,
            "requires_admin": not get_runtime_platform().is_windows,
        },
    )


def _apply_clock_caps(gpu_caps: JSONDict, config_device: JSONDict) -> None:
    frequency = resolve_intel_frequency_capability(config_device)
    if frequency is None:
        return
    update_control_capability_section(
        gpu_caps,
        "core_clock_mhz",
        {
            "min": frequency.minimum_mhz,
            "max": frequency.maximum_mhz,
            "current": frequency.current_maximum_mhz,
            "default": frequency.default_mhz,
            "supported": True,
            "requires_admin": not get_runtime_platform().is_windows,
        },
    )


def _apply_unsupported_telemetry(gpu_caps: JSONDict, dump_device: JSONDict) -> None:
    if "memory_frequency" in dump_device:
        update_control_capability_section(
            gpu_caps,
            "mem_clock_mhz",
            {"current": dump_device.get("memory_frequency"), "supported": False},
        )
    if "ras_fan_speed_rpm" in dump_device:
        update_control_capability_section(
            gpu_caps,
            "fan_speed_percent",
            {
                "current": dump_device.get("ras_fan_speed_rpm"),
                "supported": False,
                "unit": "RPM",
            },
        )


def _first_positive_int(*values: JSONValue) -> int | None:
    for value in values:
        parsed = coerce_int_from_numberish(value)
        if parsed is not None and parsed > 0:
            return parsed
    return None

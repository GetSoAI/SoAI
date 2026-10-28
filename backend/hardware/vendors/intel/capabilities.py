"""SoAI - Intel GPU control capability probing [backend/hardware/vendors/intel/capabilities.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.payload import ErrorPublicPayload
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.gpu_physical_observations import read_gpu_physical_identity
from core.runtime.platform import get_runtime_platform
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
from hardware.vendors.intel.commands import (
    IntelReadDialect,
    IntelReadError,
    IntelReadState,
    execute_intel_config_json,
    execute_intel_dump_json,
    resolve_intel_read_dialect,
)
from hardware.vendors.intel.i915_frequency import acquire_i915_frequency_state
from hardware.vendors.intel.runtime import is_xpu_smi_available

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict

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
    *,
    selected_gpu: JSONDict | None = None,
) -> JSONDict:
    gpu_caps = build_default_gpu_capabilities("Intel GPU")
    xpu_smi_available = is_xpu_smi_available()
    xpum_probe_permitted = xpu_smi_available and (
        selected_gpu is None or selected_gpu.get("telemetry_available") is not False
    )
    gpu_caps["control_backends"] = ["intel_xpum"] if xpum_probe_permitted else []
    if not xpum_probe_permitted:
        reason = "tool_missing" if not xpu_smi_available else "device_unavailable"
        gpu_caps["error"] = ErrorPublicPayload(
            code="service_unavailable",
            message=(
                "xpu-smi not found" if not xpu_smi_available else "Intel telemetry is unavailable."
            ),
            details={"vendor_id": vendor_id, "reason": reason},
        ).to_dict()
        mark_all_control_capabilities_unsupported(gpu_caps, reason, force=True)
        _apply_i915_capabilities(gpu_caps, selected_gpu, logger)
        return gpu_caps
    failure: Exception | None = None
    reason = "parse_error"
    try:
        dialect = resolve_intel_read_dialect(executor)
        config_device = extract_intel_config_device(
            execute_intel_config_json(executor, vendor_id, dialect=dialect)
        )
        if not config_device:
            raise StateError("xpu-smi config returned no device data.")
        dump_device = _read_dump_device(executor, logger, vendor_id, dialect)
        _apply_name(gpu_caps, dump_device)
        _apply_power_caps(gpu_caps, config_device)
        _apply_clock_caps(gpu_caps, config_device)
        _apply_unsupported_telemetry(gpu_caps, dump_device)
    except IntelReadError as exception:
        failure = exception
        if exception.state != IntelReadState.MALFORMED_RESPONSE:
            reason = exception.state.value
    except INTEL_CAPABILITY_EXCEPTIONS as exception:
        failure = exception
    if failure is not None:
        if logger is not None:
            log_exception(
                logger,
                failure,
                message="Failed to parse xpu-smi capability output",
                operation=OPERATION,
                details={"vendor_id": vendor_id},
            )
        gpu_caps["error"] = ErrorPublicPayload(
            code="process_error",
            message="Failed to parse xpu-smi output.",
            details={"vendor_id": vendor_id, "reason": reason},
        ).to_dict()
        mark_all_control_capabilities_unsupported(gpu_caps, reason, force=True)
    gpu_caps = normalize_gpu_control_capabilities(gpu_caps, "intel_xpum")
    _apply_i915_capabilities(gpu_caps, selected_gpu, logger)
    return gpu_caps


def _apply_i915_capabilities(
    gpu_caps: JSONDict, selected_gpu: JSONDict | None, logger: TraceLogger | None
) -> None:
    if selected_gpu is None or not get_runtime_platform().is_linux:
        return
    try:
        if selected_gpu.get("type") != "intel":
            raise ValidationError("i915 capability requires its actual Intel physical selection.")
        identity = read_gpu_physical_identity(selected_gpu)
        if identity is None or identity.pci_bdf_full is None:
            return
        state = acquire_i915_frequency_state(identity.pci_bdf_full)
    except (OSError, StateError, ValidationError) as exception:
        if logger is not None and not isinstance(exception, FileNotFoundError):
            log_handled_exception(
                logger,
                exception,
                message="i915 physical capability is unavailable.",
                operation=OPERATION,
                level="trace",
            )
        core = gpu_caps.get("core_clock_mhz")
        if isinstance(core, dict) and core.get("supported") is not True:
            core["unsupported_reason"] = (
                "permission_denied"
                if isinstance(exception, PermissionError)
                else (
                    "i915_unavailable"
                    if isinstance(exception, FileNotFoundError)
                    else "i915_invalid"
                )
            )
        return
    if not state.writable:
        core = gpu_caps.get("core_clock_mhz")
        if isinstance(core, dict) and core.get("supported") is not True:
            core.update(
                {
                    "min": state.minimum_mhz,
                    "max": state.upper_bound_mhz,
                    "current": state.maximum_mhz,
                    "default": None,
                    "supported": False,
                    "control_backend": None,
                    "unsupported_reason": "permission_denied",
                }
            )
        return
    update_control_capability_section(
        gpu_caps,
        "core_clock_mhz",
        {
            "min": state.minimum_mhz,
            "max": state.upper_bound_mhz,
            "current": state.maximum_mhz,
            "default": None,
            "supported": True,
            "requires_admin": True,
            "control_backend": "intel_i915",
            "numeric_supported": True,
            "auto_supported": False,
            "auto_requires_apply": True,
            "step": 1,
        },
    )
    backends = gpu_caps.get("control_backends")
    gpu_caps["control_backends"] = (
        list(backends) + ["intel_i915"] if isinstance(backends, list) else ["intel_i915"]
    )
    gpu_caps["pci_bdf_full"] = state.pci_bdf
    gpu_caps["pci_bdf_observations"] = [state.pci_bdf]
    gpu_caps.pop("error", None)


def _read_dump_device(
    executor: CommandExecutorProtocol,
    logger: TraceLogger | None,
    vendor_id: int,
    dialect: IntelReadDialect,
) -> JSONDict:
    try:
        return extract_intel_dump_device(
            execute_intel_dump_json(executor, vendor_id, dialect=dialect)
        )
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


def _apply_power_caps(gpu_caps: JSONDict, config_device: JSONDict) -> None:
    configured_domains: JSONDict = {
        field: config_device[field]
        for field in (
            "pl_card_sustain",
            "pl_card_burst",
            "pl_card_peak",
            "pl_package_sustain",
            "pl_package_burst",
            "pl_package_peak",
        )
        if field in config_device
    }
    update_control_capability_section(
        gpu_caps,
        "power_limit_watts",
        {
            "configured_domains": configured_domains,
            "reported_valid_range": config_device.get("power_valid_range"),
            "supported": False,
            "unsupported_reason": "power_domain_authority_unavailable",
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
            "numeric_supported": True,
            "auto_supported": False,
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

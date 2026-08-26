"""SoAI - AMD SMI capabilities probe [backend/hardware/vendors/amd/capabilities.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.payload import ErrorPublicPayload
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from hardware.gpu_capabilities.payloads import (
    build_default_gpu_capabilities,
    mark_all_control_capabilities_unsupported,
    merge_supported_capability_section,
    normalize_gpu_control_capabilities,
    update_control_capability_section,
)
from hardware.vendors.amd.amd_smi_parsing import (
    build_amd_smi_clock_caps,
    extract_amd_smi_numeric,
    extract_amd_smi_text,
)
from hardware.vendors.amd.amd_smi_payload_selection import (
    collect_amd_smi_gpu_payloads,
    select_amd_smi_gpu_entry_for_card,
    select_amd_smi_payload_for_card,
)
from hardware.vendors.amd.availability import is_amd_smi_available
from hardware.vendors.amd.commands import execute_amd_smi_json_command
from hardware.vendors.amd.overdrive_state import (
    AMDGPU_OVERDRIVE_BACKEND,
    build_amdgpu_overdrive_capabilities,
)

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict

__all__ = ("sync_get_amd_capabilities",)

LOGGER_NAME = "SoAI.hardware.vendors.capabilities"
OPERATION = "hardware_amd.sync_get_amd_capabilities"
AMD_SMI_BACKEND = "amd_smi"
AMD_CAPABILITY_RECOVERABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    ValidationError,
    *RECOVERABLE_EXCEPTIONS,
)


def _read_amd_smi_payloads(
    executor: CommandExecutorProtocol,
    vendor_id: int,
    logger: TraceLogger | None,
) -> tuple[JSONDict, JSONDict | None]:
    static_value = execute_amd_smi_json_command(
        executor,
        ["amd-smi", "static", "-g", str(vendor_id), "-a", "-b", "-d", "-v", "-l", "--json"],
        timeout=10,
    )
    static_entries = collect_amd_smi_gpu_payloads(static_value)
    if not static_entries:
        raise ValidationError("amd-smi returned an unexpected JSON payload shape.")
    static_payload = select_amd_smi_gpu_entry_for_card(static_value, vendor_id)
    if static_payload is None:
        raise ValidationError("amd-smi did not return data for the requested GPU.")
    metric_payload: JSONDict | None = None
    try:
        metric_value = execute_amd_smi_json_command(
            executor,
            ["amd-smi", "metric", "-g", str(vendor_id), "-p", "-c", "-f", "--json"],
            timeout=10,
        )
        selected_metric = select_amd_smi_payload_for_card(
            metric_value,
            static_payload,
            vendor_id,
            len(static_entries),
        )
        if isinstance(selected_metric, dict):
            metric_payload = {str(key): value for key, value in selected_metric.items()}
    except RECOVERABLE_EXCEPTIONS as exception:
        if logger is not None:
            log_handled_exception(
                logger,
                exception,
                message="amd-smi metric capability query failed (non-critical).",
                operation=OPERATION,
                details={"vendor_id": vendor_id},
                level="trace",
            )
    return (static_payload, metric_payload)


def _apply_power_caps(gpu_caps: JSONDict, static_payload: JSONDict) -> None:
    min_power = extract_amd_smi_numeric(static_payload, (("min", "power"),))
    max_power = extract_amd_smi_numeric(static_payload, (("max", "power"), ("power", "cap", "max")))
    if min_power is None or max_power is None or min_power >= max_power:
        return
    update_control_capability_section(
        gpu_caps,
        "power_limit_watts",
        {
            "min": int(min_power),
            "max": int(max_power),
            "default": int(max_power),
            "current": int(max_power),
            "supported": True,
            "requires_admin": True,
            "control_backend": AMD_SMI_BACKEND,
        },
    )


def _apply_clock_caps(gpu_caps: JSONDict, static_payload: JSONDict) -> None:
    merge_supported_capability_section(
        gpu_caps,
        "core_clock_mhz",
        _clock_caps_requiring_admin(
            build_amd_smi_clock_caps(static_payload, ("sys", "gfx", "sclk")),
        ),
        logger=get_logger(LOGGER_NAME),
        operation="hardware.amd.capabilities.core_clock_supported",
    )
    merge_supported_capability_section(
        gpu_caps,
        "mem_clock_mhz",
        _clock_caps_requiring_admin(build_amd_smi_clock_caps(static_payload, ("mem", "mclk"))),
        logger=get_logger(LOGGER_NAME),
        operation="hardware.amd.capabilities.mem_clock_supported",
    )


def _clock_caps_requiring_admin(caps: JSONDict) -> JSONDict:
    if caps.get("supported") is True:
        caps["requires_admin"] = True
        caps["control_backend"] = AMD_SMI_BACKEND
    return caps


def _apply_fan_caps(gpu_caps: JSONDict, metric_payload: JSONDict | None) -> None:
    if metric_payload is None:
        return
    fan_percent = extract_amd_smi_numeric(metric_payload, (("fan", "speed"), ("fan",)))
    if fan_percent is None or fan_percent < 0 or fan_percent > 100:
        return
    update_control_capability_section(
        gpu_caps,
        "fan_speed_percent",
        {
            "current": int(fan_percent),
            "default": int(fan_percent),
            "supported": True,
            "requires_admin": True,
            "control_backend": AMD_SMI_BACKEND,
            "auto_requires_apply": True,
        },
    )


def _apply_overdrive_caps(gpu_caps: JSONDict, static_payload: JSONDict) -> None:
    pci_bdf = extract_amd_smi_text(static_payload, (("bdf",),))
    overdrive_caps = build_amdgpu_overdrive_capabilities(pci_bdf)
    if overdrive_caps is None:
        return
    overdrive_bdf = overdrive_caps.get("overdrive_pci_bdf")
    if isinstance(overdrive_bdf, str) and overdrive_bdf:
        gpu_caps["overdrive_pci_bdf"] = overdrive_bdf
    for caps_key in ("core_clock_mhz", "mem_clock_mhz"):
        section = overdrive_caps.get(caps_key)
        if isinstance(section, dict):
            merge_supported_capability_section(
                gpu_caps,
                caps_key,
                section,
                logger=get_logger(LOGGER_NAME),
                operation=f"hardware.amd.capabilities.{caps_key}_overdrive_supported",
            )
    control_backends = gpu_caps.get("control_backends")
    if isinstance(control_backends, list) and AMDGPU_OVERDRIVE_BACKEND not in control_backends:
        control_backends.append(AMDGPU_OVERDRIVE_BACKEND)


def sync_get_amd_capabilities(
    executor: CommandExecutorProtocol,
    logger: TraceLogger | None,
    vendor_id: int,
) -> JSONDict:
    gpu_caps = build_default_gpu_capabilities("AMD GPU")
    amd_smi_available = is_amd_smi_available()
    gpu_caps["control_backends"] = [AMD_SMI_BACKEND] if amd_smi_available else []
    if not amd_smi_available:
        gpu_caps["error"] = ErrorPublicPayload(
            code="service_unavailable",
            message="amd-smi not found",
            details={"vendor_id": vendor_id, "reason": "tool_missing"},
        ).to_dict()
        return mark_all_control_capabilities_unsupported(gpu_caps, "tool_missing")
    try:
        static_payload, metric_payload = _read_amd_smi_payloads(executor, vendor_id, logger)
        gpu_caps["name"] = (
            extract_amd_smi_text(static_payload, (("market", "name"), ("product", "name")))
            or "AMD GPU"
        )
        _apply_power_caps(gpu_caps, static_payload)
        _apply_clock_caps(gpu_caps, static_payload)
        _apply_overdrive_caps(gpu_caps, static_payload)
        _apply_fan_caps(gpu_caps, metric_payload)
    except AMD_CAPABILITY_RECOVERABLE_EXCEPTIONS as exception:
        if logger is not None:
            log_exception(
                logger,
                exception,
                message="Failed to parse amd-smi JSON output",
                operation=OPERATION,
                details={"vendor_id": vendor_id},
            )
        gpu_caps["error"] = ErrorPublicPayload(
            code="process_error",
            message="Failed to parse amd-smi output.",
            details={"vendor_id": vendor_id, "reason": str(exception)},
        ).to_dict()
        mark_all_control_capabilities_unsupported(gpu_caps, "parse_error", force=True)
    return normalize_gpu_control_capabilities(gpu_caps, None, enforce_backend=False)

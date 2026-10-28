"""SoAI - AMD SMI capabilities probe [backend/hardware/vendors/amd/capabilities.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.payload import ErrorPublicPayload
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.gpu_identity_normalization import normalize_observed_full_pci_bdf
from core.hardware.gpu_physical_identity import GPUInventoryReadState, GPUPhysicalBindingState
from core.hardware.gpu_physical_observations import read_gpu_physical_identity, read_gpu_vendor
from core.logging.trace import get_logger
from hardware.gpu_capabilities.payloads import (
    build_default_gpu_capabilities,
    mark_all_control_capabilities_unsupported,
    normalize_gpu_control_capabilities,
    read_control_capability_section,
    update_control_capability_section,
)
from hardware.gpu_inventory.physical_binding import match_gpu_physical_identity
from hardware.vendors.amd.adl_capabilities import sync_get_adl_capabilities
from hardware.vendors.amd.adl_session import AdlRuntime
from hardware.vendors.amd.amd_smi_parsing import (
    build_amd_smi_clock_caps,
    extract_amd_smi_fan_percent,
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
from hardware.vendors.amd.physical_binding import project_amd_smi_physical_observations
from hardware.vendors.amd.power_capabilities import (
    apply_amd_smi_power_capabilities,
    query_amd_native_power_capabilities,
)

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.runtime.protocols import RuntimePlatformViewProtocol
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict

__all__ = ("sync_get_amd_capabilities",)

LOGGER_NAME = "SoAI.hardware.vendors.capabilities"
OPERATION = "hardware_amd.sync_get_amd_capabilities"
AMD_SMI_BACKEND = "amd_smi"
AMD_METRIC_RECOVERABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    StateError,
    *RECOVERABLE_EXCEPTIONS,
)
AMD_CAPABILITY_RECOVERABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    StateError,
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
    except AMD_METRIC_RECOVERABLE_EXCEPTIONS as exception:
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


def _apply_clock_caps(gpu_caps: JSONDict, static_payload: JSONDict) -> None:
    for caps_key, clock_names in (
        ("core_clock_mhz", ("sys", "gfx", "sclk")),
        ("mem_clock_mhz", ("mem", "mclk")),
    ):
        section = build_amd_smi_clock_caps(static_payload, clock_names)
        section.update(
            supported=False,
            numeric_supported=False,
            auto_supported=False,
            control_backend=None,
            unsupported_reason="native_control_unavailable",
        )
        update_control_capability_section(gpu_caps, caps_key, section)


def _apply_fan_caps(gpu_caps: JSONDict, metric_payload: JSONDict | None) -> None:
    if metric_payload is None:
        return
    fan_percent = extract_amd_smi_fan_percent(metric_payload)
    if fan_percent is None:
        return
    update_control_capability_section(
        gpu_caps,
        "fan_speed_percent",
        {
            "current": None,
            "default": None,
            "supported": True,
            "numeric_supported": False,
            "auto_supported": True,
            "requires_admin": True,
            "control_backend": AMD_SMI_BACKEND,
            "auto_requires_apply": True,
        },
    )


def _apply_overdrive_caps(gpu_caps: JSONDict, selected: JSONDict | None) -> None:
    identity = read_gpu_physical_identity(selected) if selected is not None else None
    result = build_amdgpu_overdrive_capabilities(
        identity.pci_bdf_full if identity is not None else None
    )
    overdrive_caps = result.payload
    if result.state != GPUInventoryReadState.OBSERVED or overdrive_caps is None:
        if result.failure is not None:
            log_handled_exception(
                get_logger(LOGGER_NAME),
                result.failure,
                message="Independent AMDGPU OverDrive query is unavailable.",
                operation=OPERATION,
                level="trace",
            )
        return
    gpu_caps["pci_bdf_full"] = overdrive_caps["pci_bdf_full"]
    gpu_caps["pci_bdf_observations"] = overdrive_caps["pci_bdf_observations"]
    overdrive_bdf = overdrive_caps.get("overdrive_pci_bdf")
    if isinstance(overdrive_bdf, str) and overdrive_bdf:
        gpu_caps["overdrive_pci_bdf"] = overdrive_bdf
    for caps_key in ("core_clock_mhz", "mem_clock_mhz"):
        section = overdrive_caps.get(caps_key)
        if isinstance(section, dict):
            update_control_capability_section(gpu_caps, caps_key, section)
    control_backends = gpu_caps.get("control_backends")
    if isinstance(control_backends, list) and AMDGPU_OVERDRIVE_BACKEND not in control_backends:
        control_backends.append(AMDGPU_OVERDRIVE_BACKEND)


def sync_get_amd_capabilities(
    executor: CommandExecutorProtocol,
    logger: TraceLogger | None,
    vendor_id: int,
    *,
    selected_gpu: JSONDict | None = None,
    adl_runtime: AdlRuntime | None = None,
    runtime_platform: RuntimePlatformViewProtocol | None = None,
) -> JSONDict:
    if (runtime_platform is not None and runtime_platform.is_windows) or (
        selected_gpu is not None and "windows_pnp_instance_id" in selected_gpu
    ):
        return sync_get_adl_capabilities(executor, logger, selected_gpu, adl_runtime)
    selected_gpu = copy.deepcopy(selected_gpu)
    gpu_caps = build_default_gpu_capabilities("AMD GPU")
    native_power: JSONDict | None = None
    amd_smi_available = is_amd_smi_available()
    gpu_caps["control_backends"] = [AMD_SMI_BACKEND] if amd_smi_available else []
    try:
        selected_identity = (
            read_gpu_physical_identity(selected_gpu) if selected_gpu is not None else None
        )
        if selected_gpu is not None and read_gpu_vendor(selected_gpu) != "amd":
            raise ValidationError("AMD capabilities require their actual AMD inventory selection.")
    except ValidationError:
        gpu_caps["control_binding_state"] = GPUPhysicalBindingState.INVALID_RESPONSE.value
        return mark_all_control_capabilities_unsupported(gpu_caps, "identity_conflict", force=True)
    if not amd_smi_available:
        gpu_caps["error"] = ErrorPublicPayload(
            code="service_unavailable",
            message="amd-smi not found",
            details={"vendor_id": vendor_id, "reason": "tool_missing"},
        ).to_dict()
        mark_all_control_capabilities_unsupported(gpu_caps, "tool_missing")
        _apply_overdrive_caps(gpu_caps, selected_gpu)
        return normalize_gpu_control_capabilities(gpu_caps, None, enforce_backend=False)
    native_selected: JSONDict | None = selected_gpu
    try:
        static_payload, metric_payload = _read_amd_smi_payloads(executor, vendor_id, logger)
        try:
            native_observations = project_amd_smi_physical_observations(static_payload)
            native_identity = read_gpu_physical_identity(native_observations)
        except ValidationError as exception:
            if logger is not None:
                log_handled_exception(
                    logger,
                    exception,
                    message="AMD SMI physical identity is invalid.",
                    operation=OPERATION,
                    details={"vendor_id": vendor_id},
                    level="trace",
                )
            gpu_caps["control_binding_state"] = GPUPhysicalBindingState.INVALID_RESPONSE.value
            return mark_all_control_capabilities_unsupported(
                gpu_caps, "identity_conflict", force=True
            )
        if selected_gpu is not None:
            relation = match_gpu_physical_identity(selected_gpu, native_observations)
            if selected_identity is not None and native_identity is not None:
                conflicting_uuid = (
                    selected_identity.uuid is not None
                    and native_identity.uuid is not None
                    and selected_identity.uuid.casefold() != native_identity.uuid.casefold()
                )
                conflicting_pci = (
                    selected_identity.pci_bdf_full is not None
                    and native_identity.pci_bdf_full is not None
                    and normalize_observed_full_pci_bdf(selected_identity.pci_bdf_full)
                    != normalize_observed_full_pci_bdf(native_identity.pci_bdf_full)
                )
                if conflicting_uuid or conflicting_pci:
                    relation = GPUPhysicalBindingState.IDENTITY_CONFLICT
            if relation in (
                GPUPhysicalBindingState.IDENTITY_CONFLICT,
                GPUPhysicalBindingState.INVALID_RESPONSE,
            ):
                gpu_caps["control_binding_state"] = relation.value
                return mark_all_control_capabilities_unsupported(
                    gpu_caps, "identity_conflict", force=True
                )
            if selected_identity is not None and relation != GPUPhysicalBindingState.BOUND:
                raise StateError("AMD SMI capability identity is unavailable.")
        elif native_identity is not None:
            native_selected = native_observations
        gpu_caps.update(native_observations)
        gpu_caps["name"] = (
            extract_amd_smi_text(static_payload, (("market", "name"), ("product", "name")))
            or "AMD GPU"
        )
        apply_amd_smi_power_capabilities(gpu_caps, [static_payload, metric_payload])
        if selected_gpu is not None:
            native_power = query_amd_native_power_capabilities(executor, logger, selected_gpu)
        _apply_clock_caps(gpu_caps, static_payload)
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
            details={"vendor_id": vendor_id, "reason": "amd_smi_unavailable"},
        ).to_dict()
        mark_all_control_capabilities_unsupported(gpu_caps, "parse_error", force=True)
        gpu_caps["control_backends"] = []
    _apply_overdrive_caps(gpu_caps, native_selected)
    normalized = normalize_gpu_control_capabilities(gpu_caps, None, enforce_backend=False)
    if native_power is not None:
        section = read_control_capability_section(normalized, "power_limit_watts")
        section.update(native_power)
        normalized["power_limit_watts"] = section
    return normalized

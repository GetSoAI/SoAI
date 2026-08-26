"""SoAI - NVIDIA GPU capability collection through NVML and NvAPI [backend/hardware/vendors/nvidia/metrics.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.protocols import (
    NvidiaCapabilitiesCacheServiceProtocol,
    NvmlGateProtocol,
)
from core.imports.availability import module_available
from hardware.gpu_capabilities.payloads import (
    CONTROL_CAPABILITY_KEYS,
    build_default_gpu_capabilities,
    enforce_gpu_control_backend_support,
    normalize_gpu_control_capabilities,
    read_control_capability_section,
)
from hardware.vendors.nvidia.discovery import (
    classify_nvidia_gpu,
    query_nvidia_smi_ecc_support,
    query_nvidia_smi_gpu_name,
    read_nvml_ecc_support,
)
from hardware.vendors.nvidia.internal_protocols import (
    NvmlDeviceGetHandleByIndexProtocol,
)
from hardware.vendors.nvidia.nvapi_capabilities import (
    collect_nvapi_capabilities,
    merge_nvapi_capabilities,
)
from hardware.vendors.nvidia.nvidia_settings_capabilities import (
    apply_nvidia_settings_capabilities,
)
from hardware.vendors.nvidia.nvml_capabilities import collect_nvidia_capabilities
from hardware.vendors.nvidia.nvml_metric_reading import is_nvml_error_not_supported

if TYPE_CHECKING:
    import ctypes

    from core.logging.protocols import TraceLogger
    from core.types.json import JSONDict

    type NvmlDeviceHandle = ctypes.c_void_p

__all__ = ("sync_get_nvidia_capabilities",)

OPERATION = "hardware_nvidia.sync_get_nvidia_capabilities"

pynvml_module_ref = None
if module_available("pynvml"):
    import pynvml

    pynvml_module_ref = pynvml


def _collect_nvidia_capabilities(handle: NvmlDeviceHandle | None) -> JSONDict:
    if handle is None:
        return _collect_nvidia_capabilities_minimal(handle)
    return collect_nvidia_capabilities(handle)


def _collect_nvidia_capabilities_minimal(_handle: NvmlDeviceHandle | None) -> JSONDict:
    return build_default_gpu_capabilities("NVIDIA GPU")


def _pynvml_available() -> bool:
    pynvml_module = pynvml_module_ref
    if pynvml_module is None:
        return False
    try:
        handle_function = pynvml_module.nvmlDeviceGetHandleByIndex
    except AttributeError:
        return False
    return isinstance(handle_function, NvmlDeviceGetHandleByIndexProtocol)


def _set_control_backend(gpu_caps: JSONDict, caps_key: str, backend: str | None) -> str | None:
    cap_entry = read_control_capability_section(gpu_caps, caps_key)
    if cap_entry.get("supported") is True and backend is not None:
        cap_entry["control_backend"] = backend
        cap_entry["unsupported_reason"] = None
        cap_entry["error"] = None
        gpu_caps[caps_key] = cap_entry
        return backend
    if cap_entry.get("supported") is not True:
        cap_entry["control_backend"] = None
        if not isinstance(cap_entry.get("unsupported_reason"), str):
            cap_entry["unsupported_reason"] = "unsupported_hardware"
    gpu_caps[caps_key] = cap_entry
    return None


def _apply_nvidia_backend_metadata(
    gpu_caps: JSONDict,
    *,
    nvml_available: bool,
    nvapi_available: bool,
    nvidia_settings_available: bool,
) -> None:
    control_backends: list[str] = []
    for caps_key in CONTROL_CAPABILITY_KEYS:
        cap_entry = read_control_capability_section(gpu_caps, caps_key)
        via_nvapi = cap_entry.get("via_nvapi") is True
        via_nvml = cap_entry.get("via_nvml") is True
        via_nvidia_settings = cap_entry.get("via_nvidia_settings") is True
        backend: str | None = None
        if via_nvapi and nvapi_available:
            backend = "nvidia_nvapi"
        elif via_nvml and nvml_available:
            backend = "nvidia_nvml"
        elif via_nvidia_settings and nvidia_settings_available:
            backend = "nvidia_settings"
        assigned_backend = _set_control_backend(gpu_caps, caps_key, backend)
        if assigned_backend is not None and assigned_backend not in control_backends:
            control_backends.append(assigned_backend)
    gpu_caps["control_backends"] = control_backends


def _is_finalized_nvidia_capabilities(gpu_caps: JSONDict) -> bool:
    if not isinstance(gpu_caps.get("classification"), dict):
        return False
    for caps_key in CONTROL_CAPABILITY_KEYS:
        cap_entry = read_control_capability_section(gpu_caps, caps_key)
        backend = cap_entry.get("control_backend")
        if cap_entry.get("supported") is True and not (
            isinstance(backend, str) and backend.strip()
        ):
            return False
    return True


def _expensive_capability_computation(
    trace_logger: TraceLogger | None,
    vendor_id: int,
    *,
    nvml_gate: NvmlGateProtocol,
) -> JSONDict:
    nvapi_available = nvml_gate.nvapi_support.can_attempt
    nvidia_settings_available = nvml_gate.nvidia_settings_available
    nvidia_settings_control_available = nvidia_settings_available
    nvml_available = nvml_gate.nvml_available and _pynvml_available()
    gpu_caps = build_default_gpu_capabilities("NVIDIA GPU")
    nvml_ecc_supported: bool | None = None
    if nvml_available:
        pynvml_module = pynvml_module_ref
        if pynvml_module is None:
            nvml_available = False
        else:
            try:
                with nvml_gate.session():
                    try:
                        device_handle_function = pynvml_module.nvmlDeviceGetHandleByIndex
                    except AttributeError:
                        device_handle_function = None
                    if isinstance(device_handle_function, NvmlDeviceGetHandleByIndexProtocol):
                        handle = device_handle_function(vendor_id)
                        gpu_caps = _collect_nvidia_capabilities(handle)
                        nvml_ecc_supported = read_nvml_ecc_support(handle)
                    else:
                        nvml_available = False
            except pynvml_module.NVMLError as exception:
                nvml_available = False
                if trace_logger:
                    if is_nvml_error_not_supported(exception):
                        trace_logger.trace(
                            "NVML capability not supported for GPU %s: %s",
                            vendor_id,
                            str(exception),
                        )
                    else:
                        log_exception(
                            trace_logger,
                            exception,
                            message="A critical NVML error occurred while getting GPU capabilities",
                            operation=OPERATION,
                            details={"vendor_id": vendor_id},
                        )
            except RECOVERABLE_EXCEPTIONS as exception:
                nvml_available = False
                if trace_logger:
                    log_handled_exception(
                        trace_logger,
                        exception,
                        message=(
                            "NVIDIA capability collection failed without NVML access "
                            "(non-critical)."
                        ),
                        operation=OPERATION,
                        details={"vendor_id": vendor_id},
                        level="trace",
                    )
    if nvapi_available:
        nvapi_caps = collect_nvapi_capabilities(vendor_id, nvml_gate=nvml_gate)
        gpu_caps = merge_nvapi_capabilities(gpu_caps, nvapi_caps)
    if nvidia_settings_available and nvml_gate.runtime_platform.is_linux:
        nvidia_settings_control_available = apply_nvidia_settings_capabilities(
            nvml_gate.logger,
            vendor_id,
            gpu_caps,
        )
    gpu_name_value = gpu_caps.get("name")
    if (
        (not isinstance(gpu_name_value, str))
        or (not gpu_name_value.strip())
        or (gpu_name_value == "NVIDIA GPU")
    ):
        gpu_name_value = query_nvidia_smi_gpu_name(vendor_id)
    gpu_name = gpu_name_value if isinstance(gpu_name_value, str) else "NVIDIA GPU"
    classification = classify_nvidia_gpu(
        gpu_name,
        vendor_id,
        ecc_supported_hint=(
            nvml_ecc_supported if nvml_available else query_nvidia_smi_ecc_support(vendor_id)
        ),
        runtime_platform=nvml_gate.runtime_platform,
        nvidia_settings_available=nvidia_settings_control_available,
        nvml_available=nvml_available,
        nvapi_available=nvapi_available,
    )
    gpu_caps["classification"] = {
        "gpu_class": classification.gpu_class.value,
        "control_method": classification.control_method.value,
        "ecc_supported": classification.ecc_supported,
        "reasoning": classification.reasoning,
        "control_reasoning": classification.control_reasoning,
    }
    normalize_gpu_control_capabilities(gpu_caps, None, enforce_backend=False)
    _apply_nvidia_backend_metadata(
        gpu_caps,
        nvml_available=nvml_available,
        nvapi_available=nvapi_available,
        nvidia_settings_available=nvidia_settings_control_available,
    )
    enforce_gpu_control_backend_support(gpu_caps)
    return gpu_caps


def sync_get_nvidia_capabilities(
    trace_logger: TraceLogger | None,
    vendor_id: int,
    *,
    nvml_gate: NvmlGateProtocol,
    capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
) -> JSONDict:
    cached = capabilities_cache_service.get_cached(vendor_id)
    if cached is not None and _is_finalized_nvidia_capabilities(cached):
        return cached
    if cached is not None:
        capabilities_cache_service.invalidate(vendor_id)

    def _compute_capabilities() -> JSONDict:
        return _expensive_capability_computation(
            trace_logger,
            vendor_id,
            nvml_gate=nvml_gate,
        )

    return capabilities_cache_service.compute_or_wait(vendor_id, _compute_capabilities)

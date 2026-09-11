"""SoAI - GPU capability probing utilities [backend/hardware/probe.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import copy
from collections.abc import Callable
from typing import TYPE_CHECKING

from core.concurrency.deadlines import deadline_after
from core.errors.exception_logging import log_handled_exception
from core.errors.payload import ErrorPublicPayload
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.device_display_name import build_device_display_name
from core.hardware.protocols import (
    NvidiaCapabilitiesCacheServiceProtocol,
    NvmlGateProtocol,
)
from core.logging.trace import TraceLogger
from core.runtime.platform import get_runtime_platform
from core.types.json_value import coerce_json_dict_or_empty
from hardware.gpu_capabilities.aggregate_payloads import (
    build_capabilities_aggregate_payload,
    build_probe_error_payload,
    collect_control_backends,
)
from hardware.gpu_capabilities.payloads import (
    CONTROL_CAPABILITY_KEYS,
    build_default_gpu_capabilities,
    mark_all_control_capabilities_unsupported,
    mark_control_capability_unsupported,
    read_control_capability_section,
)
from hardware.gpu_info_resolution import resolve_gpu_info
from hardware.gpu_inventory.display_name import select_gpu_display_name
from hardware.gpu_inventory.identity import normalize_gpu_index
from hardware.internal_protocols import (
    GPUInfoCacheServiceProtocol,
    GPUVendorDetectionServiceProtocol,
)
from hardware.operations import sum_vram_gb
from hardware.vendors.amd.capabilities import sync_get_amd_capabilities
from hardware.vendors.intel.capabilities import sync_get_intel_capabilities
from hardware.vendors.nvidia.metrics import sync_get_nvidia_capabilities
from hardware.vendors.nvidia.smi import NvidiaSettingsController
from hardware.vendors.vendor_metadata import resolve_driver_version
from hardware.vendors.vendor_types import AMD_VENDOR, INTEL_VENDOR, NVIDIA_VENDOR

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict

__all__ = (
    "async_get_raw_capabilities",
    "sync_get_raw_capabilities",
)

OPERATION_HARDWARE_PROBE_VENDOR_CAPABILITIES = (
    "hardware.probe.sync_get_raw_capabilities.vendor_probe"
)


def sync_get_raw_capabilities(
    executor: CommandExecutorProtocol,
    *,
    gpu_info_cache_service: GPUInfoCacheServiceProtocol,
    gpu_vendor_detection_service: GPUVendorDetectionServiceProtocol,
    nvidia_nvml_gate: NvmlGateProtocol,
    nvidia_capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
    nvidia_settings_controller: NvidiaSettingsController | None,
    gpu_info: JSONDict | None = None,
    logger: TraceLogger | None = None,
) -> JSONDict:
    all_gpu_info = resolve_gpu_info(
        executor,
        gpu_info_cache_service=gpu_info_cache_service,
        gpu_vendor_detection_service=gpu_vendor_detection_service,
        nvidia_nvml_gate=nvidia_nvml_gate,
        nvidia_capabilities_cache_service=nvidia_capabilities_cache_service,
        gpu_info=gpu_info,
    )
    compute_drivers = coerce_json_dict_or_empty(all_gpu_info.get("compute_drivers"))
    capabilities = build_capabilities_aggregate_payload(
        compute_drivers=compute_drivers,
        total_vram_gb=sum_vram_gb(all_gpu_info),
    )
    optional_deadline = deadline_after(10.0)
    vendor_map: dict[str, Callable[[int], JSONDict]] = {
        AMD_VENDOR: lambda vendor_id: sync_get_amd_capabilities(executor, logger, vendor_id),
        INTEL_VENDOR: lambda vendor_id: sync_get_intel_capabilities(executor, logger, vendor_id),
        NVIDIA_VENDOR: lambda vendor_id: sync_get_nvidia_capabilities(
            logger,
            vendor_id,
            nvml_gate=nvidia_nvml_gate,
            capabilities_cache_service=nvidia_capabilities_cache_service,
            controller=nvidia_settings_controller,
            deadline=optional_deadline,
        ),
    }
    runtime_platform = get_runtime_platform()
    gpus_value = all_gpu_info.get("gpus")
    if not isinstance(gpus_value, list):
        return capabilities
    probe_generation = nvidia_capabilities_cache_service.revision()
    unfinished_before = nvidia_capabilities_cache_service.unfinished_devices()
    unfinished_after: list[str] = []
    ordered_gpus = sorted(
        gpus_value,
        key=lambda gpu: (
            0 if isinstance(gpu, dict) and gpu.get("device_id") in unfinished_before else 1
        ),
    )
    for gpu in ordered_gpus:
        if not isinstance(gpu, dict):
            continue
        vendor_type = gpu.get("type")
        if not isinstance(vendor_type, str):
            continue
        getter = vendor_map.get(vendor_type)
        if not getter:
            continue
        vendor_id_value = normalize_gpu_index(gpu.get("vendor_id"))
        if vendor_id_value is None:
            continue
        if gpu.get("telemetry_available") is False:
            caps_payload = build_default_gpu_capabilities(str(gpu.get("name") or "GPU"))
            mark_all_control_capabilities_unsupported(
                caps_payload,
                _resolve_inventory_runtime_reason(gpu, vendor_type) or "device_unavailable",
                force=True,
            )
        else:
            try:
                caps_payload = getter(vendor_id_value)
            except RECOVERABLE_EXCEPTIONS as exception:
                if logger is not None:
                    log_handled_exception(
                        logger,
                        exception,
                        message="GPU capability probe failed for one device (non-critical).",
                        operation=OPERATION_HARDWARE_PROBE_VENDOR_CAPABILITIES,
                        details={"vendor": vendor_type, "vendor_id": vendor_id_value},
                        level="warning",
                    )
                caps_payload = build_default_gpu_capabilities(str(gpu.get("name") or "GPU"))
                caps_payload["error"] = ErrorPublicPayload(
                    code="gpu_probe_failed",
                    message="GPU capability probe failed for this device.",
                    details={
                        "vendor": vendor_type,
                        "vendor_id": vendor_id_value,
                        "reason": "device_unavailable",
                    },
                ).to_dict()
                mark_all_control_capabilities_unsupported(
                    caps_payload,
                    "device_unavailable",
                    force=True,
                )
        if not isinstance(caps_payload, dict):
            continue
        if vendor_type == NVIDIA_VENDOR and optional_deadline.remaining_seconds() < 1:
            unfinished_device = gpu.get("device_id")
            if isinstance(unfinished_device, str):
                unfinished_after.append(unfinished_device)
            capabilities["error"] = ErrorPublicPayload(
                code="timeout", message="Optional GPU capability discovery is incomplete."
            ).to_dict()
        caps_copy = copy.deepcopy(caps_payload)
        _apply_inventory_runtime_reasons(caps_copy, gpu, vendor_type)
        driver = resolve_driver_version(compute_drivers, vendor_type)
        caps_copy["name"] = select_gpu_display_name(gpu.get("name"), caps_copy.get("name")) or str(
            caps_copy.get("name") or gpu.get("name") or "GPU",
        )
        caps_copy["display_name"] = build_device_display_name(caps_copy["name"])
        caps_copy.update(
            {
                "index": gpu.get("index"),
                "device_id": gpu.get("device_id"),
                "vendor": vendor_type,
                "type": vendor_type,
                "vendor_id": vendor_id_value,
                "pci_bdf": gpu.get("pci_bdf"),
                "os": runtime_platform.os_name,
                "driver": driver,
            },
        )
        if not isinstance(caps_copy.get("control_backends"), list):
            caps_copy["control_backends"] = collect_control_backends(caps_copy)
        index = normalize_gpu_index(gpu.get("index"))
        if index is not None:
            index_key = str(index)
            caps_by_index = capabilities.get("gpus")
            if isinstance(caps_by_index, dict):
                caps_by_index[index_key] = copy.deepcopy(caps_copy)
        device_id = gpu.get("device_id")
        if isinstance(device_id, str) and device_id:
            caps_by_device = capabilities.get("gpus_by_device_id")
            if isinstance(caps_by_device, dict):
                caps_by_device[device_id] = copy.deepcopy(caps_copy)
    if probe_generation != nvidia_capabilities_cache_service.revision():
        return build_probe_error_payload(
            "stale_probe", "GPU inventory changed while probing capabilities."
        )
    nvidia_capabilities_cache_service.record_probe_progress(
        probe_generation, tuple(unfinished_after)
    )
    for map_key, identity_key in (("gpus", "index"), ("gpus_by_device_id", "device_id")):
        collected = capabilities.get(map_key)
        if isinstance(collected, dict):
            ordered: JSONDict = {}
            for gpu in gpus_value:
                if isinstance(gpu, dict):
                    key = str(gpu.get(identity_key))
                    if key in collected:
                        ordered[key] = collected[key]
            capabilities[map_key] = ordered
    return capabilities


def _apply_inventory_runtime_reasons(
    caps: JSONDict,
    gpu: JSONDict,
    vendor_type: str,
) -> None:
    if gpu.get("telemetry_available") is True:
        return
    reason = _resolve_inventory_runtime_reason(gpu, vendor_type)
    if reason is None:
        return
    for caps_key in CONTROL_CAPABILITY_KEYS:
        section = read_control_capability_section(caps, caps_key)
        if section.get("supported") is True:
            continue
        mark_control_capability_unsupported(caps, caps_key, reason, force=True)


def _resolve_inventory_runtime_reason(gpu: JSONDict, vendor_type: str) -> str | None:
    if vendor_type == AMD_VENDOR:
        return "tool_missing"
    if vendor_type == INTEL_VENDOR:
        return "tool_missing"
    if vendor_type != NVIDIA_VENDOR:
        return None
    kernel_driver = gpu.get("kernel_driver")
    kernel_modules_value = gpu.get("kernel_modules")
    kernel_modules = (
        tuple(value for value in kernel_modules_value if isinstance(value, str))
        if isinstance(kernel_modules_value, list)
        else ()
    )
    if kernel_driver == "nouveau":
        return "driver_inactive"
    if kernel_driver != "nvidia" and "nvidia" not in kernel_modules:
        return "driver_inactive"
    return "tool_missing"


async def async_get_raw_capabilities(
    executor: CommandExecutorProtocol,
    *,
    gpu_info_cache_service: GPUInfoCacheServiceProtocol,
    gpu_vendor_detection_service: GPUVendorDetectionServiceProtocol,
    nvidia_nvml_gate: NvmlGateProtocol,
    nvidia_capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
    nvidia_settings_controller: NvidiaSettingsController | None,
    gpu_info: JSONDict | None = None,
    logger: TraceLogger | None = None,
) -> JSONDict:
    return await asyncio.to_thread(
        sync_get_raw_capabilities,
        executor,
        gpu_info_cache_service=gpu_info_cache_service,
        gpu_vendor_detection_service=gpu_vendor_detection_service,
        nvidia_nvml_gate=nvidia_nvml_gate,
        nvidia_capabilities_cache_service=nvidia_capabilities_cache_service,
        gpu_info=gpu_info,
        nvidia_settings_controller=nvidia_settings_controller,
        logger=logger,
    )

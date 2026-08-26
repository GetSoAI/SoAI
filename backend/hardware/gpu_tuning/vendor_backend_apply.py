"""SoAI - GPU tuning vendor backend application [backend/hardware/gpu_tuning/vendor_backend_apply.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.hardware.gpu_operation_results import build_gpu_result
from hardware.gpu_tuning.backend_apply_results import merge_backend_apply_result
from hardware.gpu_tuning.settings_request import build_gpu_settings_apply_request
from hardware.vendors.amd.settings import sync_set_amd_settings
from hardware.vendors.intel.settings import sync_set_intel_settings
from hardware.vendors.nvidia.tuning import sync_set_nvidia_settings
from hardware.vendors.vendor_types import AMD_VENDOR, INTEL_VENDOR, NVIDIA_VENDOR

if TYPE_CHECKING:
    from collections.abc import Mapping

    from core.logging.protocols import TraceLogger
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict
    from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies
    from hardware.gpu_tuning.settings_request import GpuSettingsApplyRequest
    from hardware.vendors.nvidia.smi import NvidiaSettingsController

__all__ = ("apply_vendor_backend_settings", "supports_vendor_backend_settings")

_SUPPORTED_VENDOR_SETTING_TYPES: tuple[str, ...] = (AMD_VENDOR, INTEL_VENDOR, NVIDIA_VENDOR)


def supports_vendor_backend_settings(vendor_type: str) -> bool:
    return vendor_type in _SUPPORTED_VENDOR_SETTING_TYPES


def apply_vendor_backend_settings(
    *,
    executor: CommandExecutorProtocol,
    logger: TraceLogger,
    nvidia_settings_controller: NvidiaSettingsController | None,
    gpu_services: GpuServiceDependencies,
    vendor_type: str,
    vendor_id: int,
    grouped_settings: Mapping[str, JSONDict],
    capabilities: JSONDict | None,
) -> tuple[JSONDict, bool]:
    apply_result = build_gpu_result()
    apply_messages = apply_result.get("messages")
    apply_errors = apply_result.get("errors")
    if not isinstance(apply_messages, list) or not isinstance(apply_errors, list):
        return (
            build_gpu_result(
                errors=["GPU apply result payload is invalid."],
                changed=False,
            ),
            False,
        )
    backend_changed = False
    for control_backend, backend_settings in grouped_settings.items():
        request = build_gpu_settings_apply_request(
            backend_settings,
            control_backend=control_backend,
        )
        backend_result = _apply_vendor_settings(
            executor=executor,
            logger=logger,
            nvidia_settings_controller=nvidia_settings_controller,
            gpu_services=gpu_services,
            vendor_type=vendor_type,
            vendor_id=vendor_id,
            request=request,
            capabilities=capabilities,
        )
        has_backend_errors, backend_mutated = merge_backend_apply_result(
            apply_result,
            backend_result,
        )
        backend_changed = backend_changed or backend_mutated
        if has_backend_errors:
            break
    apply_result["changed"] = backend_changed
    return apply_result, backend_changed


def _apply_vendor_settings(
    *,
    executor: CommandExecutorProtocol,
    logger: TraceLogger,
    nvidia_settings_controller: NvidiaSettingsController | None,
    gpu_services: GpuServiceDependencies,
    vendor_type: str,
    vendor_id: int,
    request: GpuSettingsApplyRequest,
    capabilities: JSONDict | None,
) -> JSONDict:
    if vendor_type == NVIDIA_VENDOR:
        return sync_set_nvidia_settings(
            logger,
            vendor_id,
            nvidia_settings_controller=nvidia_settings_controller,
            nvml_gate=gpu_services.nvidia_nvml_gate,
            capabilities_cache_service=gpu_services.nvidia_capabilities_cache_service,
            request=request,
            capabilities=capabilities,
        )
    if vendor_type == AMD_VENDOR:
        return sync_set_amd_settings(
            executor,
            logger,
            vendor_id,
            request=request,
            capabilities=capabilities,
        )
    if vendor_type == INTEL_VENDOR:
        return sync_set_intel_settings(
            executor,
            logger,
            vendor_id,
            request=request,
            capabilities=capabilities,
        )
    return build_gpu_result(errors=["Unknown GPU vendor"], changed=False)

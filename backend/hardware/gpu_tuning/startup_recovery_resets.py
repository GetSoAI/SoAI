"""SoAI - GPU startup dirty recovery reset selection [backend/hardware/gpu_tuning/startup_recovery_resets.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.gpu_settings_contract import (
    GPU_CLOCK_SETTING_FIELDS,
    GPU_RESET_CLOCKS_FIELD,
    GPU_SETTING_FAN_SPEED_FIELD,
    GPU_SETTING_POWER_LIMIT_FIELD,
)
from hardware.gpu_inventory.identity import normalize_gpu_index
from hardware.gpu_tuning.gpu_settings import async_set_gpu_settings
from hardware.gpu_tuning.result_flags import is_success_result
from hardware.gpu_tuning.setting_capabilities import setting_descriptor_for_key
from hardware.gpu_tuning.slot_capabilities import async_get_tuning_capabilities

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from hardware.gpu_tuning.gpu_settings import GpuSettingsApplyDependencies

__all__ = ("apply_dirty_recovery_gpu_resets",)

OPERATION_HARDWARE_GPU_TUNING_STARTUP_RECOVERY_RESETS = (
    "hardware.gpu_tuning.startup_recovery_resets"
)


def _capability_supported(capabilities_entry: JSONDict, setting_key: str) -> bool:
    descriptor = setting_descriptor_for_key(setting_key)
    if descriptor is None:
        return False
    value = capabilities_entry.get(descriptor.caps_key)
    return isinstance(value, dict) and value.get("supported") is True


def _shared_clock_backend_available(capabilities_entry: JSONDict) -> bool:
    backends: set[str] = set()
    for setting_key in GPU_CLOCK_SETTING_FIELDS:
        descriptor = setting_descriptor_for_key(setting_key)
        if descriptor is None:
            continue
        value = capabilities_entry.get(descriptor.caps_key)
        if not isinstance(value, dict) or value.get("supported") is not True:
            continue
        backend = value.get("control_backend")
        if isinstance(backend, str) and backend:
            backends.add(backend)
    return len(backends) == 1


def _build_dirty_recovery_settings(capabilities_entry: JSONDict) -> JSONDict:
    settings: JSONDict = {}
    if _capability_supported(capabilities_entry, GPU_SETTING_POWER_LIMIT_FIELD):
        settings[GPU_SETTING_POWER_LIMIT_FIELD] = "auto"
    if _capability_supported(capabilities_entry, GPU_SETTING_FAN_SPEED_FIELD):
        settings[GPU_SETTING_FAN_SPEED_FIELD] = "auto"
    if _shared_clock_backend_available(capabilities_entry):
        settings[GPU_RESET_CLOCKS_FIELD] = True
    return settings


async def apply_dirty_recovery_gpu_resets(
    *,
    settings_deps: GpuSettingsApplyDependencies,
) -> None:
    logger = settings_deps.logger
    try:
        capabilities = await async_get_tuning_capabilities(
            executor=settings_deps.executor,
            gpu_services=settings_deps.gpu_services,
            logger=logger,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to probe GPU capabilities for dirty startup recovery.",
            operation=OPERATION_HARDWARE_GPU_TUNING_STARTUP_RECOVERY_RESETS,
            level="warning",
        )
        return
    gpus_value = capabilities.get("gpus")
    if not isinstance(gpus_value, dict):
        return
    for index_value, capabilities_value in gpus_value.items():
        gpu_index = normalize_gpu_index(index_value)
        if gpu_index is None or not isinstance(capabilities_value, dict):
            continue
        settings = _build_dirty_recovery_settings(capabilities_value)
        if settings:
            result = await async_set_gpu_settings(
                settings_deps,
                gpu_id=gpu_index,
                settings=settings,
            )
            if not is_success_result(
                result,
                logger=logger,
                operation="hardware.gpu_tuning.startup_recovery_resets.is_success_result",
            ):
                logger.warning("GPU dirty startup recovery reset failed for GPU %s.", gpu_index)

"""SoAI - GPU settings application [backend/hardware/gpu_tuning/gpu_settings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.hardware.protocols import GpuSlotStorageManagerProtocol
from core.logging.protocols import TraceLogger
from hardware.gpu_tuning.gpu_settings_sync_apply import sync_set_gpu_settings
from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies
from hardware.vendors.nvidia.smi import NvidiaSettingsController

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "GpuSettingsApplyDependencies",
    "async_set_gpu_settings",
    "async_set_gpu_settings_with_dependencies",
    "build_gpu_settings_apply_dependencies",
    "sync_set_gpu_settings",
)


@dataclass(frozen=True, slots=True)
class GpuSettingsApplyDependencies:
    executor: CommandExecutorProtocol
    logger: TraceLogger
    storage: GpuSlotStorageManagerProtocol
    detailed_gpu_info: bool
    nvidia_settings_controller: NvidiaSettingsController | None
    gpu_services: GpuServiceDependencies

    def __post_init__(self) -> None:
        require_dependencies(
            owner="GpuSettingsApplyDependencies",
            detailed_gpu_info=self.detailed_gpu_info,
            executor=self.executor,
            gpu_services=self.gpu_services,
            logger=self.logger,
            storage=self.storage,
        )


def build_gpu_settings_apply_dependencies(
    *,
    executor: CommandExecutorProtocol,
    logger: TraceLogger,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    nvidia_settings_controller: NvidiaSettingsController | None,
    gpu_services: GpuServiceDependencies,
) -> GpuSettingsApplyDependencies:
    return GpuSettingsApplyDependencies(
        executor=executor,
        logger=logger,
        storage=storage,
        detailed_gpu_info=detailed_gpu_info,
        nvidia_settings_controller=nvidia_settings_controller,
        gpu_services=gpu_services,
    )


async def async_set_gpu_settings(
    deps: GpuSettingsApplyDependencies,
    *,
    gpu_id: int | None = None,
    settings: Mapping[str, JSONValue],
    field_modes: Mapping[str, JSONValue] | None = None,
) -> JSONDict:
    field_modes_payload = dict(field_modes) if isinstance(field_modes, Mapping) else None
    return await asyncio.to_thread(
        sync_set_gpu_settings,
        executor=deps.executor,
        logger=deps.logger,
        storage=deps.storage,
        detailed_gpu_info=deps.detailed_gpu_info,
        nvidia_settings_controller=deps.nvidia_settings_controller,
        gpu_services=deps.gpu_services,
        gpu_id=gpu_id,
        settings=dict(settings),
        field_modes=field_modes_payload,
    )


async def async_set_gpu_settings_with_dependencies(
    *,
    executor: CommandExecutorProtocol,
    logger: TraceLogger,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    nvidia_settings_controller: NvidiaSettingsController | None,
    gpu_services: GpuServiceDependencies,
    gpu_id: int,
    settings: Mapping[str, JSONValue],
    field_modes: Mapping[str, JSONValue] | None = None,
) -> JSONDict:
    deps = build_gpu_settings_apply_dependencies(
        executor=executor,
        logger=logger,
        storage=storage,
        detailed_gpu_info=detailed_gpu_info,
        nvidia_settings_controller=nvidia_settings_controller,
        gpu_services=gpu_services,
    )
    return await async_set_gpu_settings(
        deps,
        gpu_id=gpu_id,
        settings=settings,
        field_modes=field_modes,
    )

"""SoAI - GPU tuning service capability refresh decisions [backend/hardware/gpu_tuning/service_capability_refresh.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.types.json import JSONDict
from hardware.gpu_tuning.backend_apply_results import gpu_apply_result_changed
from hardware.gpu_tuning.capabilities_refresh import (
    refresh_capabilities_after_settings_change,
)
from hardware.gpu_tuning.internal_protocols import (
    HardwareGpuTuningMutationServiceProtocol,
)
from hardware.operations import can_emit_events

__all__ = ("refresh_capabilities_if_gpu_apply_changed",)


async def refresh_capabilities_if_gpu_apply_changed(
    service: HardwareGpuTuningMutationServiceProtocol,
    result: JSONDict,
) -> None:
    if (
        gpu_apply_result_changed(result)
        and service.event_bus is not None
        and can_emit_events(service.event_bus, service.main_loop)
    ):
        await refresh_capabilities_after_settings_change(
            executor=service.executor,
            gpu_services=service.gpu_services,
            enrich_gpu_capabilities=service.enrich_gpu_capabilities,
            event_bus=service.event_bus,
            main_loop=service.main_loop,
            cancellation_binder=service.cancellation_binder,
            finalizer_tracker=service.finalizer_tracker,
            logger=service.logger,
            probe_timeout_seconds=service.gpu_capabilities_probe_timeout_seconds,
        )

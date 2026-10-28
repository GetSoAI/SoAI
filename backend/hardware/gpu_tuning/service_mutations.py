"""SoAI - GPU tuning service mutation flows [backend/hardware/gpu_tuning/service_mutations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from hardware.gpu_tuning.direct_apply import apply_gpu_settings_direct
from hardware.gpu_tuning.gpu_settings import async_set_gpu_settings
from hardware.gpu_tuning.mutation_policy import hardware_mutation_disabled_payload
from hardware.gpu_tuning.request_handler import handle_gpu_settings_request
from hardware.gpu_tuning.service_parsing import prepare_settings_payload
from hardware.operations import can_emit_events

if TYPE_CHECKING:
    from collections.abc import Mapping

    from core.hardware.types import GPUSettingsOutcome
    from core.types.json import JSONDict, JSONValue
    from hardware.gpu_tuning.internal_protocols import (
        HardwareGpuTuningMutationServiceProtocol,
    )

__all__ = (
    "apply_gpu_settings_direct_for_service",
    "process_gpu_settings_request_for_service",
)


async def apply_gpu_settings_direct_for_service(
    service: HardwareGpuTuningMutationServiceProtocol,
    device_id: str,
    settings: JSONDict,
) -> JSONDict:
    if service.runtime_flags.hardware_mutation_disabled:
        return hardware_mutation_disabled_payload()
    capabilities = await service.get_gpu_capabilities()
    if service.runtime_flags.hardware_mutation_disabled:
        return hardware_mutation_disabled_payload()
    result = await apply_gpu_settings_direct(
        settings_deps=service.gpu_settings_apply_deps,
        dirty_flag_path=service.dirty_flag_path,
        device_id=device_id,
        settings=settings,
        capabilities_snapshot=capabilities,
    )
    return result


async def process_gpu_settings_request_for_service(
    service: HardwareGpuTuningMutationServiceProtocol,
    payload: Mapping[str, JSONValue],
) -> GPUSettingsOutcome:
    async def apply_update(settings_payload: JSONDict) -> JSONDict:
        if service.runtime_flags.hardware_mutation_disabled:
            return hardware_mutation_disabled_payload()
        gpu_id, cleaned_payload = prepare_settings_payload(settings_payload)
        return await async_set_gpu_settings(
            service.gpu_settings_apply_deps,
            gpu_id=gpu_id,
            settings=cleaned_payload,
        )

    outcome, publish_caps_event = await handle_gpu_settings_request(
        payload=payload,
        apply_gpu_settings_direct=service.apply_gpu_settings_direct_unlocked,
        apply_gpu_settings_update=apply_update,
    )
    event_bus = service.event_bus
    if (
        publish_caps_event
        and event_bus is not None
        and can_emit_events(event_bus, service.main_loop)
    ):
        service.logger.trace(
            "GPU settings changed hardware state, rescheduling capabilities update event.",
        )
        service.reschedule_gpu_capabilities_refresh()
    return outcome

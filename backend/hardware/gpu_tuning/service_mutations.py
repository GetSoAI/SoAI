"""SoAI - GPU tuning service mutation flows [backend/hardware/gpu_tuning/service_mutations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from hardware.gpu_tuning.backend_apply_results import gpu_apply_result_changed
from hardware.gpu_tuning.direct_apply import apply_gpu_settings_direct
from hardware.gpu_tuning.events import emit_active_slot_event
from hardware.gpu_tuning.gpu_settings import async_set_gpu_settings
from hardware.gpu_tuning.mutation_policy import hardware_mutation_disabled_payload
from hardware.gpu_tuning.request_handler import handle_gpu_settings_request
from hardware.gpu_tuning.result_flags import is_success_result
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

RESULT_LOGGER_NAME = "SoAI.hardware.gpu_tuning.service_parsing"


async def apply_gpu_settings_direct_for_service(
    service: HardwareGpuTuningMutationServiceProtocol,
    device_id: str,
    settings: JSONDict,
) -> JSONDict:
    if service.runtime_flags.hardware_mutation_disabled:
        return hardware_mutation_disabled_payload()
    capabilities = await service.get_cached_gpu_capabilities()
    if capabilities is None:
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
    if gpu_apply_result_changed(result):
        service.invalidate_gpu_caches()
    if is_success_result(
        result,
        logger=get_logger(RESULT_LOGGER_NAME),
        operation="hardware.gpu_tuning.service.is_success_result",
        recover_message="Failed to parse boolean flag (non-critical).",
    ) and can_emit_events(service.event_bus, service.main_loop):
        applied_at_value = result.get("applied_at")
        applied_at = applied_at_value if isinstance(applied_at_value, str) else None
        emit_active_slot_event(
            event_bus=service.event_bus,
            main_loop=service.main_loop,
            cancellation_binder=service.cancellation_binder,
            finalizer_tracker=service.finalizer_tracker,
            logger=service.logger,
            device_id=device_id,
            slot_id=None,
            signature=None,
            applied_at=applied_at,
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
    if publish_caps_event:
        service.invalidate_gpu_caches()
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

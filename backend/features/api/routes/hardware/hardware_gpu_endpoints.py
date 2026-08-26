"""SoAI - GPU tuning and slot management API routes [backend/features/api/routes/hardware/hardware_gpu_endpoints.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from core.errors.exceptions import StateError
from core.hardware.protocols import HardwareGpuTuningProtocol
from core.logging.trace import get_logger
from core.state.access import AccessAction
from core.validation.runtime import is_success_payload
from features.api.runtime.access_dependencies import (
    require_action_dependencies,
    restart_protected_dependencies,
)
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import (
    ApiContext,
    raise_api_error,
    resolve_api_context,
)
from features.api.runtime.gpu_slot_error_responses import raise_slot_operation_error
from features.api.schemas.hardware import (
    GPUSettingsRequest,
    GPUSlotApplyRequest,
    GPUSlotClearRequest,
    GPUSlotPreviewRequest,
    GPUSlotStoreRequest,
    GPUSlotToggleBootRequest,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

    type SlotOperationPayload = (
        GPUSlotStoreRequest | GPUSlotApplyRequest | GPUSlotToggleBootRequest | GPUSlotClearRequest
    )

__all__ = (
    "apply_gpu_slot_api",
    "clear_gpu_slot_api",
    "list_gpu_slots_api",
    "preview_gpu_slot_api",
    "register_endpoints",
    "register_routes",
    "set_gpu_settings",
    "store_gpu_slot_api",
    "toggle_gpu_slot_boot_api",
)

LOGGER_NAME = "SoAI.features.api.hardware_gpu_endpoints"


def _is_successful_gpu_route_payload(result: JSONDict) -> bool:
    return is_success_payload(
        result,
        get_logger(LOGGER_NAME),
        operation="api_hardware.gpu.is_success_payload",
        recover_message="Failed to parse GPU operation success flag (non-critical).",
    )


def _raise_if_gpu_route_payload_failed(request: Request, result: JSONDict) -> None:
    if not _is_successful_gpu_route_payload(result):
        raise_slot_operation_error(request, result)


async def set_gpu_settings(
    request: Request,
    payload: GPUSettingsRequest,
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    outcome = await api_context.dependencies.hw_gpu_tuning.process_gpu_settings_request(
        payload.to_gpu_settings_payload(),
    )
    log_audit_event(request, outcome.audit_action, outcome.audit_target, outcome.audit_details)
    if not outcome.success:
        raise_api_error(
            request,
            outcome.status_code,
            outcome.error_type or "gpu_error",
            outcome.error_message or "GPU settings operation failed.",
            extra=outcome.error_detail,
        )
    return JSONResponse(status_code=outcome.status_code, content=outcome.payload or {})


async def list_gpu_slots_api(
    request: Request,
    device_id: str | None = Query(None),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    result = await api_context.dependencies.hw_gpu_tuning.list_gpu_slots(device_id=device_id)
    _raise_if_gpu_route_payload_failed(request, result)
    return JSONResponse(content=result)


async def _execute_slot_operation(
    operation: str,
    request: Request,
    slot: str,
    payload: SlotOperationPayload,
    hw_mgr: HardwareGpuTuningProtocol,
) -> JSONDict:
    if operation == "store":
        if not isinstance(payload, GPUSlotStoreRequest):
            raise StateError("Invalid payload type for store operation")
        details = {
            "device_id": payload.device_id,
            "slot": slot,
            "apply_at_boot": payload.apply_at_boot,
        }
        target = f"gpu_slot:{payload.device_id}:{slot}"
        log_audit_event(request, "STORE_GPU_SLOT", target, details)
        result = await hw_mgr.store_gpu_slot(
            payload.device_id,
            slot,
            payload.settings,
            field_modes=payload.field_modes,
            apply_at_boot=payload.apply_at_boot,
        )
    elif operation == "apply":
        if not isinstance(payload, GPUSlotApplyRequest):
            raise StateError("Invalid payload type for apply operation")
        details = {
            "device_id": payload.device_id,
            "slot": slot,
            "apply_at_boot": payload.apply_at_boot,
        }
        target = f"gpu_slot:{payload.device_id}:{slot}"
        log_audit_event(request, "APPLY_GPU_SLOT", target, details)
        result = await hw_mgr.apply_gpu_slot(
            payload.device_id,
            slot,
            apply_at_boot=payload.apply_at_boot,
        )
    elif operation == "toggle_boot":
        if not isinstance(payload, GPUSlotToggleBootRequest):
            raise StateError("Invalid payload type for toggle_boot operation")
        details = {
            "device_id": payload.device_id,
            "slot": slot,
            "enabled": payload.enabled,
        }
        target = f"gpu_slot:{payload.device_id}:{slot}"
        log_audit_event(request, "TOGGLE_GPU_SLOT_BOOT", target, details)
        result = await hw_mgr.toggle_gpu_slot_boot(payload.device_id, slot, payload.enabled)
    elif operation == "clear":
        if not isinstance(payload, GPUSlotClearRequest):
            raise StateError("Invalid payload type for clear operation")
        details = {"device_id": payload.device_id, "slot": slot}
        target = f"gpu_slot:{payload.device_id}:{slot}"
        log_audit_event(request, "CLEAR_GPU_SLOT", target, details)
        result = await hw_mgr.clear_gpu_slot(payload.device_id, slot)
    else:
        raise StateError(f"Unknown GPU slot operation: {operation}")
    _raise_if_gpu_route_payload_failed(request, result)
    return result


async def store_gpu_slot_api(
    request: Request,
    slot: str,
    payload: GPUSlotStoreRequest,
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    result = await _execute_slot_operation(
        "store",
        request,
        slot,
        payload,
        api_context.dependencies.hw_gpu_tuning,
    )
    return JSONResponse(content=result)


async def preview_gpu_slot_api(
    request: Request,
    slot: str,
    payload: GPUSlotPreviewRequest,
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    result = await api_context.dependencies.hw_gpu_tuning.preview_gpu_slot(payload.device_id, slot)
    _raise_if_gpu_route_payload_failed(request, result)
    return JSONResponse(content=result)


async def apply_gpu_slot_api(
    request: Request,
    slot: str,
    payload: GPUSlotApplyRequest,
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    result = await _execute_slot_operation(
        "apply",
        request,
        slot,
        payload,
        api_context.dependencies.hw_gpu_tuning,
    )
    return JSONResponse(content=result)


async def toggle_gpu_slot_boot_api(
    request: Request,
    slot: str,
    payload: GPUSlotToggleBootRequest,
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    result = await _execute_slot_operation(
        "toggle_boot",
        request,
        slot,
        payload,
        api_context.dependencies.hw_gpu_tuning,
    )
    return JSONResponse(content=result)


async def clear_gpu_slot_api(
    request: Request,
    slot: str,
    payload: GPUSlotClearRequest,
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONResponse:
    result = await _execute_slot_operation(
        "clear",
        request,
        slot,
        payload,
        api_context.dependencies.hw_gpu_tuning,
    )
    return JSONResponse(content=result)


def register_endpoints(router: APIRouter) -> None:
    hardware_read_deps = require_action_dependencies(AccessAction.HARDWARE_READ)
    gpu_tuning_deps = require_action_dependencies(AccessAction.HW_GPU_TUNING)
    restart_gpu_tuning_deps = tuple(restart_protected_dependencies(AccessAction.HW_GPU_TUNING))
    router.post("/gpu/settings", dependencies=restart_gpu_tuning_deps)(set_gpu_settings)
    router.get("/gpu/slots", dependencies=hardware_read_deps)(list_gpu_slots_api)
    router.post(
        "/gpu/slots/{slot}/store",
        dependencies=restart_gpu_tuning_deps,
    )(store_gpu_slot_api)
    router.post("/gpu/slots/{slot}/preview", dependencies=gpu_tuning_deps)(preview_gpu_slot_api)
    router.post(
        "/gpu/slots/{slot}/apply",
        dependencies=restart_gpu_tuning_deps,
    )(apply_gpu_slot_api)
    router.patch(
        "/gpu/slots/{slot}/boot",
        dependencies=restart_gpu_tuning_deps,
    )(toggle_gpu_slot_boot_api)
    router.delete(
        "/gpu/slots/{slot}",
        dependencies=restart_gpu_tuning_deps,
    )(clear_gpu_slot_api)


def register_routes(routers: ApiRouters) -> None:
    register_endpoints(routers.hardware)

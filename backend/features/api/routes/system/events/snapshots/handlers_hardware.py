"""SoAI - Snapshot handlers for hardware resources [backend/features/api/routes/system/events/snapshots/handlers_hardware.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import WebSocket

from core.errors.exceptions import ValidationError
from core.hardware.soaibench_limits import (
    SOAIBENCH_HISTORY_DEFAULT_LIMIT,
    SOAIBENCH_LIST_MAX_LIMIT,
    SOAIBENCH_LIST_MIN_LIMIT,
    SOAIBENCH_RUNS_DEFAULT_LIMIT,
)
from core.validation.integers import is_positive_strict_int
from core.validation.numbers import coerce_int_clamped_with_default
from features.api.schemas.hardware import (
    GPUSettingsRequest,
    GPUSlotApplyRequest,
    GPUSlotPreviewRequest,
    GPUSlotStoreRequest,
    GPUSoAIBenchStartRequest,
    KillProcessRequest,
)
from features.api.streaming.websocket import WebsocketConnection

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "snapshot_hardware_capabilities",
    "snapshot_hardware_gpu_capabilities",
    "snapshot_hardware_gpu_settings_update",
    "snapshot_hardware_gpu_slot_apply",
    "snapshot_hardware_gpu_slot_preview",
    "snapshot_hardware_gpu_slot_store",
    "snapshot_hardware_gpu_slots",
    "snapshot_hardware_gpu_soaibench_history",
    "snapshot_hardware_gpu_soaibench_runs",
    "snapshot_hardware_gpu_soaibench_start",
    "snapshot_hardware_gpu_soaibench_status",
    "snapshot_hardware_gpu_soaibench_stop",
    "snapshot_hardware_process_kill",
    "snapshot_hardware_processes",
    "snapshot_hardware_snapshot",
)


async def snapshot_hardware_snapshot(
    data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    components_value = data.get("components")
    if isinstance(components_value, list):
        components = [item for item in components_value if isinstance(item, str) and item.strip()]
    else:
        components = None
    return await connection.api_context.dependencies.hw_manager.get_system_info(
        components=components or None,
    )


async def snapshot_hardware_capabilities(
    data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    _ = data
    return await connection.api_context.dependencies.hw_manager.get_system_capabilities()


async def snapshot_hardware_gpu_capabilities(
    data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    _ = data
    return await connection.api_context.dependencies.hw_manager.get_gpu_capabilities()


async def snapshot_hardware_gpu_settings_update(
    data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    payload = GPUSettingsRequest.model_validate(data)
    outcome = await connection.api_context.dependencies.hw_gpu_tuning.process_gpu_settings_request(
        payload.model_dump(),
    )
    if not outcome.success:
        raise ValidationError(outcome.error_message or "GPU settings operation failed.")
    return outcome.payload or {}


async def snapshot_hardware_gpu_soaibench_start(
    data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    payload = GPUSoAIBenchStartRequest.model_validate(data)
    return await connection.api_context.dependencies.hardware_soaibench.start_run(
        device_id=payload.device_id,
        profile=payload.profile,
        benchmark_mode=payload.benchmark_mode,
        temperature_limit_celsius=payload.temperature_limit_celsius,
        created_by_user_id=_require_user_id(connection),
        created_by_tool="hardware_page",
    )


async def snapshot_hardware_gpu_soaibench_status(
    data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    return await connection.api_context.dependencies.hardware_soaibench.get_run(
        run_id=_required_text(data, "run_id"),
        user_id=_require_user_id(connection),
    )


async def snapshot_hardware_gpu_soaibench_stop(
    data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    return await connection.api_context.dependencies.hardware_soaibench.stop_run(
        run_id=_required_text(data, "run_id"),
        user_id=_require_user_id(connection),
    )


async def snapshot_hardware_gpu_soaibench_history(
    data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    limit = coerce_int_clamped_with_default(
        data.get("history_limit"),
        default=SOAIBENCH_HISTORY_DEFAULT_LIMIT,
        fallback=SOAIBENCH_HISTORY_DEFAULT_LIMIT,
        minimum=SOAIBENCH_LIST_MIN_LIMIT,
        maximum=SOAIBENCH_LIST_MAX_LIMIT,
    )
    return await connection.api_context.dependencies.hardware_soaibench.list_history(
        device_id=_required_text(data, "device_id"),
        user_id=_require_user_id(connection),
        limit=limit,
    )


async def snapshot_hardware_gpu_soaibench_runs(
    data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    limit = coerce_int_clamped_with_default(
        data.get("limit"),
        default=SOAIBENCH_RUNS_DEFAULT_LIMIT,
        fallback=SOAIBENCH_RUNS_DEFAULT_LIMIT,
        minimum=SOAIBENCH_LIST_MIN_LIMIT,
        maximum=SOAIBENCH_LIST_MAX_LIMIT,
    )
    return await connection.api_context.dependencies.hardware_soaibench.list_runs(
        user_id=_require_user_id(connection),
        limit=limit,
    )


async def snapshot_hardware_gpu_slots(
    data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    device_value = data.get("device_id")
    device_id = (
        device_value.strip() if isinstance(device_value, str) and device_value.strip() else None
    )
    return await connection.api_context.dependencies.hw_gpu_tuning.list_gpu_slots(
        device_id=device_id,
    )


async def snapshot_hardware_gpu_slot_preview(
    data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    payload = GPUSlotPreviewRequest.model_validate(data)
    slot_value = data.get("slot")
    slot = slot_value.strip() if isinstance(slot_value, str) and slot_value.strip() else ""
    if not slot:
        raise ValidationError("slot is required")
    result = await connection.api_context.dependencies.hw_gpu_tuning.preview_gpu_slot(
        payload.device_id,
        slot,
    )
    if not isinstance(result, dict):
        raise ValidationError("GPU slot preview returned invalid payload")
    return result


async def snapshot_hardware_gpu_slot_apply(
    data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    payload = GPUSlotApplyRequest.model_validate(data)
    slot_value = data.get("slot")
    slot = slot_value.strip() if isinstance(slot_value, str) and slot_value.strip() else ""
    if not slot:
        raise ValidationError("slot is required")
    result = await connection.api_context.dependencies.hw_gpu_tuning.apply_gpu_slot(
        payload.device_id,
        slot,
        apply_at_boot=payload.apply_at_boot,
    )
    if not isinstance(result, dict):
        raise ValidationError("GPU slot apply returned invalid payload")
    return result


async def snapshot_hardware_gpu_slot_store(
    data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    payload = GPUSlotStoreRequest.model_validate(data)
    slot_value = data.get("slot")
    slot = slot_value.strip() if isinstance(slot_value, str) and slot_value.strip() else ""
    if not slot:
        raise ValidationError("slot is required")
    result = await connection.api_context.dependencies.hw_gpu_tuning.store_gpu_slot(
        payload.device_id,
        slot,
        payload.settings,
        field_modes=payload.field_modes,
        apply_at_boot=payload.apply_at_boot,
    )
    if not isinstance(result, dict):
        raise ValidationError("GPU slot store returned invalid payload")
    return result


async def snapshot_hardware_processes(
    data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    filter_value = data.get("filter")
    filter_str = filter_value if isinstance(filter_value, str) else None
    processes = await connection.api_context.dependencies.terminal.get_process_list(
        filter_str=filter_str,
    )
    return processes or []


async def snapshot_hardware_process_kill(
    data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    pid_value = data.get("pid")
    if not is_positive_strict_int(pid_value):
        raise ValidationError("hardware.process.kill snapshot requires integer pid > 0")
    payload = KillProcessRequest.model_validate(
        {"signal": data.get("signal"), "use_sudo": data.get("use_sudo")},
    )
    success, message = await connection.api_context.dependencies.terminal.kill_process(
        pid=pid_value,
        signal_to_send=int(payload.signal),
        use_sudo=bool(payload.use_sudo),
    )
    if not success:
        raise ValidationError(message)
    return {"status": "success", "message": message}


def _require_user_id(connection: WebsocketConnection) -> int:
    user_id_value = connection.user.get("id")
    if not is_positive_strict_int(user_id_value):
        raise ValidationError("Authenticated user id is required for SoAIBench.")
    return user_id_value


def _required_text(data: JSONDict, key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{key} is required.")
    return value.strip()

"""SoAI - Complete physical native preparation and receipt-bound GPU application [backend/hardware/gpu_tuning/vendor_backend_apply.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from collections.abc import Mapping

from core.concurrency.protocols import CancellationTokenProtocol
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.hardware.gpu_control_operation_types import (
    GPUClockConversionUnavailableError,
    GPUControlPreflightRejection,
)
from core.hardware.gpu_control_types import GPUControlResult, GPUPreparedControl
from core.hardware.gpu_physical_identity import GPUPhysicalDevice
from core.hardware.gpu_recovery_records import GPURecoveryRecord
from core.hardware.gpu_settings_contract import GPU_DIRECT_SETTING_FIELDS
from core.hardware.protocols import GPUControlRecoveryProtocol
from core.logging.protocols import TraceLogger
from core.system.protocols import CommandExecutorProtocol
from core.types.json import JSONDict
from core.validation.strings import require_canonical_trimmed_json_text
from hardware.gpu_tuning.native_backend_execution import NativeBackendExecution
from hardware.gpu_tuning.native_backend_resources import native_backend_resources
from hardware.gpu_tuning.native_operation_execution import (
    execute_native_control_record,
    execute_native_original_record,
)
from hardware.gpu_tuning.native_plan_composition import merge_prepared_native_records
from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies
from hardware.vendors.amd.adl_settings import prepare_adl_control_record
from hardware.vendors.amd.control_preparation import prepare_amd_control_record
from hardware.vendors.intel.control_preparation import (
    prepare_i915_control_record,
    prepare_intel_control_record,
)
from hardware.vendors.nvidia.control_preparation import prepare_nvml_control_record
from hardware.vendors.nvidia.nvapi_control_preparation import prepare_nvapi_control_record
from hardware.vendors.nvidia.settings_control_preparation import prepare_settings_control_record
from hardware.vendors.nvidia.smi import NvidiaSettingsController

OPERATION_HARDWARE_GPU_PREPARE_NATIVE_CONTROL = "hardware.gpu.prepare_native_control"


__all__ = (
    "supports_vendor_backend_settings",
    "prepare_vendor_backend_settings",
    "apply_vendor_backend_settings",
    "restore_vendor_backend_originals",
)


def supports_vendor_backend_settings(vendor_type: str) -> bool:
    return vendor_type in ("nvidia", "amd", "intel")


def prepare_vendor_backend_settings(
    *,
    executor: CommandExecutorProtocol,
    logger: TraceLogger,
    nvidia_settings_controller: NvidiaSettingsController | None,
    gpu_services: GpuServiceDependencies,
    target: GPUPhysicalDevice,
    operation_id: str,
    normalized_settings: JSONDict,
    requested_modes: JSONDict,
    grouped_settings: Mapping[str, JSONDict],
    clock_control_types: Mapping[str, str] | None,
) -> GPURecoveryRecord | GPUControlPreflightRejection:
    require_canonical_trimmed_json_text(operation_id, error_message="GPU operation ID is invalid.")
    if (
        not normalized_settings
        or not set(normalized_settings).issubset(GPU_DIRECT_SETTING_FIELDS)
        or set(normalized_settings) != set(requested_modes)
        or any(mode not in ("auto", "manual") for mode in requested_modes.values())
    ):
        raise ValidationError(
            "GPU preparation requires complete normalized user settings and modes."
        )
    fields: set[str] = set()
    grouped = copy.deepcopy(dict(grouped_settings))
    for settings in grouped.values():
        if not settings or fields.intersection(settings):
            raise ValidationError("GPU preparation requires distinct complete native field routes.")
        if any(normalized_settings.get(field) != value for field, value in settings.items()):
            raise ValidationError("GPU native grouping conflicts with the frozen user request.")
        fields.update(settings)
    if fields != set(normalized_settings):
        raise ValidationError("GPU native grouping omits or adds normalized user fields.")
    for public_backend, native_backend in (
        ("nvidia_nvml", "nvml"),
        ("nvidia_nvapi", "nvapi"),
    ):
        if public_backend in grouped:
            settings = grouped.pop(public_backend)
            if native_backend not in grouped:
                grouped[native_backend] = {}
            grouped[native_backend].update(settings)
    if nvidia_settings_controller is not gpu_services.nvidia_settings_controller:
        raise ValidationError(
            "GPU preparation must retain the selected settings resource authority."
        )
    conversion = tuple(
        field
        for field in grouped.get("nvapi", {})
        if field in ("power_limit", "core_clock", "mem_clock")
        and requested_modes[field] == "manual"
    )
    try:
        with native_backend_resources(
            executor=executor,
            logger=logger,
            gpu_services=gpu_services,
            backends=tuple(grouped),
            conversion_fields=conversion,
            goal="requested",
        ) as boundary:
            plans: list[GPURecoveryRecord] = []
            for backend, settings in grouped.items():
                modes = {field: requested_modes[field] for field in settings}
                plan = _prepare_backend(
                    boundary, target, operation_id, backend, settings, modes, clock_control_types
                )
                if isinstance(plan, GPUControlPreflightRejection):
                    return plan
                plans.append(plan)
            return merge_prepared_native_records(target, operation_id, plans)
    except GPUClockConversionUnavailableError as exception:
        return GPUControlPreflightRejection(str(exception.code), str(exception))
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="GPU native preparation did not complete (non-critical).",
            operation=OPERATION_HARDWARE_GPU_PREPARE_NATIVE_CONTROL,
            details={"operation_id": operation_id, "device_id": target.device_id},
            level="trace",
        )
        return GPUControlPreflightRejection("native_query_failed", "GPU native preparation failed.")


def _prepare_backend(
    boundary: NativeBackendExecution,
    target: GPUPhysicalDevice,
    operation_id: str,
    backend: str,
    settings: JSONDict,
    modes: JSONDict,
    clock_control_types: Mapping[str, str] | None,
) -> GPURecoveryRecord | GPUControlPreflightRejection:
    expected_vendor = {
        "nvml": "nvidia",
        "nvapi": "nvidia",
        "nvidia_settings": "nvidia",
        "amd_smi": "amd",
        "amd_adl": "amd",
        "amd_overdrive": "amd",
        "intel_xpum": "intel",
        "intel_i915": "intel",
    }.get(backend)
    if expected_vendor is not None and target.vendor != expected_vendor:
        raise ValidationError("GPU native backend conflicts with the actual selected vendor.")
    if backend == "nvml" and boundary.nvml_module is not None:
        return prepare_nvml_control_record(
            boundary.nvml_module,
            target=target,
            operation_id=operation_id,
            requested_settings=settings,
            requested_modes=modes,
            modern_function_resolver=boundary.resolver,
            clock_control_types=(
                {
                    field: control_type
                    for field, control_type in clock_control_types.items()
                    if field in settings
                }
                if clock_control_types is not None
                else None
            ),
        )
    if backend == "nvapi" and boundary.query_interface is not None:
        return prepare_nvapi_control_record(
            boundary.executor,
            target=target,
            executable=boundary.gpu_services.nvidia_smi_executable,
            query_interface=boundary.query_interface,
            nvml_module=boundary.nvml_module,
            operation_id=operation_id,
            requested_settings=settings,
            requested_modes=modes,
        )
    if backend == "nvidia_settings" and boundary.settings_session is not None:
        return prepare_settings_control_record(
            boundary.settings_session,
            target=target,
            operation_id=operation_id,
            requested_settings=settings,
            requested_modes=modes,
        )
    if backend == "amd_adl" and boundary.adl_session is not None:
        return prepare_adl_control_record(
            boundary.adl_session,
            boundary.executor,
            target=target,
            operation_id=operation_id,
            requested_settings=settings,
            requested_modes=modes,
        )
    if backend in ("amd_smi", "amd_overdrive"):
        return prepare_amd_control_record(
            boundary.executor,
            target=target,
            operation_id=operation_id,
            control_backend=backend,
            requested_settings=settings,
            requested_modes=modes,
        )
    if backend == "intel_i915":
        if not boundary.gpu_services.nvidia_nvml_gate.runtime_platform.is_linux:
            return GPUControlPreflightRejection(
                "native_control_unsupported", "i915 frequency requires its Linux native route."
            )
        return prepare_i915_control_record(
            target=target,
            operation_id=operation_id,
            requested_settings=settings,
            requested_modes=modes,
        )
    if backend == "intel_xpum":
        return prepare_intel_control_record(
            boundary.executor,
            target=target,
            executable=boundary.gpu_services.intel_executable,
            operation_id=operation_id,
            requested_settings=settings,
            requested_modes=modes,
        )
    return GPUControlPreflightRejection(
        "native_query_failed" if expected_vendor == "nvidia" else "native_control_unsupported",
        "The selected native backend or facility is unavailable.",
    )


def apply_vendor_backend_settings(
    *,
    executor: CommandExecutorProtocol,
    logger: TraceLogger,
    nvidia_settings_controller: NvidiaSettingsController | None,
    gpu_services: GpuServiceDependencies,
    target: GPUPhysicalDevice,
    record: GPURecoveryRecord,
    prepared: GPUPreparedControl,
    recovery: GPUControlRecoveryProtocol,
    cancellation_token: CancellationTokenProtocol,
) -> tuple[GPUControlResult, GPUPreparedControl]:
    if nvidia_settings_controller is not gpu_services.nvidia_settings_controller:
        raise ValidationError("GPU application changed its settings resource authority.")
    backends = tuple(dict.fromkeys(member.backend for member in record.members if member.backend))
    conversion = tuple(
        member.field
        for member in record.members
        if member.backend == "nvapi"
        and record.requested_modes[member.field] == "manual"
        and member.field in ("power_limit", "core_clock", "mem_clock")
    )
    with native_backend_resources(
        executor=executor,
        logger=logger,
        gpu_services=gpu_services,
        backends=backends,
        conversion_fields=conversion,
        goal="requested",
    ) as boundary:
        return execute_native_control_record(
            target=target,
            record=record,
            prepared=prepared,
            recovery=recovery,
            cancellation_token=cancellation_token,
            logger=logger,
            preflight=boundary.preflight,
            invoke_member=boundary.invoke_member,
        )


def restore_vendor_backend_originals(
    *,
    executor: CommandExecutorProtocol,
    logger: TraceLogger,
    nvidia_settings_controller: NvidiaSettingsController | None,
    gpu_services: GpuServiceDependencies,
    target: GPUPhysicalDevice,
    record: GPURecoveryRecord,
    prepared: GPUPreparedControl,
    recovery: GPUControlRecoveryProtocol,
    cancellation_token: CancellationTokenProtocol,
) -> tuple[GPUControlResult, GPUPreparedControl]:
    if nvidia_settings_controller is not gpu_services.nvidia_settings_controller:
        raise ValidationError("GPU restoration changed its settings resource authority.")
    with native_backend_resources(
        executor=executor,
        logger=logger,
        gpu_services=gpu_services,
        backends=tuple(
            dict.fromkeys(member.backend for member in record.members if member.backend)
        ),
        conversion_fields=(),
        goal="original",
    ) as boundary:
        return execute_native_original_record(
            target=target,
            record=record,
            prepared=prepared,
            recovery=recovery,
            cancellation_token=cancellation_token,
            logger=logger,
            original_member_order=boundary.original_member_order(record),
            preflight=boundary.preflight,
            invoke_member=boundary.invoke_member,
        )

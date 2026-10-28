"""SoAI - Exhaustive GPU startup accounting and canonical cleanup targets [backend/hardware/gpu_tuning/startup_scope_accounting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.hardware.gpu_physical_identity import (
    GPUInventoryReadState,
    GPUPhysicalBindingState,
    GPUPhysicalDevice,
    GPUPhysicalSnapshot,
    GPUVendorObservation,
    gpu_physical_device_observations,
)
from core.hardware.gpu_recovery_records import (
    GPUOriginalObservationState,
    GPURecoveryRecord,
    GPUStartupLegacyCommit,
    GPUStartupLegacyRecoveryRecord,
    GPUStartupRecoveryRecord,
)
from core.validation.strings import require_canonical_trimmed_json_text
from hardware.gpu_inventory.physical_binding import match_gpu_physical_identity
from hardware.gpu_tuning.control_recovery_records import require_record_target
from hardware.gpu_tuning.control_recovery_serialization import encode_recovery_record
from hardware.gpu_tuning.startup_scope_types import (
    GPUControlStartupScope,
    GPUStartupRecordedGoal,
    GPUStartupScopePolicy,
)
from hardware.presets.gpu_recovery_format import decode_gpu_recovery_record
from hardware.vendors.vendor_types import AMD_VENDOR, INTEL_VENDOR, NVIDIA_VENDOR, UNKNOWN_VENDOR

__all__ = (
    "require_complete_startup_accounting",
    "startup_cleanup_targets",
    "require_empty_startup_accounting",
    "same_startup_physical_device",
    "startup_absent_native_vendors",
    "startup_darwin_intel_route_inapplicable",
)


def require_complete_startup_accounting(scope: GPUControlStartupScope) -> None:
    if not isinstance(scope, GPUControlStartupScope):
        raise ValidationError("GPU startup accounting requires its complete typed scope.")
    require_canonical_trimmed_json_text(
        scope.physical_snapshot.acquisition_id,
        error_message="GPU startup physical acquisition is invalid.",
    )
    if not isinstance(scope.physical_snapshot.devices, tuple) or any(
        not isinstance(device, GPUPhysicalDevice) for device in scope.physical_snapshot.devices
    ):
        raise ValidationError("GPU startup physical devices require immutable actual observations.")
    expected: list[
        tuple[GPURecoveryRecord, GPUStartupRecordedGoal, GPUStartupLegacyCommit | None]
    ] = []
    initial_devices: set[str] = set()
    initial_operations: set[str] = set()
    for outer_record in scope.initial_records:
        operation_ids: tuple[str, ...]
        if (
            decode_gpu_recovery_record(outer_record.device_id, encode_recovery_record(outer_record))
            != outer_record
        ):
            raise ValidationError("GPU startup initial record scope is malformed.")
        if outer_record.device_id in initial_devices:
            raise ValidationError("GPU startup initial records duplicate durable device scope.")
        initial_devices.add(outer_record.device_id)
        if isinstance(outer_record, GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord):
            operation_ids = (
                outer_record.startup_operation_id,
                outer_record.legacy_record.operation_id,
            )
            if isinstance(outer_record, GPUStartupRecoveryRecord):
                operation_ids += (outer_record.original_record.operation_id,)
                expected.append(
                    (outer_record.original_record, GPUStartupRecordedGoal.ORIGINAL, None)
                )
            goal = (
                GPUStartupRecordedGoal.UNCOMMITTED_LEGACY
                if outer_record.legacy_commit is None
                else GPUStartupRecordedGoal.COMMITTED_LEGACY_TARGET
            )
            expected.append((outer_record.legacy_record, goal, outer_record.legacy_commit))
        else:
            operation_ids = (outer_record.operation_id,)
            expected.append((outer_record, GPUStartupRecordedGoal.ORIGINAL, None))
        if initial_operations.intersection(operation_ids):
            raise ValidationError("GPU startup initial operation scopes are duplicated.")
        initial_operations.update(operation_ids)
    if len(scope.recorded) != len(expected):
        raise ValidationError("GPU startup accounting omits or adds an initial record goal.")
    observed_operations: set[str] = set()
    for row in scope.recorded:
        operation_id = row.record.operation_id
        if (
            operation_id in observed_operations
            or (row.record, row.goal, row.legacy_commit) not in expected
        ):
            raise ValidationError(
                "GPU startup accounting changes or duplicates an initial record goal."
            )
        observed_operations.add(operation_id)
        if row.state == GPUPhysicalBindingState.BOUND:
            if row.target is None:
                raise ValidationError("GPU startup bound recorded target is missing.")
            require_record_target(row.record, row.target)
    plan = scope.legacy_plan
    if scope.policy == GPUStartupScopePolicy.RECORDED_RECOVERY:
        return
    if plan is None or plan.physical_snapshot != scope.physical_snapshot:
        raise ValidationError("GPU startup legacy accounting conflicts with physical acquisition.")
    native_routes: set[tuple[str, str]] = set()
    all_devices = list(scope.physical_snapshot.devices)
    for roster in plan.rosters:
        route = (roster.vendor, roster.backend)
        if (
            route in native_routes
            or roster.acquisition_id != scope.physical_snapshot.acquisition_id
        ):
            raise ValidationError(
                "GPU startup native roster acquisition or route is contradictory."
            )
        native_routes.add(route)
        for device in roster.devices:
            if not any(same_startup_physical_device(device, existing) for existing in all_devices):
                all_devices.append(device)
    for device in all_devices:
        if sum(same_startup_physical_device(device, row.target) for row in plan.devices) != 1:
            raise ValidationError(
                "GPU startup legacy accounting omits or duplicates an actual peer."
            )
    for device_plan in plan.devices:
        if not any(
            same_startup_physical_device(device_plan.target, device) for device in all_devices
        ):
            raise ValidationError("GPU startup legacy accounting invents an actual peer.")
        if device_plan.record is not None:
            require_record_target(device_plan.record, device_plan.target)


def startup_cleanup_targets(scope: GPUControlStartupScope) -> tuple[GPUPhysicalDevice, ...]:
    require_complete_startup_accounting(scope)
    targets = [
        row.target
        for row in scope.recorded
        if row.state == GPUPhysicalBindingState.BOUND and row.target is not None
    ]
    if scope.legacy_plan is not None:
        targets.extend(
            row.target
            for row in scope.legacy_plan.devices
            if row.rejection is None
            and (
                row.record is not None
                or (
                    row.facilities
                    and all(
                        facility.state == GPUOriginalObservationState.UNSUPPORTED
                        for facility in row.facilities
                    )
                )
            )
        )
    unique: list[GPUPhysicalDevice] = []
    for target in targets:
        previous = next((device for device in unique if device.device_id == target.device_id), None)
        if previous is not None:
            if not same_startup_physical_device(target, previous):
                raise ValidationError("GPU startup cleanup has ambiguous canonical lease identity.")
            continue
        unique.append(target)
    return tuple(unique)


def require_empty_startup_accounting(scope: GPUControlStartupScope) -> None:
    require_complete_startup_accounting(scope)
    plan = scope.legacy_plan
    if (
        scope.policy != GPUStartupScopePolicy.HISTORICAL_WHOLE_POOL
        or scope.initial_records
        or scope.recorded
    ):
        raise ValidationError(
            "GPU startup empty admission cannot omit historical or recorded obligations."
        )
    if scope.physical_snapshot.devices or len(scope.physical_snapshot.vendors) != 4:
        raise ValidationError(
            "GPU startup empty admission requires exhaustive empty physical scope."
        )
    if any(
        not isinstance(vendor, GPUVendorObservation) for vendor in scope.physical_snapshot.vendors
    ):
        raise ValidationError(
            "GPU startup empty admission physical vendor observations are invalid."
        )
    if {vendor.vendor for vendor in scope.physical_snapshot.vendors} != {
        NVIDIA_VENDOR,
        AMD_VENDOR,
        INTEL_VENDOR,
        UNKNOWN_VENDOR,
    }:
        raise ValidationError("GPU startup empty admission omits physical vendor scope.")
    if any(
        not isinstance(vendor.state, GPUInventoryReadState)
        or vendor.state != GPUInventoryReadState.OBSERVED
        for vendor in scope.physical_snapshot.vendors
    ):
        raise ValidationError("GPU startup empty admission has unavailable physical coverage.")
    if plan is None or plan.devices or not plan.rosters:
        raise ValidationError(
            "GPU startup empty admission requires actual empty native accounting."
        )
    if any(
        roster.state != GPUInventoryReadState.OBSERVED or roster.devices for roster in plan.rosters
    ):
        raise ValidationError(
            "GPU startup empty admission has unavailable or nonempty native scope."
        )


def same_startup_physical_device(first: GPUPhysicalDevice, second: GPUPhysicalDevice) -> bool:
    return (
        first.device_id == second.device_id
        and match_gpu_physical_identity(
            gpu_physical_device_observations(first), gpu_physical_device_observations(second)
        )
        == GPUPhysicalBindingState.BOUND
    )


def startup_absent_native_vendors(
    snapshot: GPUPhysicalSnapshot,
    initial_records: tuple[
        GPURecoveryRecord | GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord, ...
    ],
    acquisition_id: str,
) -> set[str]:
    if snapshot.acquisition_id != acquisition_id:
        raise ValidationError("Native negative presence requires its actual physical acquisition.")
    if (
        len(snapshot.vendors) != 4
        or {row.vendor for row in snapshot.vendors} != {"nvidia", "amd", "intel", "unknown"}
        or any(row.state != GPUInventoryReadState.OBSERVED for row in snapshot.vendors)
    ):
        return set()
    required = {device.vendor for device in snapshot.devices}
    for outer in initial_records:
        records = (
            (outer.original_record, outer.legacy_record)
            if isinstance(outer, GPUStartupRecoveryRecord)
            else (
                (outer.legacy_record,)
                if isinstance(outer, GPUStartupLegacyRecoveryRecord)
                else (outer,)
            )
        )
        for record in records:
            for member in record.members:
                backend = member.backend
                if backend in ("nvml", "nvapi", "nvidia_smi", "nvidia_settings"):
                    required.add("nvidia")
                elif backend in ("amd_smi", "amd_overdrive", "amd_adl"):
                    required.add("amd")
                elif backend in ("intel_xpum", "intel_i915"):
                    required.add("intel")
                else:
                    return set()
    return {"nvidia", "amd", "intel"} - required


def startup_darwin_intel_route_inapplicable(
    snapshot: GPUPhysicalSnapshot,
    initial_records: tuple[
        GPURecoveryRecord | GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord, ...
    ],
) -> bool:
    if (
        len(snapshot.vendors) != 4
        or {row.vendor for row in snapshot.vendors} != {"nvidia", "amd", "intel", "unknown"}
        or any(row.state != GPUInventoryReadState.OBSERVED for row in snapshot.vendors)
    ):
        return False
    intel_devices = tuple(device for device in snapshot.devices if device.vendor == "intel")
    if not intel_devices or any(
        device.identity.native_device_path is None
        or not device.identity.native_device_path.startswith("darwin:ioreg:IOService:/")
        or device.platform_driver != "IOPCIDevice"
        for device in intel_devices
    ):
        return False
    for outer in initial_records:
        records = (
            (outer.original_record, outer.legacy_record)
            if isinstance(outer, GPUStartupRecoveryRecord)
            else (
                (outer.legacy_record,)
                if isinstance(outer, GPUStartupLegacyRecoveryRecord)
                else (outer,)
            )
        )
        if any(
            member.backend
            not in ("nvml", "nvapi", "nvidia_smi", "nvidia_settings", "amd_smi", "amd_overdrive")
            for record in records
            for member in record.members
        ):
            return False
    return True

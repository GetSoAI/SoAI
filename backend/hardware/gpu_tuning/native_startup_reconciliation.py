"""SoAI - Fresh native startup reconciliation and goal verification [backend/hardware/gpu_tuning/native_startup_reconciliation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_physical_identity import GPUPhysicalDevice
from core.hardware.gpu_recovery_records import GPURecoveryRecord
from core.validation.strings import require_canonical_trimmed_json_text
from hardware.gpu_tuning.control_recovery_records import (
    require_application_targets,
    require_record_target,
)
from hardware.gpu_tuning.control_recovery_serialization import recovery_scope_digest
from hardware.gpu_tuning.native_backend_observations import (
    acquire_native_actuator_footprint,
)
from hardware.gpu_tuning.native_backend_resources import native_backend_resources
from hardware.gpu_tuning.startup_scope_accounting import (
    require_empty_startup_accounting,
)
from hardware.gpu_tuning.startup_scope_acquisition import build_gpu_control_startup_scope
from hardware.gpu_tuning.startup_scope_types import (
    GPUControlStartupScope,
    GPUStartupPromotionProof,
    GPUStartupScopePolicy,
)

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.runtime.protocols import RuntimePlatformViewProtocol
    from core.system.protocols import CommandExecutorProtocol
    from hardware.gpu_inventory.executable_resolution import GpuExecutableResolution
    from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies


__all__ = (
    "verify_observed_empty_startup_scope",
    "derive_startup_record_promotion",
    "validate_startup_record_promotion",
)


def verify_observed_empty_startup_scope(
    scope: GPUControlStartupScope,
    *,
    executor: CommandExecutorProtocol,
    logger: TraceLogger,
    gpu_services: GpuServiceDependencies,
    acquisition_id: str,
) -> None:
    require_empty_startup_accounting(scope)
    fresh = build_gpu_control_startup_scope(
        policy=GPUStartupScopePolicy.HISTORICAL_WHOLE_POOL,
        initial_records=scope.initial_records,
        acquisition_id=acquisition_id,
        executor=executor,
        logger=logger,
        gpu_services=gpu_services,
        runtime_platform=gpu_services.nvidia_nvml_gate.runtime_platform,
        intel_executable=gpu_services.intel_executable,
    )
    initial_plan, fresh_plan = scope.legacy_plan, fresh.legacy_plan
    if initial_plan is None or fresh_plan is None:
        raise ValidationError(
            "GPU startup empty verification requires actual complete native acquisition."
        )
    if {(row.vendor, row.backend) for row in initial_plan.rosters} != {
        (row.vendor, row.backend) for row in fresh_plan.rosters
    }:
        raise ValidationError(
            "GPU startup empty verification omits or invents an actual native route."
        )
    require_empty_startup_accounting(fresh)


def derive_startup_record_promotion(
    original_record: GPURecoveryRecord,
    legacy_record: GPURecoveryRecord,
    *,
    target: GPUPhysicalDevice,
    executor: CommandExecutorProtocol,
    logger: TraceLogger,
    gpu_services: GpuServiceDependencies,
    runtime_platform: RuntimePlatformViewProtocol,
    acquisition_id: str,
    intel_executable: GpuExecutableResolution,
) -> GPUStartupPromotionProof:
    if (
        runtime_platform is not gpu_services.nvidia_nvml_gate.runtime_platform
        or intel_executable is not gpu_services.intel_executable
    ):
        raise ValidationError("GPU startup promotion changed its actual acquisition resources.")
    require_canonical_trimmed_json_text(
        acquisition_id, error_message="GPU startup promotion acquisition is invalid."
    )
    original_record, legacy_record = copy.deepcopy(original_record), copy.deepcopy(legacy_record)
    require_record_target(original_record, target)
    require_record_target(legacy_record, target)
    require_application_targets(legacy_record)
    if original_record.operation_id == legacy_record.operation_id:
        raise ValidationError("GPU startup promotion requires distinct original and legacy scopes.")
    backends = tuple(
        dict.fromkeys(
            member.backend
            for record in (original_record, legacy_record)
            for member in record.members
            if member.backend is not None
        )
    )
    with native_backend_resources(
        executor=executor,
        logger=logger,
        gpu_services=gpu_services,
        backends=backends,
        conversion_fields=(),
        goal="original",
    ) as boundary:
        protected = tuple(
            acquire_native_actuator_footprint(boundary, original_record, target, member)
            for member in original_record.members
        )
        actuators = tuple(
            acquire_native_actuator_footprint(boundary, legacy_record, target, member)
            for member in legacy_record.members
        )
    protected_fields = {field for footprint in protected for field in footprint.affected_fields}
    protected_keys = {key for footprint in protected for key in footprint.native_member_keys}
    if any(
        protected_fields.intersection(footprint.affected_fields)
        or protected_keys.intersection(footprint.native_member_keys)
        for footprint in actuators
    ):
        raise ValidationError(
            "GPU startup legacy setter footprint overlaps original-governed scope."
        )
    return GPUStartupPromotionProof(
        target,
        recovery_scope_digest(original_record),
        recovery_scope_digest(legacy_record),
        acquisition_id,
        actuators,
    )


def validate_startup_record_promotion(
    proof: GPUStartupPromotionProof,
    original_record: GPURecoveryRecord,
    legacy_record: GPURecoveryRecord,
    *,
    target: GPUPhysicalDevice,
    executor: CommandExecutorProtocol,
    logger: TraceLogger,
    gpu_services: GpuServiceDependencies,
    runtime_platform: RuntimePlatformViewProtocol,
    acquisition_id: str,
    intel_executable: GpuExecutableResolution,
) -> None:
    actual = derive_startup_record_promotion(
        original_record,
        legacy_record,
        target=target,
        executor=executor,
        logger=logger,
        gpu_services=gpu_services,
        runtime_platform=runtime_platform,
        acquisition_id=acquisition_id,
        intel_executable=intel_executable,
    )
    if not isinstance(proof, GPUStartupPromotionProof) or proof != actual:
        raise ValidationError("GPU startup promotion changed its actual native footprint proof.")

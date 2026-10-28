"""SoAI - Sole fresh physical and native startup scope acquisition [backend/hardware/gpu_tuning/startup_scope_acquisition.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from dataclasses import replace
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_physical_identity import (
    GPUPhysicalBindingResult,
    GPUPhysicalBindingState,
    GPUPhysicalDevice,
    gpu_physical_device_observations,
)
from core.hardware.gpu_recovery_records import (
    GPURecoveryRecord,
    GPUStartupLegacyCommit,
    GPUStartupLegacyRecoveryRecord,
    GPUStartupRecoveryRecord,
)
from hardware.gpu_inventory.executable_resolution import require_gpu_executable_selector
from hardware.gpu_inventory.physical_binding import (
    match_gpu_physical_identity,
    resolve_gpu_physical_binding,
)
from hardware.gpu_inventory.physical_snapshot import acquire_gpu_physical_snapshot
from hardware.gpu_tuning.startup_legacy_planning import plan_gpu_legacy_reset_device
from hardware.gpu_tuning.startup_native_rosters import acquire_startup_native_rosters
from hardware.gpu_tuning.startup_scope_types import (
    GPUControlLegacyResetPlan,
    GPUControlStartupScope,
    GPULegacyResetRoster,
    GPUStartupRecordedGoal,
    GPUStartupRecordedScope,
    GPUStartupScopePolicy,
)

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.runtime.protocols import RuntimePlatformViewProtocol
    from core.system.protocols import CommandExecutorProtocol
    from hardware.gpu_inventory.executable_resolution import GpuExecutableResolution
    from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies


__all__ = ("build_gpu_control_startup_scope",)


def build_gpu_control_startup_scope(
    *,
    executor: CommandExecutorProtocol,
    logger: TraceLogger,
    gpu_services: GpuServiceDependencies,
    runtime_platform: RuntimePlatformViewProtocol,
    acquisition_id: str,
    intel_executable: GpuExecutableResolution,
    policy: GPUStartupScopePolicy,
    initial_records: tuple[
        GPURecoveryRecord | GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord, ...
    ],
) -> GPUControlStartupScope:
    if (
        runtime_platform is not gpu_services.nvidia_nvml_gate.runtime_platform
        or intel_executable is not gpu_services.intel_executable
    ):
        raise ValidationError(
            "GPU startup acquisition resources do not share their actual authority."
        )
    require_gpu_executable_selector(intel_executable, executable="xpu-smi")
    if not isinstance(policy, GPUStartupScopePolicy) or not isinstance(initial_records, tuple):
        raise ValidationError("GPU startup acquisition policy or initial records are invalid.")
    records = copy.deepcopy(initial_records)
    snapshot = acquire_gpu_physical_snapshot(
        executor, runtime_platform=runtime_platform, acquisition_id=acquisition_id
    )
    rosters = acquire_startup_native_rosters(
        executor,
        logger,
        gpu_services,
        acquisition_id,
        physical_snapshot=snapshot,
        initial_records=records,
    )
    peers = list(snapshot.devices)
    for roster in rosters:
        for target in roster.devices:
            matches = [
                index
                for index, peer in enumerate(peers)
                if _relation(target, peer) == GPUPhysicalBindingState.BOUND
            ]
            binding = resolve_gpu_physical_binding(
                gpu_physical_device_observations(target),
                [gpu_physical_device_observations(peer) for peer in peers],
            )
            if binding.state == GPUPhysicalBindingState.BOUND and len(matches) == 1:
                index = matches[0]
                merged = resolve_gpu_physical_binding(
                    gpu_physical_device_observations(peers[index]),
                    [gpu_physical_device_observations(target)],
                )
                if merged.device is None:
                    raise ValidationError("GPU startup actual peer merge lost its proved relation.")
                peers[index] = merged.device
            else:
                peers.append(target)
    recorded: list[GPUStartupRecordedScope] = []
    for outer in records:
        children: tuple[
            tuple[GPURecoveryRecord, GPUStartupRecordedGoal, GPUStartupLegacyCommit | None], ...
        ]
        if isinstance(outer, GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord):
            goal = (
                GPUStartupRecordedGoal.UNCOMMITTED_LEGACY
                if outer.legacy_commit is None
                else GPUStartupRecordedGoal.COMMITTED_LEGACY_TARGET
            )
            children = ((outer.legacy_record, goal, outer.legacy_commit),)
            if isinstance(outer, GPUStartupRecoveryRecord):
                children = (
                    (outer.original_record, GPUStartupRecordedGoal.ORIGINAL, None),
                ) + children
        else:
            children = ((outer, GPUStartupRecordedGoal.ORIGINAL, None),)
        for record, goal, commit in children:
            binding = _record_target(record, peers)
            recorded_target = binding.device
            if recorded_target is not None:
                for index, peer in enumerate(peers):
                    if _relation(recorded_target, peer) == GPUPhysicalBindingState.BOUND:
                        peers[index] = replace(peer, device_id=recorded_target.device_id)
            recorded.append(
                GPUStartupRecordedScope(
                    record,
                    goal,
                    recorded_target,
                    commit,
                    binding.state,
                    binding.reason_code,
                )
            )
    projected: list[GPUPhysicalDevice] = []
    for physical in snapshot.devices:
        physical_matches = [
            peer for peer in peers if _relation(physical, peer) == GPUPhysicalBindingState.BOUND
        ]
        projected.append(physical_matches[0] if len(physical_matches) == 1 else physical)
    snapshot = replace(snapshot, devices=tuple(projected))
    if policy == GPUStartupScopePolicy.RECORDED_RECOVERY:
        return GPUControlStartupScope(policy, snapshot, records, tuple(recorded), None)
    canonical_rosters: list[GPULegacyResetRoster] = []
    for roster in rosters:
        devices: list[GPUPhysicalDevice] = []
        for native in roster.devices:
            native_matches = [
                peer for peer in peers if _relation(native, peer) == GPUPhysicalBindingState.BOUND
            ]
            devices.append(
                replace(native, device_id=native_matches[0].device_id)
                if len(native_matches) == 1
                else native
            )
        canonical_rosters.append(replace(roster, devices=tuple(devices)))
    rosters = tuple(canonical_rosters)
    device_plans = tuple(
        plan_gpu_legacy_reset_device(
            target,
            executor=executor,
            logger=logger,
            gpu_services=gpu_services,
            operation_id=f"{acquisition_id}:legacy:{target.device_id}",
            rosters=rosters,
            initial_records=records,
        )
        for target in peers
    )
    return GPUControlStartupScope(
        policy,
        snapshot,
        records,
        tuple(recorded),
        GPUControlLegacyResetPlan(snapshot, rosters, device_plans),
    )


def _relation(first: GPUPhysicalDevice, second: GPUPhysicalDevice) -> GPUPhysicalBindingState:
    return match_gpu_physical_identity(
        gpu_physical_device_observations(first), gpu_physical_device_observations(second)
    )


def _record_target(
    record: GPURecoveryRecord, peers: list[GPUPhysicalDevice]
) -> GPUPhysicalBindingResult:
    backend_vendors = {
        "amd_smi": "amd",
        "amd_adl": "amd",
        "amd_overdrive": "amd",
        "intel_xpum": "intel",
        "intel_i915": "intel",
        "nvml": "nvidia",
        "nvapi": "nvidia",
        "nvidia_settings": "nvidia",
    }
    vendors = {
        backend_vendors[member.backend]
        for member in record.members
        if member.backend in backend_vendors
    }
    if (
        len(vendors) != 1
        or any(member.backend not in backend_vendors for member in record.members)
        or record.pci_bdf_observations is None
    ):
        return GPUPhysicalBindingResult(
            GPUPhysicalBindingState.IDENTITY_UNAVAILABLE,
            None,
            "recorded_physical_authority_unavailable",
        )
    target = GPUPhysicalDevice(
        record.device_id,
        next(iter(vendors)),
        record.physical_identity,
        None,
        None,
        record.pci_bdf_observations,
    )
    binding = resolve_gpu_physical_binding(
        gpu_physical_device_observations(target),
        [gpu_physical_device_observations(peer) for peer in peers],
    )
    return GPUPhysicalBindingResult(
        binding.state,
        target if binding.state == GPUPhysicalBindingState.BOUND else None,
        binding.reason_code,
    )
